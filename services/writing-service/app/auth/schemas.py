"""
app/auth/schemas.py

Pydantic request/response schemas for all auth endpoints.
FastAPI validates every request against these automatically.
Kept separate from SQLAlchemy models — those are for Alembic,
these are for the HTTP layer.
"""

from datetime import datetime
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
        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login"""
    email: EmailStr
    password: str


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


class MFAVerifyRequest(BaseModel):
    """
    POST /api/v1/auth/mfa/verify

    Submitted after a successful admin login that requires MFA.
    mfa_session_token is the short-lived token issued in the 202 response.
    totp_code is the 6-digit code from the authenticator app.
    """
    mfa_session_token: str
    totp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MFASetupVerifyRequest(BaseModel):
    """
    POST /api/v1/auth/mfa/setup/verify

    Confirms MFA setup by verifying the first TOTP code from the
    authenticator app after scanning the QR code.
    """
    totp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """
    Returned on successful register or login.
    access_token goes in the Authorization header.
    refresh_token is set as HTTP-only cookie — NOT in this body.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int    # seconds until access token expires


class UserResponse(BaseModel):
    """Returned as part of registration or GET /user/me"""
    id: str
    email: str
    display_name: str | None
    role: str
    subscription_tier: str
    email_verified: bool = False


class MFARequiredResponse(BaseModel):
    """
    Returned as 202 Accepted when an admin account has MFA enabled.
    The client must POST the TOTP code to /api/v1/auth/mfa/verify
    with this token to receive the actual JWT.
    """
    mfa_required: bool = True
    # Short-lived Redis-backed token that ties the MFA challenge
    # to the authenticated user without issuing a full JWT yet
    mfa_session_token: str
    expires_in: int = 300    # 5 minutes to enter the TOTP code


class MFASetupResponse(BaseModel):
    """
    Returned when MFA setup is initiated.
    totp_uri is an otpauth:// URI for QR code generation on the frontend.
    """
    totp_uri: str
    secret: str    # shown once for manual entry if QR scan fails


class ActiveSessionResponse(BaseModel):
    """One active session (refresh token) for GET /api/v1/user/sessions"""
    session_id: str
    device_label: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
