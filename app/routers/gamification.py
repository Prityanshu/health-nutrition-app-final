from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, User, Challenge, Achievement
from app.auth import get_current_active_user
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any
import json

router = APIRouter()

class ChallengeResponse(BaseModel):
    id: int
    name: str
    description: str
    rules: Dict[str, Any]
    reward_points: int
    active_from: datetime
    active_to: datetime
    is_active: bool

    class Config:
        from_attributes = True

class AchievementResponse(BaseModel):
    id: int
    challenge: ChallengeResponse
    points_earned: int
    completed_at: datetime

    class Config:
        from_attributes = True

class UserStats(BaseModel):
    total_points: int
    completed_challenges: int
    current_streak: int
    achievements: List[AchievementResponse]

@router.get("/challenges", response_model=List[ChallengeResponse])
async def get_challenges(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get available challenges"""
    query = db.query(Challenge)
    
    if active_only:
        query = query.filter(Challenge.is_active == True)
    
    challenges = query.order_by(Challenge.created_at.desc()).all()
    
    # Parse rules JSON strings and create proper response objects
    result = []
    for challenge in challenges:
        try:
            rules_dict = json.loads(challenge.rules) if challenge.rules else {}
        except (json.JSONDecodeError, TypeError):
            rules_dict = {}
        
        result.append(ChallengeResponse(
            id=challenge.id,
            name=challenge.name,
            description=challenge.description,
            rules=rules_dict,
            reward_points=challenge.reward_points,
            active_from=challenge.active_from,
            active_to=challenge.active_to,
            is_active=challenge.is_active
        ))
    
    return result

@router.get("/achievements", response_model=List[AchievementResponse])
async def get_user_achievements(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's achievements"""
    achievements = db.query(Achievement).filter(
        Achievement.user_id == current_user.id
    ).order_by(Achievement.completed_at.desc()).all()
    
    result = []
    for achievement in achievements:
        challenge = db.query(Challenge).filter(
            Challenge.id == achievement.challenge_id
        ).first()
        
        # Parse rules JSON string
        try:
            rules_dict = json.loads(challenge.rules) if challenge.rules else {}
        except (json.JSONDecodeError, TypeError):
            rules_dict = {}
        
        result.append(AchievementResponse(
            id=achievement.id,
            challenge=ChallengeResponse(
                id=challenge.id,
                name=challenge.name,
                description=challenge.description,
                rules=rules_dict,
                reward_points=challenge.reward_points,
                active_from=challenge.active_from,
                active_to=challenge.active_to,
                is_active=challenge.is_active
            ),
            points_earned=achievement.points_earned,
            completed_at=achievement.completed_at
        ))
    
    return result

@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's gamification statistics"""
    achievements = db.query(Achievement).filter(
        Achievement.user_id == current_user.id
    ).all()
    
    total_points = sum(achievement.points_earned for achievement in achievements)
    completed_challenges = len(achievements)
    
    # Calculate current streak (simplified - in real app, this would be more sophisticated)
    current_streak = 0
    if achievements:
        # Simple streak calculation based on recent achievements
        recent_achievements = sorted(achievements, key=lambda x: x.completed_at, reverse=True)
        current_streak = min(7, len(recent_achievements))  # Simplified
    
    # Get achievement details
    achievement_responses = []
    for achievement in achievements:
        challenge = db.query(Challenge).filter(
            Challenge.id == achievement.challenge_id
        ).first()
        
        # Parse rules JSON string
        try:
            rules_dict = json.loads(challenge.rules) if challenge.rules else {}
        except (json.JSONDecodeError, TypeError):
            rules_dict = {}
        
        achievement_responses.append(AchievementResponse(
            id=achievement.id,
            challenge=ChallengeResponse(
                id=challenge.id,
                name=challenge.name,
                description=challenge.description,
                rules=rules_dict,
                reward_points=challenge.reward_points,
                active_from=challenge.active_from,
                active_to=challenge.active_to,
                is_active=challenge.is_active
            ),
            points_earned=achievement.points_earned,
            completed_at=achievement.completed_at
        ))
    
    return UserStats(
        total_points=total_points,
        completed_challenges=completed_challenges,
        current_streak=current_streak,
        achievements=achievement_responses
    )

@router.post("/complete-challenge/{challenge_id}")
async def complete_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark a challenge as completed (simplified implementation)"""
    challenge = db.query(Challenge).filter(
        Challenge.id == challenge_id,
        Challenge.is_active == True
    ).first()
    
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Check if already completed
    existing_achievement = db.query(Achievement).filter(
        Achievement.user_id == current_user.id,
        Achievement.challenge_id == challenge_id
    ).first()
    
    if existing_achievement:
        return {"message": "Challenge already completed"}
    
    # Create achievement
    achievement = Achievement(
        user_id=current_user.id,
        challenge_id=challenge_id,
        points_earned=challenge.reward_points
    )
    
    db.add(achievement)
    db.commit()
    
    return {
        "message": "Challenge completed!",
        "points_earned": challenge.reward_points
    }