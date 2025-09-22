# app/routers/social_cooking_router.py
"""
API endpoints for social cooking data and family preferences
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.auth import get_current_active_user
from app.services.social_cooking_service import SocialCookingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social-cooking", tags=["social-cooking"])

@router.post("/profile")
async def update_social_cooking_profile(
    family_size: Optional[int] = Body(None, ge=1, le=20, description="Number of family members"),
    cooking_for_others: Optional[bool] = Body(None, description="Whether user cooks for others"),
    family_dietary_restrictions: Optional[List[str]] = Body(None, description="Family dietary restrictions"),
    social_meal_preferences: Optional[Dict[str, Any]] = Body(None, description="Social meal preferences"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user's social cooking profile"""
    try:
        service = SocialCookingService(db)
        result = service.update_social_cooking_profile(
            current_user.id,
            family_size,
            cooking_for_others,
            family_dietary_restrictions,
            social_meal_preferences
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in update_social_cooking_profile endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")

@router.get("/profile")
async def get_social_cooking_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's social cooking profile"""
    try:
        service = SocialCookingService(db)
        result = service.get_social_cooking_profile(current_user.id)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_social_cooking_profile endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")

@router.get("/family-recommendations")
async def get_family_friendly_recommendations(
    limit: int = Query(10, ge=1, le=20, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get family-friendly food and recipe recommendations"""
    try:
        service = SocialCookingService(db)
        recommendations = service.get_family_friendly_recommendations(current_user.id, limit)
        
        return {
            "success": True,
            "recommendations": recommendations,
            "total_count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error in get_family_friendly_recommendations endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

@router.get("/family-patterns")
async def get_family_eating_patterns(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Analyze family eating patterns for better recommendations"""
    try:
        service = SocialCookingService(db)
        patterns = service.analyze_family_eating_patterns(current_user.id)
        
        if "error" in patterns:
            raise HTTPException(status_code=400, detail=patterns["error"])
        
        return {
            "success": True,
            "patterns": patterns
        }
        
    except Exception as e:
        logger.error(f"Error in get_family_eating_patterns endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze patterns: {str(e)}")

@router.get("/shared-recipe-suggestions")
async def get_shared_recipe_suggestions(
    occasion: str = Query("family_dinner", description="Occasion for shared cooking"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get recipe suggestions for sharing with family/friends"""
    try:
        service = SocialCookingService(db)
        suggestions = service.get_shared_recipe_suggestions(current_user.id, occasion)
        
        return {
            "success": True,
            "suggestions": suggestions,
            "occasion": occasion,
            "total_count": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Error in get_shared_recipe_suggestions endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")

@router.post("/track-shared-experience")
async def track_shared_cooking_experience(
    recipe_id: int = Body(..., description="Recipe ID"),
    family_feedback: Dict[str, Any] = Body(..., description="Family feedback on the cooking experience"),
    occasion: str = Body("family_meal", description="Occasion for the shared cooking"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Track shared cooking experiences and family feedback"""
    try:
        service = SocialCookingService(db)
        result = service.track_shared_cooking_experience(
            current_user.id,
            recipe_id,
            family_feedback,
            occasion
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in track_shared_cooking_experience endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to track experience: {str(e)}")

@router.get("/cooking-insights")
async def get_social_cooking_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive social cooking insights"""
    try:
        service = SocialCookingService(db)
        
        # Get profile
        profile_result = service.get_social_cooking_profile(current_user.id)
        profile = profile_result.get("profile", {}) if profile_result["success"] else {}
        
        # Get family patterns
        patterns = service.analyze_family_eating_patterns(current_user.id)
        
        # Get recommendations
        recommendations = service.get_family_friendly_recommendations(current_user.id, 5)
        
        insights = {
            "profile": profile,
            "eating_patterns": patterns,
            "sample_recommendations": recommendations,
            "cooking_for_family": profile.get("cooking_for_others", False),
            "family_size": profile.get("family_size", 1)
        }
        
        return {
            "success": True,
            "insights": insights
        }
        
    except Exception as e:
        logger.error(f"Error in get_social_cooking_insights endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")

@router.post("/quick-profile-setup")
async def quick_profile_setup(
    family_size: int = Body(..., ge=1, le=20, description="Number of family members"),
    cooking_for_family: bool = Body(..., description="Do you cook for your family?"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Quick setup for social cooking profile"""
    try:
        service = SocialCookingService(db)
        
        # Set up basic profile
        result = service.update_social_cooking_profile(
            current_user.id,
            family_size=family_size,
            cooking_for_others=cooking_for_family
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "message": "Social cooking profile set up successfully",
            "profile": result["profile"]
        }
        
    except Exception as e:
        logger.error(f"Error in quick_profile_setup endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to setup profile: {str(e)}")
