import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db, User

load_dotenv()
logger = logging.getLogger(__name__)

# Configuration
#
# SECRET_KEY was previously hardcoded here, which meant anyone with access to
# the source could mint valid tokens for any account. It now comes from the
# environment. In production a missing key is fatal; in development we generate
# an ephemeral one (which invalidates existing tokens on restart - that is
# intentional, it makes the misconfiguration obvious rather than silent).
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SECRET_KEY = os.getenv("SECRET_KEY")

_INSECURE_DEFAULTS = {
    "your-super-secret-key-change-in-production-2024",
    "your-super-secret-key-change-in-production-min-32-chars",
    "changeme",
    "secret",
}

if SECRET_KEY and SECRET_KEY in _INSECURE_DEFAULTS:
    logger.warning("SECRET_KEY is a known placeholder value - treating it as unset.")
    SECRET_KEY = None

if not SECRET_KEY:
    if ENVIRONMENT == "production":
        raise RuntimeError(
            "SECRET_KEY environment variable must be set to a strong random value "
            "in production. Generate one with: python -c \"import secrets; "
            "print(secrets.token_urlsafe(48))\""
        )
    SECRET_KEY = secrets.token_urlsafe(48)
    logger.warning(
        "No SECRET_KEY set - generated a temporary one for this process. "
        "Sessions will not survive a restart. Set SECRET_KEY in your .env file."
    )

if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters long.")

ALGORITHM = "HS256"
# 30 minutes was short enough that a session died mid-conversation: you ask the
# coach something, get distracted, come back, and every request fails. This is a
# personal health tracker, not a bank - a working day is a more sensible default,
# and it can still be tightened per deployment.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, email_or_username: str, password: str) -> Optional[User]:
    """Authenticate a user with email or username and password"""
    # Try to find user by email first, then by username
    user = db.query(User).filter(User.email == email_or_username).first()
    if not user:
        user = db.query(User).filter(User.username == email_or_username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Get the current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get the current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
