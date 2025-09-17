# app/schemas.py
"""
Pydantic schemas for request/response models
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Enums
class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

class GoalType(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_GAIN = "weight_gain"
    MUSCLE_GAIN = "muscle_gain"
    MAINTENANCE = "maintenance"
    CALORIE_TARGET = "calorie_target"
    MACRO_TARGET = "macro_target"

class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    LIGHTLY_ACTIVE = "lightly_active"
    MODERATELY_ACTIVE = "moderately_active"
    VERY_ACTIVE = "very_active"

# Base schemas
class UserBase(BaseModel):
    email: str
    username: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    activity_level: Optional[ActivityLevel] = None
    health_conditions: Optional[Dict[str, bool]] = {}
    dietary_preferences: Optional[Dict[str, Any]] = {}

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Food Item schemas
class FoodItemBase(BaseModel):
    name: str
    cuisine_type: Optional[str] = "mixed"
    calories: float
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    sodium_mg: float = 0
    sugar_g: float = 0
    cost: float = 0
    gi: float = 50
    diabetic_friendly: bool = True
    hypertension_friendly: bool = True
    ingredients: Optional[str] = None
    tags: Optional[List[str]] = []

class FoodItemCreate(FoodItemBase):
    pass

class FoodItemResponse(FoodItemBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Meal schemas
class MealItem(BaseModel):
    food_id: int
    name: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    quantity: float
    cost: float

class MealPlan(BaseModel):
    meal_index: int
    items: List[MealItem]
    total_calories: float
    total_protein: float
    total_cost: float

class DayPlan(BaseModel):
    day: int
    meals: List[MealPlan]
    total_calories: float
    total_protein: float
    total_cost: float

# ML Recommendation schemas
class UserPreferences(BaseModel):
    cuisine_preferences: Dict[str, Dict[str, float]]
    macro_preferences: Dict[str, float]
    timing_preferences: Dict[str, Any]
    calorie_patterns: Dict[str, float]
    food_categories: Dict[str, float]
    adherence_patterns: Dict[str, Any]
    preference_strength: float

class FoodRecommendation(BaseModel):
    food_id: int
    name: str
    cuisine_type: str
    calories: float
    protein_g: float
    recommendation_score: float
    reason: str

class CuisineRecommendation(BaseModel):
    cuisine: str
    reason: str
    priority: str

class MacroAdjustment(BaseModel):
    macro: str
    current: float
    suggested: float
    reason: str

class PersonalizedRecommendations(BaseModel):
    food_recommendations: List[FoodRecommendation]
    cuisine_recommendations: List[CuisineRecommendation]
    meal_timing_suggestions: Dict[str, Any]
    macro_adjustments: List[MacroAdjustment]
    variety_suggestions: List[str]

class RecommendationInsights(BaseModel):
    data_quality: Dict[str, Any]
    top_preferences: Dict[str, Any]
    improvement_areas: List[str]

# Advanced Meal Planning schemas
class AdvancedMealPlanRequest(BaseModel):
    target_calories: Optional[float] = None
    protein_percentage: Optional[float] = 25
    carb_percentage: Optional[float] = 45
    fat_percentage: Optional[float] = 30
    meals_per_day: Optional[int] = 3
    cuisine_type: Optional[str] = None
    exclude_recent_days: Optional[int] = 14
    variety_constraints: Optional[Dict[str, Any]] = {}

class AdvancedMealPlanResponse(BaseModel):
    week_plans: List[DayPlan]
    total_weekly_calories: float
    total_weekly_protein: float
    total_weekly_cost: float
    variety_score: float
    macro_balance_score: float

# Recipe Generation schemas
class RecipeGenerationRequest(BaseModel):
    ingredients: List[str]
    cuisine_type: Optional[str] = "mixed"
    target_calories: Optional[int] = None
    prep_time: Optional[int] = 30
    difficulty: Optional[str] = "medium"
    dietary_restrictions: Optional[List[str]] = []

class RecipeResponse(BaseModel):
    title: str
    ingredients: List[str]
    instructions: List[str]
    nutrition: Dict[str, float]
    prep_time: int
    cook_time: int
    difficulty: str
    cuisine_type: str
    health_benefits: List[str]
    estimated_calories: Optional[float] = None

# Nutrition Calculation schemas
class NutritionCalculationRequest(BaseModel):
    age: int
    weight: float
    height: float
    activity_level: ActivityLevel
    goal_type: GoalType
    target_weight: Optional[float] = None

class NutritionCalculationResponse(BaseModel):
    target_calories: float
    target_protein: float
    target_carbs: float
    target_fat: float
    bmr: float
    tdee: float
    macro_ratios: Dict[str, float]

# Goal schemas
class GoalBase(BaseModel):
    goal_type: GoalType
    target_weight: Optional[float] = None
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fat: Optional[float] = None
    target_date: Optional[datetime] = None

class GoalCreate(GoalBase):
    pass

class GoalResponse(GoalBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Meal Log schemas
class MealLogBase(BaseModel):
    food_item_id: int
    meal_type: MealType
    quantity: float = 1.0

class MealLogCreate(MealLogBase):
    pass

class MealLogResponse(MealLogBase):
    id: int
    user_id: int
    calories: float
    protein: float
    carbs: float
    fat: float
    logged_at: datetime
    food_item: FoodItemResponse

    class Config:
        from_attributes = True

# Progress Tracking schemas
class DailyStats(BaseModel):
    date: str
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    meal_count: int

class WeeklyStats(BaseModel):
    week_start: str
    week_end: str
    daily_stats: List[DailyStats]
    weekly_averages: Dict[str, float]

class ProgressSummary(BaseModel):
    days_logged: int
    total_meals: int
    daily_averages: Dict[str, float]
    goal_achievement: Dict[str, float]

# Challenge schemas
class ChallengeBase(BaseModel):
    name: str
    description: str
    rules: Optional[Dict[str, Any]] = {}
    reward_points: int = 0
    active_from: Optional[datetime] = None
    active_to: Optional[datetime] = None

class ChallengeCreate(ChallengeBase):
    pass

class ChallengeResponse(ChallengeBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class AchievementResponse(BaseModel):
    id: int
    user_id: int
    challenge_id: int
    points_earned: int
    completed_at: datetime
    challenge: ChallengeResponse

    class Config:
        from_attributes = True

# User Stats schema
class UserStats(BaseModel):
    total_points: int
    current_streak: int
    achievements: List[AchievementResponse]
    challenges_completed: int
    meals_logged: int
    days_active: int

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Error schemas
class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
