# app/services/food_rating_service.py
"""
Enhanced food rating service for better personalization
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.database import User, FoodItem, FoodRating, MealLog
from app.schemas import FoodRatingRequest, FoodRatingResponse

logger = logging.getLogger(__name__)

class FoodRatingService:
    """Service for managing food ratings and personalized recommendations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def rate_food(self, user_id: int, food_id: int, rating: float, review: str = None) -> Dict[str, Any]:
        """Rate a food item and update user preferences"""
        try:
            # Validate rating
            if not (1.0 <= rating <= 5.0):
                return {"success": False, "error": "Rating must be between 1.0 and 5.0"}
            
            # Check if food item exists
            food_item = self.db.query(FoodItem).filter(FoodItem.id == food_id).first()
            if not food_item:
                return {"success": False, "error": "Food item not found"}
            
            # Check if user has consumed this food
            user_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.food_item_id == food_id
                )
            ).first()
            
            if not user_meals:
                return {"success": False, "error": "You must have consumed this food to rate it"}
            
            # Check if user already rated this food
            existing_rating = self.db.query(FoodRating).filter(
                and_(
                    FoodRating.user_id == user_id,
                    FoodRating.food_id == food_id
                )
            ).first()
            
            if existing_rating:
                # Update existing rating
                existing_rating.rating = rating
                existing_rating.review = review
                existing_rating.created_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Updated food rating for user {user_id}, food {food_id}: {rating}")
            else:
                # Create new rating
                new_rating = FoodRating(
                    user_id=user_id,
                    food_id=food_id,
                    rating=rating,
                    review=review,
                    created_at=datetime.utcnow()
                )
                self.db.add(new_rating)
                self.db.commit()
                logger.info(f"Created new food rating for user {user_id}, food {food_id}: {rating}")
            
            # Update user preferences based on rating
            self._update_user_preferences(user_id, food_item, rating)
            
            return {
                "success": True,
                "message": "Food rated successfully",
                "rating": rating,
                "food_name": food_item.name
            }
            
        except Exception as e:
            logger.error(f"Error rating food: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_user_food_ratings(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all food ratings by a user"""
        try:
            ratings = self.db.query(FoodRating).join(FoodItem).filter(
                FoodRating.user_id == user_id
            ).order_by(desc(FoodRating.created_at)).limit(limit).all()
            
            result = []
            for rating in ratings:
                result.append({
                    "id": rating.id,
                    "food_id": rating.food_id,
                    "food_name": rating.food_item.name,
                    "rating": rating.rating,
                    "review": rating.review,
                    "created_at": rating.created_at.isoformat()
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user food ratings: {e}")
            return []
    
    def get_food_rating_stats(self, food_id: int) -> Dict[str, Any]:
        """Get rating statistics for a food item"""
        try:
            ratings = self.db.query(FoodRating).filter(FoodRating.food_id == food_id).all()
            
            if not ratings:
                return {
                    "food_id": food_id,
                    "average_rating": 0.0,
                    "total_ratings": 0,
                    "rating_distribution": {}
                }
            
            total_ratings = len(ratings)
            average_rating = sum(r.rating for r in ratings) / total_ratings
            
            # Rating distribution
            rating_dist = {}
            for i in range(1, 6):
                count = len([r for r in ratings if int(r.rating) == i])
                rating_dist[str(i)] = count
            
            return {
                "food_id": food_id,
                "average_rating": round(average_rating, 2),
                "total_ratings": total_ratings,
                "rating_distribution": rating_dist
            }
            
        except Exception as e:
            logger.error(f"Error getting food rating stats: {e}")
            return {"error": str(e)}
    
    def get_personalized_food_recommendations(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get personalized food recommendations based on user ratings"""
        try:
            # Get user's rating patterns
            user_ratings = self.db.query(FoodRating).filter(FoodRating.user_id == user_id).all()
            
            if not user_ratings:
                return self._get_default_recommendations()
            
            # Analyze user preferences
            preferences = self._analyze_user_preferences_from_ratings(user_ratings)
            
            # Find similar foods based on preferences
            recommendations = self._find_similar_foods(preferences, user_id, limit)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            return []
    
    def _update_user_preferences(self, user_id: int, food_item: FoodItem, rating: float):
        """Update user preferences based on food rating"""
        try:
            # This would update user's cuisine preferences, nutritional preferences, etc.
            # For now, we'll log the preference update
            logger.info(f"Updating preferences for user {user_id} based on {food_item.name} rating: {rating}")
            
            # In a more sophisticated system, this would:
            # 1. Update cuisine preferences based on highly-rated foods
            # 2. Update nutritional preferences based on macro patterns
            # 3. Update cooking preferences based on food complexity
            # 4. Update meal timing preferences
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
    
    def _analyze_user_preferences_from_ratings(self, ratings: List[FoodRating]) -> Dict[str, Any]:
        """Analyze user preferences from their ratings"""
        preferences = {
            "cuisine_preferences": {},
            "nutritional_preferences": {},
            "cooking_complexity_preferences": {},
            "average_rating": 0.0,
            "rating_pattern": {}
        }
        
        if not ratings:
            return preferences
        
        # Calculate average rating
        preferences["average_rating"] = sum(r.rating for r in ratings) / len(ratings)
        
        # Analyze highly-rated foods (rating >= 4.0)
        high_rated_foods = [r for r in ratings if r.rating >= 4.0]
        
        for rating in high_rated_foods:
            food = rating.food_item
            
            # Cuisine preferences
            if food.cuisine_type:
                cuisine = food.cuisine_type
                preferences["cuisine_preferences"][cuisine] = preferences["cuisine_preferences"].get(cuisine, 0) + 1
            
            # Nutritional preferences (simplified)
            if food.calories > 0:
                cal_range = "high" if food.calories > 300 else "medium" if food.calories > 150 else "low"
                preferences["nutritional_preferences"][cal_range] = preferences["nutritional_preferences"].get(cal_range, 0) + 1
        
        return preferences
    
    def _find_similar_foods(self, preferences: Dict[str, Any], user_id: int, limit: int) -> List[Dict[str, Any]]:
        """Find foods similar to user's preferences"""
        try:
            # Get user's already rated foods to exclude them
            rated_food_ids = [r.food_id for r in self.db.query(FoodRating).filter(FoodRating.user_id == user_id).all()]
            
            # Find foods with similar characteristics
            similar_foods = []
            
            # Prioritize by cuisine preferences
            top_cuisines = sorted(preferences["cuisine_preferences"].items(), key=lambda x: x[1], reverse=True)[:3]
            
            for cuisine, count in top_cuisines:
                foods = self.db.query(FoodItem).filter(
                    and_(
                        FoodItem.cuisine_type == cuisine,
                        ~FoodItem.id.in_(rated_food_ids)
                    )
                ).limit(limit // len(top_cuisines) if top_cuisines else limit).all()
                
                for food in foods:
                    similar_foods.append({
                        "food_id": food.id,
                        "name": food.name,
                        "cuisine_type": food.cuisine_type,
                        "calories": food.calories,
                        "reason": f"Similar to your preferred {cuisine} cuisine"
                    })
            
            return similar_foods[:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar foods: {e}")
            return []
    
    def _get_default_recommendations(self) -> List[Dict[str, Any]]:
        """Get default food recommendations when user has no ratings"""
        try:
            # Return popular foods with good ratings
            foods = self.db.query(FoodItem).limit(10).all()
            
            recommendations = []
            for food in foods:
                recommendations.append({
                    "food_id": food.id,
                    "name": food.name,
                    "cuisine_type": food.cuisine_type,
                    "calories": food.calories,
                    "reason": "Popular choice"
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting default recommendations: {e}")
            return []
