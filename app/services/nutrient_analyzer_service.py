import logging
from typing import Dict, Optional
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from dotenv import load_dotenv
from textwrap import dedent
import json
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import FoodItem, MealLog

load_dotenv()
logger = logging.getLogger(__name__)


def _run_coroutine(coro):
    """
    Run a coroutine from sync code, whether or not a loop is already running.

    `asyncio.run()` refuses to start a second loop inside a running one, which
    is exactly the situation here: this service is synchronous but is called
    from an async FastAPI endpoint. Every call raised

        RuntimeError: asyncio.run() cannot be called from a running event loop

    and the coroutine was never awaited.

    With no loop running (a script, a test) asyncio.run is correct. With one
    running, the coroutine goes to a worker thread that owns its own loop, so
    the caller still gets a result and the outer loop is never blocked by a
    nested run.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)          # no loop - the simple case

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()

# Import automatic challenge updater
try:
    from app.services.automatic_challenge_updater import automatic_challenge_updater
except ImportError:
    logger.warning("Could not import automatic_challenge_updater")
    automatic_challenge_updater = None

class NutrientAnalyzerService:
    # Bounded in-memory cache of nutrition lookups. Modest size because a few
    # hundred distinct foods covers ordinary use, and each entry is small.
    _CACHE_MAX = 500

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self.nutrient_agent = Agent(
            name="NutrientAnalyzer",
            tools=[],  # Removed ExaTools due to potential API errors
            model=GroqWithFallback(),
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

    @staticmethod
    def _cache_key(food_name: str, serving_size: str) -> str:
        """Normalised key so 'Paneer' / ' paneer ' / 'PANEER' share an entry."""
        return f"{(food_name or '').strip().lower()}|{(serving_size or '').strip().lower()}"

    # Units measured by mass or volume: ask for a per-100 figure and scale.
    _METRIC_UNITS = {
        "g": 100.0, "gram": 100.0, "grams": 100.0, "gm": 100.0,
        "ml": 100.0, "millilitre": 100.0, "milliliter": 100.0,
    }
    # Units that are simply counted: ask for one, multiply by however many.
    _COUNT_UNITS = (
        "piece", "pieces", "slice", "slices", "cup", "cups", "bowl", "bowls",
        "plate", "plates", "glass", "glasses", "serving", "servings", "roti",
        "rotis", "chapati", "chapatis", "egg", "eggs", "scoop", "scoops",
        "tbsp", "tsp", "small", "medium", "large", "handful", "katori",
    )

    @classmethod
    def parse_serving(cls, serving_size: str):
        """
        Split a serving into (base_serving, multiplier).

        WHY
        ---
        Asking the model for "3 pieces" and then again for "1 piece" produced
        975 and 420 kcal - and "2 pieces" produced 440. It re-estimates from
        scratch every time and barely registers the quantity, because
        multiplying is not what a language model is good at.

        So we ask it once for a single unit and do the multiplication here.
        Nutrition scales linearly with portion, which makes this exactly the
        kind of arithmetic that belongs in code: same input, same answer,
        every time, at no API cost.

        Returns ("100g", 1.5) for "150g", ("1 piece", 3.0) for "3 pieces".
        Unparseable servings fall back to (serving_size, 1.0) so behaviour
        degrades to the old path rather than breaking.
        """
        raw = (serving_size or "").strip().lower()
        if not raw:
            return "1 serving", 1.0

        match = re.match(
            r"^\s*(\d+(?:\.\d+)?)\s*(?:/\s*\d+\s*)?([a-z]+)?", raw
        )
        if not match:
            # No leading digit: "half a cup", "a bowl", "quarter plate".
            worded = {"half": 0.5, "quarter": 0.25, "third": 0.33,
                      "one": 1.0, "two": 2.0, "three": 3.0, "a": 1.0, "an": 1.0}
            quantity = next(
                (v for w, v in worded.items() if re.search(rf"(?<!\w){w}(?!\w)", raw)),
                1.0,
            )
            for unit in cls._COUNT_UNITS:
                if re.search(rf"(?<!\w){unit}(?!\w)", raw):
                    return f"1 {unit.rstrip('s')}", quantity
            return raw, 1.0

        quantity = float(match.group(1))
        unit = (match.group(2) or "").strip()

        if quantity <= 0:
            quantity = 1.0

        if unit in cls._METRIC_UNITS:
            base_amount = cls._METRIC_UNITS[unit]
            return f"{base_amount:.0f}{unit}", quantity / base_amount

        if unit:
            singular = unit.rstrip("s") if unit.endswith("s") and len(unit) > 2 else unit
            return f"1 {singular}", quantity

        # A bare number - "2" of whatever the food is.
        return "1 serving", quantity

    @staticmethod
    def _lookup_database(food_name: str):
        """
        Try the real food databases, returning None if nothing confident matched.

        Isolated and defensive on purpose: a lookup failure must never stop a
        meal being logged. Whatever goes wrong here, the model path still runs.
        """
        try:
            from app.services.food_lookup import lookup
            facts = lookup(food_name)
            if facts and facts.verified:
                logger.info(
                    "Using %s for %r (matched %r, confidence %.2f) - no model call needed.",
                    facts.source, food_name, facts.matched_name, facts.confidence,
                )
                return facts
        except Exception as e:
            logger.warning("Database lookup failed for %r: %s", food_name, e)
        return None

    @staticmethod
    def _scale(nutrients: dict, factor: float) -> dict:
        """Multiply every numeric field, leaving tags and text alone."""
        if factor == 1.0:
            return dict(nutrients)
        scaled = dict(nutrients)
        for key, value in nutrients.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                scaled[key] = round(value * factor, 1)
        return scaled

    def analyze_food_nutrition(self, food_name: str, serving_size: str) -> dict:
        """
        Analyze nutrition for a given food and serving size.

        Results are cached in memory. The nutritional content of a given food at
        a given serving size does not change between requests, so re-asking the
        model is pure waste - and this is the single most repeated query in the
        app. The cache is per-process and bounded; it is not shared across
        workers, which is fine because a miss just costs one normal call.
        """
        # Always ask about ONE unit and scale here. Besides making the answer
        # consistent, it means every portion of the same food shares a cache
        # entry - "150g paneer" and "200g paneer" are now one API call, not two.
        base_serving, multiplier = self.parse_serving(serving_size)

        key = self._cache_key(food_name, base_serving)
        cached = self._cache.get(key)
        if cached is not None:
            logger.info(
                "NutrientAnalyzer cache HIT for %r (x%.3g for %r)",
                key, multiplier, serving_size,
            )
            result = dict(cached)
            result["serving_size"] = serving_size
            result["parsed_nutrients"] = self._scale(cached["parsed_nutrients"], multiplier)
            return result

        # Before asking the model to remember a product, ask the database that
        # holds its label. "Milky Mist paneer" is a real item with real printed
        # figures; an estimate of those figures is strictly worse than the
        # figures, and this costs ~300ms against ~10s for a model call.
        #
        # Only per-100g bases are eligible: databases publish per 100g, and a
        # "1 piece" question cannot be answered from that without knowing what
        # a piece weighs.
        if base_serving.endswith("g") or base_serving.endswith("ml"):
            facts = self._lookup_database(food_name)
            if facts is not None:
                nutrients = facts.as_nutrients()
                base_result = {
                    "success": True,
                    "food_name": facts.matched_name or food_name,
                    "serving_size": base_serving,
                    "raw_analysis": (
                        f"{facts.matched_name or food_name}"
                        + (f" ({facts.brand})" if facts.brand else "")
                        + f"\nValues published for {facts.basis}:\n"
                        f"  Calories      {facts.calories:.0f} kcal\n"
                        f"  Protein       {facts.protein:.1f} g\n"
                        f"  Carbohydrates {facts.carbohydrates:.1f} g\n"
                        f"  Fat           {facts.fat:.1f} g\n"
                        + (f"  Fibre         {facts.fiber:.1f} g\n" if facts.fiber else "")
                        + f"\nSource: {facts.source_label}"
                    ),
                    "parsed_nutrients": nutrients,
                    "source": facts.provenance(),
                }
                if len(self._cache) >= self._CACHE_MAX:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[key] = dict(base_result)

                result = dict(base_result)
                result["serving_size"] = serving_size
                result["parsed_nutrients"] = self._scale(nutrients, multiplier)
                return result

        try:
            prompt = f"""Analyze the nutritional content for:
            Food: {food_name}
            Serving Size: {base_serving}

            Report the values for EXACTLY {base_serving} of {food_name} - not for a
            larger or smaller portion, and not for a whole package.

            Give a single number for each nutrient, not a range. If you are
            uncertain, give your best single estimate.

            Please provide a complete nutritional breakdown including calories, macronutrients, and key micronutrients.
            Format the response as a structured analysis that can be easily parsed."""

            logger.info(f"NutrientAnalyzer prompt: {prompt}")
            response = self.nutrient_agent.run(prompt)
            logger.info(f"NutrientAnalyzer raw response: {response}")
            
            # Extract content from RunOutput
            analysis = response.content if hasattr(response, 'content') else str(response)
            
            # Parse the response to extract structured data. These are the
            # per-unit figures; scaling happens after caching so the cache
            # always holds the unscaled base.
            base_nutrients = self._parse_nutrient_response(analysis, food_name, base_serving)
            self._sanity_check(base_nutrients, food_name, base_serving)

            base_result = {
                "success": True,
                "food_name": food_name,
                "serving_size": base_serving,
                "raw_analysis": analysis,
                "parsed_nutrients": base_nutrients,
            }

            # Only successful analyses are cached, and only if they parsed to
            # something usable - caching a zero would keep returning it. A
            # rate-limit failure must not be cached either, or it would persist
            # long after the quota recovered.
            if float(base_nutrients.get("calories") or 0) > 0:
                if len(self._cache) >= self._CACHE_MAX:
                    self._cache.pop(next(iter(self._cache)))  # drop oldest
                self._cache[key] = dict(base_result)
                logger.info("NutrientAnalyzer cached %r (%d entries)", key, len(self._cache))

            result = dict(base_result)
            result["serving_size"] = serving_size
            result["parsed_nutrients"] = self._scale(base_nutrients, multiplier)
            if multiplier != 1.0:
                logger.info(
                    "Scaled %r from %s by x%.3g -> %s kcal",
                    food_name, base_serving, multiplier,
                    result["parsed_nutrients"].get("calories"),
                )
            return result
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

    # Aliases for each field, longest/most specific first so "total fat" wins
    # over "fat" and "dietary fiber" over "fiber".
    _NUTRIENT_ALIASES = {
        "calories": ("calories", "calorie", "energy", "kcal"),
        "protein": ("protein",),
        "carbohydrates": ("total carbohydrate", "carbohydrates", "carbohydrate", "carbs", "carb"),
        "fat": ("total fat", "fat"),
        "fiber": ("dietary fiber", "dietary fibre", "fiber", "fibre"),
        "sugar": ("total sugars", "sugars", "sugar"),
        "sodium": ("sodium", "salt"),
        "cholesterol": ("cholesterol",),
    }

    # Lines mentioning these are talking about a different nutrient than the one
    # being searched for, so they must not be harvested by a looser alias.
    _EXCLUDE_FOR = {
        "fat": ("saturated", "unsaturated", "trans", "omega"),
        "sugar": ("added sugar",),
        "calories": ("from fat",),
    }

    @staticmethod
    def _first_number(text: str) -> Optional[float]:
        """
        First quantity in a fragment, averaging ranges.

        Models answer with ranges far more often than single figures -
        "approximately 900-1050", "25-30g", "~450". Taking the lower bound
        understates every meal, so the midpoint is used.
        """
        if not text:
            return None
        cleaned = text.replace(",", "")
        # Range: "900-1050", "25 - 30", "25 to 30"
        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)", cleaned
        )
        if range_match:
            low, high = float(range_match.group(1)), float(range_match.group(2))
            if high >= low:
                return round((low + high) / 2, 1)
        single = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        return float(single.group(1)) if single else None

    def _scan_for(self, analysis: str, field: str) -> Optional[float]:
        """
        Find one nutrient anywhere in the response.

        Works line by line and reads whatever follows the label, which covers
        two-column tables (`| Protein (g) | 25-30g |`), three-column tables,
        bullets (`- Protein: 25g`) and prose alike. The previous version
        required a digit immediately after the word, so a units bracket between
        them - the single most common layout - defeated it.
        """
        aliases = self._NUTRIENT_ALIASES[field]
        excluded = self._EXCLUDE_FOR.get(field, ())

        for raw_line in analysis.splitlines():
            line = raw_line.strip().lower()
            if not line or any(bad in line for bad in excluded):
                continue

            for alias in aliases:
                position = line.find(alias)
                if position == -1:
                    continue

                after = line[position + len(alias):]
                # Skip the unit annotation that usually follows the label so
                # "(g)" is not mistaken for the value.
                after = re.sub(r"^\s*\(([^)]*)\)", "", after)
                value = self._first_number(after)
                if value is not None:
                    return value
        return None

    def _sanity_check(self, nutrients: dict, food_name: str, serving: str) -> None:
        """
        Catch estimates that contradict themselves, and repair what we can.

        The model has no idea when it is wrong, so nothing downstream will
        notice a bad figure - it will simply be logged and quietly distort the
        user's totals. Two checks catch most of it:

          * Atwater - protein and carbs are 4 kcal/g, fat is 9. If the macros
            do not add up to the stated calories, at least one number is wrong.
          * Physical limits - nothing is more than 100g of anything per 100g,
            and 900 kcal/100g is pure fat.

        Where the calorie figure is the odd one out, it is recalculated from
        the macros, which are usually the better-remembered numbers. Anything
        that cannot be repaired is logged loudly and left for the caller's
        zero-calorie guard to reject.
        """
        calories = float(nutrients.get("calories") or 0)
        protein = float(nutrients.get("protein") or 0)
        carbs = float(nutrients.get("carbohydrates") or 0)
        fat = float(nutrients.get("fat") or 0)

        per_100g = serving.endswith("g") or serving.endswith("ml")

        # Impossible quantities mean the reading is untrustworthy as a whole -
        # one field being nonsense says nothing good about the others. Rather
        # than repair it, invalidate it: zeroing the calories makes the
        # caller's existing guard refuse to log it, which is the right outcome.
        impossible = [
            (name, value)
            for name, value in (("protein", protein), ("carbohydrates", carbs), ("fat", fat))
            if per_100g and value > 100
        ]
        if per_100g and calories > 900:
            impossible.append(("calories", calories))

        if impossible:
            for name, value in impossible:
                logger.error(
                    "%r: %s of %.1f per %s is not physically possible - discarding the reading.",
                    food_name, name, value, serving,
                )
            nutrients["calories"] = 0.0
            return

        implied = protein * 4 + carbs * 4 + fat * 9
        if implied <= 0 or calories <= 0:
            return

        # Atwater factors are exact enough that a gap this size means one of
        # the numbers is wrong. The macros are usually the better-remembered
        # ones, so the calorie figure is the one recalculated.
        if abs(implied - calories) > calories * 0.25:
            logger.warning(
                "%r: macros imply %.0f kcal but the model said %.0f - using the macros.",
                food_name, implied, calories,
            )
            nutrients["calories"] = round(implied)

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
            
            # Read every field with one scanner that copes with two- and
            # three-column tables, bullets and prose alike. The previous code
            # had a table branch that only matched three-column rows and a
            # prose branch that required a digit immediately after the label,
            # so a two-column table with units - the most common shape a model
            # produces - matched neither and every value stayed at zero.
            for field in self._NUTRIENT_ALIASES:
                value = self._scan_for(analysis, field)
                if value is not None:
                    nutrients[field] = value

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

    # Every key the FoodItem row needs. A caller-supplied dict is only trusted
    # if it has all of them with numeric values; anything else falls back to a
    # fresh analysis rather than writing zeros into the user's history.
    _REQUIRED_NUTRIENTS = ("calories", "protein", "carbohydrates", "fat")

    def _usable_nutrients(self, nutrients: Optional[dict]) -> Optional[dict]:
        """Normalise caller-supplied nutrients, or None if they cannot be trusted."""
        if not isinstance(nutrients, dict):
            return None
        try:
            clean = {
                "calories": float(nutrients["calories"]),
                "protein": float(nutrients["protein"]),
                "carbohydrates": float(nutrients["carbohydrates"]),
                "fat": float(nutrients["fat"]),
                "fiber": float(nutrients.get("fiber") or 0),
                "sugar": float(nutrients.get("sugar") or 0),
                "sodium": float(nutrients.get("sodium") or 0),
                # Omitting this is what made every log from the UI return 500.
                # The meal was written to the database first, so the failure
                # was a lie: the data was saved and only the RESPONSE blew up,
                # which is why it appeared on the dashboard a minute later.
                "cholesterol": float(nutrients.get("cholesterol") or 0),
            }
        except (KeyError, TypeError, ValueError):
            return None

        # A meal with no energy is a parse failure, not a real reading.
        if clean["calories"] <= 0:
            return None

        tags = nutrients.get("health_tags") or []
        clean["health_tags"] = [str(t) for t in tags] if isinstance(tags, list) else []
        return clean

    def log_meal_with_analysis(
        self,
        food_name: str,
        serving_size: str,
        meal_type: str,
        user_id: int,
        db: Session,
        nutrients: Optional[dict] = None,
    ) -> dict:
        """
        Log a meal, analysing it first only when we have to.

        The UI analyses a food, shows the numbers, and the user confirms. Re-running
        the model at that point costs a second API call and another 10-20 seconds
        to reproduce an answer already on screen - so pre-computed nutrients are
        accepted here and reused.
        """
        try:
            parsed_nutrients = self._usable_nutrients(nutrients)

            if parsed_nutrients is None:
                analysis_result = self.analyze_food_nutrition(food_name, serving_size)
                if not analysis_result["success"]:
                    return analysis_result  # Propagate error
                parsed_nutrients = analysis_result["parsed_nutrients"]

            # A zero-calorie meal is a parse failure, not a reading. Writing it
            # would silently corrupt the day's totals, every average built on
            # them, and the targets derived from those - and the user would have
            # no way to tell, because the log entry looks perfectly normal.
            if not parsed_nutrients or float(parsed_nutrients.get("calories") or 0) <= 0:
                logger.error(
                    "Refusing to log %r: nutrition parsed to zero calories.", food_name
                )
                return {
                    "success": False,
                    "error": (
                        "I could not read reliable nutrition figures for that. "
                        "Try naming the food more specifically - for example "
                        "'grilled chicken sandwich' rather than 'sandwich'."
                    ),
                    "error_type": "parse_failure",
                }
            else:
                logger.info("Logging %r with nutrients supplied by the client - skipping re-analysis", food_name)
            
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
            
            # Automatically update smart challenges.
            #
            # This is a sync method called from an async endpoint, so
            # asyncio.run() raised "cannot be called from a running event
            # loop" every single time and the coroutine was never awaited.
            # _run_coroutine handles both cases - see its docstring.
            if automatic_challenge_updater:
                try:
                    challenge_update_result = _run_coroutine(
                        automatic_challenge_updater.update_challenges_on_meal_log(
                            user_id=user_id,
                            meal_log=meal_log,
                            food_item=food_item,
                            db=db
                        )
                    )
                    if (challenge_update_result or {}).get('success'):
                        logger.info(f"Automatically updated {challenge_update_result.get('count', 0)} challenges")
                except Exception as e:
                    logger.error(f"Error auto-updating challenges: {e}")
                    # Don't fail the meal logging if challenge update fails

            # Points. The other logging route (/meals/log) has always done
            # this; this one never did, so a meal logged through the analyser -
            # which is what the UI actually uses - earned nothing.
            try:
                from app.database import User as _User
                from app.services import points_engine

                user = db.query(_User).filter(_User.id == user_id).first()
                if user:
                    points_engine.sync(db, user, days=1)
            except Exception as e:
                logger.error(f"Error awarding points: {e}")
                db.rollback()

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
                # .get() rather than [] on every optional field. The meal is
                # already committed by this point, so a missing key here can
                # only turn a success into a spurious error.
                "fiber": parsed_nutrients.get("fiber", 0),
                "sugar": parsed_nutrients.get("sugar", 0),
                "sodium": parsed_nutrients.get("sodium", 0),
                "cholesterol": parsed_nutrients.get("cholesterol", 0),
                "health_tags": parsed_nutrients.get("health_tags", []),
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
