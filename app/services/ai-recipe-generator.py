import random
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import math
from collections import defaultdict

class RecipeDifficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class RecipeCategory(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DESSERT = "dessert"

class RecipeCuisine(Enum):
    INDIAN = "indian"
    MEDITERRANEAN = "mediterranean"
    ASIAN = "asian"
    ITALIAN = "italian"
    MEXICAN = "mexican"
    FUSION = "fusion"

@dataclass
class Ingredient:
    name: str
    quantity: float
    unit: str
    category: str
    cost_per_unit: float
    calories_per_unit: float
    protein_per_unit: float
    carbs_per_unit: float
    fats_per_unit: float
    fiber_per_unit: float = 0.0
    sugar_per_unit: float = 0.0
    sodium_per_unit: float = 0.0

@dataclass
class Recipe:
    id: str
    name: str
    description: str
    cuisine: RecipeCuisine
    category: RecipeCategory
    difficulty: RecipeDifficulty
    preparation_time: int
    cooking_time: int
    servings: int
    ingredients: List[Ingredient]
    instructions: List[str]
    nutrition_per_serving: Dict[str, float]
    cost_per_serving: float
    tags: List[str]
    seasonal_tags: List[str]
    health_benefits: List[str]
    created_at: datetime
    rating: float = 0.0
    review_count: int = 0

@dataclass
class RecipeRequest:
    cuisine_preference: List[str]
    dietary_restrictions: List[str]
    available_ingredients: List[str]
    target_calories: int
    budget_limit: float
    meal_type: RecipeCategory
    difficulty_level: RecipeDifficulty
    time_constraint: int
    health_conditions: List[str]
    serving_size: int = 2

class AIRecipeGenerator:
    def __init__(self):
        self.recipe_templates = self._initialize_recipe_templates()
        self.ingredient_database = self._initialize_ingredient_database()
        self.cooking_techniques = self._initialize_cooking_techniques()
        self.flavor_profiles = self._initialize_flavor_profiles()
        self.recipe_patterns = self._initialize_recipe_patterns()
        
    def _initialize_recipe_templates(self) -> Dict:
        return {
            "indian_breakfast": {
                "structure": ["base_grain", "protein", "vegetable", "spice", "oil"],
                "cooking_methods": ["steam", "sauté", "boil", "temper"],
                "flavor_profile": ["aromatic", "spicy", "savory"],
                "typical_ingredients": ["rice", "lentils", "vegetables", "spices", "herbs"]
            },
            "indian_lunch": {
                "structure": ["main_dish", "vegetable", "grain", "spice", "oil"],
                "cooking_methods": ["curry", "sauté", "steam"],
                "flavor_profile": ["rich", "aromatic", "balanced"],
                "typical_ingredients": ["pulses", "vegetables", "grains", "spices", "oil"]
            },
            "indian_dinner": {
                "structure": ["protein", "vegetable", "grain", "spice", "oil"],
                "cooking_methods": ["slow_cook", "pressure_cook", "curry"],
                "flavor_profile": ["warm", "comforting", "nutritious"],
                "typical_ingredients": ["legumes", "vegetables", "grains", "spices"]
            }
        }
    
    def _initialize_ingredient_database(self) -> Dict[str, Ingredient]:
        ingredients = {
            # Grains (per 100g cooked)
            "basmati_rice": Ingredient("basmati rice", 100, "g", "grain", 0.15, 130, 2.7, 28, 0.3, 0.4, 0.1, 1),
            "rice": Ingredient("rice", 100, "g", "grain", 0.15, 130, 2.7, 28, 0.3, 0.4, 0.1, 1),
            "quinoa": Ingredient("quinoa", 100, "g", "grain", 0.25, 120, 4.4, 22, 1.9, 2.8, 0.9, 5),
            "oats": Ingredient("oats", 100, "g", "grain", 0.10, 68, 2.4, 12, 1.4, 2.8, 0.1, 3),
            
            # Proteins (per 100g)
            "chicken": Ingredient("chicken", 100, "g", "protein", 0.80, 165, 31, 0, 3.6, 0, 0, 74),
            "tofu": Ingredient("tofu", 100, "g", "protein", 0.30, 76, 8, 1.9, 4.8, 0.4, 0.6, 7),
            "lentils": Ingredient("red lentils", 100, "g", "protein", 0.20, 116, 9, 20, 0.4, 7.9, 0.2, 2),
            "chickpeas": Ingredient("chickpeas", 100, "g", "protein", 0.25, 164, 8.9, 27, 2.6, 8, 2.4, 7),
            "paneer": Ingredient("paneer", 100, "g", "protein", 0.60, 265, 18, 2.2, 20, 0, 2.2, 18),
            
            # Vegetables (per 100g)
            "spinach": Ingredient("spinach", 100, "g", "vegetable", 0.15, 23, 2.9, 3.6, 0.4, 2.2, 0.4, 79),
            "tomatoes": Ingredient("tomatoes", 100, "g", "vegetable", 0.20, 18, 0.9, 3.9, 0.2, 1.2, 2.6, 5),
            "onions": Ingredient("onions", 100, "g", "vegetable", 0.10, 40, 1.1, 9.3, 0.1, 1.7, 4.2, 4),
            "bell_peppers": Ingredient("bell peppers", 100, "g", "vegetable", 0.30, 31, 1, 7, 0.3, 2.5, 4.2, 4),
            "cauliflower": Ingredient("cauliflower", 100, "g", "vegetable", 0.25, 25, 1.9, 5, 0.3, 2, 1.9, 15),
            
            # Spices (per 1 tsp = 2g)
            "turmeric": Ingredient("turmeric", 1, "tsp", "spice", 0.05, 8, 0.3, 1.4, 0.2, 0.5, 0.1, 1),
            "cumin": Ingredient("cumin seeds", 1, "tsp", "spice", 0.03, 8, 0.4, 0.9, 0.5, 0.2, 0.1, 10),
            "coriander": Ingredient("coriander powder", 1, "tsp", "spice", 0.02, 5, 0.2, 0.9, 0.3, 0.8, 0.1, 35),
            "ginger": Ingredient("ginger", 1, "tsp", "spice", 0.05, 2, 0.04, 0.4, 0.02, 0.05, 0.03, 0.3),
            "garam_masala": Ingredient("garam masala", 1, "tsp", "spice", 0.08, 6, 0.3, 1.2, 0.3, 0.4, 0.1, 8),
            
            # Oils and fats (per 1 tbsp = 15ml)
            "olive_oil": Ingredient("olive oil", 1, "tbsp", "oil", 0.15, 119, 0, 0, 13.5, 0, 0, 0),
            "ghee": Ingredient("ghee", 1, "tbsp", "oil", 0.20, 112, 0, 0, 12.7, 0, 0, 0),
            "coconut_oil": Ingredient("coconut oil", 1, "tbsp", "oil", 0.18, 117, 0, 0, 13.6, 0, 0, 0),
            
            # Dairy alternatives (per 100ml)
            "almond_milk": Ingredient("almond milk", 100, "ml", "liquid", 0.35, 17, 0.6, 0.3, 1.1, 0.1, 0.3, 63)
        }
        return ingredients
    
    def _initialize_cooking_techniques(self) -> Dict[str, Dict]:
        return {
            "steam": {"time": 15, "skill": "easy", "equipment": "steamer"},
            "sauté": {"time": 10, "skill": "easy", "equipment": "pan"},
            "boil": {"time": 20, "skill": "easy", "equipment": "pot"},
            "temper": {"time": 5, "skill": "medium", "equipment": "pan"},
            "curry": {"time": 30, "skill": "medium", "equipment": "pot"},
            "fry": {"time": 15, "skill": "medium", "equipment": "pan"},
            "slow_cook": {"time": 240, "skill": "easy", "equipment": "slow_cooker"},
            "pressure_cook": {"time": 30, "skill": "medium", "equipment": "pressure_cooker"},
            "roast": {"time": 60, "skill": "medium", "equipment": "oven"}
        }
    
    def _initialize_flavor_profiles(self) -> Dict[str, List[str]]:
        return {
            "indian": ["aromatic", "spicy", "savory", "tangy", "sweet"],
            "mediterranean": ["fresh", "herbaceous", "olive", "citrus", "garlic"],
            "asian": ["umami", "sweet", "sour", "spicy", "aromatic"],
            "italian": ["herbaceous", "tomato", "garlic", "olive", "cheese"],
            "mexican": ["spicy", "citrus", "corn", "bean", "herb"]
        }
    
    def _initialize_recipe_patterns(self) -> Dict[str, List[str]]:
        return {
            "curry_pattern": ["oil", "aromatics", "protein", "vegetables", "spices", "liquid"],
            "salad_pattern": ["base", "protein", "vegetables", "dressing", "herbs"],
            "soup_pattern": ["oil", "aromatics", "liquid", "protein", "vegetables", "spices"],
            "stir_fry_pattern": ["oil", "protein", "vegetables", "spices"],
            "dal_pattern": ["oil", "spices", "protein", "liquid", "vegetables"]
        }

    def _round_quantity(self, quantity: float, unit: str) -> float:
        """Round quantities to practical cooking amounts"""
        if unit in ["g", "ml"]:
            if quantity < 10:
                return round(quantity, 1)
            elif quantity < 50:
                return round(quantity / 5) * 5  # Round to nearest 5g
            else:
                return round(quantity / 10) * 10  # Round to nearest 10g
        elif unit in ["cup", "tbsp", "tsp"]:
            if quantity < 0.25:
                return 0.25  # Minimum practical amount
            elif quantity < 1:
                return round(quantity * 4) / 4  # Round to nearest 1/4
            else:
                return round(quantity * 2) / 2  # Round to nearest 1/2
        else:
            return round(quantity, 1)

    def _merge_ingredients(self, ingredients: List[Ingredient]) -> List[Ingredient]:
        """Merge duplicate ingredients and round quantities"""
        ingredient_map = defaultdict(lambda: {"quantity": 0, "ingredient": None})
        
        for ingredient in ingredients:
            key = ingredient.name
            if ingredient_map[key]["ingredient"] is None:
                ingredient_map[key]["ingredient"] = ingredient
            ingredient_map[key]["quantity"] += ingredient.quantity
        
        merged_ingredients = []
        for key, data in ingredient_map.items():
            ingredient = data["ingredient"]
            rounded_quantity = self._round_quantity(data["quantity"], ingredient.unit)
            
            merged_ingredient = Ingredient(
                name=ingredient.name,
                quantity=rounded_quantity,
                unit=ingredient.unit,
                category=ingredient.category,
                cost_per_unit=ingredient.cost_per_unit,
                calories_per_unit=ingredient.calories_per_unit,
                protein_per_unit=ingredient.protein_per_unit,
                carbs_per_unit=ingredient.carbs_per_unit,
                fats_per_unit=ingredient.fats_per_unit,
                fiber_per_unit=ingredient.fiber_per_unit,
                sugar_per_unit=ingredient.sugar_per_unit,
                sodium_per_unit=ingredient.sodium_per_unit
            )
            merged_ingredients.append(merged_ingredient)
        
        return merged_ingredients

    def generate_recipe(self, request: RecipeRequest) -> Recipe:
        # Select appropriate recipe template
        template_key = f"{request.cuisine_preference[0]}_{request.meal_type.value}"
        template = self.recipe_templates.get(template_key, self.recipe_templates["indian_lunch"])
        
        # Generate recipe name
        recipe_name = self._generate_recipe_name(request, template)
        
        # Select ingredients based on constraints
        selected_ingredients = self._select_ingredients(request, template)
        
        # Merge duplicate ingredients and round quantities
        merged_ingredients = self._merge_ingredients(selected_ingredients)
        
        # Generate cooking instructions based on actual ingredients
        instructions = self._generate_context_aware_instructions(merged_ingredients, template, request)
        
        # Calculate nutrition and cost
        nutrition = self._calculate_nutrition(merged_ingredients, request.serving_size)
        total_cost = sum(ing.cost_per_unit * (ing.quantity if ing.unit in ['g', 'ml'] else ing.quantity * 100) for ing in merged_ingredients)
        cost_per_serving = total_cost / request.serving_size
        
        # Create recipe object
        recipe = Recipe(
            id=f"recipe_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=recipe_name,
            description=self._generate_description(recipe_name, merged_ingredients, request),
            cuisine=RecipeCuisine(request.cuisine_preference[0]),
            category=request.meal_type,
            difficulty=request.difficulty_level,
            preparation_time=self._calculate_prep_time(merged_ingredients, request.difficulty_level),
            cooking_time=self._calculate_cooking_time(template, request.difficulty_level),
            servings=request.serving_size,
            ingredients=merged_ingredients,
            instructions=instructions,
            nutrition_per_serving=nutrition,
            cost_per_serving=cost_per_serving,
            tags=self._generate_tags(merged_ingredients, request),
            seasonal_tags=self._get_seasonal_tags(),
            health_benefits=self._get_health_benefits(merged_ingredients, request.health_conditions),
            created_at=datetime.now()
        )
        
        return recipe
    
    def _generate_recipe_name(self, request: RecipeRequest, template: Dict) -> str:
        cuisine = request.cuisine_preference[0].title()
        meal_type = request.meal_type.value.title()
        
        # Get main ingredients
        main_ingredients = []
        if request.available_ingredients:
            main_ingredients = [ing.replace("_", " ").title() for ing in request.available_ingredients[:2]]
        
        if main_ingredients:
            return f"{cuisine} {main_ingredients[0]} {meal_type}"
        else:
            return f"{cuisine} {meal_type} Bowl"
    
    def _select_ingredients(self, request: RecipeRequest, template: Dict) -> List[Ingredient]:
        selected = []
        available_ingredients = set(request.available_ingredients) if request.available_ingredients else set()
        budget_per_category = request.budget_limit / len(template["structure"])
        
        # Select ingredients for each category in template
        for category in template["structure"]:
            suitable_ingredients = self._get_ingredients_by_category(category)
            
            # Filter by constraints
            filtered_ingredients = [
                ing for ing in suitable_ingredients
                if self._meets_constraints(ing, request, budget_per_category)
            ]
            
            if filtered_ingredients:
                # Prefer available ingredients - check both with and without underscores
                preferred = []
                for ing in filtered_ingredients:
                    ing_name_lower = ing.name.lower()
                    for avail_ing in available_ingredients:
                        avail_ing_lower = avail_ing.lower().strip()
                        if (ing_name_lower == avail_ing_lower or 
                            ing_name_lower.replace(" ", "_") == avail_ing_lower or
                            avail_ing_lower in ing_name_lower or
                            ing_name_lower in avail_ing_lower):
                            preferred.append(ing)
                            break
                
                chosen_ingredient = preferred[0] if preferred else random.choice(filtered_ingredients)
                adjusted_ingredient = self._adjust_quantity(chosen_ingredient, request.target_calories, request.serving_size, category)
                selected.append(adjusted_ingredient)
        
        return selected
    
    def _get_ingredients_by_category(self, category: str) -> List[Ingredient]:
        category_mapping = {
            "base_grain": ["rice", "basmati_rice", "quinoa", "oats"],
            "grain": ["rice", "basmati_rice", "quinoa", "oats"],
            "protein": ["chicken", "tofu", "lentils", "chickpeas", "paneer"],
            "main_dish": ["chicken", "tofu", "lentils", "chickpeas", "paneer"],
            "vegetable": ["spinach", "tomatoes", "onions", "bell_peppers", "cauliflower"],
            "spice": ["turmeric", "cumin", "coriander", "ginger", "garam_masala"],
            "oil": ["olive_oil", "ghee", "coconut_oil"],
            "liquid": ["almond_milk"]
        }
        
        ingredient_names = category_mapping.get(category, [])
        return [self.ingredient_database[name] for name in ingredient_names if name in self.ingredient_database]
    
    def _meets_constraints(self, ingredient: Ingredient, request: RecipeRequest, budget_limit: float) -> bool:
        # Budget constraint - adjust for unit differences
        cost_factor = 100 if ingredient.unit in ['g', 'ml'] else 1
        adjusted_cost = ingredient.cost_per_unit * cost_factor
        
        if adjusted_cost > budget_limit:
            return False
        
        # Dietary restrictions
        if "vegan" in request.dietary_restrictions:
            if ingredient.name in ["paneer"]:
                return False
        
        return True
    
    def _adjust_quantity(self, ingredient: Ingredient, target_calories: int, servings: int, category: str) -> Ingredient:
        # Set realistic base quantities by category
        base_quantities = {
            "protein": 150,  # 150g protein source
            "main_dish": 150,  # Same as protein
            "grain": 100,    # 100g grain
            "base_grain": 100,  # Same as grain
            "vegetable": 200, # 200g vegetables
            "spice": 1,      # 1 tsp spices
            "oil": 2,        # 2 tbsp oil
            "liquid": 200    # 200ml liquid
        }
        
        base_qty = base_quantities.get(category, 100)
        
        # Scale by servings
        adjusted_quantity = base_qty * servings / 2  # Base is for 2 servings
        
        return Ingredient(
            name=ingredient.name,
            quantity=adjusted_quantity,
            unit=ingredient.unit,
            category=ingredient.category,
            cost_per_unit=ingredient.cost_per_unit,
            calories_per_unit=ingredient.calories_per_unit,
            protein_per_unit=ingredient.protein_per_unit,
            carbs_per_unit=ingredient.carbs_per_unit,
            fats_per_unit=ingredient.fats_per_unit,
            fiber_per_unit=ingredient.fiber_per_unit,
            sugar_per_unit=ingredient.sugar_per_unit,
            sodium_per_unit=ingredient.sodium_per_unit
        )

    def _generate_context_aware_instructions(self, ingredients: List[Ingredient], template: Dict, request: RecipeRequest) -> List[str]:
        """Generate instructions based on actual ingredients present"""
        instructions = []
        step_num = 1
        
        # Get ingredient categories present
        ingredient_categories = {ing.category for ing in ingredients}
        ingredient_names = {ing.name for ing in ingredients}
        
        # Preparation phase
        instructions.append(f"{step_num}. Gather all ingredients and wash vegetables thoroughly.")
        step_num += 1
        
        # Ingredient-specific prep
        for ingredient in ingredients:
            if ingredient.category == "vegetable" and ingredient.quantity >= 50:
                instructions.append(f"{step_num}. Chop {ingredient.name} into medium pieces.")
                step_num += 1
            elif ingredient.category == "protein" and "lentils" in ingredient.name:
                instructions.append(f"{step_num}. Rinse {ingredient.name} until water runs clear.")
                step_num += 1
            elif ingredient.category == "grain":
                instructions.append(f"{step_num}. Rinse {ingredient.name} and drain well.")
                step_num += 1
        
        # Cooking phase based on available ingredients
        cooking_method = random.choice(template["cooking_methods"])
        
        if "oil" in ingredient_categories:
            oil_ingredient = next((ing for ing in ingredients if ing.category == "oil"), None)
            if oil_ingredient:
                instructions.append(f"{step_num}. Heat {oil_ingredient.name} in a large pan over medium heat.")
                step_num += 1
        
        if "spice" in ingredient_categories:
            spice_ingredients = [ing.name for ing in ingredients if ing.category == "spice"]
            if spice_ingredients:
                spice_list = ", ".join(spice_ingredients)
                instructions.append(f"{step_num}. Add {spice_list} and sauté for 30 seconds until fragrant.")
                step_num += 1
        
        if "protein" in ingredient_categories:
            protein_ingredient = next((ing for ing in ingredients if ing.category == "protein"), None)
            if protein_ingredient and "lentils" in protein_ingredient.name:
                instructions.append(f"{step_num}. Add {protein_ingredient.name} with 2 cups water and bring to boil.")
                step_num += 1
            elif protein_ingredient:
                instructions.append(f"{step_num}. Add {protein_ingredient.name} and cook for 3-4 minutes.")
                step_num += 1
        
        if "vegetable" in ingredient_categories:
            vegetable_ingredients = [ing.name for ing in ingredients if ing.category == "vegetable"]
            if vegetable_ingredients:
                veg_list = ", ".join(vegetable_ingredients)
                instructions.append(f"{step_num}. Add {veg_list} and cook until tender, about 8-10 minutes.")
                step_num += 1
        
        if "grain" in ingredient_categories:
            grain_ingredient = next((ing for ing in ingredients if ing.category == "grain"), None)
            if grain_ingredient:
                instructions.append(f"{step_num}. In a separate pot, cook {grain_ingredient.name} according to package instructions.")
                step_num += 1
        
        # Final steps
        instructions.append(f"{step_num}. Taste and adjust salt and spices as needed.")
        step_num += 1
        instructions.append(f"{step_num}. Serve hot with the cooked grain. Enjoy!")
        
        return instructions
    
    def _calculate_nutrition(self, ingredients: List[Ingredient], servings: int) -> Dict[str, float]:
        total_nutrition = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fats": 0,
            "fiber": 0,
            "sugar": 0,
            "sodium": 0
        }
        
        for ingredient in ingredients:
            # Calculate nutrition based on quantity and unit
            if ingredient.unit in ["tsp", "tbsp"]:
                # For spices and oils, multiply by quantity directly
                quantity_factor = ingredient.quantity
            elif ingredient.unit in ["g", "ml"]:
                # For per-100g values, scale appropriately
                quantity_factor = ingredient.quantity / 100
            else:
                # Default case
                quantity_factor = ingredient.quantity / 100
            
            total_nutrition["calories"] += ingredient.calories_per_unit * quantity_factor
            total_nutrition["protein"] += ingredient.protein_per_unit * quantity_factor
            total_nutrition["carbs"] += ingredient.carbs_per_unit * quantity_factor
            total_nutrition["fats"] += ingredient.fats_per_unit * quantity_factor
            total_nutrition["fiber"] += ingredient.fiber_per_unit * quantity_factor
            total_nutrition["sugar"] += ingredient.sugar_per_unit * quantity_factor
            total_nutrition["sodium"] += ingredient.sodium_per_unit * quantity_factor
        
        # Convert to per-serving values
        for key in total_nutrition:
            total_nutrition[key] = round(total_nutrition[key] / servings, 1)
        
        return total_nutrition
    
    def _calculate_prep_time(self, ingredients: List[Ingredient], difficulty: RecipeDifficulty) -> int:
        base_time = len(ingredients) * 3  # 3 minutes per ingredient
        
        difficulty_multiplier = {
            RecipeDifficulty.EASY: 1.0,
            RecipeDifficulty.MEDIUM: 1.3,
            RecipeDifficulty.HARD: 1.6
        }
        
        return int(base_time * difficulty_multiplier[difficulty])
    
    def _calculate_cooking_time(self, template: Dict, difficulty: RecipeDifficulty) -> int:
        cooking_method = random.choice(template["cooking_methods"])
        base_time = self.cooking_techniques[cooking_method]["time"]
        
        difficulty_multiplier = {
            RecipeDifficulty.EASY: 0.8,
            RecipeDifficulty.MEDIUM: 1.0,
            RecipeDifficulty.HARD: 1.2
        }
        
        return int(base_time * difficulty_multiplier[difficulty])
    
    def _generate_description(self, name: str, ingredients: List[Ingredient], request: RecipeRequest) -> str:
        cuisine = request.cuisine_preference[0].title()
        meal_type = request.meal_type.value.title()
        
        main_ingredients = [ing.name.title() for ing in ingredients[:3] if ing.category in ["protein", "vegetable", "grain"]]
        ingredient_list = ", ".join(main_ingredients)
        
        return f"A delicious {cuisine} {meal_type.lower()} featuring {ingredient_list}. This nutritious recipe serves {request.serving_size} people and can be prepared in under {request.time_constraint} minutes. Perfect for meeting your dietary needs while staying within budget."
    
    def _generate_tags(self, ingredients: List[Ingredient], request: RecipeRequest) -> List[str]:
        tags = []
        
        # Dietary tags
        if "vegetarian" in request.dietary_restrictions:
            tags.append("vegetarian")
        if "vegan" in request.dietary_restrictions:
            tags.append("vegan")
        if "low_sugar" in request.dietary_restrictions:
            tags.append("low-sugar")
        
        # Ingredient-based tags
        for ingredient in ingredients:
            if "lentils" in ingredient.name:
                tags.append("high-protein")
            if ingredient.name in ["spinach", "bell_peppers"]:
                tags.append("vitamin-rich")
        
        # Cuisine and meal type
        tags.extend(request.cuisine_preference)
        tags.append(request.meal_type.value)
        tags.append(request.difficulty_level.value)
        
        return list(set(tags))  # Remove duplicates
    
    def _get_seasonal_tags(self) -> List[str]:
        current_month = datetime.now().month
        
        if current_month in [12, 1, 2]:
            return ["winter", "comfort"]
        elif current_month in [3, 4, 5]:
            return ["spring", "fresh"]
        elif current_month in [6, 7, 8]:
            return ["summer", "light"]
        else:
            return ["autumn", "warm"]
    
    def _get_health_benefits(self, ingredients: List[Ingredient], health_conditions: List[str]) -> List[str]:
        benefits = []
        
        for ingredient in ingredients:
            if "turmeric" in ingredient.name:
                benefits.append("anti-inflammatory")
            if "ginger" in ingredient.name:
                benefits.append("digestive health")
            if "spinach" in ingredient.name:
                benefits.append("iron rich")
            if "lentils" in ingredient.name:
                benefits.append("high fiber")
            if "quinoa" in ingredient.name:
                benefits.append("complete protein")
        
        # Condition-specific benefits
        if "diabetes" in health_conditions:
            benefits.append("diabetes-friendly")
        if "hypertension" in health_conditions:
            benefits.append("heart-healthy")
        
        return list(set(benefits))
    
    def scale_recipe(self, recipe: Recipe, new_servings: int) -> Recipe:
        """Properly scale recipe for different serving sizes"""
        scaling_factor = new_servings / recipe.servings
        
        # Scale ingredients with proper rounding
        scaled_ingredients = []
        for ingredient in recipe.ingredients:
            scaled_quantity = self._round_quantity(ingredient.quantity * scaling_factor, ingredient.unit)
            
            scaled_ingredient = Ingredient(
                name=ingredient.name,
                quantity=scaled_quantity,
                unit=ingredient.unit,
                category=ingredient.category,
                cost_per_unit=ingredient.cost_per_unit,
                calories_per_unit=ingredient.calories_per_unit,
                protein_per_unit=ingredient.protein_per_unit,
                carbs_per_unit=ingredient.carbs_per_unit,
                fats_per_unit=ingredient.fats_per_unit,
                fiber_per_unit=ingredient.fiber_per_unit,
                sugar_per_unit=ingredient.sugar_per_unit,
                sodium_per_unit=ingredient.sodium_per_unit
            )
            scaled_ingredients.append(scaled_ingredient)
        
        # Merge any duplicate ingredients that might result from scaling
        merged_ingredients = self._merge_ingredients(scaled_ingredients)
        
        # Recalculate nutrition and cost for the new serving size
        nutrition = self._calculate_nutrition(merged_ingredients, new_servings)
        
        # Calculate total cost and cost per serving
        total_cost = sum(
            ing.cost_per_unit * (ing.quantity if ing.unit in ['g', 'ml'] else ing.quantity * 100) 
            for ing in merged_ingredients
        )
        cost_per_serving = total_cost / new_servings
        
        # Update cooking times if necessary (larger batches may need slightly longer)
        time_multiplier = 1.0
        if new_servings > recipe.servings * 2:
            time_multiplier = 1.1  # 10% longer for large batches
        elif new_servings < recipe.servings / 2:
            time_multiplier = 0.9  # Slightly shorter for smaller batches
        
        # Generate updated instructions with scaled quantities mentioned
        scaled_instructions = self._update_instructions_for_scaling(
            recipe.instructions, scaling_factor, merged_ingredients
        )
        
        # Create scaled recipe
        scaled_recipe = Recipe(
            id=f"{recipe.id}_scaled_{new_servings}",
            name=f"{recipe.name} ({new_servings} servings)",
            description=recipe.description.replace(
                f"serves {recipe.servings}", f"serves {new_servings}"
            ).replace(
                f"{recipe.servings} people", f"{new_servings} people"
            ),
            cuisine=recipe.cuisine,
            category=recipe.category,
            difficulty=recipe.difficulty,
            preparation_time=int(recipe.preparation_time * time_multiplier),
            cooking_time=int(recipe.cooking_time * time_multiplier),
            servings=new_servings,
            ingredients=merged_ingredients,
            instructions=scaled_instructions,
            nutrition_per_serving=nutrition,  # This stays per serving, not total
            cost_per_serving=cost_per_serving,
            tags=recipe.tags,
            seasonal_tags=recipe.seasonal_tags,
            health_benefits=recipe.health_benefits,
            created_at=datetime.now(),
            rating=recipe.rating,
            review_count=recipe.review_count
        )
        
        return scaled_recipe

    def _update_instructions_for_scaling(self, original_instructions: List[str], scaling_factor: float, ingredients: List[Ingredient]) -> List[str]:
        """Update instructions to reflect scaled quantities where relevant"""
        scaled_instructions = []
        
        for instruction in original_instructions:
            # Replace any specific quantity mentions in instructions
            updated_instruction = instruction
            
            # Pattern for "X cups of Y" or "X tbsp of Y"
            quantity_patterns = [
                r'(\d+(?:\.\d+)?)\s+(cups?|tbsp|tsp|g|ml)\s+',
                r'(\d+(?:\.\d+)?)\s+(cups?|tbsp|tsp|g|ml)\s+of\s+',
            ]
            
            for pattern in quantity_patterns:
                matches = re.finditer(pattern, updated_instruction, re.IGNORECASE)
                for match in matches:
                    original_qty = float(match.group(1))
                    unit = match.group(2).lower()
                    
                    # Scale the quantity and round appropriately
                    scaled_qty = self._round_quantity(original_qty * scaling_factor, unit)
                    
                    # Replace in the instruction
                    old_text = f"{original_qty} {unit}"
                    new_text = f"{scaled_qty} {unit}"
                    updated_instruction = updated_instruction.replace(old_text, new_text)
            
            scaled_instructions.append(updated_instruction)
        
        return scaled_instructions

    def suggest_ingredient_substitutions(self, original_ingredient: str, dietary_restrictions: List[str], budget_constraint: float) -> List[Dict]:
        """Suggest ingredient substitutions based on constraints"""
        substitutions = []
        
        # Define substitution mappings
        substitution_map = {
            "paneer": ["tofu", "chickpeas", "lentils"],
            "ghee": ["olive_oil", "coconut_oil"],
            "basmati_rice": ["quinoa", "oats"],
            "spinach": ["cauliflower", "bell_peppers"]
        }
        
        # Find suitable substitutions
        for original, alternatives in substitution_map.items():
            if original in original_ingredient:
                for alt in alternatives:
                    if alt in self.ingredient_database:
                        alt_ingredient = self.ingredient_database[alt]
                        original_ing = self.ingredient_database.get(original_ingredient)
                        
                        if alt_ingredient.cost_per_unit <= budget_constraint:
                            cost_diff = alt_ingredient.cost_per_unit - (original_ing.cost_per_unit if original_ing else 0)
                            substitutions.append({
                                "original": original_ingredient,
                                "substitution": alt,
                                "cost_difference": round(cost_diff, 2),
                                "nutrition_impact": "Similar nutritional profile with slight variations"
                            })
        
        return substitutions[:3]  # Return top 3 substitutions

