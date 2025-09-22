# app/services/recipe_interaction_service.py
"""
Recipe interaction tracking service for enhanced personalization
"""
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models.enhanced_models import RecipeInteraction, UserCookingPattern
from app.database import User, Recipe

logger = logging.getLogger(__name__)

class RecipeInteractionService:
    """Service for tracking recipe interactions and improving recommendations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def track_recipe_interaction(self, user_id: int, recipe_id: int, interaction_type: str, 
                                interaction_data: Dict = None) -> Dict[str, Any]:
        """Track user interaction with a recipe"""
        try:
            # Validate interaction type
            valid_interactions = ["viewed", "cooked", "rated", "saved", "shared", "favorited"]
            if interaction_type not in valid_interactions:
                return {"success": False, "error": f"Invalid interaction type. Must be one of: {valid_interactions}"}
            
            # Create interaction record
            interaction = RecipeInteraction(
                user_id=user_id,
                recipe_id=recipe_id,
                interaction_type=interaction_type,
                interaction_data=json.dumps(interaction_data) if interaction_data else None,
                created_at=datetime.utcnow()
            )
            
            self.db.add(interaction)
            self.db.commit()
            
            logger.info(f"Tracked {interaction_type} interaction for user {user_id}, recipe {recipe_id}")
            
            # Update user cooking patterns based on interaction
            self._update_cooking_patterns(user_id, interaction_type, interaction_data)
            
            return {
                "success": True,
                "message": f"Recipe {interaction_type} tracked successfully",
                "interaction_id": interaction.id
            }
            
        except Exception as e:
            logger.error(f"Error tracking recipe interaction: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_user_recipe_interactions(self, user_id: int, interaction_type: str = None, 
                                   limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's recipe interactions"""
        try:
            query = self.db.query(RecipeInteraction).filter(RecipeInteraction.user_id == user_id)
            
            if interaction_type:
                query = query.filter(RecipeInteraction.interaction_type == interaction_type)
            
            interactions = query.order_by(desc(RecipeInteraction.created_at)).limit(limit).all()
            
            result = []
            for interaction in interactions:
                result.append({
                    "id": interaction.id,
                    "recipe_id": interaction.recipe_id,
                    "interaction_type": interaction.interaction_type,
                    "interaction_data": json.loads(interaction.interaction_data) if interaction.interaction_data else None,
                    "created_at": interaction.created_at.isoformat()
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user recipe interactions: {e}")
            return []
    
    def get_recipe_popularity_stats(self, recipe_id: int) -> Dict[str, Any]:
        """Get popularity statistics for a recipe"""
        try:
            interactions = self.db.query(RecipeInteraction).filter(
                RecipeInteraction.recipe_id == recipe_id
            ).all()
            
            if not interactions:
                return {
                    "recipe_id": recipe_id,
                    "total_interactions": 0,
                    "interaction_types": {}
                }
            
            # Count interaction types
            interaction_types = {}
            for interaction in interactions:
                interaction_types[interaction.interaction_type] = interaction_types.get(interaction.interaction_type, 0) + 1
            
            return {
                "recipe_id": recipe_id,
                "total_interactions": len(interactions),
                "interaction_types": interaction_types,
                "popularity_score": self._calculate_popularity_score(interactions)
            }
            
        except Exception as e:
            logger.error(f"Error getting recipe popularity stats: {e}")
            return {"error": str(e)}
    
    def get_personalized_recipe_recommendations(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get personalized recipe recommendations based on user interactions"""
        try:
            # Get user's interaction patterns
            user_interactions = self.db.query(RecipeInteraction).filter(
                RecipeInteraction.user_id == user_id
            ).all()
            
            if not user_interactions:
                return self._get_default_recipe_recommendations()
            
            # Analyze user preferences from interactions
            preferences = self._analyze_interaction_preferences(user_interactions)
            
            # Find similar recipes
            recommendations = self._find_similar_recipes(preferences, user_id, limit)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting personalized recipe recommendations: {e}")
            return []
    
    def get_cooking_behavior_insights(self, user_id: int) -> Dict[str, Any]:
        """Get insights about user's cooking behavior"""
        try:
            # Get cooking pattern
            cooking_pattern = self.db.query(UserCookingPattern).filter(
                UserCookingPattern.user_id == user_id
            ).first()
            
            # Get interaction statistics
            interactions = self.db.query(RecipeInteraction).filter(
                RecipeInteraction.user_id == user_id
            ).all()
            
            # Analyze behavior patterns
            behavior_insights = {
                "cooking_frequency": cooking_pattern.cooking_frequency if cooking_pattern else "unknown",
                "skill_level": cooking_pattern.cooking_skill_level if cooking_pattern else "unknown",
                "total_recipes_interacted": len(interactions),
                "favorite_interaction_types": self._get_favorite_interaction_types(interactions),
                "cooking_trends": self._analyze_cooking_trends(interactions),
                "engagement_score": self._calculate_engagement_score(interactions)
            }
            
            return behavior_insights
            
        except Exception as e:
            logger.error(f"Error getting cooking behavior insights: {e}")
            return {"error": str(e)}
    
    def _update_cooking_patterns(self, user_id: int, interaction_type: str, interaction_data: Dict):
        """Update user cooking patterns based on interactions"""
        try:
            cooking_pattern = self.db.query(UserCookingPattern).filter(
                UserCookingPattern.user_id == user_id
            ).first()
            
            if not cooking_pattern:
                # Create new cooking pattern
                cooking_pattern = UserCookingPattern(
                    user_id=user_id,
                    last_updated=datetime.utcnow()
                )
                self.db.add(cooking_pattern)
            
            # Update patterns based on interaction type
            if interaction_type == "cooked":
                # Increase cooking frequency
                if cooking_pattern.cooking_frequency == "rarely":
                    cooking_pattern.cooking_frequency = "weekly"
                elif cooking_pattern.cooking_frequency == "weekly":
                    cooking_pattern.cooking_frequency = "daily"
            
            elif interaction_type == "saved" or interaction_type == "favorited":
                # User is interested in meal planning
                cooking_pattern.meal_prep_preference = True
            
            cooking_pattern.last_updated = datetime.utcnow()
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating cooking patterns: {e}")
    
    def _calculate_popularity_score(self, interactions: List[RecipeInteraction]) -> float:
        """Calculate popularity score for a recipe"""
        if not interactions:
            return 0.0
        
        # Weight different interaction types
        weights = {
            "viewed": 1.0,
            "saved": 2.0,
            "cooked": 3.0,
            "rated": 2.5,
            "shared": 4.0,
            "favorited": 3.5
        }
        
        total_score = 0.0
        for interaction in interactions:
            total_score += weights.get(interaction.interaction_type, 1.0)
        
        return round(total_score / len(interactions), 2)
    
    def _analyze_interaction_preferences(self, interactions: List[RecipeInteraction]) -> Dict[str, Any]:
        """Analyze user preferences from recipe interactions"""
        preferences = {
            "preferred_interaction_types": {},
            "cooking_frequency": "low",
            "engagement_level": "low"
        }
        
        if not interactions:
            return preferences
        
        # Count interaction types
        for interaction in interactions:
            interaction_type = interaction.interaction_type
            preferences["preferred_interaction_types"][interaction_type] = preferences["preferred_interaction_types"].get(interaction_type, 0) + 1
        
        # Determine cooking frequency based on "cooked" interactions
        cooked_count = preferences["preferred_interaction_types"].get("cooked", 0)
        if cooked_count > 10:
            preferences["cooking_frequency"] = "high"
        elif cooked_count > 5:
            preferences["cooking_frequency"] = "medium"
        
        # Determine engagement level
        total_interactions = len(interactions)
        if total_interactions > 20:
            preferences["engagement_level"] = "high"
        elif total_interactions > 10:
            preferences["engagement_level"] = "medium"
        
        return preferences
    
    def _find_similar_recipes(self, preferences: Dict[str, Any], user_id: int, limit: int) -> List[Dict[str, Any]]:
        """Find recipes similar to user's preferences"""
        try:
            # Get user's already interacted recipes to exclude them
            interacted_recipe_ids = [
                r.recipe_id for r in self.db.query(RecipeInteraction).filter(
                    RecipeInteraction.user_id == user_id
                ).all()
            ]
            
            # For now, return popular recipes (in a real system, this would be more sophisticated)
            recipes = self.db.query(Recipe).filter(
                ~Recipe.id.in_(interacted_recipe_ids)
            ).limit(limit).all()
            
            recommendations = []
            for recipe in recipes:
                recommendations.append({
                    "recipe_id": recipe.id,
                    "title": recipe.title,
                    "reason": "Based on your cooking preferences"
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error finding similar recipes: {e}")
            return []
    
    def _get_default_recipe_recommendations(self) -> List[Dict[str, Any]]:
        """Get default recipe recommendations"""
        return [
            {
                "recipe_id": 1,
                "title": "Quick Healthy Breakfast",
                "reason": "Popular starter recipe"
            },
            {
                "recipe_id": 2,
                "title": "Easy Lunch Bowl",
                "reason": "Beginner-friendly option"
            }
        ]
    
    def _get_favorite_interaction_types(self, interactions: List[RecipeInteraction]) -> List[str]:
        """Get user's favorite interaction types"""
        if not interactions:
            return []
        
        interaction_counts = {}
        for interaction in interactions:
            interaction_counts[interaction.interaction_type] = interaction_counts.get(interaction.interaction_type, 0) + 1
        
        # Return top 3 interaction types
        sorted_interactions = sorted(interaction_counts.items(), key=lambda x: x[1], reverse=True)
        return [interaction[0] for interaction in sorted_interactions[:3]]
    
    def _analyze_cooking_trends(self, interactions: List[RecipeInteraction]) -> Dict[str, Any]:
        """Analyze cooking trends over time"""
        if not interactions:
            return {"trend": "no_data"}
        
        # Group interactions by week
        weekly_interactions = {}
        for interaction in interactions:
            week = interaction.created_at.isocalendar()[:2]  # (year, week)
            weekly_interactions[week] = weekly_interactions.get(week, 0) + 1
        
        if len(weekly_interactions) < 2:
            return {"trend": "insufficient_data"}
        
        # Calculate trend
        weeks = sorted(weekly_interactions.keys())
        recent_weeks = weeks[-2:]
        if len(recent_weeks) == 2:
            recent_avg = weekly_interactions[recent_weeks[1]]
            previous_avg = weekly_interactions[recent_weeks[0]]
            
            if recent_avg > previous_avg * 1.2:
                return {"trend": "increasing"}
            elif recent_avg < previous_avg * 0.8:
                return {"trend": "decreasing"}
            else:
                return {"trend": "stable"}
        
        return {"trend": "stable"}
    
    def _calculate_engagement_score(self, interactions: List[RecipeInteraction]) -> float:
        """Calculate user engagement score"""
        if not interactions:
            return 0.0
        
        # Weight different interaction types
        weights = {
            "viewed": 1.0,
            "saved": 2.0,
            "cooked": 3.0,
            "rated": 2.5,
            "shared": 4.0,
            "favorited": 3.5
        }
        
        total_score = 0.0
        for interaction in interactions:
            total_score += weights.get(interaction.interaction_type, 1.0)
        
        # Normalize to 0-100 scale
        max_possible_score = len(interactions) * 4.0  # Assuming max weight is 4.0
        engagement_score = (total_score / max_possible_score) * 100 if max_possible_score > 0 else 0
        
        return round(engagement_score, 1)
