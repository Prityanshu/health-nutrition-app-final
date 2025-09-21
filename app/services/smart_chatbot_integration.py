# app/services/smart_chatbot_integration.py
"""
Smart integration of ML recommendations with chatbot responses
"""
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging

from app.database import User, FoodItem, MealLog
from app.services.enhanced_ml_recommendations import AdvancedUserProfiler, IntelligentRecommendationEngine
from app.services.chatbot_manager import ChatbotManager

logger = logging.getLogger(__name__)

class SmartChatbotIntegration:
    """Integrates ML recommendations with chatbot responses for better personalization"""
    
    def __init__(self, db: Session):
        self.db = db
        self.profiler = AdvancedUserProfiler(db)
        self.recommendation_engine = IntelligentRecommendationEngine(db)
        self.chatbot_manager = ChatbotManager()
    
    def get_smart_chatbot_response(self, user_id: int, user_query: str, context: Dict = None) -> Dict[str, Any]:
        """Get chatbot response enhanced with ML recommendations"""
        
        # Get user profile
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        # Get comprehensive user profile
        user_profile = self.profiler.create_comprehensive_profile(user_id)
        
        # Get ML recommendations
        ml_recommendations = self.recommendation_engine.get_personalized_recommendations(user, context)
        
        # Enhance chatbot context with ML data
        enhanced_context = self._enhance_chatbot_context(user_profile, ml_recommendations, context)
        
        # Get chatbot response
        chatbot_response = self.chatbot_manager.handle_query(user_id, user_query, self.db)
        
        # Enhance response with ML insights
        enhanced_response = self._enhance_response_with_ml_insights(
            chatbot_response, user_profile, ml_recommendations, user_query
        )
        
        return enhanced_response
    
    def _enhance_chatbot_context(self, user_profile: Dict, ml_recommendations: Dict, context: Dict = None) -> Dict:
        """Enhance chatbot context with ML insights"""
        
        enhanced_context = context or {}
        
        # Add user preferences
        enhanced_context['user_preferences'] = {
            'cuisine_preferences': user_profile['basic_preferences']['cuisine_preferences'],
            'cooking_profile': user_profile['cooking_profile'],
            'nutritional_goals': user_profile['nutritional_profile'].get('goals'),
            'behavioral_patterns': user_profile['behavioral_patterns']
        }
        
        # Add ML recommendations
        enhanced_context['ml_recommendations'] = {
            'food_recommendations': ml_recommendations['food_recommendations'][:5],
            'cuisine_suggestions': ml_recommendations['cuisine_suggestions'][:3],
            'meal_planning_insights': ml_recommendations['meal_planning_insights'],
            'nutritional_guidance': ml_recommendations['nutritional_guidance']
        }
        
        # Add personalization confidence
        enhanced_context['personalization_confidence'] = user_profile['preference_confidence']
        
        return enhanced_context
    
    def _enhance_response_with_ml_insights(self, chatbot_response: Dict, user_profile: Dict, 
                                         ml_recommendations: Dict, user_query: str) -> Dict:
        """Enhance chatbot response with ML insights and recommendations"""
        
        if not chatbot_response.get('success', False):
            return chatbot_response
        
        # Get the base response
        base_response = chatbot_response['response']
        
        # Determine if we should add ML insights
        should_add_insights = self._should_add_ml_insights(user_query, user_profile)
        
        if not should_add_insights:
            return chatbot_response
        
        # Add ML insights based on query type
        enhanced_response = chatbot_response.copy()
        
        if self._is_food_recommendation_query(user_query):
            enhanced_response['ml_insights'] = self._get_food_recommendation_insights(ml_recommendations)
        
        elif self._is_meal_planning_query(user_query):
            enhanced_response['ml_insights'] = self._get_meal_planning_insights(ml_recommendations)
        
        elif self._is_nutrition_query(user_query):
            enhanced_response['ml_insights'] = self._get_nutrition_insights(ml_recommendations)
        
        elif self._is_cuisine_query(user_query):
            enhanced_response['ml_insights'] = self._get_cuisine_insights(ml_recommendations)
        
        # Add personalized suggestions
        enhanced_response['personalized_suggestions'] = self._get_personalized_suggestions(
            user_profile, ml_recommendations, user_query
        )
        
        return enhanced_response
    
    def _should_add_ml_insights(self, user_query: str, user_profile: Dict) -> bool:
        """Determine if ML insights should be added based on query and user profile"""
        
        # Don't add insights if user profile is too weak
        if user_profile['preference_confidence'] < 0.3:
            return False
        
        # Add insights for food-related queries
        food_keywords = ['food', 'meal', 'recipe', 'cook', 'eat', 'dinner', 'lunch', 'breakfast', 'snack']
        if any(keyword in user_query.lower() for keyword in food_keywords):
            return True
        
        # Add insights for planning queries
        planning_keywords = ['plan', 'schedule', 'weekly', 'daily', 'menu']
        if any(keyword in user_query.lower() for keyword in planning_keywords):
            return True
        
        # Add insights for nutrition queries
        nutrition_keywords = ['nutrition', 'calories', 'protein', 'carbs', 'fat', 'healthy']
        if any(keyword in user_query.lower() for keyword in nutrition_keywords):
            return True
        
        return False
    
    def _is_food_recommendation_query(self, user_query: str) -> bool:
        """Check if query is asking for food recommendations"""
        recommendation_keywords = ['recommend', 'suggest', 'what should i eat', 'what to cook', 'food ideas']
        return any(keyword in user_query.lower() for keyword in recommendation_keywords)
    
    def _is_meal_planning_query(self, user_query: str) -> bool:
        """Check if query is about meal planning"""
        planning_keywords = ['meal plan', 'weekly plan', 'menu', 'schedule', 'plan meals']
        return any(keyword in user_query.lower() for keyword in planning_keywords)
    
    def _is_nutrition_query(self, user_query: str) -> bool:
        """Check if query is about nutrition"""
        nutrition_keywords = ['nutrition', 'calories', 'protein', 'carbs', 'fat', 'healthy', 'diet']
        return any(keyword in user_query.lower() for keyword in nutrition_keywords)
    
    def _is_cuisine_query(self, user_query: str) -> bool:
        """Check if query is about cuisines"""
        cuisine_keywords = ['cuisine', 'regional', 'kerala', 'punjab', 'italian', 'chinese', 'mexican', 'mediterranean']
        return any(keyword in user_query.lower() for keyword in cuisine_keywords)
    
    def _get_food_recommendation_insights(self, ml_recommendations: Dict) -> Dict:
        """Get food recommendation insights"""
        
        food_recs = ml_recommendations['food_recommendations'][:3]
        
        return {
            'type': 'food_recommendations',
            'title': '🍽️ Personalized Food Recommendations',
            'recommendations': [
                {
                    'name': rec['name'],
                    'cuisine': rec['cuisine_type'],
                    'calories': rec['calories'],
                    'protein': rec['protein_g'],
                    'reasons': rec['recommendation_reasons'][:2],  # Top 2 reasons
                    'score': rec['recommendation_score']
                }
                for rec in food_recs
            ],
            'confidence': ml_recommendations['personalization_confidence']
        }
    
    def _get_meal_planning_insights(self, ml_recommendations: Dict) -> Dict:
        """Get meal planning insights"""
        
        insights = ml_recommendations['meal_planning_insights']
        
        return {
            'type': 'meal_planning',
            'title': '📅 Meal Planning Insights',
            'adherence_score': insights['planning_adherence'],
            'cooking_frequency': insights['cooking_frequency'],
            'recommendations': insights['recommendations'],
            'confidence': ml_recommendations['personalization_confidence']
        }
    
    def _get_nutrition_insights(self, ml_recommendations: Dict) -> Dict:
        """Get nutrition insights"""
        
        nutrition_guidance = ml_recommendations['nutritional_guidance']
        
        return {
            'type': 'nutrition',
            'title': '🥗 Nutritional Guidance',
            'current_intake': nutrition_guidance['current_status'],
            'goals': nutrition_guidance['goals'],
            'consistency_score': nutrition_guidance['consistency_score'],
            'recommendations': nutrition_guidance['recommendations'],
            'confidence': ml_recommendations['personalization_confidence']
        }
    
    def _get_cuisine_insights(self, ml_recommendations: Dict) -> Dict:
        """Get cuisine insights"""
        
        cuisine_suggestions = ml_recommendations['cuisine_suggestions']
        
        return {
            'type': 'cuisine',
            'title': '🌍 Cuisine Suggestions',
            'suggestions': [
                {
                    'cuisine': sug['cuisine'],
                    'reason': sug['reason'],
                    'priority': sug['priority'],
                    'confidence': sug['confidence']
                }
                for sug in cuisine_suggestions
            ],
            'confidence': ml_recommendations['personalization_confidence']
        }
    
    def _get_personalized_suggestions(self, user_profile: Dict, ml_recommendations: Dict, user_query: str) -> List[Dict]:
        """Get personalized suggestions based on user profile and query"""
        
        suggestions = []
        
        # Get behavioral insights
        behavioral_insights = ml_recommendations['behavioral_insights']
        
        # Add suggestions based on user patterns
        if behavioral_insights['meal_regularity'] < 0.6:
            suggestions.append({
                'type': 'regularity',
                'message': '💡 Try eating at more consistent times to improve your meal regularity',
                'priority': 'high'
            })
        
        if behavioral_insights['variety_seeking'] < 0.4:
            suggestions.append({
                'type': 'variety',
                'message': '🌍 Consider trying different cuisines to expand your food variety',
                'priority': 'medium'
            })
        
        # Add suggestions based on cooking profile
        cooking_profile = user_profile['cooking_profile']
        if cooking_profile['meal_prep_preference']:
            suggestions.append({
                'type': 'meal_prep',
                'message': '🍱 Focus on batch cooking recipes for better meal prep efficiency',
                'priority': 'medium'
            })
        
        # Add suggestions based on nutritional goals
        nutritional_guidance = ml_recommendations['nutritional_guidance']
        if nutritional_guidance['goals'] and nutritional_guidance['recommendations']:
            for rec in nutritional_guidance['recommendations'][:2]:  # Top 2 recommendations
                suggestions.append({
                    'type': 'nutrition',
                    'message': f'🥗 {rec["message"]}',
                    'priority': 'high'
                })
        
        return suggestions[:3]  # Limit to top 3 suggestions
    
    def track_user_interaction(self, user_id: int, query: str, response: Dict, satisfaction: float = None):
        """Track user interaction for learning"""
        
        try:
            # This would save to ChatbotInteraction table
            # For now, we'll just log it
            logger.info(f"User {user_id} interaction: {query[:50]}... - Satisfaction: {satisfaction}")
            
            # In a real implementation, you would save this to the database
            # interaction = ChatbotInteraction(
            #     user_id=user_id,
            #     query=query,
            #     agent_used=response.get('agent_used', 'unknown'),
            #     response_type='success' if response.get('success') else 'error',
            #     user_satisfaction=satisfaction,
            #     context_data=response.get('user_context', {}),
            #     created_at=datetime.utcnow()
            # )
            # self.db.add(interaction)
            # self.db.commit()
            
        except Exception as e:
            logger.error(f"Error tracking user interaction: {e}")
    
    def get_user_insights_summary(self, user_id: int) -> Dict:
        """Get a summary of user insights for dashboard display"""
        
        user_profile = self.profiler.create_comprehensive_profile(user_id)
        ml_recommendations = self.recommendation_engine.get_personalized_recommendations(
            self.db.query(User).filter(User.id == user_id).first()
        )
        
        return {
            'profile_summary': {
                'preference_confidence': user_profile['preference_confidence'],
                'cooking_frequency': user_profile['cooking_profile']['cooking_frequency'],
                'skill_level': user_profile['cooking_profile']['skill_level'],
                'meal_regularity': user_profile['behavioral_patterns']['meal_regularity'],
                'variety_seeking': user_profile['behavioral_patterns']['variety_seeking']
            },
            'top_recommendations': ml_recommendations['food_recommendations'][:3],
            'cuisine_suggestions': ml_recommendations['cuisine_suggestions'][:2],
            'nutritional_status': ml_recommendations['nutritional_guidance']['current_status'],
            'behavioral_insights': ml_recommendations['behavioral_insights']['recommendations'][:3]
        }
