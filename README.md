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
- **PostgreSQL** - Relational database
- **SQLAlchemy** - SQL toolkit and ORM
- **JWT** - JSON Web Tokens for authentication
- **Pydantic** - Data validation using Python type annotations

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
major-project-redo/
├── app/
│   ├── routers/          # API route handlers
│   ├── database.py       # Database configuration
│   └── auth.py          # Authentication logic
├── frontend/
│   ├── src/
│   │   ├── App.js       # Main React component
│   │   └── index.css    # Styling
│   ├── public/          # Static assets
│   └── package.json     # Frontend dependencies
├── scripts/             # Data loading scripts
├── main.py             # FastAPI application entry point
├── requirements.txt    # Python dependencies
├── docker-compose.yml  # Docker configuration
└── README.md          # This file
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
