import logging
import re
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from app.config.groq_config import get_fast_model, get_reasoning_model
from dotenv import load_dotenv
from textwrap import dedent
import json

load_dotenv()
logger = logging.getLogger(__name__)

class FitMentorService:
    def __init__(self):
        self.fitness_agent = Agent(
            name="FitMentor",
            # Reasoning tier: a 7-day plan has to simultaneously respect
            # sport-specific demands, equipment/time limits, AND every injury
            # exclusion in constraints_block below - the most constraints of
            # any single-shot generation in the app. Safe to fall back to the
            # fast tier under exhaustion specifically BECAUSE injury safety
            # here does not depend on which model drafted the plan: the
            # severity gate above blocks generation outright before any model
            # is called, and plan_repair.py checks and fixes the output
            # afterward regardless of source - the model's job is plan
            # quality within already-enforced bounds, not the safety
            # decision itself.
            model=GroqWithFallback(id=get_reasoning_model(), fallback_id=get_fast_model()),
            description=dedent("""\
                You are FitMentor, a knowledgeable and motivating personal fitness coach. 🏋️‍♂️
                
                Your mission: create personalized weekly workout plans based on a user's
                activity level, fitness goal, age, weight, available time, and any constraints.
                You adapt plans weekly based on user feedback and progress."""),
            instructions=dedent("""\
                FORMATTING: Never use Markdown tables, including for the
                weekly schedule or sets/reps. The app's renderer and PDF
                export only understand headings, bullet points, numbered
                lists and bold text - a table renders as broken pipe-
                delimited text. Use a bulleted or numbered list per day
                instead, with sets/reps as bold inline text.

                Approach each plan creation with these steps:

                1. Input Analysis 📝
                   - Activity level (beginner/intermediate/advanced)
                   - Primary goal (weight loss, muscle gain, endurance, flexibility)
                   - Time available per day
                   - Equipment availability (none/home/gym)
                   - Constraints (injuries, medical conditions)
                   - Age & weight (optional)

                2. Plan Generation 🗓️
                   - Create a **7-day workout plan** with specific activities & durations
                   - Mix cardio, strength, flexibility according to goal
                   - Vary intensity & rest days logically
                   - Suggest warm-ups and cooldowns
                   - Mark activities with emojis:
                     🏃 Cardio | 🏋️ Strength | 🧘 Flexibility | ⏱️ Quick session
                   - Give a "progression tip" for the next week
                   - Allow plan edits after feedback

                3. Presentation
                   - Use markdown formatting
                   - Present workouts in a structured day-by-day format
                   - Add optional tips for nutrition pairing
                   - Add warnings for injuries or medical issues

                4. Feedback Adaptation 🔄
                   - Accept weekly feedback
                   - Adjust volume/intensity/duration accordingly"""),
        )

    async def generate_workout_plan(self, activity_level: str, fitness_goal: str,
                                  time_per_day: int, equipment: str, constraints: list = None,
                                  age: int = None, weight: float = None,
                                  sport: str = None, preferences: str = None) -> dict:
        """
        Generate a personalized workout plan.

        `sport` is what they train FOR, which is not the same as a fitness goal:
        a footballer needs repeat sprint ability, single-leg strength and enough
        left in the legs to actually play, none of which fall out of
        "general_fitness". Without it, every sport request collapsed to a
        bodybuilding split.

        `preferences` is free text for everything the enums cannot hold - "I
        hate burpees", "only mornings", "no gym on Sundays".
        """
        try:
            age_weight_str = ""
            if age and weight:
                age_weight_str = f"Age: {age} years, Weight: {weight} kg"
            elif age:
                age_weight_str = f"Age: {age} years"
            elif weight:
                age_weight_str = f"Weight: {weight} kg"

            sport_block = ""
            if sport:
                sport_block = f"""
            SPORT: I play {sport}. Build this plan around {sport}, not around general gym training:
            - train the qualities {sport} actually demands
            - leave enough in my legs to train and play {sport} itself
            - order the week so hard sessions do not land next to match or practice days
            """

            preference_block = f"\n            PREFERENCES: {preferences}\n" if preferences else ""

            # Constraints go LAST and are stated as hard rules. Models weight
            # the end of a prompt most heavily, and burying injury exclusions
            # in the middle is how hanging leg raises ended up in a plan for a
            # torn hamstring.
            # Above roughly 7/10 a modified plan is the wrong output entirely.
            # Handing someone a "hamstring friendly" week when they have rated
            # it 9/10 dresses up an unsafe answer as a careful one.
            #
            # Parse ONCE, here, and reuse. The severity check used to run its
            # own copy of the severity regex; two parsers for one field is how
            # they drift apart, and this one decides whether we refuse.
            from app.services import injury_taxonomy as taxonomy
            profiles = taxonomy.parse_all(constraints)

            # Above roughly 7/10 a modified plan is the wrong output entirely.
            # Handing someone a "hamstring friendly" week when they have rated
            # it 9/10 dresses up an unsafe answer as a careful one.
            # Deliberately keyed on the stage, NOT on `needs_medical`. That
            # property is also true for red flags, and refusing every plan for
            # anyone who types "sharp pain" is over-restriction, not caution -
            # they can still train everything else. Red flags stay a prominent
            # warning on the result, which is the existing behaviour.
            blocking = [p for p in profiles if not p.stage.prescribe]
            if blocking:
                worst = max(p.severity for p in blocking)
                logger.warning(
                    "Refusing to generate: %s at severity %s.",
                    ", ".join(p.label for p in blocking), worst,
                )
                return {
                    "success": False,
                    "error": (
                        f"You've rated this at {worst} out of 10. That is past the "
                        "point where a training plan is the right answer - it needs "
                        "looking at by a physio or doctor before you load it again. "
                        "Once it settles below that, update the severity and I'll "
                        "build you something."
                    ),
                    "error_type": "needs_assessment",
                    "severity": worst,
                }

            constraints_block = ""
            if constraints:
                joined = "\n            ".join(f"- {c}" for c in constraints)
                # The structured brief is what makes severity mean something at
                # generation time. Without it a 2/10 and a 7/10 hamstring
                # produced identical first drafts and the entire difference was
                # made by deleting things afterwards - safe, but it wasted a
                # generation and left the plan thinner than it needed to be.
                guidance = taxonomy.brief(profiles)
                guidance_block = f"""
            What each injury means for this plan:
            {guidance}
            """ if guidance else ""
                constraints_block = f"""
            HARD CONSTRAINTS - these override everything above:
            {joined}
            {guidance_block}
            Do not include any excluded movement, in any session, including
            warm-ups, cool-downs, stretching and active recovery days. If an
            exercise is excluded, its variations are excluded too. Where you
            drop something, say in one line what you removed and why.

            Do not simply delete the affected area from the week. Train it in
            whatever way the stage above does allow, and train everything
            unaffected at full intensity - an injured ankle is not a reason for
            an easy upper body week.
            """
            else:
                constraints_block = "\n            No injuries or limitations.\n"

            prompt = f"""Create a personalized weekly workout plan for me.

            My details:
            - Activity Level: {activity_level}
            - Fitness Goal: {fitness_goal}
            - Time Available: {time_per_day} minutes per day
            - Equipment: {equipment}
            {age_weight_str}
            {sport_block}{preference_block}{constraints_block}
            Please create a detailed 7-day workout plan with specific exercises, durations, and progression tips."""

            logger.info(f"FitMentor prompt: {prompt}")
            response = self.fitness_agent.run(prompt)
            logger.info(f"FitMentor raw response: {response}")

            # Extract content from RunOutput
            workout_plan = response.content if hasattr(response, 'content') else str(response)

            # Deterministic repair. The prompt states the exclusions as hard
            # rules and the model still breaks them - a plan for a torn
            # hamstring came back with hanging leg raises and jogging warm-ups
            # under a heading reading "hamstring friendly".
            #
            # Previously this only deleted the offending lines, which was safe
            # and frequently useless: six of ten exercises removed left the
            # user with a stub. Now unsafe movements are swapped for ones that
            # do the same job, the plan is assessed, and it is regenerated if
            # what remains is not a workout. Safety still wins every conflict.
            repair_meta = {}
            removed = []
            if constraints:
                try:
                    from app.services import plan_repair

                    def _regenerate(brief: str) -> str:
                        """Ask the model again, told what MOVEMENTS to avoid."""
                        retry = f"{prompt}\n\n{brief}"
                        again = self.fitness_agent.run(retry)
                        return again.content if hasattr(again, "content") else str(again)

                    result = plan_repair.repair(
                        workout_plan,
                        constraints,
                        equipment=equipment,
                        requested_minutes=time_per_day,
                        goal=fitness_goal,
                        sport=sport,
                        level=activity_level,
                        regenerate=_regenerate,
                    )
                    workout_plan = result.plan
                    repair_meta = result.as_dict()
                    removed = list(result.removed)

                    if result.replacements or result.removed:
                        logger.warning(
                            "FitMentor broke the constraints: %d swapped, %d removed, "
                            "%d regeneration(s). Final audit clean: %s",
                            len(result.replacements), len(result.removed),
                            result.regenerations, result.audit_clean,
                        )
                    if not result.audit_clean:
                        # Should be impossible - repair re-audits and strips.
                        # If it ever happens, refuse rather than ship it.
                        logger.error("Plan still unsafe after repair; refusing to return it.")
                        return {
                            "success": False,
                            "error": ("I could not build a plan that works around this "
                                      "safely. Worth speaking to a physio about what "
                                      "you can train right now."),
                            "error_type": "unsafe_after_repair",
                        }
                except Exception as e:
                    logger.error("Plan repair failed: %s", e, exc_info=True)
                    # Fall back to the old behaviour - remove and return -
                    # because an unrepaired plan must never reach the user.
                    try:
                        from app.services.contraindications import strip_excluded
                        workout_plan, findings = strip_excluded(workout_plan, constraints)
                        removed = sorted({f["movement"] for f in findings})
                    except Exception:
                        logger.critical("Safety filtering unavailable; refusing to return a plan.")
                        return {
                            "success": False,
                            "error": "Safety checks are unavailable right now. Try again shortly.",
                            "error_type": "safety_unavailable",
                        }

            return {
                "removed_for_safety": removed,
                "repair": repair_meta,
                "success": True,
                "workout_plan": workout_plan,
                "activity_level": activity_level,
                "fitness_goal": fitness_goal,
                "time_per_day": time_per_day,
                "equipment": equipment,
                "constraints": constraints or [],
                # What the severity actually did, so the user can see the plan
                # was shaped by their rating rather than taking it on trust.
                "injury_stages": [
                    {
                        "label": p.label,
                        "side": p.side,
                        "severity": p.severity,
                        "stage": p.stage.key,
                        "stage_label": p.stage.label,
                        "guidance": p.stage.guidance,
                        "red_flags": p.red_flags,
                    }
                    for p in profiles
                ],
                "age": age,
                "weight": weight
            }
        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg or "Rate limit reached" in error_msg:
                logger.error(f"Groq API rate limit exceeded: {e}")
                return {
                    "success": True,
                    "workout_plan": f"""### Weekly Workout Plan for {activity_level.title()} Fitness 🏋️

#### Day 1: Monday - Upper Body 🏋️
* Warm-up: 5 minutes of jumping jacks 🏃
* Push-ups: 3 sets of 10-15 reps
* Tricep dips (using a chair): 3 sets of 10 reps
* Cool-down: 5 minutes of stretching 🧘
* Duration: 20 minutes

#### Day 2: Tuesday - Lower Body 🏋️
* Warm-up: 5 minutes of jumping jacks 🏃
* Squats: 3 sets of 15 reps
* Lunges: 3 sets of 10 per leg
* Calf raises: 3 sets of 15 reps
* Cool-down: 5 minutes of stretching 🧘
* Duration: 25 minutes

#### Day 3: Wednesday - Cardio 🏃
* Warm-up: 5 minutes of light jogging
* High knees: 3 sets of 30 seconds
* Jumping jacks: 3 sets of 30 seconds
* Burpees: 3 sets of 10 reps
* Cool-down: 5 minutes of walking 🧘
* Duration: 20 minutes

#### Day 4: Thursday - Core 🏋️
* Warm-up: 5 minutes of light cardio
* Plank: 3 sets of 30-60 seconds
* Russian twists: 3 sets of 15 reps
* Bicycle crunches: 3 sets of 15 reps
* Cool-down: 5 minutes of stretching 🧘
* Duration: 20 minutes

#### Day 5: Friday - Full Body 🏋️
* Warm-up: 5 minutes of jumping jacks
* Mountain climbers: 3 sets of 30 seconds
* Push-ups: 3 sets of 10 reps
* Squats: 3 sets of 15 reps
* Cool-down: 5 minutes of stretching 🧘
* Duration: 25 minutes

#### Day 6: Saturday - Flexibility 🧘
* Warm-up: 5 minutes of light cardio
* Leg swings: 3 sets of 10 reps
* Arm circles: 3 sets of 10 reps
* Full body stretches: 15 minutes
* Cool-down: 5 minutes of deep breathing 🧘
* Duration: 30 minutes

#### Day 7: Sunday - Rest Day 🧘
* Take a well-deserved rest day
* Light walking or gentle stretching optional
* Focus on recovery and hydration

### Progression Tips:
- Increase reps by 2-3 each week
- Add 1-2 more sets when comfortable
- Focus on proper form over speed

### Nutrition Tips:
- Stay hydrated (8+ glasses of water)
- Include protein in every meal
- Eat balanced meals with fruits and vegetables

*Note: AI service temporarily unavailable. This is a general {activity_level} workout plan. Try again later for personalized plans.*""",
                    "activity_level": activity_level,
                    "fitness_goal": fitness_goal,
                    "time_per_day": time_per_day,
                    "equipment": equipment,
                    "constraints": constraints,
                    "age": age,
                    "weight": weight
                }
            else:
                logger.error(f"Error generating workout plan with FitMentor: {e}")
                return {"success": False, "error": str(e)}

    async def adapt_workout_plan(self, current_plan: str, feedback: str, 
                               progress_notes: str = None) -> dict:
        """Adapt existing workout plan based on user feedback"""
        try:
            prompt = f"""Based on this feedback, please adapt the workout plan:

            Current Plan:
            {current_plan}

            User Feedback:
            {feedback}

            {f"Progress Notes: {progress_notes}" if progress_notes else ""}

            Please provide an updated workout plan that addresses the feedback while maintaining progress."""

            logger.info(f"FitMentor adaptation prompt: {prompt}")
            response = self.fitness_agent.run(prompt)
            logger.info(f"FitMentor adaptation response: {response}")

            # Extract content from RunOutput
            adapted_plan = response.content if hasattr(response, 'content') else str(response)

            return {
                "success": True,
                "adapted_plan": adapted_plan,
                "feedback": feedback,
                "progress_notes": progress_notes
            }
        except Exception as e:
            logger.error(f"Error adapting workout plan with FitMentor: {e}")
            return {"success": False, "error": str(e)}

fitmentor_service = FitMentorService()
