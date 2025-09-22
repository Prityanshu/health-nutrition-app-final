# app/schemas/food_rating_schemas.py
"""
Pydantic schemas for food rating and recommendation features
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class FoodRatingRequest(BaseModel):
    """Request schema for rating a food item"""
    food_id: int = Field(..., description="ID of the food item to rate")
    rating: float = Field(..., ge=1.0, le=5.0, description="Rating from 1.0 to 5.0")
    review: Optional[str] = Field(None, description="Optional review text")

class FoodRatingResponse(BaseModel):
    """Response schema for food rating"""
    success: bool
    message: str
    rating: float
    food_name: str

class FoodRatingItem(BaseModel):
    """Schema for a food rating item"""
    id: int
    food_id: int
    food_name: str
    rating: float
    review: Optional[str]
    created_at: datetime

class FoodRatingStats(BaseModel):
    """Schema for food rating statistics"""
    food_id: int
    average_rating: float
    total_ratings: int
    rating_distribution: Dict[str, int]

class FoodRecommendation(BaseModel):
    """Schema for food recommendation"""
    food_id: int
    name: str
    cuisine_type: Optional[str]
    calories: Optional[float]
    reason: str

class FoodRecommendationResponse(BaseModel):
    """Response schema for food recommendations"""
    success: bool
    recommendations: List[FoodRecommendation]
    total_count: int

class TopRatedFood(BaseModel):
    """Schema for top-rated food item"""
    food_id: int
    name: str
    cuisine_type: Optional[str]
    calories: Optional[float]
    average_rating: float
    rating_count: int

class TopRatedFoodsResponse(BaseModel):
    """Response schema for top-rated foods"""
    success: bool
    top_rated_foods: List[TopRatedFood]
    total_count: int
