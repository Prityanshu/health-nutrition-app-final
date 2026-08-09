import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from sqlalchemy.orm import Session

from ..services.nutrient_analyzer_service import nutrient_analyzer_service
from ..database import get_db
from ..auth import get_current_active_user
from ..database import User

logger = logging.getLogger(__name__)
router = APIRouter()

class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

class NutrientAnalysisRequest(BaseModel):
    food_name: str = Field(..., description="Name of the food item")
    serving_size: str = Field(..., description="Serving size (e.g., '1 cup', '150g', '2 pieces')")

class BarcodeRequest(BaseModel):
    barcode: str = Field(..., description="EAN/UPC digits from the packet")
    serving_size: str = Field(default="100g", description="How much of it they ate")


class MealLogRequest(BaseModel):
    food_name: str = Field(..., description="Name of the food item")
    serving_size: str = Field(..., description="Serving size (e.g., '1 cup', '150g', '2 pieces')")
    meal_type: MealType = Field(default=MealType.LUNCH, description="Type of meal")
    # The UI analyses first and shows the result for confirmation. Passing that
    # result back here lets the meal be logged without asking the model the
    # same question a second time - halving both the wait and the API quota
    # spent per logged meal.
    nutrients: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Nutrients from a prior /nutrient/analyze call. Re-analysed if omitted.",
    )

