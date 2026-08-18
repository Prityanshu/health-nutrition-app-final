"""
ConversationManager - a single conversational assistant that can call the
existing specialist services as tools.

DESIGN
------
The old ChatbotManager treated ChefGenius / FitMentor / etc. as *routes*: every
message was classified by keyword scoring and handed to one service, which then
answered in isolation. That produced agent ping-pong, because routing ran again
on every turn and a single stray word ("want", "fat") could flip the target.

Here there is exactly ONE assistant. It holds the conversation, remembers what
was said, asks its own follow-up questions, and calls a specialist service only
once it has enough information. The specialists are unchanged - they are simply
exposed to the model as callable tools.

    user message
        -> load history from ChatMessage
        -> [system + profile] + history + [user]
        -> Groq (with tool schemas attached)
        -> model either REPLIES (asking follow-ups itself) or CALLS a tool
        -> tool output is the answer for generator tools
        -> persist and return

Notes on two deliberate choices:

1. Generator tools are *terminal*. A recipe or 7-day plan is already polished
   markdown; feeding it back through the model to be "narrated" would cost a
   second round-trip and thousands of tokens for no gain. So the tool's output
   is returned to the user directly.

2. History sent to the model is truncated per-message (see _HISTORY_CHAR_CAP).
   The database keeps the full text for rendering in the UI, but a 3000-token
   meal plan does not need to occupy the prompt on every subsequent turn.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq as GroqClient
from sqlalchemy.orm import Session

from app.config.groq_config import (
    get_orchestrator_model,
    groq_config,
    handle_groq_error,
    mark_groq_success,
)
from app.database import ChatMessage, Goal, User

# Reuse the module-level singletons rather than constructing a second copy of
# every service. Each construction builds an agno Agent plus its own Groq
# client, and these modules already instantiate one at import time - so
# creating our own doubled the count for no benefit. The services are
# stateless with respect to users (all per-user state lives in the database),
# so sharing them is safe.
from app.services.advanced_meal_planner_service import advanced_meal_planner_service
from app.services.budgetchef_service import budgetchef_service
from app.services.chefgenius_service import chefgenius_service
from app.services.culinaryexplorer_service import culinaryexplorer_service
from app.services.fitmentor_service import fitmentor_service
from app.services.nutrient_analyzer_service import nutrient_analyzer_service

logger = logging.getLogger(__name__)

# Orchestrator model. Separate from the generators' model so the two draw on
# separate per-model daily quotas - see groq_config for the reasoning.
MODEL_ID = get_orchestrator_model()

# How many prior turns to replay to the model.
#
# These numbers are a token budget, not a preference. Groq's free tier caps
# tokens per DAY, and it counts input + max_tokens on every call - so a
# generous reservation costs quota even when the reply is short. At the old
# settings a single message cost ~4k tokens, which exhausted a 100k daily
# allowance in about 25 messages.
_HISTORY_TURNS = 6
# Per-message cap when replaying history. Long generated plans are summarised
# down to their opening lines so the model remembers *that* it produced a plan
# without carrying the whole thing forward.
_HISTORY_CHAR_CAP = 500
# Upper bound on reply length. Generators produce the long artifacts; the
# orchestrator only needs enough room to converse or emit a tool call.
_MAX_REPLY_TOKENS = 700
# Ceiling on a single user message. Assistant messages were already truncated,
# but a pasted article went in verbatim - and then again on every following
# turn as history. ~4000 characters is roughly 1000 tokens, generous for
# anything typed and firm enough to stop a paste from eating the day's quota.
_USER_CHAR_CAP = 4000


def tidy_truncated(text: str) -> str:
    """
    Salvage a reply that hit the token ceiling.

    A conversational answer that stops at "| Mixed frozen veg" reads as a
    crash. Cutting back to the last complete sentence or list item and saying
    so is honest and looks deliberate - and it gives the user an obvious way to
    get the rest.
    """
    if not text:
        return text

    stripped = text.rstrip()

    # Drop trailing structure that was never finished: table rows, and then any
    # heading or list marker left dangling above them once they are gone.
    lines = stripped.splitlines()
    while lines and lines[-1].lstrip().startswith("|"):
        lines.pop()
    while lines and re.fullmatch(r"\s*(?:[-*•]|\d+[.)]|#{1,6})\s*\S{0,40}\s*", lines[-1]):
        lines.pop()
    stripped = "\n".join(lines).rstrip()

    removed_structure = len(lines) != len(text.rstrip().splitlines())

    # If it does not end on punctuation, the last sentence was cut mid-word -
    # back off to the last one that finished. The negative lookbehind stops
    # "1." in a numbered list counting as a sentence end, which would otherwise
    # leave the reply ending on a bare list marker.
    trimmed_sentence = False
    if stripped and stripped[-1] not in ".!?:":
        ends = [m.end() for m in re.finditer(r"(?<!\d)[.!?](?=\s|$)", stripped)]
        # Keep the cut only if a usable sentence survives; below roughly this
        # length the truncation happened so early that trimming would delete
        # the answer rather than tidy it.
        if ends and ends[-1] >= 25:
            stripped = stripped[: ends[-1]]
            trimmed_sentence = True

    stripped = stripped.rstrip()
    if not stripped:
        return "Let me start that again - ask me once more and I'll keep it shorter."

    if removed_structure or trimmed_sentence:
        return stripped + "\n\nWant me to write the full version out properly?"
    return stripped


def clamp_user_message(message: str) -> str:
    """Trim an over-long message, telling the model what happened."""
    if not message or len(message) <= _USER_CHAR_CAP:
        return message
    return (
        message[:_USER_CHAR_CAP]
        + "\n\n[message truncated - if you need the rest, ask the user to summarise it]"
    )


INJURY_GUIDANCE = """
## Injuries and physical limitations - treat as safety-critical
If the user mentions an injury, pain, or a physical limitation at ANY point, it applies to everything you produce from then on. It never expires and you never silently drop it.

