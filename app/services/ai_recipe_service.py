from fastapi import HTTPException
from typing import Dict, List, Optional, Union
import json
import logging
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum
from .chefgenius_service import chefgenius_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API responses
class RecipeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None

class RecipeGeneratorService:
    """Service layer for ChefGenius Recipe Generator with caching and error handling"""
    
    def __init__(self):
        self.recipe_cache = {}  # In-memory cache - could be replaced with Redis
        
    async def generate_recipe(self, request_data: dict) -> dict:
        """Generate a new recipe using ChefGenius based on request parameters"""
        try:
            # Extract ingredients from the request
            ingredients = request_data.get('available_ingredients', [])
            dietary_restrictions = request_data.get('dietary_restrictions', [])
            time_constraint = request_data.get('time_constraint', 60)
            meal_type = request_data.get('meal_type', 'dinner')
            
            # Check cache first
            cache_key = f"{','.join(sorted(ingredients))}_{','.join(sorted(dietary_restrictions))}_{time_constraint}_{meal_type}"
            if cache_key in self.recipe_cache:
                logger.info(f"Recipe found in cache: {cache_key}")
                return self.recipe_cache[cache_key]
            
            # Generate new recipe using ChefGenius
            logger.info("Generating new recipe using ChefGenius...")
            result = await chefgenius_service.generate_recipe_from_ingredients(
                ingredients=ingredients,
                dietary_restrictions=dietary_restrictions,
                time_constraint=time_constraint,
                meal_type=meal_type
            )
            
            if result["success"]:
                # Cache the result
                self.recipe_cache[cache_key] = result
                logger.info(f"Recipe generated successfully: {len(ingredients)} ingredients")
                return result
            else:
                raise HTTPException(status_code=500, detail=result["error"])
            
        except Exception as e:
            logger.error(f"Error generating recipe: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Recipe generation failed: {str(e)}")
    
    async def scale_recipe(self, recipe_id: str, new_servings: int) -> dict:
        """Scale recipe for different serving sizes"""
        # For now, return a simple response since ChefGenius handles scaling in the prompt
        return {
            "success": True,
            "message": "Recipe scaling is handled by ChefGenius in the generated content",
            "data": {"scaled_servings": new_servings}
        }
    
    async def suggest_ingredient_substitutions(self, original_ingredient: str, dietary_restrictions: List[str], budget_constraint: float) -> List[Dict]:
        """Suggest ingredient substitutions"""
        # ChefGenius can handle substitutions in the generated content
        return [{
            "original": original_ingredient,
            "substitution": "Ask ChefGenius for suggestions",
            "cost_difference": 0.0,
            "nutrition_impact": "ChefGenius will provide detailed substitution advice"
        }]

# Global service instance
recipe_service = RecipeGeneratorService()