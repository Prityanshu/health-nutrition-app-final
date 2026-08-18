import logging
from typing import Optional

from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from app.config.groq_config import get_fast_model
from dotenv import load_dotenv
from textwrap import dedent

from app.services import dietary_rules

load_dotenv()
logger = logging.getLogger(__name__)


def _closer(candidate, incumbent) -> bool:
    """
    Is the retry actually better than what we already had?

    Compared on how many macros landed, then on total distance. Without this a
    retry that fixes carbs and blows calories would silently replace a plan
    that was only slightly off - regeneration has to be an improvement, not
    just a change.
    """
    if not candidate or not candidate.get("checked"):
        return False
    if not incumbent or not incumbent.get("checked"):
        return True
    if candidate.get("hit"):
        return True

    def distance(v):
        return sum(abs(m["delta"]) / max(1, m["target"])
                   for m in v.get("macros", {}).values())

    if len(candidate.get("missed", [])) != len(incumbent.get("missed", [])):
        return len(candidate["missed"]) < len(incumbent["missed"])
    return distance(candidate) < distance(incumbent)

class Assessment:
    """
    What the deterministic checks make of one model response.

    The same object for a meal plan, a recipe and an adaptation: their
    Markdown differs, but the question asked of each is identical - does it
    prescribe anything the user's restrictions forbid, and where macros were
    requested, does it hit them.
    """

    def __init__(self, text: str, audit, macro=None):
        self.text = text or ""
        self.audit = audit
        self.macro = macro

    @property
    def hard_safe(self) -> bool:
        return self.audit is None or self.audit.hard_safe

    @property
    def macro_ok(self) -> bool:
        """True when macros were not requested, or were requested and hit."""
        return self.macro is None or bool(self.macro.get("hit"))

    @property
    def usable(self) -> bool:
        """
        The gate for returning success. Hard dietary safety only.

        A macro miss is reported honestly and still shipped - a plan 15g of
        protein short is a usable plan. A vegan plan containing ghee is not.
        """
        return bool(self.text.strip()) and self.hard_safe

    def needs_retry(self) -> bool:
        return not self.hard_safe or (self.macro is not None
                                      and self.macro.get("checked")
                                      and not self.macro.get("hit"))

    def brief(self, macro_target=None) -> str:
        """
        ONE corrective instruction covering every failed check.

        Deliberately combined: a brief per validator would mean a retry per
        validator, and this agent is allowed exactly one corrective call.
        """
        parts = []
        if self.audit is not None and self.audit.violations:
            parts.append(
                "DIETARY - the previous version broke a hard restriction. "
                "Replace the ingredient itself; renaming the dish does not "
                "help:")
            for v in self.audit.violations[:8]:
                parts.append(f"  - {v.ingredient!r} is not "
                             f"{v.restriction.replace('_', ' ')} "
                             f"(matched {v.matched!r})")
        if self.macro is not None and self.macro.get("checked") \
                and not self.macro.get("hit"):
            from app.services import macro_targets as mt
            parts.append(mt.retry_brief(self.macro, macro_target))
        return "\n            ".join(parts)

    def as_dict(self) -> dict:
        return {
            "dietary": self.audit.as_dict() if self.audit else None,
            "macros": self.macro,
            "hard_safe": self.hard_safe,
            "usable": self.usable,
        }


def _better(candidate: "Assessment", incumbent: "Assessment") -> bool:
    """
    Ordered so what cannot be traded away comes first.

    Hard dietary safety beats every macro consideration: a retry whose macros
    improved but which introduced paneer into a dairy-free plan must never
    win. Only between two equally safe candidates does the macro comparison
    (_closer, unchanged) decide.
    """
    if candidate.hard_safe != incumbent.hard_safe:
        return candidate.hard_safe
    if not candidate.text.strip():
        return False
    return _closer(candidate.macro, incumbent.macro)