When an injury is mentioned AFTER you have already produced a plan, call refine_previous_output. Do not call the generator again from scratch - that discards the plan and routinely produces the same unsafe exercises.

When you pass an injury into a tool, translate it into concrete exclusions rather than repeating the user's words. The specialist services do not reason about anatomy for you.

Exclude movements on THREE grounds, not just the obvious one:
1. Direct contraction of the injured muscle
2. Loaded positions that lengthen or stretch it (commonly missed - a hip hinge loads the hamstring hard even though it "looks like" a back exercise)
3. Stretching and mobility work that takes it to end range

Mappings:
- Hamstring, especially upper/proximal near the sit bone -> exclude squats, deadlifts, Romanian deadlifts, good mornings, lunges, leg press, leg curls, sprinting, HIIT, box jumps AND all loaded hip hinges including bent-over barbell rows, T-bar rows and kettlebell swings, AND straight-leg raises, hanging leg raises, forward folds, seated hamstring stretches, downward dog and pike positions. Substitute chest-supported or seated rows for hinge-based rows, and bent-knee core work for straight-leg core work.
- Lower back -> exclude deadlifts, bent-over rows, heavy overhead press, weighted twists, sit-ups, leg raises
- Shoulder -> exclude overhead press, upright rows, dips, bench press near end range, behind-the-neck work
- Knee -> exclude deep squats, lunges, jumping, leg extensions under load, pistol squats

Never recommend unqualified "light yoga", "gentle stretching" or "active recovery" to someone with a soft-tissue injury - name the specific movements that are safe, because the generic version usually includes the exact stretch they must avoid.

After producing an adapted plan, state in one or two lines what you removed and why, so the user can see the injury was accounted for.

Whenever you produce a plan around a named injury, end with one short, plain line noting that an exercise plan is not rehab, and that a physio can tell them what their specific injury actually tolerates. Say it once, without drama, and do not repeat it on every subsequent message.

If they report sharp pain, numbness, swelling, giving way, or pain that is getting worse, do not hand over a modified plan as though the problem were solved - tell them plainly to get it looked at before training that area.

"""

# Deciding whether to spend ~700 tokens on the injury guidance.
#
# The first version was a substring scan over a list that included "back",
# "hip" and "ache". That fired on "get BACK into running", "HIP hop class" and
# "headACHE", and missed sciatica, asthma, plantar fasciitis and slipped disc
# entirely. Both failure modes matter: false positives burn the daily quota,
# false negatives produce a plan with no safety exclusions at all.
#
# So: match on word boundaries, and split the vocabulary into terms that are
# unambiguous on their own versus body parts that only count alongside a
# complaint.

# Unambiguous - if any of these appear, an injury or condition is in play.
_INJURY_TERMS = (
    # states
    "injury", "injured", "injuries", "sprain", "sprained", "strain", "strained",
    "torn", "tear", "ruptured", "rupture", "dislocated", "fracture", "fractured",
    "broken bone", "inflamed", "inflammation", "swollen", "swelling", "stiffness",
    # care
    "physio", "physiotherapy", "physical therapy", "rehab", "rehabilitation",
    "surgery", "post-op", "post op", "operated", "recovering from",
    # named conditions - the whole set the old list missed
    "sciatica", "shin splints", "plantar fasciitis", "tennis elbow",
    "golfer's elbow", "golfers elbow", "it band", "iliotibial", "runner's knee",
    "runners knee", "rotator cuff", "slipped disc", "herniated", "bulging disc",
    "meniscus", "acl", "mcl", "pcl", "labrum", "labral", "tendonitis",
    "tendinitis", "tendinopathy", "bursitis", "arthritis", "osteoarthritis",
    "frozen shoulder", "carpal tunnel", "achilles", "hernia", "scoliosis",
    "spondylitis", "asthma", "asthmatic", "epilepsy", "diabetic neuropathy",
    "vertigo", "concussion", "whiplash",
)

# Body parts. Only meaningful when a complaint word appears near them - which
# is what separates "my knee hurts" from "knee-high socks".
_BODY_PARTS = (
    "hamstring", "quad", "quadricep", "calf", "groin", "glute", "hip flexor",
    "shoulder", "knee", "elbow", "wrist", "ankle", "neck", "spine",
    "lower back", "upper back", "hip", "shin", "foot", "heel", "thigh", "chest",
)

_COMPLAINTS = (
    "pain", "painful", "hurt", "hurts", "hurting", "sore", "soreness", "ache",
    "aching", "aches", "niggle", "tight", "tightness", "issue", "problem",
    "trouble", "weak", "clicking", "locked", "gave way", "giving way", "flare",
    # How people usually describe doing it, rather than naming the injury.
    # These are safe next to a body part: "pulled pork" and "rolled oats" have
    # no body part in them, so they cannot reach this branch.
    "pulled", "pull", "tweaked", "tweak", "twisted", "rolled", "popped",
    "jammed", "stiff", "swelling", "bruised", "blown",
)

# Retained under the old name because scripts and tests reference it.
INJURY_TRIGGERS = _INJURY_TERMS + _BODY_PARTS


def _has_word(text: str, phrase: str) -> bool:
    """Whole-word / whole-phrase match, so 'hip' never fires inside 'hip hop'."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def mentions_injury(text: str) -> bool:
    """
    Whether this text implies an injury or physical condition.

    Body parts alone are not enough - "back", "hip" and "chest" appear in
    ordinary sentences constantly. They must be accompanied by a complaint.
    """
    if not text:
        return False
    lowered = text.lower()

    if any(_has_word(lowered, term) for term in _INJURY_TERMS):
        return True

    if any(_has_word(lowered, part) for part in _BODY_PARTS):
        if any(_has_word(lowered, word) for word in _COMPLAINTS):
            return True

    return False

