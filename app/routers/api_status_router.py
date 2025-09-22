"""
API Status and Monitoring Router
Provides endpoints to monitor API key status and system health
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.database import get_db
from app.auth import get_current_active_user
from app.config.groq_config import groq_config

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/api-keys/status")
async def get_api_keys_status(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the current status of all API keys"""
    try:
        status = groq_config.get_status()
        return {
            "success": True,
            "api_keys_status": status,
            "message": "API keys status retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting API keys status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get API keys status: {str(e)}")

@router.post("/api-keys/reset")
async def reset_api_keys(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Reset all API keys (useful for testing or manual reset)"""
    try:
        groq_config.reset_all_keys()
        return {
            "success": True,
            "message": "All API keys have been reset successfully"
        }
    except Exception as e:
        logger.error(f"Error resetting API keys: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset API keys: {str(e)}")

@router.get("/system/health")
async def get_system_health(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get overall system health including API key status"""
    try:
        api_status = groq_config.get_status()
        
        # Check if we have any active API keys
        has_active_keys = api_status["active_keys"] > 0
        
        # Determine overall health
        if has_active_keys:
            health_status = "healthy"
            message = "System is running normally with active API keys"
        else:
            health_status = "degraded"
            message = "No active API keys available - service may be limited"
        
        return {
            "success": True,
            "health_status": health_status,
            "message": message,
            "api_keys": api_status,
            "timestamp": "2025-01-22T00:00:00Z"  # You can add actual timestamp
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")
