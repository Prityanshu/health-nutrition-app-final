from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db, User
from app.auth import get_current_active_user
from pydantic import BaseModel

router = APIRouter()

class UserUpdate(BaseModel):
    full_name: str = None
    age: int = None
    weight: float = None
    height: float = None
    activity_level: str = None
    health_conditions: str = None
    dietary_preferences: str = None

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_active_user)):
    """Get user profile"""
    return current_user

@router.put("/profile")
async def update_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    return current_user
