from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

# Import the service
from ..services.budgetchef_service import budgetchef_service

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget", tags=["budget"])

class BudgetMealPlanRequest(BaseModel):
    """Request model for budget meal plan generation"""
    budget_per_day: float = Field(
        ...,
        ge=50.0,
        le=2000.0,
        description="Budget per day in INR"
    )
    calorie_target: Optional[int] = Field(
        default=None,
        ge=1000,
        le=5000,
        description="Target calories per day (optional, will be estimated if not provided)"
    )
    dietary_preferences: List[str] = Field(
        default=[],
        description="Dietary preferences (e.g., 'vegetarian', 'vegan', 'gluten-free')"
    )
    meals_per_day: int = Field(
        default=3,
        ge=1,
        le=6,
        description="Number of meals per day"
    )
    cooking_time: str = Field(
        default="moderate",
        description="Available cooking time: quick, moderate, or extensive"
    )
    skill_level: str = Field(
        default="intermediate",
        description="Cooking skill level: beginner, intermediate, or advanced"
    )
    age: Optional[int] = Field(
        default=None,
        ge=13,
        le=100,
        description="Age in years (optional, for calorie estimation)"
    )
    weight: Optional[float] = Field(
        default=None,
        ge=30.0,
        le=300.0,
        description="Weight in kg (optional, for calorie estimation)"
    )
    activity_level: str = Field(
        default="moderate",
        description="Activity level: sedentary, light, moderate, active, or very_active"
    )

class BudgetMealAdaptationRequest(BaseModel):
    """Request model for budget meal plan adaptation"""
    current_plan: str = Field(
        ...,
        description="Current budget meal plan to adapt"
    )
    feedback: str = Field(
        ...,
        description="User feedback on the current plan"
    )
    new_budget: Optional[float] = Field(
        default=None,
        ge=50.0,
        le=2000.0,
        description="New budget per day in INR (optional)"
    )
    new_calorie_target: Optional[int] = Field(
        default=None,
        ge=1000,
        le=5000,
        description="New calorie target (optional)"
    )

@router.post("/generate-meal-plan", status_code=201)
async def generate_budget_meal_plan(request: BudgetMealPlanRequest):
    """
    Generate a budget meal plan using BudgetChef agent.
    
    This endpoint creates a cost-effective meal plan based on:
    - Daily budget constraints
    - Calorie and nutrition targets
    - Dietary preferences and restrictions
    - Cooking time and skill level
    - Personal factors (age, weight, activity level)
    """
    try:
        result = await budgetchef_service.generate_budget_meal_plan(
            budget_per_day=request.budget_per_day,
            calorie_target=request.calorie_target,
            dietary_preferences=request.dietary_preferences,
            meals_per_day=request.meals_per_day,
            cooking_time=request.cooking_time,
            skill_level=request.skill_level,
            age=request.age,
            weight=request.weight,
            activity_level=request.activity_level
        )

        if result["success"]:
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "Budget meal plan generated successfully using BudgetChef",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Budget meal plan generation failed",
                    "error": result["error"]
                }
            )

    except Exception as e:
        logger.error(f"Error in generate_budget_meal_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/adapt-meal-plan", status_code=200)
async def adapt_budget_meal_plan(request: BudgetMealAdaptationRequest):
    """
    Adapt an existing budget meal plan based on user feedback.
    
    This endpoint modifies a meal plan based on:
    - User feedback and preferences
    - Budget changes
    - Calorie target adjustments
    - Specific requests for modifications
    """
    try:
        result = await budgetchef_service.adapt_budget_meal_plan(
            current_plan=request.current_plan,
            feedback=request.feedback,
            new_budget=request.new_budget,
            new_calorie_target=request.new_calorie_target
        )

        if result["success"]:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Budget meal plan adapted successfully using BudgetChef",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Budget meal plan adaptation failed",
                    "error": result["error"]
                }
            )

    except Exception as e:
        logger.error(f"Error in adapt_budget_meal_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cooking-time-options")
async def get_cooking_time_options():
    """Get available cooking time options"""
    return {
        "cooking_time_options": [
            {"value": "quick", "label": "Quick (15-30 minutes)", "description": "Fast meals with minimal prep time"},
            {"value": "moderate", "label": "Moderate (30-60 minutes)", "description": "Balanced cooking time with some prep"},
            {"value": "extensive", "label": "Extensive (60+ minutes)", "description": "Complex meals with longer cooking times"}
        ]
    }

@router.get("/skill-levels")
async def get_skill_levels():
    """Get available cooking skill levels"""
    return {
        "skill_levels": [
            {"value": "beginner", "label": "Beginner", "description": "Basic cooking skills, simple recipes"},
            {"value": "intermediate", "label": "Intermediate", "description": "Some experience, moderate complexity"},
            {"value": "advanced", "label": "Advanced", "description": "Experienced cook, complex techniques"}
        ]
    }

@router.get("/activity-levels")
async def get_activity_levels():
    """Get available activity levels for calorie estimation"""
    return {
        "activity_levels": [
            {"value": "sedentary", "label": "Sedentary", "description": "Little to no exercise"},
            {"value": "light", "label": "Light", "description": "Light exercise 1-3 days/week"},
            {"value": "moderate", "label": "Moderate", "description": "Moderate exercise 3-5 days/week"},
            {"value": "active", "label": "Active", "description": "Heavy exercise 6-7 days/week"},
            {"value": "very_active", "label": "Very Active", "description": "Very heavy exercise, physical job"}
        ]
    }
