"""
MyFitnessPal Dataset Loader for Nutrition App
"""
import pandas as pd
import numpy as np
import os
import sys
import re
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base, FoodItem, Challenge
from config.data_config import MFP_DATASET_PATH, CUISINE_KEYWORDS
from scripts.mfp_parser import MFPDiaryParser

class MFPDatasetLoader:
    """Loads and processes MyFitnessPal dataset into the nutrition app database"""
    
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.db: Session = SessionLocal()
        self.food_items_loaded = 0
        self.challenges_loaded = 0
        
    def __del__(self):
        """Clean up database connection"""
        if hasattr(self, 'db'):
            self.db.close()
    
    def analyze_dataset_structure(self) -> Dict:
        """Analyze the dataset structure without loading data"""
        print("🔍 Analyzing dataset structure...")
        
        if not os.path.exists(self.dataset_path):
            print(f"❌ Dataset file not found: {self.dataset_path}")
            return {}
        
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(self.dataset_path, sep='\t', encoding=encoding, nrows=1000, low_memory=False)
                    print(f"✅ Successfully read with encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                print("❌ Could not read file with any encoding")
                return {}
            
            analysis = {
                'total_rows': len(pd.read_csv(self.dataset_path, sep='\t', encoding=encoding, low_memory=False)),
                'columns': list(df.columns),
                'sample_data': df.head(3).to_dict('records'),
                'encoding': encoding
            }
            
            print(f"📊 Dataset Analysis:")
            print(f"   Total rows: {analysis['total_rows']:,}")
            print(f"   Columns ({len(analysis['columns'])}): {analysis['columns']}")
            print(f"   Encoding: {encoding}")
            
            # Show sample data
            print(f"\n📋 Sample data (first 3 rows):")
            for i, row in enumerate(analysis['sample_data'], 1):
                print(f"   Row {i}: {dict(list(row.items())[:5])}")  # Show first 5 columns
            
            return analysis
            
        except Exception as e:
            print(f"❌ Error analyzing dataset: {e}")
            return {}
    
    def load_and_process_data(self, max_records: int = 10000) -> bool:
        """Load and process the MFP dataset"""
        print(f"🚀 Loading MyFitnessPal dataset (max {max_records:,} records)...")
        
        if not os.path.exists(self.dataset_path):
            print(f"❌ Dataset file not found: {self.dataset_path}")
            return False
        
        try:
            # Create database tables
            Base.metadata.create_all(bind=engine)
            
            # Use the specialized MFP parser
            parser = MFPDiaryParser(self.dataset_path)
            food_items = parser.parse_dataset(max_records)
            
            if not food_items:
                print("❌ No food items extracted from dataset")
                return False
            
            print(f"📊 Extracted {len(food_items):,} food items from MFP diary")
            
            # Process and load food items
            success = self._load_parsed_food_items(food_items)
            
            if success:
                print(f"✅ Successfully loaded {self.food_items_loaded:,} food items")
                return True
            else:
                print("❌ Failed to load food items")
                return False
                
        except Exception as e:
            print(f"❌ Error loading dataset: {e}")
            return False
    
    def _load_dataset(self, max_records: int) -> Optional[pd.DataFrame]:
        """Load the dataset with proper encoding handling"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(self.dataset_path, sep='\t', encoding=encoding, 
                                   nrows=max_records, low_memory=False)
                    print(f"✅ Successfully loaded with encoding: {encoding}")
                    return df
                except UnicodeDecodeError:
                    continue
            
            print("❌ Could not read file with any encoding")
            return None
            
        except Exception as e:
            print(f"❌ Error loading dataset: {e}")
            return None
    
    def _load_parsed_food_items(self, food_items: List[Dict]) -> bool:
        """Process and load parsed food items into database"""
        try:
            print(f"🍎 Processing {len(food_items):,} food items...")
            
            # Process in batches
            batch_size = 1000
            total_batches = len(food_items) // batch_size + (1 if len(food_items) % batch_size > 0 else 0)
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(food_items))
                batch_items = food_items[start_idx:end_idx]
                
                self._process_parsed_batch(batch_items)
                
                if (batch_num + 1) % 10 == 0:
                    print(f"📦 Processed batch {batch_num + 1}/{total_batches} ({self.food_items_loaded:,} items loaded)")
            
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"❌ Error loading food items: {e}")
            self.db.rollback()
            return False
    
    def _process_parsed_batch(self, batch_items: List[Dict]):
        """Process a batch of parsed food items"""
        for item in batch_items:
            try:
                # Determine cuisine type
                cuisine_type = self._determine_cuisine(item['name'])
                
                # Estimate health properties
                health_props = self._estimate_health_properties_from_item(item)
                
                # Estimate cost and complexity
                estimated_cost = self._estimate_cost_from_item(item)
                complexity_level = self._estimate_complexity_from_item(item)
                
                # Create food item
                food_item = FoodItem(
                    name=item['name'][:200],  # Limit name length
                    calories=float(item.get('calories', 100)),
                    protein_g=float(item.get('protein_g', 5)),
                    carbs_g=float(item.get('carbs_g', 15)),
                    fat_g=float(item.get('fat_g', 3)),
                    fiber_g=float(item.get('fiber_g', 2)),
                    sodium_mg=float(item.get('sodium_mg', 200)),
                    sugar_g=float(item.get('sugar_g', 5)),
                    cuisine_type=cuisine_type,
                    diabetic_friendly=health_props['diabetic_friendly'],
                    low_sodium=health_props['low_sodium'],
                    cost=estimated_cost,
                    prep_complexity=complexity_level
                )
                
                self.db.add(food_item)
                self.food_items_loaded += 1
                
            except Exception as e:
                print(f"⚠️ Error processing item {item.get('name', 'Unknown')}: {e}")
                continue
    
    def _load_food_items(self, df: pd.DataFrame) -> bool:
        """Process and load food items into database"""
        try:
            # Map column names to standard names
            column_mapping = self._map_columns(df.columns)
            print(f"📋 Column mapping: {column_mapping}")
            
            # Rename columns
            df = df.rename(columns=column_mapping)
            
            # Clean and validate data
            df = self._clean_data(df)
            
            # Process in batches
            batch_size = 1000
            total_batches = len(df) // batch_size + (1 if len(df) % batch_size > 0 else 0)
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(df))
                batch_df = df.iloc[start_idx:end_idx]
                
                self._process_batch(batch_df)
                
                if (batch_num + 1) % 10 == 0:
                    print(f"📦 Processed batch {batch_num + 1}/{total_batches} ({self.food_items_loaded:,} items loaded)")
            
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"❌ Error loading food items: {e}")
            self.db.rollback()
            return False
    
    def _map_columns(self, columns: List[str]) -> Dict[str, str]:
        """Map dataset columns to our database schema"""
        mapping = {}
        
        # Common column name variations
        name_variations = ['food', 'item', 'food_item', 'name', 'description']
        calories_variations = ['calories', 'cal', 'energy', 'kcal']
        protein_variations = ['protein', 'protein(g)', 'protein_g']
        carbs_variations = ['carbs', 'carbohydrates', 'carb', 'carbs(g)', 'carbohydrates(g)']
        fat_variations = ['fat', 'fat(g)', 'total_fat']
        fiber_variations = ['fiber', 'dietary_fiber', 'fiber(g)']
        sodium_variations = ['sodium', 'sodium(mg)', 'sodium_mg']
        sugar_variations = ['sugar', 'sugars', 'sugar(g)']
        
        for col in columns:
            col_lower = col.lower().strip()
            
            if any(var in col_lower for var in name_variations):
                mapping[col] = 'name'
            elif any(var in col_lower for var in calories_variations):
                mapping[col] = 'calories'
            elif any(var in col_lower for var in protein_variations):
                mapping[col] = 'protein_g'
            elif any(var in col_lower for var in carbs_variations):
                mapping[col] = 'carbs_g'
            elif any(var in col_lower for var in fat_variations):
                mapping[col] = 'fat_g'
            elif any(var in col_lower for var in fiber_variations):
                mapping[col] = 'fiber_g'
            elif any(var in col_lower for var in sodium_variations):
                mapping[col] = 'sodium_mg'
            elif any(var in col_lower for var in sugar_variations):
                mapping[col] = 'sugar_g'
        
        return mapping
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate the dataset"""
        print("🧹 Cleaning dataset...")
        
        # Remove rows with missing essential data
        df = df.dropna(subset=['name'], how='any')
        
        # Clean food names
        df['name'] = df['name'].astype(str).str.strip()
        df = df[df['name'].str.len() > 2]  # Remove very short names
        
        # Remove duplicates based on name
        df = df.drop_duplicates(subset=['name'], keep='first')
        
        # Clean numeric columns
        numeric_columns = ['calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g', 'sodium_mg', 'sugar_g']
        
        for col in numeric_columns:
            if col in df.columns:
                # Convert to numeric, errors become NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Remove outliers (values that are too extreme)
                if col == 'calories':
                    df = df[(df[col] > 0) & (df[col] < 5000)]
                elif col in ['protein_g', 'carbs_g', 'fat_g']:
                    df = df[(df[col] >= 0) & (df[col] < 1000)]
                elif col == 'fiber_g':
                    df = df[(df[col] >= 0) & (df[col] < 100)]
                elif col == 'sodium_mg':
                    df = df[(df[col] >= 0) & (df[col] < 50000)]
                elif col == 'sugar_g':
                    df = df[(df[col] >= 0) & (df[col] < 500)]
        
        # Fill missing values with reasonable defaults
        defaults = {
            'calories': 100,
            'protein_g': 5,
            'carbs_g': 15,
            'fat_g': 3,
            'fiber_g': 2,
            'sodium_mg': 200,
            'sugar_g': 5
        }
        
        for col, default in defaults.items():
            if col in df.columns:
                df[col] = df[col].fillna(default)
        
        print(f"✅ Cleaned dataset: {len(df):,} valid food items")
        return df
    
    def _process_batch(self, batch_df: pd.DataFrame):
        """Process a batch of food items"""
        for _, row in batch_df.iterrows():
            try:
                # Determine cuisine type
                cuisine_type = self._determine_cuisine(row['name'])
                
                # Estimate health properties
                health_props = self._estimate_health_properties(row)
                
                # Estimate cost and complexity
                estimated_cost = self._estimate_cost(row)
                complexity_level = self._estimate_complexity(row)
                
                # Create food item
                food_item = FoodItem(
                    name=row['name'][:200],  # Limit name length
                    calories=float(row.get('calories', 100)),
                    protein_g=float(row.get('protein_g', 5)),
                    carbs_g=float(row.get('carbs_g', 15)),
                    fat_g=float(row.get('fat_g', 3)),
                    fiber_g=float(row.get('fiber_g', 2)),
                    sodium_mg=float(row.get('sodium_mg', 200)),
                    sugar_g=float(row.get('sugar_g', 5)),
                    cuisine_type=cuisine_type,
                    diabetic_friendly=health_props['diabetic_friendly'],
                    low_sodium=health_props['low_sodium'],
                    cost=estimated_cost,
                    prep_complexity=complexity_level
                )
                
                self.db.add(food_item)
                self.food_items_loaded += 1
                
            except Exception as e:
                print(f"⚠️ Error processing item {row.get('name', 'Unknown')}: {e}")
                continue
    
    def _determine_cuisine(self, food_name: str) -> str:
        """Determine cuisine type based on food name"""
        food_lower = food_name.lower()
        
        for cuisine, keywords in CUISINE_KEYWORDS.items():
            if any(keyword in food_lower for keyword in keywords):
                return cuisine
        
        return 'other'
    
    def _estimate_health_properties_from_item(self, item: Dict) -> Dict[str, bool]:
        """Estimate health properties based on nutritional values from parsed item"""
        calories = float(item.get('calories', 100))
        fiber = float(item.get('fiber_g', 2))
        sodium = float(item.get('sodium_mg', 200))
        sugar = float(item.get('sugar_g', 5))
        fat = float(item.get('fat_g', 3))
        
        return {
            'diabetic_friendly': sugar < 10 and fiber > 3,
            'low_sodium': sodium < 200
        }
    
    def _estimate_cost_from_item(self, item: Dict) -> float:
        """Estimate cost per serving from parsed item"""
        base_cost = 2.0  # Base cost
        
        # Adjust based on calories
        calories = float(item.get('calories', 100))
        if calories > 400:
            base_cost *= 1.2
        elif calories < 100:
            base_cost *= 1.5
        
        return round(base_cost, 2)
    
    def _estimate_complexity_from_item(self, item: Dict) -> str:
        """Estimate preparation complexity from parsed item"""
        nutrients = [
            float(item.get('protein_g', 5)),
            float(item.get('carbs_g', 15)),
            float(item.get('fat_g', 3)),
            float(item.get('fiber_g', 2))
        ]
        
        complexity_score = sum(nutrients)
        
        if complexity_score < 10:
            return 'low'
        elif complexity_score < 25:
            return 'medium'
        else:
            return 'high'
    
    def _estimate_health_properties(self, row: pd.Series) -> Dict[str, bool]:
        """Estimate health properties based on nutritional values"""
        calories = float(row.get('calories', 100))
        fiber = float(row.get('fiber_g', 2))
        sodium = float(row.get('sodium_mg', 200))
        sugar = float(row.get('sugar_g', 5))
        fat = float(row.get('fat_g', 3))
        
        return {
            'diabetic_friendly': sugar < 10 and fiber > 3,
            'low_sodium': sodium < 200
        }
    
    def _estimate_cost(self, row: pd.Series) -> float:
        """Estimate cost per serving (rough estimate)"""
        # Simple heuristic based on food type and complexity
        base_cost = 2.0  # Base cost
        
        # Adjust based on calories (higher calorie foods tend to be cheaper)
        calories = float(row.get('calories', 100))
        if calories > 400:
            base_cost *= 1.2
        elif calories < 100:
            base_cost *= 1.5
        
        return round(base_cost, 2)
    
    def _estimate_complexity(self, row: pd.Series) -> str:
        """Estimate preparation complexity"""
        # Simple heuristic based on nutritional complexity
        nutrients = [
            float(row.get('protein_g', 5)),
            float(row.get('carbs_g', 15)),
            float(row.get('fat_g', 3)),
            float(row.get('fiber_g', 2))
        ]
        
        complexity_score = sum(nutrients)
        
        if complexity_score < 10:
            return 'low'
        elif complexity_score < 25:
            return 'medium'
        else:
            return 'high'

def load_sample_challenges():
    """Load sample gamification challenges"""
    db = SessionLocal()
    try:
        # Check if challenges already exist
        existing_challenges = db.query(Challenge).count()
        if existing_challenges > 0:
            print("✅ Challenges already loaded")
            return
        
        challenges = [
            {
                'name': 'Week Warrior',
                'description': 'Log meals for 7 consecutive days',
                'reward_points': 100,
                'is_active': True
            },
            {
                'name': 'Protein Power',
                'description': 'Meet your protein goal for 5 days',
                'reward_points': 75,
                'is_active': True
            },
            {
                'name': 'Hydration Hero',
                'description': 'Drink 8 glasses of water daily for a week',
                'reward_points': 50,
                'is_active': True
            }
        ]
        
        for challenge_data in challenges:
            challenge = Challenge(**challenge_data)
            db.add(challenge)
        
        db.commit()
        print("✅ Loaded sample challenges")
        
    except Exception as e:
        print(f"❌ Error loading challenges: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main function for command-line usage"""
    print("🍎 MyFitnessPal Dataset Loader")
    print("=" * 50)
    
    if not os.path.exists(MFP_DATASET_PATH):
        print(f"❌ Dataset file not found: {MFP_DATASET_PATH}")
        print("Please check the path in config/data_config.py")
        return
    
    print("Choose an option:")
    print("1. Load MFP dataset into database")
    print("2. Analyze dataset structure only")
    print("3. Load sample challenges only")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    loader = MFPDatasetLoader(MFP_DATASET_PATH)
    
    if choice == '1':
        success = loader.load_and_process_data()
        if success:
            load_sample_challenges()
            print("\n🎉 Dataset loading complete!")
            print("You can now start the application with: uvicorn main:app --reload")
        else:
            print("\n❌ Dataset loading failed")
    
    elif choice == '2':
        analysis = loader.analyze_dataset_structure()
        if analysis:
            print("\n✅ Analysis complete!")
    
    elif choice == '3':
        load_sample_challenges()
    
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
