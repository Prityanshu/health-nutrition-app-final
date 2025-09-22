# 🥗 Health & Nutrition App

A comprehensive full-stack nutrition tracking and meal planning application with AI-powered chatbot assistance, built with FastAPI (Python) backend and React frontend.

## ✨ Features

### 🍽️ **Meal Management**
- **Smart Meal Logging** - Log meals with detailed nutritional information and automatic calculations
- **Food Database** - Comprehensive food items with calories, protein, carbs, and fat
- **Meal History** - Track and review past meals with nutritional summaries
- **Quantity Tracking** - Precise measurements with automatic nutritional calculations

### 🎯 **Goal Setting & Tracking**
- **Personalized Goals** - Set nutrition targets for weight loss, muscle gain, or maintenance
- **Multi-Goal Support** - Calories, protein, carbs, fat, and weight targets
- **Progress Monitoring** - Real-time tracking with visual progress indicators
- **Achievement System** - Celebrate milestones and goal completions

### 📊 **Advanced Analytics**
- **Daily Dashboard** - Comprehensive nutrition overview with real-time updates
- **Weekly Analytics** - 7-day progress tracking with averages and trends
- **Monthly Reports** - 30-day nutrition summaries and insights
- **Goal Comparison** - Visual comparison of targets vs. actual progress

### 🤖 **AI-Powered Chatbot Assistant**
- **Intelligent Agent Routing** - Automatically detects which AI agent to use based on user queries
- **Multi-Agent Architecture** - 6 specialized AI agents for different use cases:
  - **ChefGenius** - Recipe generation and cooking advice
  - **CulinaryExplorer** - Regional and cultural cuisine exploration
  - **BudgetChef** - Budget-friendly meal planning
  - **FitMentor** - Fitness and workout planning
  - **AdvancedMealPlanner** - Comprehensive 7-day meal planning
  - **NutrientAnalyzer** - Nutritional analysis and tracking
- **Context-Aware Responses** - Remembers conversation history for personalized interactions
- **Smart Field Collection** - Reduces repetitive questions with intelligent defaults
- **Fallback Responses** - Helpful responses even when AI services are unavailable
- **Beautiful Chat Interface** - Markdown rendering with rich text formatting

### 🏆 **Gamification & Challenges**
- **Active Challenges** - Personalized nutrition and fitness challenges
- **Reward Points System** - Earn points for completing challenges and logging meals
- **Achievement Badges** - Unlock badges for milestones and consistency
- **Progress Streaks** - Track daily logging streaks and healthy habits
- **Leaderboard** - Friendly competition with other users

### 🔐 **User Management**
- **Secure Authentication** - JWT token-based authentication with bcrypt password hashing
- **User Profiles** - Comprehensive profile management with preferences
- **Session Persistence** - Seamless user experience across sessions
- **Privacy Protection** - Secure data handling and user privacy

### 💰 **Budget Meal Planning**
- **Cost-Effective Recipes** - Budget-friendly meal suggestions
- **Shopping Lists** - Automatic generation of ingredient lists
- **Price Tracking** - Monitor meal costs and budget adherence
- **Affordable Nutrition** - Maintain nutrition goals within budget constraints

### 🏃‍♂️ **Fitness Integration**
- **Workout Planning** - Personalized exercise routines based on goals
- **Activity Tracking** - Log workouts and physical activities
- **Fitness Goals** - Set and track fitness objectives
- **Progress Monitoring** - Visual fitness progress tracking

## 🛠️ **Tech Stack**

### Backend
- **FastAPI** - Modern, fast web framework for building APIs with automatic documentation
- **SQLite/PostgreSQL** - Relational database with SQLAlchemy ORM
- **JWT Authentication** - Secure token-based authentication
- **Pydantic** - Data validation using Python type annotations
- **Agno Framework** - AI agent orchestration for intelligent chatbot
- **Groq API** - High-performance AI model inference with fallback support
- **Uvicorn** - ASGI server for production deployment

### Frontend
- **React 18** - Modern JavaScript library with hooks and functional components
- **Custom CSS** - Responsive design with modern styling and animations
- **Lucide React** - Beautiful, consistent icon library
- **Fetch API** - Modern API communication with error handling

