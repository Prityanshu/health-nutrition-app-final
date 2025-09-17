# app/services/recipe_generator.py
"""
Enhanced recipe generation with LLM integration
"""
import json
import os
from typing import List, Dict, Optional, Any
import asyncio
from datetime import datetime

from app.database import FoodItem, User
from app.schemas import RecipeGenerationRequest, RecipeResponse

class EnhancedRecipeGenerator:
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.use_llm = bool(self.openai_api_key)
        
        if not self.use_llm:
            print("OpenAI API key not provided. Using template-based recipe generation.")
    
    async def generate_personalized_recipe(self, user: User, 
                                         request: RecipeGenerationRequest) -> RecipeResponse:
        """Generate a personalized recipe based on user profile and preferences"""
        
        # Build user profile
        user_profile = {
            'health_conditions': user.health_conditions or {},
            'cuisine_pref': getattr(user, 'cuisine_pref', 'mixed'),
            'activity_level': user.activity_level or 'moderately_active',
            'age': user.age,
            'weight': user.weight,
            'height': user.height
        }
        
        if self.use_llm:
            try:
                return await self.generate_llm_recipe(user_profile, request)
            except Exception as e:
                print(f"LLM recipe generation failed: {e}")
                return self.generate_template_recipe(request)
        else:
            return self.generate_template_recipe(request)
    
    async def generate_llm_recipe(self, user_profile: Dict, 
                                request: RecipeGenerationRequest) -> RecipeResponse:
        """Generate recipe using LLM (OpenAI GPT)"""
        
        # Import openai here to avoid import errors if not installed
        try:
            import openai
            openai.api_key = self.openai_api_key
        except ImportError:
            raise Exception("OpenAI library not installed. Install with: pip install openai")
        
        # Construct the prompt based on user profile
        prompt = self.build_recipe_prompt(user_profile, request)
        
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
            return self.parse_llm_recipe_response(recipe_text, request)
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return self.generate_template_recipe(request)
    
    def build_recipe_prompt(self, user_profile: Dict, 
                           request: RecipeGenerationRequest) -> str:
        """Build a detailed prompt for recipe generation"""
        
        health_conditions = user_profile.get('health_conditions', {})
        cuisine_pref = user_profile.get('cuisine_pref', 'mixed')
        activity_level = user_profile.get('activity_level', 'moderate')
        
        prompt = f"""
Create a healthy recipe using these ingredients: {', '.join(request.ingredients)}

User Profile:
- Cuisine preference: {cuisine_pref}
- Activity level: {activity_level}
- Health considerations: {', '.join([k for k, v in health_conditions.items() if v])}

Recipe Requirements:
- Target calories: {request.target_calories or 'moderate portion'}
- Prep time: {request.prep_time} minutes maximum
- Difficulty: {request.difficulty}
- Cuisine style: {request.cuisine_type}
- Dietary restrictions: {', '.join(request.dietary_restrictions) if request.dietary_restrictions else 'None'}

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
    
    def generate_template_recipe(self, request: RecipeGenerationRequest) -> RecipeResponse:
        """Generate recipe using templates (fallback method)"""
        
        primary_ingredient = request.ingredients[0] if request.ingredients else "mixed vegetables"
        cuisine = request.cuisine_type or 'mixed'
        
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
                'spices': ['turmeric', 'coriander powder', 'garam masala', 'cumin seeds'],
                'prep_time': 15,
                'cook_time': 25
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
                'spices': ['garlic', 'ginger', 'soy sauce', 'sesame oil'],
                'prep_time': 10,
                'cook_time': 15
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
                'spices': ['oregano', 'basil', 'olive oil', 'lemon juice'],
                'prep_time': 10,
                'cook_time': 20
            },
            'mexican': {
                'title': f'{primary_ingredient.title()} Tacos',
                'instructions': [
                    f'Season {primary_ingredient} with taco spices',
                    f'Cook in a pan until done',
                    f'Warm tortillas in a dry pan',
                    f'Fill tortillas with {primary_ingredient}',
                    f'Top with lettuce, tomatoes, and cheese'
                ],
                'spices': ['cumin', 'chili powder', 'paprika', 'garlic powder'],
                'prep_time': 15,
                'cook_time': 15
            }
        }
        
        template = recipes.get(cuisine, recipes['mediterranean'])
        
        # Calculate estimated nutrition
        estimated_calories = request.target_calories or 400
        estimated_protein = estimated_calories * 0.25 / 4  # 25% protein
        estimated_carbs = estimated_calories * 0.45 / 4   # 45% carbs
        estimated_fat = estimated_calories * 0.30 / 9     # 30% fat
        
        return RecipeResponse(
            title=template['title'],
            ingredients=request.ingredients + template['spices'],
            instructions=template['instructions'],
            nutrition={
                'calories': estimated_calories,
                'protein': estimated_protein,
                'carbs': estimated_carbs,
                'fat': estimated_fat
            },
            prep_time=template['prep_time'],
            cook_time=template['cook_time'],
            difficulty=request.difficulty,
            cuisine_type=cuisine,
            health_benefits=self.generate_health_benefits(request.ingredients),
            estimated_calories=estimated_calories
        )
    
    def parse_llm_recipe_response(self, response_text: str, 
                                request: RecipeGenerationRequest) -> RecipeResponse:
        """Parse LLM response into structured recipe data"""
        try:
            # Try to extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_text = response_text[json_start:json_end]
                recipe_data = json.loads(json_text)
                
                return RecipeResponse(
                    title=recipe_data.get('title', 'Generated Recipe'),
                    ingredients=recipe_data.get('ingredients', request.ingredients),
                    instructions=recipe_data.get('instructions', []),
                    nutrition=recipe_data.get('nutrition', {
                        'calories': request.target_calories or 400,
                        'protein': 0,
                        'carbs': 0,
                        'fat': 0
                    }),
                    prep_time=recipe_data.get('prep_time', request.prep_time),
                    cook_time=recipe_data.get('cook_time', 20),
                    difficulty=recipe_data.get('difficulty', request.difficulty),
                    cuisine_type=recipe_data.get('cuisine_type', request.cuisine_type),
                    health_benefits=recipe_data.get('health_benefits', []),
                    estimated_calories=recipe_data.get('nutrition', {}).get('calories', request.target_calories)
                )
            else:
                # If no JSON, parse manually
                return self.manual_parse_recipe(response_text, request)
        except Exception as e:
            print(f"JSON parsing failed: {e}")
            return self.manual_parse_recipe(response_text, request)
    
    def manual_parse_recipe(self, text: str, request: RecipeGenerationRequest) -> RecipeResponse:
        """Manually parse recipe text when JSON parsing fails"""
        lines = text.split('\n')
        
        recipe = {
            'title': 'Generated Recipe',
            'ingredients': request.ingredients,
            'instructions': [],
            'prep_time': request.prep_time,
            'difficulty': request.difficulty,
            'cuisine_type': request.cuisine_type
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
        
        # Calculate estimated nutrition
        estimated_calories = request.target_calories or 400
        estimated_protein = estimated_calories * 0.25 / 4
        estimated_carbs = estimated_calories * 0.45 / 4
        estimated_fat = estimated_calories * 0.30 / 9
        
        return RecipeResponse(
            title=recipe['title'],
            ingredients=recipe['ingredients'],
            instructions=recipe['instructions'],
            nutrition={
                'calories': estimated_calories,
                'protein': estimated_protein,
                'carbs': estimated_carbs,
                'fat': estimated_fat
            },
            prep_time=recipe['prep_time'],
            cook_time=20,
            difficulty=recipe['difficulty'],
            cuisine_type=recipe['cuisine_type'],
            health_benefits=self.generate_health_benefits(request.ingredients),
            estimated_calories=estimated_calories
        )
    
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
            'greek yogurt': 'Probiotic and high protein',
            'oats': 'High in soluble fiber',
            'almonds': 'Rich in vitamin E and healthy fats',
            'tomatoes': 'High in lycopene',
            'garlic': 'Natural antimicrobial properties',
            'ginger': 'Anti-inflammatory properties',
            'turmeric': 'Powerful anti-inflammatory',
            'olive oil': 'Heart-healthy monounsaturated fats'
        }
        
        for ingredient in ingredients:
            ingredient_lower = ingredient.lower()
            for food, benefit in health_map.items():
                if food in ingredient_lower:
                    benefits.append(benefit)
        
        return benefits or ['Balanced nutrition', 'Fresh ingredients']

# Utility functions for recipe generation
def calculate_recipe_nutrition(ingredients: List[str], quantities: List[float]) -> Dict[str, float]:
    """Calculate total nutrition for a recipe based on ingredients and quantities"""
    # This would integrate with your food database
    # For now, return placeholder values
    total_calories = sum(quantities) * 100  # Placeholder calculation
    total_protein = sum(quantities) * 10
    total_carbs = sum(quantities) * 15
    total_fat = sum(quantities) * 5
    
    return {
        'calories': total_calories,
        'protein': total_protein,
        'carbs': total_carbs,
        'fat': total_fat
    }

def suggest_recipe_modifications(recipe: RecipeResponse, 
                               dietary_restrictions: List[str]) -> List[str]:
    """Suggest modifications to a recipe based on dietary restrictions"""
    modifications = []
    
    if 'vegetarian' in dietary_restrictions:
        modifications.append("Replace meat with plant-based proteins like tofu or beans")
    
    if 'vegan' in dietary_restrictions:
        modifications.append("Use plant-based alternatives for dairy products")
    
    if 'gluten-free' in dietary_restrictions:
        modifications.append("Use gluten-free flour or grains")
    
    if 'low-sodium' in dietary_restrictions:
        modifications.append("Reduce salt and use herbs and spices for flavor")
    
    if 'low-carb' in dietary_restrictions:
        modifications.append("Replace high-carb ingredients with low-carb alternatives")
    
    return modifications
