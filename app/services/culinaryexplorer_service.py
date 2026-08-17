import logging
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from app.config.groq_config import get_fast_model
from dotenv import load_dotenv
from textwrap import dedent
import json

load_dotenv()
logger = logging.getLogger(__name__)


def _closer(candidate, incumbent) -> bool:
    """
    Is the retry actually better than what we already had?

    Compared on how many macros landed, then on total distance. Without this a
    retry that fixes carbs and blows calories would silently replace a plan
    that was only slightly off - regeneration has to be an improvement, not
    just a change.
    """
    if not candidate or not candidate.get("checked"):
        return False
    if not incumbent or not incumbent.get("checked"):
        return True
    if candidate.get("hit"):
        return True

    def distance(v):
        return sum(abs(m["delta"]) / max(1, m["target"])
                   for m in v.get("macros", {}).values())

    if len(candidate.get("missed", [])) != len(incumbent.get("missed", [])):
        return len(candidate["missed"]) < len(incumbent["missed"])
    return distance(candidate) < distance(incumbent)

class CulinaryExplorerService:
    def __init__(self):
        self.regional_food_agent = Agent(
            name="CulinaryExplorer",
            tools=[],  # Removed ExaTools due to potential API errors
            # Fast tier: creative regional-recipe generation, no tools. When a
            # macro_target IS given (see generate_regional_meal_plan below),
            # the numbers are checked and one corrective retry is issued
            # deterministically by macro_targets.verify()/retry_brief() - the
            # arithmetic accuracy that would justify the reasoning tier is
            # already handled in Python, not left to the model.
            model=GroqWithFallback(id=get_fast_model()),
            description=dedent("""\
                You are CulinaryExplorer, a culturally aware and health-focused chef. 🌍🍴

                Your mission: suggest recipes and meal plans based on a user's regional or
                cultural cuisine preference. This includes international cuisines
                (Mediterranean, Japanese, Mexican) as well as specific Indian states
                (Punjab, Kerala, Gujarat, Tamil Nadu, Rajasthan, etc.).

                You provide healthier versions of those traditional recipes while keeping 
                authentic taste and cultural notes.
            """),
            instructions=dedent("""\
                FORMATTING: Never use Markdown tables. The app's renderer and
                PDF export only understand headings, bullet points, numbered
                lists and bold text - a table renders as broken pipe-delimited
                text, not a table. Use bullet or numbered lists instead.

                Approach each recipe recommendation with these steps:

                1. Input Analysis 📝
                   - Identify user's preferred cuisine/region:
                     • Global cuisines (Mediterranean, Japanese, Mexican, etc.)
                     • Indian states (Punjab, Kerala, Gujarat, Tamil Nadu, Rajasthan, etc.)
                   - Consider any dietary restrictions or preferences
                   - Note time constraints & cooking skill level
                   - Check available ingredients (if provided)

                2. Cuisine Filtering 🌎
                   - Use a dataset with cuisine tags for each recipe
                   - For India, filter by state-specific cuisine (e.g. Kerala = Appam & Stew, Punjab = Sarson da Saag, etc.)
                   - Select dishes commonly eaten in that region/state

                3. Healthy Modifications 💚
                   - Reduce excess oils, sugars, and refined carbs
                   - Suggest whole-grain or plant-based substitutes where appropriate
                   - Add portion-control or preparation tips to keep it healthier

                4. Presentation Style 📑
                   - Use clear markdown formatting
                   - Present ingredients in a structured list
                   - Number cooking steps clearly
                   - Add emoji indicators:
                     🌱 Vegetarian
                     🌿 Vegan
                     🌾 Gluten-free
                     🥜 Contains nuts
                     🍗 Contains meat/poultry
                     🐟 Contains fish/seafood
                     🩺 Healthier version
                   - Include cultural notes (e.g. "This dish originates from Kerala's backwater cuisine")
                   - Suggest side dishes authentic to the region/state

                5. Feedback & Adaptation 🔄
                   - Accept user feedback on taste & authenticity
                   - Adjust future suggestions accordingly
            """),
            markdown=True,
        )

    async def generate_regional_meal_plan(self, cuisine_region: str, meal_type: str = "full_day",
                                        dietary_restrictions: list = None, time_constraint: int = 60,
                                        cooking_skill: str = "intermediate", available_ingredients: list = None,
                                        macro_target=None, goal_context: str = "") -> dict:
        """
        Generate a regional meal plan using CulinaryExplorer agent.

        `macro_target` is optional and off by default, so the generic behaviour
        is unchanged. When given, it goes LAST in the prompt: models weight the
        end most heavily, and a nutritional requirement buried above four lines
        about authenticity gets treated as a suggestion.
        """
        try:
            dietary_str = f"Dietary restrictions: {', '.join(dietary_restrictions)}." if dietary_restrictions else ""
            ingredients_str = f"Available ingredients: {', '.join(available_ingredients)}." if available_ingredients else ""
            macro_str = f"\n\n            {macro_target.prompt_block()}" if macro_target else ""
            # Before the macro block, not after: the macro numbers are the hard
            # requirement and must stay last, where the model weights most
            # heavily. The goal is context that shapes the choices within them.
            goal_str = f"\n\n            {goal_context.strip()}" if goal_context else ""

            prompt = f"""I'm interested in {cuisine_region} cuisine and want a {meal_type} meal plan.
            {dietary_str}
            {ingredients_str}
            I have {time_constraint} minutes for cooking and my skill level is {cooking_skill}.
            
            Please create a healthy, authentic {cuisine_region} meal plan with traditional dishes
            that have been modified for better health while maintaining cultural authenticity.{goal_str}{macro_str}"""

            logger.info(f"CulinaryExplorer prompt: {prompt}")
            response = self.regional_food_agent.run(prompt)
            logger.info(f"CulinaryExplorer raw response: {response}")

            # Extract content from RunOutput
            meal_plan = response.content if hasattr(response, 'content') else str(response)

            # Check the numbers rather than trusting them. Asking a model to
            # hit four figures and assuming it did is a hope, not a feature -
            # and the failure is silent, which is the worst kind.
            verification = None
            if macro_target is not None:
                from app.services import macro_targets as mt

                verification = mt.verify(macro_target, meal_plan)

                # One retry, naming exactly what was wrong and by how much.
                # "Try again" produces a differently wrong answer at the same
                # cost; a specific correction usually lands.
                if verification.get("checked") and not verification.get("hit"):
                    logger.warning("Macro target missed on %s: %s",
                                   cuisine_region, verification.get("summary"))
                    try:
                        retry = f"{prompt}\n\n            {mt.retry_brief(verification, macro_target)}"
                        again = self.regional_food_agent.run(retry)
                        second = again.content if hasattr(again, "content") else str(again)
                        recheck = mt.verify(macro_target, second)
                        # Keep the better attempt. A retry that makes things
                        # worse must not replace a near miss.
                        if _closer(recheck, verification):
                            meal_plan, verification = second, recheck
                            verification["retried"] = True
                    except Exception as e:
                        logger.warning("Macro retry failed, keeping first attempt: %s", e)

            return {
                "success": True,
                "meal_plan": meal_plan,
                "verification": verification,
                "cuisine_region": cuisine_region,
                "meal_type": meal_type,
                "dietary_restrictions": dietary_restrictions or [],
                "time_constraint": time_constraint,
                "cooking_skill": cooking_skill,
                "available_ingredients": available_ingredients or []
            }
        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg or "Rate limit reached" in error_msg:
                logger.error(f"Groq API rate limit exceeded: {e}")
                return {
                    "success": True,
                    "meal_plan": f"""**{cuisine_region.title()} Lunch Meal Plan 🍴**

### Traditional {cuisine_region.title()} Cuisine
Due to high AI service usage, here's a curated meal plan based on traditional {cuisine_region.title()} cuisine:

**Main Course:**
- Traditional {cuisine_region.title()} rice dish
- Regional vegetable curry
- Fresh salad with local ingredients

**Side Dishes:**
- Traditional bread/roti
- Pickle/chutney
- Yogurt/curd

**Cooking Tips:**
- Use traditional spices and cooking methods
- Focus on fresh, local ingredients
- Maintain authentic flavors while reducing oil

*Note: AI service is temporarily unavailable. This is a general {cuisine_region.title()} meal plan. Please try again later for personalized recipes.*""",
                    "cuisine_region": cuisine_region,
                    "meal_type": meal_type,
                    "dietary_restrictions": dietary_restrictions or [],
                    "time_constraint": time_constraint,
                    "cooking_skill": cooking_skill,
                    "available_ingredients": available_ingredients or []
                }
            else:
                logger.error(f"Error generating regional meal plan with CulinaryExplorer: {e}")
                return {"success": False, "error": str(e)}

    async def generate_regional_recipe(self, cuisine_region: str, dish_name: str = None,
                                     dietary_restrictions: list = None, time_constraint: int = 60,
                                     cooking_skill: str = "intermediate", available_ingredients: list = None) -> dict:
        """Generate a specific regional recipe using CulinaryExplorer agent"""
        try:
            dish_prompt = f" for {dish_name}" if dish_name else ""
            dietary_str = f"Dietary restrictions: {', '.join(dietary_restrictions)}." if dietary_restrictions else ""
            ingredients_str = f"Available ingredients: {', '.join(available_ingredients)}." if available_ingredients else ""
            
            prompt = f"""I want a {cuisine_region} recipe{dish_prompt}.
            {dietary_str}
            {ingredients_str}
            I have {time_constraint} minutes for cooking and my skill level is {cooking_skill}.
            
            Please provide a healthy, authentic {cuisine_region} recipe with traditional flavors
            but modified for better health. Include cultural context and serving suggestions."""

            logger.info(f"CulinaryExplorer recipe prompt: {prompt}")
            response = self.regional_food_agent.run(prompt)
            logger.info(f"CulinaryExplorer recipe response: {response}")

            # Extract content from RunOutput
            recipe = response.content if hasattr(response, 'content') else str(response)

            return {
                "success": True,
                "recipe": recipe,
                "cuisine_region": cuisine_region,
                "dish_name": dish_name,
                "dietary_restrictions": dietary_restrictions or [],
                "time_constraint": time_constraint,
                "cooking_skill": cooking_skill,
                "available_ingredients": available_ingredients or []
            }
        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg or "Rate limit reached" in error_msg:
                logger.error(f"Groq API rate limit exceeded: {e}")
                
                # Provide a specific masala dosa recipe if that's what was requested
                if dish_name and "dosa" in dish_name.lower():
                    return {
                        "success": True,
                        "recipe": f"""**Masala Dosa Recipe 🥞**

### Traditional Kerala Masala Dosa
Due to high AI service usage, here's a traditional masala dosa recipe:

**For Dosa Batter:**
- 2 cups rice (preferably parboiled rice)
- 1/2 cup urad dal (black gram dal)
- 1/4 tsp fenugreek seeds
- Salt to taste

**For Masala Filling:**
- 3-4 medium potatoes, boiled and mashed
- 1 large onion, finely chopped
- 2-3 green chilies, chopped
- 1 tsp mustard seeds
- 1 tsp turmeric powder
- 2 tbsp oil
- Curry leaves
- Salt to taste

**Instructions:**
1. **Prepare Batter:** Soak rice and dal separately for 4-6 hours. Grind to smooth paste. Ferment overnight.
2. **Make Masala:** Heat oil, add mustard seeds, curry leaves. Add onions, chilies. Add mashed potatoes, turmeric, salt. Mix well.
3. **Cook Dosa:** Heat tawa, pour batter, spread thin. Cook until golden, flip, add masala, fold.

**Serving:** Serve hot with coconut chutney and sambar.

*Note: AI service temporarily unavailable. This is a traditional recipe. Try again later for personalized variations.*""",
                        "dish_name": dish_name,
                        "cuisine_region": cuisine_region,
                        "cooking_time": time_constraint,
                        "difficulty": cooking_skill,
                        "ingredients": available_ingredients or []
                    }
                else:
                    return {
                        "success": True,
                        "recipe": f"""**Traditional {cuisine_region.title()} Recipe 🍴**

### {dish_name or f"{cuisine_region.title()} Special Dish"}
Due to high AI service usage, here's a traditional recipe:

**Ingredients:**
- Traditional {cuisine_region.title()} spices
- Fresh vegetables
- Regional grains/rice
- Local herbs and seasonings

**Cooking Method:**
- Use traditional cooking techniques
- Focus on authentic flavors
- Maintain cultural authenticity

**Serving Suggestions:**
- Serve with traditional accompaniments
- Use authentic presentation style

*Note: AI service temporarily unavailable. This is a general {cuisine_region.title()} recipe. Try again later for detailed instructions.*""",
                        "dish_name": dish_name,
                        "cuisine_region": cuisine_region,
                        "cooking_time": time_constraint,
                        "difficulty": cooking_skill,
                        "ingredients": available_ingredients or []
                    }
            else:
                logger.error(f"Error generating regional recipe with CulinaryExplorer: {e}")
                return {"success": False, "error": str(e)}

    async def adapt_regional_plan(self, current_plan: str, feedback: str,
                                new_cuisine_preference: str = None, new_dietary_restrictions: list = None) -> dict:
        """Adapt existing regional meal plan based on user feedback"""
        try:
            cuisine_change_str = f"New cuisine preference: {new_cuisine_preference}." if new_cuisine_preference else ""
            dietary_change_str = f"New dietary restrictions: {', '.join(new_dietary_restrictions)}." if new_dietary_restrictions else ""
            
            prompt = f"""Based on this feedback, please adapt the regional meal plan:

            Current Plan:
            {current_plan}

            User Feedback:
            {feedback}

            {cuisine_change_str}
            {dietary_change_str}

            Please provide an updated regional meal plan that addresses the feedback while maintaining
            cultural authenticity and health benefits."""

            logger.info(f"CulinaryExplorer adaptation prompt: {prompt}")
            response = self.regional_food_agent.run(prompt)
            logger.info(f"CulinaryExplorer adaptation response: {response}")

            # Extract content from RunOutput
            adapted_plan = response.content if hasattr(response, 'content') else str(response)

            return {
                "success": True,
                "adapted_plan": adapted_plan,
                "feedback": feedback,
                "new_cuisine_preference": new_cuisine_preference,
                "new_dietary_restrictions": new_dietary_restrictions
            }
        except Exception as e:
            logger.error(f"Error adapting regional plan with CulinaryExplorer: {e}")
            return {"success": False, "error": str(e)}

culinaryexplorer_service = CulinaryExplorerService()
