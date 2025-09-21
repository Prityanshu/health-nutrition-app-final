from fastapi import APIRouter, HTTPException, Query, Path, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime
import logging
from sqlalchemy.orm import Session

# Import the service
from ..services.ai_recipe_service import recipe_service, RecipeGeneratorService
from ..database import get_db, FoodItem

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])

# Pydantic models for API requests and responses
class CuisineType(str, Enum):
    INDIAN = "indian"
    MEDITERRANEAN = "mediterranean"
    ASIAN = "asian"
    ITALIAN = "italian"
    MEXICAN = "mexican"
    FUSION = "fusion"

class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DESSERT = "dessert"

class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class RecipeGenerationRequest(BaseModel):
    """Request model for recipe generation"""
    cuisine_preference: List[CuisineType] = Field(
        default=[CuisineType.INDIAN], 
        description="Preferred cuisines"
    )
    dietary_restrictions: List[str] = Field(
        default=[], 
        description="Dietary restrictions (e.g., 'vegetarian', 'vegan', 'gluten-free')"
    )
    available_ingredients: List[str] = Field(
        default=[], 
        description="Available ingredients to include"
    )
    target_calories: int = Field(
        default=400, 
        ge=100, 
        le=1500, 
        description="Target calories per serving"
    )
    budget_limit: float = Field(
        default=200, 
        ge=50, 
        le=1000, 
        description="Budget limit in rupees"
    )
    meal_type: MealType = Field(
        default=MealType.LUNCH, 
        description="Type of meal"
    )
    difficulty_level: DifficultyLevel = Field(
        default=DifficultyLevel.EASY, 
        description="Cooking difficulty level"
    )
    time_constraint: int = Field(
        default=60, 
        ge=15, 
        le=300, 
        description="Time constraint in minutes"
    )
    health_conditions: List[str] = Field(
        default=[], 
        description="Health conditions to consider (e.g., 'diabetes', 'hypertension')"
    )
    serving_size: int = Field(
        default=2, 
        ge=1, 
        le=12, 
        description="Number of servings"
    )

    @validator('cuisine_preference', pre=True)
    def validate_cuisine_preference(cls, v):
        if isinstance(v, str):
            return [v]
        return v

class RecipeScaleRequest(BaseModel):
    """Request model for recipe scaling"""
    new_servings: int = Field(
        ge=1, 
        le=20, 
        description="New number of servings"
    )

class SubstitutionRequest(BaseModel):
    """Request model for ingredient substitutions"""
    ingredient: str = Field(description="Original ingredient name")
    dietary_restrictions: List[str] = Field(default=[], description="Dietary restrictions")
    budget_constraint: float = Field(default=100, description="Budget constraint per unit")

class RecipeResponse(BaseModel):
    """Response model for recipe data"""
    id: str
    name: str
    description: str
    cuisine: str
    category: str
    difficulty: str
    preparation_time: int
    cooking_time: int
    total_time: int
    servings: int
    ingredients: List[Dict[str, Any]]
    instructions: List[str]
    nutrition_per_serving: Dict[str, float]
    cost_per_serving: float
    total_cost: float
    tags: List[str]
    seasonal_tags: List[str]
    health_benefits: List[str]
    created_at: str
    rating: float
    review_count: int

