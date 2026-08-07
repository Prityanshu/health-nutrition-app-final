# app/routers/metrics_router.py
"""
API endpoints for performance metrics collection and reporting
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.performance_metrics import PerformanceMetricsCollector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["performance-metrics"])

@router.get("/recommendation")
async def get_recommendation_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    user_id: Optional[int] = Query(None, description="Specific user ID (optional)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get ML recommendation performance metrics"""
    try:
        collector = PerformanceMetricsCollector(db)
        metrics = collector.calculate_recommendation_metrics(user_id=user_id, days=days)
        return metrics
    except Exception as e:
        logger.error(f"Error calculating recommendation metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")

@router.get("/engagement")
async def get_engagement_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get user engagement metrics"""
    try:
        collector = PerformanceMetricsCollector(db)
        metrics = collector.calculate_engagement_metrics(days=days)
        return metrics
    except Exception as e:
        logger.error(f"Error calculating engagement metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")

@router.get("/chatbot")
async def get_chatbot_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get AI chatbot performance metrics"""
    try:
        collector = PerformanceMetricsCollector(db)
        metrics = collector.calculate_chatbot_metrics(days=days)
        return metrics
    except Exception as e:
        logger.error(f"Error calculating chatbot metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")

@router.get("/system")
async def get_system_metrics(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get system-level metrics"""
    try:
        collector = PerformanceMetricsCollector(db)
        metrics = collector.calculate_system_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error calculating system metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")

@router.get("/comprehensive")
async def get_comprehensive_report(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get comprehensive performance report for research documentation"""
    try:
        collector = PerformanceMetricsCollector(db)
        report = collector.generate_comprehensive_report(days=days)
        return report
    except Exception as e:
        logger.error(f"Error generating comprehensive report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@router.get("/export")
async def export_metrics_report(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Export comprehensive metrics report to JSON file"""
    try:
        collector = PerformanceMetricsCollector(db)
        report = collector.generate_comprehensive_report(days=days)
        filepath = collector.export_report_to_json(report)
        
        return {
            "success": True,
            "message": "Report exported successfully",
            "filepath": filepath,
            "report": report
        }
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export report: {str(e)}")




