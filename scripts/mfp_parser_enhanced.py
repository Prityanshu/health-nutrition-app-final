#!/usr/bin/env python3
"""
Enhanced MyFitnessPal Dataset Parser
Handles the complex JSON structure of the MFP dataset
"""
import json
import pandas as pd
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add parent directory to path to import app modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, FoodItem, PrepComplexity, engine, Base

class EnhancedMFPParser:
    """Enhanced parser for MyFitnessPal dataset with complex JSON structure"""
    
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.db = SessionLocal()
        self.food_items_loaded = 0
        self.processed_entries = 0
        
    def __del__(self):
        """Clean up database connection"""
        if hasattr(self, 'db'):
            self.db.close()
    
    def parse_dataset(self, max_records: int = 10000) -> bool:
        """Parse the MFP dataset and load food items"""
        print(f"🚀 Parsing MyFitnessPal dataset (max {max_records:,} records)...")
        
        if not os.path.exists(self.dataset_path):
            print(f"❌ Dataset file not found: {self.dataset_path}")
            return False
        
        try:
            # Create database tables
            Base.metadata.create_all(bind=engine)
            
            # Read the TSV file
            df = pd.read_csv(self.dataset_path, sep='\t', low_memory=False)
            print(f"📊 Dataset loaded. Shape: {df.shape}")
            print(f"📋 Columns: {list(df.columns)}")
            
            # Process the data
            food_items = self._extract_food_items(df, max_records)
            
            if not food_items:
                print("❌ No food items extracted from dataset")
                return False
            
            print(f"🍽️ Extracted {len(food_items):,} unique food items")
            
            # Load into database
            success = self._load_food_items(food_items)
            
            if success:
                print(f"✅ Successfully loaded {self.food_items_loaded:,} food items")
                return True
            else:
                print("❌ Failed to load food items")
                return False
                
        except Exception as e:
            print(f"❌ Error parsing dataset: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _extract_food_items(self, df: pd.DataFrame, max_records: int) -> List[Dict[str, Any]]:
        """Extract food items from the complex JSON structure"""
        food_items = {}
        processed_count = 0
        
        # The dataset has columns: ['1', '2014-09-14', 'JSON_MEAL_DATA', 'JSON_TOTALS']
        # We need to parse the JSON_MEAL_DATA column
        
        for idx, row in df.iterrows():
            if processed_count >= max_records:
                break
                
            try:
                # Get the meal data (3rd column)
                meal_data_str = row.iloc[2] if len(row) > 2 else None
                
                if pd.isna(meal_data_str) or not meal_data_str:
                    continue
                
                # Parse the JSON meal data
                meal_data = json.loads(meal_data_str)
                
                # Extract dishes from the meal
                if isinstance(meal_data, list) and len(meal_data) > 0:
                    meal_info = meal_data[0]  # First meal entry
                    
                    if 'dishes' in meal_info:
                        for dish in meal_info['dishes']:
                            if 'name' in dish and 'nutritions' in dish:
                                food_item = self._parse_dish(dish)
                                if food_item:
                                    # Use name as key to avoid duplicates
                                    food_items[food_item['name']] = food_item
                                    processed_count += 1
                
                self.processed_entries += 1
                
                if self.processed_entries % 1000 == 0:
                    print(f"📈 Processed {self.processed_entries:,} entries, found {len(food_items):,} unique foods")
                    
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                # Skip malformed entries
                continue
            except Exception as e:
                print(f"⚠️ Error processing row {idx}: {e}")
                continue
        
        print(f"📊 Processing complete: {self.processed_entries:,} entries processed, {len(food_items):,} unique foods found")
        return list(food_items.values())
    
    def _parse_dish(self, dish: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single dish from the meal data"""
        try:
            name = dish.get('name', '').strip()
            if not name or len(name) < 3:
                return None
            
            # Clean the name
            name = self._clean_food_name(name)
            
            # Extract nutrition data
            nutritions = dish.get('nutritions', [])
            nutrition_dict = {}
            
            for nut in nutritions:
                if 'name' in nut and 'value' in nut:
                    nut_name = nut['name'].lower()
                    nut_value = nut['value']
                    
                    # Convert to numeric
                    try:
                        nut_value = float(str(nut_value).replace(',', ''))
                    except (ValueError, TypeError):
                        nut_value = 0
                    
                    nutrition_dict[nut_name] = nut_value
            
            # Map nutrition values
            calories = nutrition_dict.get('calories', 0)
            protein_g = nutrition_dict.get('protein', 0)
            carbs_g = nutrition_dict.get('carbs', 0)
            fat_g = nutrition_dict.get('fat', 0)
            sodium_mg = nutrition_dict.get('sodium', 0)
            sugar_g = nutrition_dict.get('sugar', 0)
            
            # Skip items with no calories
            if calories <= 0:
                return None
            
            # Estimate missing values
            fiber_g = self._estimate_fiber(name, carbs_g)
            
            # Categorize the food
            cuisine_type = self._categorize_cuisine(name)
            prep_complexity = self._estimate_prep_complexity(name)
            low_sodium, diabetic_friendly, hypertension_friendly = self._determine_health_flags(name, sodium_mg)
            
            # Estimate cost and GI
            cost = self._estimate_cost(name, calories)
            gi = self._estimate_gi(name, carbs_g, fiber_g)
            
            # Generate tags
            tags = self._generate_tags(name, protein_g, carbs_g, fat_g, fiber_g)
            
            return {
                'name': name[:100],  # Limit name length
                'cuisine_type': cuisine_type,
                'calories': calories,
                'protein_g': protein_g,
                'carbs_g': carbs_g,
                'fat_g': fat_g,
                'fiber_g': fiber_g,
                'sodium_mg': sodium_mg,
                'sugar_g': sugar_g,
                'cost': cost,
                'gi': gi,
                'low_sodium': low_sodium,
                'diabetic_friendly': diabetic_friendly,
                'hypertension_friendly': hypertension_friendly,
                'prep_complexity': prep_complexity,
                'ingredients': f"Main ingredient: {name.split(',')[0]}",
                'tags': tags
            }
            
        except Exception as e:
            print(f"⚠️ Error parsing dish: {e}")
            return None
    
    def _clean_food_name(self, name: str) -> str:
        """Clean and standardize food names"""
        # Remove common prefixes and suffixes
        name = re.sub(r'^[^a-zA-Z]*', '', name)  # Remove leading non-letters
        name = re.sub(r'[^a-zA-Z0-9\s\-.,&()]+', '', name)  # Keep only alphanumeric and common chars
        
        # Remove size/quantity info in parentheses at the end
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name)
        
        # Remove brand names (common patterns)
        name = re.sub(r'^[A-Z][a-z]+\s*-\s*', '', name)  # Brand - Product
        name = re.sub(r'^[A-Z][a-z]+\s*', '', name)  # Brand Product
        
        # Clean up extra spaces
        name = ' '.join(name.split())
        
        # Title case
        name = name.title()
        
        return name.strip()
    
    def _estimate_fiber(self, name: str, carbs_g: float) -> float:
        """Estimate fiber content based on food name and carbs"""
        name_lower = name.lower()
        
        # High fiber foods
        if any(word in name_lower for word in ['whole grain', 'brown rice', 'oats', 'quinoa', 'lentils', 'beans', 'vegetables', 'fruits']):
            return min(carbs_g * 0.3, 15)  # Up to 30% of carbs as fiber
        
        # Medium fiber foods
        if any(word in name_lower for word in ['bread', 'cereal', 'pasta', 'rice']):
            return min(carbs_g * 0.1, 5)  # Up to 10% of carbs as fiber
        
        # Default estimation
        return min(carbs_g * 0.05, 3)  # Up to 5% of carbs as fiber
    
    def _categorize_cuisine(self, food_name: str) -> str:
        """Categorize food by cuisine type"""
        name_lower = food_name.lower()
        
        # Indian cuisine keywords
        indian_keywords = [
            'curry', 'dal', 'roti', 'naan', 'biryani', 'tandoor', 'masala', 
            'paneer', 'chicken tikka', 'samosa', 'dosa', 'idli', 'chutney',
            'basmati', 'ghee', 'lassi', 'chai', 'chapati', 'pulao', 'raita',
            'korma', 'vindaloo', 'butter chicken', 'palak', 'aloo'
        ]
        
        # Chinese cuisine keywords
        chinese_keywords = [
            'stir fry', 'fried rice', 'lo mein', 'chow mein', 'dim sum', 'wonton',
            'sweet and sour', 'kung pao', 'szechuan', 'teriyaki', 'soy sauce',
            'tofu', 'bok choy', 'spring roll', 'dumpling', 'sesame', 'ginger'
        ]
        
        # Mexican cuisine keywords
        mexican_keywords = [
            'taco', 'burrito', 'quesadilla', 'enchilada', 'salsa', 'guacamole',
            'tortilla', 'fajita', 'nachos', 'chimichanga', 'cilantro', 'jalapeño',
            'refried beans', 'pico de gallo', 'carnitas', 'carne asada'
        ]
        
        # Italian cuisine keywords
        italian_keywords = [
            'pasta', 'pizza', 'spaghetti', 'lasagna', 'risotto', 'pesto',
            'marinara', 'mozzarella', 'parmesan', 'basil', 'oregano', 'prosciutto',
            'carbonara', 'alfredo', 'gnocchi', 'bruschetta', 'caprese'
        ]
        
        # Mediterranean cuisine keywords
        mediterranean_keywords = [
            'hummus', 'falafel', 'olive', 'feta', 'pita', 'tzatziki',
            'kebab', 'couscous', 'tahini', 'greek yogurt', 'lemon', 'herbs',
            'shawarma', 'gyros', 'tabouleh', 'baba ganoush'
        ]
        
        # Check for cuisine matches
        for keyword in indian_keywords:
            if keyword in name_lower:
                return 'indian'
        
        for keyword in chinese_keywords:
            if keyword in name_lower:
                return 'chinese'
        
        for keyword in mexican_keywords:
            if keyword in name_lower:
                return 'mexican'
        
        for keyword in italian_keywords:
            if keyword in name_lower:
                return 'italian'
        
        for keyword in mediterranean_keywords:
            if keyword in name_lower:
                return 'mediterranean'
        
        return 'mixed'  # Default category
    
    def _estimate_prep_complexity(self, food_name: str) -> str:
        """Estimate preparation complexity"""
        name_lower = food_name.lower()
        
        # High complexity indicators
        high_complexity = [
            'homemade', 'scratch', 'fresh', 'marinated', 'stuffed', 'layered',
            'casserole', 'roasted', 'braised', 'slow cooked', 'fermented'
        ]
        
        # Low complexity indicators  
        low_complexity = [
            'instant', 'microwave', 'frozen', 'canned', 'packaged', 'ready',
            'quick', 'simple', 'raw', 'fresh fruit', 'fresh vegetable'
        ]
        
        for indicator in high_complexity:
            if indicator in name_lower:
                return PrepComplexity.HIGH
        
        for indicator in low_complexity:
            if indicator in name_lower:
                return PrepComplexity.LOW
        
        return PrepComplexity.MEDIUM  # Default
    
    def _determine_health_flags(self, food_name: str, sodium_mg: float) -> tuple:
        """Determine health condition flags"""
        name_lower = food_name.lower()
        
        # Low sodium foods
        low_sodium = True
        if sodium_mg > 400:  # High sodium threshold
            low_sodium = False
        
        high_sodium_indicators = [
            'canned', 'processed', 'pickled', 'cured', 'smoked', 'salted',
            'soy sauce', 'teriyaki', 'bbq sauce', 'ketchup'
        ]
        
        for indicator in high_sodium_indicators:
            if indicator in name_lower:
                low_sodium = False
                break
        
        # Diabetic friendly foods
        diabetic_friendly = True
        high_sugar_indicators = [
            'cake', 'cookie', 'candy', 'chocolate', 'ice cream', 'donut',
            'pie', 'sweet', 'syrup', 'honey', 'sugar', 'frosting'
        ]
        
        for indicator in high_sugar_indicators:
            if indicator in name_lower:
                diabetic_friendly = False
                break
        
        # Hypertension friendly (similar to low sodium)
        hypertension_friendly = low_sodium
        
        return low_sodium, diabetic_friendly, hypertension_friendly
    
    def _estimate_cost(self, food_name: str, calories: float) -> float:
        """Estimate food cost"""
        name_lower = food_name.lower()
        
        # Expensive foods
        if any(word in name_lower for word in ['salmon', 'tuna', 'lobster', 'crab', 'shrimp', 'steak', 'organic']):
            return min(15.0, calories * 0.01)
        
        # Moderate cost foods
        if any(word in name_lower for word in ['chicken', 'beef', 'pork', 'fish', 'cheese']):
            return min(8.0, calories * 0.007)
        
        # Cheap foods
        if any(word in name_lower for word in ['rice', 'bread', 'pasta', 'beans', 'lentils']):
            return min(3.0, calories * 0.003)
        
        # Default cost
        return min(5.0, calories * 0.005)
    
    def _estimate_gi(self, food_name: str, carbs_g: float, fiber_g: float) -> int:
        """Estimate glycemic index"""
        name_lower = food_name.lower()
        
        # Low GI foods
        if any(word in name_lower for word in ['oats', 'quinoa', 'lentils', 'beans', 'nuts', 'vegetables']):
            return 35
        
        # High GI foods
        if any(word in name_lower for word in ['white bread', 'white rice', 'potato', 'sugar', 'candy']):
            return 70
        
        # Estimate based on fiber content
        if fiber_g > 5:
            return 40  # High fiber = lower GI
        elif fiber_g < 2 and carbs_g > 20:
            return 65  # Low fiber, high carbs = higher GI
        
        return 50  # Default moderate GI
    
    def _generate_tags(self, name: str, protein_g: float, carbs_g: float, fat_g: float, fiber_g: float) -> str:
        """Generate tags based on nutritional content"""
        tags = []
        
        # Nutritional tags
        if protein_g > 15:
            tags.append("high_protein")
        if fiber_g > 5:
            tags.append("high_fiber")
        if fat_g < 3:
            tags.append("low_fat")
        if carbs_g < 10:
            tags.append("low_carb")
        
        # Food type tags
        name_lower = name.lower()
        if any(word in name_lower for word in ['vegetable', 'veggie', 'salad', 'greens']):
            tags.append("vegetable")
        if any(word in name_lower for word in ['fruit', 'berry', 'apple', 'banana', 'orange']):
            tags.append("fruit")
        if any(word in name_lower for word in ['whole grain', 'brown rice', 'oats', 'quinoa']):
            tags.append("whole_grain")
        if 'organic' in name_lower:
            tags.append("organic")
        
        return ','.join(tags)
    
    def _load_food_items(self, food_items: List[Dict[str, Any]]) -> bool:
        """Load food items into the database"""
        print("💾 Loading food items into database...")
        
        try:
            # Clear existing food items
            self.db.execute(text("DELETE FROM food_items"))
            self.db.commit()
            print("🗑️ Cleared existing food items")
            
            batch_size = 1000
            total_loaded = 0
            
            for i in range(0, len(food_items), batch_size):
                batch = food_items[i:i + batch_size]
                db_items = []
                
                for item_data in batch:
                    try:
                        food_item = FoodItem(**item_data)
                        db_items.append(food_item)
                    except Exception as e:
                        print(f"⚠️ Error creating food item: {e}")
                        continue
                
                # Bulk insert the batch
                if db_items:
                    self.db.add_all(db_items)
                    self.db.commit()
                    total_loaded += len(db_items)
                    print(f"📦 Loaded batch {i//batch_size + 1}: {len(db_items)} items (Total: {total_loaded})")
            
            self.food_items_loaded = total_loaded
            print(f"✅ Successfully loaded {total_loaded:,} food items")
            return True
            
        except Exception as e:
            print(f"❌ Error loading food items: {e}")
            self.db.rollback()
            return False

def main():
    """Main function to load the MFP dataset"""
    dataset_path = r"C:\Users\prity\major-project-redo\mfp-diaries.tsv"
    
    if not os.path.exists(dataset_path):
        print(f"❌ Dataset file not found: {dataset_path}")
        return
    
    # Initialize the parser
    parser = EnhancedMFPParser(dataset_path)
    
    # Parse and load the dataset
    success = parser.parse_dataset(max_records=20000)  # Load more records
    
    if success:
        print("\n🎉 MyFitnessPal dataset loaded successfully!")
        print("🍽️ Your nutrition app now has access to real food data!")
        print("\nNext steps:")
        print("1. Start the application: python main.py")
        print("2. Test the ML recommendations and meal planning features")
        print("3. All features will now use the MyFitnessPal dataset")
    else:
        print("❌ Failed to load MyFitnessPal dataset")

if __name__ == "__main__":
    main()

