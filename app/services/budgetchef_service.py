import logging
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from agno.tools.exa import ExaTools
from dotenv import load_dotenv
from textwrap import dedent
import json

load_dotenv()
logger = logging.getLogger(__name__)

class BudgetChefService:
    def __init__(self):
        self.budget_meal_agent = Agent(
            name="BudgetChef",
            tools=[],
            model=GroqWithFallback(id="llama-3.3-70b-versatile"),
            description=dedent("""\
                You are BudgetChef, a savvy culinary planner who balances nutrition and cost. 🛒💰
                
                Your mission: create meal plans that maximize nutrition and flavor while staying
                within the user's daily or weekly budget."""),
            instructions=dedent("""\
                Approach each meal plan with these steps:

                1. Input Analysis 📝
                   - User's budget per day (or week)
                   - Calorie target (if provided; else estimate from age/weight/activity)
                   - Dietary preferences or restrictions
                   - Number of meals/snacks per day
                   - Available cooking time & skill level

                2. Cost & Nutrition Mapping 💲
                   - Use a reference table of cost per food item (either from dataset or approximations)
                   - Estimate calories, macros, and cost for each food
                   - Select food items that meet calorie + macro goals while staying under budget

                3. Optimization ⚙️
                   - Apply a simple **greedy approach**:
                     - Pick staple items (rice, lentils, eggs, etc.) first
                     - Fill remaining calories with low-cost, nutrient-dense items
                   - (Later, swap to linear programming for more precision)

                4. Presentation 🍽️
                   - Use markdown to show:
                     - Daily meal plan with cost + calories
                     - Totals at the bottom (total cost, total calories)
                   - Mark vegetarian 🌱, vegan 🌿, gluten-free 🌾, contains nuts 🥜
                   - Include shopping list summary with estimated cost
                   - Suggest storage or make-ahead tips to save money

                5. Feedback 🔄
                   - Accept user feedback on items they like/dislike
                   - Adjust plan next time while staying within budget"""),
        )

    async def generate_budget_meal_plan(self, budget_per_day: float, calorie_target: int = None,
                                      dietary_preferences: list = None, meals_per_day: int = 3,
                                      cooking_time: str = "moderate", skill_level: str = "intermediate",
                                      age: int = None, weight: float = None, activity_level: str = "moderate") -> dict:
        """Generate budget meal plan using BudgetChef agent"""
        try:
            # Build the prompt for the agent
            dietary_str = f"Dietary preferences: {', '.join(dietary_preferences)}" if dietary_preferences else "No specific dietary preferences"
            age_weight_str = ""
            if age and weight:
                age_weight_str = f"Age: {age} years, Weight: {weight} kg"
            elif age:
                age_weight_str = f"Age: {age} years"
            elif weight:
                age_weight_str = f"Weight: {weight} kg"
            
            calorie_str = f"Target calories: {calorie_target}" if calorie_target else f"Estimated calories based on {activity_level} activity level"
            
            prompt = f"""Create a budget meal plan for me.

            My details:
            - Budget: ₹{budget_per_day} per day
            - {calorie_str}
            - Meals per day: {meals_per_day}
            - Cooking time available: {cooking_time}
            - Cooking skill level: {skill_level}
            {age_weight_str}
            {dietary_str}

            Please create a detailed daily meal plan with cost breakdown, nutrition information, and shopping list."""

            logger.info(f"BudgetChef prompt: {prompt}")
            response = self.budget_meal_agent.run(prompt)
            logger.info(f"BudgetChef raw response: {response}")

            # Extract content from RunOutput
            meal_plan = response.content if hasattr(response, 'content') else str(response)

            return {
                "success": True,
                "meal_plan": meal_plan,
                "budget_per_day": budget_per_day,
                "calorie_target": calorie_target,
                "dietary_preferences": dietary_preferences or [],
                "meals_per_day": meals_per_day,
                "cooking_time": cooking_time,
                "skill_level": skill_level,
                "age": age,
                "weight": weight,
                "activity_level": activity_level
            }
        except Exception as e:
            logger.error(f"Error generating budget meal plan with BudgetChef: {e}")
            return {"success": False, "error": str(e)}

    async def adapt_budget_meal_plan(self, current_plan: str, feedback: str, 
                                   new_budget: float = None, new_calorie_target: int = None) -> dict:
        """Adapt existing budget meal plan based on user feedback"""
        try:
            budget_str = f"New budget: ₹{new_budget} per day" if new_budget else ""
            calorie_str = f"New calorie target: {new_calorie_target}" if new_calorie_target else ""
            
            prompt = f"""Based on this feedback, please adapt the budget meal plan:

            Current Plan:
            {current_plan}

            User Feedback:
            {feedback}

            {budget_str}
            {calorie_str}

            Please provide an updated budget meal plan that addresses the feedback while staying within budget constraints."""

            logger.info(f"BudgetChef adaptation prompt: {prompt}")
            response = self.budget_meal_agent.run(prompt)
            logger.info(f"BudgetChef adaptation response: {response}")

            # Extract content from RunOutput
            adapted_plan = response.content if hasattr(response, 'content') else str(response)

            return {
                "success": True,
                "adapted_plan": adapted_plan,
                "feedback": feedback,
                "new_budget": new_budget,
                "new_calorie_target": new_calorie_target
            }
        except Exception as e:
            logger.error(f"Error adapting budget meal plan with BudgetChef: {e}")
            return {"success": False, "error": str(e)}

budgetchef_service = BudgetChefService()
