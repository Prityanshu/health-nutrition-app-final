from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db, User, FoodItem, MealLog
from app.auth import get_current_active_user
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

router = APIRouter()

class MealLogRequest(BaseModel):
    food_item_id: int
    meal_type: str
    quantity: float = 1.0

class MealLogResponse(BaseModel):
    id: int
    food_item: dict
    meal_type: str
    quantity: float
    calories: float
    protein: float
    carbs: float
    fat: float
    logged_at: datetime

    class Config:
        from_attributes = True

@router.post("/log", response_model=MealLogResponse)
async def log_meal(
    meal_log: MealLogRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Log a meal"""
    # Get the food item
    food_item = db.query(FoodItem).filter(FoodItem.id == meal_log.food_item_id).first()
    if not food_item:
        raise HTTPException(status_code=404, detail="Food item not found")
    
    # Calculate nutritional values based on quantity
    calories = food_item.calories * meal_log.quantity
    protein = food_item.protein_g * meal_log.quantity
    carbs = food_item.carbs_g * meal_log.quantity
    fat = food_item.fat_g * meal_log.quantity
    
    # Create meal log entry
    meal_log_entry = MealLog(
        user_id=current_user.id,
        food_item_id=meal_log.food_item_id,
        meal_type=meal_log.meal_type,
        quantity=meal_log.quantity,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat
    )
    
    db.add(meal_log_entry)
    db.commit()
    db.refresh(meal_log_entry)
    
    return MealLogResponse(
        id=meal_log_entry.id,
        food_item={
            "id": food_item.id,
            "name": food_item.name,
            "cuisine_type": food_item.cuisine_type
        },
        meal_type=meal_log_entry.meal_type,
        quantity=meal_log_entry.quantity,
        calories=meal_log_entry.calories,
        protein=meal_log_entry.protein,
        carbs=meal_log_entry.carbs,
        fat=meal_log_entry.fat,
        logged_at=meal_log_entry.logged_at
    )

@router.get("/history", response_model=List[MealLogResponse])
async def get_meal_history(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get meal logging history"""
    meal_logs = db.query(MealLog).filter(
        MealLog.user_id == current_user.id
    ).order_by(MealLog.logged_at.desc()).limit(limit).all()
    
    result = []
    for log in meal_logs:
        food_item = db.query(FoodItem).filter(FoodItem.id == log.food_item_id).first()
        result.append(MealLogResponse(
            id=log.id,
            food_item={
                "id": food_item.id,
                "name": food_item.name,
                "cuisine_type": food_item.cuisine_type
            },
            meal_type=log.meal_type,
            quantity=log.quantity,
            calories=log.calories,
            protein=log.protein,
            carbs=log.carbs,
            fat=log.fat,
            logged_at=log.logged_at
        ))
    
    return result

@router.get("/food-items", response_model=List[dict])
async def get_food_items(
    search: Optional[str] = None,
    cuisine_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get food items with enhanced search functionality using MyFitnessPal data"""
    query = db.query(FoodItem)
    
    if search:
        # Simple search - search in name only for now
        search_term = f"%{search.lower()}%"
        query = query.filter(FoodItem.name.ilike(search_term))
    
    if cuisine_type and cuisine_type != "mixed":
        query = query.filter(FoodItem.cuisine_type == cuisine_type)
    
    # Filter out very high calorie items for better food selection
    query = query.filter(FoodItem.calories <= 1000)
    
    # Filter out items with very high sodium
    query = query.filter(FoodItem.sodium_mg <= 1000)
    
    # Order by relevance and name for better search results
    if search:
        # If searching, order by name length (shorter names first) then by name
        query = query.order_by(db.func.length(FoodItem.name), FoodItem.name)
    else:
        # If not searching, order by name
        query = query.order_by(FoodItem.name)
    
    food_items = query.limit(limit).all()
    
    return [
        {
            "id": item.id,
            "name": item.name,
            "cuisine_type": item.cuisine_type,
            "calories": item.calories,
            "protein_g": item.protein_g,
            "carbs_g": item.carbs_g,
            "fat_g": item.fat_g,
            "fiber_g": item.fiber_g,
            "sodium_mg": item.sodium_mg,
            "tags": item.tags
        }
        for item in food_items
    ]

@router.get("/food-items/search", response_model=List[dict])
async def search_food_items(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """Simple food search that works reliably"""
    if len(q.strip()) < 2:
        return []
    
    try:
        # Simple search in name only
        search_term = f"%{q.lower()}%"
        food_items = db.query(FoodItem).filter(
            FoodItem.name.ilike(search_term)
        ).filter(
            FoodItem.calories <= 1000
        ).order_by(
            FoodItem.name
        ).limit(limit).all()
        
        return [
            {
                "id": item.id,
                "name": item.name,
                "cuisine_type": item.cuisine_type,
                "calories": item.calories,
                "protein_g": item.protein_g,
                "carbs_g": item.carbs_g,
                "fat_g": item.fat_g,
                "fiber_g": item.fiber_g,
                "sodium_mg": item.sodium_mg,
                "tags": item.tags or "",
                "ingredients": item.ingredients or ""
            }
            for item in food_items
        ]
    except Exception as e:
        print(f"Search error: {e}")
        return []
