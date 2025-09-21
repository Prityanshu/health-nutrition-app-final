# app/routers/enhanced_ml_router.py
"""
Enhanced ML recommendations API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from app.database import get_db, User
from app.auth import get_current_active_user
from app.services.enhanced_ml_recommendations import AdvancedUserProfiler, IntelligentRecommendationEngine
from app.services.smart_chatbot_integration import SmartChatbotIntegration
from app.database import FoodRating
from app.models.enhanced_models import UserCookingPattern, UserNutritionGoals

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/user-profile")
async def get_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive user profile with ML insights"""
    
    try:
        profiler = AdvancedUserProfiler(db)
        profile = profiler.create_comprehensive_profile(current_user.id)
        
        return {
            "success": True,
            "user_id": current_user.id,
            "profile": profile,
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user profile: {str(e)}")

@router.get("/personalized-recommendations")
async def get_personalized_recommendations(
    meal_type: Optional[str] = Query(None, description="breakfast, lunch, dinner, or snack"),
    max_recommendations: int = Query(10, ge=1, le=20, description="Maximum number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get highly personalized food and meal recommendations"""
    
    try:
        engine = IntelligentRecommendationEngine(db)
        
        context = {
            'meal_type': meal_type,
            'max_recommendations': max_recommendations,
            'current_time': datetime.now()
        }
        
        recommendations = engine.get_personalized_recommendations(current_user, context)
        
        return {
            "success": True,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat(),
            "context": context
        }
    
    except Exception as e:
        logger.error(f"Error getting personalized recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

@router.get("/smart-chatbot-response")
async def get_smart_chatbot_response(
    query: str = Query(..., description="User query for the chatbot"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chatbot response enhanced with ML recommendations"""
    
    try:
        smart_integration = SmartChatbotIntegration(db)
        
        response = smart_integration.get_smart_chatbot_response(
            user_id=current_user.id,
            user_query=query,
            context={'current_time': datetime.now()}
        )
        
        return {
            "success": True,
            "response": response,
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting smart chatbot response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get chatbot response: {str(e)}")

@router.post("/rate-food")
async def rate_food(
    food_id: int,
    rating: float = Query(..., ge=1, le=5, description="Rating from 1-5"),
    context: Optional[str] = Query(None, description="Meal context (breakfast, lunch, dinner, snack)"),
    notes: Optional[str] = Query(None, description="Optional notes about the food"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate a food item to improve recommendations"""
    
    try:
        # Check if food exists
        from app.database import FoodItem
        food_item = db.query(FoodItem).filter(FoodItem.id == food_id).first()
        if not food_item:
            raise HTTPException(status_code=404, detail="Food item not found")
        
        # Check if rating already exists
        existing_rating = db.query(FoodRating).filter(
            FoodRating.user_id == current_user.id,
            FoodRating.food_item_id == food_id
        ).first()
        
        if existing_rating:
            # Update existing rating
            existing_rating.rating = rating
            existing_rating.context = context
            existing_rating.notes = notes
            existing_rating.created_at = datetime.utcnow()
        else:
            # Create new rating
            new_rating = FoodRating(
                user_id=current_user.id,
                food_item_id=food_id,
                rating=rating,
                context=context,
                notes=notes,
                created_at=datetime.utcnow()
            )
            db.add(new_rating)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Rating of {rating} recorded for {food_item.name}",
            "food_id": food_id,
            "rating": rating,
            "context": context
        }
    
    except Exception as e:
        logger.error(f"Error rating food: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rate food: {str(e)}")

@router.post("/update-cooking-profile")
async def update_cooking_profile(
    cooking_frequency: Optional[str] = Query(None, description="daily, weekly, monthly, rarely"),
    skill_level: Optional[str] = Query(None, description="beginner, intermediate, advanced"),
    preferred_cooking_time: Optional[str] = Query(None, description="morning, afternoon, evening, night"),
    budget_range: Optional[str] = Query(None, description="low, medium, high"),
    meal_prep_preference: Optional[bool] = Query(None, description="Whether user prefers meal prep"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user's cooking profile"""
    
    try:
        # Get existing profile or create new one
        cooking_profile = db.query(UserCookingPattern).filter(
            UserCookingPattern.user_id == current_user.id
        ).first()
        
        if not cooking_profile:
            cooking_profile = UserCookingPattern(
                user_id=current_user.id,
                last_updated=datetime.utcnow()
            )
            db.add(cooking_profile)
        
        # Update fields
        if cooking_frequency:
            cooking_profile.cooking_frequency = cooking_frequency
        if skill_level:
            cooking_profile.cooking_skill_level = skill_level
        if preferred_cooking_time:
            cooking_profile.preferred_cooking_time = preferred_cooking_time
        if budget_range:
            cooking_profile.budget_range = budget_range
        if meal_prep_preference is not None:
            cooking_profile.meal_prep_preference = meal_prep_preference
        
        cooking_profile.last_updated = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": "Cooking profile updated successfully",
            "profile": {
                "cooking_frequency": cooking_profile.cooking_frequency,
                "skill_level": cooking_profile.cooking_skill_level,
                "preferred_cooking_time": cooking_profile.preferred_cooking_time,
                "budget_range": cooking_profile.budget_range,
                "meal_prep_preference": cooking_profile.meal_prep_preference
            }
        }
    
    except Exception as e:
        logger.error(f"Error updating cooking profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update cooking profile: {str(e)}")

@router.post("/set-nutrition-goals")
async def set_nutrition_goals(
    goal_type: str = Query(..., description="weight_loss, muscle_gain, maintenance, health_improvement"),
    target_calories: Optional[float] = Query(None, description="Target daily calories"),
    target_protein: Optional[float] = Query(None, description="Target daily protein (g)"),
    target_carbs: Optional[float] = Query(None, description="Target daily carbs (g)"),
    target_fat: Optional[float] = Query(None, description="Target daily fat (g)"),
    target_fiber: Optional[float] = Query(None, description="Target daily fiber (g)"),
    target_sodium: Optional[float] = Query(None, description="Target daily sodium (mg)"),
    target_sugar: Optional[float] = Query(None, description="Target daily sugar (g)"),
    target_date: Optional[datetime] = Query(None, description="Target date for goals"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Set detailed nutrition goals"""
    
    try:
        # Deactivate existing goals
        existing_goals = db.query(UserNutritionGoals).filter(
            UserNutritionGoals.user_id == current_user.id,
            UserNutritionGoals.is_active == True
        ).all()
        
        for goal in existing_goals:
            goal.is_active = False
        
        # Create new goal
        new_goal = UserNutritionGoals(
            user_id=current_user.id,
            goal_type=goal_type,
            target_calories=target_calories,
            target_protein=target_protein,
            target_carbs=target_carbs,
            target_fat=target_fat,
            target_fiber=target_fiber,
            target_sodium=target_sodium,
            target_sugar=target_sugar,
            target_date=target_date,
            is_active=True,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow()
        )
        
        db.add(new_goal)
        db.commit()
        
        return {
            "success": True,
            "message": "Nutrition goals set successfully",
            "goal": {
                "goal_type": new_goal.goal_type,
                "target_calories": new_goal.target_calories,
                "target_protein": new_goal.target_protein,
                "target_carbs": new_goal.target_carbs,
                "target_fat": new_goal.target_fat,
                "target_fiber": new_goal.target_fiber,
                "target_sodium": new_goal.target_sodium,
                "target_sugar": new_goal.target_sugar,
                "target_date": new_goal.target_date.isoformat() if new_goal.target_date else None
            }
        }
    
    except Exception as e:
        logger.error(f"Error setting nutrition goals: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set nutrition goals: {str(e)}")

@router.get("/user-insights")
async def get_user_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user insights summary for dashboard"""
    
    try:
        smart_integration = SmartChatbotIntegration(db)
        insights = smart_integration.get_user_insights_summary(current_user.id)
        
        return {
            "success": True,
            "insights": insights,
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting user insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user insights: {str(e)}")

@router.get("/recommendation-insights")
async def get_recommendation_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get insights about how recommendations are generated for the user"""
    
    try:
        profiler = AdvancedUserProfiler(db)
        profile = profiler.create_comprehensive_profile(current_user.id)
        
        insights = {
            "data_quality": {
                "preference_confidence": profile["preference_confidence"],
                "status": "excellent" if profile["preference_confidence"] > 0.8 else 
                         "good" if profile["preference_confidence"] > 0.5 else 
                         "building" if profile["preference_confidence"] > 0.2 else "insufficient",
                "recommendations": []
            },
            "behavioral_insights": {
                "meal_regularity": profile["behavioral_patterns"]["meal_regularity"],
                "cooking_frequency": profile["behavioral_patterns"]["cooking_frequency"],
                "variety_seeking": profile["behavioral_patterns"]["variety_seeking"],
                "experimentation_tendency": profile["behavioral_patterns"]["experimentation_tendency"]
            },
            "cooking_profile": {
                "skill_level": profile["cooking_profile"]["skill_level"],
                "preferred_cooking_time": profile["cooking_profile"]["preferred_cooking_time"],
                "budget_range": profile["cooking_profile"]["budget_range"],
                "meal_prep_preference": profile["cooking_profile"]["meal_prep_preference"]
            },
            "nutritional_status": {
                "current_intake": profile["nutritional_profile"]["current_intake"],
                "macro_ratios": profile["nutritional_profile"]["macro_ratios"],
                "consistency_score": profile["nutritional_profile"]["consistency_score"]
            },
            "improvement_suggestions": []
        }
        
        # Add improvement suggestions based on data quality
        if profile["preference_confidence"] < 0.3:
            insights["data_quality"]["recommendations"].append(
                "Log more meals and rate foods to get better personalized recommendations"
            )
        
        if profile["behavioral_patterns"]["variety_seeking"] < 0.4:
            insights["improvement_suggestions"].append(
                "Try different cuisines to expand your food variety and get better recommendations"
            )
        
        if profile["behavioral_patterns"]["meal_regularity"] < 0.6:
            insights["improvement_suggestions"].append(
                "Eating at more consistent times will help improve your meal recommendations"
            )
        
        return {
            "success": True,
            "insights": insights,
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting recommendation insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendation insights: {str(e)}")

@router.post("/track-chatbot-satisfaction")
async def track_chatbot_satisfaction(
    query: str,
    satisfaction: float = Query(..., ge=1, le=5, description="Satisfaction rating from 1-5"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Track user satisfaction with chatbot responses"""
    
    try:
        smart_integration = SmartChatbotIntegration(db)
        
        # This would save to ChatbotInteraction table
        # For now, we'll just log it
        smart_integration.track_user_interaction(
            user_id=current_user.id,
            query=query,
            response={"success": True},  # Placeholder
            satisfaction=satisfaction
        )
        
        return {
            "success": True,
            "message": "Satisfaction rating recorded",
            "query": query[:50] + "..." if len(query) > 50 else query,
            "satisfaction": satisfaction
        }
    
    except Exception as e:
        logger.error(f"Error tracking satisfaction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to track satisfaction: {str(e)}")
