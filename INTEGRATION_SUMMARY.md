# ML Recommendations & Advanced Meal Planning Integration Summary

## Overview
Successfully integrated ML-powered recommendations and advanced meal planning features into your nutrition app. The integration includes both backend services and frontend components.

## New Features Added

### 1. ML Recommendation System
- **User Preference Learning**: Analyzes user eating patterns, cuisine preferences, macro patterns, and meal timing
- **Intelligent Food Recommendations**: Provides personalized food suggestions based on learned preferences
- **Cuisine Recommendations**: Suggests new cuisines to try for variety
- **Macro Adjustments**: Recommends macro-nutrient adjustments based on goals
- **Variety Suggestions**: Provides tips to improve meal variety

### 2. Advanced Meal Planning
- **Week-long Meal Plans**: Generates comprehensive 7-day meal plans
- **Macro Targeting**: Plans meals to meet specific macro-nutrient ratios
- **Variety Constraints**: Ensures food variety across the week
- **Cuisine Preferences**: Incorporates user's preferred cuisines
- **Cost Optimization**: Considers food costs in planning

### 3. Enhanced Recipe Generation
- **LLM Integration**: Uses OpenAI GPT for personalized recipe generation
- **Template Fallback**: Template-based recipes when LLM is unavailable
- **Health Considerations**: Adapts recipes based on health conditions
- **Nutritional Analysis**: Calculates estimated nutrition per serving

### 4. Nutrition Calculator
- **BMR/TDEE Calculation**: Calculates basal metabolic rate and total daily energy expenditure
- **Goal-based Targets**: Adjusts calorie targets based on user goals
- **Macro Distribution**: Calculates optimal macro-nutrient ratios
- **Meal Timing**: Suggests optimal meal times

## Files Created/Modified

### Backend Files
1. **app/schemas.py** - Pydantic models for all new features
2. **app/routers/advanced_planning.py** - Advanced meal planning API endpoints
3. **app/services/recipe_generator.py** - Enhanced recipe generation service
4. **app/services/nutrition.py** - Nutrition calculation service
5. **main.py** - Updated to include new routers
6. **app/database.py** - Added new models for ML features

### Frontend Files
1. **frontend/src/App.js** - Added ML recommendations and advanced planning views

## API Endpoints Added

### ML Recommendations (`/api/ml/`)
- `GET /user-preferences` - Get learned user preferences
- `GET /personalized-recommendations` - Get personalized food recommendations
- `GET /smart-meal-suggestions` - Get smart meal suggestions
- `POST /update-food-rating` - Rate foods to improve recommendations
- `GET /recommendation-insights` - Get recommendation insights

### Advanced Planning (`/api/advanced-planning/`)
- `POST /generate-week-plan` - Generate advanced week meal plan
- `GET /smart-recommendations` - Get smart recommendations
- `GET /meal-variety-analysis` - Analyze meal variety
- `GET /macro-balance-analysis` - Analyze macro balance
- `POST /optimize-meal-plan` - Optimize existing meal plan
- `GET /planning-insights` - Get planning insights

## Database Models Added

1. **FoodRating** - User food ratings for ML learning
2. **UserPreference** - Stored user preferences
3. **Recipe** - Generated and saved recipes

## Frontend Features Added

### New Views
1. **AI Recommendations** - Displays personalized food recommendations, cuisine suggestions, and variety tips
2. **Advanced Planning** - Form to generate advanced meal plans with macro targeting

### Dashboard Updates
- Added new quick action buttons for ML recommendations and advanced planning
- Updated layout to accommodate new features

## Configuration Required

### Environment Variables
```bash
# Optional: For LLM recipe generation
OPENAI_API_KEY=your_openai_api_key_here
```

### Dependencies
The following Python packages are required:
```bash
pip install numpy pandas openai
```

## Usage Instructions

### 1. Start the Backend
```bash
cd /path/to/your/project
python main.py
```

### 2. Start the Frontend
```bash
cd frontend
npm start
```

### 3. Access the Application
- Frontend: http://localhost:3000
- API Documentation: http://localhost:8000/docs

## Key Features

### ML Recommendations
- Learns from user's meal history
- Provides personalized food suggestions
- Suggests new cuisines to try
- Offers variety improvement tips
- Adapts to user's health conditions

### Advanced Meal Planning
- Generates 7-day meal plans
- Targets specific macro ratios
- Ensures food variety
- Considers user preferences
- Provides detailed nutrition breakdown

### Recipe Generation
- Uses AI for personalized recipes
- Falls back to templates if AI unavailable
- Considers dietary restrictions
- Calculates nutritional information

## Testing the Integration

1. **Register/Login** to the application
2. **Log some meals** to build user preference data
3. **Visit AI Recommendations** to see personalized suggestions
4. **Use Advanced Planning** to generate meal plans
5. **Check the API documentation** at `/docs` for all available endpoints

## Next Steps

1. **Add more food data** to improve recommendations
2. **Implement user feedback** collection for better learning
3. **Add more recipe templates** for better fallback
4. **Integrate with external nutrition APIs** for more accurate data
5. **Add meal plan sharing** features
6. **Implement grocery list generation** from meal plans

## Troubleshooting

### Common Issues
1. **Import errors**: Make sure all dependencies are installed
2. **Database errors**: Run database migrations if needed
3. **API errors**: Check that all services are running
4. **Frontend errors**: Ensure React app is properly built

### Support
- Check the API documentation at `/docs` for endpoint details
- Review the console logs for error messages
- Ensure all environment variables are set correctly
