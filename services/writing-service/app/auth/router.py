"""
app/auth/router.py

HTTP layer for all auth endpoints.
Handles cookies, headers, and HTTP status codes.
Delegates all business logic to auth/service.py.

Endpoints (PRD §35.1):
  POST   /api/v1/auth/register
  POST   /api/v1/auth/login
  POST   /api/v1/auth/refresh
  POST   /api/v1/auth/logout
  POST   /api/v1/auth/mfa/verify
  GET    /api/v1/auth/mfa/setup
  POST   /api/v1/auth/mfa/setup/verify
  POST   /api/v1/auth/password/reset   (stub — email not wired yet)
  GET    /api/v1/user/sessions
  DELETE /api/v1/user/sessions/{session_id}
  DELETE /api/v1/user/me  
"""

import secrets
from datetime import timedelta

import asyncpg
import redis.asyncio as aioredis
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.auth import schemas, service
from app.auth.security import (
    blacklist_access_token,
    create_access_token,
    decode_access_token,
    init_jwt_keys,
    is_token_blacklisted,
)
from app.config import get_settings
from app.dependencies import get_db, get_redis, get_current_user, get_redis
from app.exceptions import UnauthorizedError, ValidationError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
user_router = APIRouter(prefix="/api/v1/user", tags=["user"])

# Cookie name used throughout — centralised so it never diverges
_REFRESH_COOKIE = "lm_refresh_token"

# ---------------------------------------------------------------------------
# Rate limiting helpers
# ---------------------------------------------------------------------------
# Login and register endpoints are the primary targets for
# brute force and credential stuffing attacks. We enforce
# per-IP rate limits in Redis independently of the account lockout.
#
# Limits:
#   /login    — 10 attempts per IP per 15 minutes
#   /register — 5 attempts per IP per hour
#
# These complement account lockout — lockout protects a specific account,
# IP rate limiting protects against distributed attacks across many accounts.

_RATE_LIMITS = {
    "login": {"max_attempts": 10, "window_seconds": 900},     # 15 minutes
    "register": {"max_attempts": 5, "window_seconds": 3600},  # 1 hour
}

async def _check_rate_limit(
    endpoint: str,
    client_ip: str,
    redis: aioredis.Redis,
) -> None:
    """
    Enforces per-IP rate limiting using Redis counter with TTL.

    Key: lm:rate:{endpoint}:{ip_hash}
    We hash the IP so raw IP addresses don't appear in Redis keys.

    Raises ValidationError with retry information if limit exceeded.
    """
    import hashlib
    limit = _RATE_LIMITS[endpoint]
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
    key = f"lm:rate:{endpoint}:{ip_hash}"

    # Atomic increment — returns new value after increment
    count = await redis.incr(key)

    if count == 1:
        # First request in this window — set the TTL
        await redis.expire(key, limit["window_seconds"])

    if count > limit["max_attempts"]:
        ttl = await redis.ttl(key)
        raise ValidationError(
            f"Too many attempts. Try again in {ttl} seconds."
        )

