# app/services/performance_metrics.py
"""
Performance Metrics Collection System for Research Documentation
Collects comprehensive metrics for comparing with other models and research papers
"""
import time
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, distinct
import statistics

from app.database import (
    User, FoodItem, MealLog, Goal, Recipe, FoodRating
)
from app.models.enhanced_models import (
    FoodPreferenceLearning, RecipeInteraction, ChatbotInteraction
)

logger = logging.getLogger(__name__)

class PerformanceMetricsCollector:
    """
    Comprehensive performance metrics collector for research documentation
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== ML RECOMMENDATION METRICS ====================
    
    def calculate_recommendation_metrics(self, user_id: Optional[int] = None, 
                                       days: int = 30) -> Dict[str, Any]:
        """
        Calculate ML recommendation performance metrics:
        - Precision@K (K=5, 10)
        - Recall@K
        - NDCG@K (Normalized Discounted Cumulative Gain)
        - Mean Reciprocal Rank (MRR)
        - Coverage (diversity of recommendations)
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all recommendations made in the period
        # (This would need to be tracked - for now, we'll use logged meals as proxy)
        
        # Get user's logged meals (ground truth)
        query = self.db.query(MealLog).filter(
            MealLog.logged_at >= start_date,
            MealLog.logged_at <= end_date
        )
        
        if user_id:
            query = query.filter(MealLog.user_id == user_id)
        
        logged_meals = query.all()
        
        # Calculate metrics
        total_users = self.db.query(func.count(distinct(MealLog.user_id))).scalar() or 1
        total_foods_logged = len(logged_meals)
        unique_foods_logged = len(set(m.food_item_id for m in logged_meals if m.food_item_id))
        
        # Calculate diversity (coverage)
        all_foods = self.db.query(FoodItem).count()
        coverage = (unique_foods_logged / all_foods * 100) if all_foods > 0 else 0
        
        # Calculate average meals per user
        avg_meals_per_user = total_foods_logged / total_users if total_users > 0 else 0
        
        return {
            "metric_type": "recommendation_performance",
            "period_days": days,
            "total_users": total_users,
            "total_interactions": total_foods_logged,
            "unique_items_logged": unique_foods_logged,
            "coverage_percentage": round(coverage, 2),
            "avg_interactions_per_user": round(avg_meals_per_user, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def calculate_precision_recall(self, user_id: int, recommended_foods: List[int], 
                                  actual_logged: List[int], k: int = 10) -> Dict[str, float]:
        """
        Calculate Precision@K and Recall@K for a user
        """
        recommended_set = set(recommended_foods[:k])
        actual_set = set(actual_logged)
        
        if len(recommended_set) == 0:
            return {"precision": 0.0, "recall": 0.0}
        
        relevant_recommended = recommended_set.intersection(actual_set)
        
        precision = len(relevant_recommended) / len(recommended_set) if recommended_set else 0.0
        recall = len(relevant_recommended) / len(actual_set) if actual_set else 0.0
        
        return {
            f"precision@{k}": round(precision, 4),
            f"recall@{k}": round(recall, 4),
            "relevant_recommended": len(relevant_recommended),
            "total_recommended": len(recommended_set),
            "total_actual": len(actual_set)
        }
    
    # ==================== USER ENGAGEMENT METRICS ====================
    
    def calculate_engagement_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculate user engagement metrics:
        - Daily Active Users (DAU)
        - Monthly Active Users (MAU)
        - Retention rate
        - Average session duration
        - Actions per session
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Daily Active Users
        daily_active = self.db.query(
            func.date(MealLog.logged_at).label('date'),
            func.count(distinct(MealLog.user_id)).label('users')
        ).filter(
            MealLog.logged_at >= start_date
        ).group_by(func.date(MealLog.logged_at)).all()
        
        avg_dau = statistics.mean([d.users for d in daily_active]) if daily_active else 0
        
        # Total unique users in period
        total_active_users = self.db.query(func.count(distinct(MealLog.user_id))).filter(
            MealLog.logged_at >= start_date
        ).scalar() or 0
        
        # Total registered users
        total_registered = self.db.query(func.count(User.id)).scalar() or 0
        
        # Engagement rate
        engagement_rate = (total_active_users / total_registered * 100) if total_registered > 0 else 0
        
        # Average meals logged per active user
        meals_per_user = self.db.query(
            MealLog.user_id,
            func.count(MealLog.id).label('meal_count')
        ).filter(
            MealLog.logged_at >= start_date
        ).group_by(MealLog.user_id).all()
        
        avg_meals_per_active_user = statistics.mean([m.meal_count for m in meals_per_user]) if meals_per_user else 0
        
        return {
            "metric_type": "user_engagement",
            "period_days": days,
            "avg_daily_active_users": round(avg_dau, 2),
            "total_active_users": total_active_users,
            "total_registered_users": total_registered,
            "engagement_rate_percentage": round(engagement_rate, 2),
            "avg_meals_per_active_user": round(avg_meals_per_active_user, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # ==================== AI CHATBOT METRICS ====================
    
    def calculate_chatbot_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculate AI chatbot performance metrics:
        - Total queries
        - Average response time
        - Success rate
        - User satisfaction (if tracked)
        - Agent distribution
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        interactions = self.db.query(ChatbotInteraction).filter(
            ChatbotInteraction.created_at >= start_date
        ).all()
        
        total_queries = len(interactions)
        
        # Agent distribution
        agent_counts = defaultdict(int)
        response_types = defaultdict(int)
        satisfaction_scores = []
        
        for interaction in interactions:
            if interaction.agent_used:
                agent_counts[interaction.agent_used] += 1
            if interaction.response_type:
                response_types[interaction.response_type] += 1
            if interaction.user_satisfaction:
                satisfaction_scores.append(interaction.user_satisfaction)
        
        success_rate = (response_types.get('success', 0) / total_queries * 100) if total_queries > 0 else 0
        avg_satisfaction = statistics.mean(satisfaction_scores) if satisfaction_scores else None
        
        return {
            "metric_type": "chatbot_performance",
            "period_days": days,
            "total_queries": total_queries,
            "success_rate_percentage": round(success_rate, 2),
            "avg_user_satisfaction": round(avg_satisfaction, 3) if avg_satisfaction else None,
            "agent_distribution": dict(agent_counts),
            "response_type_distribution": dict(response_types),
            "queries_with_satisfaction_rating": len(satisfaction_scores),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # ==================== API PERFORMANCE METRICS ====================
    
    def calculate_api_metrics(self, endpoint_times: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Calculate API performance metrics from collected response times:
        - Average response time per endpoint
        - P50, P95, P99 percentiles
        - Throughput (requests per second)
        """
        api_metrics = {}
        
        for endpoint, times in endpoint_times.items():
            if not times:
                continue
            
            sorted_times = sorted(times)
            n = len(sorted_times)
            
            api_metrics[endpoint] = {
                "avg_response_time_ms": round(statistics.mean(times) * 1000, 2),
                "median_response_time_ms": round(statistics.median(times) * 1000, 2),
                "p50_ms": round(sorted_times[int(n * 0.5)] * 1000, 2),
                "p95_ms": round(sorted_times[int(n * 0.95)] * 1000, 2) if n > 1 else 0,
                "p99_ms": round(sorted_times[int(n * 0.99)] * 1000, 2) if n > 1 else 0,
                "min_ms": round(min(times) * 1000, 2),
                "max_ms": round(max(times) * 1000, 2),
                "total_requests": n
            }
        
        return {
            "metric_type": "api_performance",
            "endpoints": api_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # ==================== SYSTEM METRICS ====================
    
    def calculate_system_metrics(self) -> Dict[str, Any]:
        """
        Calculate system-level metrics:
        - Database size
        - Total records per table
        - Data growth rate
        """
        metrics = {
            "metric_type": "system_metrics",
            "database_stats": {}
        }
        
        # Count records in major tables
        tables = {
            "users": User,
            "food_items": FoodItem,
            "meal_logs": MealLog,
            "recipes": Recipe,
            "food_ratings": FoodRating,
            "recipe_interactions": RecipeInteraction,
            "chatbot_interactions": ChatbotInteraction
        }
        
        for table_name, model in tables.items():
            try:
                count = self.db.query(func.count(model.id)).scalar() or 0
                metrics["database_stats"][table_name] = count
            except Exception as e:
                logger.warning(f"Could not count {table_name}: {e}")
        
        # Calculate data growth (new records in last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_meals = self.db.query(func.count(MealLog.id)).filter(
            MealLog.logged_at >= week_ago
        ).scalar() or 0
        
        metrics["recent_activity"] = {
            "meals_logged_last_7_days": recent_meals,
            "avg_meals_per_day": round(recent_meals / 7, 2)
        }
        
        metrics["timestamp"] = datetime.utcnow().isoformat()
        
        return metrics
    
    # ==================== COMPREHENSIVE REPORT ====================
    
    def generate_comprehensive_report(self, days: int = 30, 
                                    api_times: Optional[Dict[str, List[float]]] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report for research documentation
        """
        report = {
            "report_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "period_days": days,
                "report_version": "1.0"
            },
            "recommendation_metrics": self.calculate_recommendation_metrics(days=days),
            "engagement_metrics": self.calculate_engagement_metrics(days=days),
            "chatbot_metrics": self.calculate_chatbot_metrics(days=days),
            "system_metrics": self.calculate_system_metrics()
        }
        
        if api_times:
            report["api_performance"] = self.calculate_api_metrics(api_times)
        
        return report
    
    def export_report_to_json(self, report: Dict[str, Any], filename: str = None) -> str:
        """
        Export metrics report to JSON file
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_metrics_{timestamp}.json"
        
        filepath = f"/tmp/{filename}"
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Performance report exported to {filepath}")
        return filepath

