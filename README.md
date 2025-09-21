# 🥗 Nutrition Tracking App

A comprehensive full-stack nutrition tracking application built with FastAPI (Python) backend and React frontend.

## ✨ Features

### 🍽️ **Meal Logging**
- Log meals with detailed nutritional information
- Food item database with calories, protein, carbs, and fat
- Meal type categorization (breakfast, lunch, dinner, snack)
- Quantity tracking with automatic nutritional calculations

### 🎯 **Goal Setting**
- Set personalized nutrition goals
- Multiple goal types: weight loss, muscle gain, calorie targets, macro targets
- Target weight, calories, protein, carbs, fat tracking
- Goal deadline management

### 📊 **Progress Tracking**
- Daily nutrition dashboard
- Weekly progress overview with averages
- 30-day progress summary
- Goals vs actual progress comparison
- Visual progress indicators

### 🤖 **AI-Powered Chatbot Assistant**
- **Intelligent Agent Routing** - Automatically detects which AI agent to use based on user queries
- **Conversation Memory** - Remembers last 5-6 messages for context-aware responses
- **Smart Field Collection** - Reduces repetitive questions with intelligent defaults
- **Multi-Agent Support** - Works with 6 specialized AI agents:
  - **ChefGenius** - Recipe generation and cooking advice
  - **CulinaryExplorer** - Regional and cultural cuisine exploration
  - **BudgetChef** - Budget-friendly meal planning
  - **FitMentor** - Fitness and workout planning
  - **AdvancedMealPlanner** - Comprehensive 7-day meal planning
  - **NutrientAnalyzer** - Nutritional analysis and tracking
- **Fallback Responses** - Helpful responses even when AI services are unavailable
- **Beautiful Chat Interface** - Markdown rendering with rich text formatting

### 🏆 **Challenges & Gamification**
- Active challenges with reward points
- User achievements and badges
- Progress streaks tracking
- Points-based reward system
- Challenge requirements and deadlines

### 🔐 **User Management**
- Secure user registration and login
- JWT token-based authentication
- User profile management
- Session persistence

## 🛠️ **Tech Stack**

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **SQLite/PostgreSQL** - Relational database
- **SQLAlchemy** - SQL toolkit and ORM
- **JWT** - JSON Web Tokens for authentication
- **Pydantic** - Data validation using Python type annotations
- **Agno** - AI agent framework for intelligent chatbot
- **Groq** - High-performance AI model inference

### Frontend
- **React 18** - JavaScript library for building user interfaces
- **Custom CSS** - Responsive design with modern styling
- **Lucide React** - Beautiful icon library
- **Fetch API** - For API communication

### Development Tools
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Git** - Version control

## 🚀 **Quick Start**

### Prerequisites
- Python 3.8+
- Node.js 16+
- Docker (optional)
- Git

### Backend Setup

1. **Navigate to project directory:**
   ```bash
   cd major-project-redo
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the backend server:**
   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8001 --reload
   ```

4. **Access API documentation:**
   - Open http://127.0.0.1:8001/docs

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
   npm start
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
│   │   └── advanced_meal_planner.py # Advanced meal planning
│   ├── services/                  # Business logic services
│   │   ├── chatbot_manager.py     # AI chatbot orchestration
│   │   ├── chefgenius_service.py  # Recipe generation
│   │   ├── fitmentor_service.py   # Workout planning
│   │   ├── budgetchef_service.py  # Budget meal planning
│   │   ├── culinaryexplorer_service.py # Regional cuisine
│   │   ├── advanced_meal_planner_service.py # Meal planning
│   │   └── nutrient_analyzer_service.py # Nutrition analysis
│   ├── database.py                # Database configuration
│   ├── auth.py                    # Authentication logic
│   └── schemas.py                 # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── App.js                 # Main React component with chatbot
│   │   └── index.css              # Styling
│   ├── public/                    # Static assets
│   └── package.json               # Frontend dependencies
├── scripts/                       # Data loading scripts
├── main.py                       # FastAPI application entry point
├── requirements.txt              # Python dependencies
├── docker-compose.yml            # Docker configuration
└── README.md                     # This file
```

## 🔧 **API Endpoints**

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user

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
- `GET /api/tracking/daily/{date}` - Get daily stats
- `GET /api/tracking/weekly` - Get weekly stats
- `GET /api/tracking/progress` - Get progress summary

### Gamification
- `GET /api/gamification/challenges` - Get challenges
- `GET /api/gamification/achievements` - Get user achievements
- `GET /api/gamification/stats` - Get user stats

### AI Chatbot
- `POST /api/chatbot/chat` - Main chatbot endpoint with full response
- `POST /api/chatbot/chat/simple` - Simplified chatbot endpoint
- `GET /api/chatbot/agents` - Get available AI agents
- `GET /api/chatbot/health` - Chatbot service health check

## 🤖 **AI Chatbot Usage Examples**

### Recipe Generation
```
User: "I want a Kerala lunch recipe with chicken"
Bot: [Generates detailed Kerala chicken curry recipe with ingredients, instructions, and nutrition info]
```

### Workout Planning
```
User: "Plan a workout for muscle gain, 60 minutes, gym equipment"
Bot: [Creates comprehensive 7-day workout plan with exercises, sets, reps, and progression tips]
```

### Nutrition Analysis
```
User: "Analyze the nutrition in chicken curry 100g"
Bot: [Provides detailed nutritional breakdown with calories, macros, and micronutrients]
```

### Budget Meal Planning
```
User: "Create a budget meal plan for 200 rupees per day"
Bot: [Suggests cost-effective meal plans with shopping lists and cost breakdowns]
```

### Regional Cuisine
```
User: "I want Mediterranean dishes for dinner"
Bot: [Recommends authentic Mediterranean recipes with health adaptations]
```

### Advanced Meal Planning
```
User: "Suggest a 7-day meal plan for 2000 calories, vegetarian"
Bot: [Creates comprehensive weekly meal plan with shopping lists and prep tips]
```

## 🎨 **Screenshots**

### Dashboard
- Clean, modern interface with daily nutrition overview
- Quick action buttons for easy navigation
- Real-time data updates

### Meal Logging
- Intuitive food selection dropdown
- Meal type categorization
- Quantity input with validation

### Progress Tracking
- Color-coded nutrition metrics
- Weekly and monthly analytics
- Goals comparison with visual indicators

### Challenges
- Active challenges with progress tracking
- Achievement system with points
- User statistics dashboard

### AI Chatbot Interface
- Intelligent conversation with context awareness
- Beautiful markdown rendering for rich responses
- Service status indicators
- Quick suggestion buttons for common queries
- Multi-agent support with automatic routing

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
[Github](https://github.com/Prityanshu)
[LinkedIn](https://www.linkedin.com/in/prityanshu-yadav-301242304)

## 🙏 **Acknowledgments**

- FastAPI documentation and community
- React documentation and ecosystem
- Nutrition data from MyFitnessPal dataset
- Lucide React for beautiful icons

---

**Built with ❤️ for healthy living and nutrition tracking**
