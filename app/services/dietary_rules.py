"""
What a stated dietary restriction actually forbids, as data.

WHY THIS EXISTS
---------------
Dietary restrictions reached the meal planner as a comma-joined string inside
a prompt and nothing else. "vegan" plus a plan containing milk returned
success; so did nut-free with peanuts and gluten-free with wheat bread. The
restriction was a suggestion the model was free to ignore, and nothing
downstream ever looked.

This module is the single vocabulary for that question, deliberately separate
from any one agent so ChefGenius, BudgetChef and CulinaryExplorer can consume
the identical rules later rather than each growing their own list.

WHAT THIS IS AND IS NOT
-----------------------
This is INGREDIENT-NAME MATCHING. It catches a plan that openly lists milk
for a vegan user, which is the failure that actually happens. It cannot
certify that a dish is safe for someone with a medical allergy - it does not
know the recipe, the kitchen, or the supply chain, and no name-matching layer
does.

So the audit reports two different things and never conflates them:

    violations  an explicitly listed forbidden ingredient. A hard failure.
    advisories  something worth flagging that is not proof - a precautionary
                "may contain nuts" label, or a restriction this schema
                cannot verify at all.

`status` says which of those happened, and the caller is expected to show the
advisory wording rather than implying the plan was cleared.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

# ---------------------------------------------------------------------------
# canonical restriction names
# ---------------------------------------------------------------------------
#
# The same restriction arrives as "gluten-free", "gluten_free", "Gluten Free"
# and "glutenfree" depending on whether it came from the dropdown, free text
# or a saved plan. Normalising once here is what stops three different
# spellings silently meaning three different things.

VEGETARIAN = "vegetarian"
VEGAN = "vegan"
DAIRY_FREE = "dairy_free"
GLUTEN_FREE = "gluten_free"
NUT_FREE = "nut_free"
EGG_FREE = "egg_free"

# Nutrient-style labels. These are not ingredient bans - they are claims about
# the numbers, so they are assessed from macros where the schema supports it
# and reported as unverifiable where it does not.
LOW_CARB = "low_carb"
KETO = "keto"
LOW_FAT = "low_fat"
LOW_SODIUM = "low_sodium"
DIABETIC_FRIENDLY = "diabetic_friendly"
HEART_HEALTHY = "heart_healthy"
PALEO = "paleo"

_ALIASES: Dict[str, str] = {
    "vegetarian": VEGETARIAN, "veggie": VEGETARIAN,
    "vegan": VEGAN, "plantbased": VEGAN, "plant based": VEGAN,
    "dairyfree": DAIRY_FREE, "dairy free": DAIRY_FREE, "nodairy": DAIRY_FREE,
    "lactosefree": DAIRY_FREE, "lactose free": DAIRY_FREE,
    "glutenfree": GLUTEN_FREE, "gluten free": GLUTEN_FREE, "nogluten": GLUTEN_FREE,
    "celiac": GLUTEN_FREE, "coeliac": GLUTEN_FREE,
    "nutfree": NUT_FREE, "nut free": NUT_FREE, "nonuts": NUT_FREE,
    "treenutfree": NUT_FREE, "tree nut free": NUT_FREE, "peanutfree": NUT_FREE,
    "eggfree": EGG_FREE, "egg free": EGG_FREE, "noeggs": EGG_FREE, "noegg": EGG_FREE,
    "lowcarb": LOW_CARB, "low carb": LOW_CARB,
    "keto": KETO, "ketogenic": KETO,
    "lowfat": LOW_FAT, "low fat": LOW_FAT,
    "lowsodium": LOW_SODIUM, "low sodium": LOW_SODIUM, "lowsalt": LOW_SODIUM,
    "diabeticfriendly": DIABETIC_FRIENDLY, "diabetic friendly": DIABETIC_FRIENDLY,
    "diabetic": DIABETIC_FRIENDLY,
    "hearthealthy": HEART_HEALTHY, "heart healthy": HEART_HEALTHY,
    "paleo": PALEO, "paleolithic": PALEO,
}

# Restrictions this module enforces by looking at ingredients.
INGREDIENT_RESTRICTIONS = {VEGETARIAN, VEGAN, DAIRY_FREE, GLUTEN_FREE,
                           NUT_FREE, EGG_FREE}

# Assessable from the four-macro schema the planner already produces.
MACRO_RESTRICTIONS = {LOW_CARB, KETO, LOW_FAT}

# Cannot be established from calories/protein/carbs/fat. Sodium, glycaemic
# load and saturated-fat share are simply not in the schema, so claiming to
# have verified them would be inventing certainty.
UNVERIFIABLE_RESTRICTIONS = {LOW_SODIUM, DIABETIC_FRIENDLY, HEART_HEALTHY, PALEO}


def canonical(raw: Any) -> Optional[str]:
    """"Gluten-Free" / "gluten_free" / "gluten free" -> "gluten_free"."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    squashed = re.sub(r"[\s_-]+", " ", text).strip()
    if squashed in _ALIASES:
        return _ALIASES[squashed]
    tight = squashed.replace(" ", "")
    if tight in _ALIASES:
        return _ALIASES[tight]
    # Unknown restriction: keep it in a stable shape rather than dropping it,
    # so the caller can still report that something was requested and not
    # verified instead of pretending it was never asked for.
    return re.sub(r"[^a-z0-9]+", "_", squashed).strip("_") or None


