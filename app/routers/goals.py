from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, User, Goal, WeightLog
from app.auth import get_current_active_user
from pydantic import BaseModel, Field
from datetime import datetime, date, timedelta
from typing import List, Optional

from app.services.nutrition_targets import (
    calculate_targets,
    list_presets,
    suggest_preset,
)

router = APIRouter()


# --------------------------------------------------------------------------
# Automatic target calculation
#
# Users should not be asked to supply their own protein or carbohydrate
# targets - working those out from a stated goal is the app's job. These
# endpoints take a goal choice and derive everything from the user's profile
# and most recent weigh-in.
# --------------------------------------------------------------------------


# Response/request models are defined before the endpoints because FastAPI
# evaluates `response_model=` when the decorator runs at import time.

class GoalCreate(BaseModel):
    goal_type: str
    target_weight: Optional[float] = None
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fat: Optional[float] = None
    target_date: Optional[date] = None

class GoalResponse(BaseModel):
    id: int
    goal_type: str
    target_weight: Optional[float]
    target_calories: Optional[float]
    target_protein: Optional[float]
    target_carbs: Optional[float]
    target_fat: Optional[float]
    start_date: datetime
    target_date: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TargetPreviewRequest(BaseModel):
    goal_key: str = Field(..., description="Preset key, e.g. weight_loss")
    target_weight: Optional[float] = None
    target_date: Optional[date] = None
    # Optional overrides for users whose profile is incomplete.
    sex: Optional[str] = None
    activity_level: Optional[str] = None
    current_weight: Optional[float] = None


class GoalFromPresetRequest(TargetPreviewRequest):
    """Same inputs as a preview, but persists the result."""
    save_profile_updates: bool = True


class WeightLogCreate(BaseModel):
    weight_kg: float = Field(..., gt=20, lt=400)
    note: Optional[str] = None


class WeightLogResponse(BaseModel):
    id: int
    weight_kg: float
    logged_at: datetime
    note: Optional[str] = None

    class Config:
        from_attributes = True


def _current_weight(user: User, db: Session) -> float:
    """
    Most recent weigh-in, falling back to the registration weight.

    Targets are only as good as the weight they are based on, so the latest
    measurement always wins over the profile field.
    """
    latest = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user.id)
        .order_by(WeightLog.logged_at.desc())
        .first()
    )
    if latest:
        return latest.weight_kg
    return user.weight or 70.0


