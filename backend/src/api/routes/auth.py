"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr

from src.services.user_store import user_store
from src.services.auth import create_access_token, get_current_user

router = APIRouter(tags=["Authentication"])


class SignupRequest(BaseModel):
    """Signup request model."""

    username: str
    email: EmailStr
    password: str
    role: str = "user"  # Add this with default


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest):
    """Create a new user account."""
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Validate role
    role = request.role if request.role in ["admin", "user"] else "user"

    user = user_store.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
        role=role,
    )

    if not user:
        raise HTTPException(status_code=400, detail="Email or username already exists")

    token = create_access_token({
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
    })
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login and get access token."""
    user = user_store.authenticate(request.email, request.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({
        "user_id": user["id"],
        "email": user["email"],
        "role": user.get("role", "user"),
    })
    return TokenResponse(access_token=token, user=user)


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return current_user