def canonical_set(values: Optional[Iterable[Any]]) -> List[str]:
    """Normalise a list of restrictions, de-duplicated, order preserved."""
    out: List[str] = []
    for value in values or []:
        name = canonical(value)
        if name and name not in out:
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# forbidden ingredients
# ---------------------------------------------------------------------------
#
# Matched as whole words against a normalised ingredient name. Word
# boundaries do most of the false-positive work for free: "\begg\b" does not
# match "eggplant", "\bnuts?\b" does not match "nutmeg" or "butternut", and
# "\bbutter\b" does not match "butternut" - in each case the two words run
# together with no boundary between them.
#
# What word boundaries CANNOT solve is a phrase whose head noun is genuinely
# the forbidden word but which is not the forbidden thing: "coconut milk" is
# milk-shaped and contains no dairy, "peanut butter" is butter-shaped and
# contains no dairy, "gluten-free bread" is bread-shaped and contains no
# gluten. Those are handled by CLEARED_BY below, which exempts a specific
# ingredient from a specific restriction before the forbidden list is
# consulted at all.

_MEAT = [
    "chicken", "beef", "pork", "lamb", "mutton", "goat", "veal", "venison",
    "bacon", "ham", "sausage", "salami", "pepperoni", "prosciutto", "chorizo",
    "meat", "steak", "turkey", "duck", "liver", "keema", "mince", "brisket",
]
_FISH = [
    "fish", "salmon", "tuna", "cod", "haddock", "sardine", "sardines",
    "anchovy", "anchovies", "mackerel", "trout", "prawn", "prawns", "shrimp",
    "crab", "lobster", "squid", "octopus", "clam", "clams", "mussel",
    "mussels", "oyster", "oysters", "shellfish", "seafood", "fish sauce",
]
_ANIMAL_SET = ["gelatin", "gelatine", "lard", "tallow", "suet", "bone broth",
               "rennet", "isinglass"]
_DAIRY = [
    "milk", "cheese", "butter", "yogurt", "yoghurt", "curd", "dahi", "paneer",
    "ghee", "cream", "whey", "casein", "buttermilk", "custard", "kefir",
    "ricotta", "mozzarella", "cheddar", "parmesan", "mascarpone", "condensed milk",
    "khoya", "malai", "lassi",
]
_EGG = ["egg", "eggs", "albumen", "egg white", "egg yolk", "mayonnaise", "meringue"]
_GLUTEN = [
    "wheat", "barley", "rye", "semolina", "sooji", "rava", "maida", "seitan",
    "couscous", "bulgur", "farro", "spelt", "durum", "bread", "pasta",
    "noodles", "chapati", "roti", "naan", "paratha", "biscuit", "cracker",
    "breadcrumbs", "soy sauce", "beer", "malt",
]
_NUTS = [
    "peanut", "peanuts", "almond", "almonds", "cashew", "cashews", "walnut",
    "walnuts", "pecan", "pecans", "pistachio", "pistachios", "hazelnut",
    "hazelnuts", "macadamia", "brazil nut", "pine nut", "pine nuts",
    "tree nut", "tree nuts", "nut", "nuts", "nut butter", "chestnut",
    "chestnuts", "marzipan",
    "praline", "nutella",
    # Coconut is classed as a tree nut for allergen labelling (FDA), so a
    # nut-free request has to see it even though it is botanically a drupe
    # and is fine for vegan/dairy-free.
    "coconut",
]

FORBIDDEN: Dict[str, List[str]] = {
    VEGETARIAN: _MEAT + _FISH + _ANIMAL_SET,
    VEGAN: _MEAT + _FISH + _ANIMAL_SET + _DAIRY + _EGG + ["honey"],
    DAIRY_FREE: _DAIRY,
    GLUTEN_FREE: _GLUTEN,
    NUT_FREE: _NUTS,
    EGG_FREE: _EGG,
}

# An ingredient matching one of these is exempt from that restriction, checked
# BEFORE the forbidden list. Each entry exists because the ingredient's name
# contains a forbidden word while the ingredient itself does not contain the
# forbidden thing.
_PLANT_MILKS = [
    "coconut milk", "almond milk", "soy milk", "soya milk", "oat milk",
    "rice milk", "cashew milk", "hemp milk", "flax milk", "pea milk",
    "plant milk", "plant-based milk", "non-dairy milk", "nondairy milk",
    "coconut cream", "coconut yogurt", "coconut yoghurt", "soy yogurt",
    "almond yogurt", "oat cream", "soy cream",
]
_NUT_BUTTERS = ["peanut butter", "almond butter", "cashew butter",
                "nut butter", "seed butter", "tahini", "sunflower butter",
                "cocoa butter", "shea butter"]
# Established food names that NAME an animal but are not one. Deliberately a
# short, explicit list of compound names rather than any general heuristic:
# "Chicken of the Woods" is a bracket fungus, and the recipe-name audit
# (which is what makes a hidden "Chicken Biryani" catchable) would otherwise
# read it as poultry. Only exact compounds belong here - "chicken" alone must
# stay forbidden, which is what keeps "Chicken Biryani" caught.
_ANIMAL_NAMED_PLANTS = [
    "chicken of the woods", "hen of the woods", "beef steak fungus",
    "beefsteak fungus", "beefsteak tomato", "beef steak tomato",
    "oyster mushroom", "lion's mane", "lions mane", "crab apple",
    "monkfish tail mushroom", "vegetable oyster",
]

