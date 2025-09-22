import logging
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from agno.tools.exa import ExaTools
from dotenv import load_dotenv
from textwrap import dedent
import json
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import FoodItem, MealLog

load_dotenv()
logger = logging.getLogger(__name__)

class NutrientAnalyzerService:
    def __init__(self):
        self.nutrient_agent = Agent(
            name="NutrientAnalyzer",
            tools=[],  # Removed ExaTools due to potential API errors
            model=GroqWithFallback(id="llama-3.3-70b-versatile"),
            description=dedent("""\
                You are NutrientAnalyzer, a health-focused nutrition expert. 🥦📊

                Your mission: Given a food name and portion size, return its complete
                nutritional breakdown (calories, macronutrients, micronutrients).
                You do NOT rely on a local database — you search or infer nutritional
                info from known sources and approximate when needed.
            """),
            instructions=dedent("""\
                For each user query follow these steps:

                1. Input Parsing 📝
                   - Identify the food name (e.g., "Chicken Breast")
                   - Identify the quantity/serving (e.g., "2 servings" or "150 g")

                2. Data Lookup 🔎
                   - Search reliable sources or use internal knowledge for nutrient info
                   - If the food is common, use typical USDA-style values
                   - Scale nutrients to the specified serving size

                3. Output Structuring 📑
                   - Present results clearly in Markdown
                   - Include:
                     • Calories (kcal)
                     • Macronutrients (protein, carbs, fat, fiber)
                     • Micronutrients (vitamins, minerals) if available
                     • Health tags (🌱 vegetarian, 🍗 meat, 🐟 fish, 🌾 gluten-free)

                4. Portion Scaling ⚖️
                   - Adjust all values to the portion given by user

                5. Output Format 📝
                   - JSON-like structure or table for easy parsing by your backend
                   - Include "food_name", "serving_size" and "nutrients" keys

                6. Feedback 🔄
                   - If the food is not found, politely ask for clarification or offer closest match
            """),
            markdown=True,
        )

    def analyze_food_nutrition(self, food_name: str, serving_size: str) -> dict:
        """Analyze nutrition for a given food and serving size"""
        try:
            prompt = f"""Analyze the nutritional content for:
            Food: {food_name}
            Serving Size: {serving_size}
            
            Please provide a complete nutritional breakdown including calories, macronutrients, and key micronutrients.
            Format the response as a structured analysis that can be easily parsed."""
            
            logger.info(f"NutrientAnalyzer prompt: {prompt}")
            response = self.nutrient_agent.run(prompt)
            logger.info(f"NutrientAnalyzer raw response: {response}")
            
            # Extract content from RunOutput
            analysis = response.content if hasattr(response, 'content') else str(response)
            
            # Parse the response to extract structured data
            parsed_nutrients = self._parse_nutrient_response(analysis, food_name, serving_size)
            
            return {
                "success": True,
                "food_name": food_name,
                "serving_size": serving_size,
                "raw_analysis": analysis,
                "parsed_nutrients": parsed_nutrients
            }
        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg or "Rate limit reached" in error_msg:
                logger.error(f"Groq API rate limit exceeded: {e}")
                return {
                    "success": False, 
                    "error": "AI service is temporarily unavailable due to high usage. Please try again in a few minutes.",
                    "error_type": "rate_limit"
                }
            else:
                logger.error(f"Error analyzing nutrition with NutrientAnalyzer: {e}")
                return {"success": False, "error": str(e)}

    def _parse_nutrient_response(self, analysis: str, food_name: str, serving_size: str) -> dict:
        """Parse the AI response to extract structured nutrient data"""
        try:
            # Initialize default values
            nutrients = {
                "calories": 0,
                "protein": 0,
                "carbohydrates": 0,
                "fat": 0,
                "fiber": 0,
                "sugar": 0,
                "sodium": 0,
                "cholesterol": 0,
                "vitamins": {},
                "minerals": {},
                "health_tags": []
            }
            
            # First, try to extract from JSON structure if present
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis, re.DOTALL)
            if json_match:
                try:
                    json_data = json.loads(json_match.group(1))
                    if 'nutrients' in json_data:
                        nutrients_data = json_data['nutrients']
                        nutrients["calories"] = float(nutrients_data.get('calories', 0))
                        
                        # Handle nested macronutrients structure
                        if 'macronutrients' in nutrients_data:
                            macro_data = nutrients_data['macronutrients']
                            nutrients["protein"] = float(macro_data.get('protein', 0))
                            nutrients["carbohydrates"] = float(macro_data.get('carbohydrates', 0))
                            nutrients["fat"] = float(macro_data.get('fat', 0))
                            nutrients["fiber"] = float(macro_data.get('fiber', 0))
                        else:
                            # Handle flat structure
                            nutrients["protein"] = float(nutrients_data.get('protein', 0))
                            nutrients["carbohydrates"] = float(nutrients_data.get('carbohydrates', 0))
                            nutrients["fat"] = float(nutrients_data.get('fat', 0))
                            nutrients["fiber"] = float(nutrients_data.get('fiber', 0))
                        
                        nutrients["sugar"] = float(nutrients_data.get('sugar', 0))
                        nutrients["sodium"] = float(nutrients_data.get('sodium', 0))
                        nutrients["cholesterol"] = float(nutrients_data.get('cholesterol', 0))
                        
                        if 'health_tags' in json_data:
                            nutrients["health_tags"] = json_data['health_tags']
                        
                        return nutrients
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass  # Fall back to regex parsing
            
            # Extract from table format (markdown tables)
            # Look for table rows with nutrient data
            table_rows = re.findall(r'\|[^|]*\|[^|]*\|[^|]*\|', analysis)
            for row in table_rows:
                # Skip header rows
                if 'nutrient' in row.lower() or 'value' in row.lower() or 'unit' in row.lower():
                    continue
                
                # Extract nutrient name and value
                cells = [cell.strip() for cell in row.split('|') if cell.strip()]
                if len(cells) >= 2:
                    nutrient_name = cells[0].lower()
                    value_str = cells[1]
                    
                    # Extract numeric value
                    value_match = re.search(r'(\d+(?:\.\d+)?)', value_str)
                    if value_match:
                        value = float(value_match.group(1))
                        
                        if 'calorie' in nutrient_name:
                            nutrients["calories"] = value
                        elif 'protein' in nutrient_name:
                            nutrients["protein"] = value
                        elif 'carbohydrate' in nutrient_name or 'carb' in nutrient_name:
                            nutrients["carbohydrates"] = value
                        elif 'fat' in nutrient_name and 'total' in nutrient_name:
                            nutrients["fat"] = value
                        elif 'fiber' in nutrient_name:
                            nutrients["fiber"] = value
                        elif 'sugar' in nutrient_name:
                            nutrients["sugar"] = value
                        elif 'sodium' in nutrient_name:
                            nutrients["sodium"] = value
                        elif 'cholesterol' in nutrient_name:
                            nutrients["cholesterol"] = value
            
            # Fallback to regex patterns for non-table formats
            if nutrients["calories"] == 0:
                calorie_patterns = [
                    r'calories?[:\s]*(\d+(?:\.\d+)?)',
                    r'(\d+(?:\.\d+)?)\s*kcal',
                    r'(\d+(?:\.\d+)?)\s*calories?'
                ]
                for pattern in calorie_patterns:
                    calorie_match = re.search(pattern, analysis, re.IGNORECASE)
                    if calorie_match:
                        nutrients["calories"] = float(calorie_match.group(1))
                        break
            
            # Extract macronutrients - try multiple patterns
            if nutrients["protein"] == 0:
                protein_patterns = [
                    r'protein[:\s]*(\d+(?:\.\d+)?)\s*g',
                    r'(\d+(?:\.\d+)?)\s*g\s*protein',
                    r'protein[:\s]*(\d+(?:\.\d+)?)'
                ]
                for pattern in protein_patterns:
                    protein_match = re.search(pattern, analysis, re.IGNORECASE)
                    if protein_match:
                        nutrients["protein"] = float(protein_match.group(1))
                        break
            
            if nutrients["carbohydrates"] == 0:
                carb_patterns = [
                    r'carbohydrates?[:\s]*(\d+(?:\.\d+)?)\s*g',
                    r'(\d+(?:\.\d+)?)\s*g\s*carbohydrates?',
                    r'carbs?[:\s]*(\d+(?:\.\d+)?)\s*g',
                    r'(\d+(?:\.\d+)?)\s*g\s*carbs?'
                ]
                for pattern in carb_patterns:
                    carb_match = re.search(pattern, analysis, re.IGNORECASE)
                    if carb_match:
                        nutrients["carbohydrates"] = float(carb_match.group(1))
                        break
            
            if nutrients["fat"] == 0:
                fat_patterns = [
                    r'fat[:\s]*(\d+(?:\.\d+)?)\s*g',
                    r'(\d+(?:\.\d+)?)\s*g\s*fat',
                    r'total\s*fat[:\s]*(\d+(?:\.\d+)?)\s*g'
                ]
                for pattern in fat_patterns:
                    fat_match = re.search(pattern, analysis, re.IGNORECASE)
                    if fat_match:
                        nutrients["fat"] = float(fat_match.group(1))
                        break
            
            if nutrients["fiber"] == 0:
                fiber_match = re.search(r'fiber[:\s]*(\d+(?:\.\d+)?)\s*g', analysis, re.IGNORECASE)
                if fiber_match:
                    nutrients["fiber"] = float(fiber_match.group(1))
            
            if nutrients["sugar"] == 0:
                sugar_match = re.search(r'sugar[:\s]*(\d+(?:\.\d+)?)\s*g', analysis, re.IGNORECASE)
                if sugar_match:
                    nutrients["sugar"] = float(sugar_match.group(1))
            
            if nutrients["sodium"] == 0:
                sodium_match = re.search(r'sodium[:\s]*(\d+(?:\.\d+)?)\s*mg', analysis, re.IGNORECASE)
                if sodium_match:
                    nutrients["sodium"] = float(sodium_match.group(1))
            
            if nutrients["cholesterol"] == 0:
                cholesterol_match = re.search(r'cholesterol[:\s]*(\d+(?:\.\d+)?)\s*mg', analysis, re.IGNORECASE)
                if cholesterol_match:
                    nutrients["cholesterol"] = float(cholesterol_match.group(1))
            
            # Extract health tags
            analysis_lower = analysis.lower()
            
            # Vegetarian/Vegan detection
            if any(word in analysis_lower for word in ['vegetarian', 'vegan', 'plant-based', 'plant based']):
                nutrients["health_tags"].append("vegetarian")
            elif any(word in analysis_lower for word in ['vegan', 'plant-based', 'plant based']):
                nutrients["health_tags"].append("vegan")
            
            # Meat detection
            if any(word in analysis_lower for word in ['chicken', 'beef', 'pork', 'lamb', 'meat', 'poultry']):
                nutrients["health_tags"].append("meat")
            
            # Fish detection
            if any(word in analysis_lower for word in ['fish', 'salmon', 'tuna', 'seafood', 'cod', 'mackerel']):
                nutrients["health_tags"].append("fish")
            
            # Gluten-free detection
            if any(word in analysis_lower for word in ['gluten-free', 'gluten free', 'glutenfree']):
                nutrients["health_tags"].append("gluten-free")
            
            # Dairy-free detection
            if any(word in analysis_lower for word in ['dairy-free', 'dairy free', 'lactose-free', 'lactose free']):
                nutrients["health_tags"].append("dairy-free")
            
            # Nut-free detection
            if any(word in analysis_lower for word in ['nut-free', 'nut free', 'peanut-free', 'peanut free']):
                nutrients["health_tags"].append("nut-free")
            
            return nutrients
            
        except Exception as e:
            logger.error(f"Error parsing nutrient response: {e}")
            return {
                "calories": 0,
                "protein": 0,
                "carbohydrates": 0,
                "fat": 0,
                "fiber": 0,
                "sugar": 0,
                "sodium": 0,
                "cholesterol": 0,
                "vitamins": {},
                "minerals": {},
                "health_tags": []
            }

    def log_meal_with_analysis(self, food_name: str, serving_size: str, meal_type: str, user_id: int, db: Session) -> dict:
        """Analyze nutrition and log a meal with the extracted data to the database."""
        try:
            # First analyze the nutrition
            analysis_result = self.analyze_food_nutrition(food_name, serving_size)
            if not analysis_result["success"]:
                return analysis_result  # Propagate error

            parsed_nutrients = analysis_result["parsed_nutrients"]
            
            # Create or find existing FoodItem
            food_item = db.query(FoodItem).filter(
                FoodItem.name.ilike(f"%{food_name}%"),
                FoodItem.calories == parsed_nutrients["calories"]
            ).first()
            
            if not food_item:
                # Create new FoodItem with analyzed nutrition data
                food_item = FoodItem(
                    name=food_name,
                    cuisine_type="ai_analyzed",
                    calories=parsed_nutrients["calories"],
                    protein_g=parsed_nutrients["protein"],
                    carbs_g=parsed_nutrients["carbohydrates"],
                    fat_g=parsed_nutrients["fat"],
                    fiber_g=parsed_nutrients["fiber"],
                    sugar_g=parsed_nutrients["sugar"],
                    sodium_mg=parsed_nutrients["sodium"],
                    ingredients="",  # Not available from AI analysis
                    tags=",".join(parsed_nutrients["health_tags"]) if parsed_nutrients["health_tags"] else "",
                    created_at=datetime.utcnow()
                )
                db.add(food_item)
                db.commit()
                db.refresh(food_item)
                logger.info(f"Created new FoodItem: {food_item.name} (ID: {food_item.id})")
            else:
                logger.info(f"Using existing FoodItem: {food_item.name} (ID: {food_item.id})")

            # Create MealLog entry
            meal_log = MealLog(
                user_id=user_id,
                food_item_id=food_item.id,
                meal_type=meal_type,
                quantity=1.0,  # Default quantity, could be enhanced to parse serving size
                calories=parsed_nutrients["calories"],
                protein=parsed_nutrients["protein"],
                carbs=parsed_nutrients["carbohydrates"],
                fat=parsed_nutrients["fat"],
                logged_at=datetime.utcnow(),
                planned=False
            )
            
            db.add(meal_log)
            db.commit()
            db.refresh(meal_log)
            
            logger.info(f"Logged meal: {food_name} for user {user_id}")

            # Return the logged meal data using actual database values
            meal_log_data = {
                "id": meal_log.id,
                "food_name": food_name,
                "serving_size": serving_size,
                "meal_type": meal_type,
                "calories": meal_log.calories,
                "protein": meal_log.protein,
                "carbs": meal_log.carbs,
                "fat": meal_log.fat,
                "fiber": parsed_nutrients["fiber"],
                "sugar": parsed_nutrients["sugar"],
                "sodium": parsed_nutrients["sodium"],
                "cholesterol": parsed_nutrients["cholesterol"],
                "health_tags": parsed_nutrients["health_tags"],
                "logged_at": meal_log.logged_at.isoformat(),
                "food_item_id": food_item.id
            }

            return {
                "success": True,
                "message": "Meal logged successfully with nutrition analysis",
                "data": meal_log_data
            }
            
        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg or "Rate limit reached" in error_msg:
                logger.error(f"Groq API rate limit exceeded: {e}")
                return {
                    "success": False, 
                    "error": "AI service is temporarily unavailable due to high usage. Please try again in a few minutes.",
                    "error_type": "rate_limit"
                }
            else:
                logger.error(f"Error logging meal with analysis: {e}")
                return {"success": False, "error": str(e)}

nutrient_analyzer_service = NutrientAnalyzerService()