class PaginatedRecipesResponse(BaseModel):
    """Response model for paginated recipe lists"""
    recipes: List[RecipeResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool

class NutritionAnalysisResponse(BaseModel):
    """Response model for nutrition analysis"""
    nutrition_per_serving: Dict[str, float]
    daily_value_percentage: Dict[str, float]
    health_score: int
    dietary_flags: List[str]

class SubstitutionResponse(BaseModel):
    """Response model for ingredient substitutions"""
    original: str
    substitution: str
    cost_difference: float
    nutrition_impact: str

# Dependency to get service instance
async def get_recipe_service() -> RecipeGeneratorService:
    return recipe_service

@router.post("/generate", response_model=RecipeResponse, status_code=201)
async def generate_recipe(
    request: RecipeGenerationRequest,
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Generate a new AI recipe based on the provided parameters.
    
    This endpoint creates a personalized recipe considering:
    - Cuisine preferences
    - Dietary restrictions
    - Available ingredients
    - Budget and time constraints
    - Health conditions
    """
    try:
        # Convert to dictionary for service
        request_dict = request.dict()
        request_dict["cuisine_preference"] = [c.value for c in request.cuisine_preference]
        request_dict["meal_type"] = request.meal_type.value
        request_dict["difficulty_level"] = request.difficulty_level.value
        
        recipe = await service.generate_recipe(request_dict)
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Recipe generated successfully",
                "data": recipe
            }
        )
        
    except Exception as e:
        logger.error(f"Error in generate_recipe endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: str = Path(..., description="Recipe ID"),
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Retrieve a specific recipe by its ID.
    """
    try:
        recipe = await service.get_recipe_by_id(recipe_id)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Recipe retrieved successfully",
                "data": recipe
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_recipe endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=PaginatedRecipesResponse)
async def get_all_recipes(
    limit: int = Query(default=20, ge=1, le=100, description="Number of recipes to return"),
    offset: int = Query(default=0, ge=0, description="Number of recipes to skip"),
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Retrieve all cached recipes with pagination.
    """
    try:
        result = await service.get_all_recipes(limit=limit, offset=offset)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Retrieved {len(result['recipes'])} recipes",
                "data": result
            }
        )
    except Exception as e:
        logger.error(f"Error in get_all_recipes endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{recipe_id}/scale", response_model=RecipeResponse)
async def scale_recipe(
    recipe_id: str = Path(..., description="Recipe ID to scale"),
    request: RecipeScaleRequest = None,
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Scale an existing recipe to a different number of servings.
    
    This will adjust ingredient quantities, cooking times, and recalculate costs.
    """
    try:
        scaled_recipe = await service.scale_recipe(recipe_id, request.new_servings)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Recipe scaled to {request.new_servings} servings",
                "data": scaled_recipe
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scale_recipe endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/recipes")
async def search_recipes(
    query: str = Query(default="", description="Search query for recipe name or description"),
    cuisine: Optional[CuisineType] = Query(default=None, description="Filter by cuisine"),
    category: Optional[MealType] = Query(default=None, description="Filter by meal category"),
    difficulty: Optional[DifficultyLevel] = Query(default=None, description="Filter by difficulty"),
    max_prep_time: Optional[int] = Query(default=None, ge=1, description="Maximum preparation time in minutes"),
    tags: Optional[List[str]] = Query(default=None, description="Filter by tags"),
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Search recipes based on various criteria.
    
    Supports filtering by:
    - Text search in name/description
    - Cuisine type
    - Meal category
    - Difficulty level
    - Maximum preparation time
    - Tags
    """
    try:
        results = await service.search_recipes(
            query=query,
            cuisine=cuisine.value if cuisine else None,
            category=category.value if category else None,
            difficulty=difficulty.value if difficulty else None,
            max_prep_time=max_prep_time,
            tags=tags or []
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Found {len(results)} recipes",
                "data": {
                    "recipes": results,
                    "count": len(results)
                }
            }
        )
    except Exception as e:
        logger.error(f"Error in search_recipes endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{recipe_id}/nutrition", response_model=NutritionAnalysisResponse)
async def get_recipe_nutrition_analysis(
    recipe_id: str = Path(..., description="Recipe ID for nutrition analysis"),
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Get detailed nutrition analysis for a specific recipe.
    
    Returns:
    - Nutrition facts per serving
    - Daily value percentages
    - Health score (0-100)
    - Dietary flags
    """
    try:
        analysis = await service.get_recipe_nutrition_analysis(recipe_id)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Nutrition analysis completed",
                "data": analysis
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in nutrition analysis endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/substitutions", response_model=List[SubstitutionResponse])
async def get_ingredient_substitutions(
    request: SubstitutionRequest,
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Get ingredient substitution suggestions based on dietary restrictions and budget.
    
    Useful for adapting recipes when certain ingredients are unavailable or don't meet dietary requirements.
    """
    try:
        substitutions = await service.get_ingredient_substitutions(
            ingredient=request.ingredient,
            dietary_restrictions=request.dietary_restrictions,
            budget_constraint=request.budget_constraint
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Found {len(substitutions)} substitutions",
                "data": substitutions
            }
        )
    except Exception as e:
        logger.error(f"Error in substitutions endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cuisines/available")
async def get_available_cuisines():
    """
    Get list of available cuisine types.
    """
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Available cuisines retrieved",
            "data": {
                "cuisines": [cuisine.value for cuisine in CuisineType],
                "count": len(CuisineType)
            }
        }
    )

@router.get("/categories/available")
async def get_available_categories():
    """
    Get list of available meal categories.
    """
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Available categories retrieved",
            "data": {
                "categories": [category.value for category in MealType],
                "count": len(MealType)
            }
        }
    )

@router.get("/difficulties/available")
async def get_available_difficulties():
    """
    Get list of available difficulty levels.
    """
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Available difficulty levels retrieved",
            "data": {
                "difficulties": [difficulty.value for difficulty in DifficultyLevel],
                "count": len(DifficultyLevel)
            }
        }
    )

@router.get("/stats/overview")
async def get_recipe_stats(
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Get overview statistics of cached recipes.
    """
    try:
        all_recipes = await service.get_all_recipes(limit=1000, offset=0)
        recipes = all_recipes["recipes"]
        
        if not recipes:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "No recipes available for statistics",
                    "data": {
                        "total_recipes": 0,
                        "avg_prep_time": 0,
                        "avg_cost_per_serving": 0,
                        "cuisine_distribution": {},
                        "difficulty_distribution": {},
                        "category_distribution": {}
                    }
                }
            )
        
        # Calculate statistics
        total_recipes = len(recipes)
        avg_prep_time = sum(r["preparation_time"] for r in recipes) / total_recipes
        avg_cooking_time = sum(r["cooking_time"] for r in recipes) / total_recipes
        avg_cost = sum(r["cost_per_serving"] for r in recipes) / total_recipes
        avg_calories = sum(r["nutrition_per_serving"]["calories"] for r in recipes) / total_recipes
        
        # Distribution calculations
        cuisine_dist = {}
        difficulty_dist = {}
        category_dist = {}
        
        for recipe in recipes:
            cuisine = recipe["cuisine"]
            difficulty = recipe["difficulty"]
            category = recipe["category"]
            
            cuisine_dist[cuisine] = cuisine_dist.get(cuisine, 0) + 1
            difficulty_dist[difficulty] = difficulty_dist.get(difficulty, 0) + 1
            category_dist[category] = category_dist.get(category, 0) + 1
        
        # Most popular tags
        all_tags = []
        for recipe in recipes:
            all_tags.extend(recipe.get("tags", []))
        
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        stats = {
            "total_recipes": total_recipes,
            "averages": {
                "prep_time": round(avg_prep_time, 1),
                "cooking_time": round(avg_cooking_time, 1),
                "total_time": round(avg_prep_time + avg_cooking_time, 1),
                "cost_per_serving": round(avg_cost, 2),
                "calories_per_serving": round(avg_calories, 1)
            },
            "distributions": {
                "cuisine": cuisine_dist,
                "difficulty": difficulty_dist,
                "category": category_dist
            },
            "popular_tags": [{"tag": tag, "count": count} for tag, count in popular_tags],
            "ranges": {
                "prep_time": {
                    "min": min(r["preparation_time"] for r in recipes),
                    "max": max(r["preparation_time"] for r in recipes)
                },
                "cost": {
                    "min": round(min(r["cost_per_serving"] for r in recipes), 2),
                    "max": round(max(r["cost_per_serving"] for r in recipes), 2)
                },
                "calories": {
                    "min": round(min(r["nutrition_per_serving"]["calories"] for r in recipes), 1),
                    "max": round(max(r["nutrition_per_serving"]["calories"] for r in recipes), 1)
                }
            }
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Recipe statistics retrieved successfully",
                "data": stats
            }
        )
        
    except Exception as e:
        logger.error(f"Error in recipe stats endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{recipe_id}")
async def delete_recipe(
    recipe_id: str = Path(..., description="Recipe ID to delete"),
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Delete a recipe from the cache.
    """
    try:
        # Check if recipe exists
        await service.get_recipe_by_id(recipe_id)
        
        # Remove from cache - need to find the actual cache key
        recipes_to_remove = []
        for cache_key, cached_recipe in service.recipe_cache.items():
            if cached_recipe["id"] == recipe_id:
                recipes_to_remove.append(cache_key)
        
        if not recipes_to_remove:
            raise HTTPException(status_code=404, detail="Recipe not found in cache")
        
        # Remove all matching recipes (including scaled versions)
        for cache_key in recipes_to_remove:
            del service.recipe_cache[cache_key]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Recipe deleted successfully",
                "data": {
                    "deleted_recipe_id": recipe_id,
                    "versions_removed": len(recipes_to_remove)
                }
            }
        )
        
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Recipe not found")
        raise
    except Exception as e:
        logger.error(f"Error in delete_recipe endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{recipe_id}/rate")
async def rate_recipe(
    recipe_id: str = Path(..., description="Recipe ID to rate"),
    rating: float = Query(..., ge=0.0, le=5.0, description="Rating from 0.0 to 5.0"),
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Rate a recipe (0.0 to 5.0 stars).
    """
    try:
        # Get the recipe
        recipe = await service.get_recipe_by_id(recipe_id)
        
        # Update rating (simple average for now)
        current_rating = recipe.get("rating", 0.0)
        current_count = recipe.get("review_count", 0)
        
        new_count = current_count + 1
        new_rating = ((current_rating * current_count) + rating) / new_count
        
        # Update in cache - find the cache key
        for cache_key, cached_recipe in service.recipe_cache.items():
            if cached_recipe["id"] == recipe_id:
                cached_recipe["rating"] = round(new_rating, 2)
                cached_recipe["review_count"] = new_count
                break
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Recipe rated successfully",
                "data": {
                    "recipe_id": recipe_id,
                    "new_rating": round(new_rating, 2),
                    "total_reviews": new_count,
                    "your_rating": rating
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in rate_recipe endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{recipe_id}/similar")
async def get_similar_recipes(
    recipe_id: str = Path(..., description="Recipe ID to find similar recipes for"),
    limit: int = Query(default=5, ge=1, le=20, description="Number of similar recipes to return"),
    service: RecipeGeneratorService = Depends(get_recipe_service)
):
    """
    Get recipes similar to the specified recipe based on cuisine, ingredients, and tags.
    """
    try:
        # Get the base recipe
        base_recipe = await service.get_recipe_by_id(recipe_id)
        
        # Get all recipes for comparison
        all_recipes_result = await service.get_all_recipes(limit=1000, offset=0)
        all_recipes = all_recipes_result["recipes"]
        
        similar_recipes = []
        
        for recipe in all_recipes:
            if recipe["id"] == recipe_id:
                continue  # Skip the same recipe
            
            similarity_score = 0
            
            # Same cuisine (+3 points)
            if recipe["cuisine"] == base_recipe["cuisine"]:
                similarity_score += 3
            
            # Same category (+2 points)
            if recipe["category"] == base_recipe["category"]:
                similarity_score += 2
            
            # Same difficulty (+1 point)
            if recipe["difficulty"] == base_recipe["difficulty"]:
                similarity_score += 1
            
            # Common tags (+1 point per common tag)
            base_tags = set(base_recipe.get("tags", []))
            recipe_tags = set(recipe.get("tags", []))
            common_tags = base_tags.intersection(recipe_tags)
            similarity_score += len(common_tags)
            
            # Similar cooking time (+1 point if within 15 minutes)
            time_diff = abs(recipe["cooking_time"] - base_recipe["cooking_time"])
            if time_diff <= 15:
                similarity_score += 1
            
            # Similar cost (+1 point if within ₹50)
            cost_diff = abs(recipe["cost_per_serving"] - base_recipe["cost_per_serving"])
            if cost_diff <= 50:
                similarity_score += 1
            
            if similarity_score > 0:
                similar_recipes.append({
                    **recipe,
                    "similarity_score": similarity_score
                })
        
        # Sort by similarity score and return top results
        similar_recipes.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_similar = similar_recipes[:limit]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Found {len(top_similar)} similar recipes",
                "data": {
                    "base_recipe": {
                        "id": base_recipe["id"],
                        "name": base_recipe["name"]
                    },
                    "similar_recipes": top_similar,
                    "count": len(top_similar)
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_similar_recipes endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ingredients/search")
async def search_ingredients(
    q: str = Query(..., description="Search query for ingredients"),
    limit: int = Query(20, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    Search for ingredients using MyFitnessPal data with autocomplete functionality.
    
    This endpoint provides ingredient suggestions for the AI recipe generator,
    using the same food database as the meal logging feature.
    """
    try:
        if len(q.strip()) < 2:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Query too short",
                    "data": {
                        "ingredients": [],
                        "count": 0
                    }
                }
            )
        
        # Search in food items for ingredients
        search_term = f"%{q.lower()}%"
        food_items = db.query(FoodItem).filter(
            FoodItem.name.ilike(search_term)
        ).filter(
            FoodItem.calories <= 1000  # Filter out very high calorie items
        ).filter(
            FoodItem.sodium_mg <= 1000  # Filter out high sodium items
        ).order_by(
            FoodItem.name
        ).limit(limit).all()
        
        # Convert to ingredient format
        ingredients = []
        for item in food_items:
            ingredients.append({
                "id": item.id,
                "name": item.name,
                "cuisine_type": item.cuisine_type,
                "calories": item.calories,
                "protein_g": item.protein_g,
                "carbs_g": item.carbs_g,
                "fat_g": item.fat_g,
                "fiber_g": item.fiber_g,
                "sodium_mg": item.sodium_mg,
                "tags": item.tags or "",
                "ingredients": item.ingredients or "",
                "cost": item.cost,
                "prep_complexity": item.prep_complexity.value if item.prep_complexity else "medium",
                "diabetic_friendly": item.diabetic_friendly,
                "hypertension_friendly": item.hypertension_friendly
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Found {len(ingredients)} ingredients",
                "data": {
                    "ingredients": ingredients,
                    "count": len(ingredients)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error in search_ingredients endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/check")
async def health_check():
    """
    Health check endpoint for the recipe service.
    """
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Recipe service is healthy",
            "data": {
                "status": "healthy",
                "service": "ai-recipe-generator",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "endpoints_available": 16
            }
        }
    )