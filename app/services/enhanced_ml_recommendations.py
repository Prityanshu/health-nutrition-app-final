# app/services/enhanced_ml_recommendations.py
"""
Enhanced ML recommendation system with advanced personalization
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json
import math
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import logging

from app.database import User, FoodItem, MealLog, Goal
from app.database import FoodRating
from app.models.enhanced_models import (
    UserBehavior, RecipeInteraction, UserCookingPattern,
    MealPlanAdherence, UserNutritionGoals, FoodPreferenceLearning,
    ChatbotInteraction, SeasonalPreference, SocialCookingData
)
from app.services.food_rating_service import FoodRatingService
from app.services.recipe_interaction_service import RecipeInteractionService
from app.services.social_cooking_service import SocialCookingService

logger = logging.getLogger(__name__)

class AdvancedUserProfiler:
    """Advanced user profiling with multi-dimensional analysis"""
    
    def __init__(self, db: Session):
        self.db = db
        self.food_rating_service = FoodRatingService(db)
        self.recipe_interaction_service = RecipeInteractionService(db)
        self.social_cooking_service = SocialCookingService(db)
    
    def create_comprehensive_profile(self, user_id: int) -> Dict[str, Any]:
        """Create a comprehensive user profile from all available data"""
        
        profile = {
            'basic_preferences': self._analyze_basic_preferences(user_id),
            'behavioral_patterns': self._analyze_behavioral_patterns(user_id),
            'cooking_profile': self._analyze_cooking_profile(user_id),
            'nutritional_profile': self._analyze_nutritional_profile(user_id),
            'social_preferences': self._analyze_social_preferences(user_id),
            'seasonal_patterns': self._analyze_seasonal_patterns(user_id),
            'interaction_history': self._analyze_interaction_history(user_id),
            'food_rating_insights': self._analyze_food_rating_insights(user_id),
            'recipe_interaction_insights': self._analyze_recipe_interaction_insights(user_id),
            'social_cooking_insights': self._analyze_social_cooking_insights(user_id),
            'preference_confidence': self._calculate_preference_confidence(user_id)
        }
        
        return profile
    
    def _analyze_basic_preferences(self, user_id: int) -> Dict:
        """Analyze basic food and cuisine preferences"""
        # Get meal history
        meals = self.db.query(MealLog).join(FoodItem).filter(
            MealLog.user_id == user_id,
            MealLog.logged_at >= datetime.utcnow() - timedelta(days=90)
        ).all()
        
        if not meals:
            return self._get_default_preferences()
        
        # Analyze cuisine preferences
        cuisine_prefs = defaultdict(lambda: {'count': 0, 'rating_sum': 0, 'planned_count': 0})
        
        for meal in meals:
            if meal.food_item and meal.food_item.cuisine_type:
                cuisine = meal.food_item.cuisine_type
                cuisine_prefs[cuisine]['count'] += 1
                cuisine_prefs[cuisine]['planned_count'] += (1 if meal.planned else 0)
                
                # Get user rating if available
                rating = self.db.query(FoodRating).filter(
                    FoodRating.user_id == user_id,
                    FoodRating.food_id == meal.food_item_id
                ).first()
                
                if rating:
                    cuisine_prefs[cuisine]['rating_sum'] += rating.rating
        
        # Calculate preference scores
        total_meals = len(meals)
        cuisine_scores = {}
        
        for cuisine, data in cuisine_prefs.items():
            frequency = data['count'] / total_meals
            planning_preference = data['planned_count'] / data['count'] if data['count'] > 0 else 0
            avg_rating = data['rating_sum'] / data['count'] if data['count'] > 0 else 3.0
            
            # Weighted score: frequency * planning_preference * rating
            score = frequency * (0.3 + 0.7 * planning_preference) * (avg_rating / 5.0)
            
            cuisine_scores[cuisine] = {
                'preference_score': score,
                'frequency': frequency,
                'planning_preference': planning_preference,
                'avg_rating': avg_rating,
                'meal_count': data['count']
            }
        
        return {
            'cuisine_preferences': dict(sorted(cuisine_scores.items(), 
                                             key=lambda x: x[1]['preference_score'], 
                                             reverse=True)),
            'total_meals_analyzed': total_meals
        }
    
    def _analyze_behavioral_patterns(self, user_id: int) -> Dict:
        """Analyze user behavioral patterns"""
        
        # Get behavioral data
        behaviors = self.db.query(UserBehavior).filter(
            UserBehavior.user_id == user_id
        ).all()
        
        # Get meal logging patterns
        meals = self.db.query(MealLog).filter(
            MealLog.user_id == user_id,
            MealLog.logged_at >= datetime.utcnow() - timedelta(days=30)
        ).all()
        
        patterns = {
            'meal_regularity': self._calculate_meal_regularity(meals),
            'cooking_frequency': self._calculate_cooking_frequency(meals),
            'variety_seeking': self._calculate_variety_seeking(meals),
            'planning_adherence': self._calculate_planning_adherence(meals),
            'experimentation_tendency': self._calculate_experimentation_tendency(user_id)
        }
        
        return patterns
    
    def _analyze_cooking_profile(self, user_id: int) -> Dict:
        """Analyze user's cooking profile and preferences"""
        
        cooking_pattern = self.db.query(UserCookingPattern).filter(
            UserCookingPattern.user_id == user_id
        ).first()
        
        if not cooking_pattern:
            return self._get_default_cooking_profile()
        
        # Analyze recipe interactions
        recipe_interactions = self.db.query(RecipeInteraction).filter(
            RecipeInteraction.user_id == user_id
        ).all()
        
        interaction_stats = {
            'total_interactions': len(recipe_interactions),
            'cooking_rate': len([r for r in recipe_interactions if r.interaction_type == 'cooked']) / max(len(recipe_interactions), 1),
            'saving_rate': len([r for r in recipe_interactions if r.interaction_type == 'saved']) / max(len(recipe_interactions), 1),
            'sharing_rate': len([r for r in recipe_interactions if r.interaction_type == 'shared']) / max(len(recipe_interactions), 1)
        }
        
        return {
            'cooking_frequency': cooking_pattern.cooking_frequency,
            'skill_level': cooking_pattern.cooking_skill_level,
            'preferred_cooking_time': cooking_pattern.preferred_cooking_time,
            'meal_prep_preference': cooking_pattern.meal_prep_preference,
            'budget_range': cooking_pattern.budget_range,
            'interaction_stats': interaction_stats
        }
    
    def _analyze_nutritional_profile(self, user_id: int) -> Dict:
        """Analyze user's nutritional patterns and goals"""
        
        # Get nutrition goals
        nutrition_goals = self.db.query(UserNutritionGoals).filter(
            UserNutritionGoals.user_id == user_id,
            UserNutritionGoals.is_active == True
        ).first()
        
        # Get recent meal data for analysis
        meals = self.db.query(MealLog).join(FoodItem).filter(
            MealLog.user_id == user_id,
            MealLog.logged_at >= datetime.utcnow() - timedelta(days=30)
        ).all()
        
        if not meals:
            return self._get_default_nutritional_profile()
        
        # Calculate daily nutritional averages
        daily_nutrition = defaultdict(lambda: {
            'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
            'fiber': 0, 'sodium': 0, 'sugar': 0, 'meal_count': 0
        })
        
        for meal in meals:
            date = meal.logged_at.date()
            daily_nutrition[date]['calories'] += meal.calories
            daily_nutrition[date]['protein'] += meal.protein
            daily_nutrition[date]['carbs'] += meal.carbs
            daily_nutrition[date]['fat'] += meal.fat
            daily_nutrition[date]['fiber'] += meal.food_item.fiber_g * meal.quantity
            daily_nutrition[date]['sodium'] += meal.food_item.sodium_mg * meal.quantity
            daily_nutrition[date]['sugar'] += meal.food_item.sugar_g * meal.quantity
            daily_nutrition[date]['meal_count'] += 1
        
        # Calculate averages
        nutrition_data = list(daily_nutrition.values())
        avg_daily = {
            'calories': np.mean([d['calories'] for d in nutrition_data]),
            'protein': np.mean([d['protein'] for d in nutrition_data]),
            'carbs': np.mean([d['carbs'] for d in nutrition_data]),
            'fat': np.mean([d['fat'] for d in nutrition_data]),
            'fiber': np.mean([d['fiber'] for d in nutrition_data]),
            'sodium': np.mean([d['sodium'] for d in nutrition_data]),
            'sugar': np.mean([d['sugar'] for d in nutrition_data])
        }
        
        # Calculate macro ratios
        total_calories = avg_daily['calories']
        if total_calories > 0:
            macro_ratios = {
                'protein_ratio': (avg_daily['protein'] * 4) / total_calories * 100,
                'carb_ratio': (avg_daily['carbs'] * 4) / total_calories * 100,
                'fat_ratio': (avg_daily['fat'] * 9) / total_calories * 100
            }
        else:
            macro_ratios = {'protein_ratio': 25, 'carb_ratio': 45, 'fat_ratio': 30}
        
        return {
            'current_intake': avg_daily,
            'macro_ratios': macro_ratios,
            'goals': {
                'target_calories': nutrition_goals.target_calories if nutrition_goals else 2000,
                'target_protein': nutrition_goals.target_protein if nutrition_goals else 150,
                'target_carbs': nutrition_goals.target_carbs if nutrition_goals else 250,
                'target_fat': nutrition_goals.target_fat if nutrition_goals else 65
            } if nutrition_goals else None,
            'consistency_score': self._calculate_nutrition_consistency(nutrition_data)
        }
    
    def _analyze_social_preferences(self, user_id: int) -> Dict:
        """Analyze social cooking and eating preferences"""
        
        social_data = self.db.query(SocialCookingData).filter(
            SocialCookingData.user_id == user_id
        ).first()
        
        if not social_data:
            return self._get_default_social_preferences()
        
        return {
            'cooking_for_others': social_data.cooking_for_others,
            'family_size': social_data.family_size,
            'family_dietary_restrictions': social_data.dietary_restrictions_family,
            'social_meal_preferences': social_data.social_meal_preferences,
            'sharing_behavior': social_data.shared_recipe_preferences
        }
    
    def _analyze_seasonal_patterns(self, user_id: int) -> Dict:
        """Analyze seasonal food preferences"""
        
        seasonal_prefs = self.db.query(SeasonalPreference).filter(
            SeasonalPreference.user_id == user_id
        ).all()
        
        if not seasonal_prefs:
            return self._get_default_seasonal_preferences()
        
        current_season = self._get_current_season()
        current_prefs = next((p for p in seasonal_prefs if p.season == current_season), None)
        
        return {
            'current_season': current_season,
            'seasonal_preferences': {p.season: {
                'preferred_foods': p.preferred_foods,
                'avoided_foods': p.avoided_foods,
                'seasonal_goals': p.seasonal_goals
            } for p in seasonal_prefs},
            'current_recommendations': current_prefs.preferred_foods if current_prefs else []
        }
    
    def _analyze_interaction_history(self, user_id: int) -> Dict:
        """Analyze chatbot and app interaction history"""
        
        chatbot_interactions = self.db.query(ChatbotInteraction).filter(
            ChatbotInteraction.user_id == user_id
        ).order_by(desc(ChatbotInteraction.created_at)).limit(50).all()
        
        if not chatbot_interactions:
            return {'interaction_count': 0, 'preferred_agents': [], 'satisfaction_avg': 0}
        
        # Analyze agent preferences
        agent_usage = Counter([i.agent_used for i in chatbot_interactions])
        satisfaction_scores = [i.user_satisfaction for i in chatbot_interactions if i.user_satisfaction]
        
        return {
            'interaction_count': len(chatbot_interactions),
            'preferred_agents': [agent for agent, count in agent_usage.most_common(3)],
            'satisfaction_avg': np.mean(satisfaction_scores) if satisfaction_scores else 0,
            'recent_queries': [i.query for i in chatbot_interactions[:5]]
        }
    
    def _calculate_preference_confidence(self, user_id: int) -> float:
        """Calculate confidence in user preferences based on data quality"""
        
        # Get data points
        meal_count = self.db.query(MealLog).filter(MealLog.user_id == user_id).count()
        rating_count = self.db.query(FoodRating).filter(FoodRating.user_id == user_id).count()
        interaction_count = self.db.query(ChatbotInteraction).filter(ChatbotInteraction.user_id == user_id).count()
        
        # Calculate confidence score (0-1)
        confidence = min(1.0, (
            (meal_count / 100) * 0.4 +  # 40% weight on meal data
            (rating_count / 50) * 0.3 +  # 30% weight on ratings
            (interaction_count / 20) * 0.3  # 30% weight on interactions
        ))
        
        return confidence
    
    # Helper methods
    def _calculate_meal_regularity(self, meals: List[MealLog]) -> float:
        """Calculate meal timing regularity"""
        if not meals:
            return 0.0
        
        # Group by day and count meals per day
        daily_meal_counts = Counter([meal.logged_at.date() for meal in meals])
        counts = list(daily_meal_counts.values())
        
        if len(counts) < 2:
            return 0.5
        
        # Regularity = 1 - (standard_deviation / mean)
        mean_count = np.mean(counts)
        std_count = np.std(counts)
        regularity = max(0, 1 - (std_count / mean_count))
        
        return regularity
    
    def _calculate_cooking_frequency(self, meals: List[MealLog]) -> str:
        """Calculate cooking frequency based on meal patterns"""
        if not meals:
            return 'unknown'
        
        # Analyze meal types and complexity
        complex_meals = [m for m in meals if m.food_item and m.food_item.prep_complexity in ['high', 'medium']]
        cooking_ratio = len(complex_meals) / len(meals)
        
        if cooking_ratio > 0.7:
            return 'frequent'
        elif cooking_ratio > 0.4:
            return 'moderate'
        else:
            return 'occasional'
    
    def _calculate_variety_seeking(self, meals: List[MealLog]) -> float:
        """Calculate variety seeking tendency"""
        if not meals:
            return 0.0
        
        # Count unique foods and cuisines
        unique_foods = len(set(meal.food_item_id for meal in meals if meal.food_item_id))
        unique_cuisines = len(set(meal.food_item.cuisine_type for meal in meals if meal.food_item and meal.food_item.cuisine_type))
        
        # Variety score based on unique items per total meals
        food_variety = unique_foods / len(meals)
        cuisine_variety = unique_cuisines / max(unique_cuisines, 1)
        
        return (food_variety + cuisine_variety) / 2
    
    def _calculate_planning_adherence(self, meals: List[MealLog]) -> float:
        """Calculate adherence to planned meals"""
        if not meals:
            return 0.0
        
        planned_meals = sum(1 for meal in meals if meal.planned)
        return planned_meals / len(meals)
    
    def _calculate_experimentation_tendency(self, user_id: int) -> float:
        """Calculate tendency to try new foods"""
        # Get food preference learning data
        preferences = self.db.query(FoodPreferenceLearning).filter(
            FoodPreferenceLearning.user_id == user_id
        ).all()
        
        if not preferences:
            return 0.0
        
        # Calculate how often user tries new foods
        new_foods = [p for p in preferences if p.interaction_count == 1]
        return len(new_foods) / len(preferences)
    
    def _calculate_nutrition_consistency(self, nutrition_data: List[Dict]) -> float:
        """Calculate consistency in nutritional intake"""
        if len(nutrition_data) < 2:
            return 0.5
        
        calories = [d['calories'] for d in nutrition_data]
        cv = np.std(calories) / np.mean(calories) if np.mean(calories) > 0 else 1
        
        # Consistency = 1 - coefficient of variation
        return max(0, 1 - cv)
    
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
    
    def _get_default_preferences(self) -> Dict:
        return {
            'cuisine_preferences': {'mixed': {'preference_score': 0.5, 'frequency': 0.3}},
            'total_meals_analyzed': 0
        }
    
    def _get_default_cooking_profile(self) -> Dict:
        return {
            'cooking_frequency': 'moderate',
            'skill_level': 'intermediate',
            'preferred_cooking_time': 'evening',
            'meal_prep_preference': False,
            'budget_range': 'medium',
            'interaction_stats': {'total_interactions': 0, 'cooking_rate': 0, 'saving_rate': 0, 'sharing_rate': 0}
        }
    
    def _get_default_nutritional_profile(self) -> Dict:
        return {
            'current_intake': {'calories': 2000, 'protein': 150, 'carbs': 250, 'fat': 65, 'fiber': 25, 'sodium': 2300, 'sugar': 50},
            'macro_ratios': {'protein_ratio': 25, 'carb_ratio': 45, 'fat_ratio': 30},
            'goals': None,
            'consistency_score': 0.5
        }
    
    def _get_default_social_preferences(self) -> Dict:
        return {
            'cooking_for_others': False,
            'family_size': 1,
            'family_dietary_restrictions': [],
            'social_meal_preferences': {},
            'sharing_behavior': {}
        }
    
    def _get_default_seasonal_preferences(self) -> Dict:
        return {
            'current_season': self._get_current_season(),
            'seasonal_preferences': {},
            'current_recommendations': []
        }
    
    def _analyze_food_rating_insights(self, user_id: int) -> Dict[str, Any]:
        """Analyze user's food rating patterns for better recommendations"""
        try:
            # Get user's food ratings
            user_ratings = self.food_rating_service.get_user_food_ratings(user_id, 100)
            
            if not user_ratings:
                return {
                    "rating_pattern": "no_ratings",
                    "average_rating": 0.0,
                    "rating_consistency": 0.0,
                    "preferred_food_types": [],
                    "rating_confidence": 0.0
                }
            
            # Analyze rating patterns
            ratings = [rating["rating"] for rating in user_ratings]
            avg_rating = sum(ratings) / len(ratings)
            
            # Calculate rating consistency (lower standard deviation = more consistent)
            rating_std = math.sqrt(sum((r - avg_rating) ** 2 for r in ratings) / len(ratings))
            rating_consistency = max(0, 1 - (rating_std / 2.0))  # Normalize to 0-1
            
            # Analyze preferred food types based on high ratings (4.0+)
            high_rated_foods = [r for r in user_ratings if r["rating"] >= 4.0]
            
            # Get food details for high-rated foods
            preferred_food_types = []
            for rating in high_rated_foods[:10]:  # Top 10 high-rated foods
                food_item = self.db.query(FoodItem).filter(FoodItem.id == rating["food_id"]).first()
                if food_item and food_item.cuisine_type:
                    preferred_food_types.append(food_item.cuisine_type)
            
            # Calculate rating confidence based on number of ratings
            rating_confidence = min(1.0, len(user_ratings) / 20.0)  # Max confidence at 20+ ratings
            
            return {
                "rating_pattern": "consistent" if rating_consistency > 0.7 else "variable",
                "average_rating": round(avg_rating, 2),
                "rating_consistency": round(rating_consistency, 2),
                "preferred_food_types": list(set(preferred_food_types)),
                "rating_confidence": round(rating_confidence, 2),
                "total_ratings": len(user_ratings),
                "high_rated_count": len(high_rated_foods)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing food rating insights: {e}")
            return {"error": str(e)}
    
    def _analyze_recipe_interaction_insights(self, user_id: int) -> Dict[str, Any]:
        """Analyze user's recipe interaction patterns"""
        try:
            # Get user's recipe interactions
            interactions = self.recipe_interaction_service.get_user_recipe_interactions(user_id, 100)
            
            if not interactions:
                return {
                    "interaction_pattern": "no_interactions",
                    "engagement_level": "low",
                    "cooking_frequency": "unknown",
                    "preferred_interaction_types": [],
                    "engagement_score": 0.0
                }
            
            # Analyze interaction patterns
            interaction_types = [interaction["interaction_type"] for interaction in interactions]
            interaction_counts = Counter(interaction_types)
            
            # Determine engagement level
            total_interactions = len(interactions)
            if total_interactions > 50:
                engagement_level = "high"
            elif total_interactions > 20:
                engagement_level = "medium"
            else:
                engagement_level = "low"
            
            # Analyze cooking frequency based on "cooked" interactions
            cooked_count = interaction_counts.get("cooked", 0)
            if cooked_count > 15:
                cooking_frequency = "frequent"
            elif cooked_count > 8:
                cooking_frequency = "moderate"
            elif cooked_count > 3:
                cooking_frequency = "occasional"
            else:
                cooking_frequency = "rare"
            
            # Get cooking behavior insights
            behavior_insights = self.recipe_interaction_service.get_cooking_behavior_insights(user_id)
            
            return {
                "interaction_pattern": "active" if engagement_level in ["high", "medium"] else "passive",
                "engagement_level": engagement_level,
                "cooking_frequency": cooking_frequency,
                "preferred_interaction_types": [item[0] for item in interaction_counts.most_common(3)],
                "engagement_score": behavior_insights.get("engagement_score", 0.0),
                "total_interactions": total_interactions,
                "cooking_trends": behavior_insights.get("cooking_trends", {}),
                "skill_level": behavior_insights.get("skill_level", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Error analyzing recipe interaction insights: {e}")
            return {"error": str(e)}
    
    def _analyze_social_cooking_insights(self, user_id: int) -> Dict[str, Any]:
        """Analyze user's social cooking patterns and family preferences"""
        try:
            # Get social cooking profile
            profile_result = self.social_cooking_service.get_social_cooking_profile(user_id)
            
            if not profile_result["success"]:
                return {
                    "social_cooking": False,
                    "family_size": 1,
                    "cooking_context": "individual",
                    "family_dietary_needs": [],
                    "social_preferences": {}
                }
            
            profile = profile_result["profile"]
            
            # Get family eating patterns
            family_patterns = self.social_cooking_service.analyze_family_eating_patterns(user_id)
            
            # Determine cooking context
            if profile.get("cooking_for_others", False):
                family_size = profile.get("family_size", 1)
                if family_size > 4:
                    cooking_context = "large_family"
                elif family_size > 2:
                    cooking_context = "family"
                else:
                    cooking_context = "couple"
            else:
                cooking_context = "individual"
            
            # Analyze family dietary needs
            family_dietary_needs = profile.get("dietary_restrictions_family", [])
            
            return {
                "social_cooking": profile.get("cooking_for_others", False),
                "family_size": profile.get("family_size", 1),
                "cooking_context": cooking_context,
                "family_dietary_needs": family_dietary_needs,
                "social_preferences": profile.get("social_meal_preferences", {}),
                "family_patterns": family_patterns,
                "portion_considerations": family_size if profile.get("cooking_for_others", False) else 1
            }
            
        except Exception as e:
            logger.error(f"Error analyzing social cooking insights: {e}")
            return {"error": str(e)}


class IntelligentRecommendationEngine:
    """Enhanced recommendation engine with advanced personalization"""
    
    def __init__(self, db: Session):
        self.db = db
        self.profiler = AdvancedUserProfiler(db)
    
    def get_personalized_recommendations(self, user: User, context: Dict = None) -> Dict[str, Any]:
        """Get highly personalized recommendations based on comprehensive user profile"""
        
        # Get comprehensive user profile
        profile = self.profiler.create_comprehensive_profile(user.id)
        
        # Generate recommendations based on profile
        recommendations = {
            'food_recommendations': self._recommend_foods_advanced(user, profile, context),
            'recipe_recommendations': self._recommend_recipes_advanced(user, profile, context),
            'cuisine_suggestions': self._suggest_cuisines_advanced(profile),
            'meal_planning_insights': self._generate_meal_planning_insights(profile),
            'nutritional_guidance': self._generate_nutritional_guidance(profile),
            'behavioral_insights': self._generate_behavioral_insights(profile),
            'personalization_confidence': profile['preference_confidence']
        }
        
        return recommendations
    
    def _recommend_foods_advanced(self, user: User, profile: Dict, context: Dict = None) -> List[Dict]:
        """Advanced food recommendations using multiple algorithms"""
        
        # Get context
        meal_type = context.get('meal_type', 'lunch') if context else 'lunch'
        max_recommendations = context.get('max_recommendations', 10) if context else 10
        
        # Get user's food preferences
        food_preferences = self.db.query(FoodPreferenceLearning).filter(
            FoodPreferenceLearning.user_id == user.id
        ).all()
        
        # Create preference scores
        preference_scores = {fp.food_item_id: fp.preference_score for fp in food_preferences}
        
        # Get candidate foods
        query = self.db.query(FoodItem)
        
        # Apply filters based on user profile
        basic_prefs = profile['basic_preferences']
        cooking_profile = profile['cooking_profile']
        nutritional_profile = profile['nutritional_profile']
        
        # Filter by preferred cuisines
        top_cuisines = list(basic_prefs['cuisine_preferences'].keys())[:3]
        if top_cuisines:
            query = query.filter(FoodItem.cuisine_type.in_(top_cuisines))
        
        # Filter by cooking skill level
        if cooking_profile['skill_level'] == 'beginner':
            query = query.filter(FoodItem.prep_complexity.in_(['low', 'medium']))
        elif cooking_profile['skill_level'] == 'advanced':
            query = query.filter(FoodItem.prep_complexity.in_(['medium', 'high']))
        
        # Filter by budget
        budget_ranges = {
            'low': (0, 3),
            'medium': (3, 8),
            'high': (8, 20)
        }
        budget_range = budget_ranges.get(cooking_profile['budget_range'], (0, 20))
        query = query.filter(FoodItem.cost.between(budget_range[0], budget_range[1]))
        
        # Get seasonal preferences
        seasonal_prefs = profile['seasonal_patterns']
        if seasonal_prefs['current_recommendations']:
            # Prefer foods that match seasonal preferences
            pass  # This would require more complex filtering
        
        # Get recent foods to avoid repetition
        recent_foods = self._get_recent_foods(user.id, days=7)
        if recent_foods:
            query = query.filter(~FoodItem.id.in_(recent_foods))
        
        # Get candidate foods
        candidate_foods = query.limit(100).all()
        
        # Score foods using multiple algorithms
        scored_foods = []
        for food in candidate_foods:
            score = self._calculate_advanced_food_score(
                food, profile, meal_type, preference_scores.get(food.id, 0.5)
            )
            
            scored_foods.append({
                'food_id': food.id,
                'name': food.name,
                'cuisine_type': food.cuisine_type,
                'calories': food.calories,
                'protein_g': food.protein_g,
                'carbs_g': food.carbs_g,
                'fat_g': food.fat_g,
                'cost': food.cost,
                'prep_complexity': food.prep_complexity,
                'recommendation_score': score,
                'recommendation_reasons': self._generate_recommendation_reasons(food, profile, meal_type)
            })
        
        # Sort by score and return top recommendations
        scored_foods.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return scored_foods[:max_recommendations]
    
    def _calculate_advanced_food_score(self, food: FoodItem, profile: Dict, meal_type: str, preference_score: float) -> float:
        """Calculate advanced recommendation score using multiple factors"""
        
        score = 0.0
        
        # 1. Basic preference score (30% weight)
        score += preference_score * 0.3
        
        # 2. Cuisine preference alignment (20% weight)
        basic_prefs = profile['basic_preferences']
        cuisine_prefs = basic_prefs['cuisine_preferences']
        if food.cuisine_type in cuisine_prefs:
            cuisine_score = cuisine_prefs[food.cuisine_type]['preference_score']
            score += cuisine_score * 0.2
        
        # 3. Nutritional alignment (20% weight)
        nutritional_profile = profile['nutritional_profile']
        if nutritional_profile['goals']:
            goals = nutritional_profile['goals']
            current = nutritional_profile['current_intake']
            
            # Check if food helps meet nutritional goals
            if goals['target_protein'] > current['protein'] and food.protein_g > 15:
                score += 0.1
            if goals['target_fiber'] > current['fiber'] and food.fiber_g > 5:
                score += 0.1
        
        # 4. Cooking profile alignment (15% weight)
        cooking_profile = profile['cooking_profile']
        if cooking_profile['skill_level'] == 'beginner' and food.prep_complexity == 'low':
            score += 0.15
        elif cooking_profile['skill_level'] == 'advanced' and food.prep_complexity == 'high':
            score += 0.15
        else:
            score += 0.075  # Partial alignment
        
        # 5. Behavioral pattern alignment (10% weight)
        behavioral_patterns = profile['behavioral_patterns']
        if behavioral_patterns['variety_seeking'] > 0.7 and food.cuisine_type not in [f.cuisine_type for f in self._get_recent_foods(user.id, days=14)]:
            score += 0.1
        
        # 6. Meal type appropriateness (5% weight)
        meal_appropriateness = self._calculate_meal_appropriateness(food, meal_type)
        score += meal_appropriateness * 0.05
        
        return min(1.0, score)
    
    def _generate_recommendation_reasons(self, food: FoodItem, profile: Dict, meal_type: str) -> List[str]:
        """Generate human-readable reasons for recommendations"""
        
        reasons = []
        
        # Cuisine preference
        basic_prefs = profile['basic_preferences']
        cuisine_prefs = basic_prefs['cuisine_preferences']
        if food.cuisine_type in cuisine_prefs:
            pref_score = cuisine_prefs[food.cuisine_type]['preference_score']
            if pref_score > 0.7:
                reasons.append(f"Matches your love for {food.cuisine_type} cuisine")
        
        # Nutritional benefits
        nutritional_profile = profile['nutritional_profile']
        if nutritional_profile['goals']:
            goals = nutritional_profile['goals']
            current = nutritional_profile['current_intake']
            
            if goals['target_protein'] > current['protein'] and food.protein_g > 15:
                reasons.append("High in protein - helps meet your goals")
            if goals['target_fiber'] > current['fiber'] and food.fiber_g > 5:
                reasons.append("Rich in fiber - supports your nutrition goals")
        
        # Cooking skill alignment
        cooking_profile = profile['cooking_profile']
        if cooking_profile['skill_level'] == 'beginner' and food.prep_complexity == 'low':
            reasons.append("Perfect for your cooking skill level")
        elif cooking_profile['skill_level'] == 'advanced' and food.prep_complexity == 'high':
            reasons.append("Challenging recipe to showcase your skills")
        
        # Budget alignment
        budget_range = cooking_profile['budget_range']
        if budget_range == 'low' and food.cost <= 3:
            reasons.append("Budget-friendly option")
        elif budget_range == 'high' and food.cost >= 8:
            reasons.append("Premium ingredient for special occasions")
        
        # Default reason
        if not reasons:
            reasons.append("Well-balanced nutritional choice")
        
        return reasons
    
    def _recommend_recipes_advanced(self, user: User, profile: Dict, context: Dict = None) -> List[Dict]:
        """Advanced recipe recommendations"""
        # This would integrate with the existing recipe generation services
        # and use the user profile to generate more personalized recipes
        return []
    
    def _suggest_cuisines_advanced(self, profile: Dict) -> List[Dict]:
        """Advanced cuisine suggestions based on profile"""
        
        basic_prefs = profile['basic_preferences']
        behavioral_patterns = profile['behavioral_patterns']
        
        suggestions = []
        
        # Get all available cuisines
        available_cuisines = self.db.query(FoodItem.cuisine_type).distinct().all()
        available_cuisines = [c[0] for c in available_cuisines if c[0]]
        
        # Suggest based on variety seeking tendency
        if behavioral_patterns['variety_seeking'] > 0.6:
            # Suggest unexplored cuisines
            explored_cuisines = set(basic_prefs['cuisine_preferences'].keys())
            unexplored = [c for c in available_cuisines if c not in explored_cuisines]
            
            for cuisine in unexplored[:3]:
                suggestions.append({
                    'cuisine': cuisine,
                    'reason': 'New cuisine to explore for variety',
                    'priority': 'high',
                    'confidence': 0.8
                })
        
        # Suggest based on seasonal preferences
        seasonal_prefs = profile['seasonal_patterns']
        if seasonal_prefs['current_recommendations']:
            suggestions.append({
                'cuisine': 'seasonal',
                'reason': f'Perfect for {seasonal_prefs["current_season"]} season',
                'priority': 'medium',
                'confidence': 0.7
            })
        
        return suggestions
    
    def _generate_meal_planning_insights(self, profile: Dict) -> Dict:
        """Generate insights for better meal planning"""
        
        behavioral_patterns = profile['behavioral_patterns']
        cooking_profile = profile['cooking_profile']
        
        insights = {
            'planning_adherence': behavioral_patterns['planning_adherence'],
            'cooking_frequency': behavioral_patterns['cooking_frequency'],
            'recommendations': []
        }
        
        # Generate recommendations based on patterns
        if behavioral_patterns['planning_adherence'] < 0.5:
            insights['recommendations'].append({
                'type': 'planning',
                'message': 'Try planning 2-3 meals per week to improve adherence',
                'priority': 'high'
            })
        
        if behavioral_patterns['variety_seeking'] < 0.4:
            insights['recommendations'].append({
                'type': 'variety',
                'message': 'Consider trying one new cuisine per week',
                'priority': 'medium'
            })
        
        if cooking_profile['meal_prep_preference']:
            insights['recommendations'].append({
                'type': 'meal_prep',
                'message': 'Focus on batch cooking recipes for better meal prep',
                'priority': 'medium'
            })
        
        return insights
    
    def _generate_nutritional_guidance(self, profile: Dict) -> Dict:
        """Generate nutritional guidance based on profile"""
        
        nutritional_profile = profile['nutritional_profile']
        
        guidance = {
            'current_status': nutritional_profile['current_intake'],
            'goals': nutritional_profile['goals'],
            'consistency_score': nutritional_profile['consistency_score'],
            'recommendations': []
        }
        
        if nutritional_profile['goals']:
            goals = nutritional_profile['goals']
            current = nutritional_profile['current_intake']
            
            # Protein recommendations
            if goals['target_protein'] > current['protein']:
                guidance['recommendations'].append({
                    'nutrient': 'protein',
                    'current': current['protein'],
                    'target': goals['target_protein'],
                    'message': f"Increase protein intake by {goals['target_protein'] - current['protein']:.1f}g per day"
                })
            
            # Fiber recommendations
            if goals['target_fiber'] > current['fiber']:
                guidance['recommendations'].append({
                    'nutrient': 'fiber',
                    'current': current['fiber'],
                    'target': goals['target_fiber'],
                    'message': f"Increase fiber intake by {goals['target_fiber'] - current['fiber']:.1f}g per day"
                })
        
        return guidance
    
    def _generate_behavioral_insights(self, profile: Dict) -> Dict:
        """Generate behavioral insights and recommendations"""
        
        behavioral_patterns = profile['behavioral_patterns']
        
        insights = {
            'meal_regularity': behavioral_patterns['meal_regularity'],
            'cooking_frequency': behavioral_patterns['cooking_frequency'],
            'variety_seeking': behavioral_patterns['variety_seeking'],
            'experimentation_tendency': behavioral_patterns['experimentation_tendency'],
            'recommendations': []
        }
        
        # Generate recommendations based on behavioral patterns
        if behavioral_patterns['meal_regularity'] < 0.6:
            insights['recommendations'].append({
                'type': 'regularity',
                'message': 'Try to eat at more consistent times to improve regularity',
                'priority': 'high'
            })
        
        if behavioral_patterns['variety_seeking'] < 0.3:
            insights['recommendations'].append({
                'type': 'variety',
                'message': 'Explore different cuisines and food categories for better variety',
                'priority': 'medium'
            })
        
        if behavioral_patterns['experimentation_tendency'] < 0.2:
            insights['recommendations'].append({
                'type': 'experimentation',
                'message': 'Try one new food or recipe per week to expand your palate',
                'priority': 'low'
            })
        
        return insights
    
    def _get_recent_foods(self, user_id: int, days: int = 7) -> List[int]:
        """Get recently consumed food IDs"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_meals = self.db.query(MealLog.food_item_id).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.logged_at >= cutoff_date
            )
        ).distinct().all()
        
        return [meal[0] for meal in recent_meals]
    
    def _calculate_meal_appropriateness(self, food: FoodItem, meal_type: str) -> float:
        """Calculate how appropriate a food is for a specific meal type"""
        
        food_name_lower = food.name.lower()
        
        appropriateness_map = {
            'breakfast': {
                'high': ['oats', 'eggs', 'yogurt', 'fruit', 'cereal', 'toast', 'pancake', 'smoothie'],
                'medium': ['nuts', 'juice', 'cheese'],
                'low': ['curry', 'fried rice', 'pizza', 'pasta']
            },
            'lunch': {
                'high': ['salad', 'sandwich', 'soup', 'rice', 'quinoa', 'curry', 'stir fry'],
                'medium': ['pasta', 'noodles', 'wrap'],
                'low': ['dessert', 'cake', 'ice cream', 'cereal']
            },
            'dinner': {
                'high': ['curry', 'stir fry', 'grilled', 'roasted', 'soup', 'pasta', 'rice'],
                'medium': ['salad', 'sandwich'],
                'low': ['cereal', 'toast', 'fruit', 'smoothie']
            },
            'snack': {
                'high': ['nuts', 'fruit', 'yogurt', 'crackers', 'cheese'],
                'medium': ['smoothie', 'juice'],
                'low': ['curry', 'fried rice', 'pasta', 'heavy meal']
            }
        }
        
        meal_categories = appropriateness_map.get(meal_type, {})
        
        for category, keywords in meal_categories.items():
            for keyword in keywords:
                if keyword in food_name_lower:
                    if category == 'high':
                        return 1.0
                    elif category == 'medium':
                        return 0.6
                    elif category == 'low':
                        return 0.2
        
        return 0.5  # Default appropriateness
