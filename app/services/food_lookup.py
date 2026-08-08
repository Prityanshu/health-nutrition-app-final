"""
Nutrition data with a stated source.

THE PROBLEM THIS SOLVES
-----------------------
Asking a language model "how much protein is in paneer?" produces a number that
looks like data and is actually a guess. Sometimes it is close. Sometimes a
vegetarian sandwich comes back with 18g of protein. The user cannot tell which,
because both are rendered in the same confident table.

WHAT THIS DOES AND DOES NOT PROMISE
-----------------------------------
It does NOT promise correct figures for every food. That is not achievable:
crowdsourced databases contain user typos, no database covers every regional
dish, and homemade food genuinely varies between kitchens. Any library claiming
otherwise is wrong.

It promises something more useful - that every number arrives with its
provenance, so a guess is never displayed as a fact:

    VERIFIED   from a product label or a government food composition table
    ESTIMATED  a language model's approximation, explicitly marked as such

A labelled estimate is honest. An unlabelled one is misinformation.

SOURCE LADDER
-------------
1. Local FoodItem rows previously resolved from a real source (free, instant)
2. Open Food Facts   - packaged and branded products, label data per 100g
3. USDA FoodData Central - generic whole foods, government laboratory analysis
4. The model         - homemade and composite dishes, marked ESTIMATED

Each step is tried only if the ones above it miss, so the good sources are
preferred and the model becomes the fallback rather than the default.

Everything is returned per 100g or per unit; scaling to the user's portion is
done by the caller, which already has parse_serving() for exactly that.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_BARCODE_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

USDA_API_KEY = os.getenv("USDA_API_KEY", "").strip()

# Open Food Facts asks that clients identify themselves so they can contact you
# if a client misbehaves. It is a donation-funded project; this is the polite
# minimum, along with caching every lookup.
USER_AGENT = "NutriPlan/1.0 (student project; nutrition lookup)"

# Network budget. A lookup that takes longer than this is worse than falling
# through to the next source.
TIMEOUT = 6

# Below this match score the result is discarded. A confidently wrong match is
# worse than no match, because it looks authoritative.
MIN_MATCH_SCORE = 0.55
# Open Food Facts is searched by free text over millions of branded products,
# so it returns something plausible-looking for almost any query. It needs a
# higher bar than the curated USDA tables.
OFF_MIN_SCORE = 0.75


@dataclass
class NutritionFacts:
    """Nutrition for 100g (or one unit), plus where it came from."""

    food_name: str
    calories: float
    protein: float
    carbohydrates: float
    fat: float
    fiber: float = 0.0
    sugar: float = 0.0
    sodium: float = 0.0

    basis: str = "100g"          # what the figures describe
    source: str = "estimate"     # off | usda | cache | estimate
    source_label: str = ""       # shown to the user
    source_url: Optional[str] = None
    matched_name: Optional[str] = None   # the product actually found
    brand: Optional[str] = None
    confidence: float = 0.0
    verified: bool = False       # True only for real measured data
    # True only when a barcode identified the product. A name match can find a
    # real label for the wrong variant - "paneer" matches regular, low-fat and
    # high-protein versions of the same brand, which differ by 40% in protein.
    # The user needs to be told which of those two things happened.
    exact: bool = False
    health_tags: List[str] = field(default_factory=list)

    def as_nutrients(self) -> Dict[str, Any]:
        """The shape the rest of the app already expects."""
        return {
            "calories": self.calories,
            "protein": self.protein,
            "carbohydrates": self.carbohydrates,
            "fat": self.fat,
            "fiber": self.fiber,
            "sugar": self.sugar,
            "sodium": self.sodium,
            "health_tags": list(self.health_tags),
        }

    def provenance(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_label": self.source_label,
            "source_url": self.source_url,
            "matched_name": self.matched_name,
            "brand": self.brand,
            "confidence": round(self.confidence, 2),
            "verified": self.verified,
            "exact": self.exact,
            "basis": self.basis,
        }


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

_NOISE = {
    "fresh", "pack", "packet", "packaged", "organic", "natural", "premium",
    "classic", "original", "brand", "of", "the", "a", "an", "and", "with",
    # USDA descriptions are verbose by convention - "Chicken, broiler or
    # fryers, breast, meat only, cooked". These words carry no identifying
    # information, and counting them as differences would reject correct
    # laboratory entries for being wordy.
    "cooked", "raw", "meat", "only", "without", "skin", "boiled", "roasted",
    "or", "plain", "unsalted", "salted", "sliced", "chopped", "whole", "each",
    "prepared", "unprepared", "commercial", "commercially", "includes", "types",
}


def _tokens(text: str) -> List[str]:
    return [
        t for t in re.split(r"[^a-z0-9]+", (text or "").lower())
        if t and t not in _NOISE and len(t) > 1
    ]


# Words that change what the food IS. "Brown rice" and "brown rice cakes" share
# every word the user typed, but one is a grain and the other is a 400 kcal
# puffed snack. If the candidate adds one of these and the query did not, it is
# a different food and no amount of token overlap makes it the right answer.
_FORM_CHANGING = {
    "cake", "cakes", "chip", "chips", "crisps", "bar", "bars", "biscuit",
    "biscuits", "cookie", "cookies", "wafer", "wafers", "puffs", "snack",
    "snacks", "drink", "drinks", "juice", "shake", "smoothie", "powder",
    "mix", "sauce", "paste", "spread", "dip", "soup", "instant", "noodle",
    "noodles", "pasta", "flour", "atta", "oil", "syrup", "candy", "chocolate",
    "icecream", "ice", "cream", "dessert", "pudding", "pizza", "burger",
    "sandwich", "wrap", "roll", "curry", "masala", "tikka", "fried", "ready",
    "meal", "flavour", "flavor", "flavoured", "flavored", "seasoning", "cube",
    "concentrate", "extract", "supplement", "capsule", "tablet",
}


def introduces_different_food(query: str, candidate: str) -> bool:
    """
    True if the candidate turns the requested food into another product.

    This is the single most valuable guard here. Token overlap alone rates
    "brown rice cakes" as a great match for "brown rice", and the resulting
    400 kcal/100g would be presented to the user as verified label data.
    """
    asked = set(_tokens(query))
    found = set(_tokens(candidate))
    added = found - asked
    return bool(added & _FORM_CHANGING)


def macros_are_consistent(calories: float, protein: float, carbs: float,
                          fat: float, tolerance: float = 0.22) -> bool:
    """
    Do the macros account for the stated calories?

    Crowdsourced entries are typed in by hand and often disagree with
    themselves - one real example returned 96 kcal alongside macros summing to
    121. Atwater factors (4/4/9) are exact enough that a gap this large means
    the record is wrong, and a wrong record is worse than no record.

    Entries with no macros at all are not judged; some are legitimately sparse.
    """
    if calories <= 0:
        return False
    implied = protein * 4 + carbs * 4 + fat * 9
    if implied <= 0:
        return True
    return abs(implied - calories) <= calories * tolerance


def match_score(query: str, candidate: str, brand: str = "") -> float:
    """
    How well a database entry answers what the user typed.

    Deliberately strict. Search engines happily return *something* for any
    query, and accepting a loose match is how "paneer" becomes a branded paneer
    tikka masala ready meal with entirely different numbers. Requiring most of
    the user's words to appear keeps near-misses out.
    """
    wanted = _tokens(query)
    if not wanted:
        return 0.0

    have = set(_tokens(candidate)) | set(_tokens(brand))
    if not have:
        return 0.0

    hits = sum(1 for token in wanted if token in have)
    if not hits:
        return 0.0
    score = hits / len(wanted)

    # Penalise candidates that say much more than was asked for. Without this,
    # "paneer" scores a perfect match against "Paneer Tikka Masala Ready Meal"
    # - a completely different food whose numbers would be presented as fact.
    # The extra count is capped so genuinely descriptive names are not punished
    # into oblivion.
    extra = min(4, max(0, len(have) - hits))
    if extra:
        score *= len(wanted) / (len(wanted) + extra * 0.5)

    # Every word matched and nothing extraneous - almost certainly the item.
    if hits == len(wanted) and not extra:
        score = min(1.0, score + 0.1)

    return score


def _number(value: Any) -> float:
    try:
        result = float(value)
        return result if result >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Open Food Facts - packaged and branded products
# ---------------------------------------------------------------------------

def _off_search(query: str) -> List[Dict[str, Any]]:
    """
    Search Open Food Facts for a product, trying more than one phrasing.

    A single free-text search is fragile. "fru bon low fat paneer" is the brand
    followed by the product name, but the record stores those in separate
    fields - so depending on how the index tokenises, the exact phrase can rank
    below noise or miss entirely. Dropping to the core food words usually finds
    it, and the match scorer decides whether the result is actually right.

    Returns the union of every attempt, de-duplicated by barcode.
    """
    attempts = [query]

    words = _tokens(query)
    if len(words) > 2:
        # Without the leading word, which is usually the brand.
        attempts.append(" ".join(words[1:]))
        # Just the last two words - typically the food itself.
        attempts.append(" ".join(words[-2:]))
    if words:
        attempts.append(words[-1])

    seen: set = set()
    collected: List[Dict[str, Any]] = []

    for attempt in dict.fromkeys(a for a in attempts if a):   # ordered, unique
        try:
            response = requests.get(
                OFF_SEARCH_URL,
                params={
                    "search_terms": attempt,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": 25,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            if not response.ok:
                continue
            for product in response.json().get("products", []) or []:
                code = product.get("code")
                if code and code in seen:
                    continue
                if code:
                    seen.add(code)
                collected.append(product)
        except requests.RequestException as e:
            logger.warning("Open Food Facts search %r failed: %s", attempt, e)
            continue

        # A confident hit on the full query means no need to broaden.
        if attempt == query and any(
            match_score(query, p.get("product_name") or "",
                        (p.get("brands") or "").split(",")[0]) >= 0.9
            for p in collected
        ):
            break

    logger.info("Open Food Facts returned %d candidates for %r", len(collected), query)
    return collected


def lookup_open_food_facts(query: str, barcode: Optional[str] = None) -> Optional[NutritionFacts]:
    """
    Label data for a packaged product.

    Open Food Facts is crowdsourced, so two guards matter: entries frequently
    have missing nutrition fields, and the search will return something for
    almost any query. Both are checked before a result is accepted.
    """
    try:
        if barcode:
            response = requests.get(
                OFF_BARCODE_URL.format(barcode=barcode),
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            if not response.ok:
                return None
            payload = response.json()
            if payload.get("status") != 1:
                return None
            products = [payload["product"]]
        else:
            products = _off_search(query)

        best: Optional[NutritionFacts] = None
        for product in products:
            name = product.get("product_name") or ""
            brand = (product.get("brands") or "").split(",")[0].strip()
            if not name:
                continue

            nutriments = product.get("nutriments") or {}
            calories = _number(nutriments.get("energy-kcal_100g"))
            if calories <= 0:
                # A product entry with no energy value is unusable; this is the
                # most common gap in crowdsourced records.
                continue

            score = match_score(query, name, brand)
            if barcode:
                score = 1.0          # a barcode is an exact identifier
            elif introduces_different_food(query, name):
                logger.debug("Rejected %r for %r - different kind of food", name, query)
                continue

            if score < OFF_MIN_SCORE and not barcode:
                continue

            protein = _number(nutriments.get("proteins_100g"))
            carbs = _number(nutriments.get("carbohydrates_100g"))
            fat = _number(nutriments.get("fat_100g"))

            # Crowdsourced records are hand-typed and sometimes contradict
            # themselves. Rather than pass that on as verified data, drop it.
            if not macros_are_consistent(calories, protein, carbs, fat):
                logger.info(
                    "Rejected %r - macros (%.1fP/%.1fC/%.1fF) do not match %.0f kcal",
                    name, protein, carbs, fat, calories,
                )
                continue

            candidate = NutritionFacts(
                food_name=query,
                calories=calories,
                protein=protein,
                carbohydrates=carbs,
                fat=fat,
                fiber=_number(nutriments.get("fiber_100g")),
                sugar=_number(nutriments.get("sugars_100g")),
                # Open Food Facts stores sodium in grams; the app uses mg.
                sodium=_number(nutriments.get("sodium_100g")) * 1000,
                basis="100g",
                source="off",
                source_label="Product label (Open Food Facts)",
                source_url=(
                    f"https://world.openfoodfacts.org/product/{product.get('code')}"
                    if product.get("code") else None
                ),
                matched_name=name,
                brand=brand or None,
                confidence=score,
                verified=True,
                exact=bool(barcode),
            )
            if best is None or candidate.confidence > best.confidence:
                best = candidate

        return best

    except requests.RequestException as e:
        logger.warning("Open Food Facts lookup failed for %r: %s", query, e)
        return None
    except Exception as e:
        logger.error("Open Food Facts lookup error for %r: %s", query, e, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# USDA FoodData Central - generic whole foods
# ---------------------------------------------------------------------------

# FDC nutrient IDs. Names vary across datasets; the numeric IDs do not.
_USDA_NUTRIENTS = {
    1008: "calories",       # Energy (kcal)
    1003: "protein",
    1005: "carbohydrates",  # Carbohydrate, by difference
    1004: "fat",            # Total lipid (fat)
    1079: "fiber",
    2000: "sugar",
    1093: "sodium",         # mg
}


def lookup_usda(query: str) -> Optional[NutritionFacts]:
    """
    Laboratory-analysed values for generic foods.

    This is the authoritative source for things like "chicken breast" or
    "cooked rice" - foods with no label because they have no packet. Requires a
    free data.gov key; without one this simply returns None and the ladder
    moves on, so the app works either way.
    """
    if not USDA_API_KEY:
        return None

    try:
        response = requests.get(
            USDA_SEARCH_URL,
            params={
                "api_key": USDA_API_KEY,
                "query": query,
                "pageSize": 10,
                # Foundation and SR Legacy are measured in a laboratory.
                # Branded entries are manufacturer-submitted and belong to the
                # Open Food Facts step instead.
                "dataType": "Foundation,SR Legacy",
            },
            timeout=TIMEOUT,
        )
        if not response.ok:
            logger.warning("USDA returned HTTP %s for %r", response.status_code, query)
            return None

        best: Optional[NutritionFacts] = None
        for food in response.json().get("foods", []) or []:
            name = food.get("description") or ""
            if not name:
                continue

            score = match_score(query, name)
            if score < MIN_MATCH_SCORE:
                continue

            values: Dict[str, float] = {}
            for nutrient in food.get("foodNutrients", []) or []:
                field_name = _USDA_NUTRIENTS.get(nutrient.get("nutrientId"))
                if field_name:
                    values[field_name] = _number(nutrient.get("value"))

            if values.get("calories", 0) <= 0:
                continue

            candidate = NutritionFacts(
                food_name=query,
                calories=values.get("calories", 0.0),
                protein=values.get("protein", 0.0),
                carbohydrates=values.get("carbohydrates", 0.0),
                fat=values.get("fat", 0.0),
                fiber=values.get("fiber", 0.0),
                sugar=values.get("sugar", 0.0),
                sodium=values.get("sodium", 0.0),
                basis="100g",
                source="usda",
                source_label="USDA FoodData Central",
                source_url=(
                    f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{food.get('fdcId')}/nutrients"
                    if food.get("fdcId") else None
                ),
                matched_name=name,
                confidence=score,
                verified=True,
            )
            if best is None or candidate.confidence > best.confidence:
                best = candidate

        return best

    except requests.RequestException as e:
        logger.warning("USDA lookup failed for %r: %s", query, e)
        return None
    except Exception as e:
        logger.error("USDA lookup error for %r: %s", query, e, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# the ladder
# ---------------------------------------------------------------------------

# Words that mean the user is describing something cooked at home. There is no
# label and no laboratory entry for "my mum's rajma", so these skip straight to
# the estimator rather than burning two failed network calls.
_HOMEMADE_HINTS = (
    "homemade", "home made", "my ", "mum", "mom", "amma", "leftover",
    "restaurant", "hotel", "canteen", "mess ", "tiffin", "street",
)


def looks_homemade(query: str) -> bool:
    lowered = (query or "").lower()
    return any(hint in lowered for hint in _HOMEMADE_HINTS)


def lookup(query: str, barcode: Optional[str] = None) -> Optional[NutritionFacts]:
    """
    Best available real data for a food, or None if there is none.

    Returning None is a valid and important answer: it tells the caller to fall
    back to an estimate and to label it as one. Never invent a result here.
    """
    if barcode:
        found = lookup_open_food_facts(query or "", barcode=barcode)
        if found:
            logger.info("Barcode %s resolved to %r", barcode, found.matched_name)
            return found

    if not query or not query.strip():
        return None

    if looks_homemade(query):
        logger.info("%r looks homemade - going straight to an estimate.", query)
        return None

    # Packaged first: if someone names a brand, the label is the right answer.
    off = lookup_open_food_facts(query)
    if off and off.confidence >= 0.75:
        logger.info("Open Food Facts matched %r -> %r (%.2f)",
                    query, off.matched_name, off.confidence)
        return off

    # Then the generic food tables.
    usda = lookup_usda(query)
    if usda and usda.confidence >= 0.65:
        logger.info("USDA matched %r -> %r (%.2f)",
                    query, usda.matched_name, usda.confidence)
        return usda

    # Neither was confident. Prefer whichever got closer, if either cleared the
    # floor; otherwise admit there is no match.
    candidates = [c for c in (off, usda) if c]
    if candidates:
        best = max(candidates, key=lambda c: c.confidence)
        if best.confidence >= MIN_MATCH_SCORE:
            logger.info("Weak match for %r -> %r (%.2f) - flagged for confirmation.",
                        query, best.matched_name, best.confidence)
            return best

    logger.info("No database match for %r - an estimate will be used.", query)
    return None