def _compute(user: User, db: Session, req: TargetPreviewRequest):
    weight = req.current_weight or _current_weight(user, db)
    weeks = None
    if req.target_date:
        days = (req.target_date - date.today()).days
        weeks = max(1, days // 7) if days > 0 else None

    return calculate_targets(
        weight_kg=weight,
        height_cm=user.height or 170,
        age=user.age or 25,
        sex=req.sex or user.sex or "other",
        activity_level=req.activity_level or user.activity_level or "moderately_active",
        goal_key=req.goal_key,
        target_weight_kg=req.target_weight,
        weeks_available=weeks,
    )


@router.get("/presets")
async def get_goal_presets():
    """Selectable goals for the goal-setting screen."""
    return {"presets": list_presets()}


@router.get("/suggest")
async def suggest_goal_from_text(q: str):
    """
    Map a free-text description onto a preset.

    Lets the UI accept "I want to slim down" or "training for a marathon"
    without a model call.
    """
    preset = suggest_preset(q)
    if not preset:
        return {"matched": False, "suggestion": None}
    return {
        "matched": True,
        "suggestion": {
            "key": preset.key,
            "label": preset.label,
            "description": preset.description,
            "needs_target_weight": preset.needs_target_weight,
        },
    }


@router.post("/preview-targets")
async def preview_targets(
    request: TargetPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Calculate targets without saving, so the user can see the numbers and any
    safety warnings before committing to a goal.
    """
    targets = _compute(current_user, db, request)
    result = targets.as_dict()
    result["profile_used"] = {
        "weight_kg": request.current_weight or _current_weight(current_user, db),
        "height_cm": current_user.height,
        "age": current_user.age,
        "sex": request.sex or current_user.sex or "other",
        "activity_level": request.activity_level or current_user.activity_level,
        "sex_missing": not (request.sex or current_user.sex),
    }
    return result


@router.post("/from-preset", response_model=GoalResponse)
async def create_goal_from_preset(
    request: GoalFromPresetRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a goal with calorie and macro targets derived automatically."""
    targets = _compute(current_user, db, request)

    # Opportunistically fill in profile gaps the user just told us about.
    if request.save_profile_updates:
        if request.sex and not current_user.sex:
            current_user.sex = request.sex
        if request.activity_level:
            current_user.activity_level = request.activity_level
        if request.current_weight:
            current_user.weight = request.current_weight
            db.add(WeightLog(
                user_id=current_user.id,
                weight_kg=request.current_weight,
                note="Recorded while setting a goal",
            ))

    # One active goal at a time - a user cannot simultaneously cut and bulk.
    for existing in db.query(Goal).filter(
        Goal.user_id == current_user.id, Goal.is_active == True  # noqa: E712
    ).all():
        existing.is_active = False

    db_goal = Goal(
        user_id=current_user.id,
        goal_type=targets.goal_key,
        target_weight=request.target_weight,
        target_calories=round(targets.target_calories),
        target_protein=round(targets.protein_g),
        target_carbs=round(targets.carbs_g),
        target_fat=round(targets.fat_g),
        target_date=(
            datetime.combine(request.target_date, datetime.min.time())
            if request.target_date
            else (
                datetime.utcnow() + timedelta(weeks=targets.estimated_weeks)
                if targets.estimated_weeks else None
            )
        ),
    )
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal


@router.post("/weight", response_model=WeightLogResponse)
async def log_weight(
    entry: WeightLogCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Record a weigh-in and refresh any active goal's targets against it.

    Recalculating here is the point of the weekly check-in: as bodyweight
    changes so does maintenance, and a target set two months ago at a different
    weight quietly stops being correct.
    """
    log = WeightLog(user_id=current_user.id, weight_kg=entry.weight_kg, note=entry.note)
    db.add(log)
    current_user.weight = entry.weight_kg

    active = (
        db.query(Goal)
        .filter(Goal.user_id == current_user.id, Goal.is_active == True)  # noqa: E712
        .order_by(Goal.created_at.desc())
        .first()
    )
    recalculated = None
    if active:
        targets = calculate_targets(
            weight_kg=entry.weight_kg,
            height_cm=current_user.height or 170,
            age=current_user.age or 25,
            sex=current_user.sex or "other",
            activity_level=current_user.activity_level or "moderately_active",
            goal_key=active.goal_type,
            target_weight_kg=active.target_weight,
        )
        active.target_calories = round(targets.target_calories)
        active.target_protein = round(targets.protein_g)
        active.target_carbs = round(targets.carbs_g)
        active.target_fat = round(targets.fat_g)
        recalculated = targets.as_dict()

    db.commit()
    db.refresh(log)

    response = WeightLogResponse.model_validate(log).model_dump()
    response["goal_recalculated"] = recalculated is not None
    response["updated_targets"] = recalculated
    return response


@router.get("/weight/history")
async def weight_history(
    days: int = 180,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Weigh-in history for charting progress."""
    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == current_user.id, WeightLog.logged_at >= since)
        .order_by(WeightLog.logged_at.asc())
        .all()
    )
    entries = [
        {"weight_kg": l.weight_kg, "logged_at": l.logged_at.isoformat(), "note": l.note}
        for l in logs
    ]
    change = (entries[-1]["weight_kg"] - entries[0]["weight_kg"]) if len(entries) > 1 else 0.0
    return {
        "entries": entries,
        "count": len(entries),
        "change_kg": round(change, 1),
        "latest": entries[-1]["weight_kg"] if entries else None,
        "days_since_last": (
            (datetime.utcnow() - logs[-1].logged_at).days if logs else None
        ),
    }


@router.post("/", response_model=GoalResponse)
async def create_goal(
    goal: GoalCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new goal"""
    # Deactivate any existing active goals of the same type
    existing_goals = db.query(Goal).filter(
        Goal.user_id == current_user.id,
        Goal.goal_type == goal.goal_type,
        Goal.is_active == True
    ).all()
    
    for existing_goal in existing_goals:
        existing_goal.is_active = False
    
    # Create new goal
    db_goal = Goal(
        user_id=current_user.id,
        goal_type=goal.goal_type,
        target_weight=goal.target_weight,
        target_calories=goal.target_calories,
        target_protein=goal.target_protein,
        target_carbs=goal.target_carbs,
        target_fat=goal.target_fat,
        target_date=goal.target_date
    )
    
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    
    return db_goal

@router.get("/", response_model=List[GoalResponse])
async def get_goals(
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's goals"""
    query = db.query(Goal).filter(Goal.user_id == current_user.id)
    
    if active_only:
        query = query.filter(Goal.is_active == True)
    
    goals = query.order_by(Goal.created_at.desc()).all()
    return goals

@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific goal"""
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    return goal

@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: int,
    goal_update: GoalCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a goal"""
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Update goal fields
    update_data = goal_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(goal, field, value)
    
    db.commit()
    db.refresh(goal)
    
    return goal

@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a goal"""
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    db.delete(goal)
    db.commit()
    
    return {"message": "Goal deleted successfully"}
