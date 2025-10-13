"""
Fix Challenge Progress for User 6 (glitchiconicop@gmail.com)
Manually updates challenges based on existing meal logs
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
    """Fix challenges for user 6"""
    db = next(get_db())
    
    try:
        # Get user 6
        user = db.query(User).filter(User.email == 'glitchiconicop@gmail.com').first()
        if not user:
            print("❌ User not found")
            return
        
        print(f"✅ User: {user.email} (ID: {user.id})\\n")
        
        # Get all meal logs
        all_meals = db.query(MealLog).filter(
            MealLog.user_id == user.id
        ).order_by(MealLog.logged_at).all()
        
        print(f"📝 Total meals logged: {len(all_meals)}")
        
        # Get unique food IDs
        unique_food_ids = set()
        unique_foods = []
        for meal in all_meals:
            if meal.food_item_id not in unique_food_ids:
                unique_food_ids.add(meal.food_item_id)
                food = db.query(FoodItem).filter(FoodItem.id == meal.food_item_id).first()
                unique_foods.append(food.name if food else "Unknown")
        
        print(f"🌈 Unique foods: {len(unique_foods)}")
        for food in unique_foods:
            print(f"  • {food}")
        
        # Get unique days logged
        unique_days = set()
        for meal in all_meals:
            meal_date = meal.logged_at.date()
            unique_days.add(meal_date)
        
        print(f"\\n📅 Unique days logged: {len(unique_days)}")
        for day in sorted(unique_days):
            print(f"  • {day}")
        
        # Update challenges
        print(f"\\n🎯 Updating Challenges:\\n")
        
        # 1. Update Consistency Builder
        consistency_challenge = db.query(PersonalizedChallenge).filter(
            PersonalizedChallenge.user_id == user.id,
            PersonalizedChallenge.title.like('%Consistency%')
        ).first()
        
        if consistency_challenge:
            consistency_challenge.current_value = float(len(unique_days))
            consistency_challenge.completion_percentage = (
                (consistency_challenge.current_value / consistency_challenge.target_value) * 100 
                if consistency_challenge.target_value > 0 else 0
            )
            print(f"✅ Consistency Builder: {consistency_challenge.current_value}/{consistency_challenge.target_value} days ({consistency_challenge.completion_percentage:.1f}%)")
        
        # 2. Update Nutrition Explorer
        variety_challenge = db.query(PersonalizedChallenge).filter(
            PersonalizedChallenge.user_id == user.id,
            PersonalizedChallenge.title.like('%Explorer%')
        ).first()
        
        if variety_challenge:
            variety_challenge.current_value = float(len(unique_foods))
            variety_challenge.completion_percentage = (
                (variety_challenge.current_value / variety_challenge.target_value) * 100 
                if variety_challenge.target_value > 0 else 0
            )
            print(f"✅ Nutrition Explorer: {variety_challenge.current_value}/{variety_challenge.target_value} foods ({variety_challenge.completion_percentage:.1f}%)")
        
        # 3. Update Start Your Journey
        journey_challenge = db.query(PersonalizedChallenge).filter(
            PersonalizedChallenge.user_id == user.id,
            PersonalizedChallenge.title.like('%Journey%')
        ).first()
        
        if journey_challenge:
            journey_challenge.current_value = float(len(all_meals))
            journey_challenge.completion_percentage = (
                (journey_challenge.current_value / journey_challenge.target_value) * 100 
                if journey_challenge.target_value > 0 else 0
            )
            
            # Mark as complete if target reached
            if journey_challenge.completion_percentage >= 100:
                journey_challenge.is_active = False
                journey_challenge.completion_date = datetime.now()
            
            print(f"✅ Start Your Journey: {journey_challenge.current_value}/{journey_challenge.target_value} meals ({journey_challenge.completion_percentage:.1f}%)")
        
        db.commit()
        print(f"\\n🎉 All challenges updated successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
