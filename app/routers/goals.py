from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, User, Goal
from app.auth import get_current_active_user
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional

router = APIRouter()

class GoalCreate(BaseModel):
    goal_type: str
    target_weight: Optional[float] = None
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fat: Optional[float] = None
    target_date: Optional[date] = None

class GoalResponse(BaseModel):
    id: int
    goal_type: str
    target_weight: Optional[float]
    target_calories: Optional[float]
    target_protein: Optional[float]
    target_carbs: Optional[float]
    target_fat: Optional[float]
    start_date: datetime
    target_date: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=GoalResponse)
async def create_goal(
    goal: GoalCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new goal"""
    # Deactivate any existing active goals of the same type
    existing_goals = db.query(Goal).filter(
        Goal.user_id == current_user.id,
        Goal.goal_type == goal.goal_type,
        Goal.is_active == True
    ).all()
    
    for existing_goal in existing_goals:
        existing_goal.is_active = False
    
    # Create new goal
    db_goal = Goal(
        user_id=current_user.id,
        goal_type=goal.goal_type,
        target_weight=goal.target_weight,
        target_calories=goal.target_calories,
        target_protein=goal.target_protein,
        target_carbs=goal.target_carbs,
        target_fat=goal.target_fat,
        target_date=goal.target_date
    )
    
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    
    return db_goal

@router.get("/", response_model=List[GoalResponse])
async def get_goals(
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's goals"""
    query = db.query(Goal).filter(Goal.user_id == current_user.id)
    
    if active_only:
        query = query.filter(Goal.is_active == True)
    
    goals = query.order_by(Goal.created_at.desc()).all()
    return goals

@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific goal"""
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    return goal

@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: int,
    goal_update: GoalCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a goal"""
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Update goal fields
    update_data = goal_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(goal, field, value)
    
    db.commit()
    db.refresh(goal)
    
    return goal

@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a goal"""
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    db.delete(goal)
    db.commit()
    
    return {"message": "Goal deleted successfully"}
