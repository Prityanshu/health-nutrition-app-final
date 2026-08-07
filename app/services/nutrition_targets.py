"""
Deterministic calculation of calorie and macronutrient targets.

WHY THIS IS NOT AN LLM CALL
---------------------------
These numbers affect what someone eats. A language model would return slightly
different figures for identical inputs, cannot be unit-tested, and occasionally
produces values that are simply wrong. The arithmetic here is a published,
citable methodology, runs in microseconds, costs no API quota, and gives the
same answer every time.

METHOD
------
1. BMR via Mifflin-St Jeor (1990) - the equation with the best documented
   accuracy for the general population.
       men:   10*kg + 6.25*cm - 5*age + 5
       women: 10*kg + 6.25*cm - 5*age - 161
2. TDEE = BMR x activity multiplier.
3. Goal adjustment applied as a percentage of TDEE rather than a flat number,
   so a 55 kg and a 110 kg person get proportionate deficits.
4. Protein set per kg of bodyweight (the variable that actually drives muscle
   retention), fat set as a percentage of calories with a floor for hormonal
   health, carbohydrate takes the remainder.

SAFETY
------
Deficits are capped and calorie floors enforced. A goal that would require an
unsafe intake is clamped and the clamping is reported in `warnings` rather than
being applied silently - the caller is expected to show those to the user.

This module is pure: no database, no network, no logging side effects.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

Sex = Literal["male", "female", "other"]

# --- constants -------------------------------------------------------------

ACTIVITY_MULTIPLIERS: Dict[str, float] = {
    "sedentary": 1.2,            # desk job, little deliberate exercise
    "lightly_active": 1.375,     # light exercise 1-3 days/week
    "moderately_active": 1.55,   # moderate exercise 3-5 days/week
    "very_active": 1.725,        # hard exercise 6-7 days/week
    "extra_active": 1.9,         # physical job or twice-daily training
}

# Absolute floors. Below these, meeting micronutrient needs from food becomes
# impractical and the deficit is not something an app should be prescribing.
CALORIE_FLOOR = {"male": 1500.0, "female": 1200.0, "other": 1350.0}

# Never prescribe a deficit larger than this share of maintenance.
MAX_DEFICIT_FRACTION = 0.25
# Nor a surplus larger than this - excess beyond it is mostly fat gain.
MAX_SURPLUS_FRACTION = 0.20
# Safe rate of weight change, as a fraction of bodyweight per week.
MAX_WEEKLY_LOSS_FRACTION = 0.01
MAX_WEEKLY_GAIN_FRACTION = 0.005

# Roughly the energy stored in a kilogram of body tissue.
KCAL_PER_KG = 7700.0

# Fat should not drop below this share of calories (hormone production).
MIN_FAT_FRACTION = 0.20


@dataclass(frozen=True)
class GoalPreset:
    """A named goal with its energy adjustment and macro strategy."""
    key: str
    label: str
    description: str
    # Positive = surplus, negative = deficit, as a fraction of TDEE.
    calorie_adjustment: float
    protein_g_per_kg: float
    fat_fraction: float
    needs_target_weight: bool = False
    tags: List[str] = field(default_factory=list)


# Deliberately broad. Users describe the same intent in many ways, so several
# presets map onto similar maths but use the language people actually reach for.
GOAL_PRESETS: Dict[str, GoalPreset] = {
    "weight_loss": GoalPreset(
        key="weight_loss",
        label="Lose weight",
        description="A moderate deficit with high protein to hold on to muscle while fat comes off.",
        calorie_adjustment=-0.20,
        protein_g_per_kg=2.0,
        fat_fraction=0.25,
        needs_target_weight=True,
        tags=["lose weight", "lose", "cut", "slim", "fat loss", "reduce", "drop", "shred", "leaner", "belly"],
    ),
    "gentle_weight_loss": GoalPreset(
        key="gentle_weight_loss",
        label="Lose weight slowly",
        description="A small deficit that is easier to sustain and gentler on training and energy levels.",
        calorie_adjustment=-0.10,
        protein_g_per_kg=1.8,
        fat_fraction=0.28,
        needs_target_weight=True,
        tags=["slowly", "sustainable", "gradual", "gently", "steady", "long term"],
    ),
    "muscle_gain": GoalPreset(
        key="muscle_gain",
        label="Build muscle",
        description="A controlled surplus with plenty of protein and enough carbohydrate to train hard.",
        calorie_adjustment=0.12,
        protein_g_per_kg=1.8,
        fat_fraction=0.25,
        tags=["build muscle", "gain muscle", "bulk", "strength", "stronger", "mass", "muscle", "gym", "lift"],
    ),
    "lean_bulk": GoalPreset(
        key="lean_bulk",
        label="Build muscle, stay lean",
        description="A smaller surplus that adds muscle more slowly with less fat gain.",
        calorie_adjustment=0.07,
        protein_g_per_kg=2.0,
        fat_fraction=0.25,
        tags=["lean bulk", "clean bulk", "stay lean", "slow bulk", "minimal fat"],
    ),
    "body_recomposition": GoalPreset(
        key="body_recomposition",
        label="Lose fat and build muscle",
        description="Maintenance calories with very high protein - slower than doing either alone, but works well if you are new to training.",
        calorie_adjustment=0.0,
        protein_g_per_kg=2.2,
        fat_fraction=0.25,
        tags=["recomp", "tone", "toned", "both", "lose fat and", "at the same time", "definition", "abs"],
    ),
    "maintenance": GoalPreset(
        key="maintenance",
        label="Maintain my weight",
        description="Eat at maintenance with a balanced split. A good default if you are happy where you are.",
        calorie_adjustment=0.0,
        protein_g_per_kg=1.6,
        fat_fraction=0.30,
        tags=["maintain", "stay the same", "keep my weight", "where i am", "happy with"],
    ),
    "general_health": GoalPreset(
        key="general_health",
        label="Eat healthier",
        description="Maintenance calories with a balanced, sustainable split. No weight target.",
        calorie_adjustment=0.0,
        protein_g_per_kg=1.4,
        fat_fraction=0.30,
        tags=["eat healthier", "healthier", "wellness", "better diet", "nutrition", "balanced", "feel better"],
    ),
    "athletic_performance": GoalPreset(
        key="athletic_performance",
        label="Perform better in sport",
        description="Slight surplus with carbohydrate prioritised to fuel training and recovery.",
        calorie_adjustment=0.10,
        protein_g_per_kg=1.8,
        fat_fraction=0.22,
        tags=["athlete", "athletic", "sport", "performance", "endurance", "marathon", "race", "5k", "10k", "triathlon", "football", "cricket", "running", "run", "cycling", "swimming", "compete", "season"],
    ),
    "weight_gain": GoalPreset(
        key="weight_gain",
        label="Gain weight",
        description="A clear surplus for putting weight on, with enough protein that some of it is muscle.",
        calorie_adjustment=0.18,
        protein_g_per_kg=1.6,
        fat_fraction=0.30,
        needs_target_weight=True,
        tags=["gain weight", "put on weight", "underweight", "too skinny", "too thin", "heavier"],
    ),
}


@dataclass
class NutritionTargets:
    bmr: float
    tdee: float
    target_calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    goal_key: str
    goal_label: str
    rationale: str
    warnings: List[str] = field(default_factory=list)
    estimated_weeks: Optional[int] = None
    weekly_change_kg: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "bmr": round(self.bmr),
            "tdee": round(self.tdee),
            "target_calories": round(self.target_calories),
            "protein_g": round(self.protein_g),
            "carbs_g": round(self.carbs_g),
            "fat_g": round(self.fat_g),
            "goal_key": self.goal_key,
            "goal_label": self.goal_label,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "estimated_weeks": self.estimated_weeks,
            "weekly_change_kg": (
                round(self.weekly_change_kg, 2) if self.weekly_change_kg is not None else None
            ),
        }


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Mifflin-St Jeor resting energy expenditure, kcal/day."""
    base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age)
    if sex == "male":
        return base + 5.0
    if sex == "female":
        return base - 161.0
    # Unspecified: midpoint of the two constants rather than defaulting to one.
    return base - 78.0


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """Total daily energy expenditure."""
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, ACTIVITY_MULTIPLIERS["moderately_active"])
    return bmr * multiplier


