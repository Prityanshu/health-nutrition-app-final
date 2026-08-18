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

                PRIORITY ORDER when anything conflicts: hard constraints
                (injuries/restrictions, stated as non-negotiable below) beat
                everything. The stated PRIMARY GOAL leads the actual training
                design. A named sport's core physical qualities are a FLOOR
                that has to survive whatever the goal is - never a reason to
                override the goal, and never something the goal is allowed to
                erase entirely. Do not invent a constraint, injury or sport
                demand that was not stated.

                This app works with ANY sport, activity or goal - general gym
                training, a specific sport, endurance, rehab return-to-training,
                or no sport at all. Reason from the physical demands actually
                stated or implied, not from assumptions about one sport in
                particular.

                1. Input Analysis 📝
                   - Activity level (beginner/intermediate/advanced) - this
                     changes movement complexity and volume, not just how much
                     encouragement to add. A beginner should not see Olympic
                     lifts, plyometric volume, contrast sets, or training to
                     failure - not because they are told to avoid it, but
                     because you never reach for it at that level.
                   - Primary goal, sport (if any), time available, equipment,
                     age/weight, constraints, and anything in preferences
                     about schedule, match/practice days, or disliked exercises.

                2. Plan Generation 🗓️
                   - A full week, but "7 days" does not mean 7 hard sessions -
                     read any stated training frequency or schedule constraint
                     and place genuine rest/recovery days accordingly.
                   - THE TIME HAS TO BE REAL. A session stated at N minutes
                     has to actually fit in N minutes once warm-up, working
                     sets, realistic rest between sets, transitions between
                     exercises and cool-down are all counted - not just the
                     exercise list. For short sessions, cut accessory volume
                     and use supersets for movements that are safe to pair,
                     not for technically demanding or high-risk compound lifts
                     (heavy squats, deadlifts, olympic-style lifts) - those
                     keep their full rest even if it costs total exercise count.
                   - Within a session, order work: warm-up -> technical/
                     high-skill or power work -> main strength work ->
                     hypertrophy/accessory work -> conditioning -> core ->
                     cooldown. Depart from this when the session's own goal
                     calls for it - an endurance-focused session should not be
                     forced into a bodybuilding order.
                   - Never prescribe equipment that was stated as unavailable.
                   - Sequence the WEEK, not just each day: avoid stacking
                     multiple hard lower-body or high-fatigue sessions back to
                     back, and if a match/practice day was mentioned, do not
                     put a heavy lower-body session immediately before or
                     after it.
                   - Give each exercise a progression mechanism that fits what
                     it actually is and what the goal is - load for strength
                     work, reps or density for hypertrophy/endurance work,
                     distance or pace for running, RPE/RIR for autoregulated
                     work. "Add 5kg every week" is not a plan for a bodyweight
                     exercise or a sprint. State it in terms a person can
                     actually follow next week (a number, a unit, a rule) -
                     not "increase when it feels easy".
                   - Mark activities with emojis:
                     🏃 Cardio | 🏋️ Strength | 🧘 Flexibility | ⏱️ Quick session

                3. Presentation
                   - Use markdown formatting (headings/bullets/bold, never tables)
                   - Present workouts in a structured day-by-day format
                   - Where you modify something for a stated constraint or
                     schedule reason, say what and why in one line - do not
                     silently change the request
                   - Add optional tips for nutrition pairing
                   - Add warnings for injuries or medical issues

                4. Feedback Adaptation 🔄
                   - Accept weekly feedback
                   - If feedback describes high fatigue, poor recovery, or
                     persistent soreness, reduce volume/intensity rather than
                     holding or increasing it - a lighter week is a valid and
                     often correct response, not a failure to progress
                   - Otherwise adjust volume/intensity/duration accordingly"""),
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
                # Data-driven rather than trusting the model's own read of the
                # sport: plan_quality.sport_qualities() is the same lookup the
                # quality check re-verifies the finished plan against, so
                # naming the qualities here up front means the generation and
                # the check are working from one definition, not two that can
                # drift apart. Returns None for a sport it does not recognise
                # - the prompt still works, it just leans on the model's own
                # knowledge for that case rather than asserting nothing.
                from app.services import plan_quality
                known_qualities = plan_quality.sport_qualities(sport)
                quality_line = (
                    f"            Specifically, {sport} performance depends on: "
                    + ", ".join(sorted(q.replace('_', ' ') for q in known_qualities)) + ".\n"
                    if known_qualities else ""
                )
                sport_block = f"""
            SPORT: I play {sport}. Build this plan around {sport}, not around general gym training:
            - train the qualities {sport} actually demands
{quality_line}            - my PRIMARY GOAL below still leads the session - do not turn this into
              a generic {sport} conditioning block if I asked for something else -
              but never let pursuing that goal cost me the ability to train and
              play {sport} itself
            - order the week so hard lower-body or high-fatigue sessions do not
              land immediately before or after a match or practice day, if I have
              mentioned one below
            """

            # Sport + a resistance goal is the combination that reliably comes
            # back gutted: practices and matches get treated as if they
            # REPLACED the gym work, and the week returns as two light
            # sessions and five rest days. Sport is training load, but it is
            # not the stimulus a muscle-gain or strength goal asked for, and
            # the answer is to schedule around the fixed commitments rather
            # than delete the sessions. plan_quality re-checks the resistance
            # volume deterministically afterwards, so this block is here to
            # make the first attempt right - it is not what enforces it.
            if (fitness_goal or "").lower() in ("muscle_gain", "strength"):
                sport_block += f"""
            RESISTANCE VOLUME IS THE POINT OF MY GOAL - do not trade it away:
            - {sport} practices and matches are training LOAD, but they do not
              replace resistance training. Do not convert a practice or match
              day into a reason to drop a gym session.
            - Keep the weekly resistance volume appropriate to my stated level.
              Work the gym sessions AROUND my fixed {sport} commitments; do not
              remove them to make room.
            - Manage fatigue by distributing volume and intensity, not by adding
              rest days I did not ask for. Near a match, prefer an upper-body or
              lower-stress session over deleting the session entirely.
            - Do keep genuinely high-fatigue lower-body work away from the day
              before an important match.
            """

            preference_block = (
                f"\n            PREFERENCES: {preferences}\n"
                "            If this mentions match days, practice days, work/school "
                "commitments, or how many days a week I can actually train, treat that "
                "as a real scheduling constraint - place rest and lighter days accordingly "
                "rather than defaulting to hard training on all seven.\n"
                if preferences else ""
            )

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

            # Deterministic repair AND quality-checking, always - not only when
            # there are injury constraints.
            #
            # The safety half: the prompt states exclusions as hard rules and
            # the model still breaks them - a plan for a torn hamstring came
            # back with hanging leg raises and jogging warm-ups under a
            # heading reading "hamstring friendly". Unsafe movements are
            # swapped for ones that do the same job, not just deleted, and
            # regenerated if what remains is not a workout. Safety wins every
            # conflict.
            #
            # The quality half applies to EVERY plan, injury or not: is the
            # session realistic for the requested time, does it actually
            # train the stated goal and the sport's real demands, does it stay
            # inside the stated equipment, is progression something a person
            # could actually follow. `plan_repair.repair()` used to skip all
            # of this for anyone without a constraint - see its own comment -
            # which meant most users never got it.
            repair_meta = {}
            removed = []
            try:
                from app.services import plan_repair

                def _regenerate(brief: str) -> str:
                    """Ask the model again, told what to fix."""
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
                if constraints and not result.audit_clean:
                    # Should be impossible - repair re-audits and strips.
                    # If it ever happens, refuse rather than ship it. Only
                    # meaningful when there was something to violate.
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
                if constraints:
                    # An unrepaired plan must never reach the user when there
                    # is something in it to violate - fall back to the old
                    # strip-only behaviour rather than ship it unfiltered.
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
                # else: nothing unsafe was possible, only the quality pass
                # failed to run - the original plan is still fine to return.

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
                fallback_plan = f"""### Weekly Workout Plan for {activity_level.title()} Fitness 🏋️

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