# One definition of who the assistant is, shared by every prompt path.
#
# The greeting path used to declare its own thinner version, so the assistant's
# voice changed depending on whether you said "hi" or asked a question - which
# is exactly the tell that gives away a scripted bot.
PERSONA = """You are NutriCoach.

You are the user's coach, not a search engine and not a customer service bot. You have been working with this person over time: you know what they eat, what they are training for, and how their week is going. Speak like someone who already knows them.

Voice:
- Warm, direct, unfussy. A knowledgeable friend, not a brochure.
- Short sentences. No filler openers like "Certainly!" or "Great question!".
- Never introduce yourself again after the first message, and never list your features unless asked.
- Use what you know about them naturally, the way a person would - "that's your third paneer day this week" - rather than reciting their data back at them.
- Never announce that you are consulting their profile or logs. Just know it.
- One question at a time, and only when you actually need the answer.

Length and format - this matters:
- When you are TALKING, talk. Two to five sentences. No markdown tables, no ingredient costings, no numbered recipe steps, no emoji section headers.
- Suggesting what to eat is talking. Name two or three options in a sentence each, with the rough calories and protein, and stop. "Egg curry with two rotis gets you about 600 and 40g of protein. Or paneer bhurji if you want it faster."
- If they want the full thing - the actual recipe, the week of meals, the training plan - call the tool. That is what the tools are for, and their output is properly formatted.
- Never begin producing a long structured artifact in a normal reply. You will run out of room and stop mid-sentence, which looks broken.
"""

SYSTEM_PROMPT = PERSONA + """
You are a health, nutrition and fitness assistant.

You are ONE assistant having ONE continuous conversation. You are not a router and you never hand the user off. You remember everything said earlier in this conversation and build on it.

## Your tools
You can call specialist generators for recipes, workout plans, meal plans and nutrition analysis. Use them when the user actually wants that artifact produced.

## Talk first, tools second
Most messages do not need a tool. Only call one when the user is asking you to CREATE or CHANGE something right now.

Just reply normally - no tool - when the user is:
- greeting you or signing off ("hi", "hello", "hey", "good morning", "thanks", "bye")
- making small talk or reacting ("cool", "nice", "ok", "that looks good", "haha")
- asking what you can do, who you are, or how something works
- asking a general knowledge question ("is paneer high in protein?", "how much sleep do I need?", "why do I feel sore?")
- commenting on something you already produced without requesting a change

If someone says "hello", say hello back. Do not re-send a plan they already have. Never repeat a previously generated plan unless they explicitly ask to see it again.

Only call refine_previous_output when the user states a specific change they want made. "Add more protein", "make it cheaper", "I have a knee injury", "swap day 3" are change requests. "Thanks", "ok", "looks good", "hello" are not.

If you are unsure whether someone wants something generated, ask them in one short line instead of generating.

## When to ask vs. when to act
Ask a follow-up question ONLY when you genuinely cannot proceed without the answer. Then ask ONE question, conversationally, in your own words. Never present a bulleted form of fields to fill in.

Before asking anything, check:
- Did the user already tell you earlier in this conversation? Use it.
- Is it in their profile below? Use it.
- Can you pick a sensible default and mention your assumption? Prefer this.

Never ask more than two questions before producing something useful. If the user seems vague or is giving short answers, make reasonable assumptions, produce the result, and invite them to adjust it. A good plan with stated assumptions beats an interrogation.

## Style
Talk like a knowledgeable friend, not a form. Acknowledge what the user said before moving on. Keep replies tight. When you make an assumption, say so in one short line ("I've assumed gym access - tell me if it's home workouts and I'll swap the exercises").

If the user changes topic, follow them. If they refine something you just produced, adjust it rather than starting over.

## Safety
You are not a doctor. If asked about medication, diagnosis, disordered eating, or symptoms that need medical attention, say so plainly and suggest they talk to a professional. Do not produce extreme calorie restriction plans. If a user's stated goal looks unhealthy, say so kindly once, then help them toward a safer version.
"""