### AI & ML
- **Multi-Agent Architecture** - Specialized AI agents for different domains
- **Context Management** - Conversation memory and user preference learning
- **Fallback Mechanisms** - Graceful handling of API rate limits and failures
- **Smart Routing** - Intelligent agent selection based on user queries
- **Rule-Based ML Algorithms** - Advanced personalization and recommendation systems
- **UserPreferenceLearner** - Adaptive learning from user behavior patterns
- **IntelligentRecommendationEngine** - Multi-algorithm recommendation system
- **AdvancedUserProfiler** - Comprehensive user profiling and analysis
- **DataDrivenChallengeGenerator** - Personalized challenge creation based on user data

## 🚀 **Quick Start**

### Prerequisites
- Python 3.8+
- Node.js 16+
- Git

### Backend Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Prityanshu/health-nutrition-app-final.git
   cd health-nutrition-app-final
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the backend server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```

5. **Access API documentation:**
   - Open http://localhost:8001/docs

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   PORT=3001 npm start
   ```

4. **Access the application:**
   - Open http://localhost:3001

### Docker Setup (Alternative)

1. **Build and start all services:**
   ```bash
   docker-compose up --build
   ```

## 📁 **Project Structure**

```
health-nutrition-app-final/
├── app/
│   ├── routers/                    # API route handlers
│   │   ├── chatbot.py             # AI chatbot endpoints
│   │   ├── auth.py                # Authentication routes
│   │   ├── users.py               # User management
│   │   ├── meals.py               # Meal logging
│   │   ├── goals.py               # Goal setting
│   │   ├── tracking.py            # Progress tracking
│   │   ├── gamification.py        # Challenges & achievements
│   │   ├── fitness.py             # Workout planning
│   │   ├── budget.py              # Budget meal planning
│   │   ├── culinary.py            # Regional cuisine
│   │   ├── nutrient_analyzer.py   # Nutrition analysis
│   │   ├── advanced_meal_planner.py # Advanced meal planning
│   │   ├── ml_recommendations.py  # ML-based recommendations
│   │   ├── enhanced_ml_router.py  # Enhanced ML features
│   │   ├── food_rating_router.py  # Food rating system
│   │   ├── recipe_interaction_router.py # Recipe interactions
│   │   └── social_cooking_router.py # Social cooking features
│   ├── services/                  # Business logic services
│   │   ├── chatbot_manager.py     # AI chatbot orchestration
│   │   ├── chefgenius_service.py  # Recipe generation
│   │   ├── fitmentor_service.py   # Workout planning
│   │   ├── budgetchef_service.py  # Budget meal planning
│   │   ├── culinaryexplorer_service.py # Regional cuisine
│   │   ├── advanced_meal_planner_service.py # Meal planning
│   │   ├── nutrient_analyzer_service.py # Nutrition analysis
│   │   ├── enhanced_ml_recommendations.py # ML recommendations
│   │   ├── data_driven_challenge_generator.py # Challenge generation
│   │   ├── food_rating_service.py # Food rating logic
│   │   ├── recipe_interaction_service.py # Recipe interactions
│   │   └── social_cooking_service.py # Social cooking
│   ├── models/                    # Database models
│   │   ├── enhanced_models.py     # Enhanced data models
│   │   └── enhanced_challenge_models.py # Challenge models
│   ├── database.py                # Database configuration
│   ├── auth.py                    # Authentication logic
│   └── schemas.py                 # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── App.js                 # Main React component
│   │   └── index.css              # Styling
│   ├── public/                    # Static assets
│   └── package.json               # Frontend dependencies
├── scripts/                       # Data loading and setup scripts
├── main.py                       # FastAPI application entry point
├── requirements.txt              # Python dependencies
├── docker-compose.yml            # Docker configuration
└── README.md                     # This file
```

## 🔧 **API Endpoints**

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user profile

### Meals
- `POST /api/meals/log` - Log a meal
- `GET /api/meals/history` - Get meal history
- `GET /api/meals/food-items` - Get available food items

### Goals
- `POST /api/goals/` - Create a goal
- `GET /api/goals/` - Get user goals
- `PUT /api/goals/{id}` - Update a goal
- `DELETE /api/goals/{id}` - Delete a goal

