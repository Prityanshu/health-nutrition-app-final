from sqlalchemy import (create_engine, Column, Integer, String, Float, Boolean,
                        DateTime, Date, Text, ForeignKey, Enum, UniqueConstraint, Index)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import date, datetime
from typing import Optional
import enum
import os
from dotenv import load_dotenv

load_dotenv()


def age_on(dob: date, today: Optional[date] = None) -> int:
    """
    Completed years between a birth date and today.

    The subtraction has to account for whether the birthday has happened yet
    this year, or everyone is a year too old for up to eleven months. Comparing
    (month, day) tuples does that in one step and, unlike arithmetic on day
    counts, gets 29 February right for free: on 28 February of a non-leap year
    (2, 28) < (2, 29), so a leap-day birthday has correctly not yet occurred.

    Uses the server's date rather than the user's timezone. Age changes once a
    year, so being on the wrong side of midnight for a few hours is a rounding
    error - not worth importing the timezone machinery here and risking a
    circular import for.
    """
    today = today or date.today()
    had_birthday = (today.month, today.day) >= (dob.month, dob.day)
    return today.year - dob.year - (0 if had_birthday else 1)

# Database URL - falls back to SQLite for local development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nutrition_app.db")

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# SQLite needs one connection argument to be usable from FastAPI at all.
#
# Requests are served from a thread pool, and an endpoint that hands its
# Session to a worker thread (see asyncio.to_thread in the routers) touches the
# connection from a different thread than the one that opened it. SQLite's
# default guard rejects that outright. Turning the check off is safe here
# because SQLAlchemy's pool hands any one connection to a single thread at a
# time - the guard is protecting against a situation the pool already prevents.
_CONNECT_ARGS = {"check_same_thread": False} if _IS_SQLITE else {}

engine = create_engine(DATABASE_URL, connect_args=_CONNECT_ARGS)


if _IS_SQLITE:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _tune_sqlite(dbapi_connection, _connection_record):
        """
        Make SQLite behave under concurrent use.

        WAL (write-ahead logging) is the one that matters. In the default
        `delete` journal mode a writer takes a lock over the whole database and
        readers are blocked until it commits - so one person logging a meal
        stalls everyone else's dashboard. Under WAL, readers carry on against
        the last committed state while a write is in progress.

        WAL is a property of the database FILE, not the connection: setting it
        once is permanent, and it adds `-wal` and `-shm` files beside the `.db`
        (both gitignored). It is the right default for a local file database
        and the wrong one only on a network share, which this is not.

        busy_timeout replaces an instant "database is locked" error with a
        wait. Five seconds is far longer than any write here takes, so
        contention becomes a slight delay rather than a failed request.
        """
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            # NORMAL still survives an application crash; only an OS-level
            # crash or power loss can lose the most recent commits, which is
            # the accepted trade for not fsyncing on every single write.
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Enforce the ForeignKey declarations below, which SQLite ignores
            # unless asked. Off by default is a footgun, not a feature.
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Enums
class PrepComplexity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class HealthCondition(str, enum.Enum):
    DIABETES = "diabetes"
    HYPERTENSION = "hypertension"
    HEART_DISEASE = "heart_disease"
    NONE = "none"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    # A birth date beats a stored age, which is wrong within a year of being
    # entered and then keeps drifting - and age feeds the BMR calculation, so
    # it drifts into every calorie target the app produces. `age` is kept for
    # accounts created before this existed; see `current_age` below.
    date_of_birth = Column(Date, nullable=True)
    age = Column(Integer)
    weight = Column(Float)  # in kg
    height = Column(Float)  # in cm
    activity_level = Column(String)  # sedentary, lightly_active, moderately_active, very_active
    health_conditions = Column(Text)  # JSON string of health conditions
    dietary_preferences = Column(Text)  # JSON string of preferences
    cuisine_pref = Column(String, default="mixed")  # Preferred cuisine type
    # Needed by the Mifflin-St Jeor BMR equation, which uses a different
    # constant for men and women (a ~166 kcal/day difference). Nullable so
    # existing accounts keep working; "other" falls back to the midpoint.
    sex = Column(String, nullable=True)  # male, female, other
    # IANA name, e.g. "Asia/Kolkata", sent by the browser. Decides when this
    # user's day starts: without it the app used the UTC day, so in IST the
    # dashboard rolled over at 05:30 and a meal logged at 00:30 counted
    # against yesterday. Nullable so existing accounts keep working - they
    # fall back to APP_TIMEZONE.
    timezone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    @property
    def current_age(self) -> Optional[int]:
        """
        How old this user is TODAY.

        Prefers the birth date, because a stored age is a snapshot: correct on
        the day it was typed and wrong from the next birthday onwards. That
        matters more than it sounds - age is an input to the Mifflin-St Jeor
        BMR equation, so a stale age quietly biases every calorie target the
        app produces, for as long as the account exists.

        Falls back to the stored `age` for accounts created before birth dates
        were collected, so nothing breaks for them and they can add one later.
        Returns None when neither is known, and callers keep their own default
        rather than having one invented here.
        """
        if self.date_of_birth:
            return age_on(self.date_of_birth)
        return self.age

    # Relationships
    meal_plans = relationship("MealPlan", back_populates="user")
    meal_logs = relationship("MealLog", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    achievements = relationship("Achievement", back_populates="user")

class FoodItem(Base):
    __tablename__ = "food_items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    cuisine_type = Column(String, default="mixed")
    calories = Column(Float, nullable=False)
    protein_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    fiber_g = Column(Float, default=0)
    sodium_mg = Column(Float, default=0)
    sugar_g = Column(Float, default=0)
    cost = Column(Float, default=0)
    gi = Column(Float, default=50)  # Glycemic Index
    low_sodium = Column(Boolean, default=True)
    diabetic_friendly = Column(Boolean, default=True)
    hypertension_friendly = Column(Boolean, default=True)
    prep_complexity = Column(Enum(PrepComplexity), default=PrepComplexity.MEDIUM)
    ingredients = Column(Text)
    tags = Column(Text)  # JSON string of tags
    created_at = Column(DateTime, default=datetime.utcnow)
    planned = Column(Boolean, default=False)  # Whether this was a planned meal

class MealPlan(Base):
    __tablename__ = "meal_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plan_date = Column(DateTime, nullable=False)
    meal_type = Column(String, nullable=False)  # breakfast, lunch, dinner, snack
    food_item_id = Column(Integer, ForeignKey("food_items.id"))
    quantity = Column(Float, default=1.0)
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="meal_plans")
    food_item = relationship("FoodItem")

