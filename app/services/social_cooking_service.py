# app/services/social_cooking_service.py
"""
Social cooking data service for enhanced personalization
"""
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models.enhanced_models import SocialCookingData, UserCookingPattern
from app.database import User, MealLog, FoodItem

logger = logging.getLogger(__name__)

class SocialCookingService:
    """Service for managing social cooking data and family preferences"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def update_social_cooking_profile(self, user_id: int, family_size: int = None, 
                                    cooking_for_others: bool = None, 
                                    family_dietary_restrictions: List[str] = None,
                                    social_meal_preferences: Dict = None) -> Dict[str, Any]:
        """Update user's social cooking profile"""
        try:
            social_data = self.db.query(SocialCookingData).filter(
                SocialCookingData.user_id == user_id
            ).first()
            
            if not social_data:
                # Create new social cooking data
                social_data = SocialCookingData(
                    user_id=user_id,
                    cooking_for_others=cooking_for_others or False,
                    family_size=family_size or 1,
                    dietary_restrictions_family=json.dumps(family_dietary_restrictions) if family_dietary_restrictions else None,
                    social_meal_preferences=json.dumps(social_meal_preferences) if social_meal_preferences else None,
                    last_updated=datetime.utcnow()
                )
                self.db.add(social_data)
            else:
                # Update existing data
                if family_size is not None:
                    social_data.family_size = family_size
                if cooking_for_others is not None:
                    social_data.cooking_for_others = cooking_for_others
                if family_dietary_restrictions is not None:
                    social_data.dietary_restrictions_family = json.dumps(family_dietary_restrictions)
                if social_meal_preferences is not None:
                    social_data.social_meal_preferences = json.dumps(social_meal_preferences)
                
                social_data.last_updated = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Updated social cooking profile for user {user_id}")
            
            return {
                "success": True,
                "message": "Social cooking profile updated successfully",
                "profile": self._format_social_profile(social_data)
            }
            
        except Exception as e:
            logger.error(f"Error updating social cooking profile: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_social_cooking_profile(self, user_id: int) -> Dict[str, Any]:
        """Get user's social cooking profile"""
        try:
            social_data = self.db.query(SocialCookingData).filter(
                SocialCookingData.user_id == user_id
            ).first()
            
            if not social_data:
                return {
                    "success": False,
                    "message": "No social cooking profile found",
                    "profile": self._get_default_social_profile()
                }
            
            return {
                "success": True,
                "profile": self._format_social_profile(social_data)
            }
            
        except Exception as e:
            logger.error(f"Error getting social cooking profile: {e}")
            return {"success": False, "error": str(e)}
    
    def get_family_friendly_recommendations(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get family-friendly food and recipe recommendations"""
        try:
            social_data = self.db.query(SocialCookingData).filter(
                SocialCookingData.user_id == user_id
            ).first()
            
            if not social_data or not social_data.cooking_for_others:
                return self._get_individual_recommendations(user_id, limit)
            
            # Get family dietary restrictions
            family_restrictions = json.loads(social_data.dietary_restrictions_family) if social_data.dietary_restrictions_family else []
            
            # Get family-friendly foods
            family_foods = self._get_family_friendly_foods(family_restrictions, social_data.family_size, limit)
            
            return family_foods
            
        except Exception as e:
            logger.error(f"Error getting family-friendly recommendations: {e}")
            return []
    
    def analyze_family_eating_patterns(self, user_id: int) -> Dict[str, Any]:
        """Analyze family eating patterns for better recommendations"""
        try:
            social_data = self.db.query(SocialCookingData).filter(
                SocialCookingData.user_id == user_id
            ).first()
            
            if not social_data or not social_data.cooking_for_others:
                return {"message": "Individual cooking pattern - no family analysis available"}
            
            # Get meal logs to analyze family preferences
            recent_meals = self.db.query(MealLog).join(FoodItem).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.logged_at >= datetime.utcnow() - timedelta(days=30)
                )
            ).all()
            
            # Analyze patterns
            family_patterns = {
                "family_size": social_data.family_size,
                "cooking_frequency": self._analyze_cooking_frequency(recent_meals),
                "preferred_cuisines": self._analyze_family_cuisine_preferences(recent_meals),
                "meal_timing_patterns": self._analyze_meal_timing(recent_meals),
                "portion_sizes": self._analyze_portion_patterns(recent_meals, social_data.family_size),
                "dietary_accommodations": self._analyze_dietary_accommodations(recent_meals, social_data)
            }
            
            return family_patterns
            
        except Exception as e:
            logger.error(f"Error analyzing family eating patterns: {e}")
            return {"error": str(e)}
    
    def get_shared_recipe_suggestions(self, user_id: int, occasion: str = "family_dinner") -> List[Dict[str, Any]]:
        """Get recipe suggestions for sharing with family/friends"""
        try:
            social_data = self.db.query(SocialCookingData).filter(
                SocialCookingData.user_id == user_id
            ).first()
            
            if not social_data:
                return []
            
            # Get shared recipe preferences
            shared_preferences = json.loads(social_data.shared_recipe_preferences) if social_data.shared_recipe_preferences else {}
            
            # Generate suggestions based on occasion and family preferences
            suggestions = self._generate_shared_recipe_suggestions(occasion, social_data, shared_preferences)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting shared recipe suggestions: {e}")
            return []
    
    def track_shared_cooking_experience(self, user_id: int, recipe_id: int, 
                                      family_feedback: Dict, occasion: str = "family_meal") -> Dict[str, Any]:
        """Track shared cooking experiences and family feedback"""
        try:
            # This would typically store in a separate table for shared experiences
            # For now, we'll update the social cooking data
            
            social_data = self.db.query(SocialCookingData).filter(
                SocialCookingData.user_id == user_id
            ).first()
            
            if not social_data:
                return {"success": False, "error": "No social cooking profile found"}
            
            # Update shared recipe preferences based on feedback
            current_preferences = json.loads(social_data.shared_recipe_preferences) if social_data.shared_recipe_preferences else {}
            
            if occasion not in current_preferences:
                current_preferences[occasion] = []
            
            current_preferences[occasion].append({
                "recipe_id": recipe_id,
                "family_feedback": family_feedback,
                "date": datetime.utcnow().isoformat()
            })
            
            social_data.shared_recipe_preferences = json.dumps(current_preferences)
            social_data.last_updated = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Tracked shared cooking experience for user {user_id}, recipe {recipe_id}")
            
            return {
                "success": True,
                "message": "Shared cooking experience tracked successfully"
            }
            
        except Exception as e:
            logger.error(f"Error tracking shared cooking experience: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def _format_social_profile(self, social_data: SocialCookingData) -> Dict[str, Any]:
        """Format social cooking profile for response"""
        return {
            "user_id": social_data.user_id,
            "cooking_for_others": social_data.cooking_for_others,
            "family_size": social_data.family_size,
            "dietary_restrictions_family": json.loads(social_data.dietary_restrictions_family) if social_data.dietary_restrictions_family else [],
            "social_meal_preferences": json.loads(social_data.social_meal_preferences) if social_data.social_meal_preferences else {},
            "shared_recipe_preferences": json.loads(social_data.shared_recipe_preferences) if social_data.shared_recipe_preferences else {},
            "last_updated": social_data.last_updated.isoformat()
        }
    
    def _get_default_social_profile(self) -> Dict[str, Any]:
        """Get default social cooking profile"""
        return {
            "cooking_for_others": False,
            "family_size": 1,
            "dietary_restrictions_family": [],
            "social_meal_preferences": {},
            "shared_recipe_preferences": {}
        }
    
    def _get_individual_recommendations(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        """Get recommendations for individual cooking"""
        try:
            foods = self.db.query(FoodItem).filter(
                FoodItem.cuisine_type.in_(["quick", "simple", "individual"])
            ).limit(limit).all()
            
            recommendations = []
            for food in foods:
                recommendations.append({
                    "food_id": food.id,
                    "name": food.name,
                    "reason": "Perfect for individual cooking"
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting individual recommendations: {e}")
            return []
    
    def _get_family_friendly_foods(self, restrictions: List[str], family_size: int, limit: int) -> List[Dict[str, Any]]:
        """Get family-friendly foods based on restrictions and size"""
        try:
            # Get foods that are family-friendly
            foods = self.db.query(FoodItem).filter(
                and_(
                    FoodItem.calories >= 200,  # Substantial enough for family
                    FoodItem.calories <= 500   # Not too heavy
                )
            ).limit(limit).all()
            
            recommendations = []
            for food in foods:
                recommendations.append({
                    "food_id": food.id,
                    "name": food.name,
                    "calories": food.calories,
                    "reason": f"Family-friendly option for {family_size} people"
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting family-friendly foods: {e}")
            return []
    
    def _analyze_cooking_frequency(self, meals: List[MealLog]) -> str:
        """Analyze how often user cooks"""
        if not meals:
            return "unknown"
        
        # Analyze meal logging frequency
        meal_count = len(meals)
        if meal_count >= 20:
            return "daily"
        elif meal_count >= 10:
            return "frequent"
        elif meal_count >= 5:
            return "moderate"
        else:
            return "occasional"
    
    def _analyze_family_cuisine_preferences(self, meals: List[MealLog]) -> List[str]:
        """Analyze family cuisine preferences"""
        if not meals:
            return []
        
        cuisine_counts = {}
        for meal in meals:
            if meal.food_item and meal.food_item.cuisine_type:
                cuisine = meal.food_item.cuisine_type
                cuisine_counts[cuisine] = cuisine_counts.get(cuisine, 0) + 1
        
        # Return top 3 cuisines
        sorted_cuisines = sorted(cuisine_counts.items(), key=lambda x: x[1], reverse=True)
        return [cuisine[0] for cuisine in sorted_cuisines[:3]]
    
    def _analyze_meal_timing(self, meals: List[MealLog]) -> Dict[str, Any]:
        """Analyze family meal timing patterns"""
        if not meals:
            return {"pattern": "no_data"}
        
        meal_times = [meal.logged_at.hour for meal in meals]
        meal_types = [meal.meal_type for meal in meals]
        
        return {
            "average_meal_time": round(sum(meal_times) / len(meal_times), 1),
            "most_common_meal_type": max(set(meal_types), key=meal_types.count),
            "meal_regularity": "regular" if len(set(meal_times)) < len(meal_times) * 0.5 else "irregular"
        }
    
    def _analyze_portion_patterns(self, meals: List[MealLog], family_size: int) -> Dict[str, Any]:
        """Analyze portion size patterns"""
        if not meals:
            return {"pattern": "no_data"}
        
        total_quantity = sum(meal.quantity for meal in meals)
        avg_quantity_per_meal = total_quantity / len(meals)
        
        return {
            "average_portion_size": round(avg_quantity_per_meal, 2),
            "portion_per_person": round(avg_quantity_per_meal / family_size, 2),
            "portion_adequacy": "adequate" if avg_quantity_per_meal / family_size >= 1.0 else "small"
        }
    
    def _analyze_dietary_accommodations(self, meals: List[MealLog], social_data: SocialCookingData) -> Dict[str, Any]:
        """Analyze how well dietary restrictions are accommodated"""
        if not social_data.dietary_restrictions_family:
            return {"accommodation_level": "no_restrictions"}
        
        family_restrictions = json.loads(social_data.dietary_restrictions_family)
        
        # Analyze if meals accommodate restrictions
        accommodated_meals = 0
        for meal in meals:
            if meal.food_item:
                # Simple check - in a real system, this would be more sophisticated
                food_tags = meal.food_item.tags.lower() if meal.food_item.tags else ""
                if any(restriction.lower() in food_tags for restriction in family_restrictions):
                    accommodated_meals += 1
        
        accommodation_rate = (accommodated_meals / len(meals)) * 100 if meals else 0
        
        return {
            "accommodation_rate": round(accommodation_rate, 1),
            "accommodation_level": "high" if accommodation_rate >= 70 else "medium" if accommodation_rate >= 40 else "low"
        }
    
    def _generate_shared_recipe_suggestions(self, occasion: str, social_data: SocialCookingData, 
                                          shared_preferences: Dict) -> List[Dict[str, Any]]:
        """Generate recipe suggestions for sharing"""
        suggestions = []
        
        # Base suggestions on occasion and family preferences
        if occasion == "family_dinner":
            suggestions.extend([
                {
                    "recipe_id": 1,
                    "title": "Family Pasta Night",
                    "reason": "Perfect for family dinners",
                    "serves": social_data.family_size
                },
                {
                    "recipe_id": 2,
                    "title": "Healthy Stir Fry",
                    "reason": "Quick and family-friendly",
                    "serves": social_data.family_size
                }
            ])
        elif occasion == "weekend_brunch":
            suggestions.extend([
                {
                    "recipe_id": 3,
                    "title": "Weekend Pancake Stack",
                    "reason": "Great for weekend family time",
                    "serves": social_data.family_size
                }
            ])
        
        return suggestions
