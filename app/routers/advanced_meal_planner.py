import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import Goal, User, get_db
from app.services import macro_targets

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
    # Off by default so the existing calorie-only behaviour is untouched. When
    # set, every day is held to all four macros from the user's active goal
    # rather than to "a balance appropriate for general healthy eating", which
    # was the only macro instruction the planner had.
    match_macros: bool = Field(default=False, description="Hold every day to the user's macro targets")

class AdaptationRequirements(BaseModel):
    """
    What an adaptation is allowed to change.

    Typed and bounded rather than an open dictionary. The old
    `Dict[str, Any]` accepted anything at all and forwarded it verbatim into
    the prompt, which is both a quota-abuse vector and a way to smuggle
    instructions past the restriction handling below.

    Note what is NOT here: any way to REMOVE a dietary restriction. Additional
    restrictions may be added; the ones the plan was built with are preserved
    by the service regardless of what arrives here or in the free-text
    feedback.
    """
    target_calories: Optional[int] = Field(None, gt=0, le=10000)
    meals_per_day: Optional[int] = Field(None, ge=1, le=6)
    dietary_restrictions: Optional[List[str]] = Field(
        None, max_length=20, description="Additional restrictions to ADD")
    food_preferences: Optional[List[str]] = Field(None, max_length=30)
    budget_per_day: Optional[float] = Field(None, ge=0)
    region_or_cuisine: Optional[str] = Field(None, max_length=80)


class MealPlanAdaptationRequest(BaseModel):
    current_plan: Dict[str, Any] = Field(..., description="Current meal plan to adapt")
    feedback: str = Field(..., min_length=1, max_length=2000,
                          description="User feedback on the current plan")
    new_requirements: Optional[AdaptationRequirements] = Field(
        None, description="New requirements or preferences")
    match_macros: bool = Field(
        default=False, description="Hold every adapted day to the user's macro targets")

