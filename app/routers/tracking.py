from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db, User, MealLog
from app.auth import get_current_active_user
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

router = APIRouter()

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
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = start_datetime + timedelta(days=1)
    
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
    today = date.today()
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
    # Get last 30 days of data
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    recent_logs = db.query(MealLog).filter(
        MealLog.user_id == current_user.id,
        MealLog.logged_at >= thirty_days_ago
    ).all()
    
    total_calories = sum(log.calories for log in recent_logs)
    total_protein = sum(log.protein for log in recent_logs)
    total_carbs = sum(log.carbs for log in recent_logs)
    total_fat = sum(log.fat for log in recent_logs)
    
    # Calculate averages
    days_with_logs = len(set(log.logged_at.date() for log in recent_logs))
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
