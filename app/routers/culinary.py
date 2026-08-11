import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import User, get_db
from app.services import macro_targets

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
    ANDHRA_PRADESH = "andhra_pradesh"
    ARUNACHAL_PRADESH = "arunachal_pradesh"
    ASSAM = "assam"
    BIHAR = "bihar"
    CHHATTISGARH = "chhattisgarh"
    GOA = "goa"
    GUJARAT = "gujarat"
    HARYANA = "haryana"
    HIMACHAL_PRADESH = "himachal_pradesh"
    JHARKHAND = "jharkhand"
    KARNATAKA = "karnataka"
    KERALA = "kerala"
    MADHYA_PRADESH = "madhya_pradesh"
    MAHARASHTRA = "maharashtra"
    MANIPUR = "manipur"
    MEGHALAYA = "meghalaya"
    MIZORAM = "mizoram"
    NAGALAND = "nagaland"
    ODISHA = "odisha"
    PUNJAB = "punjab"
    RAJASTHAN = "rajasthan"
    SIKKIM = "sikkim"
    TAMIL_NADU = "tamil_nadu"
    TELANGANA = "telangana"
    TRIPURA = "tripura"
    UTTAR_PRADESH = "uttar_pradesh"
    UTTARAKHAND = "uttarakhand"
    WEST_BENGAL = "west_bengal"
    
    # Union Territories
    ANDAMAN_NICOBAR = "andaman_nicobar"
    CHANDIGARH = "chandigarh"
    DADRA_NAGAR_HAVELI = "dadra_nagar_haveli"
    DAMAN_DIU = "daman_diu"
    DELHI = "delhi"
    JAMMU_KASHMIR = "jammu_kashmir"
    LADAKH = "ladakh"
    LAKSHADWEEP = "lakshadweep"
    PUDUCHERRY = "puducherry"

class RegionalMealPlanRequest(BaseModel):
    cuisine_region: CuisineRegion = Field(..., description="Preferred cuisine or regional preference")
    meal_type: MealType = Field(default=MealType.FULL_DAY, description="Type of meal plan")
    dietary_restrictions: List[str] = Field(default=[], description="Dietary restrictions or preferences")
    time_constraint: int = Field(default=60, ge=15, le=300, description="Maximum cooking time in minutes")
    cooking_skill: CookingSkill = Field(default=CookingSkill.INTERMEDIATE, description="User's cooking skill level")
    available_ingredients: List[str] = Field(default=[], description="Available ingredients (optional)")
    # Off by default, so the existing generic behaviour is untouched.
    personalised: bool = Field(default=False, description="Build the plan to hit the user's macro targets")
    # daily = the day's goal split across this meal type
    # remaining = what is left of today after everything already logged
    basis: str = Field(default="daily", description="daily | remaining")

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

