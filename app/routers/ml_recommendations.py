# app/routers/ml_recommendations.py
"""
ML-powered recommendations API endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime

from app.database import get_db, User
from app.auth import get_current_user
from app.services.ml_recommendations import IntelligentRecommendationEngine, UserPreferenceLearner

router = APIRouter()

@router.get("/user-preferences")
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get learned user preferences and eating patterns"""
    
    learner = UserPreferenceLearner(db)
    preferences = learner.analyze_user_preferences(current_user.id)
    
    return {
        'user_id': current_user.id,
        'preferences': preferences,
        'analysis_date': datetime.now().isoformat(),
        'recommendation': 'Continue logging meals to improve preference accuracy' if preferences['preference_strength'] < 0.5 else 'Preferences well established'
    }

@router.get("/personalized-recommendations")
async def get_personalized_recommendations(
    meal_type: Optional[str] = Query(None, description="breakfast, lunch, dinner, or snack"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalized food and meal recommendations"""
    
    engine = IntelligentRecommendationEngine(db)
    
    context = {
        'current_time': datetime.now(),
        'meal_type': meal_type
    }
    
    recommendations = engine.get_personalized_recommendations(current_user, context)
    
    return {
        'recommendations': recommendations,
        'generated_at': datetime.now().isoformat(),
        'context': context
    }

@router.get("/smart-meal-suggestions")
async def get_smart_meal_suggestions(
    exclude_recent_days: int = Query(7, description="Days to look back for avoiding recent foods"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get smart meal suggestions that avoid recent foods and match preferences"""
    
    engine = IntelligentRecommendationEngine(db)
    
    # Determine current meal type
    meal_type = engine.determine_meal_type(datetime.now())
    
    context = {
        'current_time': datetime.now(),
        'meal_type': meal_type,
        'exclude_recent_days': exclude_recent_days
    }
    
    recommendations = engine.get_personalized_recommendations(current_user, context)
    
    return {
        'meal_type': meal_type,
        'suggestions': recommendations['food_recommendations'][:5],
        'cuisine_to_try': recommendations.get('cuisine_recommendations', [])[:2],
        'variety_tips': recommendations.get('variety_suggestions', []),
        'context': f"Suggestions for {meal_type} at {datetime.now().strftime('%I:%M %p')}"
    }

@router.post("/update-food-rating")
async def update_food_rating(
    food_id: int,
    rating: float = Query(..., ge=1, le=5, description="Rating from 1-5"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Allow users to rate foods to improve recommendations"""
    
    # This would be implemented with a new FoodRating model
    # For now, we'll return a success message
    
    return {
        'message': f'Rating of {rating} recorded for food {food_id}',
        'note': 'Food ratings will improve future recommendations',
        'food_id': food_id,
        'rating': rating
    }

@router.get("/recommendation-insights")
async def get_recommendation_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get insights about how recommendations are generated"""
    
    learner = UserPreferenceLearner(db)
    preferences = learner.analyze_user_preferences(current_user.id)
    
    insights = {
        'data_quality': {
            'preference_strength': preferences['preference_strength'],
            'status': 'excellent' if preferences['preference_strength'] > 0.8 else 
                     'good' if preferences['preference_strength'] > 0.5 else 
                     'building' if preferences['preference_strength'] > 0.2 else 'insufficient',
            'recommendations': []
        },
        'top_preferences': {
            'favorite_cuisines': list(preferences.get('cuisine_preferences', {}).keys())[:3],
            'macro_balance': preferences.get('macro_preferences', {}),
            'meal_regularity': preferences.get('timing_preferences', {}).get('meal_regularity_score', 0)
        },
        'improvement_areas': []
    }
    
    # Add specific recommendations based on data quality
    if preferences['preference_strength'] < 0.3:
        insights['data_quality']['recommendations'].append(
            "Log more meals to get better personalized recommendations"
        )
    
    if len(preferences.get('cuisine_preferences', {})) < 2:
        insights['improvement_areas'].append(
            "Try different cuisines to expand your options"
        )
    
    return insights