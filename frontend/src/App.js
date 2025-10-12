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
  BarChart3,
  Globe
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
    username: 'chatbotuser',
    password: 'testpass123'
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


  // AI Recipe Generator state
  const [aiRecipes, setAiRecipes] = useState([]);
  const [recipeForm, setRecipeForm] = useState({
    cuisine_preference: ['indian'],
    dietary_restrictions: [],
    available_ingredients: [],
    target_calories: 400,
    budget_limit: 200,
    meal_type: 'lunch',
    difficulty_level: 'easy',
    time_constraint: 60,
    health_conditions: [],
    serving_size: 2
  });
  const [generatedRecipe, setGeneratedRecipe] = useState(null);
  const [isGeneratingRecipe, setIsGeneratingRecipe] = useState(false);
  
  // ChefGenius state
  const [chefgeniusRecipe, setChefgeniusRecipe] = useState(null);
  const [isGeneratingChefgenius, setIsGeneratingChefgenius] = useState(false);
  const [chefgeniusForm, setChefgeniusForm] = useState({
    ingredients: [],
    dietary_restrictions: [],
    time_constraint: 60,
    meal_type: 'dinner'
  });

  // FitMentor state
  const [fitmentorPlan, setFitmentorPlan] = useState(null);
  const [isGeneratingFitmentor, setIsGeneratingFitmentor] = useState(false);
  const [fitmentorForm, setFitmentorForm] = useState({
    activity_level: 'beginner',
    fitness_goal: 'general_fitness',
    time_per_day: 30,
    equipment: 'none',
    constraints: [],
    age: null,
    weight: null
  });
  const [adaptationForm, setAdaptationForm] = useState({
    current_plan: '',
    feedback: '',
    progress_notes: ''
  });

  // BudgetChef state
  const [budgetchefPlan, setBudgetchefPlan] = useState(null);
  const [isGeneratingBudgetchef, setIsGeneratingBudgetchef] = useState(false);
  const [budgetchefForm, setBudgetchefForm] = useState({
    budget_per_day: 300,
    calorie_target: null,
    dietary_preferences: [],
    meals_per_day: 3,
    cooking_time: 'moderate',
    skill_level: 'intermediate',
    age: null,
    weight: null,
    activity_level: 'moderate'
  });
  const [budgetAdaptationForm, setBudgetAdaptationForm] = useState({
    current_plan: '',
    feedback: '',
    new_budget: null,
    new_calorie_target: null
  });

  // CulinaryExplorer state
  const [culinaryexplorerPlan, setCulinaryexplorerPlan] = useState(null);
  const [isGeneratingCulinaryexplorer, setIsGeneratingCulinaryexplorer] = useState(false);
  const [culinaryexplorerForm, setCulinaryexplorerForm] = useState({
    cuisine_region: 'indian',
    meal_type: 'full_day',
    dietary_restrictions: [],
    time_constraint: 60,
    cooking_skill: 'intermediate',
    available_ingredients: []
  });
  const [culinaryAdaptationForm, setCulinaryAdaptationForm] = useState({
    current_plan: '',
    feedback: '',
    new_cuisine_preference: null,
    new_dietary_restrictions: null
  });
  
  // Ingredient search states
  const [ingredientSearchQuery, setIngredientSearchQuery] = useState('');
  const [showIngredientDropdown, setShowIngredientDropdown] = useState(false);
  const [filteredIngredients, setFilteredIngredients] = useState([]);
  const [selectedIngredients, setSelectedIngredients] = useState([]);

  // Meal logging state
  const [foodItems, setFoodItems] = useState([]);
  
  // Food search states (legacy - keeping for compatibility)
  const [foodSearchQuery, setFoodSearchQuery] = useState('');
  const [showFoodDropdown, setShowFoodDropdown] = useState(false);
  const [filteredFoodItems, setFilteredFoodItems] = useState([]);
  const [mealLogForm, setMealLogForm] = useState({
    food_item_id: '',
    meal_type: 'breakfast',
    quantity: 1.0
  });

  // Quick Meal Log Modal (for ML Recommendations)
  const [showQuickLogModal, setShowQuickLogModal] = useState(false);
  const [selectedRecommendation, setSelectedRecommendation] = useState(null);
  const [quickLogForm, setQuickLogForm] = useState({
    meal_type: 'lunch',
    quantity: 1.0
  });

  // NutrientAnalyzer state
  const [nutrientAnalysis, setNutrientAnalysis] = useState(null);
  const [isAnalyzingNutrition, setIsAnalyzingNutrition] = useState(false);
  const [nutrientForm, setNutrientForm] = useState({
    food_name: '',
    serving_size: '',
    meal_type: 'lunch'
  });
  const [showNutrientAnalysis, setShowNutrientAnalysis] = useState(false);

  // AdvancedMealPlanner state
  const [advancedMealPlan, setAdvancedMealPlan] = useState(null);
  const [isGeneratingAdvancedPlan, setIsGeneratingAdvancedPlan] = useState(false);
  const [advancedPlanForm, setAdvancedPlanForm] = useState({
    target_calories: 2000,
    meals_per_day: 3,
    food_preferences: [],
    budget_per_day: 300.0,
    work_hours_per_day: 8,
    dietary_restrictions: [],
    equipment: ['stove'],
    time_per_meal_min: 30,
    region_or_cuisine: '',
    user_notes: ''
  });
  const [advancedPlanAdaptationForm, setAdvancedPlanAdaptationForm] = useState({
    current_plan: '',
    feedback: '',
    new_requirements: {}
  });

  // Chatbot state
  const [chatbotMessages, setChatbotMessages] = useState([]);
  const [chatbotInput, setChatbotInput] = useState('');
  const [isChatbotLoading, setIsChatbotLoading] = useState(false);
  const [availableAgents, setAvailableAgents] = useState([]);

  // Enhanced Challenges state
  const [enhancedChallenges, setEnhancedChallenges] = useState([]);
  const [challengeRecommendations, setChallengeRecommendations] = useState([]);
  const [challengeAnalytics, setChallengeAnalytics] = useState(null);
  const [isGeneratingChallenges, setIsGeneratingChallenges] = useState(false);

  // Chatbot functions
  const fetchAvailableAgents = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/chatbot/agents`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const agents = await response.json();
        setAvailableAgents(agents);
      }
    } catch (error) {
      console.error('Error fetching agents:', error);
    }
  };

  const sendChatbotMessage = async () => {
    if (!chatbotInput.trim() || isChatbotLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: chatbotInput.trim(),
      timestamp: new Date()
    };

    setChatbotMessages(prev => [...prev, userMessage]);
    setChatbotInput('');
    setIsChatbotLoading(true);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/chatbot/chat/simple`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: userMessage.content
        })
      });

      if (response.ok) {
        const data = await response.json();
        let formattedResponse = data.response || 'Sorry, I couldn\'t process your request.';
        
        // Format the response if it's a string representation of a dict
        if (typeof formattedResponse === 'string' && formattedResponse.startsWith('{')) {
          try {
            const parsedResponse = JSON.parse(formattedResponse);
            if (parsedResponse.recipe) {
              formattedResponse = parsedResponse.recipe;
            } else if (parsedResponse.success && parsedResponse.data) {
              formattedResponse = parsedResponse.data;
            }
          } catch (e) {
            // Keep original response if parsing fails
          }
        }
        
        const botMessage = {
          id: Date.now() + 1,
          type: 'bot',
          content: formattedResponse,
          timestamp: new Date()
        };
        setChatbotMessages(prev => [...prev, botMessage]);
      } else {
        const errorMessage = {
          id: Date.now() + 1,
          type: 'bot',
          content: 'Sorry, I encountered an error. Please try again.',
          timestamp: new Date()
        };
        setChatbotMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: 'Sorry, I\'m having trouble connecting. Please try again.',
        timestamp: new Date()
      };
      setChatbotMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsChatbotLoading(false);
    }
  };

  const clearChatbotHistory = () => {
    setChatbotMessages([]);
  };

  // Enhanced Challenges functions
  const generateWeeklyChallenges = async () => {
    try {
      setIsGeneratingChallenges(true);
      const token = localStorage.getItem('token');
      
      const response = await fetch(`${API_BASE_URL}/enhanced-challenges/generate-weekly-challenges`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setEnhancedChallenges(data.active_challenges || []);
        setChallengeRecommendations(data.recommendations || []);
        setError('');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to generate challenges');
      }
    } catch (err) {
      setError('Error generating challenges: ' + err.message);
    } finally {
      setIsGeneratingChallenges(false);
    }
  };

  const fetchActiveChallenges = async () => {
    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch(`${API_BASE_URL}/enhanced-challenges/active-challenges`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setEnhancedChallenges(data.active_challenges || []);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to fetch challenges');
      }
    } catch (err) {
      setError('Error fetching challenges: ' + err.message);
    }
  };

  const updateChallengeProgress = async (challengeId, dailyValue) => {
    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch(`${API_BASE_URL}/enhanced-challenges/update-challenge-progress`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          challenge_id: challengeId,
          daily_value: dailyValue
        })
      });

      if (response.ok) {
        const data = await response.json();
        // Refresh challenges to show updated progress
        await fetchActiveChallenges();
        setError(''); // Clear any previous errors
        // Show success message
        alert(`Progress updated! You've completed ${data.completion_percentage.toFixed(1)}% of your challenge.`);
        return data;
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to update progress');
      }
    } catch (err) {
      setError('Error updating progress: ' + err.message);
    }
  };

  const fetchChallengeAnalytics = async () => {
    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch(`${API_BASE_URL}/enhanced-challenges/challenge-analytics`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setChallengeAnalytics(data.analytics);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to fetch analytics');
      }
    } catch (err) {
      setError('Error fetching analytics: ' + err.message);
    }
  };

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
      // Load dashboard data including Smart Challenges
      loadDashboardData();
    }
  }, []);

  useEffect(() => {
    // Fetch food items when log-meal view is active
    if (activeView === 'log-meal' && foodItems.length === 0) {
      fetchFoodItems();
    }
  }, [activeView, foodItems.length]);

  // Handle food search
  useEffect(() => {
    if (foodSearchQuery.length >= 2) {
      searchFoodItems(foodSearchQuery);
    } else {
      setFilteredFoodItems([]);
    }
  }, [foodSearchQuery]);

  // Handle ingredient search
  useEffect(() => {
    if (ingredientSearchQuery.length >= 2) {
      searchIngredients(ingredientSearchQuery);
    } else {
      setFilteredIngredients([]);
    }
  }, [ingredientSearchQuery]);

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
    // Fetch ML recommendations when ml-recommendations view is active
    if (activeView === 'ml-recommendations') {
      fetchMLRecommendations();
    }
  }, [activeView]);

  useEffect(() => {
    // Fetch AI recipes when ai-recipes view is active
    if (activeView === 'ai-recipes') {
      fetchAIRecipes();
    }
    // Fetch FitMentor data when fitmentor view is active
    if (activeView === 'fitmentor') {
      // FitMentor doesn't need to fetch existing data, it generates on demand
    }
    // Fetch chatbot agents when chatbot view is active
    if (activeView === 'chatbot') {
      fetchAvailableAgents();
    }
    // Fetch enhanced challenges when enhanced-challenges view is active
    if (activeView === 'enhanced-challenges') {
      fetchActiveChallenges();
      fetchChallengeAnalytics();
    }
    // Fetch BudgetChef data when budgetchef view is active
    if (activeView === 'budgetchef') {
      // BudgetChef doesn't need to fetch existing data, it generates on demand
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

      // Fetch Smart Challenges
      const challengesResponse = await fetch(`${API_BASE_URL}/enhanced-challenges/active-challenges`, { headers });
      if (challengesResponse.ok) {
        const challengesData = await challengesResponse.json();
        setEnhancedChallenges(challengesData.active_challenges || []);
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
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Login failed';
        setError(errorMessage);
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
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Registration failed';
        setError(errorMessage);
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

  const searchFoodItems = async (query) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/meals/food-items/search?q=${encodeURIComponent(query)}&limit=20`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        // Ensure data is an array and filter out invalid items
        if (Array.isArray(data)) {
          const validItems = data.filter(item => 
            item && 
            typeof item === 'object' && 
            item.id && 
            item.name
          );
          setFilteredFoodItems(validItems);
        } else {
          setFilteredFoodItems([]);
        }
      } else {
        setFilteredFoodItems([]);
      }
    } catch (error) {
      console.error('Error searching food items:', error);
      setFilteredFoodItems([]);
    }
  };

  const searchIngredients = async (query) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/v1/recipes/ingredients/search?q=${encodeURIComponent(query)}&limit=20`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        // Handle the new API response format
        if (data.success && data.data && Array.isArray(data.data.ingredients)) {
          const validItems = data.data.ingredients.filter(item => 
            item && 
            typeof item === 'object' && 
            item.id && 
            item.name
          );
          setFilteredIngredients(validItems);
        } else {
          setFilteredIngredients([]);
        }
      } else {
        setFilteredIngredients([]);
      }
    } catch (error) {
      console.error('Error searching ingredients:', error);
      setFilteredIngredients([]);
    }
  };

  const addIngredient = (ingredient) => {
    // Check if ingredient is already selected
    if (!selectedIngredients.find(item => item.id === ingredient.id)) {
      setSelectedIngredients([...selectedIngredients, ingredient]);
      setRecipeForm({
        ...recipeForm,
        available_ingredients: [...recipeForm.available_ingredients, ingredient.name]
      });
    }
    setIngredientSearchQuery('');
    setShowIngredientDropdown(false);
  };

  const removeIngredient = (ingredientId) => {
    const ingredient = selectedIngredients.find(item => item.id === ingredientId);
    if (ingredient) {
      setSelectedIngredients(selectedIngredients.filter(item => item.id !== ingredientId));
      setRecipeForm({
        ...recipeForm,
        available_ingredients: recipeForm.available_ingredients.filter(name => name !== ingredient.name)
      });
    }
  };

  const addIngredientToChefgenius = (ingredient) => {
    if (!chefgeniusForm.ingredients.includes(ingredient.name)) {
      setChefgeniusForm({
        ...chefgeniusForm,
        ingredients: [...chefgeniusForm.ingredients, ingredient.name]
      });
    }
    setIngredientSearchQuery('');
    setShowIngredientDropdown(false);
  };

  const removeIngredientFromChefgenius = (index) => {
    setChefgeniusForm({
      ...chefgeniusForm,
      ingredients: chefgeniusForm.ingredients.filter((_, i) => i !== index)
    });
  };

  // FitMentor functions
  const generateFitmentorPlan = async () => {
    if (!fitmentorForm.activity_level || !fitmentorForm.fitness_goal) {
      setError('Please fill in all required fields');
      return;
    }

    setIsGeneratingFitmentor(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/fitness/generate-workout-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(fitmentorForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setFitmentorPlan(data.data);
          // Pre-populate the adaptation form with the current plan
          setAdaptationForm(prev => ({
            ...prev,
            current_plan: data.data.workout_plan
          }));
          alert('FitMentor Workout Plan generated successfully!');
        } else {
          setError('Failed to generate workout plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to generate workout plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error generating FitMentor plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingFitmentor(false);
    }
  };

  const adaptFitmentorPlan = async () => {
    if (!adaptationForm.current_plan || !adaptationForm.feedback) {
      setError('Please provide current plan and feedback');
      return;
    }

    setIsGeneratingFitmentor(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/fitness/adapt-workout-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(adaptationForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          // Update the existing plan with the adapted version
          setFitmentorPlan(prevPlan => ({
            ...prevPlan,
            workout_plan: data.data.adapted_plan,
            feedback: data.data.feedback,
            progress_notes: data.data.progress_notes
          }));
          setAdaptationForm({ current_plan: '', feedback: '', progress_notes: '' });
          alert('Workout plan adapted successfully!');
        } else {
          setError('Failed to adapt workout plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to adapt workout plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error adapting FitMentor plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingFitmentor(false);
    }
  };

  // BudgetChef functions
  const generateBudgetchefPlan = async () => {
    if (!budgetchefForm.budget_per_day) {
      setError('Please enter your daily budget');
      return;
    }

    setIsGeneratingBudgetchef(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/budget/generate-meal-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(budgetchefForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setBudgetchefPlan(data.data);
          // Pre-populate the adaptation form with the current plan
          setBudgetAdaptationForm(prev => ({
            ...prev,
            current_plan: data.data.meal_plan
          }));
          alert('BudgetChef Meal Plan generated successfully!');
        } else {
          setError('Failed to generate budget meal plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to generate budget meal plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error generating BudgetChef plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingBudgetchef(false);
    }
  };

  const adaptBudgetchefPlan = async () => {
    if (!budgetAdaptationForm.current_plan || !budgetAdaptationForm.feedback) {
      setError('Please provide current plan and feedback');
      return;
    }

    setIsGeneratingBudgetchef(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/budget/adapt-meal-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(budgetAdaptationForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          // Update the existing plan with the adapted version
          setBudgetchefPlan(prevPlan => ({
            ...prevPlan,
            meal_plan: data.data.adapted_plan,
            feedback: data.data.feedback,
            new_budget: data.data.new_budget,
            new_calorie_target: data.data.new_calorie_target
          }));
          setBudgetAdaptationForm({ current_plan: '', feedback: '', new_budget: null, new_calorie_target: null });
          alert('Budget meal plan adapted successfully!');
        } else {
          setError('Failed to adapt budget meal plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to adapt budget meal plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error adapting BudgetChef plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingBudgetchef(false);
    }
  };

  const generateCulinaryexplorerPlan = async () => {
    if (!culinaryexplorerForm.cuisine_region) {
      setError('Please select a cuisine region');
      return;
    }

    setIsGeneratingCulinaryexplorer(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/culinary/generate-meal-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(culinaryexplorerForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setCulinaryexplorerPlan(data.data);
          // Pre-populate the adaptation form with the current plan
          setCulinaryAdaptationForm(prev => ({
            ...prev,
            current_plan: data.data.meal_plan
          }));
          alert('CulinaryExplorer Regional Meal Plan generated successfully!');
        } else {
          setError('Failed to generate regional meal plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to generate regional meal plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error generating CulinaryExplorer plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingCulinaryexplorer(false);
    }
  };

  const adaptCulinaryexplorerPlan = async () => {
    if (!culinaryAdaptationForm.current_plan || !culinaryAdaptationForm.feedback) {
      setError('Please provide current plan and feedback');
      return;
    }

    setIsGeneratingCulinaryexplorer(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/culinary/adapt-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(culinaryAdaptationForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          // Update the existing plan with the adapted version
          setCulinaryexplorerPlan(prevPlan => ({
            ...prevPlan,
            meal_plan: data.data.adapted_plan,
            feedback: data.data.feedback,
            new_cuisine_preference: data.data.new_cuisine_preference,
            new_dietary_restrictions: data.data.new_dietary_restrictions
          }));
          setCulinaryAdaptationForm({ current_plan: '', feedback: '', new_cuisine_preference: null, new_dietary_restrictions: null });
          alert('Regional meal plan adapted successfully!');
        } else {
          setError('Failed to adapt regional meal plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to adapt regional meal plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error adapting CulinaryExplorer plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingCulinaryexplorer(false);
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
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Failed to log meal';
        setError(errorMessage);
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const analyzeNutrition = async () => {
    if (!nutrientForm.food_name || !nutrientForm.serving_size) {
      setError('Please enter both food name and serving size');
      return;
    }

    setIsAnalyzingNutrition(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/nutrient/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify({
          food_name: nutrientForm.food_name,
          serving_size: nutrientForm.serving_size
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setNutrientAnalysis(data.data);
          setShowNutrientAnalysis(true);
          alert('Nutrition analysis completed!');
        } else {
          setError('Failed to analyze nutrition');
        }
      } else {
        const errorData = await response.json();
        let errorMessage = 'Failed to analyze nutrition';
        
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (errorData.detail && typeof errorData.detail === 'object') {
          if (errorData.detail.error_type === 'rate_limit') {
            errorMessage = 'AI service is temporarily unavailable due to high usage. Please try again in a few minutes.';
          } else {
            errorMessage = errorData.detail.error || JSON.stringify(errorData.detail);
          }
        } else {
          errorMessage = JSON.stringify(errorData.detail) || 'Failed to analyze nutrition';
        }
        
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error analyzing nutrition:', error);
      setError('Failed to connect to server');
    } finally {
      setIsAnalyzingNutrition(false);
    }
  };

  const logMealWithAnalysis = async () => {
    if (!nutrientForm.food_name || !nutrientForm.serving_size) {
      setError('Please enter both food name and serving size');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/nutrient/log-meal`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify({
          food_name: nutrientForm.food_name,
          serving_size: nutrientForm.serving_size,
          meal_type: nutrientForm.meal_type
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setNutrientAnalysis(data.data);
          setNutrientForm({ food_name: '', serving_size: '', meal_type: 'lunch' });
          setShowNutrientAnalysis(false);
          alert('Meal logged with nutrition analysis successfully!');
          // Refresh dashboard data
          loadDashboardData();
        } else {
          setError('Failed to log meal with analysis');
        }
      } else {
        const errorData = await response.json();
        let errorMessage = 'Failed to log meal';
        
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (errorData.detail && typeof errorData.detail === 'object') {
          if (errorData.detail.error_type === 'rate_limit') {
            errorMessage = 'AI service is temporarily unavailable due to high usage. Please try again in a few minutes.';
          } else {
            errorMessage = errorData.detail.error || JSON.stringify(errorData.detail);
          }
        } else {
          errorMessage = JSON.stringify(errorData.detail) || 'Failed to log meal';
        }
        
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error logging meal with analysis:', error);
      setError('Failed to connect to server');
    } finally {
      setIsLoading(false);
    }
  };

  // AdvancedMealPlanner functions
  const generateAdvancedMealPlan = async () => {
    if (!advancedPlanForm.target_calories || advancedPlanForm.target_calories < 100) {
      setError('Please enter a valid target calories (minimum 100)');
      return;
    }

    setIsGeneratingAdvancedPlan(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/advanced-meal-planner/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(advancedPlanForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setAdvancedMealPlan(data.data);
          alert('Advanced meal plan generated successfully!');
        } else {
          setError('Failed to generate advanced meal plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to generate advanced meal plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error generating advanced meal plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingAdvancedPlan(false);
    }
  };

  const adaptAdvancedMealPlan = async () => {
    if (!advancedPlanAdaptationForm.feedback.trim()) {
      setError('Please provide feedback on the current plan');
      return;
    }

    setIsGeneratingAdvancedPlan(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/advanced-meal-planner/adapt`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(advancedPlanAdaptationForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setAdvancedMealPlan(data.data);
          setAdvancedPlanAdaptationForm({
            current_plan: '',
            feedback: '',
            new_requirements: {}
          });
          alert('Advanced meal plan adapted successfully!');
        } else {
          setError('Failed to adapt advanced meal plan');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail) || 'Failed to adapt advanced meal plan';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error adapting advanced meal plan:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingAdvancedPlan(false);
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
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Failed to create goal';
        setError(errorMessage);
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
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Failed to delete goal';
        setError(errorMessage);
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
        const recommendations = data.recommendations;
        
        // Map snake_case API response to camelCase frontend state
        setMlRecommendations({
          foodRecommendations: recommendations.food_recommendations || [],
          cuisineRecommendations: recommendations.cuisine_recommendations || [],
          varietySuggestions: recommendations.variety_suggestions || [],
          macroAdjustments: recommendations.macro_adjustments || [],
          mealTimingSuggestions: recommendations.meal_timing_suggestions || {}
        });
      }
    } catch (error) {
      console.error('Error fetching ML recommendations:', error);
    }
  };

  // Quick Log Modal Functions
  const handleAddToPlan = (food) => {
    setSelectedRecommendation(food);
    
    // Set meal type based on current time
    const hour = new Date().getHours();
    let mealType = 'lunch';
    if (hour >= 6 && hour < 11) mealType = 'breakfast';
    else if (hour >= 11 && hour < 16) mealType = 'lunch';
    else if (hour >= 16 && hour < 22) mealType = 'dinner';
    else mealType = 'snack';
    
    setQuickLogForm({
      meal_type: mealType,
      quantity: 1.0
    });
    
    setShowQuickLogModal(true);
  };

  const handleQuickLogMeal = async () => {
    if (!selectedRecommendation) {
      console.error('No recommendation selected');
      alert('⚠️ No food selected. Please try again.');
      return;
    }

    console.log('=== Starting Quick Meal Log ===');
    console.log('Selected food:', {
      food_id: selectedRecommendation.food_id,
      food_name: selectedRecommendation.name,
      meal_type: quickLogForm.meal_type,
      quantity: quickLogForm.quantity
    });

    setIsLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      console.log('Token exists:', !!token);
      
      if (!token) {
        setError('Not authenticated. Please log in again.');
        setIsLoading(false);
        return;
      }

      const requestBody = {
        food_item_id: selectedRecommendation.food_id,
        meal_type: quickLogForm.meal_type,
        quantity: parseFloat(quickLogForm.quantity)
      };

      console.log('Making API call with body:', JSON.stringify(requestBody));
      console.log('API URL:', `${API_BASE_URL}/meals/log`);

      const response = await fetch(`${API_BASE_URL}/meals/log`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(requestBody)
      });

      console.log('Response received - Status:', response.status, response.statusText);

      if (response.ok) {
        const data = await response.json();
        console.log('✅ Meal logged successfully! Response data:', data);
        
        // Close modal and reset
        setShowQuickLogModal(false);
        setSelectedRecommendation(null);
        setError('');
        
        // Show success message
        const successMessage = `✅ Successfully logged ${selectedRecommendation.name} as ${quickLogForm.meal_type}!

Nutrition Added:
• Calories: ${(selectedRecommendation.calories * quickLogForm.quantity).toFixed(0)} cal
• Protein: ${(selectedRecommendation.protein_g * quickLogForm.quantity).toFixed(1)}g
• Carbs: ${(selectedRecommendation.carbs_g * quickLogForm.quantity).toFixed(1)}g`;
        
        alert(successMessage);
        
        // Refresh dashboard data to show the new meal
        console.log('Refreshing dashboard data...');
        await loadDashboardData();
        console.log('Dashboard refreshed!');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('❌ Error response:', errorData);
        setError(errorData.detail || `Failed to log meal (Status: ${response.status})`);
        alert(`❌ Failed to log meal: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('❌ Exception while logging meal:', error);
      console.error('Error stack:', error.stack);
      setError('Network error: ' + error.message);
      alert(`❌ Error logging meal: ${error.message}\n\nCheck console for details.`);
    } finally {
      setIsLoading(false);
      console.log('=== Quick Meal Log Complete ===');
    }
  };

  const closeQuickLogModal = () => {
    setShowQuickLogModal(false);
    setSelectedRecommendation(null);
    setError('');
  };



  const generateAIRecipe = async () => {
    setIsGeneratingRecipe(true);
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/v1/recipes/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(recipeForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setGeneratedRecipe(data.data);
          // Add to recipes list
          setAiRecipes(prev => [data.data, ...prev]);
          alert('AI Recipe generated successfully!');
        } else {
          setError('Failed to generate recipe');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Failed to generate recipe';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error generating AI recipe:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingRecipe(false);
    }
  };

  const generateChefgeniusRecipe = async () => {
    if (chefgeniusForm.ingredients.length === 0) {
      setError('Please add at least one ingredient');
      return;
    }

    setIsGeneratingChefgenius(true);
    setError('');
    
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/v1/recipes/generate-from-ingredients`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: JSON.stringify(chefgeniusForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setChefgeniusRecipe(data.data);
          alert('ChefGenius Recipe generated successfully!');
        } else {
          setError('Failed to generate recipe');
        }
      } else {
        const errorData = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Failed to generate recipe';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error generating ChefGenius recipe:', error);
      setError('Failed to connect to server');
    } finally {
      setIsGeneratingChefgenius(false);
    }
  };

  const fetchAIRecipes = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      const response = await fetch(`${API_BASE_URL}/ai-recipes/api/v1/recipes?limit=20`, { headers });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data && data.data.recipes) {
          setAiRecipes(data.data.recipes);
        }
      }
    } catch (error) {
      console.error('Error fetching AI recipes:', error);
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
              <h1 className="text-2xl font-bold text-gray-900">AI-Powered Meal Logging</h1>
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
          
          {/* AI-Powered Nutrition Analysis */}
          <div className="card mb-8">
            <h2 className="text-xl font-bold mb-6 flex items-center">
              <Brain className="mr-2" size={24} />
              AI Nutrition Analysis
            </h2>
            <p className="text-gray-600 mb-6">
              Simply enter any food name and serving size. Our AI will analyze the complete nutritional content and log your meal automatically.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="form-label">Food Name *</label>
                  <input
                    type="text"
                  placeholder="e.g., Grilled Chicken Breast, Apple, Brown Rice"
                  className="form-input"
                  value={nutrientForm.food_name}
                  onChange={(e) => setNutrientForm({...nutrientForm, food_name: e.target.value})}
                />
                  </div>
                  
              <div>
                <label className="form-label">Serving Size *</label>
                <input
                  type="text"
                  placeholder="e.g., 150g, 1 cup, 2 pieces, 1 medium"
                  className="form-input"
                  value={nutrientForm.serving_size}
                  onChange={(e) => setNutrientForm({...nutrientForm, serving_size: e.target.value})}
                />
              </div>
              
              <div>
                <label className="form-label">Meal Type *</label>
                <select
                  className="form-input"
                  value={nutrientForm.meal_type}
                  onChange={(e) => setNutrientForm({...nutrientForm, meal_type: e.target.value})}
                >
                  <option value="breakfast">Breakfast</option>
                  <option value="lunch">Lunch</option>
                  <option value="dinner">Dinner</option>
                  <option value="snack">Snack</option>
                </select>
                                  </div>
              
              <div className="flex items-end">
                <button
                  onClick={analyzeNutrition}
                  disabled={isAnalyzingNutrition || !nutrientForm.food_name || !nutrientForm.serving_size}
                  className="btn btn-secondary w-full"
                >
                  {isAnalyzingNutrition ? 'Analyzing...' : 'Analyze Nutrition'}
                </button>
                                    </div>
            </div>
            
            {error && (
              <div className="mt-4 text-red-600 text-sm text-center">{error}</div>
                                  )}
                                </div>

          {/* Nutrition Analysis Results */}
          {showNutrientAnalysis && nutrientAnalysis && (
            <div className="card mb-8">
              <h3 className="text-lg font-bold mb-4 flex items-center">
                <Brain className="mr-2" size={20} />
                Nutrition Analysis Results
              </h3>
              
              <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
                <h4 className="font-bold text-lg mb-4">
                  {nutrientAnalysis.food_name} ({nutrientAnalysis.serving_size})
                </h4>
                
                {nutrientAnalysis.parsed_nutrients && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {nutrientAnalysis.parsed_nutrients.calories || 0}
                                </div>
                      <div className="text-sm text-gray-600">Calories</div>
                              </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {nutrientAnalysis.parsed_nutrients.protein || 0}g
                            </div>
                      <div className="text-sm text-gray-600">Protein</div>
                        </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-orange-600">
                        {nutrientAnalysis.parsed_nutrients.carbohydrates || 0}g
                    </div>
                      <div className="text-sm text-gray-600">Carbs</div>
                </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-purple-600">
                        {nutrientAnalysis.parsed_nutrients.fat || 0}g
                    </div>
                      <div className="text-sm text-gray-600">Fat</div>
                  </div>
              </div>
                )}
                
                {nutrientAnalysis.parsed_nutrients && nutrientAnalysis.parsed_nutrients.health_tags && nutrientAnalysis.parsed_nutrients.health_tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {nutrientAnalysis.parsed_nutrients.health_tags.map((tag, index) => (
                      <span key={index} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                        {tag}
                      </span>
                    ))}
              </div>
                )}
                
                <div className="prose max-w-none text-sm">
                  <div dangerouslySetInnerHTML={{ __html: nutrientAnalysis.raw_analysis.replace(/\n/g, '<br>') }} />
                </div>
              </div>

              <div className="flex gap-4">
              <button
                  onClick={logMealWithAnalysis}
                disabled={isLoading}
                  className="btn btn-primary flex-1"
              >
                  {isLoading ? 'Logging Meal...' : 'Log This Meal'}
              </button>
                <button
                  onClick={() => setShowNutrientAnalysis(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Sample Foods */}
          <div className="card">
            <h3 className="text-lg font-bold mb-4">Sample Foods to Try</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Proteins</h4>
                <div className="space-y-1 text-sm">
                  <div>Chicken Breast - 100g</div>
                  <div>Salmon Fillet - 150g</div>
                  <div>Greek Yogurt - 1 cup</div>
                  <div>Eggs - 2 large</div>
                  <div>Tofu - 100g</div>
                </div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Carbohydrates</h4>
                <div className="space-y-1 text-sm">
                  <div>Brown Rice - 1 cup cooked</div>
                  <div>Quinoa - 1 cup cooked</div>
                  <div>Sweet Potato - 1 medium</div>
                  <div>Oatmeal - 1 cup cooked</div>
                  <div>Banana - 1 medium</div>
                </div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Vegetables</h4>
                <div className="space-y-1 text-sm">
                  <div>Broccoli - 1 cup</div>
                  <div>Spinach - 2 cups raw</div>
                  <div>Carrots - 1 cup chopped</div>
                  <div>Bell Peppers - 1 medium</div>
                  <div>Avocado - 1/2 medium</div>
                </div>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Fruits</h4>
                <div className="space-y-1 text-sm">
                  <div>Apple - 1 medium</div>
                  <div>Blueberries - 1 cup</div>
                  <div>Orange - 1 medium</div>
                  <div>Strawberries - 1 cup</div>
                  <div>Mango - 1 cup sliced</div>
                </div>
              </div>
            </div>
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
                      <button 
                        onClick={() => handleAddToPlan(food)}
                        className="btn btn-primary btn-sm"
                      >
                        Log This Meal
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

      {/* Quick Log Modal */}
      {showQuickLogModal && selectedRecommendation && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 999999
          }}
        >
          <div 
            style={{
              backgroundColor: 'white',
              padding: '24px',
              borderRadius: '8px',
              maxWidth: '500px',
              width: '90%',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              position: 'relative',
              zIndex: 1000000
            }}
          >
            <h3 className="text-xl font-bold mb-4">Log Recommended Food</h3>
            
            {/* Food Info */}
            <div className="bg-gray-50 p-4 rounded-lg mb-4">
              <h4 className="font-bold text-lg mb-2">{selectedRecommendation.name}</h4>
              <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                <div>
                  <span className="font-medium">Cuisine:</span> {selectedRecommendation.cuisine_type}
                </div>
                <div>
                  <span className="font-medium">Calories:</span> {selectedRecommendation.calories} cal
                </div>
                <div>
                  <span className="font-medium">Protein:</span> {selectedRecommendation.protein_g}g
                </div>
                <div>
                  <span className="font-medium">Carbs:</span> {selectedRecommendation.carbs_g}g
                </div>
              </div>
            </div>

            {/* Meal Type Selection */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Meal Type
              </label>
              <select
                value={quickLogForm.meal_type}
                onChange={(e) => setQuickLogForm({...quickLogForm, meal_type: e.target.value})}
                className="w-full p-2 border border-gray-300 rounded-lg"
              >
                <option value="breakfast">Breakfast</option>
                <option value="lunch">Lunch</option>
                <option value="dinner">Dinner</option>
                <option value="snack">Snack</option>
              </select>
            </div>

            {/* Quantity */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Quantity (servings)
              </label>
              <input
                type="number"
                min="0.5"
                max="10"
                step="0.5"
                value={quickLogForm.quantity}
                onChange={(e) => setQuickLogForm({...quickLogForm, quantity: parseFloat(e.target.value)})}
                className="w-full p-2 border border-gray-300 rounded-lg"
              />
            </div>

            {/* Calculated Totals */}
            <div className="bg-blue-50 p-3 rounded-lg mb-4 text-sm">
              <div className="font-medium mb-1">Total Nutrition:</div>
              <div className="grid grid-cols-3 gap-2 text-gray-700">
                <div>
                  {(selectedRecommendation.calories * quickLogForm.quantity).toFixed(0)} cal
                </div>
                <div>
                  {(selectedRecommendation.protein_g * quickLogForm.quantity).toFixed(1)}g protein
                </div>
                <div>
                  {(selectedRecommendation.carbs_g * quickLogForm.quantity).toFixed(1)}g carbs
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                {error}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3">
              <button
                onClick={handleQuickLogMeal}
                disabled={isLoading}
                className="btn btn-primary flex-1"
              >
                {isLoading ? 'Logging...' : 'Log Meal'}
              </button>
              <button
                onClick={closeQuickLogModal}
                disabled={isLoading}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderAIRecipes = () => (
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
              <h1 className="text-2xl font-bold text-gray-900">AI Recipe Generator</h1>
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
          
          {/* ChefGenius Recipe Generator */}
          <div className="card mb-8">
            <h2 className="text-xl font-bold mb-6 flex items-center">
              <Brain className="mr-2" size={24} />
              ChefGenius - Generate Recipe from Ingredients
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Available Ingredients
                </label>
                <div className="flex gap-2">
                    <input
                    type="text"
                    placeholder="Type ingredient name..."
                    value={ingredientSearchQuery}
                    onChange={(e) => setIngredientSearchQuery(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && ingredientSearchQuery.trim()) {
                        e.preventDefault();
                        if (!chefgeniusForm.ingredients.includes(ingredientSearchQuery.trim())) {
                          setChefgeniusForm({
                            ...chefgeniusForm,
                            ingredients: [...chefgeniusForm.ingredients, ingredientSearchQuery.trim()]
                          });
                        }
                        setIngredientSearchQuery('');
                      }
                    }}
                    className="form-input flex-1"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (ingredientSearchQuery.trim() && !chefgeniusForm.ingredients.includes(ingredientSearchQuery.trim())) {
                        setChefgeniusForm({
                          ...chefgeniusForm,
                          ingredients: [...chefgeniusForm.ingredients, ingredientSearchQuery.trim()]
                        });
                        setIngredientSearchQuery('');
                      }
                    }}
                    className="btn btn-secondary px-4"
                    disabled={!ingredientSearchQuery.trim()}
                  >
                    Add
                  </button>
                  </div>
              
                {/* Selected Ingredients for ChefGenius */}
                {chefgeniusForm.ingredients.length > 0 && (
                  <div className="mt-3">
                    <div className="text-sm font-medium text-gray-700 mb-2">Selected Ingredients:</div>
                    <div className="flex flex-wrap gap-2">
                      {chefgeniusForm.ingredients.map((ingredient, index) => (
                        <span
                          key={index}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-green-100 text-green-800"
                        >
                          {ingredient}
                          <button
                            type="button"
                            onClick={() => removeIngredientFromChefgenius(index)}
                            className="ml-2 text-green-600 hover:text-green-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              
              <div className="space-y-4">
                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Meal Type
                </label>
                    <select
                    value={chefgeniusForm.meal_type}
                    onChange={(e) => setChefgeniusForm({...chefgeniusForm, meal_type: e.target.value})}
                      className="form-input"
                >
                  <option value="breakfast">Breakfast</option>
                  <option value="lunch">Lunch</option>
                  <option value="dinner">Dinner</option>
                  <option value="snack">Snack</option>
                    </select>
                </div>

                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                    Time Constraint (minutes)
                </label>
                    <input
                      type="number"
                  min="15"
                  max="300"
                    value={chefgeniusForm.time_constraint}
                    onChange={(e) => setChefgeniusForm({...chefgeniusForm, time_constraint: parseInt(e.target.value)})}
                      className="form-input"
                    />
                  </div>
              
                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                    Dietary Restrictions
                </label>
                  <div className="space-y-2">
                    {['vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'nut-free'].map((restriction) => (
                      <label key={restriction} className="flex items-center">
                    <input
                          type="checkbox"
                          checked={chefgeniusForm.dietary_restrictions.includes(restriction)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setChefgeniusForm({
                                ...chefgeniusForm,
                                dietary_restrictions: [...chefgeniusForm.dietary_restrictions, restriction]
                              });
                            } else {
                              setChefgeniusForm({
                                ...chefgeniusForm,
                                dietary_restrictions: chefgeniusForm.dietary_restrictions.filter(r => r !== restriction)
                              });
                            }
                          }}
                          className="mr-2"
                        />
                        <span className="text-sm text-gray-700 capitalize">{restriction.replace('-', ' ')}</span>
                </label>
                      ))}
                  </div>
                  </div>
                </div>
                </div>

            <div className="mt-6">
                <button
                onClick={generateChefgeniusRecipe}
                className="btn btn-primary"
                disabled={isGeneratingChefgenius}
              >
                {isGeneratingChefgenius ? 'Generating Recipe...' : 'Generate ChefGenius Recipe'}
                </button>
            </div>
          </div>

          {/* Generated Recipe */}
          {generatedRecipe && (
            <div className="card mb-8">
              <h2 className="text-xl font-bold mb-6 flex items-center">
                <Lightbulb className="mr-2" size={24} />
                Your Generated Recipe
              </h2>
              
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
                <h3 className="text-2xl font-bold text-blue-800 mb-2">{generatedRecipe.name}</h3>
                <p className="text-blue-700 mb-4">{generatedRecipe.description}</p>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Cuisine:</span>
                    <span className="ml-2 capitalize">{generatedRecipe.cuisine}</span>
                  </div>
                  <div>
                    <span className="font-medium">Difficulty:</span>
                    <span className="ml-2 capitalize">{generatedRecipe.difficulty}</span>
                </div>
                  <div>
                    <span className="font-medium">Prep Time:</span>
                    <span className="ml-2">{generatedRecipe.preparation_time} min</span>
                </div>
                  <div>
                    <span className="font-medium">Cook Time:</span>
                    <span className="ml-2">{generatedRecipe.cooking_time} min</span>
                </div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Ingredients */}
                <div>
                  <h4 className="text-lg font-bold mb-4">Ingredients</h4>
                          <div className="space-y-2">
                    {generatedRecipe.ingredients && generatedRecipe.ingredients.map((ingredient, index) => (
                      <div key={index} className="flex justify-between items-center py-2 border-b border-gray-100">
                        <span className="text-gray-800">{ingredient.name}</span>
                        <span className="text-gray-600 font-medium">
                          {ingredient.quantity} {ingredient.unit}
                        </span>
                                </div>
                    ))}
                  </div>
                </div>
                
                {/* Instructions */}
                <div>
                  <h4 className="text-lg font-bold mb-4">Instructions</h4>
                  <div className="space-y-3">
                    {generatedRecipe.instructions && generatedRecipe.instructions.map((instruction, index) => (
                      <div key={index} className="flex">
                        <span className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold mr-3 flex-shrink-0">
                          {index + 1}
                        </span>
                        <span className="text-gray-700">{instruction}</span>
                              </div>
                            ))}
                          </div>
                          </div>
                        </div>
              
              {/* Nutrition Info */}
              <div className="mt-8 bg-gray-50 rounded-lg p-6">
                <h4 className="text-lg font-bold mb-4">Nutrition per Serving</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{generatedRecipe.nutrition_per_serving?.calories || 0}</div>
                    <div className="text-sm text-gray-600">Calories</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">{generatedRecipe.nutrition_per_serving?.protein || 0}g</div>
                    <div className="text-sm text-gray-600">Protein</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-600">{generatedRecipe.nutrition_per_serving?.carbs || 0}g</div>
                    <div className="text-sm text-gray-600">Carbs</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">{generatedRecipe.nutrition_per_serving?.fat || 0}g</div>
                    <div className="text-sm text-gray-600">Fat</div>
                  </div>
                </div>
              </div>
              
              {/* Health Benefits */}
              {generatedRecipe.health_benefits && generatedRecipe.health_benefits.length > 0 && (
                <div className="mt-6">
                  <h4 className="text-lg font-bold mb-4">Health Benefits</h4>
                  <div className="flex flex-wrap gap-2">
                    {generatedRecipe.health_benefits.map((benefit, index) => (
                      <span key={index} className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm">
                        {benefit}
                      </span>
                      ))}
                    </div>
                    </div>
              )}
            </div>
          )}

          {/* ChefGenius Generated Recipe */}
          {chefgeniusRecipe && (
            <div className="card mb-8">
              <h2 className="text-xl font-bold mb-6 flex items-center">
                <Brain className="mr-2" size={24} />
                Your ChefGenius Recipe
              </h2>
              
              <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
                <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: chefgeniusRecipe.recipe.replace(/\n/g, '<br>') }} />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-lg font-bold mb-4">Ingredients Used</h4>
                  <div className="space-y-2">
                    {chefgeniusRecipe.ingredients_used.map((ingredient, index) => (
                      <div key={index} className="flex items-center py-2 border-b border-gray-100">
                        <span className="text-gray-800">{ingredient}</span>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div>
                  <h4 className="text-lg font-bold mb-4">Recipe Details</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Meal Type:</span>
                      <span className="font-medium capitalize">{chefgeniusRecipe.meal_type}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Time Constraint:</span>
                      <span className="font-medium">{chefgeniusRecipe.time_constraint} minutes</span>
                    </div>
                    {chefgeniusRecipe.dietary_restrictions.length > 0 && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Dietary Restrictions:</span>
                        <span className="font-medium">{chefgeniusRecipe.dietary_restrictions.join(', ')}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Recipe History */}
          {aiRecipes && aiRecipes.length > 0 && (
            <div className="card">
              <h2 className="text-xl font-bold mb-6">Your Recipe History</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {aiRecipes.map((recipe, index) => (
                  <div key={recipe.id || index} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <h3 className="font-bold text-lg mb-2">{recipe.name}</h3>
                    <p className="text-gray-600 text-sm mb-3">{recipe.description}</p>
                    
                    <div className="text-sm text-gray-500 mb-3">
                      <div className="flex justify-between">
                        <span>{recipe.cuisine} • {recipe.difficulty}</span>
                        <span>{recipe.preparation_time + recipe.cooking_time} min</span>
                      </div>
                    </div>
                    
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">
                        {recipe.nutrition_per_serving?.calories || 0} cal
                      </span>
                      <button 
                        onClick={() => setGeneratedRecipe(recipe)}
                        className="btn btn-primary btn-sm"
                      >
                        View Recipe
                      </button>
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

  const renderFitMentor = () => (
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
              <h1 className="text-2xl font-bold text-gray-900">FitMentor - AI Workout Planner</h1>
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

          {/* FitMentor Workout Planner */}
          <div className="card mb-8">
            <h2 className="text-xl font-bold mb-6 flex items-center">
              <Target className="mr-2" size={24} />
              Create Your Personalized Workout Plan
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Activity Level *
                </label>
                <select
                  value={fitmentorForm.activity_level}
                  onChange={(e) => setFitmentorForm({...fitmentorForm, activity_level: e.target.value})}
                  className="form-input"
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Fitness Goal *
                </label>
                <select
                  value={fitmentorForm.fitness_goal}
                  onChange={(e) => setFitmentorForm({...fitmentorForm, fitness_goal: e.target.value})}
                  className="form-input"
                >
                  <option value="weight_loss">Weight Loss</option>
                  <option value="muscle_gain">Muscle Gain</option>
                  <option value="endurance">Endurance</option>
                  <option value="flexibility">Flexibility</option>
                  <option value="general_fitness">General Fitness</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Time per Day (minutes) *
                </label>
                <input
                  type="number"
                  min="15"
                  max="180"
                  value={fitmentorForm.time_per_day}
                  onChange={(e) => setFitmentorForm({...fitmentorForm, time_per_day: parseInt(e.target.value)})}
                  className="form-input"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Equipment Available *
                </label>
                <select
                  value={fitmentorForm.equipment}
                  onChange={(e) => setFitmentorForm({...fitmentorForm, equipment: e.target.value})}
                  className="form-input"
                >
                  <option value="none">No Equipment</option>
                  <option value="home">Home Equipment</option>
                  <option value="gym">Full Gym Access</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Age (optional)
                </label>
                <input
                  type="number"
                  min="13"
                  max="100"
                  value={fitmentorForm.age || ''}
                  onChange={(e) => setFitmentorForm({...fitmentorForm, age: e.target.value ? parseInt(e.target.value) : null})}
                  className="form-input"
                  placeholder="Enter your age"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Weight (kg, optional)
                </label>
                <input
                  type="number"
                  min="30"
                  max="300"
                  step="0.1"
                  value={fitmentorForm.weight || ''}
                  onChange={(e) => setFitmentorForm({...fitmentorForm, weight: e.target.value ? parseFloat(e.target.value) : null})}
                  className="form-input"
                  placeholder="Enter your weight"
                />
              </div>
              </div>
              
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Constraints (optional)
              </label>
              <div className="space-y-2">
                {['knee_injury', 'back_problems', 'shoulder_issues', 'asthma', 'diabetes', 'pregnancy'].map((constraint) => (
                  <label key={constraint} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={fitmentorForm.constraints.includes(constraint)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFitmentorForm({
                            ...fitmentorForm,
                            constraints: [...fitmentorForm.constraints, constraint]
                          });
                        } else {
                          setFitmentorForm({
                            ...fitmentorForm,
                            constraints: fitmentorForm.constraints.filter(c => c !== constraint)
                          });
                        }
                      }}
                      className="mr-2"
                    />
                    <span className="text-sm text-gray-700 capitalize">{constraint.replace('_', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
            
            <div className="mt-6">
              <button
                onClick={generateFitmentorPlan}
                className="btn btn-primary"
                disabled={isGeneratingFitmentor}
              >
                {isGeneratingFitmentor ? 'Generating Plan...' : 'Generate Workout Plan'}
              </button>
            </div>
          </div>

          {/* FitMentor Generated Plan */}
          {fitmentorPlan && (
            <div className="card mb-8">
              <h2 className="text-xl font-bold mb-6 flex items-center">
                <Target className="mr-2" size={24} />
                Your FitMentor Workout Plan
              </h2>
              
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
                <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: fitmentorPlan.workout_plan.replace(/\n/g, '<br>') }} />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-lg font-bold mb-4">Plan Details</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Activity Level:</span>
                      <span className="font-medium capitalize">{fitmentorPlan.activity_level}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Fitness Goal:</span>
                      <span className="font-medium capitalize">{fitmentorPlan.fitness_goal.replace('_', ' ')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Time per Day:</span>
                      <span className="font-medium">{fitmentorPlan.time_per_day} minutes</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Equipment:</span>
                      <span className="font-medium capitalize">{fitmentorPlan.equipment}</span>
                    </div>
                    {fitmentorPlan.constraints.length > 0 && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Constraints:</span>
                        <span className="font-medium">{fitmentorPlan.constraints.join(', ')}</span>
                      </div>
                    )}
                  </div>
                </div>
                
                <div>
                  <h4 className="text-lg font-bold mb-4">Adapt Your Plan</h4>
                  <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                        Current Plan
                      </label>
                      <textarea
                        value={adaptationForm.current_plan}
                        onChange={(e) => setAdaptationForm({...adaptationForm, current_plan: e.target.value})}
                        className="form-input"
                        rows="3"
                        placeholder="Paste your current workout plan here..."
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Feedback
                      </label>
                      <textarea
                        value={adaptationForm.feedback}
                        onChange={(e) => setAdaptationForm({...adaptationForm, feedback: e.target.value})}
                        className="form-input"
                        rows="3"
                        placeholder="What would you like to change? What's working/not working?"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Progress Notes (optional)
                      </label>
                      <textarea
                        value={adaptationForm.progress_notes}
                        onChange={(e) => setAdaptationForm({...adaptationForm, progress_notes: e.target.value})}
                        className="form-input"
                        rows="2"
                        placeholder="Any progress notes or observations..."
                      />
                    </div>
                    <button
                      onClick={adaptFitmentorPlan}
                      className="btn btn-secondary"
                      disabled={isGeneratingFitmentor || !adaptationForm.current_plan || !adaptationForm.feedback}
                    >
                      {isGeneratingFitmentor ? 'Adapting Plan...' : 'Adapt Workout Plan'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );

  const renderBudgetChef = () => (
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
              <h1 className="text-2xl font-bold text-gray-900">BudgetChef - AI Budget Meal Planner</h1>
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

          {/* BudgetChef Meal Planner */}
          <div className="card mb-8">
            <h2 className="text-xl font-bold mb-6 flex items-center">
              <Utensils className="mr-2" size={24} />
              Create Your Budget Meal Plan
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Daily Budget (₹) *
                </label>
                <input
                  type="number"
                  min="50"
                  max="2000"
                  step="10"
                  value={budgetchefForm.budget_per_day}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, budget_per_day: parseFloat(e.target.value)})}
                  className="form-input"
                  placeholder="Enter your daily budget"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Calories (optional)
                </label>
                <input
                  type="number"
                  min="1000"
                  max="5000"
                  value={budgetchefForm.calorie_target || ''}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, calorie_target: e.target.value ? parseInt(e.target.value) : null})}
                  className="form-input"
                  placeholder="Will be estimated if not provided"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Meals per Day *
                </label>
                <select
                  value={budgetchefForm.meals_per_day}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, meals_per_day: parseInt(e.target.value)})}
                  className="form-input"
                >
                  <option value={1}>1 meal</option>
                  <option value={2}>2 meals</option>
                  <option value={3}>3 meals</option>
                  <option value={4}>4 meals</option>
                  <option value={5}>5 meals</option>
                  <option value={6}>6 meals</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Cooking Time *
                </label>
                <select
                  value={budgetchefForm.cooking_time}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, cooking_time: e.target.value})}
                  className="form-input"
                >
                  <option value="quick">Quick (15-30 min)</option>
                  <option value="moderate">Moderate (30-60 min)</option>
                  <option value="extensive">Extensive (60+ min)</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Cooking Skill Level *
                </label>
                <select
                  value={budgetchefForm.skill_level}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, skill_level: e.target.value})}
                  className="form-input"
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Activity Level *
                </label>
                <select
                  value={budgetchefForm.activity_level}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, activity_level: e.target.value})}
                  className="form-input"
                >
                  <option value="sedentary">Sedentary</option>
                  <option value="light">Light</option>
                  <option value="moderate">Moderate</option>
                  <option value="active">Active</option>
                  <option value="very_active">Very Active</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Age (optional)
                </label>
                  <input
                  type="number"
                  min="13"
                  max="100"
                  value={budgetchefForm.age || ''}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, age: e.target.value ? parseInt(e.target.value) : null})}
                  className="form-input"
                  placeholder="For calorie estimation"
                />
                  </div>
                  
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Weight (kg, optional)
                </label>
                <input
                  type="number"
                  min="30"
                  max="300"
                  step="0.1"
                  value={budgetchefForm.weight || ''}
                  onChange={(e) => setBudgetchefForm({...budgetchefForm, weight: e.target.value ? parseFloat(e.target.value) : null})}
                  className="form-input"
                  placeholder="For calorie estimation"
                />
              </div>
            </div>
            
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Dietary Preferences (optional)
              </label>
              <div className="space-y-2">
                {['vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'nut-free', 'low-carb', 'high-protein'].map((preference) => (
                  <label key={preference} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={budgetchefForm.dietary_preferences.includes(preference)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setBudgetchefForm({
                            ...budgetchefForm,
                            dietary_preferences: [...budgetchefForm.dietary_preferences, preference]
                          });
                        } else {
                          setBudgetchefForm({
                            ...budgetchefForm,
                            dietary_preferences: budgetchefForm.dietary_preferences.filter(p => p !== preference)
                          });
                        }
                      }}
                      className="mr-2"
                    />
                    <span className="text-sm text-gray-700 capitalize">{preference.replace('-', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
            
            <div className="mt-6">
              <button
                onClick={generateBudgetchefPlan}
                className="btn btn-primary"
                disabled={isGeneratingBudgetchef}
              >
                {isGeneratingBudgetchef ? 'Generating Plan...' : 'Generate Budget Meal Plan'}
              </button>
                                  </div>
                                    </div>

          {/* BudgetChef Generated Plan */}
          {budgetchefPlan && (
            <div className="card mb-8">
              <h2 className="text-xl font-bold mb-6 flex items-center">
                <Utensils className="mr-2" size={24} />
                Your BudgetChef Meal Plan
              </h2>
              
              <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
                <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: budgetchefPlan.meal_plan.replace(/\n/g, '<br>') }} />
                                </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-lg font-bold mb-4">Plan Details</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Daily Budget:</span>
                      <span className="font-medium">₹{budgetchefPlan.budget_per_day}</span>
                                </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Calorie Target:</span>
                      <span className="font-medium">{budgetchefPlan.calorie_target || 'Estimated'}</span>
                              </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Meals per Day:</span>
                      <span className="font-medium">{budgetchefPlan.meals_per_day}</span>
                            </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Cooking Time:</span>
                      <span className="font-medium capitalize">{budgetchefPlan.cooking_time}</span>
                        </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Skill Level:</span>
                      <span className="font-medium capitalize">{budgetchefPlan.skill_level}</span>
                    </div>
                    {budgetchefPlan.dietary_preferences.length > 0 && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Dietary Preferences:</span>
                        <span className="font-medium">{budgetchefPlan.dietary_preferences.join(', ')}</span>
                    </div>
                  )}
                  </div>
                </div>
                
                <div>
                  <h4 className="text-lg font-bold mb-4">Adapt Your Plan</h4>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Current Plan
                      </label>
                      <textarea
                        value={budgetAdaptationForm.current_plan}
                        onChange={(e) => setBudgetAdaptationForm({...budgetAdaptationForm, current_plan: e.target.value})}
                        className="form-input"
                        rows="3"
                        placeholder="Paste your current meal plan here..."
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Feedback
                      </label>
                      <textarea
                        value={budgetAdaptationForm.feedback}
                        onChange={(e) => setBudgetAdaptationForm({...budgetAdaptationForm, feedback: e.target.value})}
                        className="form-input"
                        rows="3"
                        placeholder="What would you like to change? What's working/not working?"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          New Budget (₹, optional)
                        </label>
                        <input
                          type="number"
                          min="50"
                          max="2000"
                          value={budgetAdaptationForm.new_budget || ''}
                          onChange={(e) => setBudgetAdaptationForm({...budgetAdaptationForm, new_budget: e.target.value ? parseFloat(e.target.value) : null})}
                          className="form-input"
                          placeholder="New budget"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          New Calorie Target (optional)
                        </label>
                        <input
                          type="number"
                          min="1000"
                          max="5000"
                          value={budgetAdaptationForm.new_calorie_target || ''}
                          onChange={(e) => setBudgetAdaptationForm({...budgetAdaptationForm, new_calorie_target: e.target.value ? parseInt(e.target.value) : null})}
                          className="form-input"
                          placeholder="New calories"
                        />
                      </div>
                    </div>
                          <button
                      onClick={adaptBudgetchefPlan}
                      className="btn btn-secondary"
                      disabled={isGeneratingBudgetchef || !budgetAdaptationForm.current_plan || !budgetAdaptationForm.feedback}
                    >
                      {isGeneratingBudgetchef ? 'Adapting Plan...' : 'Adapt Meal Plan'}
                          </button>
                  </div>
                </div>
                    </div>
                  </div>
                )}

              </div>
            </div>
    </div>
  );

  const renderCulinaryExplorer = () => (
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
              <h1 className="text-2xl font-bold text-gray-900">CulinaryExplorer - Regional Cuisine Planner</h1>
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

          {/* CulinaryExplorer Regional Cuisine Planner */}
            <div className="card mb-8">
              <h2 className="text-xl font-bold mb-6 flex items-center">
              <Globe className="mr-2" size={24} />
              Explore Regional Cuisines & Cultural Foods
              </h2>
              
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Cuisine Region *
                </label>
                <select
                  value={culinaryexplorerForm.cuisine_region}
                  onChange={(e) => setCulinaryexplorerForm({...culinaryexplorerForm, cuisine_region: e.target.value})}
                  className="form-input"
                >
                  <optgroup label="Global Cuisines">
                    <option value="mediterranean">Mediterranean</option>
                    <option value="japanese">Japanese</option>
                    <option value="mexican">Mexican</option>
                    <option value="italian">Italian</option>
                    <option value="chinese">Chinese</option>
                    <option value="thai">Thai</option>
                    <option value="french">French</option>
                    <option value="indian">Indian</option>
                  </optgroup>
                  <optgroup label="Indian States">
                    <option value="andhra_pradesh">Andhra Pradesh</option>
                    <option value="arunachal_pradesh">Arunachal Pradesh</option>
                    <option value="assam">Assam</option>
                    <option value="bihar">Bihar</option>
                    <option value="chhattisgarh">Chhattisgarh</option>
                    <option value="goa">Goa</option>
                    <option value="gujarat">Gujarat</option>
                    <option value="haryana">Haryana</option>
                    <option value="himachal_pradesh">Himachal Pradesh</option>
                    <option value="jharkhand">Jharkhand</option>
                    <option value="karnataka">Karnataka</option>
                    <option value="kerala">Kerala</option>
                    <option value="madhya_pradesh">Madhya Pradesh</option>
                    <option value="maharashtra">Maharashtra</option>
                    <option value="manipur">Manipur</option>
                    <option value="meghalaya">Meghalaya</option>
                    <option value="mizoram">Mizoram</option>
                    <option value="nagaland">Nagaland</option>
                    <option value="odisha">Odisha</option>
                    <option value="punjab">Punjab</option>
                    <option value="rajasthan">Rajasthan</option>
                    <option value="sikkim">Sikkim</option>
                    <option value="tamil_nadu">Tamil Nadu</option>
                    <option value="telangana">Telangana</option>
                    <option value="tripura">Tripura</option>
                    <option value="uttar_pradesh">Uttar Pradesh</option>
                    <option value="uttarakhand">Uttarakhand</option>
                    <option value="west_bengal">West Bengal</option>
                  </optgroup>
                  <optgroup label="Union Territories">
                    <option value="andaman_nicobar">Andaman & Nicobar Islands</option>
                    <option value="chandigarh">Chandigarh</option>
                    <option value="dadra_nagar_haveli">Dadra & Nagar Haveli</option>
                    <option value="daman_diu">Daman & Diu</option>
                    <option value="delhi">Delhi</option>
                    <option value="jammu_kashmir">Jammu & Kashmir</option>
                    <option value="ladakh">Ladakh</option>
                    <option value="lakshadweep">Lakshadweep</option>
                    <option value="puducherry">Puducherry</option>
                  </optgroup>
                </select>
                  </div>
              
                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Meal Type *
                </label>
                <select
                  value={culinaryexplorerForm.meal_type}
                  onChange={(e) => setCulinaryexplorerForm({...culinaryexplorerForm, meal_type: e.target.value})}
                  className="form-input"
                >
                  <option value="breakfast">Breakfast</option>
                  <option value="lunch">Lunch</option>
                  <option value="dinner">Dinner</option>
                  <option value="snack">Snack</option>
                  <option value="full_day">Full Day Plan</option>
                </select>
                  </div>
              
                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Time Constraint (minutes) *
                </label>
                <input
                  type="number"
                  min="15"
                  max="300"
                  value={culinaryexplorerForm.time_constraint}
                  onChange={(e) => setCulinaryexplorerForm({...culinaryexplorerForm, time_constraint: parseInt(e.target.value)})}
                  className="form-input"
                />
                  </div>
              
                  <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Cooking Skill Level *
                </label>
                <select
                  value={culinaryexplorerForm.cooking_skill}
                  onChange={(e) => setCulinaryexplorerForm({...culinaryexplorerForm, cooking_skill: e.target.value})}
                  className="form-input"
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
                </div>
              </div>
              
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Dietary Restrictions (optional)
              </label>
                  <div className="space-y-2">
                {['vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'nut-free', 'low-carb', 'high-protein', 'keto', 'paleo', 'halal', 'kosher'].map((restriction) => (
                  <label key={restriction} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={culinaryexplorerForm.dietary_restrictions.includes(restriction)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setCulinaryexplorerForm({
                            ...culinaryexplorerForm,
                            dietary_restrictions: [...culinaryexplorerForm.dietary_restrictions, restriction]
                          });
                        } else {
                          setCulinaryexplorerForm({
                            ...culinaryexplorerForm,
                            dietary_restrictions: culinaryexplorerForm.dietary_restrictions.filter(r => r !== restriction)
                          });
                        }
                      }}
                      className="mr-2"
                    />
                    <span className="text-sm text-gray-700 capitalize">{restriction.replace('-', ' ')}</span>
                  </label>
                    ))}
                  </div>
                </div>
                
            <div className="mt-6">
              <button
                onClick={generateCulinaryexplorerPlan}
                className="btn btn-primary"
                disabled={isGeneratingCulinaryexplorer}
              >
                {isGeneratingCulinaryexplorer ? 'Generating Plan...' : 'Generate Regional Meal Plan'}
              </button>
                      </div>
                  </div>

          {/* CulinaryExplorer Generated Plan */}
          {culinaryexplorerPlan && (
            <div className="card mb-8">
              <h2 className="text-xl font-bold mb-6 flex items-center">
                <Globe className="mr-2" size={24} />
                Your CulinaryExplorer Regional Meal Plan
              </h2>
              
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-6 mb-6">
                <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: culinaryexplorerPlan.meal_plan.replace(/\n/g, '<br>') }} />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-lg font-bold mb-4">Plan Details</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Cuisine Region:</span>
                      <span className="font-medium capitalize">{culinaryexplorerPlan.cuisine_region.replace('_', ' ')}</span>
                  </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Meal Type:</span>
                      <span className="font-medium capitalize">{culinaryexplorerPlan.meal_type.replace('_', ' ')}</span>
                  </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Time Constraint:</span>
                      <span className="font-medium">{culinaryexplorerPlan.time_constraint} minutes</span>
                  </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Cooking Skill:</span>
                      <span className="font-medium capitalize">{culinaryexplorerPlan.cooking_skill}</span>
                  </div>
                    {culinaryexplorerPlan.dietary_restrictions.length > 0 && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Dietary Restrictions:</span>
                        <span className="font-medium">{culinaryexplorerPlan.dietary_restrictions.join(', ')}</span>
                      </div>
                    )}
                </div>
              </div>
              
                <div>
                  <h4 className="text-lg font-bold mb-4">Adapt Your Plan</h4>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Current Plan
                      </label>
                      <textarea
                        value={culinaryAdaptationForm.current_plan}
                        onChange={(e) => setCulinaryAdaptationForm({...culinaryAdaptationForm, current_plan: e.target.value})}
                        className="form-input"
                        rows="3"
                        placeholder="Paste your current meal plan here..."
                      />
                  </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Feedback
                      </label>
                      <textarea
                        value={culinaryAdaptationForm.feedback}
                        onChange={(e) => setCulinaryAdaptationForm({...culinaryAdaptationForm, feedback: e.target.value})}
                        className="form-input"
                        rows="3"
                        placeholder="What would you like to change? What's working/not working?"
                      />
                </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          New Cuisine Preference (optional)
                        </label>
                        <input
                          type="text"
                          value={culinaryAdaptationForm.new_cuisine_preference || ''}
                          onChange={(e) => setCulinaryAdaptationForm({...culinaryAdaptationForm, new_cuisine_preference: e.target.value})}
                          className="form-input"
                          placeholder="e.g., Italian, Kerala"
                        />
            </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          New Dietary Restrictions (optional)
                        </label>
                        <input
                          type="text"
                          value={culinaryAdaptationForm.new_dietary_restrictions || ''}
                          onChange={(e) => setCulinaryAdaptationForm({...culinaryAdaptationForm, new_dietary_restrictions: e.target.value.split(',').map(s => s.trim())})}
                          className="form-input"
                          placeholder="e.g., vegetarian, gluten-free"
                        />
                      </div>
                    </div>
                      <button 
                      onClick={adaptCulinaryexplorerPlan}
                      className="btn btn-secondary"
                      disabled={isGeneratingCulinaryexplorer || !culinaryAdaptationForm.current_plan || !culinaryAdaptationForm.feedback}
                      >
                      {isGeneratingCulinaryexplorer ? 'Adapting Plan...' : 'Adapt Meal Plan'}
                      </button>
                    </div>
                  </div>
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
      <header className="app-header">
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
              <h1 className="header-title text-2xl font-bold">Nutrition App</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="welcome-text">Welcome, {user?.full_name || user?.username}</span>
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

          {/* Smart Challenges */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold flex items-center">
                <Award className="mr-2" />
                Smart Challenges
              </h3>
              <button
                onClick={generateWeeklyChallenges}
                disabled={isGeneratingChallenges}
                className="text-xs bg-blue-500 text-white px-2 py-1 rounded hover:bg-blue-600 disabled:opacity-50"
              >
                {isGeneratingChallenges ? 'Generating...' : 'Generate'}
              </button>
            </div>
            {enhancedChallenges && enhancedChallenges.length > 0 ? (
              <div className="space-y-3">
                {enhancedChallenges.slice(0, 3).map((challenge) => (
                  <div key={challenge.challenge_id} className="border rounded-lg p-3 bg-gray-50">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="font-medium text-sm">{challenge.title}</div>
                        <div className="text-xs text-gray-500">{challenge.description}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-bold text-blue-600">
                          {(challenge.progress_percentage || 0).toFixed(0)}%
                        </div>
                        <div className="text-xs text-gray-500">Complete</div>
                      </div>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5 mb-2">
                      <div
                        className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(100, challenge.progress_percentage || 0)}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-gray-600">
                        {(challenge.current_value || 0).toFixed(1)} / {challenge.target_value || 0} {challenge.unit || ''}
                      </span>
                      <span className="text-green-600 font-bold">{challenge.points_reward || 0} pts</span>
                    </div>
                  </div>
                ))}
                {enhancedChallenges.length > 3 && (
                  <button
                    onClick={() => setActiveView('enhanced-challenges')}
                    className="w-full text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    View All Challenges ({enhancedChallenges.length})
                  </button>
                )}
              </div>
            ) : (
              <div className="text-center py-4">
                <Award className="mx-auto mb-2 text-gray-400" size={24} />
                <p className="text-gray-500 text-sm mb-2">No active challenges</p>
                <button
                  onClick={generateWeeklyChallenges}
                  disabled={isGeneratingChallenges}
                  className="text-xs bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600 disabled:opacity-50"
                >
                  {isGeneratingChallenges ? 'Generating...' : 'Generate Challenges'}
                </button>
              </div>
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
              onClick={() => setActiveView('ml-recommendations')}
            >
              <div className="text-center">
                <Brain className="mx-auto mb-2" size={32} />
                <div className="font-medium">AI Recommendations</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('ai-recipes')}
            >
              <div className="text-center">
                <ChefHat className="mx-auto mb-2" size={32} />
                <div className="font-medium">AI Recipe Generator</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('fitmentor')}
            >
              <div className="text-center">
                <Target className="mx-auto mb-2" size={32} />
                <div className="font-medium">FitMentor</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('budgetchef')}
            >
              <div className="text-center">
                <Utensils className="mx-auto mb-2" size={32} />
                <div className="font-medium">BudgetChef</div>
          </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('culinaryexplorer')}
            >
              <div className="text-center">
                <Globe className="mx-auto mb-2" size={32} />
                <div className="font-medium">CulinaryExplorer</div>
        </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('advancedmealplanner')}
            >
              <div className="text-center">
                <Calendar className="mx-auto mb-2" size={32} />
                <div className="font-medium">Advanced Planner</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('chatbot')}
            >
              <div className="text-center">
                <Brain className="mx-auto mb-2" size={32} />
                <div className="font-medium">AI Chatbot</div>
              </div>
            </button>
            <button 
              className="card hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setActiveView('enhanced-challenges')}
            >
              <div className="text-center">
                <Award className="mx-auto mb-2" size={32} />
                <div className="font-medium">Smart Challenges</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderChatbot = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="app-header">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="btn btn-secondary mr-4"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="header-title text-2xl font-bold">AI Chatbot Assistant</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="welcome-text">Welcome, {user?.full_name || user?.username}</span>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          
            {/* Service Status */}
            <div className="card mb-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold flex items-center">
                  <Brain className="mr-2" size={20} />
                  AI Service Status
                </h2>
                <div className="flex items-center">
                  <div className="w-3 h-3 bg-yellow-400 rounded-full mr-2 animate-pulse"></div>
                  <span className="text-sm text-yellow-600">Rate Limited - Using Fallback Responses</span>
                </div>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                Our AI service is currently experiencing high usage. We're providing helpful fallback responses until the service is restored.
              </p>
            </div>

            {/* Available Agents Info */}
          {availableAgents.length > 0 && (
            <div className="card mb-6">
              <h2 className="text-lg font-bold mb-4 flex items-center">
                <Brain className="mr-2" size={20} />
                Available AI Agents
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {availableAgents.map((agent, index) => (
                  <div key={index} className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="font-medium text-blue-900 capitalize">{agent.name.replace(/([A-Z])/g, ' $1').trim()}</div>
                    <div className="text-sm text-blue-700">{agent.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Chat Interface */}
          <div className="card">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold flex items-center">
                <Brain className="mr-2" size={24} />
                Chat with AI Assistant
              </h2>
              <button
                onClick={clearChatbotHistory}
                className="btn btn-secondary text-sm"
                disabled={chatbotMessages.length === 0}
              >
                Clear History
              </button>
            </div>

            {/* Messages */}
            <div className="h-96 overflow-y-auto border border-gray-200 rounded-lg p-4 mb-4 bg-gray-50">
              {chatbotMessages.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  <Brain size={48} className="mx-auto mb-4 text-gray-300" />
                  <p>Start a conversation with our AI assistant!</p>
                  <p className="text-sm mt-2">Try asking about recipes, meal plans, workouts, or nutrition advice.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {chatbotMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-xs lg:max-w-2xl px-4 py-2 rounded-lg ${
                          message.type === 'user'
                            ? 'bg-blue-500 text-white'
                            : 'bg-white border border-gray-200'
                        }`}
                      >
                        <div className={`text-sm ${message.type === 'bot' ? 'prose prose-sm max-w-none' : ''}`}>
                          {message.type === 'bot' ? (
                            <div 
                              className="whitespace-pre-wrap"
                              dangerouslySetInnerHTML={{
                                __html: message.content
                                  .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                  .replace(/\*(.*?)\*/g, '<em>$1</em>')
                                  .replace(/### (.*?)/g, '<h3 class="font-bold text-lg mt-4 mb-2">$1</h3>')
                                  .replace(/## (.*?)/g, '<h2 class="font-bold text-xl mt-4 mb-2">$1</h2>')
                                  .replace(/# (.*?)/g, '<h1 class="font-bold text-2xl mt-4 mb-2">$1</h1>')
                                  .replace(/\n\n/g, '<br><br>')
                                  .replace(/\n/g, '<br>')
                                  .replace(/- (.*?)(?=\n|$)/g, '<li class="ml-4">$1</li>')
                                  .replace(/(\d+)\. (.*?)(?=\n|$)/g, '<li class="ml-4">$1. $2</li>')
                              }}
                            />
                          ) : (
                            message.content
                          )}
                        </div>
                        <div className={`text-xs mt-1 ${
                          message.type === 'user' ? 'text-blue-100' : 'text-gray-500'
                        }`}>
                          {message.timestamp.toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  ))}
                  {isChatbotLoading && (
                    <div className="flex justify-start">
                      <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                        <div className="flex items-center space-x-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
                          <span className="text-sm text-gray-600">AI is thinking...</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={chatbotInput}
                onChange={(e) => setChatbotInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendChatbotMessage()}
                placeholder="Ask me anything about nutrition, recipes, workouts, or meal planning..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isChatbotLoading}
              />
              <button
                onClick={sendChatbotMessage}
                disabled={!chatbotInput.trim() || isChatbotLoading}
                className="btn btn-primary px-6"
              >
                {isChatbotLoading ? 'Sending...' : 'Send'}
              </button>
            </div>

            {/* Quick Suggestions */}
            <div className="mt-4">
              <p className="text-sm text-gray-600 mb-2">Try asking:</p>
              <div className="flex flex-wrap gap-2">
                {[
                  "Plan a workout for muscle gain, 60 minutes, gym equipment",
                  "I want a Kerala lunch recipe with chicken",
                  "Create a budget meal plan for 200 rupees per day",
                  "Analyze the nutrition in chicken curry 100g",
                  "Suggest a 7-day meal plan for 2000 calories"
                ].map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => setChatbotInput(suggestion)}
                    className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-full transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderAdvancedMealPlanner = () => (
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
              <h1 className="text-2xl font-bold text-gray-900">Advanced Meal Planner</h1>
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
          
          {/* Advanced Meal Planner Form */}
          <div className="card mb-8">
            <h2 className="text-xl font-bold mb-6 flex items-center">
              <Calendar className="mr-2" size={24} />
              Create Your 7-Day Meal Plan
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div>
                <label className="form-label">Target Calories (Daily) *</label>
                <input
                  type="number"
                  className="form-input"
                  value={advancedPlanForm.target_calories}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, target_calories: parseInt(e.target.value) || 0})}
                  min="100"
                  max="5000"
                />
              </div>
              
              <div>
                <label className="form-label">Meals Per Day *</label>
                <select
                  className="form-input"
                  value={advancedPlanForm.meals_per_day}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, meals_per_day: parseInt(e.target.value)})}
                >
                  <option value={3}>3 meals</option>
                  <option value={4}>4 meals</option>
                  <option value={5}>5 meals</option>
                  <option value={6}>6 meals</option>
                </select>
              </div>
              
              <div>
                <label className="form-label">Budget Per Day (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={advancedPlanForm.budget_per_day}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, budget_per_day: parseFloat(e.target.value) || 0})}
                  min="0"
                  step="10"
                  placeholder="e.g., 300"
                />
                <p className="text-sm text-gray-500 mt-1">Enter your daily food budget in Indian Rupees</p>
              </div>
              
              <div>
                <label className="form-label">Work Hours Per Day</label>
                <input
                  type="number"
                  className="form-input"
                  value={advancedPlanForm.work_hours_per_day}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, work_hours_per_day: parseInt(e.target.value) || 8})}
                  min="0"
                  max="24"
                />
              </div>
              
              <div>
                <label className="form-label">Time Per Meal (minutes)</label>
                <input
                  type="number"
                  className="form-input"
                  value={advancedPlanForm.time_per_meal_min}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, time_per_meal_min: parseInt(e.target.value) || 30})}
                  min="5"
                  max="120"
                />
              </div>
              
              <div>
                <label className="form-label">Cuisine/Region</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., Indian, Mediterranean, Asian"
                  value={advancedPlanForm.region_or_cuisine}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, region_or_cuisine: e.target.value})}
                />
              </div>
              
              <div className="md:col-span-2 lg:col-span-3">
                <label className="form-label">Food Preferences (comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., chicken, rice, vegetables, spicy"
                  value={advancedPlanForm.food_preferences.join(', ')}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, food_preferences: e.target.value.split(',').map(s => s.trim()).filter(s => s)})}
                />
              </div>
              
              <div className="md:col-span-2 lg:col-span-3">
                <label className="form-label">Dietary Restrictions (comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., gluten-free, dairy-free, vegetarian"
                  value={advancedPlanForm.dietary_restrictions.join(', ')}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, dietary_restrictions: e.target.value.split(',').map(s => s.trim()).filter(s => s)})}
                />
              </div>
              
              <div className="md:col-span-2 lg:col-span-3">
                <label className="form-label">Kitchen Equipment (comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., stove, oven, microwave, blender"
                  value={advancedPlanForm.equipment.join(', ')}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, equipment: e.target.value.split(',').map(s => s.trim()).filter(s => s)})}
                />
              </div>
              
              <div className="md:col-span-2 lg:col-span-3">
                <label className="form-label">Additional Notes</label>
                <textarea
                  className="form-input"
                  rows={3}
                  placeholder="Any specific requirements, allergies, or preferences..."
                  value={advancedPlanForm.user_notes}
                  onChange={(e) => setAdvancedPlanForm({...advancedPlanForm, user_notes: e.target.value})}
                />
              </div>
            </div>
            
            <div className="mt-6">
              <button
                onClick={generateAdvancedMealPlan}
                disabled={isGeneratingAdvancedPlan || !advancedPlanForm.target_calories}
                className="btn btn-primary w-full"
              >
                {isGeneratingAdvancedPlan ? 'Generating Plan...' : 'Generate 7-Day Meal Plan'}
              </button>
            </div>
            
            {error && (
              <div className="mt-4 text-red-600 text-sm text-center">{error}</div>
            )}
          </div>

          {/* Advanced Meal Plan Results */}
          {advancedMealPlan && (
            <div className="card mb-8">
              <h2 className="text-xl font-bold mb-6 flex items-center">
                <Calendar className="mr-2" size={24} />
                Your 7-Day Advanced Meal Plan
              </h2>
              
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
                <h3 className="text-lg font-bold mb-4">Plan Summary</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {advancedMealPlan.meta?.total_daily_calories || 'N/A'}
                    </div>
                    <div className="text-sm text-gray-600">Daily Calories</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {advancedMealPlan.meta?.meals_per_day || 'N/A'}
                    </div>
                    <div className="text-sm text-gray-600">Meals Per Day</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      ₹{advancedMealPlan.summary?.avg_daily_cost || 'N/A'}
                    </div>
                    <div className="text-sm text-gray-600">Avg Daily Cost</div>
                  </div>
                </div>
                
                {advancedMealPlan.meta?.assumptions && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mb-4">
                    <h4 className="font-semibold text-yellow-800 mb-2">Assumptions Made:</h4>
                    <p className="text-yellow-700 text-sm">{advancedMealPlan.meta.assumptions}</p>
                  </div>
                )}
              </div>
              
              {/* Weekly Plan */}
              <div className="space-y-6">
                {Object.entries(advancedMealPlan.plan || {}).map(([day, meals]) => (
                  <div key={day} className="border border-gray-200 rounded-lg p-4">
                    <h3 className="text-lg font-bold mb-4 capitalize">{day.replace('_', ' ')}</h3>
                    <div className="space-y-4">
                      {Array.isArray(meals) && meals.map((meal, index) => (
                        <div key={index} className="bg-gray-50 rounded-lg p-4">
                          <div className="flex justify-between items-start mb-2">
                            <h4 className="font-semibold text-lg">{meal.recipe_name}</h4>
                            <span className="text-sm text-gray-600">{meal.meal_label}</span>
                          </div>
                          
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
                            <div className="text-center">
                              <div className="font-bold text-blue-600">{meal.target_calories}</div>
                              <div className="text-xs text-gray-600">Calories</div>
                            </div>
                            <div className="text-center">
                              <div className="font-bold text-green-600">{meal.macros?.protein_g || 0}g</div>
                              <div className="text-xs text-gray-600">Protein</div>
                            </div>
                            <div className="text-center">
                              <div className="font-bold text-orange-600">{meal.macros?.carbs_g || 0}g</div>
                              <div className="text-xs text-gray-600">Carbs</div>
                            </div>
                            <div className="text-center">
                              <div className="font-bold text-purple-600">{meal.macros?.fat_g || 0}g</div>
                              <div className="text-xs text-gray-600">Fat</div>
                            </div>
                          </div>
                          
                          <div className="flex justify-between items-center text-sm text-gray-600 mb-2">
                            <span>Prep Time: {meal.prep_time_min} min</span>
                            <span>Make Ahead: {meal.make_ahead}</span>
                          </div>
                          
                          {meal.ingredients && meal.ingredients.length > 0 && (
                            <div className="mb-2">
                              <h5 className="font-semibold text-sm mb-1">Ingredients:</h5>
                              <div className="flex flex-wrap gap-2">
                                {meal.ingredients.map((ingredient, idx) => (
                                  <span key={idx} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                                    {ingredient.name} ({ingredient.qty}) {ingredient.est_cost ? `₹${ingredient.est_cost}` : ''}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          
                          {meal.notes && (
                            <div className="text-sm text-gray-600">
                              <strong>Notes:</strong> {meal.notes}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Shopping List */}
              {advancedMealPlan.summary?.weekly_shopping_list && (
                <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-4">
                  <h3 className="text-lg font-bold mb-4">Weekly Shopping List</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {advancedMealPlan.summary.weekly_shopping_list.map((item, index) => (
                      <div key={index} className="flex justify-between items-center bg-white rounded p-2">
                        <span className="text-sm">{item.name}</span>
                        <div className="text-right">
                          <div className="text-sm font-semibold">{item.qty_est}</div>
                          {item.est_cost && <div className="text-xs text-green-600">₹{item.est_cost}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Adaptation Section */}
              <div className="mt-6 border-t pt-6">
                <h3 className="text-lg font-bold mb-4">Adapt Your Plan</h3>
                <div className="space-y-4">
                  <div>
                    <label className="form-label">Feedback on Current Plan</label>
                    <textarea
                      className="form-input"
                      rows={3}
                      placeholder="What would you like to change about this meal plan?"
                      value={advancedPlanAdaptationForm.feedback}
                      onChange={(e) => setAdvancedPlanAdaptationForm({...advancedPlanAdaptationForm, feedback: e.target.value})}
                    />
                  </div>
                  
                  <button
                    onClick={adaptAdvancedMealPlan}
                    disabled={isGeneratingAdvancedPlan || !advancedPlanAdaptationForm.feedback.trim()}
                    className="btn btn-secondary"
                  >
                    {isGeneratingAdvancedPlan ? 'Adapting Plan...' : 'Adapt This Plan'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Enhanced Challenges View
  const renderEnhancedChallenges = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className="mr-4 p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft size={20} />
              </button>
              <div>
                <h1 className="text-2xl font-bold flex items-center">
                  <Award className="mr-2" size={24} />
                  Smart Challenges
                </h1>
                <p className="text-gray-600">Data-driven personalized challenges based on your nutrition and workout patterns</p>
              </div>
            </div>
            <button
              onClick={generateWeeklyChallenges}
              disabled={isGeneratingChallenges}
              className="btn-primary flex items-center"
            >
              {isGeneratingChallenges ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Generating...
                </>
              ) : (
                <>
                  <Lightbulb className="mr-2" size={16} />
                  Generate Weekly Challenges
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          {/* Analytics Overview */}
          {challengeAnalytics && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Challenges</p>
                    <p className="text-2xl font-bold">{challengeAnalytics.total_challenges}</p>
                  </div>
                  <Award className="text-blue-500" size={24} />
                </div>
              </div>
              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Completed</p>
                    <p className="text-2xl font-bold text-green-600">{challengeAnalytics.completed_challenges}</p>
                  </div>
                  <Target className="text-green-500" size={24} />
                </div>
              </div>
              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Completion Rate</p>
                    <p className="text-2xl font-bold">{(challengeAnalytics.completion_rate || 0).toFixed(1)}%</p>
                  </div>
                  <TrendingUp className="text-purple-500" size={24} />
                </div>
              </div>
              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Points Earned</p>
                    <p className="text-2xl font-bold text-yellow-600">{challengeAnalytics.total_points_earned}</p>
                  </div>
                  <BarChart3 className="text-yellow-500" size={24} />
                </div>
              </div>
            </div>
          )}

          {/* Active Challenges */}
          <div className="card mb-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold flex items-center">
                <Target className="mr-2" size={20} />
                Active Challenges
              </h2>
              <span className="text-sm text-gray-600">
                {enhancedChallenges?.length || 0} active challenge{(enhancedChallenges?.length || 0) !== 1 ? 's' : ''}
              </span>
            </div>

                 {(!enhancedChallenges || enhancedChallenges.length === 0) ? (
              <div className="text-center py-12">
                <Award className="mx-auto mb-4 text-gray-400" size={48} />
                <h3 className="text-lg font-semibold text-gray-600 mb-2">No Active Challenges</h3>
                <p className="text-gray-500 mb-4">Generate personalized challenges based on your data</p>
                <button
                  onClick={generateWeeklyChallenges}
                  disabled={isGeneratingChallenges}
                  className="btn-primary"
                >
                  Generate Challenges
                </button>
              </div>
            ) : (
                   <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                     {(enhancedChallenges || []).map((challenge) => (
                  <div key={challenge.challenge_id} className="border rounded-lg p-6 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="font-semibold text-lg mb-1">{challenge.title}</h3>
                        <p className="text-sm text-gray-600 mb-2">{challenge.description}</p>
                        <div className="flex items-center space-x-4 text-sm text-gray-500">
                          <span className="capitalize">{challenge.difficulty}</span>
                          <span>•</span>
                          <span>{challenge.days_remaining} days left</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold text-blue-600">
                          {(challenge.progress_percentage || 0).toFixed(0)}%
                        </div>
                        <div className="text-sm text-gray-500">Complete</div>
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-gray-600 mb-1">
                        <span>Progress</span>
                        <span>{(challenge.current_value || 0).toFixed(1)} / {challenge.target_value || 0} {challenge.unit || ''}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, challenge.progress_percentage || 0)}%` }}
                        ></div>
                      </div>
                    </div>

                    {/* Daily Targets */}
                    {challenge.daily_targets && (
                      <div className="mb-4">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Daily Targets</h4>
                        <div className="grid grid-cols-7 gap-1">
                          {challenge.daily_targets.map((target, index) => (
                            <div
                              key={index}
                              className={`text-center p-2 rounded text-xs ${
                                target.achieved
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-gray-100 text-gray-600'
                              }`}
                            >
                              <div className="font-semibold">Day {target.day}</div>
                              <div>{(target.value || 0).toFixed(1)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Rewards */}
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center space-x-4">
                        <span className="flex items-center">
                          <Award className="mr-1" size={14} />
                          {challenge.points_reward} pts
                        </span>
                        {challenge.badge_reward && (
                          <span className="flex items-center">
                            <Target className="mr-1" size={14} />
                            {challenge.badge_reward}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => {
                          const value = prompt(`Enter your progress for today (${challenge.unit}):`);
                          if (value && !isNaN(value)) {
                            updateChallengeProgress(challenge.challenge_id, parseFloat(value));
                          }
                        }}
                        className="text-blue-600 hover:text-blue-800 font-medium"
                      >
                        Update Progress
                      </button>
                    </div>

                    {/* Motivational Messages */}
                    {challenge.motivational_messages && challenge.motivational_messages.length > 0 && (
                      <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                        <p className="text-sm text-blue-800 italic">
                          "{challenge.motivational_messages[0]}"
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

               {/* Challenge Recommendations */}
               {challengeRecommendations && challengeRecommendations.length > 0 && (
            <div className="card">
              <h2 className="text-xl font-bold mb-6 flex items-center">
                <Lightbulb className="mr-2" size={20} />
                Recommended Challenges
              </h2>
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                     {(challengeRecommendations || []).map((rec, index) => (
                  <div key={index} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                    <h3 className="font-semibold mb-2">{rec.title}</h3>
                    <p className="text-sm text-gray-600 mb-3">{rec.description}</p>
                    <div className="flex items-center justify-between">
                      <div className="text-sm text-gray-500">
                        <span className="capitalize">{rec.difficulty}</span>
                        <span> • </span>
                        <span>{rec.duration_days} days</span>
                      </div>
                      <button className="text-blue-600 hover:text-blue-800 font-medium text-sm">
                        Accept Challenge
                      </button>
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
    } else if (activeView === 'ml-recommendations') {
      return renderMLRecommendations();
    } else if (activeView === 'ai-recipes') {
      return renderAIRecipes();
    } else if (activeView === 'fitmentor') {
      return renderFitMentor();
    } else if (activeView === 'budgetchef') {
      return renderBudgetChef();
    } else if (activeView === 'culinaryexplorer') {
      return renderCulinaryExplorer();
    } else if (activeView === 'advancedmealplanner') {
      return renderAdvancedMealPlanner();
    } else if (activeView === 'chatbot') {
      return renderChatbot();
    } else if (activeView === 'enhanced-challenges') {
      return renderEnhancedChallenges();
    } else {
      return renderDashboard();
    }
  }

  return null;
}

export default App;


