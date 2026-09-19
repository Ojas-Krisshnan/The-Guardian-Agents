"""
Authentication and role-based access control for Synapse API and web routes.
Authoritative contract: Contracts.md Sections C.4, D.5, D.9, F.3.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from slice.config import Settings, settings as load_settings

security = HTTPBearer(auto_error=False)


def _get_secret() -> str:
    s = load_settings()
    return s.synapse_jwt_secret or "synapse_dev_secret_key_change_in_prod"


def create_token(user_id: str, role: str, expires_minutes: int = 1440) -> str:
    """Issue a JWT token with user_id and role claims."""
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_secret(), algorithm="HS256")


def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_id: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header(None),
) -> dict[str, str]:
    """Resolve authenticated user from JWT Bearer header, cookie, or test headers."""
    token = None
    if creds and creds.credentials:
        token = creds.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if token:
        try:
            payload = jwt.decode(token, _get_secret(), algorithms=["HS256"])
            return {"user_id": payload.get("sub", ""), "role": payload.get("role", "")}
        except (jwt.PyJWTError, Exception):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
            )

    # Fallback to dev/test headers if present
    if x_user_id and x_user_role:
        return {"user_id": x_user_id, "role": x_user_role}

    # Default anonymous fallback for unrestricted local discovery
    return {"user_id": "anonymous", "role": "student"}


def require_teacher(user: dict[str, str] = Depends(get_current_user)) -> dict[str, str]:
    if user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher role required for this endpoint",
        )
    return user


def require_student(user: dict[str, str] = Depends(get_current_user)) -> dict[str, str]:
    if user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student role required for this endpoint",
        )
    return user
