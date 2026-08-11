import React, { useState, useEffect, useRef } from 'react';
import { localDateString, syncTimezone, onLocalDayChange } from './localDay';
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
import Auth from './components/Auth';
import AppShell from './components/AppShell';
import Profile from './components/Profile';
import LogMeal from './components/LogMeal';
import Assistant from './components/Assistant';
import Challenges from './components/Challenges';
import InjuryTracker from './components/InjuryTracker';
import Dashboard from './components/Dashboard';
import GoalSetup from './components/GoalSetup';
import WeightCheckIn from './components/WeightCheckIn';
import Progress from './components/Progress';
import ForYou from './components/ForYou';
import ChefGenius from './components/ChefGenius';
import FitMentor from './components/FitMentor';
import BudgetChef from './components/BudgetChef';
import Explorer from './components/Explorer';
import MealPlanner from './components/MealPlanner';
import renderMarkdown from './components/markdown';
import { apiBase, isNativeApp } from './apiBase';
import ServerSetup from './components/ServerSetup';
import ResetPassword from './components/ResetPassword';
import Welcome from './components/Welcome';
import { toast, toastError } from './Toast';

// Resolved at runtime rather than baked in at build time: inside an APK the
// backend address changes constantly during testing (LAN IP, tunnel URL, a
// friend's network), and a build-time constant would mean a rebuild and a
// fresh install for every one of those. See src/apiBase.js.
const API_BASE_URL = apiBase();