class MealLog(Base):
    __tablename__ = "meal_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    food_item_id = Column(Integer, ForeignKey("food_items.id"))
    meal_type = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat = Column(Float, default=0)
    logged_at = Column(DateTime, default=datetime.utcnow)
    planned = Column(Boolean, default=False)  # Whether this was a planned meal
    
    # Relationships
    user = relationship("User", back_populates="meal_logs")
    food_item = relationship("FoodItem")

class SavedPlan(Base):
    """
    Persisted output from the specialist agents.

    Generated plans previously lived only in React state, so closing the tab -
    or backgrounding the app on a phone, which frequently unloads it - lost the
    plan entirely. That is the opposite of what a workout plan is for: you
    close the app between sets and come back to it.

    Storing them here also means PDF export and sharing can work from the
    server rather than depending on whatever is currently on screen.
    """
    __tablename__ = "saved_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    # workout | budget_meal_plan | regional | weekly_meal_plan | recipe
    plan_type = Column(String, nullable=False, index=True)
    title = Column(String)
    # Markdown for most agents; the weekly planner stores rendered text and
    # keeps its structured form in `params`.
    content = Column(Text, nullable=False)
    # The inputs that produced it, so it can be regenerated or explained.
    params = Column(Text)  # JSON
    # Only one plan per type is "current"; older ones stay as history.
    is_current = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class PasswordResetToken(Base):
    """
    A one-shot ticket to set a new password.

    WHAT IS STORED IS A HASH, NOT THE TOKEN
    ---------------------------------------
    The token itself only ever exists in the email. What lands here is its
    SHA-256, so anyone who reads this table - a stolen backup, a careless log,
    a `SELECT *` in a screenshare - still cannot reset anybody's password. It
    is the same reasoning that makes the passwords themselves unreadable, and
    it would be odd to protect the password and then leave the thing that can
    replace it lying in the clear.

    SHA-256 rather than bcrypt here on purpose: these tokens are 256 bits of
    `secrets` output, so there is no dictionary to attack and nothing for a
    slow hash to buy. Password hashing is slow because human passwords are
    guessable; this is not.

    `used_at` rather than deleting the row: a reset attempt with an
    already-spent token should be able to say "that link has already been
    used", which is a different and more useful message than "invalid link".
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # SHA-256 hex of the token that was emailed.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    # Recorded to make abuse visible in the logs. Not used for any decision -
    # an address proves nothing and blocking on it would lock out anyone
    # behind the same NAT.
    requested_from = Column(String, nullable=True)

    user = relationship("User")

    @property
    def is_spent(self) -> bool:
        return self.used_at is not None

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        return (now or datetime.utcnow()) >= self.expires_at

    def is_usable(self, now: Optional[datetime] = None) -> bool:
        return not self.is_spent and not self.is_expired(now)


class WeightLog(Base):
    """
    Periodic weight check-ins.

    Every calorie target depends on bodyweight, and the figure captured at
    registration goes stale quickly - which silently degrades every calculation
    downstream. Recording weight over time means targets can be recalculated
    against a recent measurement rather than a months-old one, and gives the
    progress view something real to chart.
    """
    __tablename__ = "weight_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    weight_kg = Column(Float, nullable=False)
    logged_at = Column(DateTime, default=datetime.utcnow, index=True)
    note = Column(String, nullable=True)

    user = relationship("User")


class Goal(Base):
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    goal_type = Column(String, nullable=False)  # weight_loss, muscle_gain, maintenance
    target_weight = Column(Float)
    target_calories = Column(Float)
    target_protein = Column(Float)
    target_carbs = Column(Float)
    target_fat = Column(Float)
    start_date = Column(DateTime, default=datetime.utcnow)
    target_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="goals")

class Challenge(Base):
    __tablename__ = "challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    rules = Column(Text)  # JSON string of rules
    reward_points = Column(Integer, default=0)
    active_from = Column(DateTime, default=datetime.utcnow)
    active_to = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    challenge_id = Column(Integer, ForeignKey("challenges.id"))
    points_earned = Column(Integer, default=0)
    completed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="achievements")
    challenge = relationship("Challenge")

class FoodRating(Base):
    __tablename__ = "food_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    food_id = Column(Integer, ForeignKey("food_items.id"))
    rating = Column(Float, nullable=False)  # 1-5 scale
    review = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    food_item = relationship("FoodItem")

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    preference_type = Column(String, nullable=False)  # cuisine, macro, timing, etc.
    preference_data = Column(Text)  # JSON string of preference data
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class Recipe(Base):
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    ingredients = Column(Text)  # JSON string of ingredients
    instructions = Column(Text)  # JSON string of instructions
    nutrition = Column(Text)  # JSON string of nutrition data
    prep_time = Column(Integer, default=30)  # minutes
    cook_time = Column(Integer, default=20)  # minutes
    difficulty = Column(String, default="medium")
    cuisine_type = Column(String, default="mixed")
    health_benefits = Column(Text)  # JSON string of health benefits
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    role = Column(String, nullable=False)  # "user" or "bot"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User")

class ChallengeOutcome(Base):
    """
    What happened to a challenge once it ended.

    WHY THIS EXISTS
    ---------------
    Without it, challenges have no memory. Hit a protein target five days
    running and you would be offered the identical target again - no
    progression, no sense of getting anywhere. Fail the same logging streak
    three weeks in a row and it would keep reappearing unchanged, which reads
    as the app nagging rather than adapting.

    Recording outcomes turns the challenge list into something that responds:
    succeed and the next one asks slightly more, struggle and it asks less,
    and a key that was just attempted moves down the queue so the same thing
    is not served twice in a row.
    """
    __tablename__ = "challenge_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # The generator's stable identifier ("protein_step", "logging_streak"),
    # not the display title - titles contain personalised numbers and change
    # between runs.
    challenge_key = Column(String, nullable=False, index=True)
    challenge_type = Column(String)

    # Difficulty level this attempt was set at. Drives the next target.
    level = Column(Integer, default=0)

    target_value = Column(Float)
    achieved_value = Column(Float)
    completed = Column(Boolean, default=False, index=True)
    points_awarded = Column(Integer, default=0)

    started_at = Column(DateTime)
    ended_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")


class Injury(Base):
    """
    An injury the user is currently managing.

    WHY THIS IS A TABLE AND NOT A PROFILE STRING
    --------------------------------------------
    An injury is not a static fact - it is a thing that changes week to week,
    and almost every useful behaviour depends on knowing *how* it is changing:

      * a workout plan should exclude different movements at week 1 and week 6
      * a recovery challenge only makes sense while it is still healing
      * "how is the hamstring?" needs a previous answer to compare against
      * getting worse is a signal to stop training it and see a physio

    Storing it as free text on the user row loses all of that, and loses it
    silently. The injury also has to outlive the chat window: previously it
    lived only in conversation history and was forgotten after six turns.
    """
    __tablename__ = "injuries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Matches a key in contraindications.INJURIES where possible, so exercise
    # exclusions can be looked up rather than inferred by a language model.
    body_part = Column(String, nullable=False)
    # Exactly what the user said, kept verbatim - "upper hamstring, near the
    # sit bone" carries detail the body_part key cannot.
    description = Column(String)

    # 0 = fully recovered, 10 = severe. Deliberately the user's own rating:
    # it is subjective, and their subjective trend is what matters.
    severity = Column(Integer, default=5)

    status = Column(String, default="active", index=True)   # active | recovered
    started_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Set when the user reports something that needs a professional rather than
    # a modified plan - sharp pain, numbness, swelling, giving way.
    needs_attention = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    checkins = relationship(
        "InjuryCheckIn", back_populates="injury", cascade="all, delete-orphan"
    )


class InjuryCheckIn(Base):
    """
    One reported update on an injury.

    The history is the point. A single severity number says little; three
    check-ins trending 7 -> 5 -> 3 say the plan is working, and 4 -> 6 -> 7
    says it is not and training should back off.
    """
    __tablename__ = "injury_checkins"

    id = Column(Integer, primary_key=True, index=True)
    injury_id = Column(Integer, ForeignKey("injuries.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    severity = Column(Integer, nullable=False)
    # better | same | worse - how the user describes the change themselves,
    # which is not always what the numbers say.
    trend = Column(String)
    note = Column(String)
    logged_at = Column(DateTime, default=datetime.utcnow, index=True)

    injury = relationship("Injury", back_populates="checkins")


class WorkoutLog(Base):
    """
    Did they train today?

    The app has produced workout plans since the beginning and never once asked
    whether any of them happened. That gap meant three things were impossible:
    points for training, an honest "you have trained 4 of the last 7 days", and
    a planner that adapts to what the person actually does rather than what it
    hoped they would do.

    One row per user per local day - a rest day is a row too, because "I chose
    to rest" and "I did not answer" are different facts and only one of them
    should break a streak.
    """
    __tablename__ = "workout_logs"
    __table_args__ = (
        # One answer per day. Tapping "done" twice must not create two rows,
        # or the points ledger has two events to reconcile.
        UniqueConstraint("user_id", "local_date", name="uq_workout_user_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # The USER's calendar day, stored as a date rather than derived from a
    # timestamp. Everything about points is per-day, and re-deriving the day
    # from UTC at read time is what caused the whole rollover problem earlier.
    local_date = Column(Date, nullable=False, index=True)

    # done | rest | skipped
    status = Column(String, nullable=False, default="done")
    # strength | cardio | sport | mobility | other - optional, feeds planning.
    workout_type = Column(String)
    minutes = Column(Integer)
    # 1-10 how hard it felt. Cheap to give, and the single most useful number
    # for deciding whether the next session should progress or hold.
    intensity = Column(Integer)
    note = Column(String)

    logged_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class PointsLedger(Base):
    """
    Every point ever awarded, as an immutable row.

    A single `points` integer on the user row would be faster to read and
    impossible to trust: no way to answer "where did these come from", no way
    to re-run the rules after fixing a bug, and any double-fire silently
    inflates a number nobody can audit. A ledger makes the leaderboard one SUM
    and every total explainable.

    Idempotency is enforced by the database, not by application care: the
    unique constraint on (user, day, reason) means awarding the same thing
    twice is a caught error rather than a quiet duplicate.
    """
    __tablename__ = "points_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", "reason", name="uq_points_user_day_reason"),
        # The leaderboard query: sum points per user over a date range.
        Index("ix_points_user_date", "user_id", "local_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    local_date = Column(Date, nullable=False, index=True)

    # A key from points_engine.REASONS, e.g. "meal_logged", "day_on_target".
    reason = Column(String, nullable=False)
    points = Column(Integer, nullable=False, default=0)
    # Human sentence shown in the breakdown, written when awarded so the
    # explanation cannot drift from the rule that produced it.
    detail = Column(String)

    awarded_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()