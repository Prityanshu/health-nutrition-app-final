# app/routers/recipe_interaction_router.py
"""
API endpoints for recipe interactions and cooking behavior tracking
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.auth import get_current_active_user
from app.services.recipe_interaction_service import RecipeInteractionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recipe-interactions", tags=["recipe-interactions"])

@router.post("/track")
async def track_recipe_interaction(
    recipe_id: int = Body(..., description="Recipe ID"),
    interaction_type: str = Body(..., description="Type of interaction: viewed, cooked, rated, saved, shared, favorited"),
    interaction_data: Optional[Dict[str, Any]] = Body(None, description="Additional interaction data"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Track user interaction with a recipe"""
    try:
        service = RecipeInteractionService(db)
        result = service.track_recipe_interaction(
            current_user.id, 
            recipe_id, 
            interaction_type, 
            interaction_data
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error in track_recipe_interaction endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to track interaction: {str(e)}")

@router.get("/my-interactions")
async def get_my_interactions(
    interaction_type: Optional[str] = Query(None, description="Filter by interaction type"),
    limit: int = Query(50, ge=1, le=100, description="Number of interactions to return"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's recipe interactions"""
    try:
        service = RecipeInteractionService(db)
        interactions = service.get_user_recipe_interactions(
            current_user.id, 
            interaction_type, 
            limit
        )
        
        return {
            "success": True,
            "interactions": interactions,
            "total_count": len(interactions)
        }
        
    except Exception as e:
        logger.error(f"Error in get_my_interactions endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get interactions: {str(e)}")

@router.get("/recipe/{recipe_id}/stats")
async def get_recipe_popularity_stats(
    recipe_id: int,
    db: Session = Depends(get_db)
):
    """Get popularity statistics for a specific recipe"""
    try:
        service = RecipeInteractionService(db)
        stats = service.get_recipe_popularity_stats(recipe_id)
        
        if "error" in stats:
            raise HTTPException(status_code=400, detail=stats["error"])
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error in get_recipe_popularity_stats endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recipe stats: {str(e)}")

@router.get("/recommendations")
async def get_recipe_recommendations(
    limit: int = Query(10, ge=1, le=20, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get personalized recipe recommendations based on user interactions"""
    try:
        service = RecipeInteractionService(db)
        recommendations = service.get_personalized_recipe_recommendations(current_user.id, limit)
        
        return {
            "success": True,
            "recommendations": recommendations,
            "total_count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error in get_recipe_recommendations endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

@router.get("/cooking-insights")
async def get_cooking_behavior_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get insights about user's cooking behavior and patterns"""
    try:
        service = RecipeInteractionService(db)
        insights = service.get_cooking_behavior_insights(current_user.id)
        
        if "error" in insights:
            raise HTTPException(status_code=400, detail=insights["error"])
        
        return {
            "success": True,
            "insights": insights
        }
        
    except Exception as e:
        logger.error(f"Error in get_cooking_behavior_insights endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cooking insights: {str(e)}")

@router.post("/quick-track")
async def quick_track_interaction(
    recipe_id: int = Body(..., description="Recipe ID"),
    action: str = Body(..., description="Quick action: view, cook, save, favorite"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Quickly track common recipe interactions"""
    try:
        # Map quick actions to interaction types
        action_mapping = {
            "view": "viewed",
            "cook": "cooked", 
            "save": "saved",
            "favorite": "favorited"
        }
        
        if action not in action_mapping:
            raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {list(action_mapping.keys())}")
        
        interaction_type = action_mapping[action]
        
        service = RecipeInteractionService(db)
        result = service.track_recipe_interaction(
            current_user.id,
            recipe_id,
            interaction_type,
            {"quick_action": action}
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "message": f"Recipe {action}d successfully",
            "action": action,
            "recipe_id": recipe_id
        }
        
    except Exception as e:
        logger.error(f"Error in quick_track_interaction endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to track interaction: {str(e)}")

@router.get("/popular-recipes")
async def get_popular_recipes(
    limit: int = Query(10, ge=1, le=50, description="Number of popular recipes"),
    interaction_type: str = Query("cooked", description="Type of interaction to base popularity on"),
    db: Session = Depends(get_db)
):
    """Get most popular recipes based on interactions"""
    try:
        from app.models.enhanced_models import RecipeInteraction
        from sqlalchemy import func
        
        # Get recipes with most interactions of specified type
        popular_recipes = db.query(
            RecipeInteraction.recipe_id,
            func.count(RecipeInteraction.id).label('interaction_count')
        ).filter(RecipeInteraction.interaction_type == interaction_type)\
         .group_by(RecipeInteraction.recipe_id)\
         .order_by(func.count(RecipeInteraction.id).desc())\
         .limit(limit).all()
        
        result = []
        for recipe in popular_recipes:
            result.append({
                "recipe_id": recipe.recipe_id,
                "interaction_count": recipe.interaction_count,
                "interaction_type": interaction_type
            })
        
        return {
            "success": True,
            "popular_recipes": result,
            "total_count": len(result),
            "based_on": interaction_type
        }
        
    except Exception as e:
        logger.error(f"Error in get_popular_recipes endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get popular recipes: {str(e)}")