def suggest_preset(text: str) -> Optional[GoalPreset]:
    """
    Map free-text intent onto a preset.

    Users say "I want to slim down" or "get toned", not "body_recomposition".
    Matching on tags lets the UI (or the chatbot) accept natural phrasing
    without another model call.
    """
    if not text:
        return None
    low = text.lower()
    best, best_score = None, 0
    for preset in GOAL_PRESETS.values():
        score = sum(1 for tag in preset.tags if tag in low)
        if preset.label.lower() in low:
            score += 3
        if score > best_score:
            best, best_score = preset, score
    return best


def calculate_targets(
    *,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_level: str,
    goal_key: str,
    target_weight_kg: Optional[float] = None,
    weeks_available: Optional[int] = None,
) -> NutritionTargets:
    """
    Produce calorie and macro targets for a user and goal.

    `target_weight_kg` refines the pace of change where the goal involves one;
    `weeks_available` lets a user's deadline steepen the deficit, subject to the
    same safety caps.
    """
    preset = GOAL_PRESETS.get(goal_key) or GOAL_PRESETS["maintenance"]
    warnings: List[str] = []

    # Guard against nonsense inputs before they propagate into the maths.
    weight_kg = max(30.0, min(300.0, float(weight_kg or 70)))
    height_cm = max(120.0, min(230.0, float(height_cm or 170)))
    age = max(13, min(100, int(age or 25)))
    sex = sex if sex in ("male", "female") else "other"

    bmr = calculate_bmr(weight_kg, height_cm, age, sex)
    tdee = calculate_tdee(bmr, activity_level)

    adjustment = preset.calorie_adjustment

    # If the user gave both a target weight and a deadline, work out the pace
    # they are implicitly asking for and honour it up to the safety cap.
    weekly_change = None
    estimated_weeks = None

    if target_weight_kg and preset.needs_target_weight:
        delta_kg = target_weight_kg - weight_kg
        losing = delta_kg < 0

        max_weekly = weight_kg * (
            MAX_WEEKLY_LOSS_FRACTION if losing else MAX_WEEKLY_GAIN_FRACTION
        )

        if weeks_available and weeks_available > 0:
            requested_weekly = abs(delta_kg) / weeks_available
            if requested_weekly > max_weekly:
                warnings.append(
                    f"Reaching {target_weight_kg:.0f} kg in {weeks_available} weeks would mean "
                    f"{requested_weekly:.2f} kg per week, which is faster than is safe. "
                    f"Targets are set for {max_weekly:.2f} kg per week instead."
                )
                weekly_change = max_weekly
            else:
                weekly_change = requested_weekly
        else:
            # No deadline: use the preset's own pace.
            implied_daily = abs(adjustment) * tdee
            weekly_change = min(max_weekly, (implied_daily * 7) / KCAL_PER_KG)

        daily_delta = (weekly_change * KCAL_PER_KG) / 7.0
        adjustment = (-daily_delta if losing else daily_delta) / tdee

        if weekly_change > 0:
            estimated_weeks = max(1, round(abs(delta_kg) / weekly_change))

    # Clamp the adjustment itself.
    if adjustment < -MAX_DEFICIT_FRACTION:
        adjustment = -MAX_DEFICIT_FRACTION
        warnings.append("Deficit capped at 25% of maintenance to keep it sustainable.")
    if adjustment > MAX_SURPLUS_FRACTION:
        adjustment = MAX_SURPLUS_FRACTION
        warnings.append("Surplus capped at 20% of maintenance - more than this is mostly fat gain.")

    target_calories = tdee * (1.0 + adjustment)

    # Absolute floor.
    floor = CALORIE_FLOOR.get(sex, CALORIE_FLOOR["other"])
    if target_calories < floor:
        warnings.append(
            f"Raised to {floor:.0f} kcal, the lowest intake this app will recommend. "
            "Losing weight more slowly is safer and works better long term."
        )
        target_calories = floor

    # Never prescribe below resting expenditure.
    if target_calories < bmr:
        warnings.append(
            f"Raised to your estimated resting requirement ({bmr:.0f} kcal). Eating below "
            "that for long stretches tends to cost you muscle and energy."
        )
        target_calories = bmr

    # --- macros ---------------------------------------------------------
    #
    # Protein is anchored to bodyweight. When someone has a lot to lose, scaling
    # protein to current weight overshoots, so cap the reference weight at a
    # plausible lean-ish bodyweight for their height (BMI 25).
    reference_weight = weight_kg
    bmi_25_weight = 25.0 * (height_cm / 100.0) ** 2
    if weight_kg > bmi_25_weight * 1.1:
        reference_weight = bmi_25_weight
        warnings.append(
            "Protein target is based on a reference bodyweight rather than current weight, "
            "which is the usual approach when there is a fair amount to lose."
        )

    protein_g = preset.protein_g_per_kg * reference_weight
    protein_kcal = protein_g * 4.0

    fat_fraction = max(MIN_FAT_FRACTION, preset.fat_fraction)
    fat_kcal = target_calories * fat_fraction
    fat_g = fat_kcal / 9.0

    carbs_kcal = target_calories - protein_kcal - fat_kcal

    # On aggressive deficits protein + fat can exceed the budget. Trim fat to
    # its floor first, then protein, so carbohydrate never goes negative.
    if carbs_kcal < 0:
        fat_kcal = target_calories * MIN_FAT_FRACTION
        fat_g = fat_kcal / 9.0
        carbs_kcal = target_calories - protein_kcal - fat_kcal
        if carbs_kcal < 0:
            protein_kcal = target_calories - fat_kcal - (target_calories * 0.10)
            protein_g = max(0.0, protein_kcal / 4.0)
            carbs_kcal = target_calories * 0.10
            warnings.append(
                "Protein target reduced to fit the calorie budget. A smaller deficit would "
                "let you keep protein higher."
            )

    carbs_g = max(0.0, carbs_kcal / 4.0)

    direction = (
        "a deficit" if adjustment < -0.005
        else "a surplus" if adjustment > 0.005
        else "maintenance"
    )
    rationale = (
        f"Your resting requirement is about {bmr:.0f} kcal. With a {activity_level.replace('_', ' ')} "
        f"lifestyle that comes to roughly {tdee:.0f} kcal a day to stay the same weight. "
        f"For {preset.label.lower()} we've set {target_calories:.0f} kcal - {direction}."
    )

    return NutritionTargets(
        bmr=bmr,
        tdee=tdee,
        target_calories=target_calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        goal_key=preset.key,
        goal_label=preset.label,
        rationale=rationale,
        warnings=warnings,
        estimated_weeks=estimated_weeks,
        weekly_change_kg=weekly_change,
    )


def list_presets() -> List[dict]:
    """Preset catalogue for the goal-selection UI."""
    return [
        {
            "key": p.key,
            "label": p.label,
            "description": p.description,
            "needs_target_weight": p.needs_target_weight,
        }
        for p in GOAL_PRESETS.values()
    ]