class CulinaryExplorerService:

    def __init__(self):
        self.regional_food_agent = Agent(
            name="CulinaryExplorer",
            tools=[],  # Removed ExaTools due to potential API errors
            # Fast tier: creative regional-recipe generation, no tools. When a
            # macro_target IS given (see generate_regional_meal_plan below),
            # the numbers are checked and one corrective retry is issued
            # deterministically by macro_targets.verify()/retry_brief() - the
            # arithmetic accuracy that would justify the reasoning tier is
            # already handled in Python, not left to the model.
            model=GroqWithFallback(id=get_fast_model()),
            description=dedent("""\
                You are CulinaryExplorer, a culturally aware and health-focused chef. 🌍🍴

                Your mission: suggest recipes and meal plans based on a user's regional or
                cultural cuisine preference. This includes international cuisines
                (Mediterranean, Japanese, Mexican) as well as specific Indian states
                (Punjab, Kerala, Gujarat, Tamil Nadu, Rajasthan, etc.).

                You provide healthier versions of those traditional recipes while keeping 
                authentic taste and cultural notes.
            """),
            instructions=dedent("""\
                FORMATTING: Never use Markdown tables. The app's renderer and
                PDF export only understand headings, bullet points, numbered
                lists and bold text - a table renders as broken pipe-delimited
                text, not a table. Use bullet or numbered lists instead.

                Approach each recipe recommendation with these steps:

                1. Input Analysis 📝
                   - Identify user's preferred cuisine/region:
                     • Global cuisines (Mediterranean, Japanese, Mexican, etc.)
                     • Indian states (Punjab, Kerala, Gujarat, Tamil Nadu, Rajasthan, etc.)
                   - Consider any dietary restrictions or preferences
                   - Note time constraints & cooking skill level
                   - Check available ingredients (if provided)

                2. Cuisine Filtering 🌎
                   - Use a dataset with cuisine tags for each recipe
                   - For India, filter by state-specific cuisine (e.g. Kerala = Appam & Stew, Punjab = Sarson da Saag, etc.)
                   - Select dishes commonly eaten in that region/state

                3. Healthy Modifications 💚
                   - Reduce excess oils, sugars, and refined carbs
                   - Suggest whole-grain or plant-based substitutes where appropriate
                   - Add portion-control or preparation tips to keep it healthier

                4. Presentation Style 📑
                   - Use clear markdown formatting
                   - Present ingredients in a structured list
                   - Number cooking steps clearly
                   - Add emoji indicators:
                     🌱 Vegetarian
                     🌿 Vegan
                     🌾 Gluten-free
                     🥜 Contains nuts
                     🍗 Contains meat/poultry
                     🐟 Contains fish/seafood
                     🩺 Healthier version
                   - Include cultural notes (e.g. "This dish originates from Kerala's backwater cuisine")
                   - Suggest side dishes authentic to the region/state

                5. Feedback & Adaptation 🔄
                   - Accept user feedback on taste & authenticity
                   - Adjust future suggestions accordingly
            """),
            markdown=True,
        )

    # ------------------------------------------------------------------
    # the shared deterministic pipeline
    # ------------------------------------------------------------------

    def _assess(self, text: str, restrictions=None, macro_target=None) -> Assessment:
        """
        Every successful path goes through here.

        Generation, recipes, adaptation, each retry and the rate-limit
        fallbacks all assess the same way, so a path cannot accidentally skip
        a check by being written separately - which is exactly how the recipe
        and adaptation paths ended up with no dietary audit at all.
        """
        audit = dietary_rules.audit_markdown(text, restrictions)
        macro = None
        if macro_target is not None:
            from app.services import macro_targets as mt
            macro = mt.verify(macro_target, text)
        return Assessment(text, audit, macro)

    def _run(self, prompt: str) -> str:
        response = self.regional_food_agent.run(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _attempt(self, prompt: str, restrictions=None, macro_target=None,
                 operation: str = "generate") -> Assessment:
        """
        One model call, plus at most ONE corrective call. Never more.

        The corrective call carries a single combined brief covering dietary
        and macro failures together, so adding a validator can never add a
        round trip.
        """
        first = self._assess(self._run(prompt), restrictions, macro_target)
        logger.info("culinary %s attempt=1 %s", operation, _describe(first))

        if not first.needs_retry():
            return first

        brief = first.brief(macro_target)
        if not brief:
            return first

        try:
            second = self._assess(
                self._run(f"{prompt}\n\n            "
                          f"Your previous version was rejected. Fix ALL of the "
                          f"following and return the corrected version:\n"
                          f"            {brief}"),
                restrictions, macro_target)
        except Exception as exc:
            logger.warning("culinary %s retry failed (%s); keeping first",
                           operation, type(exc).__name__)
            return first

        logger.info("culinary %s attempt=2 %s", operation, _describe(second))
        if _better(second, first):
            second.retried = True
            return second
        first.retried = True
        return first

    def _fallback(self, text: str, restrictions, operation: str) -> Optional[dict]:
        """
        A canned fallback may only be returned if it actually satisfies the
        user's restrictions.

        The old fallbacks returned success=True with "Yogurt/curd" and
        "Traditional bread/roti" regardless of what the user had asked for -
        a vegan, dairy-free or gluten-free user got a conflicting plan
        presented as a successful result, from a path that never consulted a
        restriction in its life. Auditing the static text closes that without
        removing the useful unrestricted behaviour.

        Returns None when the fallback is not safe to serve, so the caller
        fails honestly instead.
        """
        audit = dietary_rules.audit_markdown(text, restrictions)
        if not audit.hard_safe:
            logger.warning("culinary %s fallback withheld: %d dietary conflict(s)",
                           operation, len(audit.violations))
            return None
        return {"text": text, "verification": Assessment(text, audit).as_dict()}

    @staticmethod
    def _unavailable(restrictions, detail: str) -> dict:
        return {
            "success": False,
            "error": ("The recipe service is busy right now. Rather than hand "
                      "you a generic plan that may not fit your dietary "
                      "requirements, please try again in a few minutes."
                      if restrictions else
                      "The recipe service is busy right now. Please try again "
                      "in a few minutes."),
            "error_type": "rate_limit",
            "detail": detail,
        }

    # ------------------------------------------------------------------
    # regional meal plan
    # ------------------------------------------------------------------

    async def generate_regional_meal_plan(self, cuisine_region: str, meal_type: str = "full_day",
                                        dietary_restrictions: list = None, time_constraint: int = 60,
                                        cooking_skill: str = "intermediate", available_ingredients: list = None,
                                        macro_target=None, goal_context: str = "") -> dict:
        """
        Generate a regional meal plan.

        `macro_target` is optional. When given it goes LAST in the prompt:
        models weight the end most heavily, and a nutritional requirement
        buried above four lines about authenticity gets treated as a
        suggestion. The restriction block sits just before it for the same
        reason - though the prompt is never what makes either true, the
        deterministic audit is.
        """
        restrictions = dietary_rules.canonical_set(dietary_restrictions)
        try:
            ingredients_str = (f"Available ingredients: {', '.join(available_ingredients)}."
                               if available_ingredients else "")
            macro_str = f"\n\n            {macro_target.prompt_block()}" if macro_target else ""
            goal_str = f"\n\n            {goal_context.strip()}" if goal_context else ""
            restriction_str = _restriction_block(dietary_restrictions)

            prompt = f"""I'm interested in {cuisine_region} cuisine and want a {meal_type} meal plan.
            {ingredients_str}
            I have {time_constraint} minutes for cooking and my skill level is {cooking_skill}.

            Please create a healthy, authentic {cuisine_region} meal plan with traditional dishes
            that have been modified for better health while maintaining cultural authenticity.{goal_str}{restriction_str}{macro_str}"""

            result = self._attempt(prompt, restrictions, macro_target,
                                   operation="meal_plan")

            if not result.usable:
                return _rejected(result, restrictions, "meal plan")

            return {
                "success": True,
                "meal_plan": result.text,
                "verification": result.as_dict(),
                "cuisine_region": cuisine_region,
                "meal_type": meal_type,
                "dietary_restrictions": restrictions,
                "time_constraint": time_constraint,
                "cooking_skill": cooking_skill,
                "available_ingredients": available_ingredients or [],
            }
        except Exception as e:
            if _is_rate_limit(e):
                logger.error("culinary meal_plan rate limited")
                safe = self._fallback(_generic_plan(cuisine_region), restrictions,
                                      "meal_plan")
                if safe is None:
                    return self._unavailable(restrictions, "meal_plan")
                return {
                    "success": True,
                    "meal_plan": safe["text"],
                    "verification": safe["verification"],
                    "fallback": True,
                    "cuisine_region": cuisine_region,
                    "meal_type": meal_type,
                    "dietary_restrictions": restrictions,
                    "time_constraint": time_constraint,
                    "cooking_skill": cooking_skill,
                    "available_ingredients": available_ingredients or [],
                }
            logger.error("culinary meal_plan failed: %s", type(e).__name__, exc_info=True)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # regional recipe
    # ------------------------------------------------------------------

    async def generate_regional_recipe(self, cuisine_region: str, dish_name: str = None,
                                     dietary_restrictions: list = None, time_constraint: int = 60,
                                     cooking_skill: str = "intermediate", available_ingredients: list = None,
                                     macro_target=None) -> dict:
        """Generate a specific regional recipe, through the same checks."""
        restrictions = dietary_rules.canonical_set(dietary_restrictions)
        try:
            dish_prompt = f" for {dish_name}" if dish_name else ""
            ingredients_str = (f"Available ingredients: {', '.join(available_ingredients)}."
                               if available_ingredients else "")
            restriction_str = _restriction_block(dietary_restrictions)
            macro_str = f"\n\n            {macro_target.prompt_block()}" if macro_target else ""

            prompt = f"""I want a {cuisine_region} recipe{dish_prompt}.
            {ingredients_str}
            I have {time_constraint} minutes for cooking and my skill level is {cooking_skill}.

            Please provide a healthy, authentic {cuisine_region} recipe with traditional flavors
            but modified for better health. Include cultural context and serving
            suggestions.{restriction_str}{macro_str}"""

            result = self._attempt(prompt, restrictions, macro_target,
                                   operation="recipe")

            if not result.usable:
                return _rejected(result, restrictions, "recipe")

            return {
                "success": True,
                "recipe": result.text,
                "verification": result.as_dict(),
                "cuisine_region": cuisine_region,
                "dish_name": dish_name,
                "dietary_restrictions": restrictions,
                "time_constraint": time_constraint,
                "cooking_skill": cooking_skill,
                "available_ingredients": available_ingredients or [],
            }
        except Exception as e:
            if _is_rate_limit(e):
                logger.error("culinary recipe rate limited")
                safe = self._fallback(_generic_recipe(cuisine_region, dish_name),
                                      restrictions, "recipe")
                if safe is None:
                    return self._unavailable(restrictions, "recipe")
                return {
                    "success": True,
                    "recipe": safe["text"],
                    "verification": safe["verification"],
                    "fallback": True,
                    "dish_name": dish_name,
                    "cuisine_region": cuisine_region,
                    "dietary_restrictions": restrictions,
                    "cooking_time": time_constraint,
                    "difficulty": cooking_skill,
                    "ingredients": available_ingredients or [],
                }
            logger.error("culinary recipe failed: %s", type(e).__name__, exc_info=True)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # adaptation
    # ------------------------------------------------------------------

    async def adapt_regional_plan(self, current_plan: str, feedback: str,
                                new_cuisine_preference: str = None,
                                new_dietary_restrictions: list = None,
                                dietary_restrictions: list = None,
                                macro_target=None) -> dict:
        """
        Adapt an existing plan, through the identical checks.

        `dietary_restrictions` is the ORIGINAL, authoritative set the plan was
        built with; `new_dietary_restrictions` may only ADD to it. Adaptation
        used to receive the new list alone, so "make it creamier" on a vegan
        plan carried no vegan requirement at all - the restriction silently
        ceased to exist at the first adaptation, and nothing downstream
        checked.

        Restrictions are never recovered from the plan's own prose: a model
        that wrote "🌿 Vegan" is asserting, not proving, and an adaptation
        that dropped the word would also drop the requirement.
        """
        merged = dietary_rules.canonical_set(
            list(dietary_restrictions or []) + list(new_dietary_restrictions or []))
        try:
            cuisine_change_str = (f"New cuisine preference: {new_cuisine_preference}."
                                  if new_cuisine_preference else "")
            restriction_str = _restriction_block(merged)
            if restriction_str:
                restriction_str += (
                    "\n            These were already in force and REMAIN in force. "
                    "The feedback cannot remove them - if it asks for something that "
                    "conflicts, substitute a compliant ingredient and say so.")

            prompt = f"""Based on this feedback, please adapt the regional meal plan:

            Current Plan:
            {current_plan}

            User Feedback:
            {feedback}

            {cuisine_change_str}
            Please provide an updated regional meal plan that addresses the feedback while
            maintaining cultural authenticity and health benefits.{restriction_str}"""

            result = self._attempt(prompt, merged, macro_target, operation="adapt")

            if not result.usable:
                return _rejected(result, merged, "adapted plan")

            return {
                "success": True,
                "adapted_plan": result.text,
                "verification": result.as_dict(),
                "feedback": feedback,
                "new_cuisine_preference": new_cuisine_preference,
                # The authoritative set going forward, so a second adaptation
                # inherits everything rather than only the newest addition.
                "dietary_restrictions": merged,
                "new_dietary_restrictions": new_dietary_restrictions,
            }
        except Exception as e:
            if _is_rate_limit(e):
                logger.error("culinary adapt rate limited")
                return self._unavailable(merged, "adapt")
            logger.error("culinary adapt failed: %s", type(e).__name__, exc_info=True)
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _is_rate_limit(exc: Exception) -> bool:
    message = str(exc)
    return "rate_limit_exceeded" in message or "Rate limit reached" in message


def _restriction_block(restrictions) -> str:
    brief = dietary_rules.restriction_brief(restrictions)
    if not brief:
        return ""
    return "\n\n            " + brief.replace("\n", "\n            ")


def _rejected(result: "Assessment", restrictions, what: str) -> dict:
    audit = result.audit
    reason = (audit.summary() if audit and not audit.hard_safe
              else f"The {what} could not be produced in a usable form.")
    return {
        "success": False,
        "error": f"Could not produce a {what} that meets your dietary "
                 f"requirements — {reason}",
        "verification": result.as_dict(),
        "dietary_restrictions": list(restrictions or []),
    }


def _describe(result: "Assessment") -> str:
    """
    Bounded metadata for the log.

    Never the prompt, the plan, the feedback or the restriction list: those
    were all being written at INFO on every request, which put the user's
    health context and dietary requirements into the application log.
    """
    parts = [f"chars={len(result.text)}",
             f"dietary={result.audit.status if result.audit else 'n/a'}",
             f"violations={len(result.audit.violations) if result.audit else 0}",
             f"advisories={len(result.audit.advisories) if result.audit else 0}"]
    if result.macro is not None:
        parts.append(f"macros_checked={bool(result.macro.get('checked'))}")
        parts.append(f"macros_hit={bool(result.macro.get('hit'))}")
    return " ".join(parts)


def _generic_plan(cuisine_region: str) -> str:
    """
    The canned plan used when the model is unavailable.

    Deliberately built from plant, grain and vegetable staples only, so it
    clears the widest set of restrictions on its own merits - but it is still
    audited before being served, and withheld if it does not fit.
    """
    region = cuisine_region.replace("_", " ").title()
    return f"""**{region} Meal Plan 🍴**

### While the AI service is busy
A simple {region} outline built from widely-tolerated staples:

**Main Course:**
- Steamed rice or a regional whole grain
- Seasonal vegetable curry cooked in oil, not butter
- Lentils or beans simmered with regional spices

**Sides:**
- Fresh salad with local vegetables
- Lemon and herb chutney

**Cooking Tips:**
- Use traditional spices and cooking methods
- Focus on fresh, local produce
- Keep oil light and let the spices carry the dish

*Note: this is a general outline, not a personalised plan. Please try again
shortly for something built around your own requirements.*"""


def _generic_recipe(cuisine_region: str, dish_name: str = None) -> str:
    region = cuisine_region.replace("_", " ").title()
    title = dish_name or f"{region} Vegetable and Lentil Bowl"
    return f"""**{title} 🍴**

### While the AI service is busy
A simple {region} outline built from widely-tolerated staples:

**Ingredients:**
- Regional whole grain or rice
- Seasonal vegetables, chopped
- Lentils or beans
- Regional spices, oil, salt

**Method:**
1. Cook the grain according to its usual method.
2. Temper the spices in oil, add the vegetables, and cook until tender.
3. Simmer the lentils separately until soft, then combine and season.

*Note: this is a general outline, not a personalised recipe. Please try again
shortly for something built around your own requirements.*"""


culinaryexplorer_service = CulinaryExplorerService()
