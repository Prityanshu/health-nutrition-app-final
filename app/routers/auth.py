import asyncio
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db, User, age_on
from app.auth import authenticate_user, create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_active_user
from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional
from datetime import date, datetime

from app.services import daytime

router = APIRouter()
logger = logging.getLogger(__name__)

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str
    # Birth date is preferred and age is the fallback. Both are optional at the
    # schema level so an older client that still sends `age` keeps working;
    # the validator below requires at least one of them, which a plain
    # `age: int` could not express.
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    weight: float
    height: float
    activity_level: str = "moderately_active"
    # Used by the BMR calculation when setting goals. Optional so existing
    # clients keep working; falls back to a sex-neutral constant.
    sex: Optional[str] = None
    health_conditions: str = "[]"
    dietary_preferences: str = "[]"
    # IANA name from the browser. Decides when this user's day starts, so
    # their dashboard rolls over at their midnight rather than UTC's.
    timezone: Optional[str] = None

    @model_validator(mode="after")
    def _need_an_age_from_somewhere(self):
        """
        One of birth date or age, and whichever is given has to be plausible.

        Age feeds the BMR equation, so a nonsense value here does not fail
        loudly - it produces a calorie target that is merely wrong, which is
        worse. The bounds match those already applied in
        nutrition_targets.calculate_targets.
        """
        if self.date_of_birth is None and self.age is None:
            raise ValueError("Give a date of birth, or an age.")

        if self.date_of_birth is not None:
            if self.date_of_birth > date.today():
                raise ValueError("That date of birth is in the future.")
            years = age_on(self.date_of_birth)
            if not 13 <= years <= 100:
                raise ValueError(
                    f"That date of birth works out as {years}. "
                    "This app is for ages 13 to 100."
                )
            # Keep the legacy column consistent, so anything still reading
            # `age` directly sees the same number as `current_age`.
            self.age = years
        elif not 13 <= self.age <= 100:
            raise ValueError("Age should be between 13 and 100.")

        return self


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    activity_level: Optional[str] = None
    sex: Optional[str] = None
    health_conditions: Optional[str] = None
    dietary_preferences: Optional[str] = None
    cuisine_pref: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user already exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(
            status_code=400,
            detail="Username already taken"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
        date_of_birth=user.date_of_birth,
        # Written from the birth date by the validator when one was given, so
        # the two never disagree at the moment of creation.
        age=user.age,
        weight=user.weight,
        height=user.height,
        activity_level=user.activity_level,
        sex=user.sex,
        health_conditions=user.health_conditions,
        dietary_preferences=user.dietary_preferences,
        timezone=daytime.normalise_timezone(user.timezone),
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and get access token"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user


# ---------------------------------------------------------------------------
# Forgotten passwords
# ---------------------------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# One answer, whatever happened. Returned for an unknown address, a known one,
# a rate-limited one and a failed send alike - see the endpoint for why.
_NEUTRAL_REPLY = {
    "success": True,
    "message": ("If that address has an account, a reset link is on its way. "
                "It expires in 45 minutes."),
}


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Send a reset link, if the address belongs to somebody.

    THIS ENDPOINT ALWAYS ANSWERS THE SAME WAY
    -----------------------------------------
    Success and "no such account" are indistinguishable from the outside, and
    deliberately so. An endpoint that says "no account with that email" is a
    free tool for checking which of a list of addresses has signed up - and on
    an app shared among friends, that is a real privacy leak about who is using
    it. Errors from the mail server are swallowed into the same reply for the
    same reason: a slow failure for a real address and a fast one for a fake
    address is the same leak wearing a different hat.

    Everything that actually went wrong is logged server-side, where it is
    useful and not disclosive.
    """
    from app.services import email_service, password_reset

    address = body.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == address).first()

    if user is None:
        logger.info("Password reset requested for unknown address")
        return _NEUTRAL_REPLY

    if not email_service.EMAIL_ENABLED:
        logger.warning("Password reset requested but SMTP is not configured")
        return _NEUTRAL_REPLY

    # The existing per-user hourly cap. Someone hammering the button cannot
    # turn this into a way to send unlimited mail to an address they do not own.
    allowed, why = email_service.check_rate_limit(user.id)
    if not allowed:
        logger.warning("Password reset rate limited for user %s: %s", user.id, why)
        return _NEUTRAL_REPLY

    token = password_reset.create(
        db, user, requested_from=(request.client.host if request.client else None)
    )

    # Built from the request rather than configured, so the link points at
    # whatever address the user actually reached us on - the tunnel hostname in
    # production, localhost in development. A hardcoded base URL is how reset
    # emails end up sending people to a machine they cannot see.
    base = str(request.base_url).rstrip("/")
    link = f"{base}/?reset_token={token}"
    minutes = int(password_reset.TOKEN_LIFETIME.total_seconds() // 60)

    text, html = password_reset.email_body(
        name=(user.full_name or user.username or "").split(" ")[0],
        link=link,
        minutes=minutes,
    )

    # Off the event loop: smtplib blocks, and this endpoint is async.
    result = await asyncio.to_thread(
        email_service.send_email,
        to_email=user.email,
        subject="Reset your Kayosha password",
        body=text,
        html_body=html,
    )
    if result.success:
        email_service.record_send(user.id)
    else:
        logger.error("Password reset email failed for user %s: %s", user.id, result.message)

    return _NEUTRAL_REPLY


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Set a new password using a token from the email.

    Unlike the request endpoint, this one IS specific about failure - expired,
    already used and not-a-real-token are three different situations, and the
    person holding the link needs to know which. There is no enumeration risk
    here: the token is 256 bits of randomness, so a wrong one tells an attacker
    only that they guessed wrong, which they knew.
    """
    from app.services import password_reset

    ok, message = password_reset.consume(db, body.token, body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.get("/reset-password/check")
async def check_reset_token(token: str, db: Session = Depends(get_db)):
    """
    Is this link still good?

    Called when the reset screen opens, so someone who clicks a stale link is
    told immediately rather than after typing a new password twice.
    """
    from app.services import password_reset

    row, problem = password_reset.look_up(db, token)
    return {"valid": row is not None, "message": problem}


class TimezoneUpdate(BaseModel):
    timezone: str


@router.put("/timezone")
async def set_timezone(
    body: TimezoneUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Record the browser's timezone.

    Its own endpoint rather than a login field because login goes through an
    OAuth2 form, and because this needs to run on every app load, not only at
    sign-in: people travel, and existing accounts predate the column. Writing
    it whenever it changes is what keeps "today" correct without asking.
    """
    resolved = daytime.normalise_timezone(body.timezone)
    if not resolved:
        # Unknown zone: keep whatever we had rather than storing rubbish that
        # would silently shift every day boundary for this user.
        return {
            "success": False,
            "timezone": current_user.timezone,
            "message": f"Unrecognised timezone {body.timezone!r}; keeping the previous setting.",
        }

    changed = current_user.timezone != resolved
    if changed:
        current_user.timezone = resolved
        db.commit()

    start, end = daytime.today_bounds(current_user)
    return {
        "success": True,
        "timezone": resolved,
        "changed": changed,
        "local_date": daytime.local_date(current_user).isoformat(),
        # Lets the client schedule its own refresh exactly on the rollover
        # rather than polling or waiting for the user to reload.
        "seconds_until_midnight": daytime.seconds_until_local_midnight(current_user),
        "day_starts_utc": start.isoformat(),
        "day_ends_utc": end.isoformat(),
    }
