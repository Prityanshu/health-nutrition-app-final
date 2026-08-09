"""
Profile: who you are, what you have done, and what it earned.

The sidebar has said "View profile" since the first build and never gone
anywhere. This is the screen behind it - identity and body stats, the points
ledger with a plain explanation of where every point came from, records worth
being proud of, and the one daily question the app has never asked: did you
actually train today?
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import MealLog, User, WeightLog, WorkoutLog, get_db
from app.services import adherence, daytime, points_engine

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# requests
# ---------------------------------------------------------------------------

class WorkoutCheckIn(BaseModel):
    # done | rest | skipped
    status: str = "done"
    workout_type: Optional[str] = None
    minutes: Optional[int] = Field(None, ge=1, le=600)
    intensity: Optional[int] = Field(None, ge=1, le=10)
    note: Optional[str] = None
    # Lets somebody catch up yesterday. Bounded below so the ledger cannot be
    # filled in for arbitrary history.
    for_date: Optional[date] = None


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    age: Optional[int] = Field(None, ge=10, le=120)
    height: Optional[float] = Field(None, ge=80, le=260)
    weight: Optional[float] = Field(None, ge=25, le=400)
    sex: Optional[str] = None
    activity_level: Optional[str] = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _bmi(user: User, weight: Optional[float]) -> Optional[Dict[str, Any]]:
    """
    BMI, with the caveat attached rather than left implicit.

    Included because people expect it, flagged because it is a population
    statistic that says nothing about an individual's body composition - a
    muscular person reads as overweight on it.
    """
    if not weight or not user.height:
        return None
    metres = user.height / 100
    if metres <= 0:
        return None
    value = weight / (metres ** 2)
    band = ("underweight" if value < 18.5
            else "healthy range" if value < 25
            else "overweight" if value < 30
            else "obese")
    return {
        "value": round(value, 1),
        "band": band,
        "note": "A population average - it does not account for muscle mass.",
    }


def _records(db: Session, user: User) -> List[Dict[str, Any]]:
    """Things worth being proud of, computed rather than stored."""
    out: List[Dict[str, Any]] = []
    tz = daytime.zone_for(user)

    history = adherence.history(db, user, days=365)
    summary = adherence.summarise(history)

    if summary["best_streak"]:
        out.append({"label": "Longest streak", "value": f"{summary['best_streak']} days",
                    "sub": "consecutive days on target"})

    logged_days = len({d.day for d in history if not d.unlogged})
    if logged_days:
        out.append({"label": "Days logged", "value": str(logged_days),
                    "sub": "in the last year"})

    workouts = (
        db.query(func.count(WorkoutLog.id))
        .filter(WorkoutLog.user_id == user.id, WorkoutLog.status == "done")
        .scalar() or 0
    )
    if workouts:
        out.append({"label": "Workouts", "value": str(workouts), "sub": "completed"})

    best_day = (
        db.query(func.sum(MealLog.protein).label("protein"))
        .filter(MealLog.user_id == user.id)
        .group_by(func.date(MealLog.logged_at))
        .order_by(func.sum(MealLog.protein).desc())
        .first()
    )
    if best_day and best_day.protein:
        out.append({"label": "Best protein day", "value": f"{best_day.protein:.0f}g",
                    "sub": "highest single day"})

    weights = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user.id)
        .order_by(WeightLog.logged_at.asc())
        .all()
    )
    if len(weights) > 1:
        change = weights[-1].weight_kg - weights[0].weight_kg
        out.append({
            "label": "Weight change",
            "value": f"{change:+.1f} kg",
            "sub": f"over {(weights[-1].logged_at - weights[0].logged_at).days} days",
        })

    member_days = (daytime.local_date(tz=tz) - daytime.local_date(user, user.created_at)).days \
        if user.created_at else 0
    out.append({"label": "Member for", "value": f"{max(member_days, 0)} days",
                "sub": "since you signed up"})
    return out


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------

@router.get("")
@router.get("/")
async def get_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Everything the profile screen needs, in one request."""
    try:
        tz = daytime.zone_for(current_user)
        today = daytime.local_date(tz=tz)

        # Award anything outstanding before reading the total, so opening the
        # profile never shows a number that is a day behind what you did.
        try:
            points_engine.sync(db, current_user, days=3)
        except Exception as e:
            logger.warning("points sync failed for %s: %s", current_user.id, e)
            db.rollback()

        total = points_engine.total_points(db, current_user.id)
        week = adherence.summarise(adherence.history(db, current_user, days=7))

        latest_weight = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == current_user.id)
            .order_by(WeightLog.logged_at.desc())
            .first()
        )
        weight = latest_weight.weight_kg if latest_weight else current_user.weight

        todays_workout = (
            db.query(WorkoutLog)
            .filter(WorkoutLog.user_id == current_user.id,
                    WorkoutLog.local_date == today)
            .first()
        )

        recent_workouts = (
            db.query(WorkoutLog)
            .filter(WorkoutLog.user_id == current_user.id,
                    WorkoutLog.local_date >= today - timedelta(days=6))
            .order_by(WorkoutLog.local_date.asc())
            .all()
        )

        return {
            "success": True,
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "full_name": current_user.full_name,
                "email": current_user.email,
                "age": current_user.age,
                "height": current_user.height,
                "weight": weight,
                "sex": current_user.sex,
                "activity_level": current_user.activity_level,
                "timezone": current_user.timezone or daytime.DEFAULT_TIMEZONE,
                "member_since": current_user.created_at.isoformat() if current_user.created_at else None,
            },
            "bmi": _bmi(current_user, weight),
            "points": {
                "total": total,
                **points_engine.level_for(total),
                "breakdown": points_engine.breakdown(db, current_user.id),
                "last_30_days": points_engine.daily_series(db, current_user, days=30),
                "this_week": sum(
                    d["points"] for d in points_engine.daily_series(db, current_user, days=7)
                ),
            },
            "week": week,
            "records": _records(db, current_user),
            "workout": {
                "today": {
                    "status": todays_workout.status if todays_workout else None,
                    "workout_type": todays_workout.workout_type if todays_workout else None,
                    "minutes": todays_workout.minutes if todays_workout else None,
                    "intensity": todays_workout.intensity if todays_workout else None,
                } if todays_workout else None,
                "asked_today": todays_workout is not None,
                "recent": [
                    {"date": w.local_date.isoformat(), "status": w.status,
                     "type": w.workout_type, "minutes": w.minutes}
                    for w in recent_workouts
                ],
                "done_this_week": sum(1 for w in recent_workouts if w.status == "done"),
            },
        }
    except Exception as e:
        logger.error("get_profile failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load your profile.")


