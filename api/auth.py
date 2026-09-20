# api/auth.py
"""Authentication and role-based access control for Synapse Cycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from slice.config import settings

security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12


class User(BaseModel):
    id: str
    role: Literal["student", "teacher"]
    name: str = ""


DEFAULT_SECRET = "dev-secret-change-in-prod-synapse-cycle-32bytes"


def _get_secret() -> str:
    s = settings().synapse_jwt_secret
    if s and len(s) >= 32:
        return s
    return DEFAULT_SECRET


def create_token(user_id: str, role: Literal["student", "teacher"], name: str = "") -> str:
    """Create a signed JWT access token."""
    secret = _get_secret()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "role": role,
        "name": name or user_id,
        "exp": expire,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_token: Optional[str] = Cookie(default=None),
) -> User:
    """Extract and verify user from Bearer header or cookie."""
    token: Optional[str] = None
    if getattr(auth_header, "credentials", None):
        token = auth_header.credentials
    elif auth_token:
        token = auth_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = _get_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub", "")
        role: str = payload.get("role", "")
        name: str = payload.get("name", "")
        if not user_id or role not in ("student", "teacher"):
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return User(id=user_id, role=role, name=name)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Token invalid or expired: {e}")


def require_teacher(user: User = Depends(get_current_user)) -> User:
    """Guard requiring teacher role."""
    if user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher role required")
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    """Guard requiring student role."""
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student role required")
    return user


def ensure_seed_data(db) -> None:
    """Seed a default teacher and sample classroom if table is empty."""
    from synapse.database import create_teacher_user, get_user_by_username, create_classroom, list_teacher_classrooms
    default_teacher = get_user_by_username(db, "teacher_prof")
    if not default_teacher:
        teacher = create_teacher_user(
            db,
            username="teacher_prof",
            password="password123",
            name="Prof. Ada Lovelace",
            email="ada@synapse.edu",
            user_id="teacher_prof",
        )
        # Create default classroom
        create_classroom(
            db,
            teacher_id=teacher["id"],
            name="Data Structures — CSE Q",
            subject="Computer Science",
            description="Core undergraduate data structures & recursion algorithms",
            academic_year="2026-Fall",
        )

