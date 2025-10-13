"""
Backfill Challenge Progress Script
Updates challenges for meals that were logged before the automatic update system was implemented
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, MealLog, FoodItem, User
from app.models.enhanced_challenge_models import PersonalizedChallenge, UserChallengeProgress
from app.services.automatic_challenge_updater import automatic_challenge_updater
from sqlalchemy import and_
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_challenges_for_user(user_id: int, db):
    """Backfill challenge progress for a specific user"""
    
    # Get all active challenges for this user
    active_challenges = db.query(PersonalizedChallenge).filter(
        and_(
            PersonalizedChallenge.user_id == user_id,
            PersonalizedChallenge.is_active == True,
            PersonalizedChallenge.end_date >= datetime.now()
        )
    ).all()
    
    if not active_challenges:
        logger.info(f"No active challenges found for user {user_id}")
        return
    
    logger.info(f"Found {len(active_challenges)} active challenges for user {user_id}")
    
    for challenge in active_challenges:
        logger.info(f"Processing challenge: {challenge.title}")
        
        # Get all meal logs during this challenge period
        meal_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.logged_at >= challenge.start_date,
                MealLog.logged_at <= datetime.now()
            )
        ).order_by(MealLog.logged_at).all()
        
        logger.info(f"  Found {len(meal_logs)} meal logs during challenge period")
        
        # Clear existing progress for this challenge (we'll rebuild it)
        db.query(UserChallengeProgress).filter(
            UserChallengeProgress.challenge_id == challenge.id
        ).delete()
        
        # Reset challenge progress
        challenge.current_value = 0.0
        challenge.completion_percentage = 0.0
        
        # Process each meal log
        updated_count = 0
        for meal_log in meal_logs:
            food_item = db.query(FoodItem).filter(FoodItem.id == meal_log.food_item_id).first()
            
            if food_item:
                result = await automatic_challenge_updater.update_challenges_on_meal_log(
                    user_id=user_id,
                    meal_log=meal_log,
                    food_item=food_item,
                    db=db
                )
                
                if result.get('success') and result.get('count') > 0:
                    updated_count += 1
        
        logger.info(f"  Updated challenge with {updated_count} meal logs")
        
    db.commit()
    logger.info(f"Backfill complete for user {user_id}")

async def main():
    """Main backfill function"""
    db = next(get_db())
    
    try:
        # Get all users with active challenges
        users_with_challenges = db.query(PersonalizedChallenge.user_id).filter(
            and_(
                PersonalizedChallenge.is_active == True,
                PersonalizedChallenge.end_date >= datetime.now()
            )
        ).distinct().all()
        
        user_ids = [u[0] for u in users_with_challenges]
        
        logger.info(f"Found {len(user_ids)} users with active challenges")
        logger.info(f"User IDs: {user_ids}")
        
        for user_id in user_ids:
            user = db.query(User).filter(User.id == user_id).first()
            logger.info(f"\\nBackfilling for user: {user.email if user else user_id}")
            await backfill_challenges_for_user(user_id, db)
        
        logger.info("\\n✅ Backfill complete for all users!")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
