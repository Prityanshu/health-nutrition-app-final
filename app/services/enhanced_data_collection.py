# app/services/enhanced_data_collection.py
"""
Enhanced data collection system for better user profiling
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import User, FoodItem, MealLog, FoodRating, Goal
from app.models.enhanced_models import (
    UserCookingPattern, UserNutritionGoals, FoodPreferenceLearning,
    ChatbotInteraction, SeasonalPreference, SocialCookingData
)

logger = logging.getLogger(__name__)

class EnhancedDataCollector:
    """Enhanced data collection for better user profiling"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def collect_user_onboarding_data(self, user_id: int, onboarding_data: Dict) -> Dict:
        """Collect comprehensive onboarding data from new users"""
        
        try:
            # Update basic user preferences
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Update dietary preferences
            if 'dietary_preferences' in onboarding_data:
                user.dietary_preferences = json.dumps(onboarding_data['dietary_preferences'])
            
            # Update cuisine preference
            if 'cuisine_preference' in onboarding_data:
                user.cuisine_pref = onboarding_data['cuisine_preference']
            
            # Create cooking pattern
            cooking_pattern = UserCookingPattern(
                user_id=user_id,
                cooking_frequency=onboarding_data.get('cooking_frequency', 'moderate'),
                preferred_cooking_time=onboarding_data.get('preferred_cooking_time', 'evening'),
                cooking_skill_level=onboarding_data.get('cooking_skill_level', 'intermediate'),
                preferred_cuisines=onboarding_data.get('preferred_cuisines', ['mixed']),
                dietary_restrictions=onboarding_data.get('dietary_restrictions', {}),
                budget_range=onboarding_data.get('budget_range', 'medium'),
                meal_prep_preference=onboarding_data.get('meal_prep_preference', False),
                last_updated=datetime.utcnow()
            )
            
            # Check if pattern already exists
            existing_pattern = self.db.query(UserCookingPattern).filter(
                UserCookingPattern.user_id == user_id
            ).first()
            
            if existing_pattern:
                # Update existing pattern
                for key, value in onboarding_data.items():
                    if hasattr(existing_pattern, key):
                        setattr(existing_pattern, key, value)
                existing_pattern.last_updated = datetime.utcnow()
            else:
                self.db.add(cooking_pattern)
            
            # Create nutrition goals if provided
            if 'nutrition_goals' in onboarding_data:
                goals_data = onboarding_data['nutrition_goals']
                nutrition_goal = UserNutritionGoals(
                    user_id=user_id,
                    goal_type=goals_data.get('goal_type', 'maintenance'),
                    target_calories=goals_data.get('target_calories'),
                    target_protein=goals_data.get('target_protein'),
                    target_carbs=goals_data.get('target_carbs'),
                    target_fat=goals_data.get('target_fat'),
                    target_fiber=goals_data.get('target_fiber'),
                    target_sodium=goals_data.get('target_sodium'),
                    target_sugar=goals_data.get('target_sugar'),
                    start_date=datetime.utcnow(),
                    target_date=datetime.utcnow() + timedelta(days=90),
                    is_active=True,
                    last_updated=datetime.utcnow()
                )
                self.db.add(nutrition_goal)
            
            # Create social cooking data if provided
            if 'social_cooking' in onboarding_data:
                social_data = onboarding_data['social_cooking']
                social_cooking = SocialCookingData(
                    user_id=user_id,
                    cooking_for_others=social_data.get('cooking_for_others', False),
                    family_size=social_data.get('family_size', 1),
                    dietary_restrictions_family=social_data.get('family_dietary_restrictions', []),
                    social_meal_preferences=social_data.get('social_meal_preferences', {}),
                    shared_recipe_preferences=social_data.get('shared_recipe_preferences', {}),
                    last_updated=datetime.utcnow()
                )
                self.db.add(social_cooking)
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Onboarding data collected successfully",
                "data_points_collected": len(onboarding_data)
            }
            
        except Exception as e:
            logger.error(f"Error collecting onboarding data: {e}")
            return {"success": False, "error": str(e)}
    
    def track_food_interaction(self, user_id: int, food_id: int, interaction_type: str, 
                             context: Dict = None, satisfaction: float = None) -> Dict:
        """Track detailed food interactions for better recommendations"""
        
        try:
            # Get or create food preference learning record
            preference_record = self.db.query(FoodPreferenceLearning).filter(
                and_(
                    FoodPreferenceLearning.user_id == user_id,
                    FoodPreferenceLearning.food_item_id == food_id
                )
            ).first()
            
            if not preference_record:
                preference_record = FoodPreferenceLearning(
                    user_id=user_id,
                    food_item_id=food_id,
                    preference_score=0.5,  # Default neutral score
                    context_preferences={},
                    seasonal_preferences={},
                    mood_preferences={},
                    last_interaction=datetime.utcnow(),
                    interaction_count=0
                )
                self.db.add(preference_record)
            
            # Update interaction count
            preference_record.interaction_count += 1
            preference_record.last_interaction = datetime.utcnow()
            
            # Update preference score based on interaction type
            score_adjustment = self._calculate_score_adjustment(interaction_type, satisfaction)
            preference_record.preference_score = max(0, min(1, 
                preference_record.preference_score + score_adjustment
            ))
            
            # Update context preferences
            if context:
                context_key = f"{context.get('meal_type', 'unknown')}_{context.get('time_of_day', 'unknown')}"
                if context_key not in preference_record.context_preferences:
                    preference_record.context_preferences[context_key] = 0
                preference_record.context_preferences[context_key] += 1
            
            # Update seasonal preferences
            current_season = self._get_current_season()
            if current_season not in preference_record.seasonal_preferences:
                preference_record.seasonal_preferences[current_season] = 0
            preference_record.seasonal_preferences[current_season] += 1
            
            self.db.commit()
            
            return {
                "success": True,
                "message": f"Food interaction tracked: {interaction_type}",
                "new_preference_score": preference_record.preference_score,
                "interaction_count": preference_record.interaction_count
            }
            
        except Exception as e:
            logger.error(f"Error tracking food interaction: {e}")
            return {"success": False, "error": str(e)}
    
    def track_chatbot_interaction(self, user_id: int, query: str, agent_used: str, 
                                response_type: str, satisfaction: float = None, 
                                context_data: Dict = None) -> Dict:
        """Track chatbot interactions for learning"""
        
        try:
            interaction = ChatbotInteraction(
                user_id=user_id,
                query=query,
                agent_used=agent_used,
                response_type=response_type,
                user_satisfaction=satisfaction,
                context_data=context_data or {},
                created_at=datetime.utcnow()
            )
            
            self.db.add(interaction)
            self.db.commit()
            
            return {
                "success": True,
                "message": "Chatbot interaction tracked",
                "interaction_id": interaction.id
            }
            
        except Exception as e:
            logger.error(f"Error tracking chatbot interaction: {e}")
            return {"success": False, "error": str(e)}
    
    def collect_user_feedback(self, user_id: int, feedback_type: str, 
                            feedback_data: Dict) -> Dict:
        """Collect user feedback for system improvement"""
        
        try:
            # Store feedback in appropriate table based on type
            if feedback_type == "recommendation_feedback":
                # Update food preference learning based on feedback
                food_id = feedback_data.get('food_id')
                rating = feedback_data.get('rating', 3.0)
                
                if food_id:
                    self.track_food_interaction(
                        user_id=user_id,
                        food_id=food_id,
                        interaction_type="feedback",
                        satisfaction=rating
                    )
            
            elif feedback_type == "chatbot_feedback":
                # Update chatbot interaction
                query = feedback_data.get('query', '')
                agent_used = feedback_data.get('agent_used', 'unknown')
                satisfaction = feedback_data.get('satisfaction', 3.0)
                
                self.track_chatbot_interaction(
                    user_id=user_id,
                    query=query,
                    agent_used=agent_used,
                    response_type="feedback",
                    satisfaction=satisfaction
                )
            
            elif feedback_type == "general_feedback":
                # Store general feedback (could be in a new table)
                logger.info(f"General feedback from user {user_id}: {feedback_data}")
            
            return {
                "success": True,
                "message": f"Feedback collected: {feedback_type}",
                "feedback_data": feedback_data
            }
            
        except Exception as e:
            logger.error(f"Error collecting feedback: {e}")
            return {"success": False, "error": str(e)}
    
    def get_user_data_quality_score(self, user_id: int) -> Dict:
        """Calculate data quality score for user"""
        
        try:
            # Get user data points
            meal_count = self.db.query(MealLog).filter(MealLog.user_id == user_id).count()
            rating_count = self.db.query(FoodRating).filter(FoodRating.user_id == user_id).count()
            interaction_count = self.db.query(ChatbotInteraction).filter(
                ChatbotInteraction.user_id == user_id
            ).count()
            
            # Get user profile completeness
            user = self.db.query(User).filter(User.id == user_id).first()
            cooking_pattern = self.db.query(UserCookingPattern).filter(
                UserCookingPattern.user_id == user_id
            ).first()
            nutrition_goals = self.db.query(UserNutritionGoals).filter(
                UserNutritionGoals.user_id == user_id,
                UserNutritionGoals.is_active == True
            ).first()
            
            # Calculate completeness scores
            basic_profile_score = self._calculate_basic_profile_completeness(user)
            cooking_profile_score = 1.0 if cooking_pattern else 0.0
            nutrition_goals_score = 1.0 if nutrition_goals else 0.0
            
            # Calculate interaction scores
            meal_interaction_score = min(1.0, meal_count / 30)  # 30 meals = full score
            rating_interaction_score = min(1.0, rating_count / 20)  # 20 ratings = full score
            chatbot_interaction_score = min(1.0, interaction_count / 10)  # 10 interactions = full score
            
            # Overall data quality score
            overall_score = (
                basic_profile_score * 0.2 +
                cooking_profile_score * 0.2 +
                nutrition_goals_score * 0.2 +
                meal_interaction_score * 0.2 +
                rating_interaction_score * 0.1 +
                chatbot_interaction_score * 0.1
            )
            
            return {
                "overall_score": overall_score,
                "breakdown": {
                    "basic_profile": basic_profile_score,
                    "cooking_profile": cooking_profile_score,
                    "nutrition_goals": nutrition_goals_score,
                    "meal_interactions": meal_interaction_score,
                    "rating_interactions": rating_interaction_score,
                    "chatbot_interactions": chatbot_interaction_score
                },
                "data_points": {
                    "meals_logged": meal_count,
                    "foods_rated": rating_count,
                    "chatbot_interactions": interaction_count
                },
                "recommendations": self._get_data_quality_recommendations(overall_score, {
                    "meal_count": meal_count,
                    "rating_count": rating_count,
                    "interaction_count": interaction_count
                })
            }
            
        except Exception as e:
            logger.error(f"Error calculating data quality score: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_score_adjustment(self, interaction_type: str, satisfaction: float = None) -> float:
        """Calculate score adjustment based on interaction type and satisfaction"""
        
        base_adjustments = {
            "viewed": 0.01,
            "cooked": 0.05,
            "rated": 0.03,
            "saved": 0.04,
            "shared": 0.06,
            "feedback": 0.02
        }
        
        base_adjustment = base_adjustments.get(interaction_type, 0.01)
        
        if satisfaction is not None:
            # Adjust based on satisfaction (1-5 scale)
            satisfaction_multiplier = (satisfaction - 3) / 2  # -1 to 1
            return base_adjustment * (1 + satisfaction_multiplier)
        
        return base_adjustment
    
    def _get_current_season(self) -> str:
        """Get current season based on date"""
        month = datetime.now().month
        if month in [12, 1, 2]:
            return 'winter'
        elif month in [3, 4, 5]:
            return 'spring'
        elif month in [6, 7, 8]:
            return 'summer'
        else:
            return 'fall'
    
    def _calculate_basic_profile_completeness(self, user: User) -> float:
        """Calculate how complete the basic user profile is"""
        
        if not user:
            return 0.0
        
        required_fields = ['age', 'weight', 'height', 'activity_level']
        optional_fields = ['health_conditions', 'dietary_preferences', 'cuisine_pref']
        
        required_score = sum(1 for field in required_fields if getattr(user, field) is not None) / len(required_fields)
        optional_score = sum(1 for field in optional_fields if getattr(user, field) is not None) / len(optional_fields)
        
        return (required_score * 0.7) + (optional_score * 0.3)
    
    def _get_data_quality_recommendations(self, overall_score: float, data_points: Dict) -> List[str]:
        """Get recommendations for improving data quality"""
        
        recommendations = []
        
        if overall_score < 0.3:
            recommendations.append("Complete your user profile for better recommendations")
            recommendations.append("Start logging meals regularly")
        
        if data_points['meal_count'] < 10:
            recommendations.append("Log more meals to improve food recommendations")
        
        if data_points['rating_count'] < 5:
            recommendations.append("Rate foods you've tried to help the system learn your preferences")
        
        if data_points['interaction_count'] < 3:
            recommendations.append("Try using the chatbot to get personalized suggestions")
        
        if overall_score > 0.8:
            recommendations.append("Great! Your profile is comprehensive and will provide excellent recommendations")
        
        return recommendations