_VEGAN_ANALOGUES = ["vegan cheese", "plant-based cheese", "plant based cheese",
                    "vegan butter", "plant-based butter", "plant based butter",
                    "vegan cream", "vegan yogurt", "vegan yoghurt",
                    "nutritional yeast", "vegan mayonnaise", "vegan mayo",
                    "tofu cream cheese"]

CLEARED_BY: Dict[str, List[str]] = {
    # None of these are dairy despite being milk/butter/cream/cheese-shaped.
    DAIRY_FREE: _PLANT_MILKS + _NUT_BUTTERS + _VEGAN_ANALOGUES,
    VEGAN: _PLANT_MILKS + _NUT_BUTTERS + _VEGAN_ANALOGUES + _ANIMAL_NAMED_PLANTS + [
        "eggplant", "egg plant", "aquafaba", "vegan egg", "egg replacer",
        "egg substitute", "flax egg",
    ],
    # "gluten-free bread" / "gluten free pasta" are the whole point of the
    # category and must not be rejected for containing the word.
    GLUTEN_FREE: ["gluten-free", "gluten free", "glutenfree", "rice noodles",
                  "rice flour", "almond flour", "chickpea flour", "besan",
                  "corn flour", "cornflour", "buckwheat", "tamari",
                  "gluten-free soy sauce"],
    # "water chestnut" is an aquatic tuber and genuinely not a nut. Plain
    # "chestnut" is a tree nut and must NOT inherit that exemption - listing
    # it here meant "chestnut flour" passed a nut-free check.
    NUT_FREE: ["nutmeg", "butternut", "water chestnut",
               "nutritional yeast", "coconut oil", "coconut water"],
    EGG_FREE: ["eggplant", "egg plant", "aquafaba", "vegan egg", "egg replacer",
               "egg substitute", "flax egg", "vegan mayonnaise", "vegan mayo"],
    VEGETARIAN: ["mock meat", "meat substitute", "meat-free", "meat free",
                 "soy chunks", "jackfruit", "mushroom", "vegetarian sausage",
                 "veggie sausage", "plant-based meat", "plant based meat",
                 "fishless", "vegan fish sauce"] + _ANIMAL_NAMED_PLANTS,
}

# Precautionary labelling. Not proof of an allergen and not proof of absence -
# reported as an advisory so a nut-free user sees it rather than a silent pass.
_PRECAUTIONARY = re.compile(
    r"may\s+contain|traces?\s+of|processed\s+in\s+a\s+facility|"
    r"shared\s+equipment|manufactured\s+in\s+a\s+facility",
    re.I,
)


# Marks where one listed item ends and the next begins. Punctuation used to
# be flattened to whitespace, which erased exactly the information the
# modifier scope needs: "vegan cheese, milk" became "vegan cheese milk", so
# the two-word scope after "vegan" swallowed the milk and the violation
# vanished. Keeping an explicit barrier lets the scope stop at the item
# boundary while every other match behaves as before - the barrier is not a
# word character, so `[\s-]` and `[a-z0-9]` can never cross it.
_ITEM_BOUNDARY = "|"

# A hyphen is BOTH a word joiner and an item separator depending on spacing,
# and getting that distinction wrong breaks one side or the other:
#
#   "gluten-free bread"   tight hyphen  -> joiner, the phrase is one thing
#   "vegan cheese - milk" spaced hyphen -> separator, these are two things
#
# So the ASCII hyphen is only a boundary when it is surrounded by whitespace
# (or opens a bullet line). En dash, em dash and "+" are never intra-word
# joiners in an ingredient name, so those are unconditional boundaries.
#
# Everything here runs BEFORE the punctuation strip below, which is the only
# point at which the distinction is still visible - once "+" and "–" have
# been flattened to spaces, "vegan cheese + milk" is indistinguishable from
# "vegan cheese milk" and the modifier scope legitimately swallows the milk.
_SEPARATORS = re.compile(
    r"[,;/\n\r•·+–—]+"      # , ; / newline bullet + en-dash em-dash
    r"|(?<=\s)-+(?=\s)"               # a spaced ASCII hyphen
    r"|(?:(?<=^)|(?<=\n))\s*-+(?=\s)"  # a hyphen opening a bullet line
    r"|\bplus\b|\bwith\b|\band\b"
)