### Tracking
- `GET /api/tracking/daily/{date}` - Get daily nutrition stats
- `GET /api/tracking/weekly` - Get weekly progress
- `GET /api/tracking/progress` - Get progress summary

### Gamification
- `GET /api/gamification/challenges` - Get active challenges
- `GET /api/gamification/achievements` - Get user achievements
- `GET /api/gamification/stats` - Get user statistics

### AI Chatbot
- `POST /api/chatbot/chat` - Main chatbot endpoint
- `POST /api/chatbot/chat/simple` - Simplified chatbot endpoint
- `GET /api/chatbot/agents` - Get available AI agents
- `GET /api/chatbot/health` - Chatbot service health check

### Enhanced Features
- `GET /api/enhanced-challenges/active-challenges` - Get active challenges
- `POST /api/enhanced-challenges/generate-weekly-challenges` - Generate new challenges
- `POST /api/food-ratings/rate` - Rate food items
- `POST /api/recipe-interactions/track` - Track recipe interactions
- `POST /api/social-cooking/create-profile` - Create social cooking profile

### ML & Recommendation Engine
- `GET /api/ml/preferences` - Get learned user preferences
- `GET /api/ml/recommendations` - Get personalized recommendations
- `GET /api/enhanced-ml/profile` - Get comprehensive user profile
- `GET /api/enhanced-ml/insights` - Get behavioral insights and analytics

## 🤖 **AI Chatbot Usage Examples**

### Recipe Generation
```
User: "I want a Kerala lunch recipe with chicken"
Bot: [Generates detailed Kerala chicken curry recipe with ingredients, 
      instructions, cooking time, and nutritional information]
```

### Workout Planning
```
User: "Plan a workout for muscle gain, 60 minutes, gym equipment"
Bot: [Creates comprehensive workout plan with exercises, sets, reps, 
      and progression tips]
```

### Nutrition Analysis
```
User: "Analyze the nutrition in chicken curry 100g"
Bot: [Provides detailed nutritional breakdown with calories, macros, 
      and micronutrients]
```

### Budget Meal Planning
```
User: "Create a budget meal plan for 200 rupees per day"
Bot: [Suggests cost-effective meal plans with shopping lists and 
      cost breakdowns]
```

### Regional Cuisine
```
User: "I want Mediterranean dishes for dinner"
Bot: [Recommends authentic Mediterranean recipes with health 
      adaptations]
```

### Advanced Meal Planning
```
User: "Suggest a 7-day meal plan for 2000 calories, vegetarian"
Bot: [Creates comprehensive weekly meal plan with shopping lists 
      and prep tips]
```

## 🎨 **User Interface**

### Dashboard
- Clean, modern interface with daily nutrition overview
- Real-time data updates and progress indicators
- Quick action buttons for easy navigation
- Responsive design for all devices

### Meal Logging
- Intuitive food selection with search functionality
- Meal type categorization (breakfast, lunch, dinner, snack)
- Quantity input with validation and suggestions
- Automatic nutritional calculations

### Progress Tracking
- Color-coded nutrition metrics and progress bars
- Weekly and monthly analytics with trends
- Goals comparison with visual indicators
- Export functionality for progress reports

### Challenges & Gamification
- Active challenges with progress tracking
- Achievement system with points and badges
- User statistics dashboard
- Social features and leaderboards

### AI Chatbot Interface
- Intelligent conversation with context awareness
- Beautiful markdown rendering for rich responses
- Service status indicators and error handling
- Quick suggestion buttons for common queries
- Multi-agent support with automatic routing

## 🔒 **Security Features**

- **JWT Authentication** - Secure token-based authentication
- **Password Hashing** - bcrypt encryption for user passwords
- **CORS Protection** - Cross-origin resource sharing configuration
- **Input Validation** - Pydantic models for data validation
- **SQL Injection Protection** - SQLAlchemy ORM with parameterized queries
- **Rate Limiting** - API rate limiting to prevent abuse

## 📊 **Performance Features**

- **Async/Await** - Non-blocking I/O operations
- **Database Optimization** - Efficient queries with proper indexing
- **Caching** - Response caching for frequently accessed data
- **Error Handling** - Comprehensive error handling and logging
- **API Documentation** - Automatic OpenAPI/Swagger documentation
- **Health Checks** - Service health monitoring endpoints

## 🧠 **Advanced ML & Personalization Features**

