from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, users, planner, meals, tracking, goals, recipes, gamification, ml_recommendations, fitness, budget, culinary, nutrient_analyzer, advanced_meal_planner, chatbot, enhanced_ml_router, onboarding_router, enhanced_challenges_router
from app.routers.ai_recipe_router import router as ai_recipe_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Nutrition App API",
    description="A comprehensive nutrition and meal planning application",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(planner.router, prefix="/api/planner", tags=["meal-planning"])
app.include_router(meals.router, prefix="/api/meals", tags=["meals"])
app.include_router(tracking.router, prefix="/api/tracking", tags=["progress-tracking"])
app.include_router(goals.router, prefix="/api/goals", tags=["goals"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])
app.include_router(ai_recipe_router)
app.include_router(fitness.router, prefix="/api", tags=["fitness"])
app.include_router(budget.router, prefix="/api", tags=["budget"])
app.include_router(culinary.router, prefix="/api", tags=["culinary"])
app.include_router(nutrient_analyzer.router, prefix="/api", tags=["nutrient-analyzer"])
app.include_router(advanced_meal_planner.router, prefix="/api", tags=["advanced-meal-planner"])
app.include_router(chatbot.router, prefix="/api/chatbot", tags=["chatbot"])
app.include_router(gamification.router, prefix="/api/gamification", tags=["gamification"])
app.include_router(ml_recommendations.router, prefix="/api/ml", tags=["ml-recommendations"])
app.include_router(enhanced_ml_router.router, prefix="/api/enhanced-ml", tags=["enhanced-ml"])
app.include_router(onboarding_router.router, prefix="/api/onboarding", tags=["onboarding"])
app.include_router(enhanced_challenges_router.router, prefix="/api/enhanced-challenges", tags=["enhanced-challenges"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Nutrition App API", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "nutrition-app"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
