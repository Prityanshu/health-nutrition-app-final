# app/services/advanced_meal_planning.py
"""
Advanced meal planning with variety constraints, macro targeting, and intelligent recommendations
"""
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
import random
from collections import defaultdict, Counter

from app.database import User, FoodItem, MealLog
from app.schemas import MealItem, MealPlan, DayPlan

class AdvancedMealPlanner:
    def __init__(self, db: Session):
        self.db = db
        
    def generate_week_plan_with_variety(self, user: User, preferences: Dict) -> List[DayPlan]:
        """Generate a week meal plan with variety constraints"""
        
        # Get user's recent meals to avoid repetition
        recent_cutoff = datetime.utcnow() - timedelta(days=14)
        recent_foods = self.db.query(MealLog.food_item_id).filter(
            and_(
                MealLog.user_id == user.id,
                MealLog.logged_at >= recent_cutoff
            )
        ).all()
        recent_food_ids = {food_id[0] for food_id in recent_foods}
        
        # Get available foods, excluding recently eaten ones for variety
        available_foods = self.get_varied_food_selection(user, recent_food_ids, preferences)
        
        week_plans = []
        used_foods_this_week = set()
        
        for day in range(1, 8):
            # Ensure variety within the week
            day_foods = [f for f in available_foods if f.id not in used_foods_this_week]
            
            # If we're running low on variety, allow some repetition
            if len(day_foods) < preferences.get('meals_per_day', 3) * 2:
                day_foods = available_foods
            
            day_plan = self.generate_day_with_macro_targets(
                user, day_foods, preferences, day
            )
            
            # Track used foods for variety
            for meal in day_plan.meals:
                for item in meal.items:
                    used_foods_this_week.add(item.food_id)
            
            week_plans.append(day_plan)
        
        return week_plans
    
    def generate_day_with_macro_targets(self, user: User, foods: List[FoodItem], 
                                      preferences: Dict, day_num: int) -> DayPlan:
        """Generate a day plan targeting specific macro ratios"""
        
        target_calories = preferences.get('target_calories') or self.calculate_target_calories(user)
        meals_per_day = preferences.get('meals_per_day', 3)
        
        # Macro targets (percentages)
        protein_target = preferences.get('protein_percentage', 25) / 100  # 25% protein
        carb_target = preferences.get('carb_percentage', 45) / 100      # 45% carbs  
        fat_target = preferences.get('fat_percentage', 30) / 100        # 30% fat
        
        # Calculate macro targets in grams
        target_protein = (target_calories * protein_target) / 4  # 4 cal/g protein
        target_carbs = (target_calories * carb_target) / 4       # 4 cal/g carbs
        target_fat = (target_calories * fat_target) / 9          # 9 cal/g fat
        
        meals = []
        remaining_calories = target_calories
        remaining_protein = target_protein
        remaining_carbs = target_carbs
        remaining_fat = target_fat
        
        for meal_idx in range(meals_per_day):
            # Calculate targets for this meal
            meals_left = meals_per_day - meal_idx
            meal_cal_target = remaining_calories / meals_left
            meal_protein_target = remaining_protein / meals_left
            meal_carb_target = remaining_carbs / meals_left
            meal_fat_target = remaining_fat / meals_left
            
            # Generate meal with macro targeting
            meal = self.generate_macro_balanced_meal(
                foods, meal_cal_target, meal_protein_target, 
                meal_carb_target, meal_fat_target, meal_idx + 1
            )
            
            meals.append(meal)
            
            # Update remaining targets
            remaining_calories -= meal.total_calories
            remaining_protein -= meal.total_protein
            remaining_carbs -= sum(item.carbs_g for item in meal.items)
            remaining_fat -= sum(item.fat_g for item in meal.items)
        
        total_calories = sum(meal.total_calories for meal in meals)
        total_protein = sum(meal.total_protein for meal in meals)
        total_cost = sum(meal.total_cost for meal in meals)
        
        return DayPlan(
            day=day_num,
            meals=meals,
            total_calories=total_calories,
            total_protein=total_protein,
            total_cost=total_cost
        )
    
    def generate_macro_balanced_meal(self, foods: List[FoodItem], cal_target: float,
                                   protein_target: float, carb_target: float, 
                                   fat_target: float, meal_index: int) -> MealPlan:
        """Generate a single meal targeting specific macros"""
        
        # Sort foods by how well they match our macro needs
        scored_foods = []
        for food in foods:
            if food.calories > 0:  # Avoid division by zero
                protein_ratio = food.protein_g / food.calories * 4  # protein calories / total calories
                carb_ratio = food.carbs_g / food.calories * 4
                fat_ratio = food.fat_g / food.calories * 9
                
                # Calculate how well this food matches our needs
                protein_match = 1 - abs(protein_ratio - (protein_target / cal_target))
                carb_match = 1 - abs(carb_ratio - (carb_target / cal_target))
                fat_match = 1 - abs(fat_ratio - (fat_target / cal_target))
                
                overall_score = (protein_match + carb_match + fat_match) / 3
                scored_foods.append((food, overall_score))
        
        # Sort by score (best matches first)
        scored_foods.sort(key=lambda x: x[1], reverse=True)
        
        # Select foods for this meal (1-3 items)
        meal_items = []
        current_calories = 0
        current_protein = 0
        current_cost = 0
        
        for food, score in scored_foods[:5]:  # Consider top 5 matches
            if len(meal_items) >= 3:  # Max 3 items per meal
                break
                
            # Calculate optimal quantity
            if current_calories < cal_target * 0.8:  # Still need significant calories
                quantity = min(2.0, (cal_target - current_calories) / food.calories)
                quantity = max(0.5, quantity)  # Minimum serving size
                
                meal_item = MealItem(
                    food_id=food.id,
                    name=food.name,
                    calories=food.calories * quantity,
                    protein_g=food.protein_g * quantity,
                    carbs_g=food.carbs_g * quantity,
                    fat_g=food.fat_g * quantity,
                    quantity=quantity,
                    cost=food.cost * quantity
                )
                
                meal_items.append(meal_item)
                current_calories += meal_item.calories
                current_protein += meal_item.protein_g
                current_cost += meal_item.cost
        
        return MealPlan(
            meal_index=meal_index,
            items=meal_items,
            total_calories=current_calories,
            total_protein=current_protein,
            total_cost=current_cost
        )
    
    def get_varied_food_selection(self, user: User, exclude_ids: set, 
                                preferences: Dict) -> List[FoodItem]:
        """Get a varied selection of foods for meal planning"""
        
        query = self.db.query(FoodItem)
        
        # Apply health condition filters
        import json
        health_conditions = json.loads(user.health_conditions) if user.health_conditions else {}
        # Ensure health_conditions is a dict, not a list
        if isinstance(health_conditions, list):
            health_conditions = {}
        if health_conditions.get("diabetes"):
            query = query.filter(FoodItem.diabetic_friendly == True)
        
        if health_conditions.get("hypertension"):
            query = query.filter(FoodItem.hypertension_friendly == True)
        
        # Apply cuisine preference
        cuisine_pref = preferences.get('cuisine_type') or user.cuisine_pref
        if cuisine_pref and cuisine_pref != "mixed":
            query = query.filter(FoodItem.cuisine_type == cuisine_pref)
        
        # Exclude recently eaten foods for variety
        if exclude_ids:
            query = query.filter(~FoodItem.id.in_(exclude_ids))
        
        foods = query.all()
        
        # If we don't have enough variety, include some recent foods
        if len(foods) < 20:
            fallback_query = self.db.query(FoodItem)
            if cuisine_pref and cuisine_pref != "mixed":
                fallback_query = fallback_query.filter(FoodItem.cuisine_type == cuisine_pref)
            foods = fallback_query.all()
        
        return foods
    
    def calculate_target_calories(self, user: User) -> float:
        """Calculate target calories based on user profile and goals"""
        # This would integrate with your existing nutrition calculation
        from app.services.nutrition import NutritionCalculator
        return NutritionCalculator.get_target_calories(user)

