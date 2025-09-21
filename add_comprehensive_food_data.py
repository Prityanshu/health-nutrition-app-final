#!/usr/bin/env python3
"""
Add comprehensive food data to the nutrition app database
"""
import sqlite3
import json
from datetime import datetime

# Comprehensive food database with Indian and international dishes
FOOD_ITEMS = [
    # Indian Dishes
    {"name": "Dal Tadka", "cuisine_type": "indian", "calories": 150, "protein_g": 8, "carbs_g": 20, "fat_g": 4, "fiber_g": 6, "sodium_mg": 400, "sugar_g": 2, "cost": 3.0, "gi": 45, "low_sodium": False, "diabetic_friendly": True, "hypertension_friendly": False, "prep_complexity": "medium", "ingredients": "Lentils, onions, tomatoes, spices", "tags": "vegetarian,protein,high_fiber"},
    {"name": "Biryani", "cuisine_type": "indian", "calories": 350, "protein_g": 15, "carbs_g": 45, "fat_g": 12, "fiber_g": 3, "sodium_mg": 600, "sugar_g": 4, "cost": 8.0, "gi": 70, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "high", "ingredients": "Rice, meat, spices, yogurt", "tags": "non_vegetarian,high_calorie"},
    {"name": "Chole Bhature", "cuisine_type": "indian", "calories": 450, "protein_g": 12, "carbs_g": 60, "fat_g": 18, "fiber_g": 8, "sodium_mg": 500, "sugar_g": 3, "cost": 5.0, "gi": 75, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "medium", "ingredients": "Chickpeas, flour, spices", "tags": "vegetarian,high_calorie"},
    {"name": "Rajma Chawal", "cuisine_type": "indian", "calories": 280, "protein_g": 14, "carbs_g": 45, "fat_g": 6, "fiber_g": 12, "sodium_mg": 350, "sugar_g": 2, "cost": 4.0, "gi": 50, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "medium", "ingredients": "Kidney beans, rice, onions, tomatoes", "tags": "vegetarian,protein,high_fiber"},
    {"name": "Palak Paneer", "cuisine_type": "indian", "calories": 200, "protein_g": 12, "carbs_g": 8, "fat_g": 14, "fiber_g": 4, "sodium_mg": 300, "sugar_g": 3, "cost": 6.0, "gi": 30, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "medium", "ingredients": "Spinach, paneer, onions, spices", "tags": "vegetarian,protein,iron_rich"},
    {"name": "Butter Chicken", "cuisine_type": "indian", "calories": 320, "protein_g": 25, "carbs_g": 12, "fat_g": 18, "fiber_g": 2, "sodium_mg": 450, "sugar_g": 8, "cost": 12.0, "gi": 40, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "high", "ingredients": "Chicken, cream, tomatoes, spices", "tags": "non_vegetarian,high_protein"},
    {"name": "Masala Dosa", "cuisine_type": "indian", "calories": 180, "protein_g": 6, "carbs_g": 25, "fat_g": 6, "fiber_g": 4, "sodium_mg": 200, "sugar_g": 2, "cost": 4.0, "gi": 55, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "high", "ingredients": "Rice flour, potatoes, onions, spices", "tags": "vegetarian,fermented"},
    {"name": "Samosa", "cuisine_type": "indian", "calories": 120, "protein_g": 3, "carbs_g": 15, "fat_g": 6, "fiber_g": 2, "sodium_mg": 250, "sugar_g": 1, "cost": 2.0, "gi": 60, "low_sodium": True, "diabetic_friendly": False, "hypertension_friendly": True, "prep_complexity": "medium", "ingredients": "Flour, potatoes, peas, spices", "tags": "vegetarian,snack"},
    {"name": "Tandoori Chicken", "cuisine_type": "indian", "calories": 180, "protein_g": 28, "carbs_g": 2, "fat_g": 6, "fiber_g": 0, "sodium_mg": 400, "sugar_g": 1, "cost": 10.0, "gi": 0, "low_sodium": False, "diabetic_friendly": True, "hypertension_friendly": False, "prep_complexity": "medium", "ingredients": "Chicken, yogurt, spices", "tags": "non_vegetarian,high_protein,grilled"},
    {"name": "Aloo Gobi", "cuisine_type": "indian", "calories": 120, "protein_g": 4, "carbs_g": 20, "fat_g": 3, "fiber_g": 5, "sodium_mg": 200, "sugar_g": 4, "cost": 3.0, "gi": 45, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Potatoes, cauliflower, onions, spices", "tags": "vegetarian,low_calorie"},
    
    # International Dishes
    {"name": "Pasta Carbonara", "cuisine_type": "italian", "calories": 400, "protein_g": 18, "carbs_g": 45, "fat_g": 16, "fiber_g": 2, "sodium_mg": 600, "sugar_g": 3, "cost": 8.0, "gi": 65, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "medium", "ingredients": "Pasta, eggs, cheese, bacon", "tags": "non_vegetarian,high_calorie"},
    {"name": "Margherita Pizza", "cuisine_type": "italian", "calories": 250, "protein_g": 12, "carbs_g": 30, "fat_g": 8, "fiber_g": 2, "sodium_mg": 500, "sugar_g": 3, "cost": 6.0, "gi": 70, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "medium", "ingredients": "Dough, tomato sauce, mozzarella, basil", "tags": "vegetarian"},
    {"name": "Chicken Stir Fry", "cuisine_type": "chinese", "calories": 180, "protein_g": 22, "carbs_g": 8, "fat_g": 6, "fiber_g": 3, "sodium_mg": 400, "sugar_g": 4, "cost": 7.0, "gi": 35, "low_sodium": False, "diabetic_friendly": True, "hypertension_friendly": False, "prep_complexity": "low", "ingredients": "Chicken, vegetables, soy sauce", "tags": "non_vegetarian,high_protein,low_calorie"},
    {"name": "Caesar Salad", "cuisine_type": "american", "calories": 200, "protein_g": 8, "carbs_g": 12, "fat_g": 14, "fiber_g": 3, "sodium_mg": 300, "sugar_g": 4, "cost": 5.0, "gi": 25, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Lettuce, croutons, parmesan, dressing", "tags": "vegetarian,low_calorie"},
    {"name": "Beef Burger", "cuisine_type": "american", "calories": 350, "protein_g": 20, "carbs_g": 30, "fat_g": 16, "fiber_g": 2, "sodium_mg": 500, "sugar_g": 5, "cost": 8.0, "gi": 60, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "low", "ingredients": "Beef patty, bun, lettuce, tomato", "tags": "non_vegetarian,high_protein"},
    {"name": "Sushi Roll", "cuisine_type": "japanese", "calories": 200, "protein_g": 8, "carbs_g": 35, "fat_g": 2, "fiber_g": 1, "sodium_mg": 400, "sugar_g": 2, "cost": 12.0, "gi": 55, "low_sodium": False, "diabetic_friendly": True, "hypertension_friendly": False, "prep_complexity": "high", "ingredients": "Rice, fish, seaweed, vegetables", "tags": "non_vegetarian,low_fat"},
    {"name": "Pad Thai", "cuisine_type": "thai", "calories": 300, "protein_g": 12, "carbs_g": 45, "fat_g": 8, "fiber_g": 3, "sodium_mg": 600, "sugar_g": 8, "cost": 9.0, "gi": 65, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "medium", "ingredients": "Rice noodles, shrimp, peanuts, vegetables", "tags": "non_vegetarian"},
    {"name": "Fish and Chips", "cuisine_type": "british", "calories": 450, "protein_g": 20, "carbs_g": 35, "fat_g": 25, "fiber_g": 2, "sodium_mg": 400, "sugar_g": 2, "cost": 10.0, "gi": 70, "low_sodium": False, "diabetic_friendly": False, "hypertension_friendly": False, "prep_complexity": "medium", "ingredients": "Fish, potatoes, flour, oil", "tags": "non_vegetarian,high_calorie"},
    {"name": "Tacos", "cuisine_type": "mexican", "calories": 180, "protein_g": 12, "carbs_g": 15, "fat_g": 8, "fiber_g": 4, "sodium_mg": 300, "sugar_g": 2, "cost": 5.0, "gi": 50, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Tortilla, meat, vegetables, cheese", "tags": "non_vegetarian"},
    {"name": "Greek Salad", "cuisine_type": "greek", "calories": 150, "protein_g": 6, "carbs_g": 8, "fat_g": 12, "fiber_g": 3, "sodium_mg": 200, "sugar_g": 4, "cost": 6.0, "gi": 20, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Tomatoes, cucumbers, olives, feta", "tags": "vegetarian,mediterranean"},
    
    # Healthy Options
    {"name": "Quinoa Bowl", "cuisine_type": "mixed", "calories": 250, "protein_g": 10, "carbs_g": 35, "fat_g": 8, "fiber_g": 6, "sodium_mg": 200, "sugar_g": 5, "cost": 7.0, "gi": 40, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Quinoa, vegetables, avocado, seeds", "tags": "vegetarian,superfood,high_fiber"},
    {"name": "Grilled Salmon", "cuisine_type": "mixed", "calories": 220, "protein_g": 25, "carbs_g": 0, "fat_g": 12, "fiber_g": 0, "sodium_mg": 150, "sugar_g": 0, "cost": 15.0, "gi": 0, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Salmon, herbs, lemon", "tags": "non_vegetarian,omega3,high_protein"},
    {"name": "Avocado Toast", "cuisine_type": "mixed", "calories": 200, "protein_g": 8, "carbs_g": 20, "fat_g": 12, "fiber_g": 8, "sodium_mg": 300, "sugar_g": 2, "cost": 4.0, "gi": 45, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Bread, avocado, lemon, salt", "tags": "vegetarian,healthy_fats"},
    {"name": "Green Smoothie", "cuisine_type": "mixed", "calories": 120, "protein_g": 4, "carbs_g": 25, "fat_g": 2, "fiber_g": 6, "sodium_mg": 50, "sugar_g": 15, "cost": 3.0, "gi": 60, "low_sodium": True, "diabetic_friendly": False, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Spinach, banana, apple, water", "tags": "vegetarian,antioxidants"},
    {"name": "Oatmeal", "cuisine_type": "mixed", "calories": 150, "protein_g": 5, "carbs_g": 27, "fat_g": 3, "fiber_g": 4, "sodium_mg": 100, "sugar_g": 1, "cost": 2.0, "gi": 55, "low_sodium": True, "diabetic_friendly": True, "hypertension_friendly": True, "prep_complexity": "low", "ingredients": "Oats, milk, berries", "tags": "vegetarian,whole_grain"},
]

def add_food_items():
    """Add comprehensive food items to the database"""
    conn = sqlite3.connect('nutrition_app.db')
    cursor = conn.cursor()
    
    print(f"Adding {len(FOOD_ITEMS)} food items to the database...")
    
    for item in FOOD_ITEMS:
        try:
            cursor.execute("""
                INSERT INTO food_items (
                    name, cuisine_type, calories, protein_g, carbs_g, fat_g, 
                    fiber_g, sodium_mg, sugar_g, cost, gi, low_sodium, 
                    diabetic_friendly, hypertension_friendly, prep_complexity, 
                    ingredients, tags, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item['name'],
                item['cuisine_type'],
                item['calories'],
                item['protein_g'],
                item['carbs_g'],
                item['fat_g'],
                item['fiber_g'],
                item['sodium_mg'],
                item['sugar_g'],
                item['cost'],
                item['gi'],
                item['low_sodium'],
                item['diabetic_friendly'],
                item['hypertension_friendly'],
                item['prep_complexity'],
                item['ingredients'],
                item['tags'],
                datetime.utcnow()
            ))
            print(f"✓ Added: {item['name']}")
        except Exception as e:
            print(f"✗ Error adding {item['name']}: {e}")
    
    conn.commit()
    conn.close()
    print(f"\n✅ Successfully added {len(FOOD_ITEMS)} food items!")

if __name__ == "__main__":
    add_food_items()
