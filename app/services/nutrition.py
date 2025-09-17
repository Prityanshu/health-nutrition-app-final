# app/services/nutrition.py
"""
Nutrition calculation and basic meal planning service
"""
import math
from typing import Dict, Optional, Tuple, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import User, Goal
from app.schemas import NutritionCalculationRequest, NutritionCalculationResponse, ActivityLevel, GoalType

class NutritionCalculator:
    """Calculate nutritional requirements and provide meal planning guidance"""
    
    @staticmethod
    def calculate_bmr(weight: float, height: float, age: int, gender: str = 'male') -> float:
        """Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation"""
        if gender.lower() == 'male':
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:  # female
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        
        return bmr
    
    @staticmethod
    def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
        """Calculate Total Daily Energy Expenditure"""
        activity_multipliers = {
            ActivityLevel.SEDENTARY: 1.2,
            ActivityLevel.LIGHTLY_ACTIVE: 1.375,
            ActivityLevel.MODERATELY_ACTIVE: 1.55,
            ActivityLevel.VERY_ACTIVE: 1.725
        }
        
        multiplier = activity_multipliers.get(activity_level, 1.55)
        return bmr * multiplier
    
    @staticmethod
    def calculate_target_calories(user: User, goal: Optional[Goal] = None) -> float:
        """Calculate target calories based on user profile and goals"""
        
        # Get basic info
        weight = user.weight or 70
        height = user.height or 170
        age = user.age or 30
        activity_level = ActivityLevel(user.activity_level) if user.activity_level else ActivityLevel.MODERATELY_ACTIVE
        
        # Calculate BMR and TDEE
        bmr = NutritionCalculator.calculate_bmr(weight, height, age)
        tdee = NutritionCalculator.calculate_tdee(bmr, activity_level)
        
        # Adjust based on goal
        if goal:
            if goal.goal_type == GoalType.WEIGHT_LOSS:
                # 500 calorie deficit per day for 1 lb/week loss
                target_calories = tdee - 500
            elif goal.goal_type == GoalType.WEIGHT_GAIN:
                # 500 calorie surplus per day for 1 lb/week gain
                target_calories = tdee + 500
            elif goal.goal_type == GoalType.MUSCLE_GAIN:
                # Slight surplus for muscle gain
                target_calories = tdee + 300
            elif goal.goal_type == GoalType.MAINTENANCE:
                target_calories = tdee
            else:
                target_calories = tdee
        else:
            target_calories = tdee
        
        # Ensure minimum calories
        return max(1200, target_calories)
    
    @staticmethod
    def calculate_macro_targets(calories: float, goal_type: Optional[GoalType] = None) -> Dict[str, float]:
        """Calculate macro-nutrient targets based on calories and goal"""
        
        if goal_type == GoalType.WEIGHT_LOSS:
            # Higher protein for weight loss
            protein_ratio = 0.30
            carb_ratio = 0.40
            fat_ratio = 0.30
        elif goal_type == GoalType.MUSCLE_GAIN:
            # Higher protein and carbs for muscle gain
            protein_ratio = 0.35
            carb_ratio = 0.45
            fat_ratio = 0.20
        elif goal_type == GoalType.WEIGHT_GAIN:
            # Balanced macros for weight gain
            protein_ratio = 0.25
            carb_ratio = 0.50
            fat_ratio = 0.25
        else:
            # Maintenance - balanced macros
            protein_ratio = 0.25
            carb_ratio = 0.45
            fat_ratio = 0.30
        
        # Calculate grams
        protein_g = (calories * protein_ratio) / 4  # 4 cal/g protein
        carbs_g = (calories * carb_ratio) / 4       # 4 cal/g carbs
        fat_g = (calories * fat_ratio) / 9          # 9 cal/g fat
        
        return {
            'protein_g': protein_g,
            'carbs_g': carbs_g,
            'fat_g': fat_g,
            'protein_percentage': protein_ratio * 100,
            'carbs_percentage': carb_ratio * 100,
            'fat_percentage': fat_ratio * 100
        }
    
    @staticmethod
    def calculate_nutrition_requirements(user: User, goal: Optional[Goal] = None) -> NutritionCalculationResponse:
        """Calculate complete nutrition requirements for a user"""
        
        # Get basic info
        weight = user.weight or 70
        height = user.height or 170
        age = user.age or 30
        activity_level = ActivityLevel(user.activity_level) if user.activity_level else ActivityLevel.MODERATELY_ACTIVE
        goal_type = GoalType(goal.goal_type) if goal else GoalType.MAINTENANCE
        
        # Calculate BMR and TDEE
        bmr = NutritionCalculator.calculate_bmr(weight, height, age)
        tdee = NutritionCalculator.calculate_tdee(bmr, activity_level)
        
        # Calculate target calories
        target_calories = NutritionCalculator.calculate_target_calories(user, goal)
        
        # Calculate macro targets
        macro_targets = NutritionCalculator.calculate_macro_targets(target_calories, goal_type)
        
        return NutritionCalculationResponse(
            target_calories=target_calories,
            target_protein=macro_targets['protein_g'],
            target_carbs=macro_targets['carbs_g'],
            target_fat=macro_targets['fat_g'],
            bmr=bmr,
            tdee=tdee,
            macro_ratios={
                'protein_percentage': macro_targets['protein_percentage'],
                'carbs_percentage': macro_targets['carbs_percentage'],
                'fat_percentage': macro_targets['fat_percentage']
            }
        )
    
    @staticmethod
    def calculate_meal_distribution(target_calories: float, meals_per_day: int = 3) -> Dict[str, float]:
        """Calculate calorie distribution across meals"""
        
        if meals_per_day == 3:
            # Traditional 3 meals
            distribution = {
                'breakfast': target_calories * 0.25,  # 25%
                'lunch': target_calories * 0.35,      # 35%
                'dinner': target_calories * 0.40      # 40%
            }
        elif meals_per_day == 4:
            # 3 meals + 1 snack
            distribution = {
                'breakfast': target_calories * 0.25,  # 25%
                'lunch': target_calories * 0.30,      # 30%
                'snack': target_calories * 0.15,      # 15%
                'dinner': target_calories * 0.30      # 30%
            }
        elif meals_per_day == 5:
            # 3 meals + 2 snacks
            distribution = {
                'breakfast': target_calories * 0.20,  # 20%
                'snack': target_calories * 0.10,      # 10%
                'lunch': target_calories * 0.25,      # 25%
                'snack': target_calories * 0.15,      # 15%
                'dinner': target_calories * 0.30      # 30%
            }
        else:
            # Default to 3 meals
            distribution = {
                'breakfast': target_calories * 0.25,
                'lunch': target_calories * 0.35,
                'dinner': target_calories * 0.40
            }
        
        return distribution
    
    @staticmethod
    def calculate_water_intake(weight: float, activity_level: ActivityLevel) -> float:
        """Calculate recommended daily water intake in liters"""
        
        # Base water intake: 35ml per kg of body weight
        base_intake = (weight * 35) / 1000  # Convert to liters
        
        # Adjust for activity level
        activity_multipliers = {
            ActivityLevel.SEDENTARY: 1.0,
            ActivityLevel.LIGHTLY_ACTIVE: 1.1,
            ActivityLevel.MODERATELY_ACTIVE: 1.2,
            ActivityLevel.VERY_ACTIVE: 1.3
        }
        
        multiplier = activity_multipliers.get(activity_level, 1.1)
        return base_intake * multiplier
    
    @staticmethod
    def calculate_bmi(weight: float, height: float) -> Tuple[float, str]:
        """Calculate BMI and category"""
        
        # Convert height from cm to meters
        height_m = height / 100
        
        # Calculate BMI
        bmi = weight / (height_m ** 2)
        
        # Determine category
        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25:
            category = "Normal weight"
        elif bmi < 30:
            category = "Overweight"
        else:
            category = "Obese"
        
        return bmi, category
    
    @staticmethod
    def calculate_ideal_weight(height: float, gender: str = 'male') -> float:
        """Calculate ideal weight using Devine formula"""
        
        height_inches = height / 2.54  # Convert cm to inches
        
        if gender.lower() == 'male':
            ideal_weight = 50 + (2.3 * (height_inches - 60))
        else:  # female
            ideal_weight = 45.5 + (2.3 * (height_inches - 60))
        
        return ideal_weight * 0.453592  # Convert to kg
    
    @staticmethod
    def calculate_weight_change_rate(current_weight: float, target_weight: float, 
                                   target_date: Optional[datetime] = None) -> Dict[str, float]:
        """Calculate weight change rate and required calorie adjustment"""
        
        weight_difference = target_weight - current_weight
        
        if target_date:
            days_remaining = (target_date - datetime.now()).days
            if days_remaining > 0:
                weekly_change = (weight_difference / days_remaining) * 7
            else:
                weekly_change = 0
        else:
            # Default to 0.5 kg per week
            weekly_change = 0.5 if weight_difference > 0 else -0.5
        
        # Calculate required calorie adjustment
        # 1 kg = ~7700 calories
        daily_calorie_adjustment = (weekly_change * 7700) / 7
        
        return {
            'weight_difference': weight_difference,
            'weekly_change_kg': weekly_change,
            'daily_calorie_adjustment': daily_calorie_adjustment,
            'is_realistic': abs(weekly_change) <= 1.0  # Max 1 kg per week is realistic
        }

