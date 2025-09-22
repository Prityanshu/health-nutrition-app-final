import logging
from agno.agent import Agent
from app.models.groq_with_fallback import GroqWithFallback
from agno.tools.exa import ExaTools
from dotenv import load_dotenv
from textwrap import dedent
import json

load_dotenv()
logger = logging.getLogger(__name__)

class FitMentorService:
    def __init__(self):
        self.fitness_agent = Agent(
            name="FitMentor",
            tools=[ExaTools()],
            model=GroqWithFallback(id="llama-3.3-70b-versatile"),
            description=dedent("""\
                You are FitMentor, a knowledgeable and motivating personal fitness coach. 🏋️‍♂️
                
                Your mission: create personalized weekly workout plans based on a user's
                activity level, fitness goal, age, weight, available time, and any constraints.
                You adapt plans weekly based on user feedback and progress."""),
            instructions=dedent("""\
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
                                  age: int = None, weight: float = None) -> dict:
        """Generate personalized workout plan using FitMentor agent"""
        try:
            # Build the prompt for the agent
            constraints_str = f"Constraints: {', '.join(constraints)}" if constraints else "No specific constraints"
            age_weight_str = ""
            if age and weight:
                age_weight_str = f"Age: {age} years, Weight: {weight} kg"
            elif age:
                age_weight_str = f"Age: {age} years"
            elif weight:
                age_weight_str = f"Weight: {weight} kg"
            
            prompt = f"""Create a personalized weekly workout plan for me.

            My details:
            - Activity Level: {activity_level}
            - Fitness Goal: {fitness_goal}
            - Time Available: {time_per_day} minutes per day
            - Equipment: {equipment}
            {age_weight_str}
            {constraints_str}

            Please create a detailed 7-day workout plan with specific exercises, durations, and progression tips."""

            logger.info(f"FitMentor prompt: {prompt}")
            response = self.fitness_agent.run(prompt)
            logger.info(f"FitMentor raw response: {response}")

            # Extract content from RunOutput
            workout_plan = response.content if hasattr(response, 'content') else str(response)

            return {
                "success": True,
                "workout_plan": workout_plan,
                "activity_level": activity_level,
                "fitness_goal": fitness_goal,
                "time_per_day": time_per_day,
                "equipment": equipment,
                "constraints": constraints or [],
                "age": age,
                "weight": weight
            }
        except Exception as e:
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
