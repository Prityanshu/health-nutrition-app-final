#!/usr/bin/env python3
"""
Script to generate comprehensive performance metrics report for research documentation
"""
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.performance_metrics import PerformanceMetricsCollector

def generate_report(days: int = 30, output_file: str = None):
    """Generate and save performance metrics report"""
    db = SessionLocal()
    
    try:
        collector = PerformanceMetricsCollector(db)
        
        print(f"Generating performance metrics report for last {days} days...")
        print("=" * 60)
        
        # Generate comprehensive report
        report = collector.generate_comprehensive_report(days=days)
        
        # Generate filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"performance_metrics_report_{days}days_{timestamp}.json"
        
        # Save to file
        output_path = os.path.join(os.path.dirname(__file__), "..", output_file)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✅ Report generated successfully!")
        print(f"📄 Saved to: {output_path}")
        print("\n" + "=" * 60)
        print("REPORT SUMMARY")
        print("=" * 60)
        
        # Print summary
        if "recommendation_metrics" in report:
            rm = report["recommendation_metrics"]
            print(f"\n📊 Recommendation Metrics:")
            print(f"   - Total Users: {rm.get('total_users', 0)}")
            print(f"   - Total Interactions: {rm.get('total_interactions', 0)}")
            print(f"   - Coverage: {rm.get('coverage_percentage', 0)}%")
        
        if "engagement_metrics" in report:
            em = report["engagement_metrics"]
            print(f"\n👥 Engagement Metrics:")
            print(f"   - Avg Daily Active Users: {em.get('avg_daily_active_users', 0)}")
            print(f"   - Engagement Rate: {em.get('engagement_rate_percentage', 0)}%")
            print(f"   - Avg Meals per Active User: {em.get('avg_meals_per_active_user', 0)}")
        
        if "chatbot_metrics" in report:
            cm = report["chatbot_metrics"]
            print(f"\n🤖 Chatbot Metrics:")
            print(f"   - Total Queries: {cm.get('total_queries', 0)}")
            print(f"   - Success Rate: {cm.get('success_rate_percentage', 0)}%")
            if cm.get('avg_user_satisfaction'):
                print(f"   - Avg Satisfaction: {cm.get('avg_user_satisfaction', 0)}/5")
        
        if "system_metrics" in report:
            sm = report["system_metrics"]
            print(f"\n💾 System Metrics:")
            if "database_stats" in sm:
                print(f"   - Users: {sm['database_stats'].get('users', 0)}")
                print(f"   - Food Items: {sm['database_stats'].get('food_items', 0)}")
                print(f"   - Meal Logs: {sm['database_stats'].get('meal_logs', 0)}")
        
        print("\n" + "=" * 60)
        print(f"📋 Full report available in: {output_file}")
        print("=" * 60)
        
        return output_path
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate performance metrics report")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output filename (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    generate_report(days=args.days, output_file=args.output)




