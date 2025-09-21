import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

from ..services.advanced_meal_planner_service import advanced_meal_planner_service

logger = logging.getLogger(__name__)
router = APIRouter()

class MealPlanRequest(BaseModel):
    target_calories: int = Field(..., gt=0, description="Daily target calories")
    meals_per_day: int = Field(3, ge=1, le=6, description="Number of meals per day")
    food_preferences: Optional[List[str]] = Field(default_factory=list, description="Food preferences (e.g., 'Indian', 'chicken', 'vegetarian')")
    budget_per_day: Optional[float] = Field(None, ge=0, description="Daily budget in currency units")
    work_hours_per_day: Optional[int] = Field(8, ge=0, le=24, description="Work hours per day")
    dietary_restrictions: Optional[List[str]] = Field(default_factory=list, description="Dietary restrictions (e.g., 'gluten-free', 'dairy-free')")
    equipment: Optional[List[str]] = Field(default_factory=list, description="Available kitchen equipment")
    time_per_meal_min: Optional[int] = Field(30, ge=5, description="Average time per meal in minutes")
    region_or_cuisine: Optional[str] = Field(None, description="Preferred region or cuisine")
    user_notes: Optional[str] = Field(None, description="Additional user notes or preferences")

class MealPlanAdaptationRequest(BaseModel):
    current_plan: Dict[str, Any] = Field(..., description="Current meal plan to adapt")
    feedback: str = Field(..., description="User feedback on the current plan")
    new_requirements: Optional[Dict[str, Any]] = Field(None, description="New requirements or preferences")

@router.post("/advanced-meal-planner/generate", status_code=201)
async def generate_advanced_meal_plan(request: MealPlanRequest):
    """
    Generate a comprehensive 7-day meal plan using AdvancedMealPlanner AI agent.
    """
    try:
        # Convert Pydantic model to dict
        payload = request.dict()
        
        result = advanced_meal_planner_service.generate_meal_plan(payload)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Advanced meal plan generated successfully",
                "data": result["meal_plan"]
            }
        else:
            error_msg = result.get("error", "Failed to generate meal plan")
            logger.error(f"Service failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
            
    except Exception as e:
        logger.error(f"Error in generate_advanced_meal_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")

@router.post("/advanced-meal-planner/adapt", status_code=200)
async def adapt_advanced_meal_plan(request: MealPlanAdaptationRequest):
    """
    Adapt an existing meal plan based on user feedback using AdvancedMealPlanner AI agent.
    """
    try:
        result = advanced_meal_planner_service.adapt_meal_plan(
            current_plan=request.current_plan,
            feedback=request.feedback,
            new_requirements=request.new_requirements
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Meal plan adapted successfully",
                "data": result["adapted_plan"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to adapt meal plan"))
            
    except Exception as e:
        logger.error(f"Error in adapt_advanced_meal_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to adapt meal plan: {str(e)}")

@router.get("/advanced-meal-planner/equipment-options")
async def get_equipment_options():
    """Get available kitchen equipment options"""
    return [
        {"value": "stove", "label": "Stove", "description": "Gas or electric stove"},
        {"value": "oven", "label": "Oven", "description": "Conventional or convection oven"},
        {"value": "microwave", "label": "Microwave", "description": "Microwave oven"},
        {"value": "blender", "label": "Blender", "description": "Countertop or immersion blender"},
        {"value": "food_processor", "label": "Food Processor", "description": "Food processor or chopper"},
        {"value": "slow_cooker", "label": "Slow Cooker", "description": "Crock pot or slow cooker"},
        {"value": "pressure_cooker", "label": "Pressure Cooker", "description": "Instant pot or pressure cooker"},
        {"value": "grill", "label": "Grill", "description": "Indoor or outdoor grill"},
        {"value": "air_fryer", "label": "Air Fryer", "description": "Air fryer"},
        {"value": "rice_cooker", "label": "Rice Cooker", "description": "Rice cooker"},
        {"value": "basic", "label": "Basic", "description": "Basic kitchen setup only"}
    ]

@router.get("/advanced-meal-planner/cuisine-options")
async def get_cuisine_options():
    """Get available cuisine and region options"""
    return [
        {"value": "indian", "label": "Indian", "description": "Traditional Indian cuisine"},
        {"value": "mediterranean", "label": "Mediterranean", "description": "Mediterranean diet"},
        {"value": "asian", "label": "Asian", "description": "Asian cuisine"},
        {"value": "mexican", "label": "Mexican", "description": "Mexican cuisine"},
        {"value": "italian", "label": "Italian", "description": "Italian cuisine"},
        {"value": "american", "label": "American", "description": "American cuisine"},
        {"value": "middle_eastern", "label": "Middle Eastern", "description": "Middle Eastern cuisine"},
        {"value": "thai", "label": "Thai", "description": "Thai cuisine"},
        {"value": "chinese", "label": "Chinese", "description": "Chinese cuisine"},
        {"value": "japanese", "label": "Japanese", "description": "Japanese cuisine"},
        {"value": "french", "label": "French", "description": "French cuisine"},
        {"value": "mixed", "label": "Mixed", "description": "Mixed international cuisine"}
    ]

@router.get("/advanced-meal-planner/dietary-restrictions")
async def get_dietary_restrictions():
    """Get available dietary restriction options"""
    return [
        {"value": "vegetarian", "label": "Vegetarian", "description": "No meat or fish"},
        {"value": "vegan", "label": "Vegan", "description": "No animal products"},
        {"value": "gluten_free", "label": "Gluten-Free", "description": "No gluten-containing foods"},
        {"value": "dairy_free", "label": "Dairy-Free", "description": "No dairy products"},
        {"value": "nut_free", "label": "Nut-Free", "description": "No nuts or tree nuts"},
        {"value": "low_carb", "label": "Low-Carb", "description": "Reduced carbohydrate intake"},
        {"value": "low_fat", "label": "Low-Fat", "description": "Reduced fat intake"},
        {"value": "low_sodium", "label": "Low-Sodium", "description": "Reduced sodium intake"},
        {"value": "keto", "label": "Ketogenic", "description": "Very low carb, high fat diet"},
        {"value": "paleo", "label": "Paleo", "description": "Paleolithic diet"},
        {"value": "diabetic_friendly", "label": "Diabetic-Friendly", "description": "Suitable for diabetes management"},
        {"value": "heart_healthy", "label": "Heart-Healthy", "description": "Heart-healthy diet"}
    ]

@router.get("/advanced-meal-planner/sample-preferences")
async def get_sample_preferences():
    """Get sample food preferences for inspiration"""
    return {
        "proteins": ["chicken", "fish", "beef", "pork", "lamb", "tofu", "eggs", "beans", "lentils"],
        "cuisines": ["indian", "mediterranean", "asian", "mexican", "italian", "american"],
        "cooking_methods": ["grilled", "baked", "steamed", "stir-fried", "roasted", "boiled"],
        "ingredients": ["rice", "pasta", "quinoa", "vegetables", "fruits", "nuts", "seeds"],
        "meal_types": ["quick", "make-ahead", "one-pot", "sheet-pan", "slow-cooker"]
    }
