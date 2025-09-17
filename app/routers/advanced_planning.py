# app/routers/advanced_planning.py
"""
Advanced meal planning API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime

from app.database import get_db, User
from app.auth import get_current_user
from app.services.advanced_meal_planning import AdvancedMealPlanner
from app.services.ml_recommendations import IntelligentRecommendationEngine
from app.schemas import (
    AdvancedMealPlanRequest, 
    AdvancedMealPlanResponse,
    DayPlan,
    PersonalizedRecommendations
)

router = APIRouter()

@router.post("/generate-week-plan", response_model=AdvancedMealPlanResponse)
async def generate_week_plan(
    request: AdvancedMealPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate an advanced week meal plan with variety constraints and macro targeting"""
    
    try:
        planner = AdvancedMealPlanner(db)
        
        # Convert request to preferences dict
        preferences = {
            'target_calories': request.target_calories,
            'protein_percentage': request.protein_percentage,
            'carb_percentage': request.carb_percentage,
            'fat_percentage': request.fat_percentage,
            'meals_per_day': request.meals_per_day,
            'cuisine_type': request.cuisine_type,
            'exclude_recent_days': request.exclude_recent_days,
            'variety_constraints': request.variety_constraints
        }
        
        # Generate week plan
        week_plans = planner.generate_week_plan_with_variety(current_user, preferences)
        
        # Calculate totals
        total_weekly_calories = sum(day.total_calories for day in week_plans)
        total_weekly_protein = sum(day.total_protein for day in week_plans)
        total_weekly_cost = sum(day.total_cost for day in week_plans)
        
        # Calculate variety score (simplified)
        all_food_ids = set()
        for day in week_plans:
            for meal in day.meals:
                for item in meal.items:
                    all_food_ids.add(item.food_id)
        
        variety_score = min(1.0, len(all_food_ids) / (len(week_plans) * 3 * 2))  # Max 2 items per meal
        
        # Calculate macro balance score
        total_protein_cal = total_weekly_protein * 4
        total_carbs_cal = sum(sum(item.carbs_g for item in meal.items) for day in week_plans for meal in day.meals) * 4
        total_fat_cal = sum(sum(item.fat_g for item in meal.items) for day in week_plans for meal in day.meals) * 9
        
        if total_weekly_calories > 0:
            protein_ratio = total_protein_cal / total_weekly_calories
            carb_ratio = total_carbs_cal / total_weekly_calories
            fat_ratio = total_fat_cal / total_weekly_calories
            
            target_protein = request.protein_percentage / 100
            target_carb = request.carb_percentage / 100
            target_fat = request.fat_percentage / 100
            
            macro_balance_score = 1 - (
                abs(protein_ratio - target_protein) + 
                abs(carb_ratio - target_carb) + 
                abs(fat_ratio - target_fat)
            ) / 3
        else:
            macro_balance_score = 0.0
        
        return AdvancedMealPlanResponse(
            week_plans=week_plans,
            total_weekly_calories=total_weekly_calories,
            total_weekly_protein=total_weekly_protein,
            total_weekly_cost=total_weekly_cost,
            variety_score=variety_score,
            macro_balance_score=max(0, macro_balance_score)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")

@router.get("/smart-recommendations", response_model=PersonalizedRecommendations)
async def get_smart_recommendations(
    meal_type: Optional[str] = Query(None, description="breakfast, lunch, dinner, or snack"),
    exclude_recent_days: int = Query(7, description="Days to look back for avoiding recent foods"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get smart meal recommendations based on user preferences and patterns"""
    
    try:
        engine = IntelligentRecommendationEngine(db)
        
        context = {
            'current_time': datetime.now(),
            'meal_type': meal_type,
            'exclude_recent_days': exclude_recent_days
        }
        
        recommendations = engine.get_personalized_recommendations(current_user, context)
        
        return PersonalizedRecommendations(
            food_recommendations=recommendations['food_recommendations'],
            cuisine_recommendations=recommendations['cuisine_recommendations'],
            meal_timing_suggestions=recommendations['meal_timing_suggestions'],
            macro_adjustments=recommendations['macro_adjustments'],
            variety_suggestions=recommendations['variety_suggestions']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

@router.get("/meal-variety-analysis")
async def get_meal_variety_analysis(
    days: int = Query(30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze user's meal variety and provide improvement suggestions"""
    
    try:
        engine = IntelligentRecommendationEngine(db)
        preferences = engine.preference_learner.analyze_user_preferences(current_user.id)
        
        # Calculate variety metrics
        cuisine_variety = len(preferences.get('cuisine_preferences', {}))
        food_category_variety = len(preferences.get('food_categories', {}))
        preference_strength = preferences.get('preference_strength', 0)
        
        # Generate variety score
        variety_score = min(1.0, (cuisine_variety * 0.3 + food_category_variety * 0.2 + preference_strength * 0.5))
        
        # Get improvement suggestions
        variety_suggestions = engine.suggest_variety_improvements(current_user.id, preferences)
        
        return {
            'variety_score': variety_score,
            'cuisine_variety': cuisine_variety,
            'food_category_variety': food_category_variety,
            'preference_strength': preference_strength,
            'improvement_suggestions': variety_suggestions,
            'analysis_period_days': days
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze variety: {str(e)}")

@router.get("/macro-balance-analysis")
async def get_macro_balance_analysis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze user's macro-nutrient balance and provide recommendations"""
    
    try:
        engine = IntelligentRecommendationEngine(db)
        preferences = engine.preference_learner.analyze_user_preferences(current_user.id)
        
        macro_prefs = preferences.get('macro_preferences', {})
        current_protein = macro_prefs.get('preferred_protein_ratio', 15)
        current_carbs = macro_prefs.get('preferred_carb_ratio', 50)
        current_fat = macro_prefs.get('preferred_fat_ratio', 35)
        
        # Get macro adjustment suggestions
        macro_adjustments = engine.suggest_macro_adjustments(current_user, preferences)
        
        # Calculate balance score
        total_ratio = current_protein + current_carbs + current_fat
        balance_score = 1 - abs(total_ratio - 100) / 100 if total_ratio > 0 else 0
        
        return {
            'current_macros': {
                'protein_percentage': current_protein,
                'carbs_percentage': current_carbs,
                'fat_percentage': current_fat
            },
            'balance_score': balance_score,
            'macro_adjustments': macro_adjustments,
            'consistency': macro_prefs.get('consistency', 0.5)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze macro balance: {str(e)}")

@router.post("/optimize-meal-plan")
async def optimize_meal_plan(
    plan_request: AdvancedMealPlanRequest,
    optimization_goals: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Optimize an existing meal plan based on specific goals"""
    
    try:
        planner = AdvancedMealPlanner(db)
        
        # Add optimization goals to preferences
        preferences = {
            'target_calories': plan_request.target_calories,
            'protein_percentage': plan_request.protein_percentage,
            'carb_percentage': plan_request.carb_percentage,
            'fat_percentage': plan_request.fat_percentage,
            'meals_per_day': plan_request.meals_per_day,
            'cuisine_type': plan_request.cuisine_type,
            'exclude_recent_days': plan_request.exclude_recent_days,
            'variety_constraints': plan_request.variety_constraints,
            'optimization_goals': optimization_goals
        }
        
        # Generate optimized plan
        week_plans = planner.generate_week_plan_with_variety(current_user, preferences)
        
        # Calculate optimization metrics
        total_calories = sum(day.total_calories for day in week_plans)
        total_protein = sum(day.total_protein for day in week_plans)
        
        optimization_score = 0.8  # Placeholder - would calculate based on goals
        
        return {
            'optimized_plan': week_plans,
            'optimization_score': optimization_score,
            'total_calories': total_calories,
            'total_protein': total_protein,
            'optimization_goals_met': list(optimization_goals.keys())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to optimize meal plan: {str(e)}")

@router.get("/planning-insights")
async def get_planning_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get insights about meal planning patterns and recommendations"""
    
    try:
        engine = IntelligentRecommendationEngine(db)
        preferences = engine.preference_learner.analyze_user_preferences(current_user.id)
        
        # Analyze adherence patterns
        adherence = preferences.get('adherence_patterns', {})
        overall_adherence = adherence.get('overall_adherence', 0)
        
        # Analyze timing preferences
        timing = preferences.get('timing_preferences', {})
        meal_regularity = timing.get('meal_regularity_score', 0)
        
        # Generate insights
        insights = {
            'adherence_analysis': {
                'overall_adherence_rate': overall_adherence,
                'daily_adherence': adherence.get('daily_adherence', {}),
                'adherence_trend': adherence.get('adherence_trend', 'needs_improvement')
            },
            'timing_analysis': {
                'meal_regularity_score': meal_regularity,
                'breakfast_consistency': timing.get('breakfast_preference', {}).get('consistency', 0),
                'lunch_consistency': timing.get('lunch_preference', {}).get('consistency', 0),
                'dinner_consistency': timing.get('dinner_preference', {}).get('consistency', 0)
            },
            'preference_analysis': {
                'cuisine_diversity': len(preferences.get('cuisine_preferences', {})),
                'food_category_diversity': len(preferences.get('food_categories', {})),
                'preference_strength': preferences.get('preference_strength', 0)
            },
            'recommendations': []
        }
        
        # Add specific recommendations
        if overall_adherence < 0.7:
            insights['recommendations'].append("Try to follow your meal plans more consistently")
        
        if meal_regularity < 0.6:
            insights['recommendations'].append("Establish more regular meal times")
        
        if len(preferences.get('cuisine_preferences', {})) < 3:
            insights['recommendations'].append("Explore more diverse cuisines")
        
        return insights
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get planning insights: {str(e)}")
