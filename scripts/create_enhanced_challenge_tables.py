#!/usr/bin/env python3
"""
Script to create enhanced challenge tables for data-driven personalization
"""
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, engine, SessionLocal, User, FoodItem, FoodRating, Recipe
from app.models.enhanced_challenge_models import (
    PersonalizedChallenge, ChallengeTemplate, UserChallengeProgress,
    ChallengeAchievement, ChallengeRecommendation, ChallengeType, ChallengeDifficulty
)

def create_tables():
    """Create enhanced challenge tables"""
    print("Creating enhanced challenge tables...")
    
    # Create all tables defined in Base (including those from enhanced_challenge_models)
    Base.metadata.create_all(bind=engine)
    
    print("✅ Successfully created enhanced challenge tables:")
    print("   - personalized_challenges")
    print("   - challenge_templates")
    print("   - user_challenge_progress")
    print("   - challenge_achievements")
    print("   - challenge_recommendations")

def add_sample_challenge_templates():
    """Add sample challenge templates"""
    db = SessionLocal()
    try:
        print("\nAdding sample challenge templates...")
        
        templates = [
            {
                "challenge_type": ChallengeType.NUTRITION,
                "difficulty": ChallengeDifficulty.EASY,
                "title_template": "Protein Power Week",
                "description_template": "Increase your daily protein intake to {target_value}g per day",
                "unit": "grams",
                "baseline_requirements": ["protein_intake"],
                "improvement_ranges": {"easy": 10, "medium": 20, "hard": 30, "expert": 40},
                "target_calculation_rules": {
                    "formula": "baseline * (1 + improvement_percentage/100)",
                    "min_target": 80,
                    "max_target": 200
                },
                "personalization_rules": {
                    "based_on_weakness": "low_protein",
                    "min_baseline": 50,
                    "max_baseline": 150
                },
                "min_user_data_days": 7,
                "max_challenges_per_type": 1
            },
            {
                "challenge_type": ChallengeType.NUTRITION,
                "difficulty": ChallengeDifficulty.MEDIUM,
                "title_template": "Fiber Fuel Challenge",
                "description_template": "Boost your daily fiber intake to {target_value}g per day",
                "unit": "grams",
                "baseline_requirements": ["fiber_intake"],
                "improvement_ranges": {"easy": 15, "medium": 25, "hard": 35, "expert": 50},
                "target_calculation_rules": {
                    "formula": "baseline * (1 + improvement_percentage/100)",
                    "min_target": 20,
                    "max_target": 50
                },
                "personalization_rules": {
                    "based_on_weakness": "low_fiber",
                    "min_baseline": 10,
                    "max_baseline": 30
                },
                "min_user_data_days": 7,
                "max_challenges_per_type": 1
            },
            {
                "challenge_type": ChallengeType.CONSISTENCY,
                "difficulty": ChallengeDifficulty.EASY,
                "title_template": "Daily Logging Streak",
                "description_template": "Log meals {target_value}% of days this week",
                "unit": "percentage",
                "baseline_requirements": ["meal_logging_consistency"],
                "improvement_ranges": {"easy": 10, "medium": 20, "hard": 30, "expert": 40},
                "target_calculation_rules": {
                    "formula": "baseline + improvement_percentage",
                    "min_target": 50,
                    "max_target": 100
                },
                "personalization_rules": {
                    "based_on_weakness": "inconsistent_logging",
                    "min_baseline": 30,
                    "max_baseline": 80
                },
                "min_user_data_days": 7,
                "max_challenges_per_type": 1
            },
            {
                "challenge_type": ChallengeType.VARIETY,
                "difficulty": ChallengeDifficulty.MEDIUM,
                "title_template": "Food Explorer Challenge",
                "description_template": "Try {target_value} different foods this week",
                "unit": "unique_foods",
                "baseline_requirements": ["food_variety_score"],
                "improvement_ranges": {"easy": 2, "medium": 4, "hard": 6, "expert": 8},
                "target_calculation_rules": {
                    "formula": "baseline * (1 + improvement_percentage/100)",
                    "min_target": 5,
                    "max_target": 20
                },
                "personalization_rules": {
                    "based_on_weakness": "low_variety",
                    "min_baseline": 0.2,
                    "max_baseline": 0.8
                },
                "min_user_data_days": 7,
                "max_challenges_per_type": 1
            },
            {
                "challenge_type": ChallengeType.GOAL_ORIENTED,
                "difficulty": ChallengeDifficulty.HARD,
                "title_template": "Goal Achievement Week",
                "description_template": "Make progress toward your {goal_type} goal for {target_value} days",
                "unit": "days",
                "baseline_requirements": ["goal_progress"],
                "improvement_ranges": {"easy": 3, "medium": 5, "hard": 7, "expert": 10},
                "target_calculation_rules": {
                    "formula": "improvement_percentage",
                    "min_target": 3,
                    "max_target": 10
                },
                "personalization_rules": {
                    "based_on_weakness": "goal_progress",
                    "min_baseline": 0,
                    "max_baseline": 0.5
                },
                "min_user_data_days": 14,
                "max_challenges_per_type": 1
            }
        ]
        
        for template_data in templates:
            template = ChallengeTemplate(**template_data)
            db.add(template)
        
        db.commit()
        print("✅ Successfully added sample challenge templates!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error adding sample templates: {e}")
    finally:
        db.close()

