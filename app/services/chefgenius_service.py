from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from agno.tools.exa import ExaTools
from dotenv import load_dotenv
from textwrap import dedent
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class ChefGeniusService:
    def __init__(self):
        self.recipe_agent = Agent(
            name="ChefGenius",
            tools=[ExaTools()],
            model=GroqWithFallback(id="llama-3.3-70b-versatile"),
            description=dedent("""\
                You are ChefGenius, a passionate and knowledgeable culinary expert with expertise in global cuisine! 🍳

                Your mission is to help users create delicious meals by providing detailed,
                personalized recipes based on their available ingredients, dietary restrictions,
                and time constraints. You combine deep culinary knowledge with nutritional wisdom
                to suggest recipes that are both practical and enjoyable."""),
            instructions=dedent("""\
                Approach each recipe recommendation with these steps:

                1. Analysis Phase 📋
                   - Understand available ingredients
                   - Consider dietary restrictions (if any)
                   - Note time constraints
                   - Factor in cooking skill level
                   - Check for kitchen equipment needs

                Dietary Flexibility:
                - If no dietary restrictions are specified, create the best recipe using available ingredients
                - If meat/protein ingredients are available, feel free to use them for complete nutrition
                - Only restrict to vegetarian/vegan if explicitly requested
                - Balance nutrition and taste based on available ingredients

                Presentation Style:
                - Use clear markdown formatting
                - Present ingredients in a structured list
                - Number cooking steps clearly
                - Add emoji indicators for:
                  🌱 Vegetarian (only if explicitly requested)
                  🌿 Vegan (only if explicitly requested)
                  🌾 Gluten-free
                  🥜 Contains nuts
                  ⏱️ Quick recipes
                  🥩 Non-vegetarian (if meat/protein is used)
                - Include tips for scaling portions
                - Note allergen warnings
                - Highlight make-ahead steps
                - Suggest side dish pairings"""),
        )

    async def generate_recipe_from_ingredients(self, ingredients: list, dietary_restrictions: list = None, 
                                             time_constraint: int = 60, meal_type: str = "dinner") -> dict:
        """Generate recipe using ChefGenius agent based on available ingredients"""
        try:
            # Build the prompt for the agent
            ingredients_str = ", ".join(ingredients)
            
            # Handle dietary restrictions more intelligently
            dietary_guidance = ""
            if dietary_restrictions:
                if "vegetarian" in dietary_restrictions:
                    dietary_guidance = "IMPORTANT: This must be a VEGETARIAN recipe. Do not include any meat, poultry, fish, or seafood. Use plant-based proteins like beans, lentils, tofu, or dairy if needed."
                elif "vegan" in dietary_restrictions:
                    dietary_guidance = "IMPORTANT: This must be a VEGAN recipe. Do not include any animal products including meat, dairy, eggs, or honey. Use plant-based alternatives."
                else:
                    dietary_guidance = f"Dietary considerations: {', '.join(dietary_restrictions)}"
            else:
                dietary_guidance = "You can create either vegetarian or non-vegetarian recipes based on the available ingredients. If meat/protein ingredients are available, feel free to use them for a complete meal."
            
            prompt = f"""I have these ingredients: {ingredients_str}. 
            {dietary_guidance}
            I need a healthy {meal_type} recipe that takes less than {time_constraint} minutes.
            Please provide a detailed recipe with ingredients list, step-by-step instructions, 
            cooking time, and nutritional information. Make sure the recipe is practical and delicious!"""
            
            # Get response from ChefGenius agent
            response = self.recipe_agent.run(prompt)
            
            return {
                "success": True,
                "recipe": response.content,
                "ingredients_used": ingredients,
                "dietary_restrictions": dietary_restrictions or [],
                "time_constraint": time_constraint,
                "meal_type": meal_type
            }
            
        except Exception as e:
            logger.error(f"Error generating recipe with ChefGenius: {str(e)}")
            return {
                "success": False,
                "error": f"Recipe generation failed: {str(e)}",
                "recipe": None
            }

# Global instance
chefgenius_service = ChefGeniusService()
