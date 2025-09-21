# app/services/data_driven_challenge_generator.py
"""
Data-driven challenge generator that creates personalized challenges based on user behavior
"""
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
import statistics

from app.database import User, FoodItem, MealLog, FoodRating, Goal
from app.models.enhanced_challenge_models import (
    PersonalizedChallenge, ChallengeTemplate, UserChallengeProgress,
    ChallengeAchievement, ChallengeRecommendation, ChallengeType, ChallengeDifficulty
)

logger = logging.getLogger(__name__)

class DataDrivenChallengeGenerator:
    """Generate personalized challenges based on user data analysis"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_weekly_challenges(self, user_id: int) -> Dict[str, Any]:
        """Generate personalized challenges for the coming week"""
        
        try:
            # Analyze user data
            user_analysis = self._analyze_user_data(user_id)
            
            # Generate challenge recommendations
            recommendations = self._generate_challenge_recommendations(user_id, user_analysis)
            
            # Create active challenges
            active_challenges = self._create_active_challenges(user_id, recommendations)
            
            return {
                "success": True,
                "user_analysis": user_analysis,
                "recommendations": recommendations,
                "active_challenges": active_challenges,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating weekly challenges: {e}")
            return {"success": False, "error": str(e)}
    
    def _analyze_user_data(self, user_id: int) -> Dict[str, Any]:
        """Comprehensive analysis of user's nutrition and workout data"""
        
        # Get user's recent data (last 30 days)
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        # Nutrition analysis
        nutrition_analysis = self._analyze_nutrition_patterns(user_id, cutoff_date)
        
        # Workout analysis
        workout_analysis = self._analyze_workout_patterns(user_id, cutoff_date)
        
        # Consistency analysis
        consistency_analysis = self._analyze_consistency_patterns(user_id, cutoff_date)
        
        # Goal progress analysis
        goal_analysis = self._analyze_goal_progress(user_id)
        
        # Behavioral patterns
        behavioral_analysis = self._analyze_behavioral_patterns(user_id, cutoff_date)
        
        return {
            "nutrition": nutrition_analysis,
            "workout": workout_analysis,
            "consistency": consistency_analysis,
            "goals": goal_analysis,
            "behavioral": behavioral_analysis,
            "analysis_period_days": 30,
            "data_quality_score": self._calculate_data_quality_score(user_id, cutoff_date)
        }
    
    def _analyze_nutrition_patterns(self, user_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Analyze user's nutrition patterns"""
        
        meals = self.db.query(MealLog).join(FoodItem).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.logged_at >= cutoff_date
            )
        ).all()
        
        if not meals:
            return self._get_default_nutrition_analysis()
        
        # Daily nutrition aggregation
        daily_nutrition = {}
        for meal in meals:
            date = meal.logged_at.date()
            if date not in daily_nutrition:
                daily_nutrition[date] = {
                    'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
                    'fiber': 0, 'sodium': 0, 'sugar': 0, 'meal_count': 0
                }
            
            daily_nutrition[date]['calories'] += meal.calories
            daily_nutrition[date]['protein'] += meal.protein
            daily_nutrition[date]['carbs'] += meal.carbs
            daily_nutrition[date]['fat'] += meal.fat
            daily_nutrition[date]['fiber'] += meal.food_item.fiber_g * meal.quantity
            daily_nutrition[date]['sodium'] += meal.food_item.sodium_mg * meal.quantity
            daily_nutrition[date]['sugar'] += meal.food_item.sugar_g * meal.quantity
            daily_nutrition[date]['meal_count'] += 1
        
        # Calculate averages and patterns
        nutrition_values = list(daily_nutrition.values())
        
        avg_daily = {
            'calories': statistics.mean([d['calories'] for d in nutrition_values]),
            'protein': statistics.mean([d['protein'] for d in nutrition_values]),
            'carbs': statistics.mean([d['carbs'] for d in nutrition_values]),
            'fat': statistics.mean([d['fat'] for d in nutrition_values]),
            'fiber': statistics.mean([d['fiber'] for d in nutrition_values]),
            'sodium': statistics.mean([d['sodium'] for d in nutrition_values]),
            'sugar': statistics.mean([d['sugar'] for d in nutrition_values]),
            'meal_count': statistics.mean([d['meal_count'] for d in nutrition_values])
        }
        
        # Calculate consistency
        calorie_consistency = 1 - (statistics.stdev([d['calories'] for d in nutrition_values]) / avg_daily['calories'])
        meal_consistency = 1 - (statistics.stdev([d['meal_count'] for d in nutrition_values]) / avg_daily['meal_count'])
        
        # Analyze trends
        calorie_trend = self._calculate_trend([d['calories'] for d in nutrition_values])
        protein_trend = self._calculate_trend([d['protein'] for d in nutrition_values])
        
        # Identify weaknesses
        weaknesses = []
        if avg_daily['protein'] < 100:
            weaknesses.append("low_protein")
        if avg_daily['fiber'] < 25:
            weaknesses.append("low_fiber")
        if avg_daily['sodium'] > 2300:
            weaknesses.append("high_sodium")
        if avg_daily['sugar'] > 50:
            weaknesses.append("high_sugar")
        if calorie_consistency < 0.7:
            weaknesses.append("inconsistent_calories")
        if meal_consistency < 0.6:
            weaknesses.append("inconsistent_meals")
        
        return {
            "average_daily": avg_daily,
            "consistency": {
                "calorie_consistency": calorie_consistency,
                "meal_consistency": meal_consistency
            },
            "trends": {
                "calorie_trend": calorie_trend,
                "protein_trend": protein_trend
            },
            "weaknesses": weaknesses,
            "strengths": self._identify_nutrition_strengths(avg_daily, calorie_consistency, meal_consistency),
            "total_days_analyzed": len(daily_nutrition),
            "total_meals": len(meals)
        }
    
    def _analyze_workout_patterns(self, user_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Analyze user's workout patterns"""
        
        # This would integrate with your fitness tracking system
        # For now, we'll create a placeholder analysis
        
        # In a real implementation, you'd query workout data
        # workouts = self.db.query(WorkoutLog).filter(...)
        
        # Placeholder analysis based on available data
        return {
            "workout_frequency": "unknown",  # Would be calculated from workout data
            "workout_consistency": 0.5,
            "workout_intensity": "moderate",
            "weaknesses": ["inconsistent_workouts", "low_frequency"],
            "strengths": [],
            "recommendations": [
                "Try to work out at least 3 times per week",
                "Focus on consistency over intensity"
            ]
        }
    
    def _analyze_consistency_patterns(self, user_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Analyze user's consistency patterns"""
        
        meals = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.logged_at >= cutoff_date
            )
        ).all()
        
        if not meals:
            return self._get_default_consistency_analysis()
        
        # Analyze daily consistency
        daily_meal_counts = {}
        for meal in meals:
            date = meal.logged_at.date()
            daily_meal_counts[date] = daily_meal_counts.get(date, 0) + 1
        
        # Calculate consistency metrics
        total_days = len(daily_meal_counts)
        days_with_meals = len([d for d in daily_meal_counts.values() if d > 0])
        consistency_rate = days_with_meals / total_days if total_days > 0 else 0
        
        # Analyze meal timing consistency
        meal_times = [meal.logged_at.hour for meal in meals]
        breakfast_times = [h for h in meal_times if 6 <= h <= 10]
        lunch_times = [h for h in meal_times if 11 <= h <= 14]
        dinner_times = [h for h in meal_times if 17 <= h <= 21]
        
        timing_consistency = {
            "breakfast": 1 - (statistics.stdev(breakfast_times) / 24) if breakfast_times else 0,
            "lunch": 1 - (statistics.stdev(lunch_times) / 24) if lunch_times else 0,
            "dinner": 1 - (statistics.stdev(dinner_times) / 24) if dinner_times else 0
        }
        
        return {
            "daily_consistency": consistency_rate,
            "timing_consistency": timing_consistency,
            "average_meals_per_day": statistics.mean(daily_meal_counts.values()) if daily_meal_counts else 0,
            "total_days_logged": total_days,
            "weaknesses": self._identify_consistency_weaknesses(consistency_rate, timing_consistency),
            "strengths": self._identify_consistency_strengths(consistency_rate, timing_consistency)
        }
    
    def _analyze_goal_progress(self, user_id: int) -> Dict[str, Any]:
        """Analyze user's progress toward goals"""
        
        goals = self.db.query(Goal).filter(
            and_(
                Goal.user_id == user_id,
                Goal.is_active == True
            )
        ).all()
        
        if not goals:
            return {"active_goals": 0, "progress": [], "weaknesses": [], "strengths": []}
        
        progress_analysis = []
        for goal in goals:
            # Calculate progress (simplified)
            progress_percentage = 0.5  # Would be calculated based on actual progress
            progress_analysis.append({
                "goal_type": goal.goal_type,
                "progress_percentage": progress_percentage,
                "is_on_track": progress_percentage > 0.7
            })
        
        return {
            "active_goals": len(goals),
            "progress": progress_analysis,
            "weaknesses": [g["goal_type"] for g in progress_analysis if not g["is_on_track"]],
            "strengths": [g["goal_type"] for g in progress_analysis if g["is_on_track"]]
        }
    
    def _analyze_behavioral_patterns(self, user_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Analyze user's behavioral patterns"""
        
        meals = self.db.query(MealLog).join(FoodItem).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.logged_at >= cutoff_date
            )
        ).all()
        
        if not meals:
            return self._get_default_behavioral_analysis()
        
        # Analyze variety
        unique_foods = len(set(meal.food_item_id for meal in meals))
        variety_score = unique_foods / len(meals) if meals else 0
        
        # Analyze cuisine preferences
        cuisine_counts = {}
        for meal in meals:
            if meal.food_item and meal.food_item.cuisine_type:
                cuisine = meal.food_item.cuisine_type
                cuisine_counts[cuisine] = cuisine_counts.get(cuisine, 0) + 1
        
        # Analyze meal planning
        planned_meals = len([meal for meal in meals if meal.planned])
        planning_rate = planned_meals / len(meals) if meals else 0
        
        return {
            "variety_score": variety_score,
            "cuisine_diversity": len(cuisine_counts),
            "planning_rate": planning_rate,
            "weaknesses": self._identify_behavioral_weaknesses(variety_score, planning_rate),
            "strengths": self._identify_behavioral_strengths(variety_score, planning_rate)
        }
    
    def _generate_challenge_recommendations(self, user_id: int, user_analysis: Dict) -> List[Dict[str, Any]]:
        """Generate personalized challenge recommendations"""
        
        recommendations = []
        
        # Nutrition-based challenges
        nutrition_weaknesses = user_analysis["nutrition"]["weaknesses"]
        if "low_protein" in nutrition_weaknesses:
            recommendations.append(self._create_protein_challenge(user_analysis))
        if "low_fiber" in nutrition_weaknesses:
            recommendations.append(self._create_fiber_challenge(user_analysis))
        if "inconsistent_meals" in nutrition_weaknesses:
            recommendations.append(self._create_meal_consistency_challenge(user_analysis))
        
        # Consistency-based challenges
        consistency_weaknesses = user_analysis["consistency"]["weaknesses"]
        if "daily_consistency" in consistency_weaknesses:
            recommendations.append(self._create_daily_logging_challenge(user_analysis))
        
        # Variety-based challenges
        behavioral_weaknesses = user_analysis["behavioral"]["weaknesses"]
        if "low_variety" in behavioral_weaknesses:
            recommendations.append(self._create_variety_challenge(user_analysis))
        
        # Goal-oriented challenges
        goal_weaknesses = user_analysis["goals"]["weaknesses"]
        for goal_type in goal_weaknesses:
            recommendations.append(self._create_goal_challenge(user_analysis, goal_type))
        
        return recommendations
    
    def _create_protein_challenge(self, user_analysis: Dict) -> Dict[str, Any]:
        """Create a protein-focused challenge"""
        
        current_protein = user_analysis["nutrition"]["average_daily"]["protein"]
        target_protein = max(120, current_protein * 1.2)  # 20% increase
        
        return {
            "challenge_type": ChallengeType.NUTRITION,
            "difficulty": ChallengeDifficulty.MEDIUM,
            "title": "Protein Power Week",
            "description": f"Increase your daily protein intake to {target_protein:.0f}g per day",
            "target_value": target_protein,
            "unit": "grams",
            "duration_days": 7,
            "baseline_data": {"current_protein": current_protein},
            "target_improvement": 20,
            "personalization_factors": {
                "based_on": "low_protein_intake",
                "current_level": current_protein,
                "improvement_needed": target_protein - current_protein
            },
            "points_reward": 150,
            "badge_reward": "protein_power",
            "motivational_messages": [
                "Protein helps build and repair muscles!",
                "You're getting stronger with every gram!",
                "Your body will thank you for the protein boost!"
            ]
        }
    
    def _create_fiber_challenge(self, user_analysis: Dict) -> Dict[str, Any]:
        """Create a fiber-focused challenge"""
        
        current_fiber = user_analysis["nutrition"]["average_daily"]["fiber"]
        target_fiber = max(30, current_fiber * 1.3)  # 30% increase
        
        return {
            "challenge_type": ChallengeType.NUTRITION,
            "difficulty": ChallengeDifficulty.EASY,
            "title": "Fiber Fuel Challenge",
            "description": f"Boost your daily fiber intake to {target_fiber:.0f}g per day",
            "target_value": target_fiber,
            "unit": "grams",
            "duration_days": 7,
            "baseline_data": {"current_fiber": current_fiber},
            "target_improvement": 30,
            "personalization_factors": {
                "based_on": "low_fiber_intake",
                "current_level": current_fiber,
                "improvement_needed": target_fiber - current_fiber
            },
            "points_reward": 100,
            "badge_reward": "fiber_champion",
            "motivational_messages": [
                "Fiber keeps your digestive system happy!",
                "More fiber = more energy throughout the day!",
                "Your gut health is improving with every gram!"
            ]
        }
    
    def _create_meal_consistency_challenge(self, user_analysis: Dict) -> Dict[str, Any]:
        """Create a meal consistency challenge"""
        
        current_consistency = user_analysis["consistency"]["daily_consistency"]
        target_consistency = min(0.9, current_consistency + 0.2)  # 20% improvement
        
        return {
            "challenge_type": ChallengeType.CONSISTENCY,
            "difficulty": ChallengeDifficulty.MEDIUM,
            "title": "Daily Logging Streak",
            "description": f"Log meals {target_consistency*100:.0f}% of days this week",
            "target_value": target_consistency,
            "unit": "percentage",
            "duration_days": 7,
            "baseline_data": {"current_consistency": current_consistency},
            "target_improvement": 20,
            "personalization_factors": {
                "based_on": "inconsistent_meal_logging",
                "current_level": current_consistency,
                "improvement_needed": target_consistency - current_consistency
            },
            "points_reward": 120,
            "badge_reward": "consistency_king",
            "motivational_messages": [
                "Consistency is the key to success!",
                "Every logged meal brings you closer to your goals!",
                "You're building a healthy habit!"
            ]
        }
    
    def _create_daily_logging_challenge(self, user_analysis: Dict) -> Dict[str, Any]:
        """Create a daily logging challenge"""
        
        return {
            "challenge_type": ChallengeType.CONSISTENCY,
            "difficulty": ChallengeDifficulty.EASY,
            "title": "7-Day Logging Streak",
            "description": "Log at least one meal every day for 7 days",
            "target_value": 7,
            "unit": "days",
            "duration_days": 7,
            "baseline_data": {"current_streak": 0},
            "target_improvement": 100,
            "personalization_factors": {
                "based_on": "low_daily_consistency",
                "current_level": 0,
                "improvement_needed": 7
            },
            "points_reward": 100,
            "badge_reward": "streak_starter",
            "motivational_messages": [
                "Start your logging streak today!",
                "One meal at a time, one day at a time!",
                "You're building a powerful habit!"
            ]
        }
    
    def _create_variety_challenge(self, user_analysis: Dict) -> Dict[str, Any]:
        """Create a variety challenge"""
        
        current_variety = user_analysis["behavioral"]["variety_score"]
        target_variety = min(0.8, current_variety + 0.2)  # 20% improvement
        
        return {
            "challenge_type": ChallengeType.VARIETY,
            "difficulty": ChallengeDifficulty.MEDIUM,
            "title": "Food Explorer Challenge",
            "description": f"Try {int(target_variety * 10)} different foods this week",
            "target_value": int(target_variety * 10),
            "unit": "unique_foods",
            "duration_days": 7,
            "baseline_data": {"current_variety": current_variety},
            "target_improvement": 20,
            "personalization_factors": {
                "based_on": "low_food_variety",
                "current_level": current_variety,
                "improvement_needed": target_variety - current_variety
            },
            "points_reward": 130,
            "badge_reward": "food_explorer",
            "motivational_messages": [
                "Discover new flavors and nutrients!",
                "Variety is the spice of life!",
                "Your taste buds will thank you!"
            ]
        }
    
    def _create_goal_challenge(self, user_analysis: Dict, goal_type: str) -> Dict[str, Any]:
        """Create a goal-oriented challenge"""
        
        goal_challenges = {
            "weight_loss": {
                "title": "Calorie Control Week",
                "description": "Stay within your calorie target for 7 days",
                "target_value": 7,
                "unit": "days"
            },
            "muscle_gain": {
                "title": "Protein Power Week",
                "description": "Hit your protein target for 7 days",
                "target_value": 7,
                "unit": "days"
            },
            "maintenance": {
                "title": "Balance Master Week",
                "description": "Maintain balanced nutrition for 7 days",
                "target_value": 7,
                "unit": "days"
            }
        }
        
        challenge_data = goal_challenges.get(goal_type, goal_challenges["maintenance"])
        
        return {
            "challenge_type": ChallengeType.GOAL_ORIENTED,
            "difficulty": ChallengeDifficulty.HARD,
            "title": challenge_data["title"],
            "description": challenge_data["description"],
            "target_value": challenge_data["target_value"],
            "unit": challenge_data["unit"],
            "duration_days": 7,
            "baseline_data": {"goal_type": goal_type},
            "target_improvement": 100,
            "personalization_factors": {
                "based_on": f"goal_progress_{goal_type}",
                "goal_type": goal_type,
                "improvement_needed": 7
            },
            "points_reward": 200,
            "badge_reward": f"goal_{goal_type}_master",
            "motivational_messages": [
                f"You're working toward your {goal_type} goal!",
                "Every day counts toward your success!",
                "You're closer to your goal than you think!"
            ]
        }
    
    def _create_active_challenges(self, user_id: int, recommendations: List[Dict]) -> List[Dict[str, Any]]:
        """Create active challenges from recommendations"""
        
        active_challenges = []
        
        for rec in recommendations[:3]:  # Limit to 3 active challenges
            # Create personalized challenge
            challenge = PersonalizedChallenge(
                user_id=user_id,
                challenge_type=rec["challenge_type"],
                difficulty=rec["difficulty"],
                title=rec["title"],
                description=rec["description"],
                target_value=rec["target_value"],
                unit=rec["unit"],
                baseline_data=rec["baseline_data"],
                target_improvement=rec["target_improvement"],
                personalization_factors=rec["personalization_factors"],
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=rec["duration_days"]),
                points_reward=rec["points_reward"],
                badge_reward=rec["badge_reward"],
                motivational_messages=rec["motivational_messages"],
                daily_targets=self._calculate_daily_targets(rec),
                progress_history=[],
                completion_percentage=0.0
            )
            
            self.db.add(challenge)
            self.db.commit()
            
            active_challenges.append({
                "challenge_id": challenge.id,
                "title": challenge.title,
                "description": challenge.description,
                "target_value": challenge.target_value,
                "unit": challenge.unit,
                "end_date": challenge.end_date.isoformat(),
                "points_reward": challenge.points_reward,
                "badge_reward": challenge.badge_reward
            })
        
        return active_challenges
    
    def _calculate_daily_targets(self, recommendation: Dict) -> List[Dict[str, Any]]:
        """Calculate daily targets for a challenge"""
        
        duration_days = recommendation["duration_days"]
        target_value = recommendation["target_value"]
        unit = recommendation["unit"]
        
        daily_targets = []
        for day in range(duration_days):
            if unit == "days":
                daily_target = 1 if day < target_value else 0
            else:
                daily_target = target_value / duration_days
            
            daily_targets.append({
                "day": day + 1,
                "target": daily_target,
                "achieved": False,
                "value": 0.0
            })
        
        return daily_targets
    
    def _calculate_data_quality_score(self, user_id: int, cutoff_date: datetime) -> float:
        """Calculate data quality score for user"""
        
        # Get data points
        meal_count = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.logged_at >= cutoff_date
            )
        ).count()
        
        rating_count = self.db.query(FoodRating).filter(
            and_(
                FoodRating.user_id == user_id,
                FoodRating.created_at >= cutoff_date
            )
        ).count()
        
        # Calculate score
        meal_score = min(1.0, meal_count / 30)  # 30 meals = full score
        rating_score = min(1.0, rating_count / 15)  # 15 ratings = full score
        
        return (meal_score * 0.7) + (rating_score * 0.3)
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend in values"""
        if len(values) < 2:
            return "stable"
        
        # Simple linear trend calculation
        x = list(range(len(values)))
        slope = (len(values) * sum(x[i] * values[i] for i in range(len(values))) - 
                sum(x) * sum(values)) / (len(values) * sum(x[i]**2 for i in range(len(values))) - sum(x)**2)
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _identify_nutrition_strengths(self, avg_daily: Dict, calorie_consistency: float, meal_consistency: float) -> List[str]:
        """Identify nutrition strengths"""
        strengths = []
        
        if avg_daily["protein"] >= 100:
            strengths.append("high_protein")
        if avg_daily["fiber"] >= 25:
            strengths.append("high_fiber")
        if calorie_consistency >= 0.8:
            strengths.append("consistent_calories")
        if meal_consistency >= 0.8:
            strengths.append("consistent_meals")
        
        return strengths
    
    def _identify_consistency_weaknesses(self, consistency_rate: float, timing_consistency: Dict) -> List[str]:
        """Identify consistency weaknesses"""
        weaknesses = []
        
        if consistency_rate < 0.7:
            weaknesses.append("daily_consistency")
        if timing_consistency["breakfast"] < 0.6:
            weaknesses.append("breakfast_timing")
        if timing_consistency["lunch"] < 0.6:
            weaknesses.append("lunch_timing")
        if timing_consistency["dinner"] < 0.6:
            weaknesses.append("dinner_timing")
        
        return weaknesses
    
    def _identify_consistency_strengths(self, consistency_rate: float, timing_consistency: Dict) -> List[str]:
        """Identify consistency strengths"""
        strengths = []
        
        if consistency_rate >= 0.8:
            strengths.append("daily_consistency")
        if timing_consistency["breakfast"] >= 0.8:
            strengths.append("breakfast_timing")
        if timing_consistency["lunch"] >= 0.8:
            strengths.append("lunch_timing")
        if timing_consistency["dinner"] >= 0.8:
            strengths.append("dinner_timing")
        
        return strengths
    
    def _identify_behavioral_weaknesses(self, variety_score: float, planning_rate: float) -> List[str]:
        """Identify behavioral weaknesses"""
        weaknesses = []
        
        if variety_score < 0.5:
            weaknesses.append("low_variety")
        if planning_rate < 0.5:
            weaknesses.append("low_planning")
        
        return weaknesses
    
    def _identify_behavioral_strengths(self, variety_score: float, planning_rate: float) -> List[str]:
        """Identify behavioral strengths"""
        strengths = []
        
        if variety_score >= 0.7:
            strengths.append("high_variety")
        if planning_rate >= 0.7:
            strengths.append("high_planning")
        
        return strengths
    
    def _get_default_nutrition_analysis(self) -> Dict[str, Any]:
        """Get default nutrition analysis for new users"""
        return {
            "average_daily": {
                "calories": 2000, "protein": 100, "carbs": 250, "fat": 65,
                "fiber": 25, "sodium": 2300, "sugar": 50, "meal_count": 3
            },
            "consistency": {"calorie_consistency": 0.5, "meal_consistency": 0.5},
            "trends": {"calorie_trend": "stable", "protein_trend": "stable"},
            "weaknesses": ["low_protein", "low_fiber", "inconsistent_meals"],
            "strengths": [],
            "total_days_analyzed": 0,
            "total_meals": 0
        }
    
    def _get_default_consistency_analysis(self) -> Dict[str, Any]:
        """Get default consistency analysis for new users"""
        return {
            "daily_consistency": 0.0,
            "timing_consistency": {"breakfast": 0.0, "lunch": 0.0, "dinner": 0.0},
            "average_meals_per_day": 0.0,
            "total_days_logged": 0,
            "weaknesses": ["daily_consistency", "breakfast_timing", "lunch_timing", "dinner_timing"],
            "strengths": []
        }
    
    def _get_default_behavioral_analysis(self) -> Dict[str, Any]:
        """Get default behavioral analysis for new users"""
        return {
            "variety_score": 0.0,
            "cuisine_diversity": 0,
            "planning_rate": 0.0,
            "weaknesses": ["low_variety", "low_planning"],
            "strengths": []
        }
