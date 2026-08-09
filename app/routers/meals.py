from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db, User, FoodItem, MealLog
from app.auth import get_current_active_user
from app.services.automatic_challenge_updater import automatic_challenge_updater
from app.services import points_engine
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

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
    # How many points that log just earned. Optional so the /history endpoint,
    # which does not compute them, keeps validating.
    points_earned: int = 0

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
    
    # Automatically update smart challenges
    try:
        challenge_update_result = await automatic_challenge_updater.update_challenges_on_meal_log(
            user_id=current_user.id,
            meal_log=meal_log_entry,
            food_item=food_item,
            db=db
        )
        if challenge_update_result.get('success'):
            logger.info(f"Automatically updated {challenge_update_result.get('count', 0)} challenges")
    except Exception as e:
        logger.error(f"Error auto-updating challenges: {e}")
        # Don't fail the meal logging if challenge update fails

    # Points. Awarded here so they accrue as you log rather than only when the
    # profile is opened - a total that jumps when you visit a screen reads as
    # broken. Idempotent, so the extra call on every meal costs nothing.
    points_earned = 0
    try:
        before = points_engine.total_points(db, current_user.id)
        points_engine.sync(db, current_user, days=1)
        points_earned = points_engine.total_points(db, current_user.id) - before
    except Exception as e:
        logger.error(f"Error awarding points: {e}")
        db.rollback()

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
        logged_at=meal_log_entry.logged_at,
        points_earned=points_earned,
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
    
    # One query for every food referenced, instead of one per log row.
    food_ids = {log.food_item_id for log in meal_logs}
    foods = {
        f.id: f for f in db.query(FoodItem).filter(FoodItem.id.in_(food_ids)).all()
    } if food_ids else {}

    result = []
    for log in meal_logs:
        food_item = foods.get(log.food_item_id)
        result.append(MealLogResponse(
            id=log.id,
            # A log can outlive the food item it points at. Returning a
            # placeholder keeps the rest of the history readable; the previous
            # code raised AttributeError on None and took the whole endpoint
            # down with it.
            food_item={
                "id": log.food_item_id,
                "name": food_item.name if food_item else "Unknown food",
                "cuisine_type": food_item.cuisine_type if food_item else None,
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
