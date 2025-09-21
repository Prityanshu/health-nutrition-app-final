from fastapi import HTTPException
from typing import Dict, List, Optional, Union
import json
import logging
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

# Import the core recipe generator classes
import importlib.util
import sys
import os

# Load the ai-recipe-generator module
spec = importlib.util.spec_from_file_location("ai_recipe_generator", os.path.join(os.path.dirname(__file__), "ai-recipe-generator.py"))
ai_recipe_generator = importlib.util.module_from_spec(spec)
sys.modules["ai_recipe_generator"] = ai_recipe_generator
spec.loader.exec_module(ai_recipe_generator)

# Import classes from the loaded module
AIRecipeGenerator = ai_recipe_generator.AIRecipeGenerator
Recipe = ai_recipe_generator.Recipe
RecipeRequest = ai_recipe_generator.RecipeRequest
RecipeCategory = ai_recipe_generator.RecipeCategory
RecipeDifficulty = ai_recipe_generator.RecipeDifficulty
RecipeCuisine = ai_recipe_generator.RecipeCuisine
Ingredient = ai_recipe_generator.Ingredient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecipeGeneratorService:
    """Service layer for AI Recipe Generator with caching and error handling"""
    
    def __init__(self):
        self.generator = AIRecipeGenerator()
        self.recipe_cache = {}  # In-memory cache - could be replaced with Redis
        self.substitution_cache = {}
        
    async def generate_recipe(self, request_data: dict) -> dict:
        """Generate a new recipe based on request parameters"""
        try:
            # Validate and create request object
            recipe_request = self._create_recipe_request(request_data)
            
            # Check cache first
            cache_key = self._generate_cache_key(recipe_request)
            if cache_key in self.recipe_cache:
                logger.info(f"Recipe found in cache: {cache_key}")
                return self.recipe_cache[cache_key]
            
            # Generate new recipe
            logger.info("Generating new recipe...")
            recipe = self.generator.generate_recipe(recipe_request)
            
            # Convert to dictionary for API response
            recipe_dict = self._recipe_to_dict(recipe)
            
            # Cache the result
            self.recipe_cache[cache_key] = recipe_dict
            
            logger.info(f"Recipe generated successfully: {recipe.name}")
            return recipe_dict
            
        except Exception as e:
            logger.error(f"Error generating recipe: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Recipe generation failed: {str(e)}")
    
    async def scale_recipe(self, recipe_id: str, new_servings: int) -> dict:
        """Scale an existing recipe to new serving size"""
        try:
            # Find recipe in cache
            original_recipe_dict = None
            for cached_recipe in self.recipe_cache.values():
                if cached_recipe["id"] == recipe_id:
                    original_recipe_dict = cached_recipe
                    break
            
            if not original_recipe_dict:
                raise HTTPException(status_code=404, detail="Recipe not found")
            
            # Convert back to Recipe object
            original_recipe = self._dict_to_recipe(original_recipe_dict)
            
            # Scale the recipe
            scaled_recipe = self.generator.scale_recipe(original_recipe, new_servings)
            
            # Convert to dictionary
            scaled_dict = self._recipe_to_dict(scaled_recipe)
            
            # Cache the scaled recipe
            self.recipe_cache[scaled_recipe.id] = scaled_dict
            
            logger.info(f"Recipe scaled successfully: {scaled_recipe.name}")
            return scaled_dict
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error scaling recipe: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Recipe scaling failed: {str(e)}")
    
    async def get_ingredient_substitutions(
        self, 
        ingredient: str, 
        dietary_restrictions: List[str], 
        budget_constraint: float
    ) -> List[dict]:
        """Get ingredient substitution suggestions"""
        try:
            cache_key = f"{ingredient}_{','.join(sorted(dietary_restrictions))}_{budget_constraint}"
            
            if cache_key in self.substitution_cache:
                return self.substitution_cache[cache_key]
            
            substitutions = self.generator.suggest_ingredient_substitutions(
                ingredient, dietary_restrictions, budget_constraint
            )
            
            self.substitution_cache[cache_key] = substitutions
            return substitutions
            
        except Exception as e:
            logger.error(f"Error getting substitutions: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Substitution lookup failed: {str(e)}")
    
    async def get_recipe_by_id(self, recipe_id: str) -> dict:
        """Retrieve a recipe by its ID"""
        for cached_recipe in self.recipe_cache.values():
            if cached_recipe["id"] == recipe_id:
                return cached_recipe
        
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    async def get_all_recipes(self, limit: int = 50, offset: int = 0) -> dict:
        """Get all cached recipes with pagination"""
        recipes = list(self.recipe_cache.values())
        total_count = len(recipes)
        
        # Apply pagination
        paginated_recipes = recipes[offset:offset + limit]
        
        return {
            "recipes": paginated_recipes,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
    
    async def search_recipes(
        self, 
        query: str = "", 
        cuisine: Optional[str] = None,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        max_prep_time: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> List[dict]:
        """Search recipes based on various criteria"""
        try:
            results = []
            
            for recipe in self.recipe_cache.values():
                # Text search in name and description
                if query and query.lower() not in recipe["name"].lower() and \
                   query.lower() not in recipe["description"].lower():
                    continue
                
                # Filter by cuisine
                if cuisine and recipe["cuisine"] != cuisine.lower():
                    continue
                
                # Filter by category
                if category and recipe["category"] != category.lower():
                    continue
                
                # Filter by difficulty
                if difficulty and recipe["difficulty"] != difficulty.lower():
                    continue
                
                # Filter by preparation time
                if max_prep_time and recipe["preparation_time"] > max_prep_time:
                    continue
                
                # Filter by tags
                if tags:
                    recipe_tags = [tag.lower() for tag in recipe["tags"]]
                    if not any(tag.lower() in recipe_tags for tag in tags):
                        continue
                
                results.append(recipe)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching recipes: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Recipe search failed: {str(e)}")
    
    async def get_recipe_nutrition_analysis(self, recipe_id: str) -> dict:
        """Get detailed nutrition analysis for a recipe"""
        try:
            recipe = await self.get_recipe_by_id(recipe_id)
            
            nutrition = recipe["nutrition_per_serving"]
            
            # Add nutrition analysis
            analysis = {
                "nutrition_per_serving": nutrition,
                "daily_value_percentage": {
                    "calories": round((nutrition["calories"] / 2000) * 100, 1),  # Based on 2000 cal diet
                    "protein": round((nutrition["protein"] / 50) * 100, 1),     # 50g daily value
                    "carbs": round((nutrition["carbs"] / 300) * 100, 1),        # 300g daily value
                    "fats": round((nutrition["fats"] / 65) * 100, 1),           # 65g daily value
                    "fiber": round((nutrition["fiber"] / 25) * 100, 1),         # 25g daily value
                    "sodium": round((nutrition["sodium"] / 2300) * 100, 1)      # 2300mg daily value
                },
                "health_score": self._calculate_health_score(nutrition),
                "dietary_flags": self._get_dietary_flags(recipe, nutrition)
            }
            
            return analysis
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error analyzing nutrition: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Nutrition analysis failed: {str(e)}")
    
    def _create_recipe_request(self, request_data: dict) -> RecipeRequest:
        """Create RecipeRequest object from dictionary"""
        return RecipeRequest(
            cuisine_preference=request_data.get("cuisine_preference", ["indian"]),
            dietary_restrictions=request_data.get("dietary_restrictions", []),
            available_ingredients=request_data.get("available_ingredients", []),
            target_calories=request_data.get("target_calories", 400),
            budget_limit=request_data.get("budget_limit", 200),
            meal_type=RecipeCategory(request_data.get("meal_type", "lunch")),
            difficulty_level=RecipeDifficulty(request_data.get("difficulty_level", "easy")),
            time_constraint=request_data.get("time_constraint", 60),
            health_conditions=request_data.get("health_conditions", []),
            serving_size=request_data.get("serving_size", 2)
        )
    
    def _generate_cache_key(self, request: RecipeRequest) -> str:
        """Generate cache key from recipe request"""
        key_parts = [
            ",".join(sorted(request.cuisine_preference)),
            ",".join(sorted(request.dietary_restrictions)),
            ",".join(sorted(request.available_ingredients)),
            str(request.target_calories),
            str(request.budget_limit),
            request.meal_type.value,
            request.difficulty_level.value,
            str(request.time_constraint),
            ",".join(sorted(request.health_conditions)),
            str(request.serving_size)
        ]
        return "|".join(key_parts)
    
    def _recipe_to_dict(self, recipe: Recipe) -> dict:
        """Convert Recipe object to dictionary"""
        return {
            "id": recipe.id,
            "name": recipe.name,
            "description": recipe.description,
            "cuisine": recipe.cuisine.value,
            "category": recipe.category.value,
            "difficulty": recipe.difficulty.value,
            "preparation_time": recipe.preparation_time,
            "cooking_time": recipe.cooking_time,
            "total_time": recipe.preparation_time + recipe.cooking_time,
            "servings": recipe.servings,
            "ingredients": [
                {
                    "name": ing.name,
                    "quantity": ing.quantity,
                    "unit": ing.unit,
                    "category": ing.category,
                    "cost_per_unit": ing.cost_per_unit
                }
                for ing in recipe.ingredients
            ],
            "instructions": recipe.instructions,
            "nutrition_per_serving": recipe.nutrition_per_serving,
            "cost_per_serving": round(recipe.cost_per_serving, 2),
            "total_cost": round(recipe.cost_per_serving * recipe.servings, 2),
            "tags": recipe.tags,
            "seasonal_tags": recipe.seasonal_tags,
            "health_benefits": recipe.health_benefits,
            "created_at": recipe.created_at.isoformat(),
            "rating": recipe.rating,
            "review_count": recipe.review_count
        }
    
    def _dict_to_recipe(self, recipe_dict: dict) -> Recipe:
        """Convert dictionary back to Recipe object"""
        ingredients = [
            Ingredient(
                name=ing["name"],
                quantity=ing["quantity"],
                unit=ing["unit"],
                category=ing["category"],
                cost_per_unit=ing["cost_per_unit"],
                calories_per_unit=0,  # These would need to be looked up
                protein_per_unit=0,
                carbs_per_unit=0,
                fats_per_unit=0
            )
            for ing in recipe_dict["ingredients"]
        ]
        
        return Recipe(
            id=recipe_dict["id"],
            name=recipe_dict["name"],
            description=recipe_dict["description"],
            cuisine=RecipeCuisine(recipe_dict["cuisine"]),
            category=RecipeCategory(recipe_dict["category"]),
            difficulty=RecipeDifficulty(recipe_dict["difficulty"]),
            preparation_time=recipe_dict["preparation_time"],
            cooking_time=recipe_dict["cooking_time"],
            servings=recipe_dict["servings"],
            ingredients=ingredients,
            instructions=recipe_dict["instructions"],
            nutrition_per_serving=recipe_dict["nutrition_per_serving"],
            cost_per_serving=recipe_dict["cost_per_serving"],
            tags=recipe_dict["tags"],
            seasonal_tags=recipe_dict["seasonal_tags"],
            health_benefits=recipe_dict["health_benefits"],
            created_at=datetime.fromisoformat(recipe_dict["created_at"]),
            rating=recipe_dict.get("rating", 0.0),
            review_count=recipe_dict.get("review_count", 0)
        )
    
    def _calculate_health_score(self, nutrition: dict) -> int:
        """Calculate health score based on nutrition (0-100)"""
        score = 50  # Base score
        
        # Add points for good nutrients
        if nutrition["protein"] >= 15:
            score += 10
        if nutrition["fiber"] >= 5:
            score += 10
        if nutrition["calories"] <= 500:
            score += 10
        
        # Subtract points for concerning nutrients
        if nutrition["sodium"] > 800:
            score -= 10
        if nutrition["sugar"] > 15:
            score -= 10
        if nutrition["fats"] > 20:
            score -= 5
        
        return max(0, min(100, score))
    
    def _get_dietary_flags(self, recipe: dict, nutrition: dict) -> List[str]:
        """Get dietary flags for the recipe"""
        flags = []
        
        if nutrition["calories"] > 600:
            flags.append("high-calorie")
        elif nutrition["calories"] < 200:
            flags.append("low-calorie")
        
        if nutrition["protein"] > 20:
            flags.append("high-protein")
        
        if nutrition["sodium"] > 800:
            flags.append("high-sodium")
        
        if nutrition["fiber"] > 8:
            flags.append("high-fiber")
        
        if "vegan" in recipe["tags"]:
            flags.append("vegan-friendly")
        
        if "vegetarian" in recipe["tags"]:
            flags.append("vegetarian-friendly")
        
        return flags

# Create global service instance
recipe_service = RecipeGeneratorService()