@router.post("/nutrient/analyze", status_code=200)
async def analyze_food_nutrition(
    request: NutrientAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Analyze nutritional content of a food item using NutrientAnalyzer AI agent.

    Requires a signed-in user: every call spends shared AI quota, so this must
    not be open to anonymous traffic.
    """
    try:
        result = nutrient_analyzer_service.analyze_food_nutrition(
            food_name=request.food_name,
            serving_size=request.serving_size
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Nutrition analysis completed successfully",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to analyze nutrition"))
            
    except Exception as e:
        logger.error(f"Error in analyze_food_nutrition endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze nutrition: {str(e)}")

@router.post("/nutrient/log-meal", status_code=201)
async def log_meal_with_analysis(
    request: MealLogRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Analyze nutrition and log meal to database using NutrientAnalyzer AI agent.
    """
    try:
        result = nutrient_analyzer_service.log_meal_with_analysis(
            food_name=request.food_name,
            serving_size=request.serving_size,
            meal_type=request.meal_type.value,
            user_id=current_user.id,
            db=db,
            nutrients=request.nutrients,
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Meal logged with nutrition analysis successfully",
                "data": result["data"]
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to log meal with analysis"))
            
    except Exception as e:
        logger.error(f"Error in log_meal_with_analysis endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to log meal: {str(e)}")

@router.post("/nutrient/barcode", status_code=200)
async def analyze_by_barcode(
    request: BarcodeRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Nutrition from a scanned packet.

    This is the only path in the app whose numbers are not an approximation:
    a barcode identifies exactly one product, and Open Food Facts returns what
    is printed on its label. No model, no matching heuristics, no guessing at
    which product was meant - which is why the UI nudges people towards it.

    Returns the same shape as /nutrient/analyze so the frontend can render
    either without branching, plus a `source` block describing where the
    numbers came from.
    """
    from app.services.food_lookup import is_valid_gtin, lookup
    from app.services.nutrient_analyzer_service import nutrient_analyzer_service

    digits = "".join(c for c in request.barcode if c.isdigit())
    if not 8 <= len(digits) <= 14:
        raise HTTPException(
            status_code=400,
            detail="That does not look like a barcode. They are 8 to 14 digits.",
        )

    facts = lookup(query="", barcode=digits)
    if not facts:
        # Two very different failures used to share one message, and the wrong
        # one was almost always shown. "Not in the database" told people their
        # perfectly ordinary packet did not exist, when the real problem was a
        # bad camera read. Say which it is, and quote the digits - so if the
        # number on screen is not the number on the box, that is visible.
        misread = not is_valid_gtin(digits)
        raise HTTPException(
            status_code=404,
            detail=(
                f"Read {digits}, but that is not a valid barcode — likely a "
                "misread. Try again, or type the number under the bars."
                if misread else
                f"Barcode {digits} is not in the food database yet. "
                "Type the food name instead and I'll estimate it."
            ),
        )

    # Label data is per 100g; scale to whatever they actually ate using the
    # same parser the estimate path uses.
    base_serving, multiplier = nutrient_analyzer_service.parse_serving(request.serving_size)
    nutrients = nutrient_analyzer_service._scale(facts.as_nutrients(), multiplier)

    name = facts.matched_name or "Scanned product"
    if facts.brand:
        name = f"{facts.brand} {name}"

    return {
        "success": True,
        "message": "Nutrition read from the product label",
        "data": {
            "food_name": name,
            "serving_size": request.serving_size,
            "parsed_nutrients": nutrients,
            "raw_analysis": (
                f"{name}\n"
                f"Values printed on the packet, per {facts.basis}:\n"
                f"  Calories      {facts.calories:.0f} kcal\n"
                f"  Protein       {facts.protein:.1f} g\n"
                f"  Carbohydrates {facts.carbohydrates:.1f} g\n"
                f"  Fat           {facts.fat:.1f} g\n"
                + (f"  Fibre         {facts.fiber:.1f} g\n" if facts.fiber else "")
                + f"\nScaled to {request.serving_size}."
            ),
            "source": facts.provenance(),
        },
    }


@router.get("/nutrient/meal-types")
async def get_meal_types():
    """Get available meal types for logging"""
    return [{"value": meal.value, "label": meal.value.replace('_', ' ').title()} for meal in MealType]

@router.get("/nutrient/health-tags")
async def get_health_tags():
    """Get available health tags for food categorization"""
    return [
        {"value": "vegetarian", "label": "Vegetarian", "emoji": "🌱"},
        {"value": "vegan", "label": "Vegan", "emoji": "🌿"},
        {"value": "meat", "label": "Contains Meat", "emoji": "🍗"},
        {"value": "fish", "label": "Contains Fish", "emoji": "🐟"},
        {"value": "gluten-free", "label": "Gluten-Free", "emoji": "🌾"},
        {"value": "dairy-free", "label": "Dairy-Free", "emoji": "🥛"},
        {"value": "nut-free", "label": "Nut-Free", "emoji": "🥜"},
        {"value": "low-carb", "label": "Low-Carb", "emoji": "🥗"},
        {"value": "high-protein", "label": "High-Protein", "emoji": "💪"},
        {"value": "organic", "label": "Organic", "emoji": "🌿"}
    ]

@router.get("/nutrient/sample-foods")
async def get_sample_foods():
    """Get sample food items for testing and suggestions"""
    return {
        "proteins": [
            {"name": "Chicken Breast", "serving": "100g"},
            {"name": "Salmon Fillet", "serving": "150g"},
            {"name": "Greek Yogurt", "serving": "1 cup"},
            {"name": "Eggs", "serving": "2 large"},
            {"name": "Tofu", "serving": "100g"}
        ],
        "carbohydrates": [
            {"name": "Brown Rice", "serving": "1 cup cooked"},
            {"name": "Quinoa", "serving": "1 cup cooked"},
            {"name": "Sweet Potato", "serving": "1 medium"},
            {"name": "Oatmeal", "serving": "1 cup cooked"},
            {"name": "Banana", "serving": "1 medium"}
        ],
        "vegetables": [
            {"name": "Broccoli", "serving": "1 cup"},
            {"name": "Spinach", "serving": "2 cups raw"},
            {"name": "Carrots", "serving": "1 cup chopped"},
            {"name": "Bell Peppers", "serving": "1 medium"},
            {"name": "Avocado", "serving": "1/2 medium"}
        ],
        "fruits": [
            {"name": "Apple", "serving": "1 medium"},
            {"name": "Blueberries", "serving": "1 cup"},
            {"name": "Orange", "serving": "1 medium"},
            {"name": "Strawberries", "serving": "1 cup"},
            {"name": "Mango", "serving": "1 cup sliced"}
        ]
    }
