import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

from ..services.culinaryexplorer_service import culinaryexplorer_service

logger = logging.getLogger(__name__)
router = APIRouter()

class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    FULL_DAY = "full_day"

class CookingSkill(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class CuisineRegion(str, Enum):
    # Global Cuisines
    MEDITERRANEAN = "mediterranean"
    JAPANESE = "japanese"
    MEXICAN = "mexican"
    ITALIAN = "italian"
    CHINESE = "chinese"
    THAI = "thai"
    FRENCH = "french"
    INDIAN = "indian"
    
    # Indian States
    PUNJAB = "punjab"
    KERALA = "kerala"
    GUJARAT = "gujarat"
    TAMIL_NADU = "tamil_nadu"
    RAJASTHAN = "rajasthan"
    BENGAL = "bengal"
    MAHARASHTRA = "maharashtra"
    KARNATAKA = "karnataka"
    ANDHRA_PRADESH = "andhra_pradesh"
    UTTAR_PRADESH = "uttar_pradesh"
    DELHI = "delhi"
    GOA = "goa"
    HIMACHAL_PRADESH = "himachal_pradesh"
    KASHMIR = "kashmir"

class RegionalMealPlanRequest(BaseModel):
    cuisine_region: CuisineRegion = Field(..., description="Preferred cuisine or regional preference")
    meal_type: MealType = Field(default=MealType.FULL_DAY, description="Type of meal plan")
    dietary_restrictions: List[str] = Field(default=[], description="Dietary restrictions or preferences")
    time_constraint: int = Field(default=60, ge=15, le=300, description="Maximum cooking time in minutes")
    cooking_skill: CookingSkill = Field(default=CookingSkill.INTERMEDIATE, description="User's cooking skill level")
    available_ingredients: List[str] = Field(default=[], description="Available ingredients (optional)")

class RegionalRecipeRequest(BaseModel):
    cuisine_region: CuisineRegion = Field(..., description="Preferred cuisine or regional preference")
    dish_name: Optional[str] = Field(default=None, description="Specific dish name (optional)")
    dietary_restrictions: List[str] = Field(default=[], description="Dietary restrictions or preferences")
    time_constraint: int = Field(default=60, ge=15, le=300, description="Maximum cooking time in minutes")
    cooking_skill: CookingSkill = Field(default=CookingSkill.INTERMEDIATE, description="User's cooking skill level")
    available_ingredients: List[str] = Field(default=[], description="Available ingredients (optional)")

class RegionalPlanAdaptationRequest(BaseModel):
    current_plan: str = Field(..., description="The current meal plan in markdown format")
    feedback: str = Field(..., description="User's feedback on the current plan")
    new_cuisine_preference: Optional[str] = Field(default=None, description="New cuisine preference (optional)")
    new_dietary_restrictions: Optional[List[str]] = Field(default=None, description="New dietary restrictions (optional)")

@router.post("/culinary/generate-meal-plan", status_code=201)
async def generate_regional_meal_plan(request: RegionalMealPlanRequest):
    """
    Generate a personalized regional meal plan using CulinaryExplorer AI agent.
    """
    try:
        result = await culinaryexplorer_service.generate_regional_meal_plan(
            cuisine_region=request.cuisine_region.value,
            meal_type=request.meal_type.value,
            dietary_restrictions=request.dietary_restrictions,
            time_constraint=request.time_constraint,
            cooking_skill=request.cooking_skill.value,
            available_ingredients=request.available_ingredients
        )
        if result["success"]:
            return {"success": True, "message": "Regional meal plan generated successfully", "data": result}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate regional meal plan"))
    except Exception as e:
        logger.error(f"Error in generate_regional_meal_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate regional meal plan: {str(e)}")

@router.post("/culinary/generate-recipe", status_code=201)
async def generate_regional_recipe(request: RegionalRecipeRequest):
    """
    Generate a specific regional recipe using CulinaryExplorer AI agent.
    """
    try:
        result = await culinaryexplorer_service.generate_regional_recipe(
            cuisine_region=request.cuisine_region.value,
            dish_name=request.dish_name,
            dietary_restrictions=request.dietary_restrictions,
            time_constraint=request.time_constraint,
            cooking_skill=request.cooking_skill.value,
            available_ingredients=request.available_ingredients
        )
        if result["success"]:
            return {"success": True, "message": "Regional recipe generated successfully", "data": result}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate regional recipe"))
    except Exception as e:
        logger.error(f"Error in generate_regional_recipe endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate regional recipe: {str(e)}")

@router.post("/culinary/adapt-plan", status_code=200)
async def adapt_regional_plan(request: RegionalPlanAdaptationRequest):
    """
    Adapt an existing regional meal plan based on user feedback using CulinaryExplorer AI agent.
    """
    try:
        result = await culinaryexplorer_service.adapt_regional_plan(
            current_plan=request.current_plan,
            feedback=request.feedback,
            new_cuisine_preference=request.new_cuisine_preference,
            new_dietary_restrictions=request.new_dietary_restrictions
        )
        if result["success"]:
            return {"success": True, "message": "Regional meal plan adapted successfully", "data": result}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to adapt regional meal plan"))
    except Exception as e:
        logger.error(f"Error in adapt_regional_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to adapt regional meal plan: {str(e)}")

@router.get("/culinary/cuisine-regions")
async def get_cuisine_regions():
    """Get available cuisine regions and Indian states"""
    global_cuisines = [{"value": region.value, "label": region.value.replace('_', ' ').title(), "type": "global"} 
                      for region in CuisineRegion if region.value in ["mediterranean", "japanese", "mexican", "italian", "chinese", "thai", "french", "indian"]]
    
    indian_states = [{"value": region.value, "label": region.value.replace('_', ' ').title(), "type": "indian_state"} 
                    for region in CuisineRegion if region.value not in ["mediterranean", "japanese", "mexican", "italian", "chinese", "thai", "french", "indian"]]
    
    return {
        "global_cuisines": global_cuisines,
        "indian_states": indian_states
    }

@router.get("/culinary/meal-types")
async def get_meal_types():
    return [{"value": meal.value, "label": meal.value.replace('_', ' ').title()} for meal in MealType]

@router.get("/culinary/cooking-skills")
async def get_cooking_skills():
    return [{"value": skill.value, "label": skill.value.replace('_', ' ').title()} for skill in CookingSkill]

@router.get("/culinary/dietary-options")
async def get_dietary_options():
    return [
        {"value": "vegetarian", "label": "Vegetarian"},
        {"value": "vegan", "label": "Vegan"},
        {"value": "gluten-free", "label": "Gluten-Free"},
        {"value": "dairy-free", "label": "Dairy-Free"},
        {"value": "nut-free", "label": "Nut-Free"},
        {"value": "low-carb", "label": "Low-Carb"},
        {"value": "high-protein", "label": "High-Protein"},
        {"value": "keto", "label": "Keto"},
        {"value": "paleo", "label": "Paleo"},
        {"value": "halal", "label": "Halal"},
        {"value": "kosher", "label": "Kosher"}
    ]
