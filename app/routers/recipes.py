from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db, User, FoodItem
from app.auth import get_current_active_user
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class RecipeRequest(BaseModel):
    cuisine_type: str
    meal_type: str
    max_prep_time: int = 30  # minutes
    dietary_restrictions: List[str] = []

class RecipeResponse(BaseModel):
    name: str
    cuisine_type: str
    prep_time: int
    ingredients: List[Dict[str, Any]]
    instructions: List[str]
    nutrition: Dict[str, float]

@router.post("/generate", response_model=RecipeResponse)
async def generate_recipe(
    recipe_request: RecipeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate a recipe based on preferences"""
    # Simple recipe generation - in a real app, this would use ML/AI
    food_items = db.query(FoodItem).filter(
        FoodItem.cuisine_type == recipe_request.cuisine_type
    ).limit(5).all()
    
    if not food_items:
        # Fallback to any food items
        food_items = db.query(FoodItem).limit(5).all()
    
    # Create a simple recipe
    recipe_name = f"{recipe_request.cuisine_type.title()} {recipe_request.meal_type.title()}"
    
    ingredients = []
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    for i, item in enumerate(food_items[:3]):  # Use first 3 items
        quantity = 1.0 if i == 0 else 0.5  # Main ingredient gets full portion
        ingredients.append({
            "name": item.name,
            "quantity": quantity,
            "unit": "serving",
            "calories": item.calories * quantity,
            "protein": item.protein_g * quantity,
            "carbs": item.carbs_g * quantity,
            "fat": item.fat_g * quantity
        })
        
        total_calories += item.calories * quantity
        total_protein += item.protein_g * quantity
        total_carbs += item.carbs_g * quantity
        total_fat += item.fat_g * quantity
    
    # Simple cooking instructions
    instructions = [
        f"Prepare all ingredients for {recipe_name.lower()}",
        "Heat a pan over medium heat",
        "Add main ingredients and cook for 10-15 minutes",
        "Season to taste and serve hot"
    ]
    
    return RecipeResponse(
        name=recipe_name,
        cuisine_type=recipe_request.cuisine_type,
        prep_time=recipe_request.max_prep_time,
        ingredients=ingredients,
        instructions=instructions,
        nutrition={
            "calories": total_calories,
            "protein": total_protein,
            "carbs": total_carbs,
            "fat": total_fat
        }
    )

@router.get("/cuisines")
async def get_available_cuisines(db: Session = Depends(get_db)):
    """Get available cuisine types"""
    cuisines = db.query(FoodItem.cuisine_type).distinct().all()
    return [cuisine[0] for cuisine in cuisines if cuisine[0]]

@router.get("/meal-types")
async def get_meal_types():
    """Get available meal types"""
    return ["breakfast", "lunch", "dinner", "snack"]
