# app/routers/enhanced_challenges_router.py
"""
Enhanced challenges API with data-driven personalization
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

from app.database import get_db, User
from app.auth import get_current_active_user
from app.services.data_driven_challenge_generator import DataDrivenChallengeGenerator
from app.models.enhanced_challenge_models import (
    PersonalizedChallenge, UserChallengeProgress, ChallengeAchievement,
    ChallengeRecommendation, ChallengeType, ChallengeDifficulty
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for requests
class UpdateProgressRequest(BaseModel):
    challenge_id: int
    daily_value: float
    progress_date: Optional[datetime] = None
    nutrition_data: Optional[Dict[str, Any]] = None
    workout_data: Optional[Dict[str, Any]] = None
    mood_data: Optional[Dict[str, Any]] = None

@router.get("/generate-weekly-challenges")
async def generate_weekly_challenges(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate personalized weekly challenges based on user data"""
    
    try:
        generator = DataDrivenChallengeGenerator(db)
        
        result = generator.generate_weekly_challenges(current_user.id)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Weekly challenges generated successfully",
                "user_analysis": result["user_analysis"],
                "recommendations": result["recommendations"],
                "active_challenges": result["active_challenges"],
                "generated_at": result["generated_at"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
    
    except Exception as e:
        logger.error(f"Error generating weekly challenges: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate challenges: {str(e)}")

@router.get("/active-challenges")
async def get_active_challenges(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's active challenges with progress"""
    
    try:
        challenges = db.query(PersonalizedChallenge).filter(
            and_(
                PersonalizedChallenge.user_id == current_user.id,
                PersonalizedChallenge.is_active == True,
                PersonalizedChallenge.end_date > datetime.utcnow()
            )
        ).all()
        
        challenge_data = []
        for challenge in challenges:
            # Get progress for this challenge
            progress = db.query(UserChallengeProgress).filter(
                UserChallengeProgress.challenge_id == challenge.id
            ).order_by(desc(UserChallengeProgress.progress_date)).all()
            
            # Calculate current progress
            total_progress = sum(p.daily_value for p in progress)
            progress_percentage = (total_progress / challenge.target_value) * 100 if challenge.target_value > 0 else 0
            
            # Calculate days remaining
            days_remaining = (challenge.end_date - datetime.utcnow()).days
            
            challenge_data.append({
                "challenge_id": challenge.id,
                "title": challenge.title,
                "description": challenge.description,
                "challenge_type": challenge.challenge_type.value,
                "difficulty": challenge.difficulty.value,
                "target_value": challenge.target_value,
                "current_value": total_progress,
                "unit": challenge.unit,
                "progress_percentage": min(100, progress_percentage),
                "days_remaining": max(0, days_remaining),
                "points_reward": challenge.points_reward,
                "badge_reward": challenge.badge_reward,
                "start_date": challenge.start_date.isoformat(),
                "end_date": challenge.end_date.isoformat(),
                "is_completed": progress_percentage >= 100,
                "daily_targets": challenge.daily_targets,
                "motivational_messages": challenge.motivational_messages
            })
        
        return {
            "success": True,
            "active_challenges": challenge_data,
            "total_challenges": len(challenge_data),
            "completed_challenges": len([c for c in challenge_data if c["is_completed"]]),
            "retrieved_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting active challenges: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get challenges: {str(e)}")

@router.post("/update-challenge-progress")
async def update_challenge_progress(
    request: UpdateProgressRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update progress for a specific challenge"""
    
    try:
        logger.info(f"Updating progress for challenge {request.challenge_id} with value {request.daily_value}")
        
        # Get the challenge
        challenge = db.query(PersonalizedChallenge).filter(
            and_(
                PersonalizedChallenge.id == request.challenge_id,
                PersonalizedChallenge.user_id == current_user.id,
                PersonalizedChallenge.is_active == True
            )
        ).first()
        
        if not challenge:
            logger.error(f"Challenge {request.challenge_id} not found for user {current_user.id}")
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Use current date if not provided
        progress_date = request.progress_date or datetime.now()
        
        # Calculate daily target
        daily_target = challenge.target_value / 7  # Assuming 7-day challenges
        
        # Check if progress already exists for this date
        existing_progress = db.query(UserChallengeProgress).filter(
            and_(
                UserChallengeProgress.challenge_id == request.challenge_id,
                func.date(UserChallengeProgress.progress_date) == progress_date.date()
            )
        ).first()
        
        if existing_progress:
            # Update existing progress
            existing_progress.daily_value = request.daily_value
            existing_progress.completion_percentage = (request.daily_value / daily_target) * 100 if daily_target > 0 else 0
            existing_progress.nutrition_data = request.nutrition_data or {}
            existing_progress.workout_data = request.workout_data or {}
            existing_progress.mood_data = request.mood_data or {}
            logger.info(f"Updated existing progress entry")
        else:
            # Create new progress entry
            progress = UserChallengeProgress(
                user_id=current_user.id,
                challenge_id=request.challenge_id,
                progress_date=progress_date,
                daily_value=request.daily_value,
                daily_target=daily_target,
                completion_percentage=(request.daily_value / daily_target) * 100 if daily_target > 0 else 0,
                nutrition_data=request.nutrition_data or {},
                workout_data=request.workout_data or {},
                mood_data=request.mood_data or {}
            )
            db.add(progress)
            logger.info(f"Created new progress entry")
        
        # Update challenge progress
        challenge.current_value += request.daily_value
        challenge.completion_percentage = (challenge.current_value / challenge.target_value) * 100 if challenge.target_value > 0 else 0
        
        # Check if challenge is completed
        if challenge.completion_percentage >= 100:
            challenge.is_active = False
            logger.info(f"Challenge {request.challenge_id} completed!")
        
        db.commit()
        logger.info(f"Successfully updated challenge {request.challenge_id}")
        
        return {
            "success": True,
            "message": "Challenge progress updated",
            "challenge_id": request.challenge_id,
            "daily_value": request.daily_value,
            "completion_percentage": challenge.completion_percentage,
            "is_completed": challenge.completion_percentage >= 100
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating challenge progress: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update progress: {str(e)}")

@router.get("/challenge-recommendations")
async def get_challenge_recommendations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get personalized challenge recommendations"""
    
    try:
        generator = DataDrivenChallengeGenerator(db)
        
        # Analyze user data
        user_analysis = generator._analyze_user_data(current_user.id)
        
        # Generate recommendations
        recommendations = generator._generate_challenge_recommendations(current_user.id, user_analysis)
        
        # Get existing recommendations
        existing_recs = db.query(ChallengeRecommendation).filter(
            and_(
                ChallengeRecommendation.user_id == current_user.id,
                ChallengeRecommendation.is_accepted == False,
                ChallengeRecommendation.is_dismissed == False,
                ChallengeRecommendation.expires_at > datetime.utcnow()
            )
        ).all()
        
        return {
            "success": True,
            "user_analysis": user_analysis,
            "recommendations": recommendations,
            "existing_recommendations": [
                {
                    "id": rec.id,
                    "challenge_type": rec.recommended_challenge_type.value,
                    "difficulty": rec.recommended_difficulty.value,
                    "confidence_score": rec.confidence_score,
                    "suggested_title": rec.suggested_title,
                    "suggested_description": rec.suggested_description,
                    "suggested_target": rec.suggested_target,
                    "suggested_duration_days": rec.suggested_duration_days,
                    "recommendation_reasons": rec.recommendation_reasons,
                    "user_weaknesses": rec.user_weaknesses,
                    "user_strengths": rec.user_strengths,
                    "expires_at": rec.expires_at.isoformat()
                }
                for rec in existing_recs
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting challenge recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

@router.post("/accept-challenge-recommendation")
async def accept_challenge_recommendation(
    recommendation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Accept a challenge recommendation and create an active challenge"""
    
    try:
        # Get the recommendation
        recommendation = db.query(ChallengeRecommendation).filter(
            and_(
                ChallengeRecommendation.id == recommendation_id,
                ChallengeRecommendation.user_id == current_user.id,
                ChallengeRecommendation.is_accepted == False,
                ChallengeRecommendation.is_dismissed == False,
                ChallengeRecommendation.expires_at > datetime.utcnow()
            )
        ).first()
        
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation not found or expired")
        
        # Create the challenge
        challenge = PersonalizedChallenge(
            user_id=current_user.id,
            challenge_type=recommendation.recommended_challenge_type,
            difficulty=recommendation.recommended_difficulty,
            title=recommendation.suggested_title,
            description=recommendation.suggested_description,
            target_value=recommendation.suggested_target,
            unit="units",  # Would be determined based on challenge type
            baseline_data=recommendation.user_weaknesses,
            target_improvement=20,  # Default 20% improvement
            personalization_factors=recommendation.recommendation_reasons,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=recommendation.suggested_duration_days),
            points_reward=100,  # Default points
            badge_reward="challenge_completer",
            motivational_messages=[
                "You've got this!",
                "Every step counts!",
                "You're making progress!"
            ],
            daily_targets=[],  # Would be calculated
            progress_history=[],
            completion_percentage=0.0
        )
        
        db.add(challenge)
        
        # Mark recommendation as accepted
        recommendation.is_accepted = True
        
        db.commit()
        
        return {
            "success": True,
            "message": "Challenge created successfully",
            "challenge_id": challenge.id,
            "title": challenge.title,
            "description": challenge.description,
            "end_date": challenge.end_date.isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error accepting challenge recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to accept recommendation: {str(e)}")

@router.post("/dismiss-challenge-recommendation")
async def dismiss_challenge_recommendation(
    recommendation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Dismiss a challenge recommendation"""
    
    try:
        recommendation = db.query(ChallengeRecommendation).filter(
            and_(
                ChallengeRecommendation.id == recommendation_id,
                ChallengeRecommendation.user_id == current_user.id,
                ChallengeRecommendation.is_accepted == False,
                ChallengeRecommendation.is_dismissed == False
            )
        ).first()
        
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        recommendation.is_dismissed = True
        db.commit()
        
        return {
            "success": True,
            "message": "Recommendation dismissed",
            "recommendation_id": recommendation_id
        }
    
    except Exception as e:
        logger.error(f"Error dismissing recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to dismiss recommendation: {str(e)}")

@router.get("/challenge-achievements")
async def get_challenge_achievements(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's challenge achievements"""
    
    try:
        achievements = db.query(ChallengeAchievement).filter(
            ChallengeAchievement.user_id == current_user.id
        ).order_by(desc(ChallengeAchievement.achieved_at)).all()
        
        achievement_data = []
        for achievement in achievements:
            achievement_data.append({
                "id": achievement.id,
                "achievement_type": achievement.achievement_type,
                "title": achievement.achievement_title,
                "description": achievement.achievement_description,
                "points_earned": achievement.points_earned,
                "badge_earned": achievement.badge_earned,
                "achievement_data": achievement.achievement_data,
                "achieved_at": achievement.achieved_at.isoformat(),
                "challenge_id": achievement.challenge_id
            })
        
        return {
            "success": True,
            "achievements": achievement_data,
            "total_achievements": len(achievement_data),
            "total_points": sum(a.points_earned for a in achievements),
            "retrieved_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting achievements: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get achievements: {str(e)}")

@router.get("/challenge-analytics")
async def get_challenge_analytics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get analytics about user's challenge performance"""
    
    try:
        # Get all challenges for user
        all_challenges = db.query(PersonalizedChallenge).filter(
            PersonalizedChallenge.user_id == current_user.id
        ).all()
        
        # Get progress data
        all_progress = db.query(UserChallengeProgress).filter(
            UserChallengeProgress.user_id == current_user.id
        ).all()
        
        # Calculate analytics
        total_challenges = len(all_challenges)
        completed_challenges = len([c for c in all_challenges if c.completion_percentage >= 100])
        completion_rate = (completed_challenges / total_challenges) * 100 if total_challenges > 0 else 0
        
        # Calculate average completion percentage
        avg_completion = sum(c.completion_percentage for c in all_challenges) / total_challenges if total_challenges > 0 else 0
        
        # Calculate streak data
        current_streak = 0
        longest_streak = 0
        temp_streak = 0
        
        for progress in sorted(all_progress, key=lambda x: x.progress_date):
            if progress.completion_percentage >= 100:
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 0
        
        current_streak = temp_streak
        
        # Calculate points earned
        total_points = sum(c.points_reward for c in all_challenges if c.completion_percentage >= 100)
        
        # Calculate badges earned
        badges_earned = len(set(a.badge_earned for a in all_challenges if a.badge_reward))
        
        return {
            "success": True,
            "analytics": {
                "total_challenges": total_challenges,
                "completed_challenges": completed_challenges,
                "completion_rate": completion_rate,
                "average_completion_percentage": avg_completion,
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "total_points_earned": total_points,
                "badges_earned": badges_earned,
                "total_progress_entries": len(all_progress)
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting challenge analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@router.get("/challenge-leaderboard")
async def get_challenge_leaderboard(
    challenge_type: Optional[str] = Query(None, description="Filter by challenge type"),
    limit: int = Query(10, ge=1, le=50, description="Number of users to return"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get challenge leaderboard (simplified for small userbase)"""
    
    try:
        # For small userbase, we'll show all users
        # In a larger system, you'd implement proper leaderboard logic
        
        # Get all users with their challenge performance
        users = db.query(User).all()
        
        leaderboard = []
        for user in users:
            user_challenges = db.query(PersonalizedChallenge).filter(
                PersonalizedChallenge.user_id == user.id
            ).all()
            
            if user_challenges:
                completed = len([c for c in user_challenges if c.completion_percentage >= 100])
                total_points = sum(c.points_reward for c in user_challenges if c.completion_percentage >= 100)
                avg_completion = sum(c.completion_percentage for c in user_challenges) / len(user_challenges)
                
                leaderboard.append({
                    "user_id": user.id,
                    "username": user.username,
                    "total_challenges": len(user_challenges),
                    "completed_challenges": completed,
                    "total_points": total_points,
                    "average_completion": avg_completion,
                    "completion_rate": (completed / len(user_challenges)) * 100 if user_challenges else 0
                })
        
        # Sort by total points
        leaderboard.sort(key=lambda x: x["total_points"], reverse=True)
        
        return {
            "success": True,
            "leaderboard": leaderboard[:limit],
            "current_user_rank": next(
                (i + 1 for i, user in enumerate(leaderboard) if user["user_id"] == current_user.id), 
                None
            ),
            "total_users": len(leaderboard),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get leaderboard: {str(e)}")