def _get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP, accounting for reverse proxy headers.
    X-Forwarded-For is set by the API Gateway when it forwards requests.
    Falls back to direct connection IP if header is absent.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can be a comma-separated list — take the first (original client)
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def _set_refresh_cookie(response: Response, token: str) -> None:
    """
    Sets the refresh token as an HTTP-only Secure SameSite=Strict cookie.
    PRD §37.1: "stored in HttpOnly Secure SameSite=Strict cookie"

    HTTP-only: JavaScript cannot read it — XSS-safe.
    Secure: only sent over HTTPS (browser enforces this in production).
    SameSite=Strict: not sent on cross-site requests — CSRF-safe.
    """
    settings = get_settings()
    max_age = settings.lm_jwt_refresh_token_expire_days * 24 * 60 * 60  # seconds

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.app_env != "development",   # False in dev (no HTTPS locally)
        samesite="strict",
        path="/api/v1/auth",    # cookie only sent to auth endpoints
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clears the refresh token cookie on logout."""
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/api/v1/auth",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: schemas.RegisterRequest,
    request: Request,
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> JSONResponse:
    # Rate limit before any DB work — fail fast on abuse
    await _check_rate_limit("register", _get_client_ip(request), redis)

    user = await service.register_user(data, conn)

    access_token = create_access_token(
        user_id=user["id"],
        role=user["role"],
        subscription_tier=user["subscription_tier"],
    )
    device_label = request.headers.get("User-Agent", "")[:100]
    refresh_token = await service.create_refresh_token_record(
        user_id=user["id"],
        device_label=device_label,
        conn=conn,
    )

    settings = get_settings()
    resp = JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "user": schemas.UserResponse(**user).model_dump(),
        },
    )
    _set_refresh_cookie(resp, refresh_token)
    return resp


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------

@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    data: schemas.LoginRequest,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> JSONResponse:
    await _check_rate_limit("login", _get_client_ip(request), redis)

    user = await service.authenticate_user(data.email, data.password, conn)

    # MFA gate — admin accounts with MFA enabled get a 202 response
    # and must complete TOTP verification before receiving a JWT
    if user.get("mfa_enabled") and user["role"] == "admin":
        mfa_token = secrets.token_urlsafe(32)
        # Store the MFA challenge in Redis for 5 minutes
        # Key maps the short-lived token to the authenticated user_id
        await redis.set(
            f"lm:mfa_challenge:{mfa_token}",
            user["id"],
            ex=300,    # 5 minutes
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=schemas.MFARequiredResponse(
                mfa_session_token=mfa_token
            ).model_dump(),
        )

    # Standard login — issue tokens directly
    access_token = create_access_token(
        user_id=user["id"],
        role=user["role"],
        subscription_tier=user["subscription_tier"],
    )
    device_label = request.headers.get("User-Agent", "")[:100]
    refresh_token = await service.create_refresh_token_record(
        user_id=user["id"],
        device_label=device_label,
        conn=conn,
    )

    settings = get_settings()
    resp = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "user": schemas.UserResponse(**user).model_dump(),
        },
    )
    _set_refresh_cookie(resp, refresh_token)
    return resp

# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/verify
# ---------------------------------------------------------------------------

@router.post("/mfa/verify", status_code=status.HTTP_200_OK)
async def mfa_verify(
    data: schemas.MFAVerifyRequest,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> JSONResponse:
    """
    Completes MFA login for admin accounts.
    Validates the TOTP code and issues the full JWT if correct.
    """
    import pyotp

    # Retrieve and immediately delete the MFA challenge
    # One-time use — prevents replay attacks
    user_id = await redis.getdel(f"lm:mfa_challenge:{data.mfa_session_token}")
    if not user_id:
        raise UnauthorizedError("MFA session expired or invalid — please log in again")

    # Fetch the user's TOTP secret
    row = await conn.fetchrow(
        """
        SELECT id, email, display_name, role, subscription_tier,
               email_verified, mfa_totp_secret
        FROM linguamentor.users
        WHERE id = $1 AND deleted_at IS NULL
        """,
        user_id,
    )
    if not row or not row["mfa_totp_secret"]:
        raise UnauthorizedError("MFA configuration error — please contact support")

    # Verify the TOTP code
    totp = pyotp.TOTP(row["mfa_totp_secret"])
    if not totp.verify(data.totp_code, valid_window=1):
        raise UnauthorizedError("Invalid authentication code")

    # TOTP valid — issue the real JWT
    user = {
        "id": str(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "subscription_tier": row["subscription_tier"],
        "email_verified": row["email_verified"],
    }

    access_token = create_access_token(
        user_id=user["id"],
        role=user["role"],
        subscription_tier=user["subscription_tier"],
    )
    device_label = request.headers.get("User-Agent", "")[:100]
    refresh_token = await service.create_refresh_token_record(
        user_id=user["id"],
        device_label=device_label,
        conn=conn,
    )

    settings = get_settings()
    resp = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "user": schemas.UserResponse(**user).model_dump(),
        },
    )
    _set_refresh_cookie(resp, refresh_token)
    return resp


# ---------------------------------------------------------------------------
# GET /api/v1/auth/mfa/setup
# ---------------------------------------------------------------------------

@router.get("/mfa/setup", status_code=status.HTTP_200_OK)
async def mfa_setup(
    conn: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """
    Initiates MFA setup for the current user.
    Generates a TOTP secret and returns the otpauth:// URI for QR code display.
    The secret is stored tentatively — only activated after verify.
    """
    import pyotp

    secret = pyotp.random_base32()

    # Store the pending secret — not activated until verify step confirms
    # the user has successfully scanned and entered a valid code
    await conn.execute(
        """
        UPDATE linguamentor.users
        SET mfa_totp_secret = $1, updated_at = NOW()
        WHERE id = $2
        """,
        secret,
        user["sub"],
    )

    totp = pyotp.TOTP(secret)
    # otpauth URI is the standard format recognised by all authenticator apps
    # (Google Authenticator, Authy, 1Password, etc.)
    uri = totp.provisioning_uri(
        name=user.get("email", user["sub"]),
        issuer_name="LinguaMentor",
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=schemas.MFASetupResponse(totp_uri=uri, secret=secret).model_dump(),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/setup/verify
# ---------------------------------------------------------------------------

@router.post("/mfa/setup/verify", status_code=status.HTTP_200_OK)
async def mfa_setup_verify(
    data: schemas.MFASetupVerifyRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """
    Confirms MFA setup by verifying the first TOTP code from the
    authenticator app. Enables MFA on the account if valid.
    """
    import pyotp

    row = await conn.fetchrow(
        "SELECT mfa_totp_secret FROM linguamentor.users WHERE id = $1",
        user["sub"],
    )
    if not row or not row["mfa_totp_secret"]:
        raise ValidationError("MFA setup not initiated — call GET /mfa/setup first")

    totp = pyotp.TOTP(row["mfa_totp_secret"])
    if not totp.verify(data.totp_code, valid_window=1):
        raise UnauthorizedError("Invalid code — please try again")

    # Code verified — activate MFA
    await conn.execute(
        """
        UPDATE linguamentor.users
        SET mfa_enabled = TRUE, updated_at = NOW()
        WHERE id = $1
        """,
        user["sub"],
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "MFA enabled successfully"},
    )

@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh(
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    lm_refresh_token: str | None = Cookie(default=None),
) -> JSONResponse:
    if not lm_refresh_token:
        raise UnauthorizedError("No refresh token provided")

    new_refresh_token, user = await service.rotate_refresh_token(
        raw_token=lm_refresh_token,
        conn=conn,
    )

    access_token = create_access_token(
        user_id=user["id"],
        role=user["role"],
        subscription_tier=user["subscription_tier"],
    )

    settings = get_settings()
    resp = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        },
    )
    _set_refresh_cookie(resp, new_refresh_token)
    return resp


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    lm_refresh_token: str | None = Cookie(default=None),
) -> JSONResponse:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        await blacklist_access_token(auth_header[7:], redis)

    if lm_refresh_token:
        await service.revoke_refresh_token(lm_refresh_token, conn)

    resp = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Logged out successfully"},
    )
    _clear_refresh_cookie(resp)
    return resp


# ---------------------------------------------------------------------------
# POST /api/v1/auth/password/reset  (stub — email service not wired yet)
# ---------------------------------------------------------------------------

@router.post("/password/reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    data: schemas.PasswordResetRequest,
    conn: asyncpg.Connection = Depends(get_db),
) -> JSONResponse:
    # Always return success — never confirm whether the email exists
    # TODO: wire SendGrid in Phase 2 email integration
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "If that email is registered, a reset link has been sent"},
    )


# ---------------------------------------------------------------------------
# GET /api/v1/user/sessions
# ---------------------------------------------------------------------------

@user_router.get("/sessions", status_code=status.HTTP_200_OK)
async def list_sessions(
    conn: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Returns all active sessions for the current user."""
    sessions = await service.get_active_sessions(user["sub"], conn)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "sessions": [
                schemas.ActiveSessionResponse(**s).model_dump(mode="json")
                for s in sessions
            ]
        },
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/user/sessions/{session_id}
# ---------------------------------------------------------------------------

@user_router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def revoke_session(
    session_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Revokes a specific session. Users can only revoke their own sessions."""
    revoked = await service.revoke_session(user["sub"], session_id, conn)
    if not revoked:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": True, "message": "Session not found or already revoked"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Session revoked successfully"},
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/user/me  (GDPR erasure)
# ---------------------------------------------------------------------------

@user_router.delete("/me", status_code=status.HTTP_200_OK)
async def gdpr_erase(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    lm_refresh_token: str | None = Cookie(default=None),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    await service.gdpr_erase_user(user["sub"], conn)

    # Blacklist the access token and clear cookies
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        await blacklist_access_token(auth_header[7:], redis)

    resp = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Account data has been anonymized per GDPR request"},
    )
    _clear_refresh_cookie(resp)
    return resp
