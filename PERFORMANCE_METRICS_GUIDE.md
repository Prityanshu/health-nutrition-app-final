# Performance Metrics Collection Guide

## Overview

This guide explains how to collect and analyze performance metrics from your health nutrition app for research documentation and comparison with other models/research papers.

## Available Metrics

### 1. **ML Recommendation Metrics**
- **Coverage**: Percentage of food items recommended vs total available
- **Average interactions per user**: User engagement with recommendations
- **Precision@K & Recall@K**: Accuracy of recommendations (when ground truth available)

### 2. **User Engagement Metrics**
- **Daily Active Users (DAU)**: Average daily active users
- **Engagement Rate**: Percentage of registered users who are active
- **Average meals per active user**: User activity level
- **Retention metrics**: User return patterns

### 3. **AI Chatbot Metrics**
- **Total queries**: Number of chatbot interactions
- **Success rate**: Percentage of successful responses
- **User satisfaction**: Average satisfaction ratings (1-5 scale)
- **Agent distribution**: Which AI agents are used most

### 4. **API Performance Metrics**
- **Response times**: Average, median, P50, P95, P99 percentiles
- **Throughput**: Requests per second
- **Endpoint performance**: Per-endpoint metrics

### 5. **System Metrics**
- **Database statistics**: Record counts per table
- **Data growth**: Recent activity trends
- **System health**: Overall system status

## How to Collect Metrics

### Method 1: Via API Endpoints

#### Get Recommendation Metrics
```bash
curl http://localhost:8001/api/metrics/recommendation?days=30
```

#### Get Engagement Metrics
```bash
curl http://localhost:8001/api/metrics/engagement?days=30
```

#### Get Chatbot Metrics
```bash
curl http://localhost:8001/api/metrics/chatbot?days=30
```

#### Get System Metrics
```bash
curl http://localhost:8001/api/metrics/system
```

#### Get Comprehensive Report
```bash
curl http://localhost:8001/api/metrics/comprehensive?days=30
```

#### Export Report to JSON
```bash
curl http://localhost:8001/api/metrics/export?days=30
```

### Method 2: Using Python Script

```bash
# Generate report for last 30 days
python scripts/generate_metrics_report.py --days 30

# Generate report for last 7 days
python scripts/generate_metrics_report.py --days 7

# Specify output file
python scripts/generate_metrics_report.py --days 30 --output my_report.json
```

### Method 3: Via API Documentation

1. Start your backend server
2. Visit `http://localhost:8001/docs`
3. Navigate to the "performance-metrics" section
4. Try out the endpoints interactively

## Report Format

The comprehensive report includes:

```json
{
  "report_metadata": {
    "generated_at": "2025-10-23T12:00:00",
    "period_days": 30,
    "report_version": "1.0"
  },
  "recommendation_metrics": {
    "metric_type": "recommendation_performance",
    "total_users": 150,
    "total_interactions": 5000,
    "coverage_percentage": 15.5,
    "avg_interactions_per_user": 33.33
  },
  "engagement_metrics": {
    "metric_type": "user_engagement",
    "avg_daily_active_users": 45.2,
    "engagement_rate_percentage": 30.0,
    "avg_meals_per_active_user": 5.5
  },
  "chatbot_metrics": {
    "metric_type": "chatbot_performance",
    "total_queries": 1200,
    "success_rate_percentage": 95.5,
    "avg_user_satisfaction": 4.2
  },
  "system_metrics": {
    "metric_type": "system_metrics",
    "database_stats": {
      "users": 150,
      "food_items": 29000,
      "meal_logs": 5000
    }
  }
}
```

## Comparing with Research Papers

### Standard Metrics for Recommendation Systems

When comparing with research papers, focus on:

1. **Precision@K** (K=5, 10)
   - Measures accuracy of top-K recommendations
   - Higher is better (0-1 scale)

2. **Recall@K** (K=5, 10)
   - Measures coverage of relevant items
   - Higher is better (0-1 scale)

3. **NDCG@K** (Normalized Discounted Cumulative Gain)
   - Measures ranking quality
   - Higher is better (0-1 scale)

4. **Coverage**
   - Percentage of catalog items recommended
   - Higher indicates better diversity

5. **Diversity**
   - Variety in recommendations
   - Measured by cuisine/category distribution

### Standard Metrics for User Engagement

1. **Daily Active Users (DAU)**
2. **Monthly Active Users (MAU)**
3. **DAU/MAU Ratio** (Stickiness)
4. **Retention Rate** (Day 1, Day 7, Day 30)
5. **Average Session Duration**
6. **Actions per Session**

### Standard Metrics for AI Systems

1. **Response Time** (latency)
2. **Success Rate** (error-free responses)
3. **User Satisfaction** (1-5 scale)
4. **Task Completion Rate**

## Example: Generating Research Documentation

### Step 1: Collect Metrics
```bash
python scripts/generate_metrics_report.py --days 30 --output research_metrics_30days.json
```

### Step 2: Analyze Results
```python
import json

with open('research_metrics_30days.json', 'r') as f:
    report = json.load(f)

# Extract key metrics
precision = report['recommendation_metrics']['coverage_percentage']
engagement = report['engagement_metrics']['engagement_rate_percentage']
chatbot_success = report['chatbot_metrics']['success_rate_percentage']

print(f"Recommendation Coverage: {precision}%")
print(f"User Engagement: {engagement}%")
print(f"Chatbot Success Rate: {chatbot_success}%")
```

### Step 3: Compare with Baselines

Compare your metrics with:
- **Baseline models**: Simple popularity-based recommendations
- **State-of-the-art**: Recent research papers (2020-2025)
- **Industry standards**: Production systems

## Tips for Research Documentation

1. **Collect metrics over multiple time periods**
   - 7 days, 30 days, 90 days
   - Shows trends and stability

2. **Include confidence intervals**
   - Use standard deviation for error bars
   - Shows statistical significance

3. **Document experimental setup**
   - Number of users
   - Data collection period
   - System configuration

4. **Compare with baselines**
   - Random recommendations
   - Popularity-based
   - Collaborative filtering (if applicable)

5. **Include ablation studies**
   - Test individual components
   - Show contribution of each feature

## API Response Times

API performance is automatically tracked via middleware. Response times are included in the `X-Response-Time` header for each request.

To view API performance metrics:
```bash
curl http://localhost:8001/api/metrics/comprehensive
```

## Troubleshooting

### No Data Available
- Ensure users have logged meals/interactions
- Check date range (may need to extend `days` parameter)
- Verify database has activity in the specified period

### Missing Metrics
- Some metrics require specific data (e.g., satisfaction ratings)
- Check if features are enabled and being used

### Performance Issues
- Large date ranges may take longer to process
- Consider analyzing smaller time windows
- Use the script method for better performance

## Next Steps

1. **Run initial metrics collection**
2. **Analyze results** and identify areas for improvement
3. **Compare with research papers** in your domain
4. **Document findings** in your research paper
5. **Iterate and improve** based on metrics

## References

- **Recommendation Systems**: Precision@K, Recall@K, NDCG metrics
- **User Engagement**: DAU/MAU, retention metrics
- **AI Performance**: Response time, success rate, satisfaction

For more details, see the API documentation at `/docs` when your server is running.




