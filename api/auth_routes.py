# api/auth_routes.py
"""Authentication endpoints for Teachers and Students."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.auth import User, create_token, get_current_user
from api.dependencies import get_store
from slice.store import Store
from synapse.api_contracts import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    store: Store = Depends(get_store),
) -> AuthResponse:
    """Register a new persistent Teacher or Student account in SQLite.
    
    Passwords are encrypted with PBKDF2-HMAC-SHA256 and never stored in plain text.
    """
    clean_username = req.username.strip().lower()
    if not clean_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is required",
        )

    # 1. Check duplicate username
    existing_user = store.get_user_by_username(clean_username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{req.username}' is already registered",
        )

    # 2. Check duplicate email if provided
    clean_email = req.email.strip().lower() if req.email else ""
    if clean_email:
        existing_email = store.get_user_by_username(clean_email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

    # 3. Create persistent user in SQLite
    user_record = store.create_user(
        role=req.role,
        username=clean_username,
        password=req.password,
        name=req.name.strip(),
        email=clean_email,
    )

    # 4. Generate signed JWT access token
    token = create_token(user_record["id"], user_record["role"], user_record["name"])

    # 5. Return AuthResponse (passwords and hashes are never returned)
    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user_record["id"],
            role=user_record["role"],
            name=user_record["name"],
            username=user_record.get("username"),
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    store: Store = Depends(get_store),
) -> AuthResponse:
    """Authenticate either a student (STU-XXXXXX login ID) or any user (username/email + password)."""
    identifier = req.login_id or req.username or ""
    identifier = identifier.strip()

    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or Student ID is required",
        )

    # 1. Student login via STU- ID
    if identifier.upper().startswith("STU-") or (req.role == "student" and not req.password):
        student_data = store.authenticate_student_id(identifier)
        if not student_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Student ID. Please check the ID provided by your teacher.",
            )
        token = create_token(student_data["id"], "student", student_data["name"])
        return AuthResponse(
            token=token,
            user=UserResponse(
                id=student_data["id"],
                role="student",
                name=student_data["name"],
                login_id=student_data["login_id"],
            ),
        )

    # 2. Check if identifier without STU- prefix is an unconfusable student login ID
    if not req.password:
        student_data = store.authenticate_student_id(f"STU-{identifier.upper()}")
        if student_data:
            token = create_token(student_data["id"], "student", student_data["name"])
            return AuthResponse(
                token=token,
                user=UserResponse(
                    id=student_data["id"],
                    role="student",
                    name=student_data["name"],
                    login_id=student_data["login_id"],
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required for password-protected accounts",
        )

    # 3. Username/email + password login (teachers and registered students)
    user_data = store.authenticate_user(identifier, req.password)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Role is strictly enforced from the database record, not from client request
    actual_role = user_data["role"]
    token = create_token(user_data["id"], actual_role, user_data["name"])
    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user_data["id"],
            role=actual_role,
            name=user_data["name"],
            username=user_data.get("username"),
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> UserResponse:
    """Return the authenticated user profile."""
    user_data = store.get_user_by_id(current_user.id)
    if not user_data:
        return UserResponse(
            id=current_user.id,
            role=current_user.role,
            name=current_user.name or current_user.id,
        )
    return UserResponse(
        id=user_data["id"],
        role=user_data["role"],
        name=user_data["name"],
        username=user_data.get("username"),
    )
