# app/models/enhanced_models.py
"""
Enhanced data models for better personalization and ML recommendations
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import json

# Import the existing Base from database.py to avoid conflicts
from app.database import Base

class UserBehavior(Base):
    """Track user behavioral patterns for better recommendations"""
    __tablename__ = "user_behaviors"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    behavior_type = Column(String, nullable=False)  # cooking_frequency, meal_planning, variety_seeking, etc.
    behavior_data = Column(JSON)  # Detailed behavior metrics
    frequency_score = Column(Float, default=0.0)  # 0-1 score
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

# FoodRating already exists in database.py, so we'll use that one

class RecipeInteraction(Base):
    """Track user interactions with generated recipes"""
    __tablename__ = "recipe_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)
    interaction_type = Column(String, nullable=False)  # viewed, cooked, rated, saved, shared
    interaction_data = Column(JSON)  # Additional interaction details
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    recipe = relationship("Recipe")

class UserCookingPattern(Base):
    """Track user cooking patterns and preferences"""
    __tablename__ = "user_cooking_patterns"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cooking_frequency = Column(String)  # daily, weekly, monthly, rarely
    preferred_cooking_time = Column(String)  # morning, afternoon, evening, night
    cooking_skill_level = Column(String)  # beginner, intermediate, advanced
    preferred_cuisines = Column(JSON)  # List of preferred cuisines
    dietary_restrictions = Column(JSON)  # Detailed dietary restrictions
    budget_range = Column(String)  # low, medium, high
    meal_prep_preference = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class MealPlanAdherence(Base):
    """Track adherence to meal plans for better planning"""
    __tablename__ = "meal_plan_adherence"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_date = Column(DateTime, nullable=False)
    planned_meals = Column(JSON)  # List of planned meal IDs
    actual_meals = Column(JSON)  # List of actual meal IDs consumed
    adherence_score = Column(Float, default=0.0)  # 0-1 score
    substitution_patterns = Column(JSON)  # What user substituted
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class UserNutritionGoals(Base):
    """Detailed nutrition goals and tracking"""
    __tablename__ = "user_nutrition_goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal_type = Column(String, nullable=False)  # weight_loss, muscle_gain, maintenance, health_improvement
    target_calories = Column(Float)
    target_protein = Column(Float)
    target_carbs = Column(Float)
    target_fat = Column(Float)
    target_fiber = Column(Float)
    target_sodium = Column(Float)
    target_sugar = Column(Float)
    start_date = Column(DateTime, default=datetime.utcnow)
    target_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    progress_data = Column(JSON)  # Weekly progress tracking
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class FoodPreferenceLearning(Base):
    """Advanced food preference learning"""
    __tablename__ = "food_preference_learning"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    food_item_id = Column(Integer, ForeignKey("food_items.id"), nullable=False)
    preference_score = Column(Float, default=0.5)  # 0-1 score
    context_preferences = Column(JSON)  # Preferences by meal type, time, etc.
    seasonal_preferences = Column(JSON)  # Seasonal food preferences
    mood_preferences = Column(JSON)  # Food preferences based on mood/weather
    last_interaction = Column(DateTime, default=datetime.utcnow)
    interaction_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User")
    food_item = relationship("FoodItem")

class ChatbotInteraction(Base):
    """Track chatbot interactions for better responses"""
    __tablename__ = "chatbot_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query = Column(Text, nullable=False)
    agent_used = Column(String)  # Which AI agent was used
    response_type = Column(String)  # success, fallback, error
    user_satisfaction = Column(Float)  # 1-5 rating if provided
    follow_up_actions = Column(JSON)  # Actions taken after chatbot response
    context_data = Column(JSON)  # Context used for the response
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class SeasonalPreference(Base):
    """Track seasonal food preferences"""
    __tablename__ = "seasonal_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season = Column(String, nullable=False)  # spring, summer, fall, winter
    preferred_foods = Column(JSON)  # List of preferred foods for this season
    avoided_foods = Column(JSON)  # List of avoided foods for this season
    seasonal_goals = Column(JSON)  # Seasonal nutrition goals
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class SocialCookingData(Base):
    """Track social aspects of cooking and eating"""
    __tablename__ = "social_cooking_data"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cooking_for_others = Column(Boolean, default=False)
    family_size = Column(Integer, default=1)
    dietary_restrictions_family = Column(JSON)  # Family dietary restrictions
    social_meal_preferences = Column(JSON)  # Preferences when cooking for others
    shared_recipe_preferences = Column(JSON)  # What recipes they share
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
