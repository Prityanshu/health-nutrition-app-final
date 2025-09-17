#!/usr/bin/env python3
"""
Load initial data for the Nutrition App
This script loads sample data and the MFP dataset if available
"""
import os
import sys
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, FoodItem, Challenge, PrepComplexity, engine, Base

def create_sample_food_items():
    """Create sample food items for testing"""
    print("Creating sample food items...")
    
    db = SessionLocal()
    
    # Sample food items
    sample_foods = [
        {
            "name": "Grilled Chicken Breast",
            "cuisine_type": "mixed",
            "calories": 165,
            "protein_g": 31,
            "carbs_g": 0,
            "fat_g": 3.6,
            "fiber_g": 0,
            "sodium_mg": 74,
            "sugar_g": 0,
            "cost": 8.0,
            "gi": 0,
            "low_sodium": True,
            "diabetic_friendly": True,
            "hypertension_friendly": True,
            "prep_complexity": PrepComplexity.MEDIUM,
            "ingredients": "Chicken breast, olive oil, herbs",
            "tags": "high_protein,low_carb,diabetic_friendly"
        },
        {
            "name": "Brown Rice",
            "cuisine_type": "mixed",
            "calories": 111,
            "protein_g": 2.6,
            "carbs_g": 23,
            "fat_g": 0.9,
            "fiber_g": 1.8,
            "sodium_mg": 5,
            "sugar_g": 0.4,
            "cost": 2.0,
            "gi": 68,
            "low_sodium": True,
            "diabetic_friendly": True,
            "hypertension_friendly": True,
            "prep_complexity": PrepComplexity.LOW,
            "ingredients": "Brown rice, water",
            "tags": "whole_grain,high_fiber"
        },
        {
            "name": "Salmon Fillet",
            "cuisine_type": "mixed",
            "calories": 208,
            "protein_g": 22,
            "carbs_g": 0,
            "fat_g": 12,
            "fiber_g": 0,
            "sodium_mg": 59,
            "sugar_g": 0,
            "cost": 15.0,
            "gi": 0,
            "low_sodium": True,
            "diabetic_friendly": True,
            "hypertension_friendly": True,
            "prep_complexity": PrepComplexity.MEDIUM,
            "ingredients": "Salmon fillet, lemon, herbs",
            "tags": "high_protein,omega3,diabetic_friendly"
        },
        {
            "name": "Quinoa Salad",
            "cuisine_type": "mediterranean",
            "calories": 120,
            "protein_g": 4.4,
            "carbs_g": 22,
            "fat_g": 1.9,
            "fiber_g": 2.8,
            "sodium_mg": 7,
            "sugar_g": 0.9,
            "cost": 5.0,
            "gi": 53,
            "low_sodium": True,
            "diabetic_friendly": True,
            "hypertension_friendly": True,
            "prep_complexity": PrepComplexity.MEDIUM,
            "ingredients": "Quinoa, vegetables, olive oil",
            "tags": "whole_grain,high_fiber,vegetable"
        },
        {
            "name": "Greek Yogurt",
            "cuisine_type": "mediterranean",
            "calories": 100,
            "protein_g": 17,
            "carbs_g": 6,
            "fat_g": 0,
            "fiber_g": 0,
            "sodium_mg": 50,
            "sugar_g": 4,
            "cost": 3.0,
            "gi": 35,
            "low_sodium": True,
            "diabetic_friendly": True,
            "hypertension_friendly": True,
            "prep_complexity": PrepComplexity.LOW,
            "ingredients": "Greek yogurt, probiotics",
            "tags": "high_protein,probiotic,low_fat"
        }
    ]
    
    # Check if food items already exist
    existing_count = db.query(FoodItem).count()
    if existing_count > 0:
        print(f"Food items already exist ({existing_count} items). Skipping sample data creation.")
        db.close()
        return
    
    # Create food items
    for food_data in sample_foods:
        food_item = FoodItem(**food_data)
        db.add(food_item)
    
    db.commit()
    print(f"Created {len(sample_foods)} sample food items")
    db.close()

def create_sample_challenges():
    """Create sample challenges for gamification"""
    print("Creating sample challenges...")
    
    db = SessionLocal()
    
    # Check if challenges already exist
    existing_challenge = db.query(Challenge).first()
    if existing_challenge:
        print("Challenges already exist. Skipping...")
        db.close()
        return
    
    challenges = [
        {
            "name": "7-Day Logging Challenge",
            "description": "Log your meals for 7 consecutive days",
            "rules": '{"consecutive_days": 7, "action": "log_meal"}',
            "reward_points": 200,
            "active_from": datetime.utcnow(),
            "active_to": datetime.utcnow() + timedelta(days=30)
        },
        {
            "name": "Protein Power Week",
            "description": "Meet your daily protein goals for 7 days",
            "rules": '{"daily_protein_goal": true, "duration_days": 7}',
            "reward_points": 300,
            "active_from": datetime.utcnow(),
            "active_to": datetime.utcnow() + timedelta(days=30)
        },
        {
            "name": "Healthy Explorer",
            "description": "Try foods from 3 different cuisines this week",
            "rules": '{"different_cuisines": 3, "duration_days": 7}',
            "reward_points": 250,
            "active_from": datetime.utcnow(),
            "active_to": datetime.utcnow() + timedelta(days=30)
        },
        {
            "name": "Fiber Champion",
            "description": "Consume high-fiber foods for 5 days",
            "rules": '{"high_fiber_days": 5}',
            "reward_points": 150,
            "active_from": datetime.utcnow(),
            "active_to": datetime.utcnow() + timedelta(days=30)
        }
    ]
    
    for challenge_data in challenges:
        challenge = Challenge(**challenge_data)
        db.add(challenge)
    
    db.commit()
    print(f"Created {len(challenges)} sample challenges")
    db.close()

def load_mfp_dataset():
    """Load MyFitnessPal dataset if available"""
    print("Checking for MFP dataset...")
    
    dataset_path = os.getenv("MFP_DATASET_PATH", "mfp-diaries.tsv")
    
    if not os.path.exists(dataset_path):
        print(f"MFP dataset not found at {dataset_path}. Skipping MFP data loading.")
        return
    
    print(f"Found MFP dataset at {dataset_path}")
    
    try:
        # Import the MFP loader
        from myfitnesspal_dataset_loader import MFPDatasetLoader
        
        # Load the dataset
        loader = MFPDatasetLoader(dataset_path)
        max_records = int(os.getenv("MAX_RECORDS_TO_LOAD", "1000"))
        
        print(f"Loading MFP dataset (max {max_records} records)...")
        success = loader.load_and_process_data(max_records=max_records)
        
        if success:
            print("✅ MFP dataset loaded successfully!")
        else:
            print("❌ Failed to load MFP dataset")
            
    except ImportError:
        print("MFP dataset loader not available. Using sample data only.")
    except Exception as e:
        print(f"Error loading MFP dataset: {e}")

def main():
    """Main function to load initial data"""
    print("🚀 Loading initial data for Nutrition App...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
    
    # Load sample data
    create_sample_food_items()
    create_sample_challenges()
    
    # Try to load MFP dataset
    load_mfp_dataset()
    
    print("\n🎉 Initial data loading complete!")
    print("\nNext steps:")
    print("1. Start the application: docker-compose up")
    print("2. Access the API docs: http://localhost:8000/docs")
    print("3. Register a user and start using the app!")

if __name__ == "__main__":
    main()