# app/services/enhanced_recommendation_rules.py
"""
Enhanced recommendation rules for better personalization
"""
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import math

from app.database import User, FoodItem, MealLog, FoodRating, Goal
from app.models.enhanced_models import (
    UserCookingPattern, UserNutritionGoals, FoodPreferenceLearning,
    ChatbotInteraction, SeasonalPreference, SocialCookingData
)

logger = logging.getLogger(__name__)

class EnhancedRecommendationRules:
    """Enhanced recommendation rules with sophisticated logic"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_enhanced_recommendations(self, user_id: int, context: Dict = None) -> Dict[str, Any]:
        """Get enhanced recommendations using sophisticated rules"""
        
        try:
            # Get user profile
            user_profile = self._get_comprehensive_user_profile(user_id)
            
            # Get context
            context = context or {}
            meal_type = context.get('meal_type', 'lunch')
            max_recommendations = context.get('max_recommendations', 10)
            
            # Get candidate foods
            candidate_foods = self._get_candidate_foods(user_profile, context)
            
            # Score foods using enhanced rules
            scored_foods = []
            for food in candidate_foods:
                score, reasons = self._calculate_enhanced_score(food, user_profile, context)
                
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
                    'recommendation_reasons': reasons,
                    'confidence_level': self._calculate_confidence_level(score, user_profile)
                })
            
            # Sort by score and return top recommendations
            scored_foods.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            return {
                'recommendations': scored_foods[:max_recommendations],
                'user_profile_summary': self._get_profile_summary(user_profile),
                'context_used': context,
                'total_candidates': len(candidate_foods),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced recommendations: {e}")
            return {"error": str(e)}
    
    def _get_comprehensive_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user profile with all data"""
        
        # Get basic user data
        user = self.db.query(User).filter(User.id == user_id).first()
        
        # Get cooking pattern
        cooking_pattern = self.db.query(UserCookingPattern).filter(
            UserCookingPattern.user_id == user_id
        ).first()
        
        # Get nutrition goals
        nutrition_goals = self.db.query(UserNutritionGoals).filter(
            UserNutritionGoals.user_id == user_id,
            UserNutritionGoals.is_active == True
        ).first()
        
        # Get social cooking data
        social_cooking = self.db.query(SocialCookingData).filter(
            SocialCookingData.user_id == user_id
        ).first()
        
        # Get seasonal preferences
        seasonal_prefs = self.db.query(SeasonalPreference).filter(
            SeasonalPreference.user_id == user_id
        ).all()
        
        # Get recent meal history for analysis
        recent_meals = self.db.query(MealLog).join(FoodItem).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.logged_at >= datetime.utcnow() - timedelta(days=30)
            )
        ).all()
        
        # Get food preferences
        food_preferences = self.db.query(FoodPreferenceLearning).filter(
            FoodPreferenceLearning.user_id == user_id
        ).all()
        
        # Analyze patterns
        patterns = self._analyze_user_patterns(recent_meals, food_preferences)
        
        return {
            'user': user,
            'cooking_pattern': cooking_pattern,
            'nutrition_goals': nutrition_goals,
            'social_cooking': social_cooking,
            'seasonal_preferences': {p.season: p for p in seasonal_prefs},
            'patterns': patterns,
            'recent_meals': recent_meals,
            'food_preferences': {fp.food_item_id: fp for fp in food_preferences}
        }
    
    def _analyze_user_patterns(self, recent_meals: List[MealLog], 
                             food_preferences: List[FoodPreferenceLearning]) -> Dict[str, Any]:
        """Analyze user patterns from recent data"""
        
        if not recent_meals:
            return self._get_default_patterns()
        
        # Analyze cuisine preferences
        cuisine_counts = {}
        for meal in recent_meals:
            if meal.food_item and meal.food_item.cuisine_type:
                cuisine = meal.food_item.cuisine_type
                cuisine_counts[cuisine] = cuisine_counts.get(cuisine, 0) + 1
        
        # Analyze meal timing patterns
        meal_times = [meal.logged_at.hour for meal in recent_meals]
        meal_types = [meal.meal_type for meal in recent_meals]
        
        # Analyze nutritional patterns
        daily_nutrition = {}
        for meal in recent_meals:
            date = meal.logged_at.date()
            if date not in daily_nutrition:
                daily_nutrition[date] = {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0}
            
            daily_nutrition[date]['calories'] += meal.calories
            daily_nutrition[date]['protein'] += meal.protein
            daily_nutrition[date]['carbs'] += meal.carbs
            daily_nutrition[date]['fat'] += meal.fat
        
        # Calculate variety score
        unique_foods = len(set(meal.food_item_id for meal in recent_meals))
        variety_score = unique_foods / len(recent_meals) if recent_meals else 0
        
        # Calculate regularity score
        meal_regularity = self._calculate_meal_regularity(meal_times)
        
        return {
            'cuisine_preferences': cuisine_counts,
            'meal_timing_patterns': {
                'breakfast_hours': [h for h in meal_times if 6 <= h <= 10],
                'lunch_hours': [h for h in meal_times if 11 <= h <= 14],
                'dinner_hours': [h for h in meal_times if 17 <= h <= 21],
                'snack_hours': [h for h in meal_times if h not in range(6, 11) and h not in range(11, 15) and h not in range(17, 22)]
            },
            'meal_type_distribution': {
                'breakfast': meal_types.count('breakfast'),
                'lunch': meal_types.count('lunch'),
                'dinner': meal_types.count('dinner'),
                'snack': meal_types.count('snack')
            },
            'nutritional_patterns': daily_nutrition,
            'variety_score': variety_score,
            'meal_regularity': meal_regularity,
            'total_meals': len(recent_meals)
        }
    
    def _get_candidate_foods(self, user_profile: Dict, context: Dict) -> List[FoodItem]:
        """Get candidate foods based on user profile and context"""
        
        query = self.db.query(FoodItem)
        
        # Apply filters based on user profile
        cooking_pattern = user_profile.get('cooking_pattern')
        nutrition_goals = user_profile.get('nutrition_goals')
        patterns = user_profile.get('patterns', {})
        
        # Filter by cooking skill level
        if cooking_pattern and cooking_pattern.cooking_skill_level:
            skill_level = cooking_pattern.cooking_skill_level
            if skill_level == 'beginner':
                query = query.filter(FoodItem.prep_complexity.in_(['low', 'medium']))
            elif skill_level == 'advanced':
                query = query.filter(FoodItem.prep_complexity.in_(['medium', 'high']))
        
        # Filter by budget range
        if cooking_pattern and cooking_pattern.budget_range:
            budget_ranges = {
                'low': (0, 5),
                'medium': (5, 15),
                'high': (15, 50)
            }
            budget_range = budget_ranges.get(cooking_pattern.budget_range, (0, 50))
            query = query.filter(FoodItem.cost.between(budget_range[0], budget_range[1]))
        
        # Filter by preferred cuisines
        if cooking_pattern and cooking_pattern.preferred_cuisines:
            preferred_cuisines = cooking_pattern.preferred_cuisines
            if 'mixed' not in preferred_cuisines:
                query = query.filter(FoodItem.cuisine_type.in_(preferred_cuisines))
        
        # Filter by dietary restrictions
        user = user_profile.get('user')
        if user and user.health_conditions:
            health_conditions = json.loads(user.health_conditions) if isinstance(user.health_conditions, str) else user.health_conditions
            if health_conditions.get('diabetes'):
                query = query.filter(FoodItem.diabetic_friendly == True)
            if health_conditions.get('hypertension'):
                query = query.filter(FoodItem.hypertension_friendly == True)
        
        # Filter by meal type appropriateness
        meal_type = context.get('meal_type', 'lunch')
        query = self._filter_by_meal_type(query, meal_type)
        
        # Filter out very high calorie items for better recommendations
        query = query.filter(FoodItem.calories <= 1000)
        
        # Filter out very high sodium items
        query = query.filter(FoodItem.sodium_mg <= 1000)
        
        # Get recent foods to avoid repetition
        recent_foods = self._get_recent_foods(user_profile['user'].id, days=7)
        if recent_foods:
            query = query.filter(~FoodItem.id.in_(recent_foods))
        
        return query.limit(100).all()
    
    def _calculate_enhanced_score(self, food: FoodItem, user_profile: Dict, context: Dict) -> Tuple[float, List[str]]:
        """Calculate enhanced recommendation score with detailed reasoning"""
        
        score = 0.0
        reasons = []
        
        # 1. Cuisine preference alignment (25% weight)
        cuisine_score, cuisine_reasons = self._calculate_cuisine_score(food, user_profile)
        score += cuisine_score * 0.25
        reasons.extend(cuisine_reasons)
        
        # 2. Nutritional alignment (20% weight)
        nutrition_score, nutrition_reasons = self._calculate_nutrition_score(food, user_profile)
        score += nutrition_score * 0.20
        reasons.extend(nutrition_reasons)
        
        # 3. Cooking profile alignment (15% weight)
        cooking_score, cooking_reasons = self._calculate_cooking_score(food, user_profile)
        score += cooking_score * 0.15
        reasons.extend(cooking_reasons)
        
        # 4. Behavioral pattern alignment (15% weight)
        behavior_score, behavior_reasons = self._calculate_behavior_score(food, user_profile, context)
        score += behavior_score * 0.15
        reasons.extend(behavior_reasons)
        
        # 5. Seasonal appropriateness (10% weight)
        seasonal_score, seasonal_reasons = self._calculate_seasonal_score(food, user_profile)
        score += seasonal_score * 0.10
        reasons.extend(seasonal_reasons)
        
        # 6. Social cooking alignment (10% weight)
        social_score, social_reasons = self._calculate_social_score(food, user_profile)
        score += social_score * 0.10
        reasons.extend(social_reasons)
        
        # 7. Meal type appropriateness (5% weight)
        meal_score, meal_reasons = self._calculate_meal_type_score(food, context.get('meal_type', 'lunch'))
        score += meal_score * 0.05
        reasons.extend(meal_reasons)
        
        return min(1.0, score), reasons
    
    def _calculate_cuisine_score(self, food: FoodItem, user_profile: Dict) -> Tuple[float, List[str]]:
        """Calculate cuisine preference score"""
        
        score = 0.0
        reasons = []
        
        cooking_pattern = user_profile.get('cooking_pattern')
        patterns = user_profile.get('patterns', {})
        
        if cooking_pattern and cooking_pattern.preferred_cuisines:
            if food.cuisine_type in cooking_pattern.preferred_cuisines:
                score = 1.0
                reasons.append(f"Matches your preferred {food.cuisine_type} cuisine")
            elif 'mixed' in cooking_pattern.preferred_cuisines:
                score = 0.7
                reasons.append("Good variety choice")
            else:
                score = 0.3
                reasons.append("Different from your usual preferences")
        
        # Check recent cuisine patterns
        cuisine_preferences = patterns.get('cuisine_preferences', {})
        if food.cuisine_type in cuisine_preferences:
            frequency = cuisine_preferences[food.cuisine_type] / patterns.get('total_meals', 1)
            if frequency > 0.3:
                score = max(score, 0.8)
                reasons.append(f"You've been enjoying {food.cuisine_type} cuisine recently")
        
        return score, reasons
    
    def _calculate_nutrition_score(self, food: FoodItem, user_profile: Dict) -> Tuple[float, List[str]]:
        """Calculate nutritional alignment score"""
        
        score = 0.0
        reasons = []
        
        nutrition_goals = user_profile.get('nutrition_goals')
        patterns = user_profile.get('patterns', {})
        
        if nutrition_goals:
            # Check protein alignment
            if nutrition_goals.target_protein and food.protein_g > 15:
                score += 0.3
                reasons.append("High in protein - helps meet your goals")
            
            # Check fiber alignment
            if nutrition_goals.target_fiber and food.fiber_g > 5:
                score += 0.2
                reasons.append("Rich in fiber - supports your nutrition goals")
            
            # Check calorie appropriateness
            if nutrition_goals.target_calories:
                if food.calories < 200:
                    score += 0.2
                    reasons.append("Light option for your calorie goals")
                elif 200 <= food.calories <= 500:
                    score += 0.3
                    reasons.append("Well-balanced for your calorie goals")
        
        # Check health conditions
        user = user_profile.get('user')
        if user and user.health_conditions:
            health_conditions = json.loads(user.health_conditions) if isinstance(user.health_conditions, str) else user.health_conditions
            if health_conditions.get('diabetes') and food.diabetic_friendly:
                score += 0.2
                reasons.append("Diabetic-friendly option")
            if health_conditions.get('hypertension') and food.hypertension_friendly:
                score += 0.2
                reasons.append("Heart-healthy choice")
        
        return min(1.0, score), reasons
    
    def _calculate_cooking_score(self, food: FoodItem, user_profile: Dict) -> Tuple[float, List[str]]:
        """Calculate cooking profile alignment score"""
        
        score = 0.0
        reasons = []
        
        cooking_pattern = user_profile.get('cooking_pattern')
        
        if cooking_pattern:
            # Skill level alignment
            skill_level = cooking_pattern.cooking_skill_level
            if skill_level == 'beginner' and food.prep_complexity == 'low':
                score += 0.5
                reasons.append("Perfect for your skill level")
            elif skill_level == 'intermediate' and food.prep_complexity in ['low', 'medium']:
                score += 0.4
                reasons.append("Good match for your cooking skills")
            elif skill_level == 'advanced' and food.prep_complexity == 'high':
                score += 0.5
                reasons.append("Challenging recipe to showcase your skills")
            
            # Budget alignment
            budget_range = cooking_pattern.budget_range
            if budget_range == 'low' and food.cost <= 5:
                score += 0.3
                reasons.append("Budget-friendly option")
            elif budget_range == 'medium' and 5 < food.cost <= 15:
                score += 0.3
                reasons.append("Good value for money")
            elif budget_range == 'high' and food.cost > 15:
                score += 0.3
                reasons.append("Premium ingredient for special occasions")
            
            # Meal prep preference
            if cooking_pattern.meal_prep_preference and food.prep_complexity == 'low':
                score += 0.2
                reasons.append("Great for meal prep")
        
        return min(1.0, score), reasons
    
    def _calculate_behavior_score(self, food: FoodItem, user_profile: Dict, context: Dict) -> Tuple[float, List[str]]:
        """Calculate behavioral pattern alignment score"""
        
        score = 0.0
        reasons = []
        
        patterns = user_profile.get('patterns', {})
        food_preferences = user_profile.get('food_preferences', {})
        
        # Variety seeking behavior
        variety_score = patterns.get('variety_score', 0)
        if variety_score > 0.7 and food.cuisine_type not in [m.food_item.cuisine_type for m in patterns.get('recent_meals', [])]:
            score += 0.4
            reasons.append("New cuisine to explore for variety")
        
        # Check if user has tried this food before
        if food.id in food_preferences:
            preference = food_preferences[food.id]
            if preference.preference_score > 0.7:
                score += 0.3
                reasons.append("You've enjoyed this food before")
            elif preference.preference_score < 0.3:
                score -= 0.2
                reasons.append("You didn't like this food previously")
        
        # Meal timing patterns
        meal_type = context.get('meal_type', 'lunch')
        meal_type_distribution = patterns.get('meal_type_distribution', {})
        if meal_type_distribution.get(meal_type, 0) > 0:
            score += 0.3
            reasons.append(f"Matches your {meal_type} preferences")
        
        return min(1.0, score), reasons
    
    def _calculate_seasonal_score(self, food: FoodItem, user_profile: Dict) -> Tuple[float, List[str]]:
        """Calculate seasonal appropriateness score"""
        
        score = 0.5  # Default neutral score
        reasons = []
        
        current_season = self._get_current_season()
        seasonal_preferences = user_profile.get('seasonal_preferences', {})
        
        if current_season in seasonal_preferences:
            season_pref = seasonal_preferences[current_season]
            if season_pref.preferred_foods and food.name.lower() in [f.lower() for f in season_pref.preferred_foods]:
                score = 1.0
                reasons.append(f"Perfect for {current_season} season")
            elif season_pref.avoided_foods and food.name.lower() in [f.lower() for f in season_pref.avoided_foods]:
                score = 0.2
                reasons.append(f"Not ideal for {current_season} season")
        
        # General seasonal appropriateness
        if current_season == 'winter' and any(word in food.name.lower() for word in ['soup', 'stew', 'curry', 'hot']):
            score = max(score, 0.8)
            reasons.append("Warming food for winter")
        elif current_season == 'summer' and any(word in food.name.lower() for word in ['salad', 'fresh', 'cold', 'smoothie']):
            score = max(score, 0.8)
            reasons.append("Refreshing food for summer")
        
        return score, reasons
    
    def _calculate_social_score(self, food: FoodItem, user_profile: Dict) -> Tuple[float, List[str]]:
        """Calculate social cooking alignment score"""
        
        score = 0.5  # Default neutral score
        reasons = []
        
        social_cooking = user_profile.get('social_cooking')
        
        if social_cooking:
            if social_cooking.cooking_for_others:
                # Prefer foods that are good for sharing
                if any(word in food.name.lower() for word in ['curry', 'pasta', 'casserole', 'stew']):
                    score = 0.8
                    reasons.append("Great for sharing with others")
                
                # Consider family size
                family_size = social_cooking.family_size or 1
                if family_size > 2 and food.cost < 10:
                    score += 0.2
                    reasons.append("Economical for family meals")
        
        return min(1.0, score), reasons
    
    def _calculate_meal_type_score(self, food: FoodItem, meal_type: str) -> Tuple[float, List[str]]:
        """Calculate meal type appropriateness score"""
        
        score = 0.5  # Default neutral score
        reasons = []
        
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
                        score = 1.0
                        reasons.append(f"Perfect for {meal_type}")
                    elif category == 'medium':
                        score = 0.6
                        reasons.append(f"Good for {meal_type}")
                    elif category == 'low':
                        score = 0.2
                        reasons.append(f"Not ideal for {meal_type}")
                    break
        
        return score, reasons
    
    def _calculate_confidence_level(self, score: float, user_profile: Dict) -> str:
        """Calculate confidence level for recommendation"""
        
        patterns = user_profile.get('patterns', {})
        total_meals = patterns.get('total_meals', 0)
        
        if total_meals < 5:
            return "low"
        elif total_meals < 20:
            return "medium"
        else:
            return "high"
    
    def _get_profile_summary(self, user_profile: Dict) -> Dict[str, Any]:
        """Get user profile summary for recommendations"""
        
        cooking_pattern = user_profile.get('cooking_pattern')
        nutrition_goals = user_profile.get('nutrition_goals')
        patterns = user_profile.get('patterns', {})
        
        return {
            'cooking_skill': cooking_pattern.cooking_skill_level if cooking_pattern else 'unknown',
            'cooking_frequency': cooking_pattern.cooking_frequency if cooking_pattern else 'unknown',
            'budget_range': cooking_pattern.budget_range if cooking_pattern else 'unknown',
            'preferred_cuisines': cooking_pattern.preferred_cuisines if cooking_pattern else [],
            'nutrition_goals': nutrition_goals.goal_type if nutrition_goals else 'none',
            'variety_seeking': patterns.get('variety_score', 0),
            'meal_regularity': patterns.get('meal_regularity', 0),
            'total_meals_analyzed': patterns.get('total_meals', 0)
        }
    
    def _filter_by_meal_type(self, query, meal_type: str):
        """Filter foods by meal type appropriateness"""
        
        # This is a simplified filter - in practice, you'd have more sophisticated logic
        if meal_type == 'breakfast':
            query = query.filter(FoodItem.calories <= 600)
        elif meal_type == 'snack':
            query = query.filter(FoodItem.calories <= 300)
        
        return query
    
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
    
    def _calculate_meal_regularity(self, meal_times: List[int]) -> float:
        """Calculate meal timing regularity"""
        
        if not meal_times:
            return 0.0
        
        # Group by meal times
        breakfast_hours = [h for h in meal_times if 6 <= h <= 10]
        lunch_hours = [h for h in meal_times if 11 <= h <= 14]
        dinner_hours = [h for h in meal_times if 17 <= h <= 21]
        
        # Calculate consistency for each meal type
        breakfast_consistency = 1 - (len(set(breakfast_hours)) / max(len(breakfast_hours), 1)) if breakfast_hours else 0
        lunch_consistency = 1 - (len(set(lunch_hours)) / max(len(lunch_hours), 1)) if lunch_hours else 0
        dinner_consistency = 1 - (len(set(dinner_hours)) / max(len(dinner_hours), 1)) if dinner_hours else 0
        
        # Overall regularity
        return (breakfast_consistency + lunch_consistency + dinner_consistency) / 3
    
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
    
    def _get_default_patterns(self) -> Dict[str, Any]:
        """Get default patterns for new users"""
        return {
            'cuisine_preferences': {},
            'meal_timing_patterns': {
                'breakfast_hours': [],
                'lunch_hours': [],
                'dinner_hours': [],
                'snack_hours': []
            },
            'meal_type_distribution': {
                'breakfast': 0,
                'lunch': 0,
                'dinner': 0,
                'snack': 0
            },
            'nutritional_patterns': {},
            'variety_score': 0.5,
            'meal_regularity': 0.5,
            'total_meals': 0
        }
