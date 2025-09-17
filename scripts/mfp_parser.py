"""
MyFitnessPal Diary Parser
Parses the specific JSON format from MFP diary exports
"""
import json
import pandas as pd
from typing import Dict, List, Optional
from collections import defaultdict

class MFPDiaryParser:
    """Parses MyFitnessPal diary export format"""
    
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.food_items = []
        self.unique_foods = set()
        
    def parse_dataset(self, max_records: int = 10000) -> List[Dict]:
        """Parse the MFP dataset and extract food items"""
        print(f"🔍 Parsing MFP diary dataset (max {max_records:,} records)...")
        
        try:
            # Read the TSV file
            df = pd.read_csv(self.dataset_path, sep='\t', encoding='utf-8', 
                           nrows=max_records, low_memory=False)
            
            print(f"📊 Loaded {len(df):,} diary entries")
            
            # Process each diary entry
            for idx, row in df.iterrows():
                try:
                    # Parse the JSON data from column 2 (index 2)
                    if len(row) > 2 and pd.notna(row.iloc[2]):
                        json_data = row.iloc[2]
                        if isinstance(json_data, str):
                            meals = json.loads(json_data)
                            self._parse_meals(meals)
                    
                    # Also check column 3 for additional meal data
                    if len(row) > 3 and pd.notna(row.iloc[3]):
                        json_data = row.iloc[3]
                        if isinstance(json_data, str):
                            meals = json.loads(json_data)
                            self._parse_meals(meals)
                            
                except Exception as e:
                    if idx < 10:  # Only show errors for first 10 rows
                        print(f"⚠️ Error parsing row {idx}: {e}")
                    continue
            
            print(f"✅ Extracted {len(self.food_items):,} food items from {len(self.unique_foods):,} unique foods")
            return self.food_items
            
        except Exception as e:
            print(f"❌ Error parsing dataset: {e}")
            return []
    
    def _parse_meals(self, meals_data: List[Dict]):
        """Parse meal data from JSON structure"""
        for meal in meals_data:
            if 'dishes' in meal:
                for dish in meal['dishes']:
                    if 'name' in dish and 'nutritions' in dish:
                        food_item = self._extract_food_item(dish)
                        if food_item:
                            # Only add if we haven't seen this exact food before
                            food_key = (food_item['name'], food_item['calories'])
                            if food_key not in self.unique_foods:
                                self.food_items.append(food_item)
                                self.unique_foods.add(food_key)
    
    def _extract_food_item(self, dish: Dict) -> Optional[Dict]:
        """Extract food item data from dish structure"""
        try:
            name = dish.get('name', '').strip()
            if not name or len(name) < 2:
                return None
            
            # Extract nutrition data
            nutrition_dict = {}
            for nutrition in dish.get('nutritions', []):
                nut_name = nutrition.get('name', '').lower()
                nut_value = nutrition.get('value', '0')
                
                # Convert value to float, handle commas
                try:
                    nut_value = float(str(nut_value).replace(',', ''))
                except (ValueError, TypeError):
                    nut_value = 0
                
                nutrition_dict[nut_name] = nut_value
            
            # Map nutrition names to our schema
            food_item = {
                'name': name,
                'calories': nutrition_dict.get('calories', 0),
                'protein_g': nutrition_dict.get('protein', 0),
                'carbs_g': nutrition_dict.get('carbs', 0),
                'fat_g': nutrition_dict.get('fat', 0),
                'sodium_mg': nutrition_dict.get('sodium', 0),
                'sugar_g': nutrition_dict.get('sugar', 0),
                'fiber_g': nutrition_dict.get('fiber', 2),  # Default fiber
            }
            
            # Only include foods with reasonable nutrition data
            if food_item['calories'] > 0 and food_item['calories'] < 5000:
                return food_item
            
            return None
            
        except Exception as e:
            return None
    
    def get_food_statistics(self) -> Dict:
        """Get statistics about the parsed food items"""
        if not self.food_items:
            return {}
        
        df = pd.DataFrame(self.food_items)
        
        stats = {
            'total_foods': len(self.food_items),
            'unique_foods': len(self.unique_foods),
            'avg_calories': df['calories'].mean(),
            'avg_protein': df['protein_g'].mean(),
            'avg_carbs': df['carbs_g'].mean(),
            'avg_fat': df['fat_g'].mean(),
            'calorie_range': (df['calories'].min(), df['calories'].max()),
            'top_foods': df['name'].value_counts().head(10).to_dict()
        }
        
        return stats

def main():
    """Test the MFP parser"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.data_config import MFP_DATASET_PATH
    
    parser = MFPDiaryParser(MFP_DATASET_PATH)
    food_items = parser.parse_dataset(max_records=1000)  # Test with 1000 records first
    
    if food_items:
        stats = parser.get_food_statistics()
        print(f"\n📈 Food Statistics:")
        print(f"   Total food items: {stats['total_foods']:,}")
        print(f"   Unique foods: {stats['unique_foods']:,}")
        print(f"   Average calories: {stats['avg_calories']:.1f}")
        print(f"   Average protein: {stats['avg_protein']:.1f}g")
        print(f"   Calorie range: {stats['calorie_range'][0]:.0f} - {stats['calorie_range'][1]:.0f}")
        
        print(f"\n🍎 Top 10 Foods:")
        for food, count in stats['top_foods'].items():
            print(f"   {food}: {count} times")
        
        print(f"\n📋 Sample food items:")
        for i, food in enumerate(food_items[:5]):
            print(f"   {i+1}. {food['name']} - {food['calories']} cal, {food['protein_g']}g protein")
    else:
        print("❌ No food items extracted")

if __name__ == "__main__":
    main()
