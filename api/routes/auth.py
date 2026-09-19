"""Authentication router implementation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.auth import DEV_USERS, create_access_token
from api.models import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
    """Authenticate user credentials and return a Bearer JWT token."""
    user = DEV_USERS.get(req.username)
    if user is None or user["password"] != req.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": user["username"], "role": user["role"]})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user["role"],
    )