def add_sample_data():
    """Add sample data for testing"""
    db = SessionLocal()
    try:
        print("\nAdding sample data...")
        
        # Get a user to create sample challenges for
        user = db.query(User).first()
        if not user:
            print("❌ No users found. Please create a user first.")
            return
        
        print(f"Creating sample challenges for user: {user.username}")
        
        # Create a sample personalized challenge
        challenge = PersonalizedChallenge(
            user_id=user.id,
            challenge_type=ChallengeType.NUTRITION,
            difficulty=ChallengeDifficulty.MEDIUM,
            title="Sample Protein Challenge",
            description="Increase your daily protein intake to 120g per day",
            target_value=120.0,
            current_value=0.0,
            unit="grams",
            baseline_data={"current_protein": 80.0},
            target_improvement=50.0,
            personalization_factors={
                "based_on": "low_protein_intake",
                "current_level": 80.0,
                "improvement_needed": 40.0
            },
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=7),
            is_active=True,
            daily_targets=[
                {"day": 1, "target": 17.14, "achieved": False, "value": 0.0},
                {"day": 2, "target": 17.14, "achieved": False, "value": 0.0},
                {"day": 3, "target": 17.14, "achieved": False, "value": 0.0},
                {"day": 4, "target": 17.14, "achieved": False, "value": 0.0},
                {"day": 5, "target": 17.14, "achieved": False, "value": 0.0},
                {"day": 6, "target": 17.14, "achieved": False, "value": 0.0},
                {"day": 7, "target": 17.14, "achieved": False, "value": 0.0}
            ],
            progress_history=[],
            completion_percentage=0.0,
            points_reward=150,
            badge_reward="protein_power",
            motivational_messages=[
                "Protein helps build and repair muscles!",
                "You're getting stronger with every gram!",
                "Your body will thank you for the protein boost!"
            ]
        )
        
        db.add(challenge)
        db.commit()
        
        print("✅ Successfully added sample data!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error adding sample data: {e}")
    finally:
        db.close()

def main():
    """Main function"""
    print("🚀 Setting up Enhanced Challenge System...")
    
    # Create tables
    create_tables()
    
    # Add sample templates
    add_sample_challenge_templates()
    
    # Add sample data
    add_sample_data()
    
    print("\n🎯 Enhanced Challenge System is ready!")
    print("\n📋 Available API endpoints:")
    print("   - POST /api/enhanced-challenges/generate-weekly-challenges")
    print("   - GET /api/enhanced-challenges/active-challenges")
    print("   - POST /api/enhanced-challenges/update-challenge-progress")
    print("   - GET /api/enhanced-challenges/challenge-recommendations")
    print("   - POST /api/enhanced-challenges/accept-challenge-recommendation")
    print("   - GET /api/enhanced-challenges/challenge-achievements")
    print("   - GET /api/enhanced-challenges/challenge-analytics")
    print("   - GET /api/enhanced-challenges/challenge-leaderboard")

if __name__ == "__main__":
    main()