def main():
    """Test the AI Recipe Generator"""
    print("AI RECIPE GENERATOR - TESTING")
    print("=" * 50)
    
    # Initialize generator
    generator = AIRecipeGenerator()
    
    # Test recipe generation
    request = RecipeRequest(
        cuisine_preference=["indian"],
        dietary_restrictions=["vegetarian", "low_sugar"],
        available_ingredients=["lentils", "spinach", "tomatoes"],
        target_calories=400,
        budget_limit=200,
        meal_type=RecipeCategory.LUNCH,
        difficulty_level=RecipeDifficulty.EASY,
        time_constraint=45,
        health_conditions=["diabetes"],
        serving_size=2
    )
    
    print("Generating recipe...")
    recipe = generator.generate_recipe(request)
    
    print(f"\nRECIPE GENERATED:")
    print(f"Name: {recipe.name}")
    print(f"Cuisine: {recipe.cuisine.value}")
    print(f"Difficulty: {recipe.difficulty.value}")
    print(f"Prep Time: {recipe.preparation_time} min")
    print(f"Cooking Time: {recipe.cooking_time} min")
    print(f"Servings: {recipe.servings}")
    print(f"Cost per serving: Rs.{recipe.cost_per_serving:.2f}")
    
    print(f"\nNutrition per serving:")
    for nutrient, value in recipe.nutrition_per_serving.items():
        print(f"   {nutrient.title()}: {value}")
    
    print(f"\nIngredients:")
    for ingredient in recipe.ingredients:
        print(f"   • {ingredient.quantity} {ingredient.unit} {ingredient.name}")
    
    print(f"\nInstructions:")
    for instruction in recipe.instructions:
        print(f"   {instruction}")
    
    print(f"\nTags: {', '.join(recipe.tags)}")
    print(f"Health Benefits: {', '.join(recipe.health_benefits)}")
    
    # Test ingredient substitution
    print(f"\nTesting ingredient substitution...")
    substitutions = generator.suggest_ingredient_substitutions("paneer", ["vegetarian"], 100)
    if substitutions:
        print(f"Substitutions for paneer:")
        for sub in substitutions:
            print(f"   • {sub['substitution']} (cost diff: Rs.{sub['cost_difference']:.2f})")
    
    # Test recipe scaling
    print(f"\nTesting recipe scaling...")
    scaled_recipe = generator.scale_recipe(recipe, 4)
    print(f"Scaled to {scaled_recipe.servings} servings")
    print(f"New cost per serving: Rs.{scaled_recipe.cost_per_serving:.2f}")
    
    print("\n" + "=" * 50)
    print("AI RECIPE GENERATOR TEST COMPLETE!")

if __name__ == "__main__":
    main()