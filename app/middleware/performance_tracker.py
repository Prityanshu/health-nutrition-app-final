# app/middleware/performance_tracker.py
"""
Middleware to track API performance metrics
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict

logger = logging.getLogger(__name__)

class PerformanceTrackerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API response times and performance metrics
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.endpoint_times = defaultdict(list)
        self.request_counts = defaultdict(int)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip tracking for metrics endpoints to avoid recursion
        if request.url.path.startswith("/api/metrics"):
            return await call_next(request)
        
        # Record start time
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Track metrics
        endpoint = f"{request.method} {request.url.path}"
        self.endpoint_times[endpoint].append(response_time)
        self.request_counts[endpoint] += 1
        
        # Keep only last 1000 requests per endpoint to avoid memory issues
        if len(self.endpoint_times[endpoint]) > 1000:
            self.endpoint_times[endpoint] = self.endpoint_times[endpoint][-1000:]
        
        # Add response time header
        response.headers["X-Response-Time"] = f"{response_time:.4f}"
        
        return response
    
    def get_metrics(self) -> dict:
        """Get collected performance metrics"""
        return {
            "endpoint_times": dict(self.endpoint_times),
            "request_counts": dict(self.request_counts)
        }
    
    def reset_metrics(self):
        """Reset collected metrics"""
        self.endpoint_times.clear()
        self.request_counts.clear()

# Note: Middleware instance is created by FastAPI when added to app

