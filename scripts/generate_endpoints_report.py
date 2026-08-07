#!/usr/bin/env python3
"""
Generate comprehensive performance report of all features/endpoints in the application
"""
import sys
import os
import json
import inspect
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.routing import APIRoute
from app.database import SessionLocal
from app.services.performance_metrics import PerformanceMetricsCollector

def get_all_endpoints(app: FastAPI) -> List[Dict[str, Any]]:
    """Extract all endpoints from FastAPI app"""
    endpoints = []
    
    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoint_info = {
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name,
                "tags": route.tags if hasattr(route, 'tags') else [],
                "summary": route.summary if hasattr(route, 'summary') else None,
                "description": route.description if hasattr(route, 'description') else None,
            }
            endpoints.append(endpoint_info)
    
    return endpoints

def categorize_endpoints(endpoints: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize endpoints by feature area"""
    categories = {
        "Authentication": [],
        "User Management": [],
        "Meal Logging": [],
        "Meal Planning": [],
        "Progress Tracking": [],
        "Goals": [],
        "Recipes": [],
        "AI Chatbot": [],
        "ML Recommendations": [],
        "Gamification": [],
        "Challenges": [],
        "Fitness": [],
        "Budget": [],
        "Culinary": [],
        "Nutrient Analysis": [],
        "Food Ratings": [],
        "Recipe Interactions": [],
        "Social Cooking": [],
        "Onboarding": [],
        "Performance Metrics": [],
        "API Status": [],
        "Health & System": []
    }
    
    for endpoint in endpoints:
        path = endpoint["path"].lower()
        tags = [tag.lower() for tag in endpoint.get("tags", [])]
        
        # Categorize based on path and tags
        if "auth" in path or "login" in path or "register" in path:
            categories["Authentication"].append(endpoint)
        elif "user" in path or "profile" in path:
            categories["User Management"].append(endpoint)
        elif "meal" in path and "log" in path:
            categories["Meal Logging"].append(endpoint)
        elif "planner" in path or ("meal" in path and "plan" in path):
            categories["Meal Planning"].append(endpoint)
        elif "tracking" in path or "progress" in path or "daily" in path or "weekly" in path:
            categories["Progress Tracking"].append(endpoint)
        elif "goal" in path:
            categories["Goals"].append(endpoint)
        elif "recipe" in path and "interaction" not in path:
            categories["Recipes"].append(endpoint)
        elif "chatbot" in path:
            categories["AI Chatbot"].append(endpoint)
        elif "ml" in path or "recommendation" in path or "preference" in path:
            categories["ML Recommendations"].append(endpoint)
        elif "gamification" in path or "achievement" in path:
            categories["Gamification"].append(endpoint)
        elif "challenge" in path:
            categories["Challenges"].append(endpoint)
        elif "fitness" in path or "workout" in path:
            categories["Fitness"].append(endpoint)
        elif "budget" in path:
            categories["Budget"].append(endpoint)
        elif "culinary" in path:
            categories["Culinary"].append(endpoint)
        elif "nutrient" in path or "analyzer" in path:
            categories["Nutrient Analysis"].append(endpoint)
        elif "rating" in path:
            categories["Food Ratings"].append(endpoint)
        elif "recipe-interaction" in path or "recipe_interaction" in path:
            categories["Recipe Interactions"].append(endpoint)
        elif "social" in path:
            categories["Social Cooking"].append(endpoint)
        elif "onboarding" in path:
            categories["Onboarding"].append(endpoint)
        elif "metrics" in path:
            categories["Performance Metrics"].append(endpoint)
        elif "status" in path or "api" in path:
            categories["API Status"].append(endpoint)
        elif path == "/" or path == "/health" or path == "/docs":
            categories["Health & System"].append(endpoint)
        else:
            # Default categorization based on tags
            if tags:
                tag = tags[0].replace("-", " ").title()
                if tag not in categories:
                    categories[tag] = []
                categories[tag].append(endpoint)
            else:
                categories["Health & System"].append(endpoint)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v}

def generate_comprehensive_report(days: int = 30) -> Dict[str, Any]:
    """Generate comprehensive report of all features and endpoints"""
    
    # Import app
    from main import app
    
    # Get all endpoints
    all_endpoints = get_all_endpoints(app)
    categorized = categorize_endpoints(all_endpoints)
    
    # Get performance metrics
    db = SessionLocal()
    try:
        collector = PerformanceMetricsCollector(db)
        performance_metrics = collector.generate_comprehensive_report(days=days)
    except Exception as e:
        print(f"Warning: Could not generate performance metrics: {e}")
        performance_metrics = {}
    finally:
        db.close()
    
    # Count endpoints by method
    method_counts = {}
    for endpoint in all_endpoints:
        for method in endpoint["methods"]:
            method_counts[method] = method_counts.get(method, 0) + 1
    
    # Generate report
    report = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "report_version": "1.0",
            "total_endpoints": len(all_endpoints)
        },
        "endpoint_summary": {
            "total_endpoints": len(all_endpoints),
            "endpoints_by_method": method_counts,
            "categories_count": len(categorized),
            "endpoints_per_category": {k: len(v) for k, v in categorized.items()}
        },
        "endpoints_by_category": {},
        "performance_metrics": performance_metrics,
        "feature_list": []
    }
    
    # Add categorized endpoints
    for category, endpoints in categorized.items():
        report["endpoints_by_category"][category] = {
            "count": len(endpoints),
            "endpoints": [
                {
                    "path": e["path"],
                    "methods": e["methods"],
                    "name": e["name"],
                    "summary": e.get("summary"),
                    "description": e.get("description")
                }
                for e in endpoints
            ]
        }
        
        # Add to feature list
        report["feature_list"].append({
            "feature": category,
            "endpoint_count": len(endpoints),
            "endpoints": [e["path"] for e in endpoints]
        })
    
    return report

def print_report_summary(report: Dict[str, Any]):
    """Print a formatted summary of the report"""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE ENDPOINTS & FEATURES PERFORMANCE REPORT")
    print("=" * 80)
    
    metadata = report["report_metadata"]
    print(f"\n📊 Report Generated: {metadata['generated_at']}")
    print(f"📅 Analysis Period: {metadata['period_days']} days")
    print(f"🔢 Total Endpoints: {metadata['total_endpoints']}")
    
    summary = report["endpoint_summary"]
    print(f"\n📈 Endpoint Summary:")
    print(f"   - Total Endpoints: {summary['total_endpoints']}")
    print(f"   - Categories: {summary['categories_count']}")
    print(f"\n📋 Endpoints by HTTP Method:")
    for method, count in summary["endpoints_by_method"].items():
        print(f"   - {method}: {count}")
    
    print(f"\n📂 Features & Endpoints by Category:")
    print("-" * 80)
    for category, data in report["endpoints_by_category"].items():
        print(f"\n🔹 {category} ({data['count']} endpoints)")
        for endpoint in data["endpoints"]:
            methods_str = ", ".join(endpoint["methods"])
            print(f"   {methods_str:12} {endpoint['path']}")
            if endpoint.get("summary"):
                print(f"              └─ {endpoint['summary']}")
    
    # Performance metrics summary
    if "performance_metrics" in report and report["performance_metrics"]:
        print(f"\n\n📊 Performance Metrics Summary:")
        print("-" * 80)
        
        if "engagement_metrics" in report["performance_metrics"]:
            em = report["performance_metrics"]["engagement_metrics"]
            print(f"\n👥 User Engagement:")
            print(f"   - Avg Daily Active Users: {em.get('avg_daily_active_users', 0)}")
            print(f"   - Engagement Rate: {em.get('engagement_rate_percentage', 0)}%")
        
        if "chatbot_metrics" in report["performance_metrics"]:
            cm = report["performance_metrics"]["chatbot_metrics"]
            print(f"\n🤖 AI Chatbot:")
            print(f"   - Total Queries: {cm.get('total_queries', 0)}")
            print(f"   - Success Rate: {cm.get('success_rate_percentage', 0)}%")
        
        if "recommendation_metrics" in report["performance_metrics"]:
            rm = report["performance_metrics"]["recommendation_metrics"]
            print(f"\n🎯 ML Recommendations:")
            print(f"   - Coverage: {rm.get('coverage_percentage', 0)}%")
            print(f"   - Total Interactions: {rm.get('total_interactions', 0)}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate comprehensive endpoints and features report")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days for performance analysis (default: 30)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON filename (default: auto-generated)"
    )
    parser.add_argument(
        "--no-print",
        action="store_true",
        help="Don't print summary to console"
    )
    
    args = parser.parse_args()
    
    print("Generating comprehensive endpoints and features report...")
    print("=" * 80)
    
    try:
        report = generate_comprehensive_report(days=args.days)
        
        # Generate filename if not provided
        if not args.output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            args.output = f"endpoints_performance_report_{args.days}days_{timestamp}.json"
        
        # Save to file
        output_path = os.path.join(os.path.dirname(__file__), "..", args.output)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✅ Report generated successfully!")
        print(f"📄 Saved to: {output_path}")
        
        if not args.no_print:
            print_report_summary(report)
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




