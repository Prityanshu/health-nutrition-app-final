"""
Automatic Challenge Updater Service
Automatically updates smart challenges based on user activity
"""

import logging
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Dict, Any, Optional

from app.database import MealLog, FoodItem
from app.models.enhanced_challenge_models import (
    PersonalizedChallenge, UserChallengeProgress, ChallengeType
)

logger = logging.getLogger(__name__)

class AutomaticChallengeUpdater:
    """Service to automatically update challenges based on user activity"""
    
    @staticmethod
    async def update_challenges_on_meal_log(
        user_id: int,
        meal_log: MealLog,
        food_item: FoodItem,
        db: Session
    ) -> Dict[str, Any]:
        """
        Automatically update relevant challenges when a meal is logged
        
        Args:
            user_id: The user's ID
            meal_log: The meal log entry
            food_item: The food item that was logged
            db: Database session
            
        Returns:
            Dictionary with update results
        """
        try:
            updated_challenges = []
            today = date.today()
            
            # Get all active challenges for this user
            active_challenges = db.query(PersonalizedChallenge).filter(
                and_(
                    PersonalizedChallenge.user_id == user_id,
                    PersonalizedChallenge.is_active == True,
                    PersonalizedChallenge.start_date <= datetime.now(),
                    PersonalizedChallenge.end_date >= datetime.now()
                )
            ).all()
            
            logger.info(f"Found {len(active_challenges)} active challenges for user {user_id}")
            
            for challenge in active_challenges:
                try:
                    challenge_updated = False
                    daily_value = 0.0
                    
                    # Handle different challenge types (using value comparison for enum)
                    challenge_type_value = challenge.challenge_type.value.upper() if hasattr(challenge.challenge_type, 'value') else str(challenge.challenge_type).upper()
                    logger.debug(f"Processing challenge '{challenge.title}' (Type: {challenge_type_value})")
                    
                    if challenge_type_value == 'NUTRITION':
                        challenge_updated, daily_value = AutomaticChallengeUpdater._handle_nutrition_challenge(
                            challenge, meal_log, food_item, user_id, today, db
                        )
                    
                    elif challenge_type_value == 'VARIETY':
                        challenge_updated, daily_value = AutomaticChallengeUpdater._handle_variety_challenge(
                            challenge, food_item, user_id, today, db
                        )
                    
                    elif challenge_type_value == 'CONSISTENCY':
                        challenge_updated, daily_value = AutomaticChallengeUpdater._handle_consistency_challenge(
                            challenge, user_id, today, db
                        )
                    
                    if challenge_updated:
                        updated_challenges.append({
                            "challenge_id": challenge.id,
                            "challenge_name": challenge.title,
                            "daily_value": daily_value,
                            "current_progress": challenge.current_value,
                            "completion_percentage": challenge.completion_percentage
                        })
                        logger.info(f"Updated challenge {challenge.id}: {challenge.title}")
                
                except Exception as e:
                    logger.error(f"Error updating challenge {challenge.id}: {e}")
                    continue
            
            # Commit all updates
            if updated_challenges:
                db.commit()
                logger.info(f"Successfully updated {len(updated_challenges)} challenges")
            
            return {
                "success": True,
                "updated_challenges": updated_challenges,
                "count": len(updated_challenges)
            }
            
        except Exception as e:
            logger.error(f"Error in automatic challenge update: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e),
                "updated_challenges": []
            }
    
    @staticmethod
    def _handle_nutrition_challenge(
        challenge: PersonalizedChallenge,
        meal_log: MealLog,
        food_item: FoodItem,
        user_id: int,
        today: date,
        db: Session
    ) -> tuple[bool, float]:
        """Handle nutrition-based challenges (protein, calories, etc.)"""
        try:
            daily_value = 0.0
            
            # Determine which nutritional metric to track
            challenge_name_lower = challenge.title.lower()
            challenge_desc_lower = challenge.description.lower() if challenge.description else ""
            combined_text = f"{challenge_name_lower} {challenge_desc_lower}"
            
            logger.debug(f"Checking nutrition challenge: '{challenge.title}'")
            
            if "protein" in combined_text:
                daily_value = meal_log.protein
                logger.debug(f"Protein challenge detected: +{daily_value}g")
            elif "calorie" in combined_text or "caloric" in combined_text:
                daily_value = meal_log.calories
                logger.debug(f"Calorie challenge detected: +{daily_value} cal")
            elif "carb" in combined_text:
                daily_value = meal_log.carbs
                logger.debug(f"Carb challenge detected: +{daily_value}g")
            elif "fiber" in combined_text:
                # Fiber needs to be tracked from food item
                daily_value = food_item.fiber_g if hasattr(food_item, 'fiber_g') else 0.0
                logger.debug(f"Fiber challenge detected: +{daily_value}g")
            elif "fat" in combined_text and "low" not in combined_text:
                daily_value = meal_log.fat
                logger.debug(f"Fat challenge detected: +{daily_value}g")
            else:
                # Generic nutrition challenge
                logger.debug(f"No matching nutrition metric found for '{challenge.title}'")
                return False, 0.0
            
            # Check if progress exists for today
            existing_progress = db.query(UserChallengeProgress).filter(
                and_(
                    UserChallengeProgress.challenge_id == challenge.id,
                    UserChallengeProgress.user_id == user_id,
                    func.date(UserChallengeProgress.progress_date) == today
                )
            ).first()
            
            if existing_progress:
                # Add to existing progress
                existing_progress.daily_value += daily_value
                existing_progress.completion_percentage = (
                    (existing_progress.daily_value / existing_progress.daily_target) * 100 
                    if existing_progress.daily_target > 0 else 0
                )
                existing_progress.nutrition_data = existing_progress.nutrition_data or {}
                existing_progress.nutrition_data['last_meal'] = {
                    'food': food_item.name,
                    'value': daily_value,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # Create new progress entry
                daily_target = challenge.target_value / 7  # Assuming 7-day challenges
                progress = UserChallengeProgress(
                    user_id=user_id,
                    challenge_id=challenge.id,
                    progress_date=datetime.now(),
                    daily_value=daily_value,
                    daily_target=daily_target,
                    completion_percentage=(daily_value / daily_target) * 100 if daily_target > 0 else 0,
                    nutrition_data={
                        'first_meal': food_item.name,
                        'value': daily_value,
                        'timestamp': datetime.now().isoformat()
                    }
                )
                db.add(progress)
            
            # Update challenge overall progress
            challenge.current_value += daily_value
            challenge.completion_percentage = (
                (challenge.current_value / challenge.target_value) * 100 
                if challenge.target_value > 0 else 0
            )
            
            # Check if challenge is completed
            if challenge.completion_percentage >= 100:
                challenge.is_active = False
                challenge.completion_date = datetime.now()
                logger.info(f"Challenge {challenge.id} completed!")
            
            return True, daily_value
            
        except Exception as e:
            logger.error(f"Error handling nutrition challenge: {e}")
            return False, 0.0
    
    @staticmethod
    def _handle_variety_challenge(
        challenge: PersonalizedChallenge,
        food_item: FoodItem,
        user_id: int,
        today: date,
        db: Session
    ) -> tuple[bool, float]:
        """Handle variety challenges (new foods, different cuisines)"""
        try:
            challenge_name_lower = challenge.title.lower()
            challenge_desc_lower = challenge.description.lower() if challenge.description else ""
            combined_text = f"{challenge_name_lower} {challenge_desc_lower}"
            
            logger.debug(f"Checking variety challenge: '{challenge.title}'")
            
            if "new" in combined_text or "different" in combined_text or "try" in combined_text or "explorer" in combined_text:
                # Check if this food was logged before the challenge started
                previous_logs_before_challenge = db.query(MealLog).filter(
                    and_(
                        MealLog.user_id == user_id,
                        MealLog.food_item_id == food_item.id,
                        MealLog.logged_at < challenge.start_date
                    )
                ).count()
                
                # Check if already counted during the challenge
                previous_logs_during_challenge = db.query(MealLog).filter(
                    and_(
                        MealLog.user_id == user_id,
                        MealLog.food_item_id == food_item.id,
                        MealLog.logged_at >= challenge.start_date,
                        MealLog.logged_at < datetime.now()
                    )
                ).count()
                
                # Only count if this is a new food (not logged before challenge and first time during challenge)
                if previous_logs_before_challenge == 0 and previous_logs_during_challenge == 0:
                    daily_value = 1.0  # One new food
                    
                    # Update or create progress for today
                    existing_progress = db.query(UserChallengeProgress).filter(
                        and_(
                            UserChallengeProgress.challenge_id == challenge.id,
                            UserChallengeProgress.user_id == user_id,
                            func.date(UserChallengeProgress.progress_date) == today
                        )
                    ).first()
                    
                    if existing_progress:
                        existing_progress.daily_value += daily_value
                        existing_progress.completion_percentage = (
                            (existing_progress.daily_value / existing_progress.daily_target) * 100 
                            if existing_progress.daily_target > 0 else 0
                        )
                    else:
                        daily_target = challenge.target_value / 7
                        progress = UserChallengeProgress(
                            user_id=user_id,
                            challenge_id=challenge.id,
                            progress_date=datetime.now(),
                            daily_value=daily_value,
                            daily_target=daily_target,
                            completion_percentage=(daily_value / daily_target) * 100 if daily_target > 0 else 0,
                            nutrition_data={'new_food': food_item.name}
                        )
                        db.add(progress)
                    
                    # Update challenge overall progress
                    challenge.current_value += daily_value
                    challenge.completion_percentage = (
                        (challenge.current_value / challenge.target_value) * 100 
                        if challenge.target_value > 0 else 0
                    )
                    
                    # Check if challenge is completed
                    if challenge.completion_percentage >= 100:
                        challenge.is_active = False
                        challenge.completion_date = datetime.now()
                    
                    return True, daily_value
            
            return False, 0.0
            
        except Exception as e:
            logger.error(f"Error handling variety challenge: {e}")
            return False, 0.0
    
    @staticmethod
    def _handle_consistency_challenge(
        challenge: PersonalizedChallenge,
        user_id: int,
        today: date,
        db: Session
    ) -> tuple[bool, float]:
        """Handle consistency challenges (logging meals daily)"""
        try:
            challenge_name_lower = challenge.title.lower()
            challenge_desc_lower = challenge.description.lower() if challenge.description else ""
            combined_text = f"{challenge_name_lower} {challenge_desc_lower}"
            
            logger.debug(f"Checking consistency challenge: '{challenge.title}'")
            
            if "log" in combined_text or "streak" in combined_text or "consecutive" in combined_text:
                # Check if we already counted today
                existing_progress = db.query(UserChallengeProgress).filter(
                    and_(
                        UserChallengeProgress.challenge_id == challenge.id,
                        UserChallengeProgress.user_id == user_id,
                        func.date(UserChallengeProgress.progress_date) == today
                    )
                ).first()
                
                if not existing_progress:
                    # First log of the day - count it
                    daily_value = 1.0  # One day logged
                    daily_target = 1.0  # Target is 1 day per day
                    
                    progress = UserChallengeProgress(
                        user_id=user_id,
                        challenge_id=challenge.id,
                        progress_date=datetime.now(),
                        daily_value=daily_value,
                        daily_target=daily_target,
                        completion_percentage=100.0,  # 100% for the day
                        nutrition_data={'logged': True}
                    )
                    db.add(progress)
                    
                    # Update challenge overall progress
                    challenge.current_value += daily_value
                    challenge.completion_percentage = (
                        (challenge.current_value / challenge.target_value) * 100 
                        if challenge.target_value > 0 else 0
                    )
                    
                    # Check if challenge is completed
                    if challenge.completion_percentage >= 100:
                        challenge.is_active = False
                        challenge.completion_date = datetime.now()
                    
                    return True, daily_value
            
            return False, 0.0
            
        except Exception as e:
            logger.error(f"Error handling consistency challenge: {e}")
            return False, 0.0

# Create global instance
automatic_challenge_updater = AutomaticChallengeUpdater()
