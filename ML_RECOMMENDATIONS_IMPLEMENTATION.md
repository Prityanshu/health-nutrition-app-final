# ML Recommendations Implementation

## Overview
The AI Recommendations feature now uses sophisticated rule-based ML algorithms to provide personalized food, cuisine, and variety suggestions based on real user data and behavior patterns.

## Features Implemented

### 1. **Personalized Food Recommendations**
- **Algorithm**: `UserPreferenceLearner` + `IntelligentRecommendationEngine`
- **Data Sources**:
  - User's meal history (last 60 days)
  - Cuisine preferences learned from logged meals
  - Macro nutrient patterns (protein, carbs, fat ratios)
  - Health conditions (diabetes-friendly, hypertension-friendly)
  - Recent food consumption (to avoid repetition)

- **Scoring System**:
  - **Cuisine Match** (30% weight): Matches user's preferred cuisines
  - **Protein Alignment** (20% weight): Matches user's protein intake patterns
  - **Meal Appropriateness** (20% weight): Suitable for time of day
  - **Health Conditions** (10% weight each): Diabetes-friendly and hypertension-friendly bonuses

- **Returns**: Top 10 food recommendations with:
  - Food name, cuisine type, calories, macros
  - Recommendation score (0-1)
  - Personalized reason explaining why it's recommended

### 2. **Cuisine Suggestions**
- **Algorithm**: Diversity-based recommendation
- **Logic**:
  - Identifies new cuisines user hasn't tried
  - Suggests cuisines with low preference scores for retry
  - Prioritizes variety to expand user's culinary experience

- **Returns**: Top 5 cuisine suggestions with:
  - Cuisine name
  - Reason for suggestion
  - Priority level (high/medium)

### 3. **Variety Improvement Tips**
- **Algorithm**: Pattern analysis and diversity checks
- **Analysis**:
  - Cuisine variety (suggests if < 3 different cuisines)
  - Food category diversity (suggests if < 5 categories)
  - Recent food rotation (suggests if < 10 different foods in 14 days)

- **Returns**: Actionable tips to improve meal variety

### 4. **Macro Adjustments** (Bonus)
- Analyzes user's current macro balance
- Compares to preferences and goals
- Suggests adjustments for better nutrition

### 5. **Meal Timing Suggestions** (Bonus)
- Analyzes meal timing patterns
- Suggests improvements for regularity
- Recommends optimal meal schedules

## Technical Implementation

### Backend
- **Endpoint**: `GET /api/ml/personalized-recommendations`
- **Authentication**: Required (JWT token)
- **Services**:
  - `UserPreferenceLearner`: Analyzes user behavior patterns
  - `IntelligentRecommendationEngine`: Generates recommendations

### Frontend
- **Component**: "AI Recommendations" section
- **State Management**: React hooks with proper data mapping
- **Features**:
  - Displays food recommendations with scores and reasons
  - Shows cuisine suggestions with priorities
  - Lists variety improvement tips
  - Refresh button to get updated recommendations

## User Experience

### How It Works for Users:

1. **Initial State**: Users with limited data see generic recommendations
2. **Learning Phase**: As users log meals, the system learns:
   - Favorite cuisines
   - Protein/carb/fat preferences
   - Meal timing patterns
   - Food variety
3. **Personalization**: After 10+ meal logs, recommendations become highly personalized
4. **Continuous Improvement**: System adapts as user preferences evolve

### Example Recommendations:

**Food Recommendation**:
```
Grilled Chicken Breast
Mixed cuisine • 165 cal
Score: 100%
Reason: "matches your love for mixed cuisine, high in protein (matches your preference), heart-healthy option"
```

**Cuisine Suggestion**:
```
Mediterranean
Reason: "New cuisine to explore for variety"
Priority: High
```

**Variety Tip**:
```
"Experiment with different food categories (whole grains, lean proteins, healthy fats)"
"Try to include more different foods in your weekly rotation"
```

## Data Sources

The ML algorithms analyze:
- **MealLog** table: User's meal history
- **FoodItem** table: MyFitnessPal food database
- **User** table: Health conditions, dietary preferences
- **Goal** table: User's nutrition and fitness goals

## Benefits

1. **Personalization**: Recommendations improve with usage
2. **Health-Aware**: Considers user's health conditions
3. **Variety-Focused**: Encourages diverse eating patterns
4. **Context-Aware**: Adapts to time of day and recent meals
5. **Data-Driven**: Based on real user behavior, not assumptions

## Future Enhancements

- Integration with food ratings for feedback loop
- Seasonal food recommendations
- Budget-aware suggestions
- Social cooking insights integration
- Recipe recommendations based on food suggestions

