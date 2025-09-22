import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import User, UserPreference, get_db
from app.services.chefgenius_service import ChefGeniusService
from app.services.culinaryexplorer_service import CulinaryExplorerService
from app.services.budgetchef_service import BudgetChefService
from app.services.fitmentor_service import FitMentorService
from app.services.advanced_meal_planner_service import AdvancedMealPlannerService
from app.services.nutrient_analyzer_service import NutrientAnalyzerService

logger = logging.getLogger(__name__)

class ChatbotManager:
    def __init__(self):
        self.agents = {
            "chefgenius": ChefGeniusService(),
            "culinaryexplorer": CulinaryExplorerService(),
            "budgetchef": BudgetChefService(),
            "fitmentor": FitMentorService(),
            "advanced_meal_planner": AdvancedMealPlannerService(),
            "nutrient_analyzer": NutrientAnalyzerService()
        }
        
        # Conversation memory for each user
        self.conversation_memory = {}
        
        # Intent detection keywords
        self.intent_keywords = {
            "chefgenius": ["ingredients", "cooking", "food"],
            "culinaryexplorer": ["recipe", "cook", "dish", "meal", "regional", "cuisine", "kerala", "punjab", "gujarat", "tamil", "rajasthan", "mediterranean", "japanese", "mexican", "italian", "chinese", "thai", "dosa", "masala", "indian", "south indian", "north indian", "curry", "biryani", "dal", "roti", "naan", "samosa", "vada", "idli", "sambar", "chutney", "how to make", "how to cook"],
            "budgetchef": ["budget", "cheap", "cost", "money", "affordable", "economical", "price"],
            "fitmentor": ["workout", "exercise", "fitness", "gym", "training", "muscle", "weight", "cardio", "burn", "lose", "kg", "pounds", "active"],
            "advanced_meal_planner": ["meal plan", "weekly plan", "7-day", "diet plan", "nutrition plan", "meal planning"],
            "nutrient_analyzer": ["nutrition", "calories", "protein", "carbs", "fat", "analyze", "nutrient", "macro"]
        }

    def detect_agent(self, query: str, conversation_history: list = None) -> str:
        """Detect which agent should handle the query based on keywords and conversation context"""
        query_lower = query.lower()
        
        # Check conversation context first
        if conversation_history:
            # Look at last few messages to understand context
            recent_messages = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
            context_text = " ".join([msg.get("user", "") + " " + msg.get("bot", "") for msg in recent_messages]).lower()
            
            # If recent context suggests a specific agent, prioritize it
            if any(word in context_text for word in ["workout", "exercise", "fitness", "gym", "training", "muscle", "weight", "cardio"]):
                if any(word in query_lower for word in ["active", "activity", "level", "intensity", "workout", "exercise"]):
                    return "fitmentor"
            
            if any(word in context_text for word in ["recipe", "cook", "ingredients", "cooking", "dish", "meal", "food"]):
                if any(word in query_lower for word in ["more", "another", "different", "ingredient", "cook", "recipe"]):
                    return "chefgenius"
        
        # Score each agent based on keyword matches
        scores = {}
        for agent, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                scores[agent] = score
        
        # If no clear match, check for context clues
        if not scores or max(scores.values()) == 0:
            # Check for follow-up indicators
            if any(word in query_lower for word in ["more", "another", "different", "also", "and", "then"]):
                # Return the same agent as the last conversation
                if conversation_history:
                    last_response = conversation_history[-1].get("bot", "").lower()
                    if "workout" in last_response or "exercise" in last_response:
                        return "fitmentor"
                    elif "recipe" in last_response or "cook" in last_response:
                        return "chefgenius"
            
            return "chefgenius"  # Default fallback
        
        return max(scores, key=scores.get)

    def get_required_fields(self, agent_name: str) -> dict:
        """Get required fields for each agent"""
        field_requirements = {
            "chefgenius": {
                "required": ["ingredients", "dietary_restrictions", "time_constraint", "meal_type"],
                "optional": ["cuisine_preference", "difficulty_level"],
                "description": "Recipe Generation"
            },
            "culinaryexplorer": {
                "required": ["cuisine_region", "meal_type", "dietary_restrictions", "time_constraint", "cooking_skill"],
                "optional": ["available_ingredients"],
                "description": "Regional Cuisine Exploration"
            },
            "budgetchef": {
                "required": ["budget_per_day", "calorie_target", "dietary_preferences", "meals_per_day", "cooking_time", "skill_level"],
                "optional": ["age", "weight", "activity_level"],
                "description": "Budget Meal Planning"
            },
            "fitmentor": {
                "required": ["activity_level", "fitness_goal", "time_per_day", "equipment"],
                "optional": ["age", "weight", "constraints"],
                "description": "Workout Planning"
            },
            "advanced_meal_planner": {
                "required": ["target_calories", "meals_per_day", "food_preferences", "dietary_restrictions"],
                "optional": ["budget_per_day", "work_hours_per_day", "equipment", "time_per_meal_min", "region_or_cuisine", "user_notes"],
                "description": "Advanced Meal Planning"
            },
            "nutrient_analyzer": {
                "required": ["food_name", "serving_size"],
                "optional": [],
                "description": "Nutrition Analysis"
            }
        }
        return field_requirements.get(agent_name, {})

    def get_conversation_context(self, user_id: int) -> list:
        """Get last 5-6 messages from conversation memory"""
        return self.conversation_memory.get(user_id, [])[-6:] if user_id in self.conversation_memory else []

    def add_to_memory(self, user_id: int, message: str, response: str):
        """Add message and response to conversation memory"""
        if user_id not in self.conversation_memory:
            self.conversation_memory[user_id] = []
        
        self.conversation_memory[user_id].append({
            "user": message,
            "bot": response,
            "timestamp": datetime.now()
        })
        
        # Keep only last 10 messages
        if len(self.conversation_memory[user_id]) > 10:
            self.conversation_memory[user_id] = self.conversation_memory[user_id][-10:]

    def extract_context_info(self, user_query: str, conversation_history: list, user_context: dict) -> dict:
        """Extract information from conversation history and user query"""
        context_info = {}
        query_lower = user_query.lower()
        
        # Combine all previous messages for context
        all_text = user_query + " " + " ".join([msg["user"] + " " + msg["bot"] for msg in conversation_history])
        all_text_lower = all_text.lower()
        
        # Extract dietary info
        if any(word in all_text_lower for word in ["vegetarian", "vegan", "no meat"]):
            context_info["dietary_restrictions"] = ["vegetarian"]
        elif any(word in all_text_lower for word in ["gluten-free", "gluten free"]):
            context_info["dietary_restrictions"] = ["gluten-free"]
        elif any(word in all_text_lower for word in ["dairy-free", "dairy free"]):
            context_info["dietary_restrictions"] = ["dairy-free"]
        
        # Extract meal info
        if any(word in all_text_lower for word in ["breakfast", "morning"]):
            context_info["meal_type"] = "breakfast"
        elif any(word in all_text_lower for word in ["lunch", "afternoon"]):
            context_info["meal_type"] = "lunch"
        elif any(word in all_text_lower for word in ["dinner", "evening", "night"]):
            context_info["meal_type"] = "dinner"
        elif any(word in all_text_lower for word in ["snack"]):
            context_info["meal_type"] = "snack"
        
        # Extract time info
        import re
        time_match = re.search(r'(\d+)\s*(minutes?|min|hours?|hr)', all_text_lower)
        if time_match:
            time_val = int(time_match.group(1))
            if "hour" in time_match.group(2):
                time_val *= 60
            context_info["time_constraint"] = time_val
            context_info["time_per_day"] = time_val
        
        # Extract calorie info
        calorie_match = re.search(r'(\d+)\s*calories?', all_text_lower)
        if calorie_match:
            context_info["target_calories"] = int(calorie_match.group(1))
            context_info["calorie_target"] = int(calorie_match.group(1))
        
        # Extract budget info
        budget_match = re.search(r'(\d+)\s*(rupees?|rs|₹)', all_text_lower)
        if budget_match:
            context_info["budget_per_day"] = float(budget_match.group(1))
        
        # Extract fitness goals
        if any(word in all_text_lower for word in ["muscle gain", "muscle_gain", "build muscle"]):
            context_info["fitness_goal"] = "muscle_gain"
        elif any(word in all_text_lower for word in ["weight loss", "weight_loss", "lose weight"]):
            context_info["fitness_goal"] = "weight_loss"
        elif any(word in all_text_lower for word in ["general fitness", "general_fitness"]):
            context_info["fitness_goal"] = "general_fitness"
        
        # Extract equipment
        if any(word in all_text_lower for word in ["gym", "dumbbell", "barbell", "weights"]):
            context_info["equipment"] = "gym"
        elif any(word in all_text_lower for word in ["bodyweight", "body weight", "no equipment"]):
            context_info["equipment"] = "bodyweight"
        elif any(word in all_text_lower for word in ["home", "home equipment"]):
            context_info["equipment"] = "home_equipment"
        
        # Extract cuisine info
        if any(word in all_text_lower for word in ["kerala", "keralite"]):
            context_info["cuisine_region"] = "kerala"
        elif any(word in all_text_lower for word in ["punjab", "punjabi"]):
            context_info["cuisine_region"] = "punjab"
        elif any(word in all_text_lower for word in ["mediterranean"]):
            context_info["cuisine_region"] = "mediterranean"
        elif any(word in all_text_lower for word in ["japanese"]):
            context_info["cuisine_region"] = "japanese"
        
        # Extract ingredients
        ingredients = []
        ingredient_words = ["chicken", "rice", "vegetables", "onion", "tomato", "potato", "carrot", "beans", "lentils", "dal", "curry", "soup", "salad", "pasta", "bread"]
        for word in ingredient_words:
            if word in all_text_lower:
                ingredients.append(word)
        if ingredients:
            context_info["ingredients"] = ingredients
        
        return context_info

    def check_missing_fields(self, agent_name: str, user_query: str, user_context: dict, conversation_history: list = None) -> dict:
        """Check what fields are missing with smart defaults and context awareness"""
        requirements = self.get_required_fields(agent_name)
        if not requirements:
            return {"missing": False, "message": ""}
        
        # Extract context information
        context_info = self.extract_context_info(user_query, conversation_history or [], user_context)
        
        # Smart defaults based on user profile and context
        smart_defaults = {
            "meals_per_day": 3,
            "time_constraint": 30,
            "time_per_day": 60,
            "cooking_skill": "intermediate",
            "skill_level": "intermediate",
            "equipment": "bodyweight",
            "serving_size": "100g",
            "dietary_restrictions": user_context.get("dietary_preferences", []),
            "dietary_preferences": user_context.get("dietary_preferences", []),
            "target_calories": 2000,
            "calorie_target": 2000,
            "activity_level": user_context.get("activity_level", "moderately_active"),
            "fitness_goal": "general_fitness"
        }
        
        missing_fields = []
        query_lower = user_query.lower()
        
        # Check required fields with smart context awareness
        for field in requirements.get("required", []):
            field_found = False
            
            # Check if field is in user context
            if field in user_context and user_context[field]:
                field_found = True
            
            # Check if field is in extracted context
            if field in context_info and context_info[field]:
                field_found = True
            
            # Check if field is explicitly mentioned in query
            if field.replace("_", " ") in query_lower or field in query_lower:
                field_found = True
            
            # For some fields, if not found, use smart defaults instead of asking
            if not field_found and field in smart_defaults:
                # Use smart default instead of asking
                context_info[field] = smart_defaults[field]
                field_found = True
            
            if not field_found:
                missing_fields.append(field)
        
        # Only ask for truly essential fields that can't be defaulted
        essential_fields = ["food_name", "ingredients", "cuisine_region"]
        missing_essential = [f for f in missing_fields if f in essential_fields]
        
        if missing_essential and len(missing_essential) <= 2:  # Only ask if 2 or fewer essential fields missing
            field_prompts = {
                "food_name": "What food would you like to analyze?",
                "ingredients": "What ingredients do you have available?",
                "cuisine_region": "Which cuisine/region? (e.g., Kerala, Punjab, Mediterranean)"
            }
            
            message = f"I need just a bit more info:\n\n"
            for field in missing_essential:
                message += f"• {field_prompts.get(field, f'Please specify {field}')}\n"
            
            return {"missing": True, "message": message, "missing_fields": missing_essential, "context_info": context_info}
        
        return {"missing": False, "message": "", "context_info": context_info}

    def get_user_context(self, user_id: int, db: Session) -> Dict[str, Any]:
        """Fetch user context from database"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            # Parse JSON fields
            health_conditions = []
            dietary_preferences = []
            
            if user.health_conditions:
                try:
                    health_conditions = json.loads(user.health_conditions)
                except:
                    health_conditions = [user.health_conditions]
            
            if user.dietary_preferences:
                try:
                    dietary_preferences = json.loads(user.dietary_preferences)
                except:
                    dietary_preferences = [user.dietary_preferences]
            
            return {
                "user_id": user.id,
                "age": user.age,
                "weight": user.weight,
                "height": user.height,
                "activity_level": user.activity_level,
                "health_conditions": health_conditions,
                "dietary_preferences": dietary_preferences,
                "cuisine_pref": user.cuisine_pref,
                "full_name": user.full_name
            }
        except Exception as e:
            logger.error(f"Error fetching user context: {e}")
            return {}

    def build_agent_prompt(self, agent_name: str, user_query: str, user_context: Dict[str, Any]) -> str:
        """Build appropriate prompt for each agent"""
        context_str = f"User Context: {json.dumps(user_context, indent=2)}\n\n"
        
        if agent_name == "chefgenius":
            return f"{context_str}User Query: {user_query}\n\nPlease generate a recipe based on the user's preferences and available context."
        
        elif agent_name == "culinaryexplorer":
            return f"{context_str}User Query: {user_query}\n\nPlease suggest regional/cultural recipes and meal plans based on the user's preferences."
        
        elif agent_name == "budgetchef":
            return f"{context_str}User Query: {user_query}\n\nPlease create a budget-friendly meal plan considering the user's financial constraints and preferences."
        
        elif agent_name == "fitmentor":
            return f"{context_str}User Query: {user_query}\n\nPlease create a personalized workout plan based on the user's fitness level and goals."
        
        elif agent_name == "advanced_meal_planner":
            return f"{context_str}User Query: {user_query}\n\nPlease create a comprehensive 7-day meal plan based on the user's nutritional needs and preferences."
        
        elif agent_name == "nutrient_analyzer":
            return f"{context_str}User Query: {user_query}\n\nPlease analyze the nutritional content and provide detailed nutrition information."
        
        return f"{context_str}User Query: {user_query}"

    async def handle_query(self, user_id: int, user_query: str, db: Session) -> Dict[str, Any]:
        """Main method to handle user queries and route to appropriate agent"""
        try:
            # Get conversation history
            conversation_history = self.get_conversation_context(user_id)
            
            # Detect which agent to use
            agent_name = self.detect_agent(user_query, conversation_history)
            logger.info(f"Routing query to {agent_name} agent")
            
            # Get user context
            user_context = self.get_user_context(user_id, db)
            
            # Check if we have all required fields with smart context awareness
            field_check = self.check_missing_fields(agent_name, user_query, user_context, conversation_history)
            if field_check["missing"]:
                response = {
                    "success": True,
                    "agent_used": agent_name,
                    "response": field_check["message"],
                    "user_context": user_context,
                    "needs_more_info": True
                }
                # Add to memory
                self.add_to_memory(user_id, user_query, field_check["message"])
                return response
            
            # Use context info for smarter defaults
            context_info = field_check.get("context_info", {})
            
            # Build prompt
            prompt = self.build_agent_prompt(agent_name, user_query, user_context)
            
            # Get the appropriate agent
            agent_service = self.agents.get(agent_name)
            if not agent_service:
                return {
                    "success": False,
                    "error": f"Agent {agent_name} not found",
                    "agent_used": agent_name
                }
            
            # Route to specific agent methods with smart context
            if agent_name == "chefgenius":
                result = await agent_service.generate_recipe_from_ingredients(
                    ingredients=context_info.get("ingredients", []),
                    dietary_restrictions=context_info.get("dietary_restrictions", user_context.get("dietary_preferences", [])),
                    time_constraint=context_info.get("time_constraint", 30),
                    meal_type=context_info.get("meal_type", "lunch")
                )
            
            elif agent_name == "culinaryexplorer":
                # Check if user is asking for a specific recipe or dish
                query_lower = user_query.lower()
                specific_dish_keywords = ["recipe", "how to make", "how to cook", "dosa", "curry", "biryani", "dal", "roti", "naan", "samosa", "vada", "idli", "sambar", "chutney"]
                
                if any(keyword in query_lower for keyword in specific_dish_keywords):
                    # Extract dish name from query
                    dish_name = None
                    if "masala dosa" in query_lower:
                        dish_name = "masala dosa"
                    elif "dosa" in query_lower:
                        dish_name = "dosa"
                    elif "curry" in query_lower:
                        dish_name = "curry"
                    elif "biryani" in query_lower:
                        dish_name = "biryani"
                    
                    result = await agent_service.generate_regional_recipe(
                        cuisine_region=context_info.get("cuisine_region", user_context.get("cuisine_pref", "indian")),
                        dish_name=dish_name,
                        dietary_restrictions=context_info.get("dietary_restrictions", user_context.get("dietary_preferences", [])),
                        time_constraint=context_info.get("time_constraint", 60),
                        cooking_skill=context_info.get("cooking_skill", "intermediate"),
                        available_ingredients=context_info.get("ingredients", [])
                    )
                else:
                    # Default to meal plan generation
                    result = await agent_service.generate_regional_meal_plan(
                        cuisine_region=context_info.get("cuisine_region", user_context.get("cuisine_pref", "indian")),
                        meal_type=context_info.get("meal_type", "lunch"),
                        dietary_restrictions=context_info.get("dietary_restrictions", user_context.get("dietary_preferences", [])),
                        time_constraint=context_info.get("time_constraint", 30),
                        cooking_skill=context_info.get("cooking_skill", "intermediate"),
                        available_ingredients=context_info.get("ingredients", [])
                    )
            
            elif agent_name == "budgetchef":
                result = await agent_service.generate_budget_meal_plan(
                    budget_per_day=context_info.get("budget_per_day", 200.0),
                    calorie_target=context_info.get("calorie_target", 2000),
                    dietary_preferences=context_info.get("dietary_preferences", user_context.get("dietary_preferences", [])),
                    meals_per_day=context_info.get("meals_per_day", 3),
                    cooking_time=context_info.get("cooking_time", "moderate"),
                    skill_level=context_info.get("skill_level", "intermediate"),
                    age=user_context.get("age"),
                    weight=user_context.get("weight"),
                    activity_level=context_info.get("activity_level", user_context.get("activity_level", "moderate"))
                )
            
            elif agent_name == "fitmentor":
                result = await agent_service.generate_workout_plan(
                    activity_level=context_info.get("activity_level", user_context.get("activity_level", "moderately_active")),
                    fitness_goal=context_info.get("fitness_goal", "muscle_gain"),
                    time_per_day=context_info.get("time_per_day", 60),
                    equipment=context_info.get("equipment", "bodyweight"),
                    constraints=user_context.get("health_conditions", []),
                    age=user_context.get("age"),
                    weight=user_context.get("weight")
                )
            
            elif agent_name == "advanced_meal_planner":
                result = agent_service.generate_meal_plan({
                    "target_calories": context_info.get("target_calories", 2000),
                    "meals_per_day": context_info.get("meals_per_day", 3),
                    "food_preferences": context_info.get("food_preferences", user_context.get("dietary_preferences", [])),
                    "dietary_restrictions": context_info.get("dietary_restrictions", user_context.get("health_conditions", [])),
                    "region_or_cuisine": context_info.get("cuisine_region", user_context.get("cuisine_pref", "mixed")),
                    "user_notes": user_query
                })
            
            elif agent_name == "nutrient_analyzer":
                result = agent_service.analyze_food_nutrition(
                    food_name=context_info.get("food_name", user_query),
                    serving_size=context_info.get("serving_size", "100g")
                )
            
            else:
                result = {"success": False, "error": "Unknown agent"}
            
            # Check if result has an error and provide fallback
            if isinstance(result, dict) and not result.get("success", True):
                error_msg = result.get("error", "Unknown error")
                if "rate limit" in str(error_msg).lower() or "rate_limit" in str(error_msg).lower():
                    fallback_response = f"I understand you want help with {agent_name.replace('_', ' ')}. However, our AI service is currently experiencing high usage. Here's what I can tell you:\n\n"
                    
                    if agent_name == "fitmentor":
                        fallback_response += "For muscle gain workouts, focus on:\n• Compound exercises (squats, deadlifts, bench press)\n• Progressive overload\n• 6-12 reps per set\n• 3-4 sets per exercise\n• 48-72 hours rest between muscle groups\n\n**Sample Workout:**\n- Push-ups: 3 sets of 12 reps\n- Squats: 3 sets of 15 reps\n- Planks: 3 sets of 60 seconds\n- Lunges: 3 sets of 12 reps per leg"
                    elif agent_name == "chefgenius":
                        # Check if the query is about dosa or South Indian food
                        if any(keyword in user_query.lower() for keyword in ["dosa", "masala", "south indian", "kerala", "tamil"]):
                            fallback_response += "**Traditional Masala Dosa Recipe 🥞**\n\n**For Dosa Batter:**\n- 2 cups rice (preferably parboiled rice)\n- 1/2 cup urad dal (black gram dal)\n- 1/4 tsp fenugreek seeds\n- Salt to taste\n\n**For Masala Filling:**\n- 3-4 medium potatoes, boiled and mashed\n- 1 large onion, finely chopped\n- 2-3 green chilies, chopped\n- 1 tsp mustard seeds\n- 1 tsp turmeric powder\n- 2 tbsp oil\n- Curry leaves\n- Salt to taste\n\n**Instructions:**\n1. **Prepare Batter:** Soak rice and dal separately for 4-6 hours. Grind to smooth paste. Ferment overnight.\n2. **Make Masala:** Heat oil, add mustard seeds, curry leaves. Add onions, chilies. Add mashed potatoes, turmeric, salt. Mix well.\n3. **Cook Dosa:** Heat tawa, pour batter, spread thin. Cook until golden, flip, add masala, fold.\n\n**Serving:** Serve hot with coconut chutney and sambar."
                        else:
                            fallback_response += "For recipe suggestions, consider:\n• Using fresh, seasonal ingredients\n• Balancing macronutrients\n• Proper cooking techniques\n• Dietary restrictions and preferences\n\n**Sample Recipe:**\n- Kerala Chicken Curry: Marinate chicken with turmeric, chili powder, and salt. Cook with onions, tomatoes, and coconut milk. Serve with rice."
                    elif agent_name == "nutrient_analyzer":
                        fallback_response += "For nutrition analysis, I can help you understand:\n• Macronutrient breakdown (protein, carbs, fats)\n• Micronutrient content\n• Calorie density\n• Health benefits and considerations\n\n**Sample Analysis:**\n- Chicken Curry (100g): ~150 calories, 20g protein, 8g carbs, 6g fat"
                    elif agent_name == "culinaryexplorer":
                        fallback_response += "For regional cuisine, consider:\n• Traditional cooking methods\n• Local spices and ingredients\n• Cultural significance\n• Health adaptations\n\n**Sample Kerala Dishes:**\n- Fish Curry with coconut milk\n- Appam with vegetable stew\n- Kerala beef fry"
                    elif agent_name == "budgetchef":
                        fallback_response += "For budget meal planning:\n• Use seasonal, local ingredients\n• Plan meals around staple foods\n• Buy in bulk when possible\n• Cook in batches\n\n**Sample Budget Meal:**\n- Dal (lentils) with rice: ~₹30 per serving\n- Vegetable curry with roti: ~₹25 per serving"
                    elif agent_name == "advanced_meal_planner":
                        fallback_response += "For meal planning:\n• Calculate your daily calorie needs\n• Plan 3 main meals + 2 snacks\n• Include all food groups\n• Prep ingredients in advance\n\n**Sample 2000-calorie day:**\n- Breakfast: Oatmeal with fruits (400 cal)\n- Lunch: Rice with dal and vegetables (600 cal)\n- Dinner: Roti with chicken curry (500 cal)\n- Snacks: Nuts and fruits (500 cal)"
                    else:
                        fallback_response += f"Please try again in a few minutes when our AI service is available."
                    
                    return {
                        "success": True,
                        "agent_used": agent_name,
                        "response": fallback_response,
                        "user_context": user_context,
                        "fallback": True
                    }
            
            # Extract response text for memory
            response_text = result
            if isinstance(result, dict):
                if "data" in result:
                    response_text = result["data"]
                elif "message" in result:
                    response_text = result["message"]
                elif "recipe" in result:
                    response_text = result["recipe"]
                else:
                    response_text = str(result)
            
            # Add to memory
            self.add_to_memory(user_id, user_query, response_text)
            
            return {
                "success": True,
                "agent_used": agent_name,
                "response": result,
                "user_context": user_context
            }
            
        except Exception as e:
            logger.error(f"Error in handle_query: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_used": "unknown"
            }

    def get_available_agents(self) -> List[Dict[str, str]]:
        """Get list of available agents with descriptions"""
        return [
            {"name": "chefgenius", "description": "Recipe generation and cooking advice"},
            {"name": "culinaryexplorer", "description": "Regional and cultural cuisine exploration"},
            {"name": "budgetchef", "description": "Budget-friendly meal planning"},
            {"name": "fitmentor", "description": "Fitness and workout planning"},
            {"name": "advanced_meal_planner", "description": "Comprehensive 7-day meal planning"},
            {"name": "nutrient_analyzer", "description": "Nutritional analysis and tracking"}
        ]
