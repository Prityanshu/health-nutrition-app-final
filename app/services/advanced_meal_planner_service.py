import logging
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from app.config.groq_config import get_fast_model, get_reasoning_model
from dotenv import load_dotenv
from textwrap import dedent
import json
import re

load_dotenv()
logger = logging.getLogger(__name__)

def _strip_code_fences(text: str) -> str:
    """
    Remove a surrounding markdown code fence, if present.

    The agent is instructed to emit bare JSON but often returns it wrapped as
    ```json … ``` regardless. That makes json.loads fail at position 0, which
    previously fell through to brace matching - a fallback meant for genuinely
    malformed output, not for a wrapper we can strip deterministically.
    """
    if not text:
        return text
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop the opening fence and any language tag on the same line.
        newline = cleaned.find("\n")
        cleaned = cleaned[newline + 1:] if newline != -1 else cleaned[3:]
        # Drop the closing fence.
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    return cleaned.strip()


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
            model=GroqWithFallback(
                id=get_reasoning_model(), fallback_id=get_fast_model(), max_tokens=6000
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
            {goal_block}{macro_block}
            Please generate the 7-day plan now.
        """)
        return query

    def generate_meal_plan(self, payload: dict, macro_target=None) -> dict:
        """
        Generate a 7-day meal plan using AdvancedMealPlanner agent.

        With `macro_target`, every day is held to all four macros and the
        result is checked by summing the plan's own per-meal figures - which is
        stronger than reading a stated total, because it uses the numbers the
        plan is actually made of.
        """
        try:
            query = self.build_query(payload, macro_target=macro_target)
            logger.info(f"AdvancedMealPlanner query: {query}")

            # call the agent; using run() returns a RunOutput object
            response = self.advanced_meal_agent.run(query)
            logger.info(f"AdvancedMealPlanner raw response: {response}")

            # Extract content from RunOutput
            agent_text = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"AdvancedMealPlanner extracted text: {agent_text}")

            # The agent is told to return pure JSON but frequently wraps it in
            # a ```json fence anyway. Strip that before parsing rather than
            # relying on the brace-matching fallback below, which is a last
            # resort and cannot cope with truncation.
            agent_text = _strip_code_fences(agent_text)

            try:
                parsed = json.loads(agent_text)
            except json.JSONDecodeError:
                # attempt to recover: extract first complete JSON object occurrence
                # Use a more precise approach to find the JSON boundaries
                json_start = agent_text.find('{')
                if json_start == -1:
                    return {
                        "success": False,
                        "error": "Agent did not return valid JSON."
                    }
                
                # Find the matching closing brace by counting braces
                brace_count = 0
                json_end = -1
                for i in range(json_start, len(agent_text)):
                    if agent_text[i] == '{':
                        brace_count += 1
                    elif agent_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end == -1:
                    # The object opened but never closed: the model stopped
                    # mid-generation. Say so plainly, with the one action that
                    # reliably helps.
                    logger.error(
                        "Truncated plan: %d chars, unbalanced braces", len(agent_text)
                    )
                    return {
                        "success": False,
                        "error": (
                            "The plan was cut off before it finished. This happens when the "
                            "week is too large to generate in one go - try fewer meals per day, "
                            "then add snacks separately."
                        )
                    }
                
                json_text = agent_text[json_start:json_end]
                try:
                    parsed = json.loads(json_text)
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed parsing JSON from agent output: {str(e)}"
                    }

            verification = None
            if macro_target is not None:
                from app.services import macro_targets as mt

                verification = mt.verify_structured(macro_target, parsed)

                # One retry, naming the days that missed and by how much.
                # A 7-day plan is expensive to generate, so this is bounded at
                # a single attempt and only kept if it is genuinely better.
                if verification.get("checked") and not verification.get("hit"):
                    logger.warning("Meal plan missed macros: %s", verification["summary"])
                    try:
                        retry_query = (
                            f"{query}\n\n            "
                            f"{mt.retry_brief_structured(verification, macro_target)}"
                        )
                        again = self.advanced_meal_agent.run(retry_query)
                        again_text = _strip_code_fences(
                            again.content if hasattr(again, "content") else str(again)
                        )
                        second = json.loads(again_text)
                        recheck = mt.verify_structured(macro_target, second)
                        if recheck.get("checked") and (
                            recheck.get("days_on_target", 0)
                            > verification.get("days_on_target", 0)
                        ):
                            parsed, agent_text = second, again_text
                            verification = recheck
                            verification["retried"] = True
                    except Exception as e:
                        # A failed retry must never cost the user the plan they
                        # already have.
                        logger.warning("Meal plan retry failed, keeping first: %s", e)

            return {
                "success": True,
                "meal_plan": parsed,
                "verification": verification,
                "raw_response": agent_text
            }

        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg or "Rate limit reached" in error_msg:
                logger.error(f"Groq API rate limit exceeded: {e}")
                return {
                    "success": False, 
                    "error": "AI service is temporarily unavailable due to high usage. Please try again in a few minutes.",
                    "error_type": "rate_limit"
                }
            else:
                logger.error(f"Error generating meal plan with AdvancedMealPlanner: {e}")
                return {"success": False, "error": str(e)}

    def adapt_meal_plan(self, current_plan: dict, feedback: str, new_requirements: dict = None) -> dict:
        """Adapt an existing meal plan based on user feedback"""
        try:
            # Build adaptation prompt
            adaptation_prompt = f"""
            Please adapt the following 7-day meal plan based on user feedback and new requirements.

            Current Plan:
            {json.dumps(current_plan, indent=2)}

            User Feedback:
            {feedback}

            New Requirements:
            {json.dumps(new_requirements or {}, indent=2)}

            Please provide an updated 7-day meal plan that addresses the feedback while maintaining
            the same JSON structure and improving the plan based on the new requirements.
            """

            logger.info(f"AdvancedMealPlanner adaptation prompt: {adaptation_prompt}")
            response = self.advanced_meal_agent.run(adaptation_prompt)
            logger.info(f"AdvancedMealPlanner adaptation response: {response}")

            # Extract content from RunOutput
            agent_text = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"AdvancedMealPlanner adaptation text: {agent_text}")

            # Parse the adapted plan
            try:
                parsed = json.loads(agent_text)
            except json.JSONDecodeError:
                # Use the same improved JSON extraction logic
                json_start = agent_text.find('{')
                if json_start == -1:
                    return {
                        "success": False,
                        "error": "Agent did not return valid JSON for adaptation."
                    }
                
                # Find the matching closing brace by counting braces
                brace_count = 0
                json_end = -1
                for i in range(json_start, len(agent_text)):
                    if agent_text[i] == '{':
                        brace_count += 1
                    elif agent_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end == -1:
                    return {
                        "success": False,
                        "error": "Agent did not return complete JSON for adaptation."
                    }
                
                json_text = agent_text[json_start:json_end]
                try:
                    parsed = json.loads(json_text)
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed parsing adapted JSON: {str(e)}"
                    }

            return {
                "success": True,
                "adapted_plan": parsed,
                "feedback": feedback,
                "new_requirements": new_requirements
            }

        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg or "Rate limit reached" in error_msg:
                logger.error(f"Groq API rate limit exceeded: {e}")
                return {
                    "success": False, 
                    "error": "AI service is temporarily unavailable due to high usage. Please try again in a few minutes.",
                    "error_type": "rate_limit"
                }
            else:
                logger.error(f"Error adapting meal plan with AdvancedMealPlanner: {e}")
                return {"success": False, "error": str(e)}

advanced_meal_planner_service = AdvancedMealPlannerService()
