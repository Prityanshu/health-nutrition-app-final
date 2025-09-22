# app/schemas/social_cooking_schemas.py
"""
Pydantic schemas for social cooking data and family preferences
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class SocialCookingProfileRequest(BaseModel):
    """Request schema for updating social cooking profile"""
    family_size: Optional[int] = Field(None, ge=1, le=20, description="Number of family members")
    cooking_for_others: Optional[bool] = Field(None, description="Whether user cooks for others")
    family_dietary_restrictions: Optional[List[str]] = Field(None, description="Family dietary restrictions")
    social_meal_preferences: Optional[Dict[str, Any]] = Field(None, description="Social meal preferences")

class SocialCookingProfile(BaseModel):
    """Schema for social cooking profile"""
    user_id: int
    cooking_for_others: bool
    family_size: int
    dietary_restrictions_family: List[str]
    social_meal_preferences: Dict[str, Any]
    shared_recipe_preferences: Dict[str, Any]
    last_updated: datetime

class SocialCookingProfileResponse(BaseModel):
    """Response schema for social cooking profile"""
    success: bool
    profile: SocialCookingProfile

class FamilyFriendlyRecommendation(BaseModel):
    """Schema for family-friendly recommendation"""
    food_id: int
    name: str
    calories: Optional[float]
    reason: str

class FamilyFriendlyRecommendationsResponse(BaseModel):
    """Response schema for family-friendly recommendations"""
    success: bool
    recommendations: List[FamilyFriendlyRecommendation]
    total_count: int

class FamilyEatingPattern(BaseModel):
    """Schema for family eating patterns"""
    family_size: int
    cooking_frequency: str
    preferred_cuisines: List[str]
    meal_timing_patterns: Dict[str, Any]
    portion_sizes: Dict[str, Any]
    dietary_accommodations: Dict[str, Any]

class FamilyPatternsResponse(BaseModel):
    """Response schema for family eating patterns"""
    success: bool
    patterns: FamilyEatingPattern

class SharedRecipeSuggestion(BaseModel):
    """Schema for shared recipe suggestion"""
    recipe_id: int
    title: str
    reason: str
    serves: int

class SharedRecipeSuggestionsResponse(BaseModel):
    """Response schema for shared recipe suggestions"""
    success: bool
    suggestions: List[SharedRecipeSuggestion]
    occasion: str
    total_count: int

class SharedCookingExperienceRequest(BaseModel):
    """Request schema for tracking shared cooking experience"""
    recipe_id: int = Field(..., description="ID of the recipe")
    family_feedback: Dict[str, Any] = Field(..., description="Family feedback on the cooking experience")
    occasion: str = Field("family_meal", description="Occasion for the shared cooking")

class SharedCookingExperienceResponse(BaseModel):
    """Response schema for shared cooking experience"""
    success: bool
    message: str

class SocialCookingInsights(BaseModel):
    """Schema for comprehensive social cooking insights"""
    profile: SocialCookingProfile
    eating_patterns: FamilyEatingPattern
    sample_recommendations: List[FamilyFriendlyRecommendation]
    cooking_for_family: bool
    family_size: int

class SocialCookingInsightsResponse(BaseModel):
    """Response schema for social cooking insights"""
    success: bool
    insights: SocialCookingInsights

class QuickProfileSetupRequest(BaseModel):
    """Request schema for quick profile setup"""
    family_size: int = Field(..., ge=1, le=20, description="Number of family members")
    cooking_for_family: bool = Field(..., description="Do you cook for your family?")

class QuickProfileSetupResponse(BaseModel):
    """Response schema for quick profile setup"""
    success: bool
    message: str
    profile: SocialCookingProfile