@router.post("/workout")
async def log_workout(
    body: WorkoutCheckIn,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Record whether they trained. One row per local day, updated in place.

    Answering twice edits the existing row rather than adding a second, so the
    points ledger has exactly one workout event per day to reconcile.
    """
    if body.status not in ("done", "rest", "skipped"):
        raise HTTPException(status_code=400,
                            detail="status must be done, rest or skipped")

    tz = daytime.zone_for(current_user)
    today = daytime.local_date(tz=tz)
    day = body.for_date or today

    # Catching up yesterday is reasonable; filling in last month is not - the
    # points would be unearned and the training history fiction.
    if day > today:
        raise HTTPException(status_code=400, detail="That day has not happened yet.")
    if (today - day).days > 7:
        raise HTTPException(status_code=400,
                            detail="You can only log workouts for the last 7 days.")

    try:
        row = (
            db.query(WorkoutLog)
            .filter(WorkoutLog.user_id == current_user.id, WorkoutLog.local_date == day)
            .first()
        )
        if row is None:
            row = WorkoutLog(user_id=current_user.id, local_date=day)
            db.add(row)

        row.status = body.status
        row.workout_type = body.workout_type
        row.minutes = body.minutes
        row.intensity = body.intensity
        row.note = body.note
        row.logged_at = daytime.utcnow()
        db.commit()

        before = points_engine.total_points(db, current_user.id)
        points_engine.sync(db, current_user, days=max(1, (today - day).days + 1))
        after = points_engine.total_points(db, current_user.id)

        return {
            "success": True,
            "date": day.isoformat(),
            "status": row.status,
            "points_earned": after - before,
            "total_points": after,
            "level": points_engine.level_for(after),
            "message": _workout_message(row.status, after - before),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("log_workout failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save that.")


def _workout_message(status: str, earned: int) -> str:
    if status == "done":
        return f"Logged. +{earned} points." if earned else "Logged."
    if status == "rest":
        return (f"Rest day noted. +{earned} points - recovery counts."
                if earned else "Rest day noted.")
    return "Noted. Tomorrow is a fresh start."


@router.put("")
@router.put("/")
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Edit body stats.

    A weight change also writes a WeightLog rather than only overwriting the
    column, because every calorie target depends on bodyweight and the trend
    is worth keeping - silently replacing the number loses the history that
    the progress chart is built from.
    """
    try:
        changed = []
        for field in ("full_name", "age", "height", "sex", "activity_level"):
            value = getattr(body, field)
            if value is not None and getattr(current_user, field) != value:
                setattr(current_user, field, value)
                changed.append(field)

        if body.weight is not None and body.weight != current_user.weight:
            current_user.weight = body.weight
            db.add(WeightLog(user_id=current_user.id, weight_kg=body.weight,
                             logged_at=daytime.utcnow(), note="updated from profile"))
            changed.append("weight")

        db.commit()

        if "weight" in changed:
            try:
                points_engine.sync(db, current_user, days=1)
            except Exception:
                db.rollback()

        return {"success": True, "changed": changed,
                "message": "Saved." if changed else "Nothing to change."}
    except Exception as e:
        db.rollback()
        logger.error("update_profile failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save your profile.")


@router.get("/points")
async def get_points(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """The ledger, itemised. Every point should be explainable."""
    from app.database import PointsLedger

    rows = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == current_user.id,
                PointsLedger.local_date >= daytime.local_date(current_user) - timedelta(days=days))
        .order_by(PointsLedger.local_date.desc(), PointsLedger.points.desc())
        .all()
    )
    total = points_engine.total_points(db, current_user.id)
    return {
        "success": True,
        "total": total,
        "level": points_engine.level_for(total),
        "tariff": points_engine.POINTS,
        "entries": [
            {"date": r.local_date.isoformat(), "reason": r.reason,
             "label": points_engine.REASONS.get(r.reason, r.reason),
             "points": r.points, "detail": r.detail}
            for r in rows
        ],
    }


@router.get("/leaderboard")
async def get_leaderboard(
    days: Optional[int] = Query(30, ge=1, le=365,
                                description="Rolling window; omit for all time"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Ranked totals over a rolling window.

    Rolling rather than all-time because an all-time board is unwinnable for
    anyone who joins late, which is the fastest way to make a leaderboard
    demotivating for exactly the people it should be encouraging.
    """
    try:
        board = points_engine.leaderboard(db, days=days, limit=limit)
        for entry in board:
            entry["is_you"] = entry["user_id"] == current_user.id
        return {
            "success": True,
            "window_days": days,
            "entries": board,
            "your_rank": points_engine.rank_of(db, current_user.id, days=days),
        }
    except Exception as e:
        logger.error("leaderboard failed: %s", e, exc_info=True)
        return {"success": False, "entries": [], "your_rank": None}
