"""
Challenges and injury tracking.

Replaces the enhanced_challenges endpoints for everything the UI actually uses.
The important difference is that progress is recomputed from source data on
every read, so a challenge reflects what the user has done rather than what one
particular code path remembered to increment.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import User, get_db
from app.models.enhanced_challenge_models import PersonalizedChallenge
from app.services import challenge_engine, injury_service

logger = logging.getLogger(__name__)
router = APIRouter()


class InjuryRequest(BaseModel):
    description: str = Field(..., min_length=2, max_length=200)
    severity: int = Field(default=5, ge=0, le=10)


class CheckInRequest(BaseModel):
    severity: int = Field(..., ge=0, le=10)
    trend: Optional[str] = Field(default=None, description="better | same | worse")
    note: Optional[str] = Field(default=None, max_length=500)


def _serialise(challenge: PersonalizedChallenge) -> Dict[str, Any]:
    factors = challenge.personalization_factors or {}
    target = challenge.target_value or 0
    current = challenge.current_value or 0
    days_left = (
        max(0, (challenge.end_date - datetime.utcnow()).days)
        if challenge.end_date else 0
    )
    return {
        "id": challenge.id,
        "title": challenge.title,
        "description": challenge.description,
        # Why this challenge, in the user's own numbers. The old UI showed
        # challenges with no explanation, which is what made them feel random.
        "reason": factors.get("reason") if isinstance(factors, dict) else None,
        "type": challenge.challenge_type.value if challenge.challenge_type else "nutrition",
        "difficulty": challenge.difficulty.value if challenge.difficulty else "easy",
        "target": target,
        "current": current,
        "unit": challenge.unit,
        "percent": min(100, round((current / target) * 100)) if target else 0,
        "days_left": days_left,
        "points": challenge.points_reward,
        "badge": challenge.badge_reward,
        "completed": target > 0 and current >= target,
        "baseline": challenge.baseline_data,
    }


@router.get("/challenges")
async def list_challenges(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Active challenges with live progress, generating some if there are none.

    Generation happens here rather than behind a button because an empty
    challenges screen is useless, and the user should not have to know that
    challenges need creating before they can be done.
    """
    try:
        active = challenge_engine.refresh_progress(db, current_user.id)

        if len(active) < 2:
            challenge_engine.generate_for_user(db, current_user.id, limit=3 - len(active))
            active = challenge_engine.refresh_progress(db, current_user.id)

        items = [_serialise(c) for c in active]
        items.sort(key=lambda i: (i["completed"], -i["percent"]))

        situation = challenge_engine.read_situation(db, current_user.id)
        return {
            "success": True,
            "challenges": items,
            "completed_count": sum(1 for i in items if i["completed"]),
            "points_available": sum(i["points"] for i in items if not i["completed"]),
            "context": {
                "goal": situation.goal_type,
                "calorie_target": situation.calorie_target,
                "protein_target": situation.protein_target,
                "avg_protein": round(situation.avg_protein),
                "avg_calories": round(situation.avg_calories),
                "days_logged": situation.days_logged,
                "logging_rate": round(situation.logging_rate, 2),
                "injured": situation.injured,
                "is_new": situation.is_new,
                # Rotation state, so the UI can show progression rather than
                # a list that looks identical every week.
                "total_points": situation.total_points,
                "streak": situation.streak,
                "levels": situation.levels,
            },
        }
    except Exception as e:
        logger.error("list_challenges failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load challenges")


@router.post("/challenges/refresh")
async def new_challenges(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Ask for a new challenge when the current set does not appeal."""
    try:
        created = challenge_engine.generate_for_user(db, current_user.id, limit=1)
        if not created:
            return {
                "success": False,
                "message": "You already have as many challenges as you can take on. Finish one first.",
            }
        return {"success": True, "challenge": _serialise(created[0])}
    except Exception as e:
        logger.error("new_challenges failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create a challenge")


@router.delete("/challenges/{challenge_id}")
async def drop_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Abandon a challenge that does not fit."""
    challenge = (
        db.query(PersonalizedChallenge)
        .filter(
            PersonalizedChallenge.id == challenge_id,
            PersonalizedChallenge.user_id == current_user.id,
        ).first()
    )
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    challenge.is_active = False
    db.commit()
    return {"success": True}


# --------------------------------------------------------------------------
# injuries
# --------------------------------------------------------------------------

@router.get("/injuries")
async def get_injuries(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Active injuries, their trend, and whether a check-in is due."""
    try:
        return {"success": True, **injury_service.summary(db, current_user.id)}
    except Exception as e:
        logger.error("get_injuries failed: %s", e, exc_info=True)
        return {"success": True, "injuries": [], "has_active": False,
                "checkin_due": False, "needs_attention": False}


@router.post("/injuries")
async def add_injury(
    request: InjuryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Start tracking an injury.

    Recording it here is what makes it survive - previously an injury lived
    only in the chat transcript and was forgotten once it fell out of the
    conversation window, so next week's plan happily reloaded it.
    """
    try:
        injury = injury_service.record_injury(
            db, current_user.id, request.description, request.severity
        )
        return {
            "success": True,
            "injury": {
                "id": injury.id,
                "label": injury.description or injury.body_part,
                "body_part": injury.body_part,
                "severity": injury.severity,
            },
            "message": (
                "Noted. Your workouts and meal suggestions will work around this, "
                "and I'll ask how it's going in a week."
            ),
        }
    except Exception as e:
        logger.error("add_injury failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not record that injury")


@router.post("/injuries/{injury_id}/checkin")
async def injury_checkin(
    injury_id: int,
    request: CheckInRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Report how an injury is doing.

    This is the loop that makes injury tracking worth anything: severity
    dropping reopens the plan, severity climbing closes it further, and a red
    flag says see someone rather than handing over another modified workout.
    """
    try:
        result = injury_service.check_in(
            db, injury_id, current_user.id,
            severity=request.severity, trend=request.trend, note=request.note,
        )
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Injury not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("injury_checkin failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not record that check-in")


@router.delete("/injuries/{injury_id}")
async def resolve_injury(
    injury_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Mark an injury healed."""
    from app.database import Injury

    injury = (
        db.query(Injury)
        .filter(Injury.id == injury_id, Injury.user_id == current_user.id)
        .first()
    )
    if not injury:
        raise HTTPException(status_code=404, detail="Injury not found")

    injury.status = "recovered"
    injury.resolved_at = datetime.utcnow()
    injury.needs_attention = False
    db.commit()
    return {"success": True, "message": "Marked as recovered - your plans will open back up."}