@router.get("/culinary/macro-targets")
async def get_macro_targets(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    What each mode would aim at right now.

    Fetched before generating so the numbers can be shown on the mode picker -
    personalisation applied invisibly is indistinguishable from no
    personalisation at all.
    """
    try:
        return {"success": True, **macro_targets.preview(db, current_user)}
    except Exception as e:
        logger.error("macro target preview failed: %s", e, exc_info=True)
        return {"success": False, "has_goal": False}


@router.post("/culinary/generate-meal-plan", status_code=201)
async def generate_regional_meal_plan(
    request: RegionalMealPlanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate a regional meal plan using CulinaryExplorer AI agent.

    With `personalised` set, the plan is built to hit the user's macro targets
    rather than being nutritionally arbitrary - the generator has never had
    access to a single one of their numbers, so a full day of regional food
    could total 40g of protein against a 150g target and look entirely fine.
    """
    try:
        target = None
        if request.personalised:
            target = macro_targets.resolve(
                db, current_user,
                meal_type=request.meal_type.value,
                basis=request.basis,
            )
            if target is None:
                # No goal set. Refuse rather than generating something that
                # claims to be personalised and is not.
                raise HTTPException(
                    status_code=400,
                    detail="Set a nutrition goal first and this can build around your targets.",
                )
            if not target.usable:
                raise HTTPException(
                    status_code=400,
                    detail=("You have already met today's targets, so there is nothing "
                            "left to plan around. Switch to a standard plan, or try "
                            "'my daily targets' instead of what's left."),
                )

        # The weight goal, independent of `personalised`. Macro matching is
        # opt-in because it constrains the food hard; knowing what the person
        # is working towards costs nothing and shapes the choices either way.
        from app.database import Goal
        from app.services import weight_progress

        active_goal = (
            db.query(Goal)
            .filter(Goal.user_id == current_user.id, Goal.is_active == True)  # noqa: E712
            .order_by(Goal.created_at.desc())
            .first()
        )
        goal_context = weight_progress.prompt_block(
            weight_progress.for_user(db, current_user, goal=active_goal),
            getattr(active_goal, "goal_type", None),
        )

        result = await culinaryexplorer_service.generate_regional_meal_plan(
            cuisine_region=request.cuisine_region.value,
            meal_type=request.meal_type.value,
            dietary_restrictions=request.dietary_restrictions,
            time_constraint=request.time_constraint,
            cooking_skill=request.cooking_skill.value,
            available_ingredients=request.available_ingredients,
            macro_target=target,
            goal_context=goal_context,
        )
        if result["success"]:
            if target:
                result["macro_target"] = target.as_dict()
            return {"success": True, "message": "Regional meal plan generated successfully", "data": result}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate regional meal plan"))
    except HTTPException:
        raise  # keep the specific reason instead of re-wrapping it
    except Exception as e:
        logger.error("generate_regional_meal_plan failed: %s", f"{type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explorer error — {type(e).__name__}: {e}" if str(e) else f"Explorer error — {type(e).__name__}")

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
    except HTTPException:
        raise  # keep the specific reason instead of re-wrapping it
    except Exception as e:
        logger.error("generate_regional_recipe failed: %s", f"{type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explorer error — {type(e).__name__}: {e}" if str(e) else f"Explorer error — {type(e).__name__}")

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
    except HTTPException:
        raise  # keep the specific reason instead of re-wrapping it
    except Exception as e:
        logger.error("adapt_regional_plan failed: %s", f"{type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explorer error — {type(e).__name__}: {e}" if str(e) else f"Explorer error — {type(e).__name__}")

@router.get("/culinary/cuisine-regions")
async def get_cuisine_regions():
    """Get available cuisine regions and Indian states"""
    global_cuisines = [{"value": region.value, "label": region.value.replace('_', ' ').title(), "type": "global"} 
                      for region in CuisineRegion if region.value in ["mediterranean", "japanese", "mexican", "italian", "chinese", "thai", "french", "indian"]]
    
    # Indian States (28 states)
    indian_states = [{"value": region.value, "label": region.value.replace('_', ' ').title(), "type": "indian_state"} 
                    for region in CuisineRegion if region.value in [
                        "andhra_pradesh", "arunachal_pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", 
                        "haryana", "himachal_pradesh", "jharkhand", "karnataka", "kerala", "madhya_pradesh", 
                        "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab", 
                        "rajasthan", "sikkim", "tamil_nadu", "telangana", "tripura", "uttar_pradesh", 
                        "uttarakhand", "west_bengal"
                    ]]
    
    # Union Territories (8 union territories)
    union_territories = [{"value": region.value, "label": region.value.replace('_', ' ').title(), "type": "union_territory"} 
                        for region in CuisineRegion if region.value in [
                            "andaman_nicobar", "chandigarh", "dadra_nagar_haveli", "daman_diu", "delhi", 
                            "jammu_kashmir", "ladakh", "lakshadweep", "puducherry"
                        ]]
    
    return {
        "global_cuisines": global_cuisines,
        "indian_states": indian_states,
        "union_territories": union_territories
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