def _normalise_text(value: Any) -> str:
    """Lowercased, punctuation-stripped, with item boundaries preserved."""
    text = str(value or "").lower()
    text = text.replace("&", " and ")
    # Barriers first, while the punctuation is still there to see.
    text = _SEPARATORS.sub(f" {_ITEM_BOUNDARY} ", text)
    text = re.sub(rf"[^a-z0-9\s{re.escape(_ITEM_BOUNDARY)}-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _phrase_matches(normalised: str, phrase: str) -> bool:
    """Whole-word/phrase match, tolerating hyphen-vs-space in the phrase."""
    pattern = r"[\s-]+".join(re.escape(part) for part in phrase.split())
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", normalised) is not None


# Words that clear the INGREDIENT THEY QUALIFY rather than naming a specific
# exempt compound. "gluten-free" on its own exempts nothing - it is the noun
# after it ("gluten-free bread") that must be spared. These mask themselves
# plus the short noun phrase that follows, which is why
# "gluten-free bread made with wheat flour" still reports the wheat: only
# "gluten-free bread made" is masked, and the tail is scanned normally.
_CLEARING_MODIFIERS: Dict[str, List[str]] = {
    GLUTEN_FREE: ["gluten free", "glutenfree", "wheat free", "wheatfree"],
    DAIRY_FREE: ["non dairy", "nondairy", "dairy free", "dairyfree",
                 "vegan", "plant based", "plantbased"],
    VEGAN: ["vegan", "plant based", "plantbased"],
    VEGETARIAN: ["vegetarian", "veggie", "meat free", "meatfree", "mock",
                 "plant based", "plantbased", "fishless", "vegan"],
    EGG_FREE: ["egg free", "eggfree", "vegan"],
    NUT_FREE: ["nut free", "nutfree"],
}

# How many words after a clearing modifier belong to the thing it qualifies.
# Two is enough for "gluten free bread", "vegan cream cheese" and
# "plant based chicken strips" without swallowing a following clause.
_MODIFIER_SCOPE_WORDS = 2


def _cleared_pattern(phrase: str) -> str:
    """
    An approved phrase, tolerating hyphen-vs-space and a plural on the last
    word - "water chestnut" has to clear "water chestnuts" too, which it did
    not, so a legitimate exemption failed on the plural alone.
    """
    parts = [re.escape(p) for p in phrase.split()]
    parts[-1] = parts[-1] + r"e?s?"
    return r"[\s-]+".join(parts)


def _blank(match: "re.Match") -> str:
    return " " * len(match.group(0))


def _mask_cleared(normalised: str, restriction: str) -> str:
    """
    Blank out only the SPANS an approved phrase actually covers.

    An approved phrase used to exempt the entire ingredient string, so one
    compliant-looking compound cleared everything beside it:

        "vegan cheese with cow milk"              -> no violation
        "gluten-free bread made with wheat flour" -> no violation
        "coconut milk with whey"                  -> no violation

    Masking spans instead means "vegan cheese" stops "cheese" from firing
    while "cow milk" is still scanned. Replaced with spaces rather than
    deleted so the surrounding word boundaries - which every match here
    relies on - are preserved exactly.
    """
    masked = normalised

    # Modifiers first: they consume the noun phrase they qualify, so doing
    # them before the exact compounds avoids a compound being half-masked.
    for modifier in sorted(_CLEARING_MODIFIERS.get(restriction, []),
                           key=len, reverse=True):
        pattern = _cleared_pattern(modifier)
        masked = re.sub(
            rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
            rf"(?:[\s-]+[a-z0-9]+){{0,{_MODIFIER_SCOPE_WORDS}}}",
            _blank, masked)

    for phrase in sorted(CLEARED_BY.get(restriction, []), key=len, reverse=True):
        masked = re.sub(rf"(?<![a-z0-9]){_cleared_pattern(phrase)}(?![a-z0-9])",
                        _blank, masked)
    return masked


def _cleared(normalised: str, restriction: str) -> Optional[str]:
    """Which approved phrase this text contains, if any. Reporting only."""
    for phrase in CLEARED_BY.get(restriction, []):
        if _phrase_matches(normalised, phrase):
            return phrase
    return None


def forbidden_hit(text: Any, restriction: str) -> Optional[str]:
    """
    The forbidden ingredient this text names for this restriction, or None.

    Approved phrases are masked out span by span first (see `_mask_cleared`),
    then whatever remains is scanned. Longest phrase first, so "coconut milk"
    is considered before "milk" and the more specific answer wins when both
    would match.
    """
    normalised = _normalise_text(text)
    if not normalised:
        return None
    remaining = _mask_cleared(normalised, restriction)
    for phrase in sorted(FORBIDDEN.get(restriction, []), key=len, reverse=True):
        if _phrase_matches(remaining, phrase):
            return phrase
    return None


def precautionary(text: Any) -> bool:
    """Does this read as a 'may contain' style allergen warning?"""
    return bool(_PRECAUTIONARY.search(str(text or "")))


def strip_precautionary(text: Any) -> str:
    """
    The ingredient without its precautionary clause.

    "granola (may contain nuts)" is not an ingredient list containing nuts -
    it is granola, carrying a manufacturer's warning. Matching the forbidden
    word inside that clause turns every cautious label into a hard failure,
    which both over-blocks and teaches users that the warning is the problem.

    The clause is removed before hard matching and reported separately as an
    advisory. What is left is still matched normally, so
    "chicken curry (may contain nuts)" still fails a vegetarian check on the
    chicken - only the warning itself is discounted.
    """
    raw = str(text or "")
    match = _PRECAUTIONARY.search(raw)
    if not match:
        return raw
    start = match.start()
    # Back up over an opening bracket/dash that introduced the clause.
    while start > 0 and raw[start - 1] in " \t":
        start -= 1
    if start > 0 and raw[start - 1] in "([-–—,;":
        start -= 1
    closing = raw.find(")", match.end())
    end = closing + 1 if closing != -1 else len(raw)
    return (raw[:start] + " " + raw[end:]).strip()


# ---------------------------------------------------------------------------
# the audit
# ---------------------------------------------------------------------------

STATUS_OK = "ok"                    # nothing found, everything checkable checked
STATUS_ADVISORY = "advisory"        # nothing forbidden, but caveats apply
STATUS_VIOLATION = "violation"      # an explicitly forbidden ingredient


@dataclass
class Finding:
    day: str
    meal: str
    restriction: str
    ingredient: str
    matched: str
    source: str = "ingredient"   # ingredient | recipe_name

    def as_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day, "meal": self.meal, "restriction": self.restriction,
            "ingredient": self.ingredient, "matched": self.matched,
            "source": self.source,
        }