### **Rule-Based ML Algorithms**
- **UserPreferenceLearner** - Learns and adapts to user eating patterns over time
  - Analyzes cuisine preferences from meal history
  - Tracks macro patterns (protein, carbs, fat ratios)
  - Identifies meal timing preferences
  - Learns calorie consumption patterns
  - Detects food category preferences
  - Measures adherence to goals and consistency

### **IntelligentRecommendationEngine** 
- **Multi-Algorithm Scoring System** - Combines multiple ML approaches:
  - **Collaborative Filtering** - User-based and item-based recommendations
  - **Content-Based Filtering** - Nutritional content analysis and matching
  - **Hybrid Recommendation System** - Ensemble methods for optimal accuracy
  - **Behavioral Pattern Analysis** - Clustering and trend analysis

### **AdvancedUserProfiler**
- **Multi-Dimensional Analysis** - Comprehensive user profiling:
  - **Cooking Pattern Analysis** - Skill level, equipment, time preferences
  - **Nutrition Goal Tracking** - Current vs. target analysis
  - **Food Preference Learning** - Adaptive preference scoring
  - **Social Cooking Insights** - Family size, dietary restrictions
  - **Seasonal Preference Analysis** - Time-based preference adaptation
  - **Chatbot Interaction Learning** - Conversation pattern analysis

### **DataDrivenChallengeGenerator**
- **Personalized Challenge Creation** - ML-driven challenge generation:
  - **Behavioral Gap Analysis** - Identifies areas for improvement
  - **Goal Alignment Scoring** - Challenges aligned with user objectives
  - **Difficulty Progression** - Adaptive difficulty based on performance
  - **Success Pattern Recognition** - Learns from successful completions

### **Enhanced Scoring Algorithms**
- **Cuisine Preference Alignment** (25% weight) - Matches user's cuisine preferences
- **Nutritional Alignment** (20% weight) - Aligns with nutritional goals
- **Cooking Profile Match** (15% weight) - Matches cooking skill and equipment
- **Behavioral Pattern Alignment** (15% weight) - Considers historical patterns
- **Seasonal Appropriateness** (10% weight) - Time and season considerations
- **Social Cooking Alignment** (10% weight) - Family and social preferences
- **Meal Type Appropriateness** (5% weight) - Context-aware meal suggestions

### **Context-Aware Intelligence**
- **Temporal Context** - Time-based recommendations (breakfast, lunch, dinner)
- **Seasonal Adaptation** - Weather and seasonal food preferences
- **Mood and Situation Awareness** - Context-sensitive suggestions
- **Budget Integration** - Cost-aware meal planning
- **Health Condition Adaptation** - Medical condition considerations
- **Equipment and Skill Matching** - Practical cooking recommendations

## 🧪 **Testing**

The project includes comprehensive testing with:
- **Unit Tests** - Individual component testing
- **Integration Tests** - API endpoint testing
- **End-to-End Tests** - Complete user workflow testing
- **Performance Tests** - Load testing and optimization
- **Chatbot Tests** - AI agent functionality testing

## 🚀 **Deployment**

### Production Setup
1. **Environment Configuration** - Set production environment variables
2. **Database Migration** - Run database migrations
3. **Static Files** - Serve static files with nginx
4. **SSL Certificate** - Configure HTTPS for security
5. **Monitoring** - Set up logging and monitoring

### Docker Deployment
```bash
# Build and deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 **Author**

**Prityanshu Yadav**
- [GitHub](https://github.com/Prityanshu)
- [LinkedIn](https://www.linkedin.com/in/prityanshu-yadav-301242304)

## 🙏 **Acknowledgments**

- FastAPI documentation and community
- React documentation and ecosystem
- Agno framework for AI agent orchestration
- Groq for high-performance AI inference
- Nutrition data from MyFitnessPal dataset
- Lucide React for beautiful icons

## 🔮 **Future Enhancements**

- **Mobile App** - React Native mobile application
- **Social Features** - User communities and sharing
- **Advanced Analytics** - Machine learning insights
- **Integration** - Third-party fitness app integration
- **Voice Interface** - Voice-activated chatbot
- **Meal Prep** - Advanced meal preparation features

---

**Built with ❤️ for healthy living and nutrition tracking**