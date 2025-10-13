"""
Fix Challenge Progress for User 6 - Version 2
Creates proper UserChallengeProgress entries
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, MealLog, FoodItem, User
from app.models.enhanced_challenge_models import PersonalizedChallenge, UserChallengeProgress
from sqlalchemy import and_, func
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Fix challenges for user 6 with proper progress entries"""
    db = next(get_db())
    
    try:
        # Get user 6
        user = db.query(User).filter(User.email == 'glitchiconicop@gmail.com').first()
        if not user:
            print("❌ User not found")
            return
        
        print(f"✅ User: {user.email} (ID: {user.id})\\n")
        
        # Get all meal logs grouped by date
        all_meals = db.query(MealLog).filter(
            MealLog.user_id == user.id
        ).order_by(MealLog.logged_at).all()
        
        # Group meals by date
        meals_by_date = {}
        for meal in all_meals:
            meal_date = meal.logged_at.date()
            if meal_date not in meals_by_date:
                meals_by_date[meal_date] = []
            meals_by_date[meal_date].append(meal)
        
        # Get unique food IDs over time
        foods_logged = []
        for meal in all_meals:
            if meal.food_item_id not in [f[0] for f in foods_logged]:
                foods_logged.append((meal.food_item_id, meal.logged_at.date()))
        
        print(f"📝 Meals by date:")
        for day, meals in sorted(meals_by_date.items()):
            print(f"  {day}: {len(meals)} meals")
        
        print(f"\\n🌈 Unique foods logged: {len(foods_logged)}")
        
        # Get active challenges
        challenges = db.query(PersonalizedChallenge).filter(
            PersonalizedChallenge.user_id == user.id
        ).all()
        
        print(f"\\n🎯 Updating Challenges:\\n")
        
        for challenge in challenges:
            # Delete existing progress
            db.query(UserChallengeProgress).filter(
                UserChallengeProgress.challenge_id == challenge.id
            ).delete()
            
            # Reset challenge
            challenge.current_value = 0.0
            challenge.completion_percentage = 0.0
            
            if 'Consistency' in challenge.title or 'Streak' in challenge.title:
                # Create progress entry for each unique day
                for day in sorted(meals_by_date.keys()):
                    if challenge.start_date.date() <= day <= challenge.end_date.date():
                        progress = UserChallengeProgress(
                            user_id=user.id,
                            challenge_id=challenge.id,
                            progress_date=datetime.combine(day, datetime.min.time()),
                            daily_value=1.0,
                            daily_target=1.0,
                            completion_percentage=100.0,
                            nutrition_data={'logged': True}
                        )
                        db.add(progress)
                        challenge.current_value += 1.0
                
                challenge.completion_percentage = (challenge.current_value / challenge.target_value) * 100 if challenge.target_value > 0 else 0
                print(f"✅ {challenge.title}: {challenge.current_value}/{challenge.target_value} days ({challenge.completion_percentage:.1f}%)")
            
            elif 'Explorer' in challenge.title or 'Try' in challenge.title:
                # Create progress entry for each new food
                days_with_new_foods = {}
                for food_id, day in foods_logged:
                    if challenge.start_date.date() <= day <= challenge.end_date.date():
                        if day not in days_with_new_foods:
                            days_with_new_foods[day] = 0
                        days_with_new_foods[day] += 1
                        challenge.current_value += 1.0
                
                # Create progress entries
                for day, count in days_with_new_foods.items():
                    progress = UserChallengeProgress(
                        user_id=user.id,
                        challenge_id=challenge.id,
                        progress_date=datetime.combine(day, datetime.min.time()),
                        daily_value=float(count),
                        daily_target=1.0,
                        completion_percentage=(count / 1.0) * 100,
                        nutrition_data={'new_foods_count': count}
                    )
                    db.add(progress)
                
                challenge.completion_percentage = (challenge.current_value / challenge.target_value) * 100 if challenge.target_value > 0 else 0
                print(f"✅ {challenge.title}: {challenge.current_value}/{challenge.target_value} foods ({challenge.completion_percentage:.1f}%)")
            
            elif 'Journey' in challenge.title:
                # Total meals challenge
                total_meals = len(all_meals)
                challenge.current_value = float(total_meals)
                challenge.completion_percentage = (challenge.current_value / challenge.target_value) * 100 if challenge.target_value > 0 else 0
                
                # Mark as completed if target reached
                if challenge.completion_percentage >= 100:
                    challenge.is_active = False
                
                print(f"✅ {challenge.title}: {challenge.current_value}/{challenge.target_value} meals ({challenge.completion_percentage:.1f}%)")
        
        db.commit()
        print(f"\\n🎉 All challenges updated with proper progress entries!")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