class BasicMealPlanner:
    """Basic meal planning functionality"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def suggest_meal_times(self, user: User) -> Dict[str, str]:
        """Suggest optimal meal times based on user profile"""
        
        # Default meal times
        meal_times = {
            'breakfast': '08:00',
            'lunch': '13:00',
            'dinner': '19:00'
        }
        
        # Adjust based on activity level
        if user.activity_level == ActivityLevel.VERY_ACTIVE:
            meal_times['breakfast'] = '07:00'
            meal_times['lunch'] = '12:30'
            meal_times['dinner'] = '18:30'
        elif user.activity_level == ActivityLevel.SEDENTARY:
            meal_times['breakfast'] = '09:00'
            meal_times['lunch'] = '13:30'
            meal_times['dinner'] = '19:30'
        
        return meal_times
    
    def calculate_portion_sizes(self, target_calories: float, 
                              food_calories_per_100g: float) -> float:
        """Calculate appropriate portion size in grams"""
        
        # Calculate grams needed for target calories
        portion_grams = (target_calories / food_calories_per_100g) * 100
        
        # Apply reasonable limits
        min_portion = 50  # Minimum 50g
        max_portion = 500  # Maximum 500g
        
        return max(min_portion, min(max_portion, portion_grams))
    
    def suggest_food_combinations(self, primary_food: str, 
                                target_calories: float) -> List[Dict[str, str]]:
        """Suggest food combinations for balanced meals"""
        
        combinations = []
        
        if 'chicken' in primary_food.lower():
            combinations = [
                {'food': 'Brown Rice', 'reason': 'Complex carbs for energy'},
                {'food': 'Steamed Broccoli', 'reason': 'Fiber and vitamins'},
                {'food': 'Olive Oil', 'reason': 'Healthy fats'}
            ]
        elif 'salmon' in primary_food.lower():
            combinations = [
                {'food': 'Quinoa', 'reason': 'Complete protein and carbs'},
                {'food': 'Asparagus', 'reason': 'Fiber and folate'},
                {'food': 'Lemon', 'reason': 'Vitamin C and flavor'}
            ]
        elif 'tofu' in primary_food.lower():
            combinations = [
                {'food': 'Stir-fried Vegetables', 'reason': 'Fiber and vitamins'},
                {'food': 'Brown Rice', 'reason': 'Complex carbohydrates'},
                {'food': 'Sesame Oil', 'reason': 'Healthy fats and flavor'}
            ]
        else:
            combinations = [
                {'food': 'Mixed Vegetables', 'reason': 'Fiber and vitamins'},
                {'food': 'Whole Grain', 'reason': 'Complex carbohydrates'},
                {'food': 'Healthy Fat Source', 'reason': 'Essential fatty acids'}
            ]
        
        return combinations
