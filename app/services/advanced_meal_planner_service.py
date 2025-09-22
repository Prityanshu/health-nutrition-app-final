import logging
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from agno.tools.exa import ExaTools
from dotenv import load_dotenv
from textwrap import dedent
import json
import re

load_dotenv()
logger = logging.getLogger(__name__)

class AdvancedMealPlannerService:
    def __init__(self):
        self.advanced_meal_agent = Agent(
            name="AdvancedMealPlanner",
            tools=[ExaTools()],  # lets the model search & validate food items if needed
            model=GroqWithFallback(id="llama-3.3-70b-versatile"),
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
                5. Aim for daily macro balance (protein-carbs-fat) roughly appropriate for general healthy eating. Provide protein-forward or low-carb variations only if requested.
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

    def build_query(self, payload: dict) -> str:
        """Build query from user inputs"""
        # convert lists to comma-separated strings for concise prompt
        prefs = ", ".join(payload.get('food_preferences', [])) if payload.get('food_preferences') else "none"
        restrictions = ", ".join(payload.get('dietary_restrictions', [])) if payload.get('dietary_restrictions') else "none"
        equipment = ", ".join(payload.get('equipment', [])) if payload.get('equipment') else "basic stove"
        region = payload.get('region_or_cuisine') or "no specific region"

        query = dedent(f"""\
            Create a 7-day meal plan JSON for the following user inputs.
            Return ONLY a single JSON object exactly matching the schema in your instructions.

            User Inputs:
            - target_calories: {payload.get('target_calories', 2000)}
            - meals_per_day: {payload.get('meals_per_day', 3)}
            - food_preferences: {prefs}
            - budget_per_day: {payload.get('budget_per_day', 50.0)}
            - work_hours_per_day: {payload.get('work_hours_per_day', 8)}
            - dietary_restrictions: {restrictions}
            - equipment: {equipment}
            - time_per_meal_min: {payload.get('time_per_meal_min', 30)}
            - region_or_cuisine: {region}
            - user_notes: {payload.get('user_notes', '')}

            Please generate the 7-day plan now.
        """)
        return query

    def generate_meal_plan(self, payload: dict) -> dict:
        """Generate a 7-day meal plan using AdvancedMealPlanner agent"""
        try:
            query = self.build_query(payload)
            logger.info(f"AdvancedMealPlanner query: {query}")

            # call the agent; using run() returns a RunOutput object
            response = self.advanced_meal_agent.run(query)
            logger.info(f"AdvancedMealPlanner raw response: {response}")

            # Extract content from RunOutput
            agent_text = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"AdvancedMealPlanner extracted text: {agent_text}")

            # attempt to parse JSON from agent output
            # agent is instructed to output pure JSON — try to parse directly.
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
                    return {
                        "success": False,
                        "error": "Agent did not return complete JSON."
                    }
                
                json_text = agent_text[json_start:json_end]
                try:
                    parsed = json.loads(json_text)
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed parsing JSON from agent output: {str(e)}"
                    }

            return {
                "success": True,
                "meal_plan": parsed,
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
