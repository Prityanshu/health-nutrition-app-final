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
    """Generate a recipe based on preferences using MyFitnessPal data"""
    # Enhanced recipe generation with MyFitnessPal data
    query = db.query(FoodItem)
    
    # Filter by cuisine type
    if recipe_request.cuisine_type and recipe_request.cuisine_type != "mixed":
        query = query.filter(FoodItem.cuisine_type == recipe_request.cuisine_type)
    
    # Filter out very high calorie items for better recipes
    query = query.filter(FoodItem.calories <= 600)
    
    # Filter out items with very high sodium
    query = query.filter(FoodItem.sodium_mg <= 600)
    
    # Order by calories for balanced recipes
    query = query.order_by(FoodItem.calories)
    
    food_items = query.limit(10).all()
    
    if not food_items:
        # Fallback to any food items with filters
        fallback_query = db.query(FoodItem).filter(
            FoodItem.calories <= 600,
            FoodItem.sodium_mg <= 600
        ).limit(10)
        food_items = fallback_query.all()
    
    # Create a more sophisticated recipe
    recipe_name = f"{recipe_request.cuisine_type.title()} {recipe_request.meal_type.title()}"
    
    ingredients = []
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    # Select ingredients based on meal type and nutritional balance
    selected_items = food_items[:4]  # Use up to 4 items
    
    for i, item in enumerate(selected_items):
        # Adjust quantities based on meal type and item position
        if recipe_request.meal_type == "breakfast":
            quantity = 1.0 if i == 0 else 0.3  # Smaller portions for breakfast
        elif recipe_request.meal_type == "lunch":
            quantity = 1.0 if i == 0 else 0.5  # Medium portions for lunch
        else:  # dinner or snack
            quantity = 1.0 if i == 0 else 0.7  # Larger portions for dinner
        
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
    
    # Enhanced cooking instructions based on cuisine type
    instructions = _generate_cooking_instructions(recipe_request.cuisine_type, recipe_name)
    
    return RecipeResponse(
        name=recipe_name,
        cuisine_type=recipe_request.cuisine_type,
        prep_time=recipe_request.max_prep_time,
        ingredients=ingredients,
        instructions=instructions,
        nutrition={
            "calories": round(total_calories, 1),
            "protein": round(total_protein, 1),
            "carbs": round(total_carbs, 1),
            "fat": round(total_fat, 1)
        }
    )

def _generate_cooking_instructions(cuisine_type: str, recipe_name: str) -> List[str]:
    """Generate cooking instructions based on cuisine type"""
    base_instructions = [
        f"Prepare all ingredients for {recipe_name.lower()}",
        "Wash and prepare fresh ingredients",
        "Heat cooking oil in a pan over medium heat"
    ]
    
    if cuisine_type == "italian":
        base_instructions.extend([
            "Add aromatics and cook until fragrant",
            "Add main ingredients and simmer for 15-20 minutes",
            "Season with herbs and serve with fresh bread"
        ])
    elif cuisine_type == "chinese":
        base_instructions.extend([
            "Stir-fry ingredients in hot oil for 3-5 minutes",
            "Add sauce and toss to combine",
            "Serve immediately over rice or noodles"
        ])
    elif cuisine_type == "mexican":
        base_instructions.extend([
            "Sauté ingredients with spices for 5-7 minutes",
            "Add liquid and simmer for 10-15 minutes",
            "Garnish with fresh cilantro and serve with tortillas"
        ])
    elif cuisine_type == "indian":
        base_instructions.extend([
            "Toast spices in hot oil until fragrant",
            "Add main ingredients and cook for 10-15 minutes",
            "Finish with fresh herbs and serve with rice or bread"
        ])
    else:  # mixed or other
        base_instructions.extend([
            "Cook main ingredients for 10-15 minutes",
            "Season to taste and adjust flavors",
            "Serve hot and enjoy"
        ])
    
    return base_instructions

@router.get("/cuisines")
async def get_available_cuisines(db: Session = Depends(get_db)):
    """Get available cuisine types"""
    cuisines = db.query(FoodItem.cuisine_type).distinct().all()
    return [cuisine[0] for cuisine in cuisines if cuisine[0]]

@router.get("/meal-types")
async def get_meal_types():
    """Get available meal types"""
    return ["breakfast", "lunch", "dinner", "snack"]