@router.post("/advanced-meal-planner/generate", status_code=201)
async def generate_advanced_meal_plan(
    request: MealPlanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate a comprehensive 7-day meal plan using AdvancedMealPlanner AI agent.
    """
    try:
        # Convert Pydantic model to dict
        payload = request.dict()

        # The weight goal travels with the request. Unlike the macro target it
        # is never a hard requirement, so it is not gated on match_macros - a
        # plan should know what the person is working towards whether or not
        # they asked for strict macro matching.
        from app.services import weight_progress
        progress = weight_progress.for_user(db, current_user)
        active_goal = (
            db.query(Goal)
            .filter(Goal.user_id == current_user.id, Goal.is_active == True)  # noqa: E712
            .order_by(Goal.created_at.desc())
            .first()
        )
        payload["goal_context"] = weight_progress.prompt_block(
            progress, getattr(active_goal, "goal_type", None)
        )

        target = None
        if request.match_macros:
            # A full day's targets, applied to each of the seven days.
            target = macro_targets.resolve(db, current_user,
                                           meal_type="full_day", basis="daily")
            if target is None:
                raise HTTPException(
                    status_code=400,
                    detail="Set a nutrition goal first and the plan can be built around your macros.",
                )
            if not target.complete:
                # Strict mode against a goal with no protein/carb/fat numbers
                # cannot produce a meaningful verdict - zero targets are
                # trivially "missed" by everything and trivially "hit" by a
                # plan totalling zero. Say what is missing instead of
                # reporting a verification nobody can act on.
                raise HTTPException(
                    status_code=400,
                    detail=("Your nutrition goal is missing "
                            + ", ".join(target.missing_fields())
                            + ". Set all four numbers to match macros, or turn "
                              "off macro matching for a calorie-only plan."),
                )

            # ONE authoritative calorie target. The form's target_calories and
            # the goal's calorie figure are two different numbers that both
            # used to reach the prompt, so the model was told to hit 1800 and
            # 2400 simultaneously and the verification then judged it against
            # the goal it never prioritised.
            requested = float(request.target_calories)
            resolved = float(target.calories)
            drift = abs(requested - resolved) / resolved if resolved else 0.0
            if drift > macro_targets.CALORIE_TOLERANCE:
                raise HTTPException(
                    status_code=400,
                    detail=(f"Macro matching uses your goal's {resolved:.0f} kcal, "
                            f"but this form asked for {requested:.0f} kcal. Set the "
                            f"form to {resolved:.0f}, or turn off macro matching to "
                            f"plan at {requested:.0f} kcal."),
                )
            # Within tolerance: align the payload to the resolved target so the
            # prompt and the verification agree on one number.
            payload["target_calories"] = int(round(resolved))

        result = advanced_meal_planner_service.generate_meal_plan(payload, macro_target=target)

        if result["success"]:
            plan = result["meal_plan"]
            # Attached to the plan itself so it survives being saved and
            # restored - a verification that vanishes on reload is not much of
            # a record.
            #
            # ALWAYS attached, not only in macro mode. Gating it on `target`
            # meant a standard-mode plan carried no verification at all, so a
            # 500 kcal/day week was returned while the UI showed the model's
            # own meta.total_daily_calories - and every dietary advisory,
            # "may contain" warning and unverifiable-restriction notice was
            # dropped at this boundary. The checks ran; nobody saw them.
            plan["verification"] = result.get("verification")
            if target:
                plan["macro_target"] = target.as_dict()
            return {
                "success": True,
                "message": "Advanced meal plan generated successfully",
                "data": plan
            }
        else:
            error_msg = result.get("error", "Failed to generate meal plan")
            logger.error(f"Service failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        # Re-raise untouched. Previously this fell into the generic handler
        # below, which wrapped it in another message - losing the specific
        # reason the service reported.
        raise
    except Exception as e:
        # Include the exception type. Some exceptions have an empty str(), and
        # the old message ("Failed to generate meal plan: " with nothing after
        # the colon) told neither the user nor the log anything at all.
        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        logger.error("generate_advanced_meal_plan failed: %s", detail, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Meal planner error — {detail}")

@router.post("/advanced-meal-planner/adapt", status_code=200)
async def adapt_advanced_meal_plan(
    request: MealPlanAdaptationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Adapt an existing meal plan based on user feedback.

    Authenticated, like generation. It was not: anyone could POST an arbitrary
    dictionary and spend a reasoning-tier generation on it, and there was no
    authenticated user to recover the macro targets or restrictions from -
    which is why adaptation could silently drop them.
    """
    try:
        requirements = (request.new_requirements.dict(exclude_none=True)
                        if request.new_requirements else {})

        target = None
        if request.match_macros:
            target = macro_targets.resolve(db, current_user,
                                           meal_type="full_day", basis="daily")
            if target is None or not target.complete:
                missing = (", ".join(target.missing_fields()) if target
                           else "a nutrition goal")
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot match macros while adapting: {missing} not set.",
                )

        # Restrictions come from the authenticated user's own plan metadata and
        # the typed requirements - never parsed out of the free-text feedback,
        # which is exactly how "make it creamier" used to be able to remove a
        # dairy-free requirement.
        target_calories = requirements.get("target_calories")
        if target is not None:
            target_calories = int(round(target.calories))

        result = advanced_meal_planner_service.adapt_meal_plan(
            current_plan=request.current_plan,
            feedback=request.feedback,
            new_requirements=requirements or None,
            meals_per_day=requirements.get("meals_per_day"),
            restrictions=requirements.get("dietary_restrictions"),
            target_calories=target_calories,
            macro_target=target,
        )

        if result["success"]:
            plan = result["adapted_plan"]
            if target:
                plan["macro_target"] = target.as_dict()
            plan["verification"] = result.get("verification")
            return {
                "success": True,
                "message": "Meal plan adapted successfully",
                "data": plan,
            }

        # A rejected adaptation is the caller's input being unusable, not a
        # server fault - 422 so the frontend can show the reason rather than a
        # generic 500.
        raise HTTPException(
            status_code=422,
            detail=result.get("error", "Failed to adapt meal plan"),
        )

    except HTTPException:
        # Re-raise untouched. Wrapping it in another 500 below lost the
        # specific reason the service reported.
        raise
    except Exception as e:
        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        logger.error("adapt_advanced_meal_plan failed: %s", detail, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Meal planner error — {detail}")

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
