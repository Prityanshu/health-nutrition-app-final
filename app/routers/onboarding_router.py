# app/routers/onboarding_router.py
"""
Enhanced user onboarding system for better data collection
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import logging

from app.database import get_db, User
from app.auth import get_current_active_user
from app.services.enhanced_data_collection import EnhancedDataCollector

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for onboarding
class OnboardingRequest(BaseModel):
    dietary_preferences: Optional[Dict[str, Any]] = {}
    cuisine_preference: Optional[str] = "mixed"
    cooking_frequency: Optional[str] = "moderate"
    preferred_cooking_time: Optional[str] = "evening"
    cooking_skill_level: Optional[str] = "intermediate"
    preferred_cuisines: Optional[List[str]] = ["mixed"]
    dietary_restrictions: Optional[Dict[str, bool]] = {}
    budget_range: Optional[str] = "medium"
    meal_prep_preference: Optional[bool] = False
    nutrition_goals: Optional[Dict[str, Any]] = {}
    social_cooking: Optional[Dict[str, Any]] = {}

class FoodInteractionRequest(BaseModel):
    food_id: int
    interaction_type: str  # viewed, cooked, rated, saved, shared, feedback
    context: Optional[Dict[str, Any]] = {}
    satisfaction: Optional[float] = None

class FeedbackRequest(BaseModel):
    feedback_type: str  # recommendation_feedback, chatbot_feedback, general_feedback
    feedback_data: Dict[str, Any]

@router.post("/complete-onboarding")
async def complete_onboarding(
    onboarding_data: OnboardingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Complete comprehensive user onboarding"""
    
    try:
        collector = EnhancedDataCollector(db)
        
        result = collector.collect_user_onboarding_data(
            user_id=current_user.id,
            onboarding_data=onboarding_data.dict()
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Onboarding completed successfully",
                "user_id": current_user.id,
                "data_points_collected": result["data_points_collected"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
    
    except Exception as e:
        logger.error(f"Error in onboarding: {e}")
        raise HTTPException(status_code=500, detail=f"Onboarding failed: {str(e)}")

@router.post("/track-food-interaction")
async def track_food_interaction(
    interaction_data: FoodInteractionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Track detailed food interactions"""
    
    try:
        collector = EnhancedDataCollector(db)
        
        result = collector.track_food_interaction(
            user_id=current_user.id,
            food_id=interaction_data.food_id,
            interaction_type=interaction_data.interaction_type,
            context=interaction_data.context,
            satisfaction=interaction_data.satisfaction
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Food interaction tracked",
                "new_preference_score": result["new_preference_score"],
                "interaction_count": result["interaction_count"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
    
    except Exception as e:
        logger.error(f"Error tracking food interaction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to track interaction: {str(e)}")

@router.post("/submit-feedback")
async def submit_feedback(
    feedback_data: FeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit user feedback for system improvement"""
    
    try:
        collector = EnhancedDataCollector(db)
        
        result = collector.collect_user_feedback(
            user_id=current_user.id,
            feedback_type=feedback_data.feedback_type,
            feedback_data=feedback_data.feedback_data
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Feedback submitted successfully",
                "feedback_type": feedback_data.feedback_type
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
    
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")

@router.get("/data-quality-score")
async def get_data_quality_score(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's data quality score and recommendations"""
    
    try:
        collector = EnhancedDataCollector(db)
        
        result = collector.get_user_data_quality_score(current_user.id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "user_id": current_user.id,
            "data_quality": result
        }
    
    except Exception as e:
        logger.error(f"Error getting data quality score: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get data quality score: {str(e)}")

@router.get("/onboarding-checklist")
async def get_onboarding_checklist(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get personalized onboarding checklist for user"""
    
    try:
        collector = EnhancedDataCollector(db)
        
        # Get current data quality
        data_quality = collector.get_user_data_quality_score(current_user.id)
        
        # Create personalized checklist
        checklist = []
        
        if data_quality["breakdown"]["basic_profile"] < 0.8:
            checklist.append({
                "item": "Complete your basic profile",
                "description": "Add age, weight, height, and activity level",
                "priority": "high",
                "completed": data_quality["breakdown"]["basic_profile"] > 0.5
            })
        
        if data_quality["breakdown"]["cooking_profile"] < 1.0:
            checklist.append({
                "item": "Set up your cooking preferences",
                "description": "Tell us about your cooking skills and preferences",
                "priority": "high",
                "completed": data_quality["breakdown"]["cooking_profile"] > 0.5
            })
        
        if data_quality["breakdown"]["nutrition_goals"] < 1.0:
            checklist.append({
                "item": "Set your nutrition goals",
                "description": "Define your health and fitness objectives",
                "priority": "medium",
                "completed": data_quality["breakdown"]["nutrition_goals"] > 0.5
            })
        
        if data_quality["data_points"]["meals_logged"] < 10:
            checklist.append({
                "item": "Log your first 10 meals",
                "description": "Start logging meals to get personalized recommendations",
                "priority": "high",
                "completed": data_quality["data_points"]["meals_logged"] >= 10
            })
        
        if data_quality["data_points"]["foods_rated"] < 5:
            checklist.append({
                "item": "Rate 5 foods you've tried",
                "description": "Rate foods to help us understand your preferences",
                "priority": "medium",
                "completed": data_quality["data_points"]["foods_rated"] >= 5
            })
        
        if data_quality["data_points"]["chatbot_interactions"] < 3:
            checklist.append({
                "item": "Try the AI chatbot",
                "description": "Ask the chatbot for personalized food suggestions",
                "priority": "low",
                "completed": data_quality["data_points"]["chatbot_interactions"] >= 3
            })
        
        return {
            "success": True,
            "user_id": current_user.id,
            "overall_progress": data_quality["overall_score"],
            "checklist": checklist,
            "recommendations": data_quality["recommendations"]
        }
    
    except Exception as e:
        logger.error(f"Error getting onboarding checklist: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get checklist: {str(e)}")

@router.get("/quick-setup-questions")
async def get_quick_setup_questions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get quick setup questions for new users"""
    
    questions = [
        {
            "id": "cooking_frequency",
            "question": "How often do you cook?",
            "type": "single_choice",
            "options": [
                {"value": "daily", "label": "Daily"},
                {"value": "weekly", "label": "A few times a week"},
                {"value": "monthly", "label": "A few times a month"},
                {"value": "rarely", "label": "Rarely"}
            ],
            "required": True
        },
        {
            "id": "cooking_skill",
            "question": "What's your cooking skill level?",
            "type": "single_choice",
            "options": [
                {"value": "beginner", "label": "Beginner - I'm learning"},
                {"value": "intermediate", "label": "Intermediate - I can follow recipes"},
                {"value": "advanced", "label": "Advanced - I can create my own dishes"}
            ],
            "required": True
        },
        {
            "id": "preferred_cuisines",
            "question": "What cuisines do you enjoy? (Select all that apply)",
            "type": "multiple_choice",
            "options": [
                {"value": "indian", "label": "Indian"},
                {"value": "italian", "label": "Italian"},
                {"value": "chinese", "label": "Chinese"},
                {"value": "mexican", "label": "Mexican"},
                {"value": "mediterranean", "label": "Mediterranean"},
                {"value": "japanese", "label": "Japanese"},
                {"value": "thai", "label": "Thai"},
                {"value": "american", "label": "American"},
                {"value": "mixed", "label": "I like variety"}
            ],
            "required": True
        },
        {
            "id": "dietary_restrictions",
            "question": "Do you have any dietary restrictions? (Select all that apply)",
            "type": "multiple_choice",
            "options": [
                {"value": "vegetarian", "label": "Vegetarian"},
                {"value": "vegan", "label": "Vegan"},
                {"value": "gluten_free", "label": "Gluten-free"},
                {"value": "dairy_free", "label": "Dairy-free"},
                {"value": "keto", "label": "Keto"},
                {"value": "paleo", "label": "Paleo"},
                {"value": "none", "label": "None"}
            ],
            "required": False
        },
        {
            "id": "budget_range",
            "question": "What's your typical food budget per meal?",
            "type": "single_choice",
            "options": [
                {"value": "low", "label": "Under $5"},
                {"value": "medium", "label": "$5-15"},
                {"value": "high", "label": "$15+"}
            ],
            "required": True
        },
        {
            "id": "nutrition_goals",
            "question": "What are your main nutrition goals?",
            "type": "multiple_choice",
            "options": [
                {"value": "weight_loss", "label": "Weight loss"},
                {"value": "muscle_gain", "label": "Muscle gain"},
                {"value": "maintenance", "label": "Weight maintenance"},
                {"value": "health_improvement", "label": "General health improvement"},
                {"value": "energy", "label": "More energy"},
                {"value": "none", "label": "No specific goals"}
            ],
            "required": False
        }
    ]
    
    return {
        "success": True,
        "questions": questions,
        "total_questions": len(questions)
    }
