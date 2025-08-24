from typing import Optional
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt
from config import settings
import secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=365*5)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    if length < 4 or length > 10:
        raise ValueError("OTP length must be between 4 and 10 digits")
    return ''.join(secrets.choice("0123456789") for _ in range(length))
