import React, { useState, useEffect } from 'react';
import { 
  Utensils, 
  Target, 
  TrendingUp, 
  Award, 
  Menu,
  X,
  ArrowLeft,
  Brain,
  Calendar,
  ChefHat,
  Lightbulb,
  BarChart3
} from 'lucide-react';
import './index.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api';

function App() {
  const [currentView, setCurrentView] = useState('login');
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Login form state
  const [loginForm, setLoginForm] = useState({
    username: '',
    password: ''
  });

  // Registration form state
  const [registerForm, setRegisterForm] = useState({
    email: '',
    username: '',
    password: '',
    full_name: '',
    age: 25,
    weight: 70,
    height: 170,
    activity_level: 'moderately_active'
  });

  // Dashboard data
  const [dashboardData, setDashboardData] = useState({
    dailyStats: null,
    recentMeals: [],
    challenges: [],
    goals: []
  });

  // Navigation state
  const [activeView, setActiveView] = useState('dashboard');

  // ML Recommendations state
  const [mlRecommendations, setMlRecommendations] = useState({
    foodRecommendations: [],
    cuisineRecommendations: [],
    varietySuggestions: [],
    macroAdjustments: []
  });

  // Advanced Planning state
  const [advancedPlan, setAdvancedPlan] = useState(null);
  const [planningForm, setPlanningForm] = useState({
    target_calories: '',
    protein_percentage: 25,
    carb_percentage: 45,
    fat_percentage: 30,
    meals_per_day: 3,
    cuisine_type: 'mixed'
  });

  // Meal logging state
  const [foodItems, setFoodItems] = useState([]);
  const [mealLogForm, setMealLogForm] = useState({
    food_item_id: '',
    meal_type: 'breakfast',
    quantity: 1.0
  });

  // Goals state
  const [goals, setGoals] = useState([]);
  const [goalForm, setGoalForm] = useState({
    goal_type: 'weight_loss',
    target_weight: '',
    target_calories: '',
    target_protein: '',
    target_carbs: '',
    target_fat: '',
    target_date: ''
  });

  // Progress state
  const [progressData, setProgressData] = useState({
    dailyStats: null,
    weeklyStats: null,
    progressSummary: null
  });

  // Challenges state
  const [challenges, setChallenges] = useState([]);
  const [userAchievements, setUserAchievements] = useState([]);
  const [userStats, setUserStats] = useState(null);

  const fetchUserData = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
        setCurrentView('dashboard');
        loadDashboardData();
      } else {
        localStorage.removeItem('token');
      }
    } catch (error) {
      console.error('Error fetching user data:', error);
      localStorage.removeItem('token');
    }
  };

  useEffect(() => {
    // Check if user is already logged in
    const token = localStorage.getItem('token');
    if (token) {
      // Verify token and get user data
      fetchUserData();
    }
  }, []);

  useEffect(() => {
    // Fetch food items when log-meal view is active
    if (activeView === 'log-meal' && foodItems.length === 0) {
      fetchFoodItems();
    }
  }, [activeView, foodItems.length]);

  useEffect(() => {
    // Fetch goals when set-goals view is active
    if (activeView === 'set-goals') {
      fetchGoals();
    }
  }, [activeView]);

  useEffect(() => {
    // Fetch progress data when view-progress view is active
    if (activeView === 'view-progress') {
      fetchProgressData();
    }
  }, [activeView]);

  useEffect(() => {
    // Fetch challenges data when challenges view is active
    if (activeView === 'challenges') {
      fetchChallengesData();
    }
  }, [activeView]);

  useEffect(() => {
    // Fetch ML recommendations when ml-recommendations view is active
    if (activeView === 'ml-recommendations') {
      fetchMLRecommendations();
    }
  }, [activeView]);

  useEffect(() => {
    // Fetch advanced planning data when advanced-planning view is active
    if (activeView === 'advanced-planning') {
      fetchAdvancedPlanningData();
    }
  }, [activeView]);

  const loadDashboardData = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      // Fetch daily stats
      const today = new Date().toISOString().split('T')[0];
      const statsResponse = await fetch(`${API_BASE_URL}/tracking/daily/${today}`, { headers });
      if (statsResponse.ok) {
        const stats = await statsResponse.json();
        setDashboardData(prev => ({ ...prev, dailyStats: stats }));
      }

      // Fetch recent meals
      const mealsResponse = await fetch(`${API_BASE_URL}/meals/history?limit=5`, { headers });
      if (mealsResponse.ok) {
        const meals = await mealsResponse.json();
        setDashboardData(prev => ({ ...prev, recentMeals: meals }));
      }

      // Fetch challenges
      const challengesResponse = await fetch(`${API_BASE_URL}/gamification/challenges`, { headers });
      if (challengesResponse.ok) {
        const challenges = await challengesResponse.json();
        setDashboardData(prev => ({ ...prev, challenges: challenges }));
      }

    } catch (error) {
      console.error('Error loading dashboard data:', error);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('username', loginForm.username);
      formData.append('password', loginForm.password);

      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        await fetchUserData();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Login failed');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(registerForm)
      });

      if (response.ok) {
        setError('');
        setCurrentView('login');
        alert('Registration successful! Please log in.');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Registration failed');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
    setCurrentView('login');
    setDashboardData({
      dailyStats: null,
      recentMeals: [],
      challenges: [],
      goals: []
    });
    setActiveView('dashboard');
  };

  const fetchFoodItems = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/meals/food-items?limit=100`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.ok) {
        const items = await response.json();
        setFoodItems(items);
      }
    } catch (error) {
      console.error('Error fetching food items:', error);
    }
  };

  const handleLogMeal = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/meals/log`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(mealLogForm)
      });

      if (response.ok) {
        setError('');
        setMealLogForm({
          food_item_id: '',
          meal_type: 'breakfast',
          quantity: 1.0
        });
        alert('Meal logged successfully!');
        // Refresh dashboard data
        loadDashboardData();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to log meal');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchGoals = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/goals/`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.ok) {
        const userGoals = await response.json();
        setGoals(userGoals);
      }
    } catch (error) {
      console.error('Error fetching goals:', error);
    }
  };

  const handleCreateGoal = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      
      // Prepare goal data - only include fields that have values
      const goalData = {
        goal_type: goalForm.goal_type
      };
      
      if (goalForm.target_weight) goalData.target_weight = parseFloat(goalForm.target_weight);
      if (goalForm.target_calories) goalData.target_calories = parseFloat(goalForm.target_calories);
      if (goalForm.target_protein) goalData.target_protein = parseFloat(goalForm.target_protein);
      if (goalForm.target_carbs) goalData.target_carbs = parseFloat(goalForm.target_carbs);
      if (goalForm.target_fat) goalData.target_fat = parseFloat(goalForm.target_fat);
      if (goalForm.target_date) goalData.target_date = goalForm.target_date;

      const response = await fetch(`${API_BASE_URL}/goals/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(goalData)
      });

      if (response.ok) {
        setError('');
        setGoalForm({
          goal_type: 'weight_loss',
          target_weight: '',
          target_calories: '',
          target_protein: '',
          target_carbs: '',
          target_fat: '',
          target_date: ''
        });
        alert('Goal created successfully!');
        // Refresh goals list
        fetchGoals();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to create goal');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteGoal = async (goalId) => {
    if (!window.confirm('Are you sure you want to delete this goal?')) return;

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/goals/${goalId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        alert('Goal deleted successfully!');
        // Refresh goals list
        fetchGoals();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to delete goal');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    }
  };

  const fetchProgressData = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      // Fetch daily stats for today
      const today = new Date().toISOString().split('T')[0];
      const dailyResponse = await fetch(`${API_BASE_URL}/tracking/daily/${today}`, { headers });
      
      // Fetch weekly stats
      const weeklyResponse = await fetch(`${API_BASE_URL}/tracking/weekly`, { headers });
      
      // Fetch progress summary (last 30 days)
      const progressResponse = await fetch(`${API_BASE_URL}/tracking/progress`, { headers });

      const newProgressData = {
        dailyStats: null,
        weeklyStats: null,
        progressSummary: null
      };

      if (dailyResponse.ok) {
        newProgressData.dailyStats = await dailyResponse.json();
      }

      if (weeklyResponse.ok) {
        newProgressData.weeklyStats = await weeklyResponse.json();
      }

      if (progressResponse.ok) {
        newProgressData.progressSummary = await progressResponse.json();
      }

      setProgressData(newProgressData);
    } catch (error) {
      console.error('Error fetching progress data:', error);
    }
  };

  const fetchChallengesData = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      // Fetch challenges
      const challengesResponse = await fetch(`${API_BASE_URL}/gamification/challenges`, { headers });
      
      // Fetch user achievements
      const achievementsResponse = await fetch(`${API_BASE_URL}/gamification/achievements`, { headers });
      
      // Fetch user stats
      const statsResponse = await fetch(`${API_BASE_URL}/gamification/stats`, { headers });

      if (challengesResponse.ok) {
        const challengesData = await challengesResponse.json();
        setChallenges(challengesData);
      }

      if (achievementsResponse.ok) {
        const achievementsData = await achievementsResponse.json();
        setUserAchievements(achievementsData);
      }

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setUserStats(statsData);
      }
    } catch (error) {
      console.error('Error fetching challenges data:', error);
    }
  };

  const fetchMLRecommendations = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      // Fetch personalized recommendations
      const recommendationsResponse = await fetch(`${API_BASE_URL}/ml/personalized-recommendations`, { headers });
      
      if (recommendationsResponse.ok) {
        const data = await recommendationsResponse.json();
        setMlRecommendations(data.recommendations);
      }
    } catch (error) {
      console.error('Error fetching ML recommendations:', error);
    }
  };

  const fetchAdvancedPlanningData = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      // Fetch variety analysis
      const varietyResponse = await fetch(`${API_BASE_URL}/advanced-planning/meal-variety-analysis`, { headers });
      
      if (varietyResponse.ok) {
        const varietyData = await varietyResponse.json();
        // Store variety data for display
        console.log('Variety analysis:', varietyData);
      }
    } catch (error) {
      console.error('Error fetching advanced planning data:', error);
    }
  };

  const generateAdvancedPlan = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/advanced-planning/generate-week-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(planningForm)
      });

      if (response.ok) {
        const plan = await response.json();
        setAdvancedPlan(plan);
        alert('Advanced meal plan generated successfully!');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to generate meal plan');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    }
  };

  const renderLogin = () => (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-bold text-gray-900">
            Sign in to your account
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleLogin}>
          <div className="space-y-4">
            <div>
              <label className="form-label">Email or Username</label>
              <input
                type="text"
                required
                className="form-input"
                value={loginForm.username}
                onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
              />
            </div>
            <div>
              <label className="form-label">Password</label>
              <input
                type="password"
                required
                className="form-input"
                value={loginForm.password}
                onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
              />
            </div>
          </div>

          {error && (
            <div className="text-red-600 text-sm text-center">{error}</div>
          )}

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="btn btn-primary w-full"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>

          <div className="text-center">
            <button
              type="button"
              onClick={() => setCurrentView('register')}
              className="text-blue-600 hover:text-blue-500"
            >
              Don't have an account? Sign up
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  const renderRegister = () => (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-bold text-gray-900">
            Create your account
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleRegister}>
          <div className="space-y-4">
            <div>
              <label className="form-label">Email</label>
              <input
                type="email"
                required
                className="form-input"
                value={registerForm.email}
                onChange={(e) => setRegisterForm({...registerForm, email: e.target.value})}
              />
            </div>
            <div>
              <label className="form-label">Username</label>
              <input
                type="text"
                required
                className="form-input"
                value={registerForm.username}
                onChange={(e) => setRegisterForm({...registerForm, username: e.target.value})}
              />
            </div>
            <div>
              <label className="form-label">Full Name</label>
              <input
                type="text"
                required
                className="form-input"
                value={registerForm.full_name}
                onChange={(e) => setRegisterForm({...registerForm, full_name: e.target.value})}
              />
            </div>
            <div>
              <label className="form-label">Password</label>
              <input
                type="password"
                required
                className="form-input"
                value={registerForm.password}
                onChange={(e) => setRegisterForm({...registerForm, password: e.target.value})}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="form-label">Age</label>
                <input
                  type="number"
                  required
                  className="form-input"
                  value={registerForm.age}
                  onChange={(e) => setRegisterForm({...registerForm, age: parseInt(e.target.value)})}
                />
              </div>
              <div>
                <label className="form-label">Weight (kg)</label>
                <input
                  type="number"
                  required
                  className="form-input"
                  value={registerForm.weight}
                  onChange={(e) => setRegisterForm({...registerForm, weight: parseFloat(e.target.value)})}
                />
              </div>
            </div>
            <div>
              <label className="form-label">Height (cm)</label>
              <input
                type="number"
                required
                className="form-input"
                value={registerForm.height}
                onChange={(e) => setRegisterForm({...registerForm, height: parseFloat(e.target.value)})}
              />
            </div>
          </div>

          {error && (
            <div className="text-red-600 text-sm text-center">{error}</div>
          )}

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="btn btn-primary w-full"
            >
              {isLoading ? 'Creating account...' : 'Create account'}
            </button>
          </div>

          <div className="text-center">
            <button
              type="button"
              onClick={() => setCurrentView('login')}
              className="text-blue-600 hover:text-blue-500"
            >
              Already have an account? Sign in
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  const renderLogMeal = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="mr-4 flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">Log Meal</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700">Welcome, {user?.full_name || user?.username}</span>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-md mx-auto">
          <div className="card">
            <h2 className="text-xl font-bold mb-6 text-center">Log Your Meal</h2>
            
            <form onSubmit={handleLogMeal} className="space-y-4">
              <div>
                <label className="form-label">Food Item</label>
                <select
                  required
                  className="form-input"
                  value={mealLogForm.food_item_id}
                  onChange={(e) => setMealLogForm({...mealLogForm, food_item_id: e.target.value})}
                >
                  <option value="">Select a food item</option>
                  {foodItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.calories} cal)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="form-label">Meal Type</label>
                <select
                  required
                  className="form-input"
                  value={mealLogForm.meal_type}
                  onChange={(e) => setMealLogForm({...mealLogForm, meal_type: e.target.value})}
                >
                  <option value="breakfast">Breakfast</option>
                  <option value="lunch">Lunch</option>
                  <option value="dinner">Dinner</option>
                  <option value="snack">Snack</option>
                </select>
              </div>

              <div>
                <label className="form-label">Quantity (servings)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  required
                  className="form-input"
                  value={mealLogForm.quantity}
                  onChange={(e) => setMealLogForm({...mealLogForm, quantity: parseFloat(e.target.value)})}
                />
              </div>

              {error && (
                <div className="text-red-600 text-sm text-center">{error}</div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="btn btn-primary w-full"
              >
                {isLoading ? 'Logging Meal...' : 'Log Meal'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );

  const renderSetGoals = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="mr-4 flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">Set Goals</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700">Welcome, {user?.full_name || user?.username}</span>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* Create New Goal Form */}
            <div className="card">
              <h2 className="text-xl font-bold mb-6 text-center">Create New Goal</h2>
              
              <form onSubmit={handleCreateGoal} className="space-y-4">
                <div>
                  <label className="form-label">Goal Type</label>
                  <select
                    required
                    className="form-input"
                    value={goalForm.goal_type}
                    onChange={(e) => setGoalForm({...goalForm, goal_type: e.target.value})}
                  >
                    <option value="weight_loss">Weight Loss</option>
                    <option value="weight_gain">Weight Gain</option>
                    <option value="muscle_gain">Muscle Gain</option>
                    <option value="maintenance">Maintenance</option>
                    <option value="calorie_target">Calorie Target</option>
                    <option value="macro_target">Macro Targets</option>
                  </select>
                </div>

                <div>
                  <label className="form-label">Target Weight (kg)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    className="form-input"
                    value={goalForm.target_weight}
                    onChange={(e) => setGoalForm({...goalForm, target_weight: e.target.value})}
                    placeholder="e.g., 70.5"
                  />
                </div>

                <div>
                  <label className="form-label">Target Calories (per day)</label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    className="form-input"
                    value={goalForm.target_calories}
                    onChange={(e) => setGoalForm({...goalForm, target_calories: e.target.value})}
                    placeholder="e.g., 2000"
                  />
                </div>

                <div>
                  <label className="form-label">Target Protein (g per day)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    className="form-input"
                    value={goalForm.target_protein}
                    onChange={(e) => setGoalForm({...goalForm, target_protein: e.target.value})}
                    placeholder="e.g., 150"
                  />
                </div>

                <div>
                  <label className="form-label">Target Carbs (g per day)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    className="form-input"
                    value={goalForm.target_carbs}
                    onChange={(e) => setGoalForm({...goalForm, target_carbs: e.target.value})}
                    placeholder="e.g., 250"
                  />
                </div>

                <div>
                  <label className="form-label">Target Fat (g per day)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    className="form-input"
                    value={goalForm.target_fat}
                    onChange={(e) => setGoalForm({...goalForm, target_fat: e.target.value})}
                    placeholder="e.g., 65"
                  />
                </div>

                <div>
                  <label className="form-label">Target Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={goalForm.target_date}
                    onChange={(e) => setGoalForm({...goalForm, target_date: e.target.value})}
                  />
                </div>

                {error && (
                  <div className="text-red-600 text-sm text-center">{error}</div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="btn btn-primary w-full"
                >
                  {isLoading ? 'Creating Goal...' : 'Create Goal'}
                </button>
              </form>
            </div>

            {/* Current Goals */}
            <div className="card">
              <h2 className="text-xl font-bold mb-6 text-center">Your Goals</h2>
              
              {goals.length > 0 ? (
                <div className="space-y-4">
                  {goals.map((goal) => (
                    <div key={goal.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <h3 className="font-medium text-lg capitalize">
                          {goal.goal_type.replace('_', ' ')}
                        </h3>
                        <button
                          onClick={() => handleDeleteGoal(goal.id)}
                          className="text-red-600 hover:text-red-800 text-sm"
                        >
                          Delete
                        </button>
                      </div>
                      
                      <div className="text-sm text-gray-600 space-y-1">
                        {goal.target_weight && (
                          <div>Target Weight: {goal.target_weight} kg</div>
                        )}
                        {goal.target_calories && (
                          <div>Target Calories: {goal.target_calories} cal/day</div>
                        )}
                        {goal.target_protein && (
                          <div>Target Protein: {goal.target_protein}g/day</div>
                        )}
                        {goal.target_carbs && (
                          <div>Target Carbs: {goal.target_carbs}g/day</div>
                        )}
                        {goal.target_fat && (
                          <div>Target Fat: {goal.target_fat}g/day</div>
                        )}
                        {goal.target_date && (
                          <div>Target Date: {new Date(goal.target_date).toLocaleDateString()}</div>
                        )}
                        <div className="text-xs text-gray-500 mt-2">
                          Created: {new Date(goal.created_at).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-500">
                  <p>No goals set yet.</p>
                  <p className="text-sm mt-2">Create your first goal using the form on the left!</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderViewProgress = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="mr-4 flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">View Progress</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700">Welcome, {user?.full_name || user?.username}</span>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          
          {/* Today's Stats */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-6">Today's Nutrition</h2>
            {progressData.dailyStats ? (
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <div className="card text-center">
                  <div className="text-3xl font-bold text-blue-600">
                    {progressData.dailyStats.total_calories.toFixed(0)}
                  </div>
                  <div className="text-sm text-gray-600">Calories</div>
                </div>
                <div className="card text-center">
                  <div className="text-3xl font-bold text-green-600">
                    {progressData.dailyStats.total_protein.toFixed(1)}g
                  </div>
                  <div className="text-sm text-gray-600">Protein</div>
                </div>
                <div className="card text-center">
                  <div className="text-3xl font-bold text-orange-600">
                    {progressData.dailyStats.total_carbs.toFixed(1)}g
                  </div>
                  <div className="text-sm text-gray-600">Carbs</div>
                </div>
                <div className="card text-center">
                  <div className="text-3xl font-bold text-purple-600">
                    {progressData.dailyStats.total_fat.toFixed(1)}g
                  </div>
                  <div className="text-sm text-gray-600">Fat</div>
                </div>
                <div className="card text-center">
                  <div className="text-3xl font-bold text-indigo-600">
                    {progressData.dailyStats.meal_count}
                  </div>
                  <div className="text-sm text-gray-600">Meals</div>
                </div>
              </div>
            ) : (
              <div className="card text-center">
                <p className="text-gray-500">No data for today yet. Log some meals to see your progress!</p>
              </div>
            )}
          </div>

          {/* Weekly Overview */}
          {progressData.weeklyStats && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-6">Weekly Overview</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                
                {/* Weekly Averages */}
                <div className="card">
                  <h3 className="text-lg font-bold mb-4">Weekly Averages</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span>Daily Calories:</span>
                      <span className="font-bold">{progressData.weeklyStats.weekly_averages.calories.toFixed(0)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Daily Protein:</span>
                      <span className="font-bold">{progressData.weeklyStats.weekly_averages.protein.toFixed(1)}g</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Daily Carbs:</span>
                      <span className="font-bold">{progressData.weeklyStats.weekly_averages.carbs.toFixed(1)}g</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Daily Fat:</span>
                      <span className="font-bold">{progressData.weeklyStats.weekly_averages.fat.toFixed(1)}g</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Daily Meals:</span>
                      <span className="font-bold">{progressData.weeklyStats.weekly_averages.meals.toFixed(1)}</span>
                    </div>
                  </div>
                </div>

                {/* Daily Breakdown */}
                <div className="card">
                  <h3 className="text-lg font-bold mb-4">Daily Breakdown</h3>
                  <div className="space-y-2">
                    {progressData.weeklyStats.daily_stats.map((day, index) => (
                      <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                        <span className="text-sm">
                          {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                        </span>
                        <span className="text-sm font-medium">
                          {day.total_calories.toFixed(0)} cal, {day.meal_count} meals
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Progress Summary */}
          {progressData.progressSummary && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-6">30-Day Progress Summary</h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="card text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {progressData.progressSummary.days_logged}
                  </div>
                  <div className="text-sm text-gray-600">Days Logged</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {progressData.progressSummary.total_meals}
                  </div>
                  <div className="text-sm text-gray-600">Total Meals</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-orange-600">
                    {progressData.progressSummary.daily_averages.calories.toFixed(0)}
                  </div>
                  <div className="text-sm text-gray-600">Avg Daily Calories</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {progressData.progressSummary.daily_averages.protein.toFixed(1)}g
                  </div>
                  <div className="text-sm text-gray-600">Avg Daily Protein</div>
                </div>
              </div>
            </div>
          )}

          {/* Goals vs Progress */}
          {goals.length > 0 && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-6">Goals vs Progress</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {goals.map((goal) => (
                  <div key={goal.id} className="card">
                    <h3 className="font-bold mb-2 capitalize">
                      {goal.goal_type.replace('_', ' ')}
                    </h3>
                    <div className="space-y-2 text-sm">
                      {goal.target_calories && progressData.dailyStats && (
                        <div className="flex justify-between">
                          <span>Calories:</span>
                          <span className={progressData.dailyStats.total_calories >= goal.target_calories * 0.9 ? 'text-green-600' : 'text-orange-600'}>
                            {progressData.dailyStats.total_calories.toFixed(0)} / {goal.target_calories}
                          </span>
                        </div>
                      )}
                      {goal.target_protein && progressData.dailyStats && (
                        <div className="flex justify-between">
                          <span>Protein:</span>
                          <span className={progressData.dailyStats.total_protein >= goal.target_protein * 0.9 ? 'text-green-600' : 'text-orange-600'}>
                            {progressData.dailyStats.total_protein.toFixed(1)}g / {goal.target_protein}g
                          </span>
                        </div>
                      )}
                      {goal.target_carbs && progressData.dailyStats && (
                        <div className="flex justify-between">
                          <span>Carbs:</span>
                          <span className={progressData.dailyStats.total_carbs >= goal.target_carbs * 0.9 ? 'text-green-600' : 'text-orange-600'}>
                            {progressData.dailyStats.total_carbs.toFixed(1)}g / {goal.target_carbs}g
                          </span>
                        </div>
                      )}
                      {goal.target_fat && progressData.dailyStats && (
                        <div className="flex justify-between">
                          <span>Fat:</span>
                          <span className={progressData.dailyStats.total_fat >= goal.target_fat * 0.9 ? 'text-green-600' : 'text-orange-600'}>
                            {progressData.dailyStats.total_fat.toFixed(1)}g / {goal.target_fat}g
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Refresh Button */}
          <div className="text-center">
            <button
              onClick={fetchProgressData}
              className="btn btn-primary"
            >
              Refresh Progress Data
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderChallenges = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="mr-4 flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">Challenges & Achievements</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700">Welcome, {user?.full_name || user?.username}</span>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          
          {/* User Stats Summary */}
          {userStats && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-6">Your Stats</h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="card text-center">
                  <div className="text-3xl font-bold text-blue-600">
                    {userStats.total_points || 0}
                  </div>
                  <div className="text-sm text-gray-600">Total Points</div>
                </div>
                <div className="card text-center">
                  <div className="text-3xl font-bold text-green-600">
                    {userStats.current_streak || 0}
                  </div>
                  <div className="text-sm text-gray-600">Current Streak</div>
                </div>
                <div className="card text-center">
                  <div className="text-3xl font-bold text-purple-600">
                    {userStats.achievements?.length || 0}
                  </div>
                  <div className="text-sm text-gray-600">Achievements</div>
                </div>
                <div className="card text-center">
                  <div className="text-3xl font-bold text-orange-600">
                    {challenges.filter(c => c.is_active).length}
                  </div>
                  <div className="text-sm text-gray-600">Active Challenges</div>
                </div>
              </div>
            </div>
          )}

          {/* Active Challenges */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-6">Active Challenges</h2>
            {challenges.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {challenges.map((challenge) => (
                  <div key={challenge.id} className="card">
                    <div className="flex justify-between items-start mb-4">
                      <h3 className="text-lg font-bold">{challenge.name}</h3>
                      <div className="flex items-center">
                        <Award className="text-yellow-500 mr-1" size={20} />
                        <span className="text-sm font-bold text-yellow-600">
                          {challenge.reward_points} pts
                        </span>
                      </div>
                    </div>
                    
                    <p className="text-gray-600 mb-4">{challenge.description}</p>
                    
                    {challenge.rules && Object.keys(challenge.rules).length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-bold text-gray-700 mb-2">Requirements:</h4>
                        <ul className="text-sm text-gray-600 space-y-1">
                          {Object.entries(challenge.rules).map(([key, value]) => (
                            <li key={key} className="flex justify-between">
                              <span className="capitalize">{key.replace('_', ' ')}:</span>
                              <span className="font-medium">{value}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    <div className="flex justify-between items-center text-xs text-gray-500">
                      <span>
                        Active: {challenge.active_from ? new Date(challenge.active_from).toLocaleDateString() : 'Always'}
                      </span>
                      {challenge.active_to && (
                        <span>
                          Until: {new Date(challenge.active_to).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    
                    <div className="mt-4">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div className="bg-blue-600 h-2 rounded-full" style={{width: '0%'}}></div>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">Progress: 0%</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="card text-center">
                <p className="text-gray-500">No challenges available at the moment.</p>
              </div>
            )}
          </div>

          {/* User Achievements */}
          {userAchievements.length > 0 && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-6">Your Achievements</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {userAchievements.map((achievement) => (
                  <div key={achievement.id} className="card">
                    <div className="flex items-center mb-3">
                      <Award className="text-yellow-500 mr-3" size={24} />
                      <div>
                        <h3 className="font-bold">{achievement.name}</h3>
                        <p className="text-sm text-gray-600">
                          {new Date(achievement.earned_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <p className="text-sm text-gray-700">{achievement.description}</p>
                    <div className="mt-3 text-sm">
                      <span className="font-bold text-green-600">+{achievement.points_earned} points</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Refresh Button */}
          <div className="text-center">
            <button
              onClick={fetchChallengesData}
              className="btn btn-primary"
            >
              Refresh Challenges Data
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderMLRecommendations = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="mr-4 flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">AI Recommendations</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700">Welcome, {user?.full_name || user?.username}</span>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          
          {/* Food Recommendations */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-6 flex items-center">
              <Brain className="mr-2" />
              Personalized Food Recommendations
            </h2>
            {mlRecommendations?.foodRecommendations?.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {mlRecommendations?.foodRecommendations?.map((food, index) => (
                  <div key={index} className="card">
                    <h3 className="font-bold text-lg mb-2">{food.name}</h3>
                    <div className="text-sm text-gray-600 mb-2">
                      {food.cuisine_type} • {food.calories} cal
                    </div>
                    <div className="text-sm text-gray-700 mb-3">
                      {food.reason}
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">
                        Score: {(food.recommendation_score * 100).toFixed(0)}%
                      </span>
                      <button className="btn btn-primary btn-sm">
                        Add to Plan
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="card text-center">
                <p className="text-gray-500">Loading recommendations...</p>
              </div>
            )}
          </div>

          {/* Cuisine Recommendations */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-6 flex items-center">
              <ChefHat className="mr-2" />
              Cuisine Suggestions
            </h2>
            {mlRecommendations?.cuisineRecommendations?.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {mlRecommendations?.cuisineRecommendations?.map((cuisine, index) => (
                  <div key={index} className="card">
                    <h3 className="font-bold text-lg mb-2 capitalize">{cuisine.cuisine}</h3>
                    <p className="text-gray-600 mb-2">{cuisine.reason}</p>
                    <span className={`px-2 py-1 rounded text-xs ${
                      cuisine.priority === 'high' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                    }`}>
                      {cuisine.priority} priority
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="card text-center">
                <p className="text-gray-500">No cuisine suggestions available</p>
              </div>
            )}
          </div>

          {/* Variety Suggestions */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-6 flex items-center">
              <Lightbulb className="mr-2" />
              Variety Improvement Tips
            </h2>
            {mlRecommendations?.varietySuggestions?.length > 0 ? (
              <div className="card">
                <ul className="space-y-2">
                  {mlRecommendations?.varietySuggestions?.map((suggestion, index) => (
                    <li key={index} className="flex items-start">
                      <span className="text-blue-500 mr-2">•</span>
                      <span>{suggestion}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="card text-center">
                <p className="text-gray-500">No variety suggestions available</p>
              </div>
            )}
          </div>

          {/* Refresh Button */}
          <div className="text-center">
            <button
              onClick={fetchMLRecommendations}
              className="btn btn-primary"
            >
              Refresh Recommendations
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderAdvancedPlanning = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="mr-4 flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">Advanced Meal Planning</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700">Welcome, {user?.full_name || user?.username}</span>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          
          {/* Planning Form */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-6 flex items-center">
              <Calendar className="mr-2" />
              Generate Advanced Meal Plan
            </h2>
            <div className="card">
              <form onSubmit={(e) => { e.preventDefault(); generateAdvancedPlan(); }} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="form-label">Target Calories (per day)</label>
                    <input
                      type="number"
                      className="form-input"
                      value={planningForm.target_calories}
                      onChange={(e) => setPlanningForm({...planningForm, target_calories: e.target.value})}
                      placeholder="e.g., 2000"
                    />
                  </div>
                  <div>
                    <label className="form-label">Meals per Day</label>
                    <select
                      className="form-input"
                      value={planningForm.meals_per_day}
                      onChange={(e) => setPlanningForm({...planningForm, meals_per_day: parseInt(e.target.value)})}
                    >
                      <option value={3}>3 meals</option>
                      <option value={4}>4 meals</option>
                      <option value={5}>5 meals</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="form-label">Protein %</label>
                    <input
                      type="number"
                      min="10"
                      max="50"
                      className="form-input"
                      value={planningForm.protein_percentage}
                      onChange={(e) => setPlanningForm({...planningForm, protein_percentage: parseInt(e.target.value)})}
                    />
                  </div>
                  <div>
                    <label className="form-label">Carbs %</label>
                    <input
                      type="number"
                      min="20"
                      max="70"
                      className="form-input"
                      value={planningForm.carb_percentage}
                      onChange={(e) => setPlanningForm({...planningForm, carb_percentage: parseInt(e.target.value)})}
                    />
                  </div>
                  <div>
                    <label className="form-label">Fat %</label>
                    <input
                      type="number"
                      min="10"
                      max="40"
                      className="form-input"
                      value={planningForm.fat_percentage}
                      onChange={(e) => setPlanningForm({...planningForm, fat_percentage: parseInt(e.target.value)})}
                    />
                  </div>
                </div>

                <div>
                  <label className="form-label">Cuisine Type</label>
                  <select
                    className="form-input"
                    value={planningForm.cuisine_type}
                    onChange={(e) => setPlanningForm({...planningForm, cuisine_type: e.target.value})}
                  >
                    <option value="mixed">Mixed</option>
                    <option value="indian">Indian</option>
                    <option value="chinese">Chinese</option>
                    <option value="mediterranean">Mediterranean</option>
                    <option value="mexican">Mexican</option>
                  </select>
                </div>

                {error && (
                  <div className="text-red-600 text-sm text-center">{error}</div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="btn btn-primary w-full"
                >
                  {isLoading ? 'Generating Plan...' : 'Generate Advanced Meal Plan'}
                </button>
              </form>
            </div>
          </div>

          {/* Generated Plan */}
          {advancedPlan && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-6 flex items-center">
                <BarChart3 className="mr-2" />
                Your Advanced Meal Plan
              </h2>
              
              {/* Plan Summary */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <div className="card text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {advancedPlan.total_weekly_calories.toFixed(0)}
                  </div>
                  <div className="text-sm text-gray-600">Weekly Calories</div>
                </div>
                <div className="text-2xl font-bold text-green-600">
                  {advancedPlan.total_weekly_protein.toFixed(0)}g
                </div>
                <div className="text-sm text-gray-600">Weekly Protein</div>
                <div className="text-2xl font-bold text-purple-600">
                  {(advancedPlan.variety_score * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-gray-600">Variety Score</div>
                <div className="text-2xl font-bold text-orange-600">
                  {(advancedPlan.macro_balance_score * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-gray-600">Macro Balance</div>
              </div>

              {/* Week Plan */}
              <div className="space-y-6">
                {advancedPlan.week_plans.map((day, dayIndex) => (
                  <div key={dayIndex} className="card">
                    <h3 className="text-lg font-bold mb-4">Day {day.day}</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {day.meals.map((meal, mealIndex) => (
                        <div key={mealIndex} className="border border-gray-200 rounded-lg p-4">
                          <h4 className="font-medium mb-2">
                            {mealIndex === 0 ? 'Breakfast' : mealIndex === 1 ? 'Lunch' : 'Dinner'}
                          </h4>
                          <div className="space-y-2">
                            {meal.items.map((item, itemIndex) => (
                              <div key={itemIndex} className="text-sm">
                                <div className="font-medium">{item.name}</div>
                                <div className="text-gray-600">
                                  {item.calories.toFixed(0)} cal • {item.quantity}x
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="mt-2 text-xs text-gray-500">
                            Total: {meal.total_calories.toFixed(0)} cal, {meal.total_protein.toFixed(1)}g protein
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 text-sm text-gray-600">
                      Day Total: {day.total_calories.toFixed(0)} calories, {day.total_protein.toFixed(1)}g protein
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderDashboard = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              {activeView !== 'dashboard' && (
                <button
                  onClick={() => setActiveView('dashboard')}
                  className="mr-4 flex items-center text-gray-600 hover:text-gray-900"
                >
                  <ArrowLeft size={20} className="mr-2" />
                  Back to Dashboard
                </button>
              )}
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="md:hidden mr-4"
              >
                {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
              <h1 className="text-2xl font-bold text-gray-900">Nutrition App</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700">Welcome, {user?.full_name || user?.username}</span>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Daily Stats */}
          <div className="card">
            <h3 className="text-lg font-bold mb-4 flex items-center">
              <TrendingUp className="mr-2" />
              Today's Nutrition
            </h3>
            {dashboardData.dailyStats ? (
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>Calories:</span>
                  <span className="font-bold">{dashboardData.dailyStats.total_calories.toFixed(0)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Protein:</span>
                  <span className="font-bold">{dashboardData.dailyStats.total_protein.toFixed(1)}g</span>
                </div>
                <div className="flex justify-between">
                  <span>Carbs:</span>
                  <span className="font-bold">{dashboardData.dailyStats.total_carbs.toFixed(1)}g</span>
                </div>
                <div className="flex justify-between">
                  <span>Fat:</span>
                  <span className="font-bold">{dashboardData.dailyStats.total_fat.toFixed(1)}g</span>
                </div>
                <div className="flex justify-between">
                  <span>Meals:</span>
                  <span className="font-bold">{dashboardData.dailyStats.meal_count}</span>
                </div>
              </div>
            ) : (
              <p className="text-gray-500">No data for today</p>
            )}
          </div>

          {/* Recent Meals */}
          <div className="card">
            <h3 className="text-lg font-bold mb-4 flex items-center">
              <Utensils className="mr-2" />
              Recent Meals
            </h3>
            {dashboardData.recentMeals.length > 0 ? (
              <div className="space-y-2">
                {dashboardData.recentMeals.slice(0, 3).map((meal, index) => (
                  <div key={index} className="flex justify-between text-sm">
                    <span>{meal.food_item.name}</span>
                    <span>{meal.calories.toFixed(0)} cal</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500">No recent meals</p>
            )}
          </div>

          {/* Challenges */}
          <div className="card">
            <h3 className="text-lg font-bold mb-4 flex items-center">
              <Award className="mr-2" />
              Active Challenges
            </h3>
            {dashboardData.challenges.length > 0 ? (
              <div className="space-y-2">
                {dashboardData.challenges.slice(0, 3).map((challenge, index) => (
                  <div key={index} className="text-sm">
                    <div className="font-medium">{challenge.name}</div>
                    <div className="text-gray-500">{challenge.description}</div>
                    <div className="text-green-600 font-bold">{challenge.reward_points} points</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500">No active challenges</p>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-8">
          <h2 className="text-xl font-bold mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('log-meal')}
            >
              <div className="text-center">
                <Utensils className="mx-auto mb-2" size={32} />
                <div className="font-medium">Log Meal</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('set-goals')}
            >
              <div className="text-center">
                <Target className="mx-auto mb-2" size={32} />
                <div className="font-medium">Set Goals</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('view-progress')}
            >
              <div className="text-center">
                <TrendingUp className="mx-auto mb-2" size={32} />
                <div className="font-medium">View Progress</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('challenges')}
            >
              <div className="text-center">
                <Award className="mx-auto mb-2" size={32} />
                <div className="font-medium">Challenges</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('ml-recommendations')}
            >
              <div className="text-center">
                <Brain className="mx-auto mb-2" size={32} />
                <div className="font-medium">AI Recommendations</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('advanced-planning')}
            >
              <div className="text-center">
                <Calendar className="mx-auto mb-2" size={32} />
                <div className="font-medium">Advanced Planning</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  if (currentView === 'login') {
    return renderLogin();
  } else if (currentView === 'register') {
    return renderRegister();
  } else if (user) {
    // Render different views based on activeView
    if (activeView === 'log-meal') {
      return renderLogMeal();
    } else if (activeView === 'set-goals') {
      return renderSetGoals();
    } else if (activeView === 'view-progress') {
      return renderViewProgress();
    } else if (activeView === 'challenges') {
      return renderChallenges();
    } else if (activeView === 'ml-recommendations') {
      return renderMLRecommendations();
    } else if (activeView === 'advanced-planning') {
      return renderAdvancedPlanning();
    } else {
      return renderDashboard();
    }
  }

  return null;
}

export default App;


