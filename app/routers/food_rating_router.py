# app/routers/food_rating_router.py
"""
API endpoints for food rating and personalized recommendations
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.auth import get_current_active_user
from app.services.food_rating_service import FoodRatingService
from app.schemas import FoodRatingRequest, FoodRatingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/food-ratings", tags=["food-ratings"])

@router.post("/rate")
async def rate_food(
    food_id: int,
    rating: float = Query(..., ge=1.0, le=5.0, description="Rating from 1.0 to 5.0"),
    review: Optional[str] = Query(None, description="Optional review text"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate a food item"""
    try:
        service = FoodRatingService(db)
        result = service.rate_food(current_user.id, food_id, rating, review)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in rate_food endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rate food: {str(e)}")

@router.get("/my-ratings")
async def get_my_ratings(
    limit: int = Query(50, ge=1, le=100, description="Number of ratings to return"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's food ratings"""
    try:
        service = FoodRatingService(db)
        ratings = service.get_user_food_ratings(current_user.id, limit)
        
        return {
            "success": True,
            "ratings": ratings,
            "total_count": len(ratings)
        }
        
    except Exception as e:
        logger.error(f"Error in get_my_ratings endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get ratings: {str(e)}")

@router.get("/food/{food_id}/stats")
async def get_food_rating_stats(
    food_id: int,
    db: Session = Depends(get_db)
):
    """Get rating statistics for a specific food item"""
    try:
        service = FoodRatingService(db)
        stats = service.get_food_rating_stats(food_id)
        
        if "error" in stats:
            raise HTTPException(status_code=400, detail=stats["error"])
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error in get_food_rating_stats endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get food stats: {str(e)}")

@router.get("/recommendations")
async def get_personalized_recommendations(
    limit: int = Query(10, ge=1, le=20, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get personalized food recommendations based on user ratings"""
    try:
        service = FoodRatingService(db)
        recommendations = service.get_personalized_food_recommendations(current_user.id, limit)
        
        return {
            "success": True,
            "recommendations": recommendations,
            "total_count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error in get_personalized_recommendations endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

@router.get("/top-rated")
async def get_top_rated_foods(
    limit: int = Query(10, ge=1, le=50, description="Number of top-rated foods"),
    min_ratings: int = Query(5, ge=1, description="Minimum number of ratings required"),
    db: Session = Depends(get_db)
):
    """Get top-rated foods across all users"""
    try:
        service = FoodRatingService(db)
        
        # Get all food items with ratings
        from app.database import FoodRating, FoodItem
        from sqlalchemy import func
        
        top_foods = db.query(
            FoodItem.id,
            FoodItem.name,
            FoodItem.cuisine_type,
            FoodItem.calories,
            func.avg(FoodRating.rating).label('avg_rating'),
            func.count(FoodRating.id).label('rating_count')
        ).join(FoodRating, FoodItem.id == FoodRating.food_id)\
         .group_by(FoodItem.id)\
         .having(func.count(FoodRating.id) >= min_ratings)\
         .order_by(func.avg(FoodRating.rating).desc())\
         .limit(limit).all()
        
        result = []
        for food in top_foods:
            result.append({
                "food_id": food.id,
                "name": food.name,
                "cuisine_type": food.cuisine_type,
                "calories": food.calories,
                "average_rating": round(float(food.avg_rating), 2),
                "rating_count": food.rating_count
            })
        
        return {
            "success": True,
            "top_rated_foods": result,
            "total_count": len(result)
        }
        
    except Exception as e:
        logger.error(f"Error in get_top_rated_foods endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get top-rated foods: {str(e)}")