*Note: AI service temporarily unavailable. This is a general {activity_level} workout plan. Try again later for personalized plans.*"""

                # This text is generic and hand-written - it has never been
                # checked against THIS user's injuries, unlike a real
                # generation which always goes through plan_repair below.
                # Route it through the same deterministic audit/repair before
                # it can reach anyone with an active constraint. No
                # `regenerate` callback: we are already here because the
                # model is rate-limited, so asking it for another attempt
                # would fail the same way and spend a call for nothing - the
                # audit/replace/remove pass itself is fully local and free.
                removed = []
                if constraints:
                    try:
                        from app.services import plan_repair
                        result = plan_repair.repair(
                            fallback_plan, constraints, equipment=equipment,
                            requested_minutes=time_per_day, goal=fitness_goal,
                            sport=sport, level=activity_level,
                        )
                        if not result.audit_clean:
                            logger.error(
                                "Fallback plan still unsafe after repair; refusing.")
                            return {
                                "success": False,
                                "error": (
                                    "AI service is temporarily unavailable, and I could not "
                                    "build a safe fallback plan around your injury. Please "
                                    "try again in a few minutes."
                                ),
                                "error_type": "rate_limit",
                            }
                        fallback_plan = result.plan
                        removed = list(result.removed)
                    except Exception as repair_error:
                        logger.critical(
                            "Safety filtering unavailable for fallback plan: %s",
                            repair_error, exc_info=True,
                        )
                        return {
                            "success": False,
                            "error": ("AI service is temporarily unavailable and safety "
                                      "checks could not run. Please try again shortly."),
                            "error_type": "safety_unavailable",
                        }

                return {
                    "success": True,
                    "workout_plan": fallback_plan,
                    "removed_for_safety": removed,
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
                               progress_notes: str = None,
                               constraints: list = None,
                               equipment: str = "gym",
                               time_per_day: int = None,
                               fitness_goal: str = None,
                               sport: str = None,
                               activity_level: str = None) -> dict:
        """
        Adapt existing workout plan based on user feedback.

        `constraints` are the same free-text injury strings generate_workout_plan
        takes ("hamstring strain (severity 6/10)"), so an adaptation for someone
        with an active injury gets the identical deterministic audit/repair a
        fresh generation does - a model asked to "adjust" a plan can just as
        easily re-introduce or fail to remove a prohibited movement as one
        asked to create a plan from scratch, and there is no reason to trust
        it less/more in either direction. Optional and defaulted so existing
        callers that do not pass an injury are unaffected.
        """
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

            # Same deterministic pipeline generate_workout_plan uses - see
            # that method's own comment for why safety must not depend on
            # which code path produced the draft.
            repair_meta = {}
            removed = []
            if constraints:
                try:
                    from app.services import plan_repair

                    def _regenerate(brief: str) -> str:
                        retry = f"{prompt}\n\n{brief}"
                        again = self.fitness_agent.run(retry)
                        return again.content if hasattr(again, "content") else str(again)

                    result = plan_repair.repair(
                        adapted_plan, constraints, equipment=equipment,
                        requested_minutes=time_per_day, goal=fitness_goal,
                        sport=sport, level=activity_level,
                        regenerate=_regenerate,
                    )
                    adapted_plan = result.plan
                    repair_meta = result.as_dict()
                    removed = list(result.removed)

                    if not result.audit_clean:
                        logger.error("Adapted plan still unsafe after repair; refusing.")
                        return {
                            "success": False,
                            "error": ("I could not adapt this plan while keeping it safe "
                                      "for your injury. Worth speaking to a physio about "
                                      "what you can train right now."),
                            "error_type": "unsafe_after_repair",
                        }
                except Exception as e:
                    logger.error("Adapted-plan repair failed: %s", e, exc_info=True)
                    try:
                        from app.services.contraindications import strip_excluded
                        adapted_plan, findings = strip_excluded(adapted_plan, constraints)
                        removed = sorted({f["movement"] for f in findings})
                    except Exception:
                        logger.critical(
                            "Safety filtering unavailable; refusing to return an adapted plan.")
                        return {
                            "success": False,
                            "error": "Safety checks are unavailable right now. Try again shortly.",
                            "error_type": "safety_unavailable",
                        }

            return {
                "success": True,
                "adapted_plan": adapted_plan,
                "feedback": feedback,
                "progress_notes": progress_notes,
                "removed_for_safety": removed,
                "repair": repair_meta,
            }
        except Exception as e:
            logger.error(f"Error adapting workout plan with FitMentor: {e}")
            return {"success": False, "error": str(e)}

fitmentor_service = FitMentorService()
