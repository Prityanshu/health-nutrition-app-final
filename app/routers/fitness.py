from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

# Import the service
from ..services.fitmentor_service import fitmentor_service

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fitness", tags=["fitness"])

class WorkoutPlanRequest(BaseModel):
    """Request model for workout plan generation"""
    activity_level: str = Field(
        ...,
        description="Activity level: beginner, intermediate, or advanced"
    )
    fitness_goal: str = Field(
        ...,
        description="Primary fitness goal: weight_loss, muscle_gain, endurance, flexibility, or general_fitness"
    )
    time_per_day: int = Field(
        ...,
        ge=15,
        le=180,
        description="Time available per day in minutes"
    )
    equipment: str = Field(
        ...,
        description="Equipment availability: none, home, or gym"
    )
    constraints: List[str] = Field(
        default=[],
        description="Any constraints or limitations (injuries, medical conditions, etc.)"
    )
    age: Optional[int] = Field(
        default=None,
        ge=13,
        le=100,
        description="Age in years (optional)"
    )
    weight: Optional[float] = Field(
        default=None,
        ge=30.0,
        le=300.0,
        description="Weight in kg (optional)"
    )
    sport: Optional[str] = Field(
        default=None,
        max_length=60,
        description=(
            "Sport or activity trained FOR - football, cricket, running. Not the "
            "same as a fitness goal: sport preparation has different demands and "
            "has to leave enough in the legs to actually play."
        ),
    )
    preferences: Optional[str] = Field(
        default=None,
        max_length=400,
        description="Anything the other fields cannot express - disliked exercises, schedule quirks.",
    )

class WorkoutAdaptationRequest(BaseModel):
    """Request model for workout plan adaptation"""
    current_plan: str = Field(
        ...,
        description="Current workout plan to adapt"
    )
    feedback: str = Field(
        ...,
        description="User feedback on the current plan"
    )
    progress_notes: Optional[str] = Field(
        default=None,
        description="Additional progress notes (optional)"
    )

@router.post("/generate-workout-plan", status_code=201)
async def generate_workout_plan(request: WorkoutPlanRequest):
    """
    Generate a personalized weekly workout plan using FitMentor agent.
    
    This endpoint creates a detailed 7-day workout plan based on:
    - Activity level and fitness goals
    - Available time and equipment
    - Personal constraints and preferences
    - Age and weight (optional)
    """
    try:
        result = await fitmentor_service.generate_workout_plan(
            activity_level=request.activity_level,
            fitness_goal=request.fitness_goal,
            time_per_day=request.time_per_day,
            equipment=request.equipment,
            constraints=request.constraints,
            age=request.age,
            weight=request.weight,
            sport=request.sport,
            preferences=request.preferences,
        )

        if result["success"]:
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "Workout plan generated successfully using FitMentor",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Workout plan generation failed",
                    "error": result["error"]
                }
            )

    except Exception as e:
        logger.error(f"Error in generate_workout_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/adapt-workout-plan", status_code=200)
async def adapt_workout_plan(request: WorkoutAdaptationRequest):
    """
    Adapt an existing workout plan based on user feedback.
    
    This endpoint modifies a workout plan based on:
    - User feedback and experience
    - Progress notes and observations
    - Specific requests for changes
    """
    try:
        # Translate any injury mentioned in the feedback into concrete exercise
        # exclusions before it reaches the generator. FitMentor does not reason
        # about anatomy, so passing "my knee hurts" through unchanged produced
        # adapted plans that still contained deep squats. Non-injury feedback is
        # returned unmodified.
        from app.services.contraindications import expand_feedback, summarise

        expanded = expand_feedback(request.feedback)
        detected = summarise(request.feedback)
        if detected:
            logger.info(
                "Injury detected in feedback: %s",
                [i["label"] for i in detected["injuries"]],
            )

        result = await fitmentor_service.adapt_workout_plan(
            current_plan=request.current_plan,
            feedback=expanded,
            progress_notes=request.progress_notes
        )

        if result["success"]:
            # Surface what was detected so the UI can show which exercises were
            # removed, rather than the user having to trust it silently.
            if detected:
                result["contraindications"] = detected
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Workout plan adapted successfully using FitMentor",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Workout plan adaptation failed",
                    "error": result["error"]
                }
            )

    except Exception as e:
        logger.error(f"Error in adapt_workout_plan endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/activity-levels")
async def get_activity_levels():
    """Get available activity levels"""
    return {
        "activity_levels": [
            {"value": "beginner", "label": "Beginner", "description": "New to fitness or returning after a long break"},
            {"value": "intermediate", "label": "Intermediate", "description": "Some fitness experience, regular but not intense workouts"},
            {"value": "advanced", "label": "Advanced", "description": "Experienced with fitness, high intensity workouts"}
        ]
    }

@router.get("/fitness-goals")
async def get_fitness_goals():
    """Get available fitness goals"""
    return {
        "fitness_goals": [
            {"value": "weight_loss", "label": "Weight Loss", "description": "Focus on burning calories and reducing body fat"},
            {"value": "muscle_gain", "label": "Muscle Gain", "description": "Build muscle mass and strength"},
            {"value": "endurance", "label": "Endurance", "description": "Improve cardiovascular fitness and stamina"},
            {"value": "flexibility", "label": "Flexibility", "description": "Increase range of motion and mobility"},
            {"value": "general_fitness", "label": "General Fitness", "description": "Overall health and fitness improvement"}
        ]
    }

@router.get("/equipment-options")
async def get_equipment_options():
    """Get available equipment options"""
    return {
        "equipment_options": [
            {"value": "none", "label": "No Equipment", "description": "Bodyweight exercises only"},
            {"value": "home", "label": "Home Equipment", "description": "Basic equipment like dumbbells, resistance bands"},
            {"value": "gym", "label": "Full Gym Access", "description": "Complete gym with all equipment available"}
        ]
    }
