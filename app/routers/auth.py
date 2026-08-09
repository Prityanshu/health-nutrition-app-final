from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db, User
from app.auth import authenticate_user, create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_active_user
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from app.services import daytime

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str
    age: int
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
