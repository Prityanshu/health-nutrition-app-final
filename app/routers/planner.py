from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, User, FoodItem, MealPlan
from app.auth import get_current_active_user
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional

router = APIRouter()

class MealPlanRequest(BaseModel):
    plan_date: date
    meal_type: str
    food_item_id: int
    quantity: float = 1.0

class MealPlanResponse(BaseModel):
    id: int
    plan_date: datetime
    meal_type: str
    food_item: dict
    quantity: float
    calories: float
    protein: float
    carbs: float
    fat: float

    class Config:
        from_attributes = True

@router.post("/generate", response_model=List[MealPlanResponse])
async def generate_meal_plan(
    target_date: date,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate a meal plan for a specific date"""
    # Simple meal plan generation - in a real app, this would be more sophisticated
    meal_types = ["breakfast", "lunch", "dinner", "snack"]
    meal_plans = []
    
    for meal_type in meal_types:
        # Get a random food item for each meal type
        food_item = db.query(FoodItem).first()
        if food_item:
            meal_plan = MealPlan(
                user_id=current_user.id,
                plan_date=datetime.combine(target_date, datetime.min.time()),
                meal_type=meal_type,
                food_item_id=food_item.id,
                quantity=1.0,
                calories=food_item.calories,
                protein=food_item.protein_g,
                carbs=food_item.carbs_g,
                fat=food_item.fat_g
            )
            db.add(meal_plan)
            meal_plans.append(meal_plan)
    
    db.commit()
    
    # Return the created meal plans
    result = []
    for plan in meal_plans:
        food_item = db.query(FoodItem).filter(FoodItem.id == plan.food_item_id).first()
        result.append(MealPlanResponse(
            id=plan.id,
            plan_date=plan.plan_date,
            meal_type=plan.meal_type,
            food_item={
                "id": food_item.id,
                "name": food_item.name,
                "cuisine_type": food_item.cuisine_type
            },
            quantity=plan.quantity,
            calories=plan.calories,
            protein=plan.protein,
            carbs=plan.carbs,
            fat=plan.fat
        ))
    
    return result

@router.get("/{target_date}", response_model=List[MealPlanResponse])
async def get_meal_plan(
    target_date: date,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get meal plan for a specific date"""
    meal_plans = db.query(MealPlan).filter(
        MealPlan.user_id == current_user.id,
        MealPlan.plan_date == datetime.combine(target_date, datetime.min.time())
    ).all()
    
    result = []
    for plan in meal_plans:
        food_item = db.query(FoodItem).filter(FoodItem.id == plan.food_item_id).first()
        result.append(MealPlanResponse(
            id=plan.id,
            plan_date=plan.plan_date,
            meal_type=plan.meal_type,
            food_item={
                "id": food_item.id,
                "name": food_item.name,
                "cuisine_type": food_item.cuisine_type
            },
            quantity=plan.quantity,
            calories=plan.calories,
            protein=plan.protein,
            carbs=plan.carbs,
            fat=plan.fat
        ))
    
    return result