# app/services/recipe_generator.py
"""
Enhanced recipe generation with LLM integration
"""
import json
from typing import List, Dict, Optional
import openai  # You'll need to install this: pip install openai
from app.database import FoodItem

class EnhancedRecipeGenerator:
    def __init__(self, openai_api_key: Optional[str] = None):
        if openai_api_key:
            openai.api_key = openai_api_key
            self.use_llm = True
        else:
            self.use_llm = False
            print("OpenAI API key not provided. Using template-based recipe generation.")
    
    async def generate_personalized_recipe(self, user_profile: Dict, 
                                         ingredients: List[str],
                                         preferences: Dict) -> Dict:
        """Generate a personalized recipe based on user profile and preferences"""
        
        if self.use_llm:
            return await self.generate_llm_recipe(user_profile, ingredients, preferences)
        else:
            return self.generate_template_recipe(ingredients, preferences)
    
    async def generate_llm_recipe(self, user_profile: Dict, ingredients: List[str],
                                preferences: Dict) -> Dict:
        """Generate recipe using LLM (OpenAI GPT)"""
        
        # Construct the prompt based on user profile
        prompt = self.build_recipe_prompt(user_profile, ingredients, preferences)
        
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional nutritionist and chef specializing in healthy, personalized recipes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            recipe_text = response.choices[0].message.content
            return self.parse_llm_recipe_response(recipe_text)
            
        except Exception as e:
            print(f"LLM recipe generation failed: {e}")
            return self.generate_template_recipe(ingredients, preferences)
    
    def build_recipe_prompt(self, user_profile: Dict, ingredients: List[str],
                           preferences: Dict) -> str:
        """Build a detailed prompt for recipe generation"""
        
        health_conditions = user_profile.get('health_conditions', {})
        cuisine_pref = user_profile.get('cuisine_pref', 'mixed')
        activity_level = user_profile.get('activity_level', 'moderate')
        
        prompt = f"""
Create a healthy recipe using these ingredients: {', '.join(ingredients)}

User Profile:
- Cuisine preference: {cuisine_pref}
- Activity level: {activity_level}
- Health considerations: {', '.join([k for k, v in health_conditions.items() if v])}

Recipe Requirements:
- Target calories: {preferences.get('target_calories', 'moderate portion')}
- Prep time: {preferences.get('prep_time', 30)} minutes maximum
- Difficulty: {preferences.get('difficulty', 'medium')}
- Cuisine style: {preferences.get('cuisine_type', cuisine_pref)}

Special Instructions:
{"- Low sodium (for hypertension)" if health_conditions.get('hypertension') else ""}
{"- Low glycemic index (for diabetes)" if health_conditions.get('diabetes') else ""}
{"- High protein (for active lifestyle)" if activity_level in ['active', 'very_active'] else ""}

Please provide:
1. Recipe title
2. Ingredients list with quantities
3. Step-by-step instructions
4. Estimated nutrition per serving (calories, protein, carbs, fat)
5. Prep and cook time
6. Health benefits

Format as JSON with these keys: title, ingredients, instructions, nutrition, prep_time, cook_time, health_benefits
"""
        return prompt
    
    def generate_template_recipe(self, ingredients: List[str], preferences: Dict) -> Dict:
        """Generate recipe using templates (fallback method)"""
        
        primary_ingredient = ingredients[0] if ingredients else "mixed vegetables"
        cuisine = preferences.get('cuisine_type', 'mixed')
        
        # Template-based recipe generation
        recipes = {
            'indian': {
                'title': f'{primary_ingredient.title()} Curry',
                'instructions': [
                    f'Heat oil in a pan and add cumin seeds',
                    f'Add chopped onions and sauté until golden',
                    f'Add {primary_ingredient} and spices (turmeric, coriander, garam masala)',
                    f'Cook covered for 15-20 minutes until tender',
                    f'Garnish with fresh cilantro and serve hot'
                ],
                'spices': ['turmeric', 'coriander powder', 'garam masala', 'cumin seeds']
            },
            'chinese': {
                'title': f'{primary_ingredient.title()} Stir Fry',
                'instructions': [
                    f'Heat oil in a wok over high heat',
                    f'Add garlic and ginger, stir for 30 seconds',
                    f'Add {primary_ingredient} and stir-fry for 3-4 minutes',
                    f'Add soy sauce and vegetables',
                    f'Stir-fry until everything is cooked through'
                ],
                'spices': ['garlic', 'ginger', 'soy sauce', 'sesame oil']
            },
            'mediterranean': {
                'title': f'Mediterranean {primary_ingredient.title()} Bowl',
                'instructions': [
                    f'Drizzle {primary_ingredient} with olive oil and herbs',
                    f'Roast in oven at 400°F for 20 minutes',
                    f'Serve with quinoa or brown rice',
                    f'Top with feta cheese and olives',
                    f'Squeeze fresh lemon before serving'
                ],
                'spices': ['oregano', 'basil', 'olive oil', 'lemon juice']
            }
        }
        
        template = recipes.get(cuisine, recipes['mediterranean'])
        
        return {
            'title': template['title'],
            'ingredients': ingredients + template['spices'],
            'instructions': template['instructions'],
            'estimated_calories': preferences.get('target_calories', 400),
            'prep_time': preferences.get('prep_time', 30),
            'difficulty': preferences.get('difficulty', 'medium'),
            'cuisine_type': cuisine,
            'health_benefits': self.generate_health_benefits(ingredients)
        }
    
    def parse_llm_recipe_response(self, response_text: str) -> Dict:
        """Parse LLM response into structured recipe data"""
        try:
            # Try to extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_text = response_text[json_start:json_end]
                return json.loads(json_text)
            else:
                # If no JSON, parse manually
                return self.manual_parse_recipe(response_text)
        except:
            return self.manual_parse_recipe(response_text)
    
    def manual_parse_recipe(self, text: str) -> Dict:
        """Manually parse recipe text when JSON parsing fails"""
        lines = text.split('\n')
        
        recipe = {
            'title': 'Generated Recipe',
            'ingredients': [],
            'instructions': [],
            'prep_time': 30,
            'difficulty': 'medium'
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if 'title' in line.lower() or line.endswith(':'):
                if 'title' in line.lower():
                    recipe['title'] = line.split(':')[-1].strip()
                current_section = line.lower()
            elif 'ingredient' in current_section:
                if line.startswith('-') or line.startswith('•'):
                    recipe['ingredients'].append(line[1:].strip())
            elif 'instruction' in current_section or 'step' in current_section:
                if line.startswith('-') or line.startswith('•') or line[0].isdigit():
                    recipe['instructions'].append(line.lstrip('-•0123456789. '))
        
        return recipe
    
    def generate_health_benefits(self, ingredients: List[str]) -> List[str]:
        """Generate health benefits based on ingredients"""
        benefits = []
        
        health_map = {
            'spinach': 'Rich in iron and folate',
            'salmon': 'High in omega-3 fatty acids',
            'quinoa': 'Complete protein source',
            'sweet potato': 'High in beta-carotene',
            'broccoli': 'High in vitamin C and fiber',
            'avocado': 'Healthy monounsaturated fats',
            'blueberries': 'Antioxidant powerhouse',
            'greek yogurt': 'Probiotic and high protein'
        }
        
        for ingredient in ingredients:
            ingredient_lower = ingredient.lower()
            for food, benefit in health_map.items():
                if food in ingredient_lower:
                    benefits.append(benefit)
        
        return benefits or ['Balanced nutrition', 'Fresh ingredients']