from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - Using SQLite for local development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nutrition_app.db")

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Enums
class PrepComplexity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class HealthCondition(str, enum.Enum):
    DIABETES = "diabetes"
    HYPERTENSION = "hypertension"
    HEART_DISEASE = "heart_disease"
    NONE = "none"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    age = Column(Integer)
    weight = Column(Float)  # in kg
    height = Column(Float)  # in cm
    activity_level = Column(String)  # sedentary, lightly_active, moderately_active, very_active
    health_conditions = Column(Text)  # JSON string of health conditions
    dietary_preferences = Column(Text)  # JSON string of preferences
    cuisine_pref = Column(String, default="mixed")  # Preferred cuisine type
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    meal_plans = relationship("MealPlan", back_populates="user")
    meal_logs = relationship("MealLog", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    achievements = relationship("Achievement", back_populates="user")

class FoodItem(Base):
    __tablename__ = "food_items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    cuisine_type = Column(String, default="mixed")
    calories = Column(Float, nullable=False)
    protein_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    fiber_g = Column(Float, default=0)
    sodium_mg = Column(Float, default=0)
    sugar_g = Column(Float, default=0)
    cost = Column(Float, default=0)
    gi = Column(Float, default=50)  # Glycemic Index
    low_sodium = Column(Boolean, default=True)
    diabetic_friendly = Column(Boolean, default=True)
    hypertension_friendly = Column(Boolean, default=True)
    prep_complexity = Column(Enum(PrepComplexity), default=PrepComplexity.MEDIUM)
    ingredients = Column(Text)
    tags = Column(Text)  # JSON string of tags
    created_at = Column(DateTime, default=datetime.utcnow)
    planned = Column(Boolean, default=False)  # Whether this was a planned meal

class MealPlan(Base):
    __tablename__ = "meal_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plan_date = Column(DateTime, nullable=False)
    meal_type = Column(String, nullable=False)  # breakfast, lunch, dinner, snack
    food_item_id = Column(Integer, ForeignKey("food_items.id"))
    quantity = Column(Float, default=1.0)
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="meal_plans")
    food_item = relationship("FoodItem")

class MealLog(Base):
    __tablename__ = "meal_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    food_item_id = Column(Integer, ForeignKey("food_items.id"))
    meal_type = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat = Column(Float, default=0)
    logged_at = Column(DateTime, default=datetime.utcnow)
    planned = Column(Boolean, default=False)  # Whether this was a planned meal
    
    # Relationships
    user = relationship("User", back_populates="meal_logs")
    food_item = relationship("FoodItem")

class Goal(Base):
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    goal_type = Column(String, nullable=False)  # weight_loss, muscle_gain, maintenance
    target_weight = Column(Float)
    target_calories = Column(Float)
    target_protein = Column(Float)
    target_carbs = Column(Float)
    target_fat = Column(Float)
    start_date = Column(DateTime, default=datetime.utcnow)
    target_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="goals")

class Challenge(Base):
    __tablename__ = "challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    rules = Column(Text)  # JSON string of rules
    reward_points = Column(Integer, default=0)
    active_from = Column(DateTime, default=datetime.utcnow)
    active_to = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    challenge_id = Column(Integer, ForeignKey("challenges.id"))
    points_earned = Column(Integer, default=0)
    completed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="achievements")
    challenge = relationship("Challenge")

class FoodRating(Base):
    __tablename__ = "food_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    food_id = Column(Integer, ForeignKey("food_items.id"))
    rating = Column(Float, nullable=False)  # 1-5 scale
    review = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    food_item = relationship("FoodItem")

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    preference_type = Column(String, nullable=False)  # cuisine, macro, timing, etc.
    preference_data = Column(Text)  # JSON string of preference data
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class Recipe(Base):
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    ingredients = Column(Text)  # JSON string of ingredients
    instructions = Column(Text)  # JSON string of instructions
    nutrition = Column(Text)  # JSON string of nutrition data
    prep_time = Column(Integer, default=30)  # minutes
    cook_time = Column(Integer, default=20)  # minutes
    difficulty = Column(String, default="medium")
    cuisine_type = Column(String, default="mixed")
    health_benefits = Column(Text)  # JSON string of health benefits
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()