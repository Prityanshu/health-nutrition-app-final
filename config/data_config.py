"""
Data configuration for the nutrition app
"""
import os

# Dataset configuration
MFP_DATASET_PATH = r"C:\Users\prity\major-project-redo\mfp-diaries.tsv"
USE_MFP_DATASET = True  # Set to False to use sample data instead
MAX_RECORDS_TO_LOAD = 10000  # Increase this once you're comfortable with the system

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nutrition_app.db")

# Data loading preferences
LOAD_SAMPLE_CHALLENGES = True
REPLACE_EXISTING_FOOD_DATA = False  # Set to True to replace existing data

# Cuisine mapping preferences
CUISINE_KEYWORDS = {
    'indian': [
        'curry', 'dal', 'roti', 'naan', 'biryani', 'tandoor', 'masala', 
        'paneer', 'chicken tikka', 'samosa', 'dosa', 'idli', 'chutney',
        'basmati', 'ghee', 'lassi', 'chai', 'chapati', 'pulao', 'raita',
        'korma', 'vindaloo', 'butter chicken', 'palak', 'aloo'
    ],
    'chinese': [
        'stir fry', 'fried rice', 'lo mein', 'chow mein', 'dim sum', 'wonton',
        'sweet and sour', 'kung pao', 'szechuan', 'teriyaki', 'soy sauce',
        'tofu', 'bok choy', 'spring roll', 'dumpling', 'sesame', 'ginger'
    ],
    'mexican': [
        'taco', 'burrito', 'quesadilla', 'enchilada', 'salsa', 'guacamole',
        'tortilla', 'fajita', 'nachos', 'chimichanga', 'cilantro', 'jalapeño',
        'refried beans', 'pico de gallo', 'carnitas', 'carne asada'
    ],
    'italian': [
        'pasta', 'pizza', 'spaghetti', 'lasagna', 'risotto', 'pesto',
        'marinara', 'mozzarella', 'parmesan', 'basil', 'oregano', 'prosciutto',
        'carbonara', 'alfredo', 'gnocchi', 'bruschetta', 'caprese'
    ],
    'mediterranean': [
        'hummus', 'falafel', 'olive', 'feta', 'pita', 'tzatziki',
        'kebab', 'couscous', 'tahini', 'greek yogurt', 'lemon', 'herbs',
        'shawarma', 'gyros', 'tabouleh', 'baba ganoush'
    ]
}