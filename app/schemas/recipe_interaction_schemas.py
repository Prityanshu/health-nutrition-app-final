# app/schemas/recipe_interaction_schemas.py
"""
Pydantic schemas for recipe interaction tracking
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class RecipeInteractionRequest(BaseModel):
    """Request schema for tracking recipe interaction"""
    recipe_id: int = Field(..., description="ID of the recipe")
    interaction_type: str = Field(..., description="Type of interaction: viewed, cooked, rated, saved, shared, favorited")
    interaction_data: Optional[Dict[str, Any]] = Field(None, description="Additional interaction data")

class RecipeInteractionResponse(BaseModel):
    """Response schema for recipe interaction"""
    success: bool
    message: str
    interaction_id: int

class RecipeInteractionItem(BaseModel):
    """Schema for a recipe interaction item"""
    id: int
    recipe_id: int
    interaction_type: str
    interaction_data: Optional[Dict[str, Any]]
    created_at: datetime

class RecipeInteractionStats(BaseModel):
    """Schema for recipe popularity statistics"""
    recipe_id: int
    total_interactions: int
    interaction_types: Dict[str, int]
    popularity_score: float

class RecipeRecommendation(BaseModel):
    """Schema for recipe recommendation"""
    recipe_id: int
    title: str
    reason: str

class RecipeRecommendationResponse(BaseModel):
    """Response schema for recipe recommendations"""
    success: bool
    recommendations: List[RecipeRecommendation]
    total_count: int

class CookingBehaviorInsights(BaseModel):
    """Schema for cooking behavior insights"""
    cooking_frequency: str
    skill_level: str
    total_recipes_interacted: int
    favorite_interaction_types: List[str]
    cooking_trends: Dict[str, Any]
    engagement_score: float

class CookingInsightsResponse(BaseModel):
    """Response schema for cooking insights"""
    success: bool
    insights: CookingBehaviorInsights

class QuickTrackRequest(BaseModel):
    """Request schema for quick interaction tracking"""
    recipe_id: int = Field(..., description="ID of the recipe")
    action: str = Field(..., description="Quick action: view, cook, save, favorite")

class QuickTrackResponse(BaseModel):
    """Response schema for quick tracking"""
    success: bool
    message: str
    action: str
    recipe_id: int

class PopularRecipe(BaseModel):
    """Schema for popular recipe"""
    recipe_id: int
    interaction_count: int
    interaction_type: str

class PopularRecipesResponse(BaseModel):
    """Response schema for popular recipes"""
    success: bool
    popular_recipes: List[PopularRecipe]
    total_count: int
    based_on: str
