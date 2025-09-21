# app/models/enhanced_challenge_models.py
"""
Enhanced challenge models for data-driven personalized challenges
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import json
from enum import Enum as PyEnum

from app.database import Base

class ChallengeType(PyEnum):
    NUTRITION = "nutrition"
    WORKOUT = "workout"
    HYBRID = "hybrid"
    CONSISTENCY = "consistency"
    VARIETY = "variety"
    GOAL_ORIENTED = "goal_oriented"

class ChallengeDifficulty(PyEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"

class PersonalizedChallenge(Base):
    """Data-driven personalized challenges based on user behavior"""
    __tablename__ = "personalized_challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_type = Column(Enum(ChallengeType), nullable=False)
    difficulty = Column(Enum(ChallengeDifficulty), nullable=False)
    
    # Challenge details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    target_value = Column(Float, nullable=False)  # Target to achieve
    current_value = Column(Float, default=0.0)    # Current progress
    unit = Column(String, nullable=False)         # e.g., "calories", "workouts", "days"
    
    # Data-driven parameters
    baseline_data = Column(JSON)                  # User's baseline data when challenge was created
    target_improvement = Column(Float)            # Percentage improvement target
    personalization_factors = Column(JSON)        # Factors used for personalization
    
    # Challenge timeline
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Progress tracking
    daily_targets = Column(JSON)                  # Daily breakdown of targets
    progress_history = Column(JSON)               # Daily progress tracking
    completion_percentage = Column(Float, default=0.0)
    
    # Rewards and motivation
    points_reward = Column(Integer, default=100)
    badge_reward = Column(String)                 # Badge to earn
    motivational_messages = Column(JSON)          # Personalized motivational messages
    
    # Relationships
    user = relationship("User")

class ChallengeTemplate(Base):
    """Templates for generating personalized challenges"""
    __tablename__ = "challenge_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_type = Column(Enum(ChallengeType), nullable=False)
    difficulty = Column(Enum(ChallengeDifficulty), nullable=False)
    
    # Template details
    title_template = Column(String, nullable=False)
    description_template = Column(Text, nullable=False)
    unit = Column(String, nullable=False)
    
    # Personalization rules
    baseline_requirements = Column(JSON)          # What data is needed
    improvement_ranges = Column(JSON)             # Improvement percentage ranges by difficulty
    target_calculation_rules = Column(JSON)       # How to calculate targets
    personalization_rules = Column(JSON)          # Rules for personalization
    
    # Activation conditions
    min_user_data_days = Column(Integer, default=7)  # Minimum days of user data needed
    max_challenges_per_type = Column(Integer, default=1)  # Max active challenges of this type
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserChallengeProgress(Base):
    """Detailed progress tracking for challenges"""
    __tablename__ = "user_challenge_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("personalized_challenges.id"), nullable=False)
    
    # Daily progress
    progress_date = Column(DateTime, nullable=False)
    daily_value = Column(Float, default=0.0)
    daily_target = Column(Float, nullable=False)
    completion_percentage = Column(Float, default=0.0)
    
    # Context data
    nutrition_data = Column(JSON)                 # Nutrition data for that day
    workout_data = Column(JSON)                  # Workout data for that day
    mood_data = Column(JSON)                     # User mood/energy level
    
    # Achievements
    streak_days = Column(Integer, default=0)
    best_day_performance = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    challenge = relationship("PersonalizedChallenge")

class ChallengeAchievement(Base):
    """Achievements earned through challenges"""
    __tablename__ = "challenge_achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("personalized_challenges.id"), nullable=False)
    
    # Achievement details
    achievement_type = Column(String, nullable=False)  # completion, streak, improvement, etc.
    achievement_title = Column(String, nullable=False)
    achievement_description = Column(Text, nullable=False)
    points_earned = Column(Integer, default=0)
    badge_earned = Column(String)
    
    # Achievement data
    achievement_data = Column(JSON)              # Specific data about the achievement
    achieved_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    challenge = relationship("PersonalizedChallenge")

class ChallengeRecommendation(Base):
    """AI-generated challenge recommendations"""
    __tablename__ = "challenge_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Recommendation details
    recommended_challenge_type = Column(Enum(ChallengeType), nullable=False)
    recommended_difficulty = Column(Enum(ChallengeDifficulty), nullable=False)
    confidence_score = Column(Float, nullable=False)  # 0-1 confidence in recommendation
    
    # Reasoning
    recommendation_reasons = Column(JSON)        # Why this challenge was recommended
    user_weaknesses = Column(JSON)              # Areas where user needs improvement
    user_strengths = Column(JSON)               # Areas where user is doing well
    
    # Generated challenge details
    suggested_title = Column(String, nullable=False)
    suggested_description = Column(Text, nullable=False)
    suggested_target = Column(Float, nullable=False)
    suggested_duration_days = Column(Integer, default=7)
    
    # Status
    is_accepted = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    user = relationship("User")