function App() {
  const [currentView, setCurrentView] = useState('login');
  const [user, setUser] = useState(null);
  // Shown under the name in the sidebar, so the score is visible from
  // every screen rather than only on the profile.
  const [totalPoints, setTotalPoints] = useState(null);
  // Today's training answer and a slice of the board, both shown on the
  // dashboard so neither needs a trip to the profile.
  const [workoutToday, setWorkoutToday] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  /*
   * Send a goal-less account to goal setup, exactly once per session.
   *
   * Every recommendation in the app is derived from a goal, so an account
   * without one can only ever be shown empty boxes - which is what four of
   * the first seven signups saw before leaving.
   *
   * A ref rather than state, and once rather than continuously: someone who
   * deliberately clicks Dashboard to look around must be able to stay there.
   * Redirecting on every render would trap them, which is a far worse problem
   * than the one being solved.
   */
  const routedToGoalSetup = useRef(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Sign-in and registration state now lives in <Auth>, which owns both forms.
  const [sessionExpired, setSessionExpired] = useState(false);
  // Only ever true in the native app: in a browser the API is on the same
  // machine, so an unreachable backend means the server is down rather than
  // misconfigured, and a "set your server address" screen would be noise.
  const [needsServer, setNeedsServer] = useState(false);

  /*
   * The token from a reset link, captured once at startup.
   *
   * Read in the initialiser rather than an effect so the reset screen is the
   * first thing rendered - an effect would flash the login form first. The
   * token is stripped from the URL immediately afterwards: leaving it there
   * puts a working password-reset credential into browser history, into any
   * Referer header the page sends, and into whatever someone screenshots.
   */
  const [resetToken, setResetToken] = useState(() => {
    try {
      const found = new URLSearchParams(window.location.search).get('reset_token');
      if (found) {
        window.history.replaceState({}, '', window.location.pathname);
      }
      return found || '';
    } catch {
      return '';
    }
  });
  // Injury summary, so the dashboard can prompt for a check-in when one is due.
  const [injurySummary, setInjurySummary] = useState(null);

  // Dashboard data
  const [dashboardData, setDashboardData] = useState({
    dailyStats: null,
    recentMeals: [],
    timeline: [],
    adherenceHistory: [],
    adherenceSummary: null,
    todayAdherence: null,
    challenges: [],
    goals: [],
    weight: null
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
  const [challengesLastUpdated, setChallengesLastUpdated] = useState(null);

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
        // Only update challenges if we got valid data
        if (data.active_challenges && data.active_challenges.length > 0) {
          setEnhancedChallenges(data.active_challenges);
          setChallengesLastUpdated(Date.now()); // Update timestamp when generating new challenges
        }
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
        // Only update challenges if we got valid data
        if (data.active_challenges && data.active_challenges.length > 0) {
          setEnhancedChallenges(data.active_challenges);
          setChallengesLastUpdated(Date.now()); // Update timestamp when fetching challenges
        }
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
        // Update the local challenge state instead of refetching
        setEnhancedChallenges(prevChallenges => 
          prevChallenges.map(challenge => 
            challenge.challenge_id === challengeId 
              ? { 
                  ...challenge, 
                  current_value: challenge.current_value + dailyValue,
                  progress_percentage: data.completion_percentage,
                  is_completed: data.is_completed
                }
              : challenge
          )
        );
        setChallengesLastUpdated(Date.now()); // Update timestamp to prevent refetching
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

  // Can we see the backend at all? Runs before anything else so a connection
  // problem is reported as a connection problem.
  useEffect(() => {
    if (!isNativeApp()) return;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);
    fetch(`${API_BASE_URL.replace(/\/api$/, '')}/health`, { signal: controller.signal })
      .then((r) => { if (!r.ok) setNeedsServer(true); })
      .catch(() => setNeedsServer(true))
      .finally(() => clearTimeout(timer));
    return () => { clearTimeout(timer); controller.abort(); };
  }, []);

  useEffect(() => {
    // Check if user is already logged in
    const token = localStorage.getItem('token');
    if (token) {
      // Tell the server which timezone we are in before asking it anything,
      // so "today" means the same thing on both sides. On load rather than
      // only at login: existing accounts have no timezone stored, and people
      // travel.
      syncTimezone(API_BASE_URL);
      // Verify token and get user data
      fetchUserData();
      // Load dashboard data including Smart Challenges
      loadDashboardData();
    }
  }, []);

  // Roll the day over live. Leaving the app open past midnight used to keep
  // yesterday's totals on screen indefinitely - the numbers only changed when
  // something else happened to trigger a reload.
  useEffect(() => {
    if (!user) return undefined;
    return onLocalDayChange(() => {
      syncTimezone(API_BASE_URL);
      loadDashboardData();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);
  
  // Clear user data when user changes or logs out
  useEffect(() => {
    if (!user) {
      // User logged out, ensure all data is cleared
      clearUserData();
    }
  }, [user?.id]);

  // The old log-meal screen prefetched the whole food-item table to drive a
  // dropdown. LogMeal describes food in free text instead, so that request is
  // no longer made.

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
    // Fetch enhanced challenges when enhanced-challenges view is active (only if not recently loaded)
    if (activeView === 'enhanced-challenges') {
      if (enhancedChallenges.length === 0 || !challengesLastUpdated || Date.now() - challengesLastUpdated > 300000) { // 5 minutes
        fetchActiveChallenges();
      }
      fetchChallengeAnalytics();
    }
    // Fetch BudgetChef data when budgetchef view is active
    if (activeView === 'budgetchef') {
      // BudgetChef doesn't need to fetch existing data, it generates on demand
    }
  }, [activeView]);

  // Helper function to clear all user-specific state
  const clearUserData = () => {
    // Clear challenge-related state
    setEnhancedChallenges([]);
    setChallengeRecommendations([]);
    setChallengeAnalytics(null);
    setChallengesLastUpdated(null);
    
    // Clear food and meal-related state
    setFoodItems([]);
    setAiRecipes([]);
    setGeneratedRecipe(null);
    setChefgeniusRecipe(null);
    setFitmentorPlan(null);
    setBudgetchefPlan(null);
    setCulinaryexplorerPlan(null);
    setAdvancedMealPlan(null);
    setNutrientAnalysis(null);
    
    // Clear goals and progress
    setGoals([]);
    setProgressData({
      dates: [],
      calories: [],
      protein: [],
      carbs: [],
      fat: []
    });
    
    // Clear ML recommendations
    setMlRecommendations({
      foodRecommendations: [],
      cuisineRecommendations: [],
      varietySuggestions: [],
      macroAdjustments: [],
      mealTimingSuggestions: {}
    });
    
    // Clear chatbot state
    setChatbotMessages([]);
    
    // Clear dashboard data
    setDashboardData({
      dailyStats: null,
      recentMeals: [],
    timeline: [],
    adherenceHistory: [],
    adherenceSummary: null,
    todayAdherence: null,
      challenges: [],
      goals: []
    });
  };

  const loadDashboardData = async (skipChallenges = false) => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`
      };

      // Fetch daily stats
      // The user's local date, not toISOString() - that returns the UTC date,
      // so before ~05:30 IST this asked the server for yesterday.
      const today = localDateString();
      const statsResponse = await fetch(`${API_BASE_URL}/tracking/daily/${today}`, { headers });
      if (statsResponse.ok) {
        const stats = await statsResponse.json();
        setDashboardData(prev => ({ ...prev, dailyStats: stats }));
      }

      // Today's meals in time order plus the last 7 days of goal adherence.
      // One request rather than two so the timeline and the streak cannot
      // straddle a midnight rollover and disagree about which day it is.
      const dayResponse = await fetch(`${API_BASE_URL}/tracking/day?days=7`, { headers });
      if (dayResponse.ok) {
        const day = await dayResponse.json();
        setDashboardData(prev => ({
          ...prev,
          timeline: day.timeline || [],
          adherenceHistory: day.history || [],
          adherenceSummary: day.summary || null,
          todayAdherence: day.today || null,
          // Kept so older screens still reading recentMeals keep working.
          // They index `meal.food_item.name` WITHOUT a guard, so the nested
          // key has to be present or they throw rather than degrade.
          recentMeals: [...(day.timeline || [])].reverse().map(m => ({
            ...m,
            food_item: { id: m.id, name: m.name },
          })),
        }));
      }

      // Points for the sidebar, plus today's training answer for the
      // dashboard card. Best-effort - both degrade to a neutral state.
      fetch(`${API_BASE_URL}/profile`, { headers })
        .then(r => (r.ok ? r.json() : null))
        .then(d => {
          if (!d) return;
          if (d.points) setTotalPoints(d.points.total);
          if (d.workout) setWorkoutToday(d.workout);
        })
        .catch(() => {});

      fetch(`${API_BASE_URL}/profile/leaderboard?days=30&limit=20`, { headers })
        .then(r => (r.ok ? r.json() : null))
        .then(d => d?.success && setLeaderboard(d))
        .catch(() => {});

      // Active injuries, so the dashboard can ask for a check-in when one is
      // due. Failing quietly is fine - the prompt simply does not render.
      fetch(`${API_BASE_URL}/injuries`, { headers })
        .then(r => (r.ok ? r.json() : null))
        .then(d => d && setInjurySummary(d))
        .catch(() => {});

      // Fetch the active goal. Without this the dashboard had no targets to
      // compare against and silently fell back to generic placeholder numbers.
      const goalsResponse = await fetch(`${API_BASE_URL}/goals/?active_only=true`, { headers });
      if (goalsResponse.ok) {
        const goals = await goalsResponse.json();
        setDashboardData(prev => ({ ...prev, goals }));
      }

      // Weight history powers the trend and the progress-to-target bar.
      const weightResponse = await fetch(`${API_BASE_URL}/goals/weight/history?days=180`, { headers });
      if (weightResponse.ok) {
        const weight = await weightResponse.json();
        setDashboardData(prev => ({ ...prev, weight }));
      }

      // Challenges. Two things were wrong here and they compounded:
      //
      //   1. the response was stored in `enhancedChallenges` while the
      //      dashboard read `dashboardData.challenges`, which nothing wrote
      //   2. it hit /enhanced-challenges/active-challenges, which SUMS stored
      //      progress rows - so every challenge read 0% no matter what had
      //      been logged
      //
      // /challenges is the endpoint the Challenges screen uses: it recomputes
      // progress from the underlying meals on every read, so it cannot drift.
      // One source of truth for both screens.
      if (!skipChallenges && (!challengesLastUpdated || Date.now() - challengesLastUpdated > 30000)) {
        const challengesResponse = await fetch(`${API_BASE_URL}/challenges`, { headers });
        if (challengesResponse.ok) {
          const challengesData = await challengesResponse.json();
          const active = (challengesData.challenges || []).map(c => ({
            challenge_id: c.id,
            title: c.title,
            current_value: c.current,
            target_value: c.target,
            unit: c.unit,
            progress_percentage: c.percent,
            days_remaining: c.days_left,
            completed: c.completed,
            points: c.points,
          }));
          setEnhancedChallenges(active);
          setDashboardData(prev => ({ ...prev, challenges: active }));
          setChallengesLastUpdated(Date.now());
        }
      }

    } catch (error) {
      console.error('Error loading dashboard data:', error);
    }
  };

  // handleLogin / handleRegister moved into <Auth>, which posts to the same
  // endpoints and hands the token back through onAuthenticated.

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
    setSessionExpired(false);
    setCurrentView('login');
    setActiveView('dashboard');

    // Clear all user-specific state to prevent data leakage between users
    clearUserData();
  };

  /*
   * An expired token used to surface as whatever the screen happened to be
   * doing - the assistant rendered "Could not validate credentials" as though
   * the coach had said it, and other screens just went quiet. Neither tells
   * the user the one thing they need to know, which is to sign in again.
   *
   * Intercepting fetch catches it everywhere at once, including screens that
   * predate this and have no error handling of their own.
   */
  useEffect(() => {
    const original = window.fetch;

    window.fetch = async (...args) => {
      const response = await original(...args);
      try {
        const target = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
        const isOurApi = target.startsWith(API_BASE_URL);
        // A failed login is a wrong password, not an expired session.
        const isAuthAttempt = target.includes('/auth/login') || target.includes('/auth/register');

        if (response.status === 401 && isOurApi && !isAuthAttempt) {
          localStorage.removeItem('token');
          setUser(null);
          setSessionExpired(true);
          setCurrentView('login');
          setActiveView('dashboard');
          clearUserData();
        }
      } catch {
        // Never let the interceptor break the response it is inspecting.
      }
      return response;
    };

    return () => { window.fetch = original; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        // Refresh dashboard data but skip challenges to avoid overwriting them
        loadDashboardData(true);
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
          // Refresh dashboard data but skip challenges to avoid overwriting them
          loadDashboardData(true);
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

        // Decided here rather than in an effect on dashboardData, because
        // dashboardData.goals starts as [] before anything has loaded - so an
        // effect could not tell "no goals" from "not fetched yet" and would
        // redirect every user on every login.
        if (!routedToGoalSetup.current) {
          routedToGoalSetup.current = true;
          if (Array.isArray(userGoals) && userGoals.length === 0) {
            setActiveView('set-goals');
          }
        }
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
      // The user's local date, not toISOString() - that returns the UTC date,
      // so before ~05:30 IST this asked the server for yesterday.
      const today = localDateString();
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
      toastError('No food selected', 'Pick something from the list and try again.');
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
        
        // A toast, not alert(). In the Android app alert() renders the system
        // dialog - a grey box with the origin URL in the title - which stops
        // the app dead until it is dismissed and looks nothing like the rest
        // of the interface.
        toast(`${selectedRecommendation.name} logged`, {
          detail: `${(selectedRecommendation.calories * quickLogForm.quantity).toFixed(0)} kcal`
                + ` · ${(selectedRecommendation.protein_g * quickLogForm.quantity).toFixed(1)}g protein`
                + ` · ${quickLogForm.meal_type}`,
        });

        // Refresh dashboard data to show the new meal but skip challenges to avoid overwriting them
        console.log('Refreshing dashboard data...');
        await loadDashboardData(true);
        console.log('Dashboard refreshed!');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('❌ Error response:', errorData);
        setError(errorData.detail || `Failed to log meal (Status: ${response.status})`);
        toastError('Could not log that meal',
          typeof errorData.detail === 'string' ? errorData.detail : `Server returned ${response.status}.`);
      }
    } catch (error) {
      console.error('❌ Exception while logging meal:', error);
      console.error('Error stack:', error.stack);
      setError('Network error: ' + error.message);
      toastError('Could not reach the server', error.message);
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

  // renderLogin / renderRegister removed - the <Auth> component replaces both.

  // renderLogMeal removed - replaced by the <LogMeal> component.

  const renderSetGoals = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
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
              <h1 className="text-2xl font-bold font-display text-primary">Set Goals</h1>
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
                className="btn btn-secondary mr-4"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">View Progress</h1>
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
                className="btn btn-secondary mr-4"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold font-display text-primary">AI Recommendations</h1>
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
            backgroundColor: 'rgba(var(--black-rgb),0.8)',
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
              boxShadow: '0 25px 50px -12px rgba(var(--black-rgb), 0.25)',
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

  // ChefGenius - own view. Previously this UI was buried inside
  // renderAIRecipes, which meant the specialist had no nav entry of its own
  // while FitMentor / BudgetChef / Explorer each did.
  const renderChefGenius = () => (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
          ChefGenius
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: 4 }}>
          Tell it what you have and it builds a recipe around it.
        </p>
      </div>
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
                className="btn btn-secondary mr-4"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">AI Recipe Generator</h1>
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
        <div className="max-w-6xl mx-auto">
          

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
                className="btn btn-secondary mr-4"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">FitMentor - AI Workout Planner</h1>
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
                className="btn btn-secondary mr-4"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">BudgetChef - AI Budget Meal Planner</h1>
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
                className="btn btn-secondary mr-4"
              >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
              </button>
              <h1 className="text-2xl font-bold text-gray-900">CulinaryExplorer - Regional Cuisine Planner</h1>
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
    <div className="min-h-screen bg-gradient-premium">
      {/* Header */}
      <header className="app-header">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              {activeView !== 'dashboard' && (
                <button
                  onClick={() => setActiveView('dashboard')}
                  className="btn btn-secondary mr-4"
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
              <h1 className="header-title text-2xl font-display">Nutrition App</h1>
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
              <h3 className="text-lg font-bold font-display text-primary flex items-center">
                <Award className="mr-2" />
                Smart Challenges
              </h3>
              <button
                onClick={generateWeeklyChallenges}
                disabled={isGeneratingChallenges}
                className="btn btn-success btn-sm"
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
                  className="btn btn-success btn-sm"
                >
                  {isGeneratingChallenges ? 'Generating...' : 'Generate Challenges'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-8">
          <h2 className="text-xl font-bold mb-4 font-display text-primary">Quick Actions</h2>
          <div className="quick-actions">
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('log-meal')}
            >
              <span className="icon">🍽️</span>
              <span className="text">Log Meal</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('set-goals')}
            >
              <span className="icon">🎯</span>
              <span className="text">Set Goals</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('view-progress')}
            >
              <span className="icon">📊</span>
              <span className="text">View Progress</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('ml-recommendations')}
            >
              <span className="icon">🧠</span>
              <span className="text">AI Recommendations</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('ai-recipes')}
            >
              <span className="icon">👨‍🍳</span>
              <span className="text">AI Recipe Generator</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('fitmentor')}
            >
              <span className="icon">💪</span>
              <span className="text">FitMentor</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('budgetchef')}
            >
              <span className="icon">💰</span>
              <span className="text">BudgetChef</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('culinaryexplorer')}
            >
              <span className="icon">🌍</span>
              <span className="text">CulinaryExplorer</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('advancedmealplanner')}
            >
              <span className="icon">📅</span>
              <span className="text">Advanced Planner</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('chatbot')}
            >
              <span className="icon">🤖</span>
              <span className="text">AI Chatbot</span>
            </button>
            <button 
              className="quick-action-item"
              onClick={() => setActiveView('enhanced-challenges')}
            >
              <span className="icon">🏆</span>
              <span className="text">Smart Challenges</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  // renderChatbot removed - replaced by the <Assistant> component.

  const renderAdvancedMealPlanner = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
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
              <h1 className="text-2xl font-bold text-gray-900">Advanced Meal Planner</h1>
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
                <h1 className="text-2xl font-bold font-display text-primary flex items-center">
                  <Award className="mr-2" size={24} />
                  Smart Challenges
                </h1>
                <p className="text-secondary">Data-driven personalized challenges based on your nutrition and workout patterns</p>
              </div>
            </div>
            <button
              onClick={generateWeeklyChallenges}
              disabled={isGeneratingChallenges}
              className="btn btn-primary flex items-center"
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
                  className="btn btn-primary"
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

  // On a phone the commonest failure by far is "the backend is not reachable
  // from here" - wrong IP, laptop asleep, different WiFi. Without this the app
  // renders an empty dashboard and looks broken, with the real cause invisible.
  if (needsServer) {
    return <ServerSetup onSaved={() => window.location.reload()} />;
  }

  /*
   * A reset link was opened.
   *
   * Checked before everything else, including the signed-in branch: someone
   * who is still logged in on this device but has forgotten their password
   * must still be able to use the link, and landing them on the dashboard
   * instead would be baffling.
   *
   * The token is read from the query string and removed from the address bar
   * as soon as it is captured, so it does not sit in the browser history, get
   * copied out of a shared screen, or leak through a Referer header.
   */
  if (resetToken) {
    return (
      <ResetPassword
        apiBase={API_BASE_URL}
        token={resetToken}
        onDone={() => { setResetToken(''); setCurrentView('login'); }}
        onCancel={() => { setResetToken(''); setCurrentView('login'); }}
      />
    );
  }

  // Auth owns both sign-in and registration, including the switch between
  // them, so `currentView` no longer needs a separate 'register' branch.
  if (currentView === 'login' || currentView === 'register') {
    return (
      <Auth
        apiBase={API_BASE_URL}
        notice={sessionExpired ? 'Your session timed out. Sign in to pick up where you left off.' : ''}
        onAuthenticated={async (token) => {
          setSessionExpired(false);
          localStorage.setItem('token', token);
          // Wipe whatever the previous account left behind before pulling the
          // new user's data, or the dashboard briefly shows someone else's.
          clearUserData();
          await fetchUserData();
        }}
      />
    );
  }

  if (user) {
    // Views still using their original markup. These are rendered inside the
    // new shell and will be converted one at a time; until then the dark-theme
    // compatibility rules in index.css keep them legible.
    // Goal setting is now derived, not hand-entered: the user picks an
    // objective and the backend computes calories and macros. The old
    // renderSetGoals form (which asked for target_protein etc.) is replaced.
    const renderGoals = () => (
      <div style={{ display: 'grid', gap: '1.25rem' }}>
        <GoalSetup apiBase={API_BASE_URL} onGoalSaved={() => loadDashboardData()} />
        <WeightCheckIn apiBase={API_BASE_URL} onLogged={() => loadDashboardData()} />
        {/* Always here, injured or not. The dashboard card only appears when
            something is being tracked, so this is where a new one gets
            recorded - alongside the other things that shape your plans. */}
        <InjuryTracker
          data={injurySummary || { injuries: [] }}
          apiBase={API_BASE_URL}
          onChanged={() => loadDashboardData(true)}
        />
      </div>
    );

    const renderProgress = () => (
      <Progress
        apiBase={API_BASE_URL}
        dashboardData={dashboardData}
        onNavigate={setActiveView}
      />
    );

    const activeGoal =
      (dashboardData.goals || []).find((g) => g.is_active) || (dashboardData.goals || [])[0] || null;

    /*
     * A new account starts on the walkthrough, then on goal setup.
     *
     * Four of the first seven people who signed up did nothing afterwards -
     * no goal, no meal, no weigh-in. They landed on an empty dashboard with
     * fourteen destinations and nothing indicating which one mattered.
     *
     * The condition is "has no goal", not "is a new account", so it resolves
     * itself the moment a goal exists and never nags anyone twice. Dismissal
     * is remembered per user, so someone who wants to look around first is
     * not shown the introduction again on every render.
     */
    const hasGoal = (dashboardData.goals || []).length > 0;
    const welcomeKey = `kayosha.seenWelcome.${user.id}`;
    let seenWelcome = true;
    try {
      seenWelcome = localStorage.getItem(welcomeKey) === '1';
    } catch {
      // Private mode. Showing the introduction once per session is a far
      // smaller problem than crashing the whole app on a storage read.
      seenWelcome = false;
    }

    if (!hasGoal && !seenWelcome) {
      return (
        <AppShell
          activeView={activeView}
          onNavigate={setActiveView}
          user={user}
          points={totalPoints}
          onLogout={handleLogout}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
        >
          <Welcome
            name={user.full_name || user.username}
            onStart={() => {
              try { localStorage.setItem(welcomeKey, '1'); } catch { /* private mode */ }
              setActiveView('set-goals');
            }}
          />
        </AppShell>
      );
    }

    const legacyViews = {
      'log-meal': () => (
        <LogMeal
          apiBase={API_BASE_URL}
          onLogged={() => loadDashboardData(true)}
          calorieTarget={activeGoal?.target_calories || 0}
          consumedToday={dashboardData.dailyStats?.total_calories || 0}
        />
      ),
      'set-goals': renderGoals,
      'view-progress': renderProgress,
      'ml-recommendations': () => (
        <ForYou apiBase={API_BASE_URL} onNavigate={setActiveView} />
      ),
      // 'ai-recipes' intentionally unrouted - the page had no working content.
      chefgenius: () => (
        <ChefGenius apiBase={API_BASE_URL} onNavigate={setActiveView} />
      ),
      fitmentor: () => <FitMentor apiBase={API_BASE_URL} onNavigate={setActiveView} />,
      budgetchef: () => <BudgetChef apiBase={API_BASE_URL} onNavigate={setActiveView} />,
      culinaryexplorer: () => <Explorer apiBase={API_BASE_URL} onNavigate={setActiveView} />,
      advancedmealplanner: () => <MealPlanner apiBase={API_BASE_URL} onNavigate={setActiveView} />,
      chatbot: () => (
        <Assistant apiBase={API_BASE_URL} userName={user?.full_name || user?.username} />
      ),
      'enhanced-challenges': () => <Challenges apiBase={API_BASE_URL} />,
      profile: () => (
        <Profile
          apiBase={API_BASE_URL}
          user={user}
          onNavigate={setActiveView}
        />
      ),
    };

    const body =
      activeView === 'dashboard' || !legacyViews[activeView] ? (
        <Dashboard
          user={user}
          dashboardData={dashboardData}
          onNavigate={setActiveView}
          isLoading={isLoading}
          injuries={injurySummary}
          apiBase={API_BASE_URL}
          onInjuryChanged={() => loadDashboardData(true)}
          workout={workoutToday}
          board={leaderboard}
          onWorkoutLogged={() => loadDashboardData(true)}
        />
      ) : (
        legacyViews[activeView]()
      );

    return (
      <AppShell
        activeView={activeView}
        onNavigate={setActiveView}
        user={user}
        points={totalPoints}
        onLogout={handleLogout}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
      >
        {body}
      </AppShell>
    );
  }

  return null;
}

export default App;


