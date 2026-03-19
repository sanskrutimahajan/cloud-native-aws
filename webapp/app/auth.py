"""Authentication - Password hashing and Basic Auth verification"""

import bcrypt
from fastapi import Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.exceptions import APIException
from app import metrics

security = HTTPBasic()


# Hash password using BCrypt
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


# Compare plain password with hashed password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


# Verify Basic Auth credentials and return user
def get_current_user(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    with metrics.Timer("db.auth.user_lookup.duration"):
        user = db.query(User).filter(func.lower(User.username) == credentials.username.lower()).first()

    if not user or not verify_password(credentials.password, user.password):
        raise APIException(
            error_type="Unauthorized",
            message="Authentication credentials are missing or invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic realm=\"Access to course catalog\""}
        )

    return user