@dataclass
class DietaryAudit:
    restrictions: List[str] = field(default_factory=list)
    violations: List[Finding] = field(default_factory=list)
    advisories: List[str] = field(default_factory=list)
    unverifiable: List[str] = field(default_factory=list)
    checked: List[str] = field(default_factory=list)

    @property
    def hard_safe(self) -> bool:
        """No explicitly forbidden ingredient anywhere. The gate that matters."""
        return not self.violations

    @property
    def status(self) -> str:
        if self.violations:
            return STATUS_VIOLATION
        if self.advisories or self.unverifiable:
            return STATUS_ADVISORY
        return STATUS_OK

    def summary(self) -> str:
        if self.violations:
            first = self.violations[0]
            extra = (f" (and {len(self.violations) - 1} more)"
                     if len(self.violations) > 1 else "")
            return (f"{first.restriction.replace('_', ' ')} conflict: "
                    f"{first.ingredient!r} in {first.day} {first.meal}{extra}.")
        if self.unverifiable:
            return ("No forbidden ingredients found. Could not verify: "
                    + ", ".join(r.replace("_", " ") for r in self.unverifiable) + ".")
        if self.advisories:
            return "No forbidden ingredients found, with caveats."
        if self.checked:
            return "No forbidden ingredients found for " + ", ".join(
                r.replace("_", " ") for r in self.checked) + "."
        return "No dietary restrictions to check."

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "hard_safe": self.hard_safe,
            "restrictions": list(self.restrictions),
            "checked": list(self.checked),
            "violations": [v.as_dict() for v in self.violations],
            "advisories": list(self.advisories),
            "unverifiable": list(self.unverifiable),
            "summary": self.summary(),
        }


