import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db, User, MealLog, FoodItem
from app.auth import get_current_active_user
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

from app.services import adherence, daytime

router = APIRouter()
logger = logging.getLogger(__name__)

class DailyStats(BaseModel):
    date: date
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    meal_count: int

class WeeklyStats(BaseModel):
    week_start: date
    week_end: date
    daily_stats: List[DailyStats]
    weekly_averages: Dict[str, float]

@router.get("/daily/{target_date}", response_model=DailyStats)
async def get_daily_stats(
    target_date: date,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get daily nutrition statistics"""
    # The window is the user's local day converted to UTC, not UTC midnight to
    # UTC midnight. In IST those differ by 5h30, which is why the dashboard
    # used to keep showing yesterday's totals until half past five in the
    # morning and a meal logged at 00:30 landed on the previous day.
    start_datetime, end_datetime = daytime.day_bounds(target_date, current_user)

    meal_logs = db.query(MealLog).filter(
        MealLog.user_id == current_user.id,
        MealLog.logged_at >= start_datetime,
        MealLog.logged_at < end_datetime
    ).all()
    
    total_calories = sum(log.calories for log in meal_logs)
    total_protein = sum(log.protein for log in meal_logs)
    total_carbs = sum(log.carbs for log in meal_logs)
    total_fat = sum(log.fat for log in meal_logs)
    meal_count = len(meal_logs)
    
    return DailyStats(
        date=target_date,
        total_calories=total_calories,
        total_protein=total_protein,
        total_carbs=total_carbs,
        total_fat=total_fat,
        meal_count=meal_count
    )

@router.get("/weekly", response_model=WeeklyStats)
async def get_weekly_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get weekly nutrition statistics"""
    # date.today() is the SERVER's day. For a user in a different zone that is
    # the wrong week entirely near the boundary.
    today = daytime.local_date(current_user)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    daily_stats = []
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    total_meals = 0
    
    for i in range(7):
        current_date = week_start + timedelta(days=i)
        daily_stat = await get_daily_stats(current_date, current_user, db)
        daily_stats.append(daily_stat)
        
        total_calories += daily_stat.total_calories
        total_protein += daily_stat.total_protein
        total_carbs += daily_stat.total_carbs
        total_fat += daily_stat.total_fat
        total_meals += daily_stat.meal_count
    
    weekly_averages = {
        "calories": total_calories / 7,
        "protein": total_protein / 7,
        "carbs": total_carbs / 7,
        "fat": total_fat / 7,
        "meals": total_meals / 7
    }
    
    return WeeklyStats(
        week_start=week_start,
        week_end=week_end,
        daily_stats=daily_stats,
        weekly_averages=weekly_averages
    )

@router.get("/progress")
async def get_progress_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get overall progress summary"""
    # Two bugs in one line before: datetime.now() is server-local but
    # logged_at is stored UTC, and starting 30*24h ago begins partway through
    # a day, so the oldest day was always a fragment.
    thirty_days_ago = daytime.days_ago_start(30, current_user)

    recent_logs = db.query(MealLog).filter(
        MealLog.user_id == current_user.id,
        MealLog.logged_at >= thirty_days_ago
    ).all()
    
    total_calories = sum(log.calories for log in recent_logs)
    total_protein = sum(log.protein for log in recent_logs)
    total_carbs = sum(log.carbs for log in recent_logs)
    total_fat = sum(log.fat for log in recent_logs)
    
    # Calculate averages
    # .date() on a UTC timestamp is the UTC day. In IST anything logged after
    # 18:30 local counted as the next day, so an evening meal and the next
    # morning's breakfast collapsed into one "day logged".
    days_with_logs = len(daytime.local_dates_between(recent_logs, "logged_at", current_user))
    if days_with_logs > 0:
        avg_daily_calories = total_calories / days_with_logs
        avg_daily_protein = total_protein / days_with_logs
        avg_daily_carbs = total_carbs / days_with_logs
        avg_daily_fat = total_fat / days_with_logs
    else:
        avg_daily_calories = avg_daily_protein = avg_daily_carbs = avg_daily_fat = 0
    
    return {
        "period_days": 30,
        "days_logged": days_with_logs,
        "total_meals": len(recent_logs),
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fat": total_fat,
        "daily_averages": {
            "calories": avg_daily_calories,
            "protein": avg_daily_protein,
            "carbs": avg_daily_carbs,
            "fat": avg_daily_fat
        }
    }


# ---------------------------------------------------------------------------
# today's timeline + how the week has gone
# ---------------------------------------------------------------------------

@router.get("/day")
async def get_day(
    days: int = Query(7, ge=1, le=31, description="How many completed days of history"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    What they ate today, and whether the last `days` days hit target.

    One endpoint rather than two because the dashboard shows them in a single
    card, and two requests meant the timeline and the streak could disagree
    across a midnight rollover - the first landing on one day and the second on
    the next.
    """
    try:
        tz = daytime.zone_for(current_user)
        start, end = daytime.today_bounds(tz=tz)

        rows = (
            db.query(MealLog)
            .filter(
                MealLog.user_id == current_user.id,
                MealLog.logged_at >= start,
                MealLog.logged_at < end,
            )
            .order_by(MealLog.logged_at.asc())     # a timeline, so oldest first
            .all()
        )

        # One query for the names rather than one per row.
        food_ids = {r.food_item_id for r in rows if r.food_item_id}
        foods = {
            f.id: f for f in db.query(FoodItem).filter(FoodItem.id.in_(food_ids)).all()
        } if food_ids else {}

        timeline = []
        for row in rows:
            food = foods.get(row.food_item_id)
            local = daytime.to_local(row.logged_at, tz=tz) if row.logged_at else None
            timeline.append({
                "id": row.id,
                # A log can outlive the food it points at; the history endpoint
                # learned this the hard way and took the whole response down.
                "name": food.name if food else "Unknown food",
                "meal_type": row.meal_type,
                "quantity": row.quantity,
                "calories": round(row.calories or 0, 1),
                "protein": round(row.protein or 0, 1),
                "carbs": round(row.carbs or 0, 1),
                "fat": round(row.fat or 0, 1),
                # Both: the client needs the exact instant for sorting and the
                # preformatted local time so it does not re-derive the timezone
                # and get a different answer.
                "logged_at": row.logged_at.isoformat() if row.logged_at else None,
                "local_time": local.strftime("%H:%M") if local else None,
                "local_hour": local.hour if local else None,
            })

        today_result = adherence.today(db, current_user)
        week = adherence.week_context(db, current_user, days=days)

        return {
            "success": True,
            "date": daytime.local_date(tz=tz).isoformat(),
            "timezone": str(tz),
            "timeline": timeline,
            "today": today_result.as_dict(),
            "history": week["days"],
            "summary": week["summary"],
            # So the client can refresh itself exactly on the rollover.
            "seconds_until_midnight": daytime.seconds_until_local_midnight(tz=tz),
        }
    except Exception as e:
        logger.error("get_day failed: %s", e, exc_info=True)
        # The dashboard must still render. An empty day is a valid answer;
        # a 500 here blanks the whole screen.
        return {
            "success": False,
            "date": daytime.local_date(current_user).isoformat(),
            "timeline": [], "today": None, "history": [], "summary": None,
        }


@router.get("/adherence")
async def get_adherence(
    days: int = Query(7, ge=1, le=90),
    include_today: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Goal adherence on its own, for the progress screen and longer windows."""
    try:
        results = adherence.history(db, current_user, days=days,
                                    include_today=include_today)
        return {
            "success": True,
            "days": [r.as_dict() for r in results],
            "summary": adherence.summarise(results),
        }
    except Exception as e:
        logger.error("get_adherence failed: %s", e, exc_info=True)
        return {"success": False, "days": [], "summary": None}
