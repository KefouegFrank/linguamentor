"""
app/auth/schemas.py

Pydantic request/response schemas for all auth endpoints.
These define the exact shape of data in and out of the API —
FastAPI validates every request against these automatically.

Kept separate from the SQLAlchemy models in app/models/ —
those are for Alembic, these are for the HTTP layer.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """POST /api/v1/auth/register"""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_not_too_simple(cls, v: str) -> str:
        # Basic strength check — at least one letter and one digit.
        # Not exhaustive, but stops '12345678' type passwords.
        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login"""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """
    POST /api/v1/auth/refresh
    Refresh token arrives in an HTTP-only cookie (PRD §37.1),
    not in the request body. This schema is for documentation only —
    the actual token is extracted from cookies in the router.
    """
    pass


class PasswordResetRequest(BaseModel):
    """POST /api/v1/auth/password/reset"""
    email: EmailStr


class PasswordChangeRequest(BaseModel):
    """PATCH /api/v1/auth/password"""
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_not_too_simple(cls, v: str) -> str:
        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """
    Returned on successful register or login.
    access_token goes in the Authorization header.
    refresh_token is set as an HTTP-only cookie by the router —
    it does NOT appear in this response body (PRD §37.1).
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds until access token expires


class UserResponse(BaseModel):
    """Returned as part of registration or GET /user/me"""
    id: str
    email: str
    display_name: str | None
    role: str
    subscription_tier: str
