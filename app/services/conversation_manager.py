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

# Words that mean the injury guidance is worth its ~350 tokens this turn.
INJURY_TRIGGERS = (
    "injur", "pain", "hurt", "sore", "strain", "sprain", "tear", "torn",
    "physio", "surgery", "recovering", "rehab", "ache", "tendon", "acl",
    "hamstring", "shoulder", "knee", "back", "wrist", "ankle", "hip",
)

SYSTEM_PROMPT = """You are NutriCoach, a warm and knowledgeable health, nutrition and fitness assistant.

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


def is_smalltalk(message: str) -> bool:
    """True if the entire message is social filler with no actionable request."""
    cleaned = message.strip().lower().strip(".!?,;:'\"")
    cleaned = " ".join(cleaned.split())
    if cleaned in _SMALLTALK:
        return True
    # "hi there", "hello!!", "thanks so much" - greeting plus filler only.
    if len(cleaned.split()) <= 3:
        filler = {"there", "man", "bro", "buddy", "so", "much", "very", "a", "lot", "again", "!"}
        words = [w for w in cleaned.split() if w not in filler]
        if words and " ".join(words) in _SMALLTALK:
            return True
    return False


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
                return response.choices[0].message

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
                "age": user.age,
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
                        current_plan=previous, feedback=feedback
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

                result = await self.fitmentor.generate_workout_plan(
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
        """Pull display text out of a service result dict."""
        if not isinstance(result, dict):
            return True, str(result), None
        if not result.get("success", True):
            logger.warning("Service reported failure: %s", result.get("error"))
            return False, "", result
        for key in (primary_key, "data", "message", "recipe", "workout_plan", "meal_plan", "raw_analysis"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return True, value, result
        return True, str(result), result

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
            "You are NutriCoach, a warm health and nutrition assistant.\n\n"
            f"The user ({name}) has just sent a short social message: \"{user_query}\".\n\n"
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
            ctx = self.get_user_context(user_id, db)
            history = self.get_history(user_id, db)

            system = SYSTEM_PROMPT + self._profile_block(ctx)

            # The injury guidance is ~700 tokens and only earns its place when
            # an injury is actually in play. Scan this message, the recent
            # history and the stored profile rather than paying for it always.
            scan = " ".join(
                [user_query.lower()]
                + [m["content"].lower() for m in history[-4:]]
                + [str(ctx.get("health_conditions", "")).lower()]
            )
            if any(t in scan for t in INJURY_TRIGGERS):
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
            smalltalk = is_smalltalk(user_query)
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