# --------------------------------------------------------------------------
# Tool schemas - what the model sees
# --------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "generate_recipe",
            "description": "Recipe from ingredients the user has on hand.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "All ingredients mentioned anywhere in the conversation.",
                    },
                    "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
                    "time_minutes": {"type": "integer"},
                    "dietary_restrictions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["ingredients"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_workout_plan",
            "description": "7-day workout plan. Use for training, muscle gain, fat loss.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fitness_goal": {
                        "type": "string",
                        "enum": ["muscle_gain", "weight_loss", "endurance", "flexibility", "general_fitness"],
                    },
                    "equipment": {"type": "string", "enum": ["gym", "home_equipment", "bodyweight"]},
                    "time_per_day": {"type": "integer"},
                    "activity_level": {
                        "type": "string",
                        "enum": ["sedentary", "lightly_active", "moderately_active", "very_active"],
                    },
                    "sport": {
                        "type": "string",
                        "description": (
                            "The sport or activity they train FOR, if they named one - "
                            "'football', 'cricket', 'running', 'swimming', 'climbing'. "
                            "Training for a sport is not the same as general fitness: it "
                            "needs the qualities that sport demands and must fit around "
                            "playing. Omit only if no sport was mentioned."
                        ),
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "SAFETY. Every injury/condition from the whole conversation plus "
                            "profile, each with the movements to avoid. Never drop one."
                        ),
                    },
                },
                "required": ["fitness_goal", "equipment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refine_previous_output",
            "description": (
                "Modify something you already produced when the user asks for a specific "
                "change ('make it cheaper', 'swap day 3', 'I have a knee injury'). Not for "
                "greetings, thanks or small talk."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "artifact_type": {
                        "type": "string",
                        "enum": ["workout_plan", "meal_plan", "recipe", "budget_meal_plan"],
                    },
                    "feedback": {
                        "type": "string",
                        "description": (
                            "What must change, as an instruction. For injuries, name the "
                            "exact movements to remove and what to substitute."
                        ),
                    },
                },
                "required": ["artifact_type", "feedback"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_regional_recipe",
            "description": "Recipe for a named dish or specific regional cuisine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cuisine_region": {"type": "string"},
                    "dish_name": {"type": "string"},
                    "dietary_restrictions": {"type": "array", "items": {"type": "string"}},
                    "time_minutes": {"type": "integer"},
                    "cooking_skill": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]},
                },
                "required": ["cuisine_region"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_budget_meal_plan",
            "description": "Meal plan constrained by a daily budget in rupees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "budget_per_day": {"type": "number"},
                    "calorie_target": {"type": "integer"},
                    "meals_per_day": {"type": "integer"},
                    "dietary_preferences": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["budget_per_day"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_weekly_meal_plan",
            "description": "Full 7-day meal plan. Heavy - prefer generate_recipe for one meal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_calories": {"type": "integer"},
                    "meals_per_day": {"type": "integer"},
                    "dietary_restrictions": {"type": "array", "items": {"type": "string"}},
                    "food_preferences": {"type": "array", "items": {"type": "string"}},
                    "region_or_cuisine": {"type": "string"},
                    "user_notes": {"type": "string"},
                },
                "required": ["target_calories"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_food_nutrition",
            "description": (
                "Nutrition breakdown of a food. Only when the user explicitly asks what is "
                "IN it - not merely because a food was mentioned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "food_name": {"type": "string"},
                    "serving_size": {"type": "string"},
                },
                "required": ["food_name"],
            },
        },
    },
]


# Messages that are purely social. When the WHOLE message is one of these we
# skip the tool schemas entirely rather than trusting the model not to call one.
# A greeting firing a workout-plan regeneration is a bad enough failure to be
# worth a deterministic guard.
#
# Deliberately narrow: it matches the entire message, not a prefix, so
# "hi, can you plan my meals" still gets tools. Short answers that carry real
# information ("gym", "paneer", "30 minutes") are NOT in this set and are
# unaffected - which matters, because those are exactly how users reply to
# follow-up questions.
_SMALLTALK = {
    "hi", "hello", "hey", "yo", "hiya", "howdy", "sup", "hola", "namaste",
    "good morning", "good afternoon", "good evening", "morning", "evening",
    "thanks", "thank you", "thanks a lot", "thankyou", "ty", "cheers",
    "ok", "okay", "k", "kk", "cool", "nice", "great", "awesome", "perfect",
    "got it", "understood", "sure", "yep", "yeah", "yes", "no", "nope",
    "bye", "goodbye", "see you", "see ya", "later", "good night", "night",
    "lol", "haha", "hmm", "oh", "wow", "test", "testing",
    "how are you", "how are you doing", "whats up", "what's up",
    "who are you", "what can you do", "what do you do", "help",
    "looks good", "that looks good", "sounds good", "good job", "well done",
}


# Words that are filler on their own but become an ANSWER the moment the
# assistant has asked something. "no" after "do you have gym access?" is the
# single most load-bearing word in the conversation; treating it as a greeting
# discards the reply and restarts the thread.
_ANSWER_WORDS = {
    "ok", "okay", "k", "kk", "sure", "yep", "yeah", "yes", "no", "nope",
    "got it", "understood", "fine", "correct", "right", "nah", "yup",
}

# Asking for help is a real request. It used to be classified as filler, which
# routed it to a prompt explicitly instructed not to list capabilities - so the
# one word a confused user types returned a greeting.
_HELP_WORDS = {"help", "what can you do", "what do you do", "who are you"}


def is_smalltalk(message: str, question_pending: bool = False) -> bool:
    """
    True if the entire message is social filler with no actionable request.

    `question_pending` should be True when the assistant's previous turn ended
    in a question. Bare confirmations are filler in isolation and content when
    something was asked - the same word means different things depending on
    what came before it.
    """
    cleaned = message.strip().lower().strip(".!?,;:'\"")
    cleaned = " ".join(cleaned.split())

    if not cleaned:
        return True

    # Never swallow a request for help, in any conversational state.
    if cleaned in _HELP_WORDS:
        return False

    # A bare answer to a question the assistant just asked is content.
    if question_pending and cleaned in _ANSWER_WORDS:
        return False

    if cleaned in _SMALLTALK:
        return True

    # "hi there", "hello!!", "thanks so much" - greeting plus filler only.
    if len(cleaned.split()) <= 3:
        filler = {"there", "man", "bro", "buddy", "so", "much", "very", "a", "lot", "again", "!"}
        words = [w for w in cleaned.split() if w not in filler]
        stripped = " ".join(words)
        if question_pending and stripped in _ANSWER_WORDS:
            return False
        if words and stripped in _SMALLTALK:
            return True
    return False


def _has_tracked_injury(db, user_id) -> bool:
    """Whether this user has an active injury on record."""
    if db is None or user_id is None:
        return False
    try:
        from app.database import Injury
        return bool(
            db.query(Injury)
            .filter(Injury.user_id == user_id, Injury.status == "active")
            .first()
        )
    except Exception:
        return False


def ends_with_question(text: str) -> bool:
    """
    Did the assistant's last turn ask something?

    A question mark is the reliable signal. Generated plans routinely contain
    rhetorical questions in their body, so only the tail is examined - what
    matters is whether the message *finished* by asking.
    """
    if not text:
        return False
    tail = text.strip()[-200:]
    return "?" in tail