def _meal_ingredient_texts(meal: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for item in (meal or {}).get("ingredients") or []:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = item
        if name is not None and str(name).strip():
            out.append(str(name))
    return out


def audit_plan(plan: Dict[str, Any], restrictions: Optional[Iterable[Any]],
               macro_totals_by_day: Optional[Dict[str, Dict[str, float]]] = None
               ) -> DietaryAudit:
    """
    Check a parsed plan against the user's restrictions.

    Ingredient names are the primary signal. Recipe names are checked as a
    DEFENSIVE SECONDARY signal only where a meal's ingredient list is missing
    or empty - a "Chicken Biryani" with no ingredients listed should not pass
    a vegetarian check just because the list the matcher wanted was absent.
    Where a full ingredient list IS present it is treated as authoritative,
    so a dish legitimately named "Butter-free Paneer Alternative" is judged on
    what is in it.
    """
    names = canonical_set(restrictions)
    audit = DietaryAudit(restrictions=names)

    ingredient_names = [r for r in names if r in INGREDIENT_RESTRICTIONS]
    audit.checked = list(ingredient_names)

    for restriction in names:
        if restriction in UNVERIFIABLE_RESTRICTIONS:
            audit.unverifiable.append(restriction)
        elif restriction not in INGREDIENT_RESTRICTIONS and restriction not in MACRO_RESTRICTIONS:
            audit.unverifiable.append(restriction)

    days = (plan or {}).get("plan") or {}
    if isinstance(days, dict) and ingredient_names:
        for day_name in sorted(days.keys()):
            meals = days.get(day_name)
            if not isinstance(meals, list):
                continue
            for index, meal in enumerate(meals):
                if not isinstance(meal, dict):
                    continue
                label = meal.get("meal_label") or f"meal {index + 1}"
                texts = _meal_ingredient_texts(meal)
                sources = [(t, "ingredient") for t in texts]

                # The recipe name is ALWAYS checked, not only when the
                # ingredient list is missing.
                #
                # Treating a present ingredient list as authoritative sounded
                # principled and was exactly the hole: structural validation
                # already requires a non-empty list, so the "authoritative"
                # branch fired on every real plan and the name branch never
                # did. A model could then name the dish "Chicken Biryani",
                # list only rice and spices, and pass a vegetarian check.
                # Omitting the forbidden item from the list while keeping it
                # in the title is precisely the failure mode worth catching.
                #
                # The modifier exemptions above are what keep this from
                # over-firing: "Vegan Chicken Curry" and "Plant-Based Meat
                # Bowl" clear on their own modifier, so an analogue is not
                # reported as the thing it imitates.
                if meal.get("recipe_name"):
                    sources.append((str(meal["recipe_name"]), "recipe_name"))

                for text, source in sources:
                    matchable = text
                    if precautionary(text):
                        note = (f"{day_name} {label}: {text!r} carries a "
                                f"precautionary allergen warning - not proof of "
                                f"an allergen, but check the packaging.")
                        if note not in audit.advisories:
                            audit.advisories.append(note)
                        # Judge the ingredient, not its warning label.
                        matchable = strip_precautionary(text)
                    for restriction in ingredient_names:
                        hit = forbidden_hit(matchable, restriction)
                        if hit:
                            audit.violations.append(Finding(
                                day=day_name, meal=str(label),
                                restriction=restriction, ingredient=text,
                                matched=hit, source=source,
                            ))

    # Macro-assessable labels, where the plan gives us the numbers.
    macro_names = [r for r in names if r in MACRO_RESTRICTIONS]
    if macro_names:
        if macro_totals_by_day:
            audit.checked.extend(macro_names)
            for restriction in macro_names:
                breaches = _macro_breaches(restriction, macro_totals_by_day)
                audit.advisories.extend(breaches)
        else:
            audit.unverifiable.extend(macro_names)

    if audit.unverifiable:
        audit.advisories.append(
            "These were requested but cannot be confirmed from the plan's "
            "nutrition fields: "
            + ", ".join(r.replace("_", " ") for r in audit.unverifiable)
            + ". Treat them as unchecked."
        )
    return audit


# Thresholds for the labels the four-macro schema can actually speak to.
_LOW_CARB_MAX_G = 130.0     # widely used "low carb" daily ceiling
_KETO_MAX_G = 50.0          # ketogenic daily ceiling
_LOW_FAT_MAX_ENERGY = 0.30  # share of calories from fat


def _macro_breaches(restriction: str,
                    totals_by_day: Dict[str, Dict[str, float]]) -> List[str]:
    out: List[str] = []
    for day in sorted(totals_by_day):
        totals = totals_by_day[day] or {}
        carbs = float(totals.get("carbs") or 0.0)
        fat = float(totals.get("fat") or 0.0)
        calories = float(totals.get("calories") or 0.0)
        if restriction == LOW_CARB and carbs > _LOW_CARB_MAX_G:
            out.append(f"{day}: {carbs:.0f}g carbs is above a low-carb day "
                       f"(<= {_LOW_CARB_MAX_G:.0f}g).")
        elif restriction == KETO and carbs > _KETO_MAX_G:
            out.append(f"{day}: {carbs:.0f}g carbs is above a ketogenic day "
                       f"(<= {_KETO_MAX_G:.0f}g).")
        elif restriction == LOW_FAT and calories > 0:
            share = (fat * 9.0) / calories
            if share > _LOW_FAT_MAX_ENERGY:
                out.append(f"{day}: {share * 100:.0f}% of calories from fat is "
                           f"above a low-fat day "
                           f"(<= {_LOW_FAT_MAX_ENERGY * 100:.0f}%).")
    return out


def restriction_brief(restrictions: Optional[Iterable[Any]]) -> str:
    """The hard-requirement wording handed to a generator."""
    names = [r for r in canonical_set(restrictions) if r in INGREDIENT_RESTRICTIONS]
    if not names:
        return ""
    lines = ["HARD DIETARY RESTRICTIONS - these are absolute, not preferences.",
             "A plan containing any of these is rejected outright:"]
    for name in names:
        examples = ", ".join(sorted(set(FORBIDDEN.get(name, [])))[:10])
        lines.append(f"  - {name.replace('_', ' ')}: no {examples}, or anything "
                     f"containing them.")
    lines.append("Every ingredient of every meal is checked against this list "
                 "after generation, so a substitution you did not actually make "
                 "will be caught.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown projection
# ---------------------------------------------------------------------------
#
# CulinaryExplorer returns Markdown prose, not the structured day/meal object
# audit_plan() expects. Rather than inventing a second vocabulary for it, this
# projects Markdown down to the same question the structured auditor asks -
# "which food names is this line PRESCRIBING?" - and then reuses
# forbidden_hit(), the exemptions, and the precautionary handling unchanged.
#
# TWO THINGS MARKDOWN NEEDS THAT AN INGREDIENT LIST DOES NOT
#
# 1. NEGATION. An ingredient list never contains an entry called "without
#    milk"; prose contains it constantly, and so do "no cream", "instead of
#    ghee" and "use plant-based milk, not cow milk". forbidden_hit() has no
#    notion of negation - correctly, for its own input shape - so the line is
#    cut at the first avoidance phrase and only the part BEFORE it is treated
#    as prescribed. Same positional rule contraindications._earliest_avoidance
#    already uses for exercises: "Chicken curry, no rice" still reports the
#    chicken, because the avoidance comes after it.
#
# 2. CONFIDENCE BY LINE SHAPE. A bulleted ingredient, a numbered step, a
#    heading and a bold dish name are PRESCRIPTIONS. A loose prose paragraph
#    might be describing, comparing or warning. Both are checked, but only the
#    structural shapes are treated as hard conflicts; prose is advisory, which
#    is what stops an explanatory sentence being reported with the same
#    confidence as an ingredient line.
#
# This is not allergen certification and does not claim to be. It catches a
# plan that openly prescribes a forbidden food, which is the failure that
# actually happens.

_MD_BULLET = re.compile(r"^\s*(?:[-*•+]|\d+[.)])\s+(.*\S)\s*$")
_MD_HEADING = re.compile(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$")
_MD_BOLD_LEAD = re.compile(r"^\s*\*{1,2}([^*]+?)\*{1,2}\s*:?\s*(.*)$")

# A Markdown table row. Models reach for tables whenever they are asked for
# quantities, and "| Milk | 200ml |" is every bit as much a prescription as
# "- Milk, 200ml". The alignment row (|---|:--:|) is not content.
_MD_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_MD_TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

# "Ingredients: chicken, salt" is the single most common recipe shape there
# is, and without this it reads as prose. Only these labels promote the text
# after the colon - a general "short label + colon" rule would swallow
# "Note: some families add cheese", which genuinely is commentary.
_MD_LABELLED = re.compile(
    r"^\s*(ingredients?|method|steps?|serves?\s+with|serving\s+suggestions?|"
    r"sides?|accompaniments?|garnish|breakfast|lunch|dinner|snacks?|"
    r"meal\s*\d*|dish|main|starter|dessert|beverages?|drinks?)\s*:\s*(.+)$",
    re.I,
)

# Clause boundaries that end an exclusion. Deliberately excludes "and"/"or",
# so "without milk or cream" excludes both - only a real break in the
# sentence ends the avoidance.
_CLAUSE_END = re.compile(r"[,;.\n]|\bbut\b", re.I)

# Phrases meaning the food named after them is being EXCLUDED, not served.
_AVOIDANCE = re.compile(
    r"\b(?:no|not|non|without|avoid(?:ing)?|omit(?:ting)?|skip(?:ping)?|"
    r"instead\s+of|in\s+place\s+of|rather\s+than|replace(?:s|d)?|"
    r"replacing|substitut\w*|swap(?:ped|ping)?|switch(?:ed|ing)?|"
    r"exchang(?:e|ed|ing)|remov(?:e|es|ed|ing)|drop(?:ped|ping)?|"
    r"discard(?:ed|ing)?|cut\s+out|forgo|free\s+from|hold\s+the|minus|"
    r"sans|except|excluding|leave\s+out|left\s+out|leave\s+off)\b",
    re.I,
)

# The subset of the above that takes a REPLACEMENT TARGET: "replace X with Y"
# names Y as the thing now being served. "instead of" and "rather than" are
# deliberately NOT here - in "coconut oil instead of butter" the food after
# the phrase is the one being dropped, not the one being added.
_REPLACEMENT_VERB = re.compile(
    r"^(?:replace(?:s|d)?|replacing|substitut\w*|swap(?:ped|ping)?|"
    r"switch(?:ed|ing)?|exchang(?:e|ed|ing))$",
    re.I,
)

# What introduces the replacement target after such a verb.
_REPLACE_TARGET = re.compile(r"\b(?:with|for|by)\b", re.I)

# A connector that ends an exclusion by starting a new PRESCRIPTION.
# "and cream" is still part of the exclusion; "and serve cream" is not - the
# serving verb is what makes the difference, so a bare conjunction never
# resumes and "without milk or cream" keeps excluding both.
_RESUME = re.compile(
    r"\b(?:and|then|plus|also|before|after)\s+(?:also\s+|instead\s+)?"
    r"(?:add(?:s|ing)?|serve[sd]?|serving|use[sd]?|using|include[sd]?|"
    r"including|top(?:ped|ping)?\s+with|garnish(?:ed|ing)?\s+with|"
    r"finish(?:ed|ing)?\s+with|stir(?:red|ring)?\s+in|mix(?:ed|ing)?\s+in|"
    r"pair(?:ed|ing)?\s+with|swap\s+in|put\s+in)\b",
    re.I,
)

# Wording that makes an item conditional rather than prescribed. Reported as
# an advisory: "optional chicken" is not served to a vegetarian by default,
# but it is absolutely worth telling them it is on the page.
_OPTIONAL = re.compile(
    r"\boptional(?:ly)?\b|\bif\s+(?:you\s+)?(?:like|prefer|wish|desired?|"
    r"available|not\s+vegan|non[\s-]?veg)\b|\bto\s+taste\b|\bor\s+omit\b",
    re.I,
)

# Emoji/label noise the agent is explicitly told to emit, which would
# otherwise read as content ("🍗 Contains meat/poultry" is a legend entry).
_LEGEND_LINE = re.compile(
    r"^\s*[^\w]*\s*(?:contains|vegetarian|vegan|gluten[\s-]?free|"
    r"healthier\s+version)\b.{0,40}$",
    re.I,
)


def split_prescription(line: str) -> tuple:
    """
    Split a line into (prescribed, excluded) text.

    A modification instruction names TWO foods with opposite meanings, and
    collapsing them into one string gets the safety answer wrong in both
    directions. "Replace tofu with paneer" served paneer to a vegan while
    "Remove paneer and use tofu" reported a paneer violation that was never
    on the plate. Only the prescribed side is scanned for forbidden foods.

        "Replace tofu with paneer"      -> ("paneer",        "tofu")
        "Swap tofu for chicken"         -> ("chicken",       "tofu")
        "No ghee and add paneer"        -> ("paneer",        "ghee")
        "Without milk and serve cheese" -> ("cheese",        "milk")
        "Omit butter then add cheese"   -> ("cheese",        "butter")
        "Drop tofu, add paneer"         -> ("paneer",        "tofu")
        "Chicken curry, no rice"        -> ("Chicken curry", "rice")
        "Cooked without milk or cream"  -> ("Cooked",        "milk or cream")
        "Coconut oil instead of butter" -> ("Coconut oil",   "butter")

    The line is walked as alternating runs. It starts prescribed; an
    avoidance phrase opens an excluded run; the run closes at whichever comes
    first of a clause boundary, a connector that starts a new prescription
    ("and add", "then serve"), or - after a replacement verb only - the
    "with"/"for" that introduces what is being served in its place. A bare
    conjunction never closes it, so "without milk or cream" excludes both.
    """
    text = line or ""
    prescribed, excluded = [], []
    pos, replacement = 0, False
    excluding = False

    for _ in range(16):                      # bounded; lines are short
        if pos >= len(text):
            break
        if not excluding:
            match = _AVOIDANCE.search(text, pos)
            if not match:
                prescribed.append(text[pos:])
                break
            prescribed.append(text[pos:match.start()])
            replacement = bool(_REPLACEMENT_VERB.match(match.group(0)))
            pos, excluding = match.end(), True
            continue

        ends = [m for m in (_CLAUSE_END.search(text, pos),
                            _RESUME.search(text, pos)) if m]
        if replacement:
            target = _REPLACE_TARGET.search(text, pos)
            if target:
                ends.append(target)
        if not ends:
            excluded.append(text[pos:])
            break
        nearest = min(ends, key=lambda m: m.start())
        excluded.append(text[pos:nearest.start()])
        # A clause boundary is kept as a separator on the prescribed side; a
        # connector or replacement target is consumed.
        pos = nearest.start() if nearest.re is _CLAUSE_END else nearest.end()
        excluding, replacement = False, False

    # Joined with a separator forbidden_hit() already splits on, so two runs
    # never fuse into one phrase.
    return ", ".join(p for p in prescribed if p.strip()), \
           ", ".join(e for e in excluded if e.strip())


def _prescribed_part(line: str) -> str:
    """The part of a line that is actually being served."""
    return split_prescription(line)[0]


def markdown_food_candidates(text: str) -> List[tuple]:
    """
    (food_text, shape, heading) for each line worth auditing.

    `shape` is "structural" for headings, bullets, numbered items and bold
    dish names - things a plan PRESCRIBES - and "prose" for everything else.
    """
    out: List[tuple] = []
    heading = ""
    items = 0                       # structural ITEM lines, headings excluded
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        head = _MD_HEADING.match(line)
        if head:
            heading = head.group(1).strip()
            out.append((heading, "structural", heading))
            continue

        if _LEGEND_LINE.match(line.strip()):
            continue

        bullet = _MD_BULLET.match(line)
        if bullet:
            out.append((bullet.group(1), "structural", heading))
            items += 1
            continue

        if _MD_TABLE_RULE.match(line):
            continue
        row = _MD_TABLE_ROW.match(line)
        if row:
            for cell in row.group(1).split("|"):
                if cell.strip():
                    out.append((cell.strip(), "structural", heading))
            items += 1
            continue

        labelled = _MD_LABELLED.match(line)
        if labelled:
            out.append((labelled.group(2).strip(), "structural", heading))
            items += 1
            continue

        bold = _MD_BOLD_LEAD.match(line)
        if bold:
            label, rest = bold.group(1).strip(), (bold.group(2) or "").strip()
            out.append((label, "structural", heading))
            if rest:
                out.append((rest, "structural", heading))
            items += 1
            continue

        out.append((line.strip(), "prose", heading))

    # "Prose is only advisory" is a concession to STRUCTURED documents, where
    # the bullets carry the prescription and the paragraphs comment on it.
    # A document with no item structure has no bullets to defer to - there,
    # the paragraphs ARE the plan, and treating them as advisory let an
    # entirely prose-written "you will prepare chicken curry" reach a
    # vegetarian as a clean success. Fail closed instead.
    if items < 2:
        out = [(food, "structural", head) for food, _shape, head in out]
    return out


def audit_markdown(text: str, restrictions: Optional[Iterable[Any]],
                   macro_totals: Optional[Dict[str, float]] = None) -> DietaryAudit:
    """
    Audit a Markdown plan or recipe, returning the same DietaryAudit shape
    audit_plan() returns so callers can treat both identically.

    Structural lines produce hard violations. Prose, optional wording and
    precautionary labels produce advisories - surfaced, never silently
    passed, but not claimed as proof.
    """
    names = canonical_set(restrictions)
    audit = DietaryAudit(restrictions=names)

    ingredient_names = [r for r in names if r in INGREDIENT_RESTRICTIONS]
    audit.checked = list(ingredient_names)

    for restriction in names:
        if restriction in UNVERIFIABLE_RESTRICTIONS:
            audit.unverifiable.append(restriction)
        elif restriction not in INGREDIENT_RESTRICTIONS and restriction not in MACRO_RESTRICTIONS:
            audit.unverifiable.append(restriction)

    if ingredient_names and text:
        for food, shape, heading in markdown_food_candidates(text):
            optional = bool(_OPTIONAL.search(food))
            matchable = food
            if precautionary(food):
                note = (f"{food.strip()!r} carries a precautionary allergen "
                        f"warning - not proof, but check the packaging.")
                if note not in audit.advisories:
                    audit.advisories.append(note)
                matchable = strip_precautionary(food)

            matchable = _prescribed_part(matchable)
            if not matchable.strip():
                continue

            for restriction in ingredient_names:
                hit = forbidden_hit(matchable, restriction)
                if not hit:
                    continue
                where = heading or "plan"
                if shape == "structural" and not optional:
                    audit.violations.append(Finding(
                        day=where, meal=food.strip()[:80],
                        restriction=restriction, ingredient=food.strip()[:120],
                        matched=hit, source="markdown",
                    ))
                else:
                    reason = "optional" if optional else "mentioned in prose"
                    note = (f"{where}: {food.strip()[:80]!r} names {hit!r}, "
                            f"which is not {restriction.replace('_', ' ')} "
                            f"({reason}) - check before cooking.")
                    if note not in audit.advisories:
                        audit.advisories.append(note)

    macro_names = [r for r in names if r in MACRO_RESTRICTIONS]
    if macro_names:
        if macro_totals:
            audit.checked.extend(macro_names)
            audit.advisories.extend(
                _macro_breaches(r, {"the plan": macro_totals}) for r in macro_names)
            audit.advisories = [a for a in audit.advisories if a]
            audit.advisories = [a for sub in audit.advisories
                                for a in (sub if isinstance(sub, list) else [sub])]
        else:
            audit.unverifiable.extend(macro_names)

    if audit.unverifiable:
        audit.advisories.append(
            "These were requested but cannot be confirmed from the text: "
            + ", ".join(r.replace("_", " ") for r in audit.unverifiable)
            + ". Treat them as unchecked."
        )
    return audit
