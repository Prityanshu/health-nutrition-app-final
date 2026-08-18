import logging
from typing import Optional

from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from app.config.groq_config import get_fast_model, get_reasoning_model
from dotenv import load_dotenv
from textwrap import dedent
import json

from app.services import dietary_rules
from app.services import meal_plan_contract as mpc

load_dotenv()
logger = logging.getLogger(__name__)

class AdvancedMealPlannerService:
    def __init__(self):
        self.advanced_meal_agent = Agent(
            name="AdvancedMealPlanner",
            # A seven-day plan is the largest output any agent here produces.
            # 6000 was originally tuned against llama-3.3-70b-versatile at
            # ~12,200 characters for 3 meals/day. gpt-oss-120b (the reasoning
            # tier, below) is noticeably more verbose for this exact prompt -
            # tested live at 6000 it truncated JSON even at 3 meals/day
            # (11,347 chars, invalid).
            #
            # NOT simply raised to fix that: at max_tokens=9500 the request
            # was rejected outright - "Request too large ... tokens per
            # minute (TPM): Limit 8000, Requested 10531" - a hard per-request
            # ceiling on this Groq account distinct from the daily quota
            # this file's comments otherwise talk about. That number blocks
            # ANY model on this account, not just this one, and the
            # documented fallback below hit the identical wall on gpt-oss-20b
            # in the same test, confirming it's the request, not the model,
            # that gets rejected. Left at 6000 - safely under that ceiling -
            # rather than picked a number that trades a clear TPM rejection
            # for a smaller chance of silent-ish truncation; both failure
            # modes are already surfaced to the caller as a clear error
            # rather than bad data, so this is a real open tradeoff, not a
            # settled one. Worth the team checking whether all three Groq
            # accounts share this same 8000 TPM figure before tuning further.
            #
            # Reasoning tier: this is the single largest, most constrained
            # output any agent here produces - a strict nested JSON schema
            # across 7 days, each day required to total four separate macro
            # numbers within range, with zero tolerance for a malformed
            # object (there is no markdown fallback path for a plan the
            # frontend cannot parse). Falls back to the fast tier only once
            # the reasoning tier is fully exhausted on every key; a plan
            # that's slightly worse at hitting macros is still preferable to
            # the caller getting nothing.
            #
            # max_retries bounds the GROQ SDK's own retrying, which defaults
            # to 2 (three HTTP attempts per logical call) with exponential
            # backoff. On a 429 that backoff is pure waste here: this app
            # already handles rate limits by rotating to another API key, and
            # GroqWithFallback cannot rotate until the SDK finishes sleeping.
            # The production log shows one corrective generation waiting 32s
            # then 21s on a key that was already exhausted. One retry keeps
            # resilience against a transient network blip; the key rotation
            # handles the rest. Set here rather than in GroqWithFallback so
            # the five other agents that share it are unaffected.
            model=GroqWithFallback(
                id=get_reasoning_model(), fallback_id=get_fast_model(),
                max_tokens=6000, max_retries=1,
            ),
            description=dedent("""\
                You are AdvancedMealPlanner, a clinically-minded nutritionist & meal planner.
                Your job: produce a practical, healthy 7-day meal plan tailored to the user's
                inputs (target calories, meals per day, preferences, budget, work schedule,
                equipment, and dietary restrictions). Prioritize nutrition, food variety,
                cost-awareness and realistic meal prep for busy schedules.
            """),
            instructions=dedent("""\
                REQUIRED OUTPUT RULES (VERY IMPORTANT):
                - Output ONLY valid JSON (no extra commentary). The final output must be a JSON object.
                - The JSON MUST follow the schema described below.

                INPUT HANDLING:
                - Use the user's target_calories (daily), meals_per_day, food_preferences (list),
                  budget_per_day, work_hours_per_day, dietary_restrictions (list), equipment (list),
                  time_per_meal (minutes average), and whether they want vegetarian/vegan emphasis.
                - If some fields are missing, make reasonable assumptions but state them inside "meta.assumptions".

                PLANNING LOGIC:
                1. Split target_calories across meals according to common distribution (e.g., 25% breakfast, 35% lunch, 25% dinner, 15% snacks) or adapt to meals_per_day.
                2. Prefer meals that match food_preferences and comply with dietary_restrictions.
                3. Respect budget_per_day by selecting cost-conscious staples and suggesting swaps.
                4. Make recipes realistic given equipment and time_per_meal. For heavy work_hours_per_day, prefer quick prep / make-ahead meals.
                5. MACRO TARGETS: if the user inputs include protein/carb/fat targets, EVERY day must total
                   all four numbers inside the stated ranges - not just calories. Adjust portion sizes and
                   pick dishes to reach them. If no macro targets are given, aim for a balance appropriate
                   for general healthy eating.
                6. Provide variety across the 7 days and reuse ingredients to reduce waste/cost.

                OUTPUT SCHEMA (Return this exact JSON structure):
                {
                  "meta": {
                    "assumptions": "...string describing any assumptions made...",
                    "total_daily_calories": int,
                    "meals_per_day": int,
                    "budget_per_day": number (in Indian Rupees ₹),
                    "food_preferences": [ ... ],
                    "dietary_restrictions": [ ... ]
                  },
                  "plan": {
                    "day_1": [
                      {
                        "meal_label": "Breakfast",
                        "target_calories": int,
                        "recipe_name": "string",
                        "ingredients": [{"name":"", "qty":"", "est_cost": number}],
                        "macros": {"calories":int,"protein_g":float,"carbs_g":float,"fat_g":float},
                        "prep_time_min": int,
                        "make_ahead": "yes/no",
                        "notes": "short cooking/packing tips"
                      },
                      ... up to meals_per_day entries ...
                    ],
                    "day_2": [...],
                    ...
                    "day_7": [...]
                  },
                  "summary": {
                    "avg_daily_cost": number,
                    "avg_daily_calories": int,
                    "weekly_shopping_list": [{"name":"", "qty_est":"", "est_cost": number}],
                    "progression_tip": "short text"
                  }
                }

                CALCULATION RULES:
                - Provide numeric macros for each meal; totals for each day should approximate the target daily calories.
                - Round estimates reasonably (two decimals for grams / two decimals for currency).
                - ALL COSTS MUST BE IN INDIAN RUPEES (₹) - use realistic Indian market prices for ingredients.
                - If cost data isn't exact, give approximate est_cost values in ₹.
                - If a requested preference item is unavailable or conflicts with restrictions, pick the closest appropriate swap and explain in meta.assumptions.

                If user input is ambiguous, make a reasonable assumption and include it in meta.assumptions.

            """),
            markdown=False,  # keep the agent's output plain text (we require strict JSON)
        )

    def build_query(self, payload: dict, macro_target=None) -> str:
        """
        Build query from user inputs.

        `macro_target` is optional. Without it the planner behaves exactly as
        it always has - calorie-only - so the generic path is untouched.

        Before this existed the only macro instruction was "aim for daily macro
        balance roughly appropriate for general healthy eating", which is
        identical advice for a 60kg sedentary user and a 90kg athlete. The plan
        still REPORTED per-meal macros, so it looked constrained while being
        constrained by nothing.
        """
        # convert lists to comma-separated strings for concise prompt
        prefs = ", ".join(payload.get('food_preferences', [])) if payload.get('food_preferences') else "none"
        restrictions = ", ".join(payload.get('dietary_restrictions', [])) if payload.get('dietary_restrictions') else "none"
        equipment = ", ".join(payload.get('equipment', [])) if payload.get('equipment') else "basic stove"
        region = payload.get('region_or_cuisine') or "no specific region"

        # Budget is optional. Note that .get('budget_per_day', 50.0) returns
        # None when the key is present with a null value - the default only
        # applies to a missing key - so the prompt would otherwise read
        # "budget_per_day: None".
        #
        # A stated budget competes with the nutrition targets: constrained
        # spending pushes the plan toward cheap, carb-heavy filler and away from
        # the protein target. When no budget is given, say so explicitly rather
        # than leaving the model to invent one.
        budget = payload.get('budget_per_day')
        if budget:
            # Only refer to targets that are actually in the prompt. The
            # original said "do not sacrifice the protein target" when no
            # protein target was ever given - the model was told to protect a
            # number it could not see. Naming them conditionally keeps that
            # from happening in either direction.
            what_to_protect = (
                "the macro targets below" if macro_target is not None
                else "nutritional quality"
            )
            budget_line = (
                f"- budget_per_day: {budget} (INR). Respect this, but do not "
                f"sacrifice {what_to_protect} to hit it - if the two conflict, "
                f"prioritise nutrition and note the overage in meta.assumptions."
            )
        else:
            budget_line = (
                "- budget_per_day: NOT SPECIFIED. Do not optimise for cost. "
                "Choose whatever best meets the nutrition targets, and still fill "
                "in est_cost fields with realistic estimates for reference."
            )

        # Dietary restrictions as an explicit hard requirement rather than one
        # more comma-separated input line. The deterministic audit rejects the
        # plan either way, so this is purely to make the first attempt right
        # more often - the prompt is never what makes it safe.
        restriction_block = dietary_rules.restriction_brief(
            payload.get("dietary_restrictions"))
        if restriction_block:
            restriction_block = "\n            " + restriction_block.replace(
                "\n", "\n            ") + "\n"

        # Goes after the inputs and immediately before the instruction to
        # generate - the last thing read, which is where a hard requirement
        # has to sit.
        macro_block = ""
        if macro_target is not None:
            macro_block = "\n" + macro_target.prompt_block(
                per_day=True, structured=True) + "\n"

        # The weight goal, if there is one. Macros say what a day must add up
        # to; this says why, and the why changes the food. The same 2000 kcal
        # looks very different for someone cutting to 74 kg than for someone
        # bulking to 85 - volume and satiety versus calorie density.
        goal_block = payload.get("goal_context") or ""
        if goal_block:
            goal_block = "\n            " + goal_block.strip() + "\n"

        query = dedent(f"""\
            Create a 7-day meal plan JSON for the following user inputs.
            Return ONLY a single JSON object exactly matching the schema in your instructions.

            User Inputs:
            - target_calories: {payload.get('target_calories', 2000)}
            - meals_per_day: {payload.get('meals_per_day', 3)}
            - food_preferences: {prefs}
            {budget_line}
            - work_hours_per_day: {payload.get('work_hours_per_day', 8)}
            - dietary_restrictions: {restrictions}
            - equipment: {equipment}
            - time_per_meal_min: {payload.get('time_per_meal_min', 30)}
            - region_or_cuisine: {region}
            - user_notes: {payload.get('user_notes', '')}
            {goal_block}{restriction_block}{macro_block}
            Please generate the 7-day plan now.
        """)
        return query


    # ------------------------------------------------------------------
    # the one canonical validation pipeline
    # ------------------------------------------------------------------

    def _assess(self, text: str, *, meals_per_day: int,
                restrictions=None, target_calories=None,
                macro_target=None) -> "mpc.PlanCandidate":
        """
        LLM text -> a fully assessed candidate.

        Generation, the generation retry, adaptation and the adaptation retry
        all come through here. That is the point: every earlier bug in this
        file existed because one path checked something another did not, so
        there is deliberately no way to obtain a candidate without running the
        whole pipeline over it.
        """
        parsed, code, message = mpc.extract_json_object(text, meals_per_day)
        if parsed is None:
            return mpc.PlanCandidate(plan=None, raw_text=text or "",
                                     parse_error=message, parse_code=code)

        candidate = mpc.PlanCandidate(plan=parsed, raw_text=text or "")
        candidate.structure = mpc.validate_structure(parsed, meals_per_day)

        totals = mpc.day_totals(parsed)
        candidate.dietary = dietary_rules.audit_plan(
            parsed, restrictions, macro_totals_by_day=totals)
        candidate.calories = mpc.verify_calories(parsed, target_calories)

        if macro_target is not None:
            from app.services import macro_targets as mt
            candidate.macro = mt.verify_structured(macro_target, parsed)
        return candidate

    def _run_agent(self, prompt: str) -> str:
        response = self.advanced_meal_agent.run(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _needs_retry(self, candidate: "mpc.PlanCandidate") -> bool:
        """
        Worth spending the one corrective generation?

        True for anything the user would consider wrong: an unusable plan, a
        hard dietary violation, or a calorie/macro miss. All of them go into a
        SINGLE brief - separate retry loops per validator would multiply the
        cost of the most expensive call in the app.
        """
        if not candidate.usable:
            return True
        if candidate.calories and candidate.calories.get("checked") \
                and not candidate.calories.get("hit"):
            return True
        if candidate.macro and candidate.macro.get("checked") \
                and not candidate.macro.get("hit"):
            return True
        return False

    def _attempt(self, prompt: str, **assess) -> "mpc.PlanCandidate":
        """One generation plus at most one bounded corrective retry."""
        first = self._assess(self._run_agent(prompt), **assess)
        logger.info("meal plan attempt 1: %s", _describe_candidate(first))

        if not self._needs_retry(first):
            return first

        brief = first.issues_brief()
        if not brief:
            return first

        try:
            retry_text = self._run_agent(
                f"{prompt}\n\n            "
                f"Your previous attempt was rejected. Fix ALL of the following "
                f"and return the complete corrected 7-day plan:\n{brief}"
            )
            second = self._assess(retry_text, **assess)
        except Exception as exc:
            # A failed retry must never cost the user a plan they already have.
            logger.warning("meal plan retry failed (%s); keeping first attempt",
                           type(exc).__name__)
            return first

        logger.info("meal plan attempt 2: %s", _describe_candidate(second))
        if mpc.better(second, first):
            second.retried = True
            return second
        first.retried = True
        return first

    # ------------------------------------------------------------------
    # generation
    # ------------------------------------------------------------------

    def generate_meal_plan(self, payload: dict, macro_target=None) -> dict:
        """
        Generate a 7-day meal plan, or fail closed.

        Success now means the plan is structurally a complete week AND
        contains no ingredient the user's restrictions forbid. Calorie and
        macro misses are returned with honest verification metadata rather
        than blocking, because a plan 200 kcal light is still usable and a
        vegan plan containing milk is not.
        """
        try:
            restrictions = payload.get("dietary_restrictions") or []
            meals_per_day = int(payload.get("meals_per_day") or 3)
            target_calories = payload.get("target_calories")

            query = self.build_query(payload, macro_target=macro_target)
            candidate = self._attempt(
                query,
                meals_per_day=meals_per_day,
                restrictions=restrictions,
                target_calories=target_calories,
                macro_target=macro_target,
            )

            if not candidate.usable:
                logger.warning("meal plan rejected: %s",
                               _describe_candidate(candidate))
                return {
                    "success": False,
                    "error": candidate.failure_reason(),
                    "verification": candidate.verification_dict(),
                }

            # Stamp the AUTHORITATIVE inputs onto the returned plan, replacing
            # whatever the model claimed in meta.
            #
            # The model writes meta.dietary_restrictions itself, and it
            # routinely writes [] even when generating against a real
            # restriction. Adaptation later reconstructs restrictions from
            # this metadata, so an omitted or falsified value silently
            # dropped the restriction on the next hop: generate vegan ->
            # model reports none -> adapt -> milk accepted. These fields are
            # the request's, not the model's, so the request wins.
            meta = candidate.plan.setdefault("meta", {})
            if isinstance(meta, dict):
                meta["dietary_restrictions"] = dietary_rules.canonical_set(restrictions)
                meta["meals_per_day"] = meals_per_day
                if target_calories:
                    meta["requested_daily_calories"] = target_calories

            return {
                "success": True,
                "meal_plan": candidate.plan,
                "verification": candidate.verification_dict(),
                # Kept for the existing response contract. Bounded so a caller
                # logging the result cannot dump the whole week.
                "raw_response": candidate.raw_text[:2000],
            }

        except Exception as exc:
            return _service_error(exc, "generating")

    # ------------------------------------------------------------------
    # adaptation
    # ------------------------------------------------------------------

    def adapt_meal_plan(self, current_plan: dict, feedback: str,
                        new_requirements: dict = None, *,
                        meals_per_day: int = None,
                        restrictions=None,
                        target_calories=None,
                        macro_target=None) -> dict:
        """
        Adapt an existing plan, through the identical validation pipeline.

        Adaptation used to be the unguarded twin of generation: no auth, no
        structural check on the plan going in OR coming out, no dietary audit,
        no macro recheck. "Make it tastier" could return a plan that dropped
        the user's vegan restriction and it was reported as success.

        `restrictions` is authoritative and comes from the caller (the router,
        from the authenticated user's saved plan), NOT from the free-text
        feedback - so "add some cheese" cannot quietly delete a dairy-free
        requirement. new_requirements may ADD restrictions; it can never
        remove one.
        """
        try:
            # Two DIFFERENT meal counts, and conflating them made changing
            # meals-per-day impossible: the incoming plan was validated
            # against the NEW requirement, so asking to go from 3 meals to 4
            # rejected the existing plan for having 3 - before the agent was
            # ever called.
            existing_meals = _infer_meals_per_day(current_plan) or 3
            wanted_meals = int(meals_per_day or existing_meals)

            # The plan going IN must already be valid ON ITS OWN TERMS.
            # Sending a broken plan to the model wastes the call and makes the
            # output impossible to attribute - was it bad because the model
            # failed, or because the input was already nonsense?
            incoming = mpc.validate_structure(current_plan, existing_meals)
            if not incoming.ok:
                head = "; ".join(incoming.errors[:4])
                return {
                    "success": False,
                    "error": f"The plan you asked to adapt is not a valid 7-day "
                             f"plan — {head}",
                    "verification": {"structure": incoming.as_dict()},
                }

            # Restrictions are the union of what the plan was built with and
            # anything newly requested. Never a subtraction.
            existing = ((current_plan.get("meta") or {}).get("dietary_restrictions")
                        if isinstance(current_plan.get("meta"), dict) else None)
            merged = dietary_rules.canonical_set(
                list(restrictions or []) + list(existing or [])
                + list((new_requirements or {}).get("dietary_restrictions") or [])
            )

            # Calorie authority, in order: a NEW target the caller explicitly
            # requested for this adaptation, then the authoritative target
            # recorded when the plan was generated. The model's own
            # meta.total_daily_calories is never a candidate - see
            # _infer_target_calories.
            if target_calories is None:
                target_calories = _infer_target_calories(current_plan)

            prompt = self._build_adaptation_prompt(
                current_plan, feedback, new_requirements, merged, macro_target,
                meals_per_day=wanted_meals)

            candidate = self._attempt(
                prompt,
                meals_per_day=wanted_meals,
                restrictions=merged,
                target_calories=target_calories,
                macro_target=macro_target,
            )

            if not candidate.usable:
                logger.warning("adapted plan rejected: %s",
                               _describe_candidate(candidate))
                return {
                    "success": False,
                    "error": candidate.failure_reason(),
                    "verification": candidate.verification_dict(),
                }

            meta = candidate.plan.setdefault("meta", {})
            if isinstance(meta, dict):
                # Same reasoning as generation: these are the caller's
                # values, so they survive whatever the model wrote.
                meta["dietary_restrictions"] = list(merged)
                meta["meals_per_day"] = wanted_meals
                if target_calories:
                    # Carried forward, so a second and third adaptation still
                    # know what the user actually asked for.
                    meta["requested_daily_calories"] = target_calories

            return {
                "success": True,
                "adapted_plan": candidate.plan,
                "feedback": feedback,
                "new_requirements": new_requirements,
                "verification": candidate.verification_dict(),
            }

        except Exception as exc:
            return _service_error(exc, "adapting")

    def _build_adaptation_prompt(self, current_plan, feedback, new_requirements,
                                 restrictions, macro_target,
                                 meals_per_day: int = 3) -> str:
        """
        The adaptation instruction, with hard requirements restated.

        Sizes are capped: an unbounded current_plan plus unbounded feedback is
        a quota-abuse vector on the single most expensive call in the app, and
        a plan large enough to need truncating was never going to round-trip
        through a 6000-token completion anyway.
        """
        plan_json = json.dumps(current_plan, indent=2)[:MAX_PLAN_CHARS]
        feedback_text = str(feedback or "")[:MAX_FEEDBACK_CHARS]
        requirements = json.dumps(new_requirements or {}, indent=2)[:MAX_REQUIREMENTS_CHARS]

        blocks = [
            "Adapt the following 7-day meal plan. Return ONLY a single JSON "
            "object in exactly the same schema as the current plan.",
            f"\nCurrent Plan:\n{plan_json}",
            f"\nUser Feedback:\n{feedback_text}",
            f"\nNew Requirements:\n{requirements}",
        ]
        brief = dietary_rules.restriction_brief(restrictions)
        if brief:
            blocks.append(
                "\n" + brief
                + "\nThese restrictions were already in force and REMAIN in force. "
                  "The feedback above cannot remove them - if it asks for "
                  "something that conflicts, substitute a compliant ingredient "
                  "and say so in meta.assumptions."
            )
        if macro_target is not None:
            blocks.append("\n" + macro_target.prompt_block(per_day=True, structured=True))
        blocks.append(f"\nKeep all seven days, with exactly {meals_per_day} "
                      f"meals on every day.")
        return "\n".join(blocks)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

# Bounded so neither an enormous saved plan nor pasted feedback can inflate a
# single request past the account's per-request token ceiling.
MAX_PLAN_CHARS = 24000
MAX_FEEDBACK_CHARS = 2000
MAX_REQUIREMENTS_CHARS = 2000


def _infer_meals_per_day(plan: dict) -> Optional[int]:
    """Read meals/day off the plan being adapted, so it is preserved."""
    meta = (plan or {}).get("meta")
    if isinstance(meta, dict):
        try:
            value = int(meta.get("meals_per_day"))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    days = (plan or {}).get("plan")
    if isinstance(days, dict):
        counts = [len(v) for v in days.values() if isinstance(v, list) and v]
        if counts:
            return max(set(counts), key=counts.count)
    return None


def _infer_target_calories(plan: dict) -> Optional[float]:
    """
    Recover the AUTHORITATIVE calorie target from plan metadata.

    Reads only `meta.requested_daily_calories` - the value generation stamps
    from the user's own request. `meta.total_daily_calories` is written by
    the MODEL and is deliberately never consulted: a model that returns
    meals totalling 2001 kcal while claiming 500 would otherwise turn its
    own false claim into the goalposts, and the adapted plan would be
    verified against - and rebuilt toward - 500 kcal/day.

    Returns None when no authoritative target is recorded (a plan generated
    before this field existed). `verify_calories` then reports checked=False
    with a reason, which is honest; inventing a target from an untrusted
    number would not be.
    """
    meta = (plan or {}).get("meta")
    if isinstance(meta, dict):
        try:
            value = float(meta.get("requested_daily_calories"))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return None


def _describe_candidate(candidate: "mpc.PlanCandidate") -> str:
    """
    Bounded metadata for the log - never the plan, the prompt or the notes.

    Full prompts and complete generated plans used to be logged at INFO,
    which put the user's health context, dietary restrictions and free-text
    notes into the application log on every request.
    """
    if candidate.parse_error:
        # Length and classification only - enough to tell a truncated week
        # from a model sending two plans, without the body reaching the log.
        return f"parse={candidate.parse_code} chars={len(candidate.raw_text or '')}"
    structure = candidate.structure
    dietary = candidate.dietary
    parts = [
        f"chars={len(candidate.raw_text)}",
        f"structure={'ok' if candidate.structurally_complete else 'invalid'}",
        f"days={structure.days if structure else 0}",
        f"structural_errors={len(structure.errors) if structure else 0}",
        f"dietary={dietary.status if dietary else 'n/a'}",
        f"violations={len(dietary.violations) if dietary else 0}",
    ]
    if candidate.calories and candidate.calories.get("checked"):
        parts.append(f"calorie_days_on_target={candidate.calories.get('days_on_target')}"
                     f"/{candidate.calories.get('days_total')}")
    if candidate.macro and candidate.macro.get("checked"):
        parts.append(f"macro_days_on_target={candidate.macro.get('days_on_target')}"
                     f"/{candidate.macro.get('days_total')}")
    return " ".join(parts)


def _service_error(exc: Exception, doing: str) -> dict:
    message = str(exc)
    if "rate_limit_exceeded" in message or "Rate limit reached" in message:
        logger.error("Groq rate limit while %s a meal plan", doing)
        return {
            "success": False,
            "error": "AI service is temporarily unavailable due to high usage. "
                     "Please try again in a few minutes.",
            "error_type": "rate_limit",
        }
    logger.error("Error %s meal plan: %s", doing, type(exc).__name__, exc_info=True)
    return {"success": False, "error": f"{type(exc).__name__}: {exc}" if message
            else type(exc).__name__}


advanced_meal_planner_service = AdvancedMealPlannerService()