class ConversationManager:
    def __init__(self):
        self.chefgenius = chefgenius_service
        self.culinaryexplorer = culinaryexplorer_service
        self.budgetchef = budgetchef_service
        self.fitmentor = fitmentor_service
        self.meal_planner = advanced_meal_planner_service
        self.nutrient_analyzer = nutrient_analyzer_service

    # ---------------------------------------------------------------- LLM

    def _client(self) -> GroqClient:
        key = groq_config.get_current_api_key()
        if not key:
            raise ValueError("No Groq API key configured")
        return GroqClient(api_key=key)

    def _complete(self, messages: List[Dict[str, Any]], use_tools: bool = True):
        """Call Groq, rotating API keys on rate-limit errors."""
        attempts = max(1, len(groq_config.api_keys))
        last_error = None

        for attempt in range(attempts):
            try:
                kwargs: Dict[str, Any] = {
                    "model": MODEL_ID,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": _MAX_REPLY_TOKENS,
                }
                if use_tools:
                    kwargs["tools"] = TOOL_SCHEMAS
                    kwargs["tool_choice"] = "auto"

                response = self._client().chat.completions.create(**kwargs)
                mark_groq_success()
                choice = response.choices[0]
                message = choice.message
                # The prompt tells the model to keep conversational replies
                # short, but instructions are not guarantees. Flag the case
                # where it ran out of room so the caller can tidy up rather
                # than shipping a sentence that stops mid-word.
                message._hit_length_limit = getattr(choice, "finish_reason", None) == "length"
                return message

            except Exception as e:
                last_error = e
                msg = str(e).lower()
                retryable = any(
                    p in msg
                    for p in ("rate limit", "rate_limit", "429", "quota", "too many requests",
                              "unauthorized", "invalid api key", "authentication")
                )
                if not retryable:
                    raise
                logger.warning("Groq call failed (attempt %d/%d): %s", attempt + 1, attempts, e)
                handle_groq_error(e)

        raise last_error

    # ------------------------------------------------------------ context

    def get_user_context(self, user_id: int, db: Session) -> Dict[str, Any]:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            def _json_list(raw):
                if not raw:
                    return []
                try:
                    parsed = json.loads(raw)
                    return parsed if isinstance(parsed, list) else [parsed]
                except (json.JSONDecodeError, TypeError):
                    return [raw]

            active_goal = (
                db.query(Goal)
                .filter(Goal.user_id == user_id, Goal.is_active == True)  # noqa: E712
                .order_by(Goal.created_at.desc())
                .first()
            )

            ctx = {
                "name": user.full_name or "there",
                "age": user.current_age,
                "weight_kg": user.weight,
                "height_cm": user.height,
                "activity_level": user.activity_level,
                "health_conditions": _json_list(user.health_conditions),
                "dietary_preferences": _json_list(user.dietary_preferences),
                "cuisine_preference": user.cuisine_pref,
            }
            if active_goal:
                ctx["active_goal"] = {
                    "type": active_goal.goal_type,
                    "target_weight": active_goal.target_weight,
                    "target_calories": active_goal.target_calories,
                    "target_protein": active_goal.target_protein,
                }
            return {k: v for k, v in ctx.items() if v not in (None, [], "")}

        except Exception as e:
            logger.error("Error building user context: %s", e)
            return {}

    def _profile_block(self, ctx: Dict[str, Any]) -> str:
        if not ctx:
            return "\n## User profile\nNo profile information on file yet.\n"
        lines = ["\n## User profile (use this instead of asking)"]
        for key, value in ctx.items():
            label = key.replace("_", " ").capitalize()
            if isinstance(value, dict):
                inner = ", ".join(f"{k}: {v}" for k, v in value.items() if v is not None)
                lines.append(f"- {label}: {inner}")
            elif isinstance(value, list):
                lines.append(f"- {label}: {', '.join(str(v) for v in value)}")
            else:
                lines.append(f"- {label}: {value}")
        return "\n".join(lines) + "\n"

    def get_history(self, user_id: int, db: Session) -> List[Dict[str, str]]:
        """Load recent turns as OpenAI-format messages, oldest first."""
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.timestamp.desc())
            .limit(_HISTORY_TURNS * 2)
            .all()
        )
        rows.reverse()

        messages = []
        for row in rows:
            content = row.content or ""
            role = "user" if row.role == "user" else "assistant"
            if role == "assistant" and len(content) > _HISTORY_CHAR_CAP:
                content = content[:_HISTORY_CHAR_CAP] + "\n\n[...full version shown to user earlier...]"
            messages.append({"role": role, "content": content})
        return messages

    def get_last_artifact(self, user_id: int, db: Session) -> Optional[str]:
        """
        The most recent substantial assistant message, untruncated.

        refine_previous_output needs the real previous plan, not the 700-char
        version that gets replayed into the prompt. Short messages are skipped
        because a one-line follow-up question is not an artifact.
        """
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id, ChatMessage.role == "bot")
            .order_by(ChatMessage.timestamp.desc())
            .limit(6)
            .all()
        )
        for row in rows:
            if row.content and len(row.content) > 400:
                return row.content
        return None

    def save_turn(self, user_id: int, user_msg: str, bot_msg: str, db: Session) -> None:
        try:
            db.add(ChatMessage(user_id=user_id, role="user", content=user_msg or ""))
            db.add(ChatMessage(user_id=user_id, role="bot", content=bot_msg or ""))
            db.commit()
        except Exception as e:
            logger.error("Failed to persist chat turn: %s", e)
            db.rollback()

    # -------------------------------------------------------------- tools

    async def _dispatch_tool(
        self,
        name: str,
        args: Dict[str, Any],
        ctx: Dict[str, Any],
        user_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Execute a tool call.

        Returns (ok, text_for_user, raw_payload). Sync services are pushed to a
        worker thread so they do not block the event loop - several of them make
        blocking network calls internally.
        """
        diet = args.get("dietary_restrictions") or ctx.get("dietary_preferences") or []

        try:
            if name == "refine_previous_output":
                if db is None or user_id is None:
                    return False, "", None
                previous = self.get_last_artifact(user_id, db)
                if not previous:
                    # Nothing to refine - fall through to the recovery path so the
                    # model asks the user what they want rather than inventing one.
                    return False, "", None

                feedback = args.get("feedback", "")
                artifact = args.get("artifact_type", "workout_plan")

                if artifact == "workout_plan":
                    result = await self.fitmentor.adapt_workout_plan(
                        current_plan=previous, feedback=feedback
                    )
                    return self._unwrap(result, "adapted_plan")
                if artifact == "budget_meal_plan":
                    result = await self.budgetchef.adapt_budget_meal_plan(
                        current_plan=previous, feedback=feedback
                    )
                    return self._unwrap(result, "adapted_plan")
                if artifact == "recipe":
                    result = await self.culinaryexplorer.adapt_regional_plan(
                        current_plan=previous, feedback=feedback,
                        # The user's own restrictions, resolved above. Without
                        # them an adaptation carries no dietary requirement at
                        # all and the audit has nothing to enforce.
                        dietary_restrictions=diet,
                    )
                    return self._unwrap(result, "adapted_plan")
                result = await asyncio.to_thread(
                    self.meal_planner.adapt_meal_plan, {"raw": previous}, feedback
                )
                return self._unwrap(result, "adapted_plan")

            if name == "generate_recipe":
                result = await self.chefgenius.generate_recipe_from_ingredients(
                    ingredients=args.get("ingredients", []),
                    dietary_restrictions=diet,
                    time_constraint=args.get("time_minutes", 30),
                    meal_type=args.get("meal_type", "dinner"),
                )
                return self._unwrap(result, "recipe")

            if name == "generate_workout_plan":
                # Union of what the model extracted from the conversation and what
                # is stored on the profile. Previously only the profile was used,
                # so an injury mentioned mid-conversation was silently discarded.
                constraints = list(args.get("constraints") or [])
                for condition in ctx.get("health_conditions", []) or []:
                    if condition and condition not in constraints:
                        constraints.append(condition)

                # Tracked injuries, with their concrete exercise exclusions.
                # These carry more weight than anything the model extracted
                # from the conversation, because they are stored facts with a
                # curated list of what to avoid - so they go first, and they
                # apply even if the user did not mention the injury this turn.
                if db is not None and user_id is not None:
                    try:
                        from app.services.injury_service import as_constraints
                        for line in as_constraints(db, user_id):
                            if line not in constraints:
                                constraints.insert(0, line)
                    except Exception as e:
                        logger.error("Could not load injury constraints: %s", e)

                # The generator has no sport parameter and the fitness_goal enum
                # has no sport values, so "footballer" had nowhere to go and the
                # request silently became general_fitness. Passing it as a
                # constraint is the honest fix: constraints is free text that
                # reaches the prompt, and a sport genuinely does constrain what
                # the plan should contain and when.
                sport = (args.get("sport") or "").strip() or None

                result = await self.fitmentor.generate_workout_plan(
                    sport=sport,
                    activity_level=args.get("activity_level")
                    or ctx.get("activity_level")
                    or "moderately_active",
                    fitness_goal=args.get("fitness_goal", "general_fitness"),
                    time_per_day=args.get("time_per_day", 60),
                    equipment=args.get("equipment", "bodyweight"),
                    constraints=constraints,
                    age=ctx.get("age"),
                    weight=ctx.get("weight_kg"),
                )
                return self._unwrap(result, "workout_plan")

            if name == "generate_regional_recipe":
                result = await self.culinaryexplorer.generate_regional_recipe(
                    cuisine_region=args.get("cuisine_region")
                    or ctx.get("cuisine_preference")
                    or "indian",
                    dish_name=args.get("dish_name"),
                    dietary_restrictions=diet,
                    time_constraint=args.get("time_minutes", 60),
                    cooking_skill=args.get("cooking_skill", "intermediate"),
                    available_ingredients=[],
                )
                return self._unwrap(result, "recipe")

            if name == "generate_budget_meal_plan":
                result = await self.budgetchef.generate_budget_meal_plan(
                    budget_per_day=args.get("budget_per_day", 200.0),
                    calorie_target=args.get("calorie_target", 2000),
                    dietary_preferences=args.get("dietary_preferences") or diet,
                    meals_per_day=args.get("meals_per_day", 3),
                    cooking_time="moderate",
                    skill_level="intermediate",
                    age=ctx.get("age"),
                    weight=ctx.get("weight_kg"),
                    activity_level=ctx.get("activity_level", "moderate"),
                )
                return self._unwrap(result, "meal_plan")

            if name == "generate_weekly_meal_plan":
                payload = {
                    "target_calories": args.get("target_calories", 2000),
                    "meals_per_day": args.get("meals_per_day", 3),
                    "food_preferences": args.get("food_preferences", []),
                    "dietary_restrictions": args.get("dietary_restrictions") or diet,
                    "region_or_cuisine": args.get("region_or_cuisine")
                    or ctx.get("cuisine_preference")
                    or "mixed",
                    "user_notes": args.get("user_notes", ""),
                }
                result = await asyncio.to_thread(self.meal_planner.generate_meal_plan, payload)
                if isinstance(result, dict) and result.get("success") and "meal_plan" in result:
                    return True, format_meal_plan(result), result
                return self._unwrap(result, "meal_plan")

            if name == "analyze_food_nutrition":
                result = await asyncio.to_thread(
                    self.nutrient_analyzer.analyze_food_nutrition,
                    args.get("food_name", ""),
                    args.get("serving_size", "100g"),
                )
                return self._unwrap(result, "data")

            return False, f"Unknown tool: {name}", None

        except Exception as e:
            logger.error("Tool '%s' failed: %s", name, e, exc_info=True)
            return False, "", None

    @staticmethod
    def _unwrap(result: Any, primary_key: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Pull display text out of a service result dict.

        The final fallback used to be `str(result)`, which rendered a raw Python
        dict - braces, quotes and all - straight into the chat window whenever a
        service returned structured data with no string field. Failing here and
        letting the recovery path answer in words is always better than showing
        someone `{'success': True, 'plan': {'day1': [...]}}`.
        """
        if isinstance(result, str):
            return (True, result, None) if result.strip() else (False, "", None)
        if not isinstance(result, dict):
            return False, "", None
        if not result.get("success", True):
            logger.warning("Service reported failure: %s", result.get("error"))
            return False, "", result

        for key in (primary_key, "data", "message", "recipe", "workout_plan",
                    "meal_plan", "adapted_plan", "raw_analysis", "content", "text"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return True, value, result
            # Some services nest one level: {"data": {"recipe": "..."}}
            if isinstance(value, dict):
                for inner in (primary_key, "recipe", "workout_plan", "meal_plan",
                              "adapted_plan", "raw_analysis", "content", "text"):
                    nested = value.get(inner)
                    if isinstance(nested, str) and nested.strip():
                        return True, nested, result

        logger.warning(
            "Service returned no displayable text (keys: %s) - routing to recovery.",
            list(result.keys()),
        )
        return False, "", result

    # --------------------------------------------------------------- main

    def _smalltalk_messages(
        self, user_query: str, ctx: Dict[str, Any], history: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        A minimal prompt for social messages.

        Replaying the full history here is actively harmful: after a few plans the
        transcript is thousands of tokens of workout content, and the model reads
        "hi" as a cue to summarise it. Instead we pass a single line describing
        what was last discussed, which is enough for a natural "how's the plan
        going?" without inviting a recap.
        """
        topic = ""
        for message in reversed(history):
            if message["role"] == "user" and not is_smalltalk(message["content"]):
                topic = message["content"][:120]
                break

        name = ctx.get("name") or "there"
        system = (
            PERSONA
            + "\n"
            + f"The user ({name}) has just sent a short social message: \"{user_query}\".\n\n"
            "Reply the way a friendly person would: one or two short sentences, maximum. "
            "Greet them back or acknowledge what they said.\n\n"
            "Do NOT summarise, recap, or repeat anything you produced earlier. "
            "Do NOT restate their goals, injuries, or previous plans. "
            "Do NOT list what you can do unless they asked. "
            "They can scroll up to see previous messages - repeating them is noise.\n\n"
            "You may add one brief, natural opener such as asking how things are going. "
            "Keep it light and do not ask more than one question."
        )
        if topic:
            system += (
                f"\n\nFor context only, the last thing they asked about was: \"{topic}\". "
                "Mention it only if it makes the greeting feel natural, in a few words at most."
            )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_query},
        ]

    async def handle_query(
        self,
        user_id: int,
        user_query: str,
        db: Session,
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        `extra_context` is appended to the system prompt. It exists so callers
        such as SmartChatbotIntegration can inject ML-derived personalisation
        without needing their own copy of the conversation loop.
        """
        try:
            user_query = clamp_user_message(user_query)
            ctx = self.get_user_context(user_id, db)
            history = self.get_history(user_id, db)

            system = SYSTEM_PROMPT + self._profile_block(ctx)

            # The injury guidance is ~700 tokens and only earns its place when
            # an injury is actually in play. Scan this message, the recent
            # history and the stored profile rather than paying for it always.
            scan = " ".join(
                [user_query]
                + [m["content"] for m in history[-4:]]
                + [str(ctx.get("health_conditions", ""))]
            )
            # A tracked injury loads the guidance unconditionally. Waiting for
            # the user to mention it again means the safety rules are absent
            # from exactly the conversation where they were most needed - they
            # told us last week and reasonably expect us to remember.
            if mentions_injury(scan) or _has_tracked_injury(db, user_id):
                system += INJURY_GUIDANCE
            if extra_context:
                system += (
                    "\n## Personalisation signals\n"
                    "Derived from this user's logged history. Weave these in naturally; "
                    "do not read them out as a list.\n"
                    f"{extra_context}\n"
                )

            messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_query})

            # Greetings and acknowledgements never need a generator. Withholding
            # the schemas makes it impossible for the model to call one, which is
            # more reliable than instructing it not to.
            # "no" is filler after "thanks for the plan" and an answer after
            # "do you have gym access?". Which one decides whether the reply is
            # used or discarded, so look at what the assistant just said.
            last_assistant = next(
                (m["content"] for m in reversed(history) if m["role"] == "assistant"),
                "",
            )
            question_pending = ends_with_question(last_assistant)

            smalltalk = is_smalltalk(user_query, question_pending=question_pending)
            if smalltalk:
                logger.info("Smalltalk detected (%r) - dispatching without tools", user_query)
                # Withholding tools stops it GENERATING a plan, but with a history
                # full of plans it will still happily RECAP one. So for a greeting
                # we also collapse the history to a one-line reminder of the topic
                # and give an explicit instruction about what a reply looks like.
                messages = self._smalltalk_messages(user_query, ctx, history)

            reply = self._complete(messages, use_tools=not smalltalk)
            tool_calls = getattr(reply, "tool_calls", None)

            # No tool needed - the model is conversing, asking its own follow-up.
            if not tool_calls:
                text = (reply.content or "").strip() or "Could you tell me a bit more about what you need?"
                if getattr(reply, "_hit_length_limit", False):
                    logger.info(
                        "Conversational reply hit the token ceiling (%d chars) - tidying.",
                        len(text),
                    )
                    text = tidy_truncated(text)
                self.save_turn(user_id, user_query, text, db)
                return {
                    "success": True,
                    "response": text,
                    "agent_used": "nutricoach",
                    "tool_used": None,
                    "user_context": ctx,
                }

            call = tool_calls[0]
            tool_name = call.function.name
            try:
                tool_args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                logger.warning("Bad tool arguments from model: %r", call.function.arguments)
                tool_args = {}

            logger.info("Tool call: %s(%s)", tool_name, tool_args)
            ok, text, raw = await self._dispatch_tool(
                tool_name, tool_args, ctx, user_id=user_id, db=db
            )

            if not ok or not text.strip():
                # Let the model recover in words rather than showing a stack trace.
                messages.append({
                    "role": "system",
                    "content": (
                        "The specialist service is temporarily unavailable. Answer the "
                        "user's request directly from your own knowledge, briefly and "
                        "helpfully. Do not mention the failure or apologise at length."
                    ),
                })
                recovery = self._complete(messages, use_tools=False)
                text = (recovery.content or "").strip() or (
                    "I'm having trouble reaching that service right now - mind trying again in a moment?"
                )
                self.save_turn(user_id, user_query, text, db)
                return {
                    "success": True,
                    "response": text,
                    "agent_used": "nutricoach",
                    "tool_used": tool_name,
                    "degraded": True,
                    "user_context": ctx,
                }

            # Preamble makes the handoff feel conversational rather than abrupt.
            preamble = (reply.content or "").strip()
            final = f"{preamble}\n\n{text}" if preamble else text

            self.save_turn(user_id, user_query, final, db)
            return {
                "success": True,
                "response": final,
                "agent_used": "nutricoach",
                "tool_used": tool_name,
                "tool_args": tool_args,
                "structured": raw,
                "user_context": ctx,
            }

        except Exception as e:
            logger.error("handle_query failed: %s", e, exc_info=True)

            # Distinguish "we are out of quota" from "something broke". The
            # previous catch-all told the user nothing and sent them hunting
            # for a bug that did not exist.
            text = str(e).lower()
            if any(p in text for p in ("rate limit", "rate_limit", "429", "quota")):
                wait = groq_config.seconds_until_available()
                if wait > 3600:
                    when = f"about {wait // 3600}h {(wait % 3600) // 60}m"
                elif wait > 60:
                    when = f"about {wait // 60} minutes"
                else:
                    when = "under a minute"

                daily = "tokens per day" in text or "tpd" in text
                if daily:
                    message = (
                        "I've hit my daily usage limit with the AI provider, so I can't "
                        f"generate anything new right now. It resets in {when}. "
                        "Everything already generated is still in your history."
                    )
                else:
                    message = (
                        "I'm being rate limited at the moment and need to pause for "
                        f"{when}. Try again shortly."
                    )
                return {
                    "success": False,
                    "response": message,
                    "agent_used": "nutricoach",
                    "rate_limited": True,
                    "retry_after_seconds": wait,
                    "error": str(e),
                }

            return {
                "success": False,
                "response": "Something went wrong on my end. Please try again in a moment.",
                "agent_used": "nutricoach",
                "error": str(e),
            }

    def get_available_agents(self) -> List[Dict[str, str]]:
        return [
            {"name": "generate_recipe", "description": "Recipes from ingredients you have"},
            {"name": "generate_regional_recipe", "description": "Regional and named-dish recipes"},
            {"name": "generate_workout_plan", "description": "Personalised 7-day workout plans"},
            {"name": "generate_budget_meal_plan", "description": "Meal plans on a daily budget"},
            {"name": "generate_weekly_meal_plan", "description": "Comprehensive 7-day meal plans"},
            {"name": "analyze_food_nutrition", "description": "Nutrition breakdown for a food"},
            {"name": "refine_previous_output", "description": "Adjust a plan or recipe already produced"},
        ]


def format_meal_plan(result: Dict[str, Any]) -> str:
    """Render the structured 7-day plan as readable markdown."""
    try:
        meal_plan = result.get("meal_plan", {})
        meta = meal_plan.get("meta", {})
        plan = meal_plan.get("plan", {})
        summary = meal_plan.get("summary", {})

        out = ["🍽️ **Your 7-Day Meal Plan**\n"]
        out.append(
            f"**{meta.get('total_daily_calories', 'N/A')} kcal/day** across "
            f"**{meta.get('meals_per_day', 'N/A')} meals**"
            + (f" · ₹{meta['budget_per_day']}/day" if meta.get("budget_per_day") else "")
        )
        if meta.get("assumptions"):
            out.append(f"\n_Assumptions: {meta['assumptions']}_")

        for day_key in sorted(plan.keys()):
            label = day_key.split("_")[-1]
            out.append(f"\n**Day {label}**")
            for meal in plan[day_key]:
                calories = meal.get("macros", {}).get("calories", "N/A")
                out.append(
                    f"- {meal.get('meal_label', 'Meal')}: "
                    f"{meal.get('recipe_name', 'Unknown')} ({calories} cal)"
                )

        if summary:
            out.append(
                f"\n**Weekly summary** — avg ₹{summary.get('avg_daily_cost', 'N/A')}/day, "
                f"{summary.get('avg_daily_calories', 'N/A')} kcal/day"
            )
            shopping = summary.get("weekly_shopping_list") or []
            if shopping:
                out.append("\n🛒 **Shopping list**")
                for item in shopping[:8]:
                    out.append(f"- {item.get('name', 'Item')} ({item.get('qty_est', 'N/A')})")
                if len(shopping) > 8:
                    out.append(f"- ...and {len(shopping) - 8} more")
            if summary.get("progression_tip"):
                out.append(f"\n💡 {summary['progression_tip']}")

        return "\n".join(out)

    except Exception as e:
        logger.error("Meal plan formatting failed: %s", e)
        return str(result)
