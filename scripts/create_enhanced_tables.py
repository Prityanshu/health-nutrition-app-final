#!/usr/bin/env python3
"""
Script to create enhanced tables for better personalization and ML recommendations
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.database import Base, engine
from app.models.enhanced_models import (
    UserBehavior, FoodRating, RecipeInteraction, UserCookingPattern,
    MealPlanAdherence, UserNutritionGoals, FoodPreferenceLearning,
    ChatbotInteraction, SeasonalPreference, SocialCookingData
)

def create_enhanced_tables():
    """Create all enhanced tables for better personalization"""
    
    print("Creating enhanced tables for better personalization...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("✅ Successfully created enhanced tables:")
        print("   - user_behaviors")
        print("   - food_ratings") 
        print("   - recipe_interactions")
        print("   - user_cooking_patterns")
        print("   - meal_plan_adherence")
        print("   - user_nutrition_goals")
        print("   - food_preference_learning")
        print("   - chatbot_interactions")
        print("   - seasonal_preferences")
        print("   - social_cooking_data")
        
        print("\n🎉 Enhanced personalization system is ready!")
        print("   - Users can now rate foods for better recommendations")
        print("   - Cooking patterns and preferences are tracked")
        print("   - Advanced ML recommendations are available")
        print("   - Chatbot responses are enhanced with personalization")
        
    except Exception as e:
        print(f"❌ Error creating enhanced tables: {e}")
        return False
    
    return True

def add_sample_data():
    """Add some sample data for testing"""
    
    print("\nAdding sample data...")
    
    try:
        from sqlalchemy.orm import sessionmaker
        from datetime import datetime, timedelta
        import json
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Add sample food ratings (if users exist)
        from app.database import User, FoodItem
        
        users = db.query(User).limit(3).all()
        foods = db.query(FoodItem).limit(10).all()
        
        if users and foods:
            # Add sample food ratings
            for user in users:
                for i, food in enumerate(foods[:5]):
                    rating = FoodRating(
                        user_id=user.id,
                        food_item_id=food.id,
                        rating=4.0 + (i * 0.2),  # 4.0 to 5.0 ratings
                        context='lunch',
                        notes=f'Sample rating for {food.name}',
                        created_at=datetime.utcnow() - timedelta(days=i)
                    )
                    db.add(rating)
            
            # Add sample cooking patterns
            for user in users:
                cooking_pattern = UserCookingPattern(
                    user_id=user.id,
                    cooking_frequency='weekly',
                    preferred_cooking_time='evening',
                    cooking_skill_level='intermediate',
                    preferred_cuisines=['indian', 'italian', 'mexican'],
                    dietary_restrictions={'vegetarian': False, 'gluten_free': False},
                    budget_range='medium',
                    meal_prep_preference=True,
                    last_updated=datetime.utcnow()
                )
                db.add(cooking_pattern)
            
            # Add sample nutrition goals
            for user in users:
                nutrition_goal = UserNutritionGoals(
                    user_id=user.id,
                    goal_type='muscle_gain',
                    target_calories=2500.0,
                    target_protein=150.0,
                    target_carbs=300.0,
                    target_fat=100.0,
                    target_fiber=30.0,
                    target_sodium=2300.0,
                    target_sugar=50.0,
                    start_date=datetime.utcnow(),
                    target_date=datetime.utcnow() + timedelta(days=90),
                    is_active=True,
                    progress_data={'week_1': {'calories': 2400, 'protein': 140}},
                    last_updated=datetime.utcnow()
                )
                db.add(nutrition_goal)
            
            db.commit()
            print("✅ Sample data added successfully")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error adding sample data: {e}")

if __name__ == "__main__":
    print("🚀 Setting up enhanced personalization system...")
    
    if create_enhanced_tables():
        add_sample_data()
        print("\n🎯 Enhanced personalization system is ready to use!")
        print("   - Access enhanced ML endpoints at /api/enhanced-ml/")
        print("   - Users can now get highly personalized recommendations")
        print("   - Chatbot responses are enhanced with ML insights")
    else:
        print("\n❌ Failed to set up enhanced personalization system")
