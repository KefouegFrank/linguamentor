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
  POST   /api/v1/auth/password/reset   (stub — email not wired yet)
  PATCH  /api/v1/auth/password          (stub — email not wired yet)
  DELETE /api/v1/user/me               (GDPR erasure)
"""

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import JSONResponse

import asyncpg
import redis.asyncio as aioredis

from app.auth import schemas, service
from app.auth.security import (
    blacklist_access_token,
    create_access_token,
    decode_access_token,
    is_token_blacklisted,
)
from app.config import get_settings
from app.dependencies import get_db, get_redis
from app.exceptions import UnauthorizedError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
user_router = APIRouter(prefix="/api/v1/user", tags=["user"])

# Cookie name used throughout — centralised so it never diverges
_REFRESH_COOKIE = "lm_refresh_token"


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

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: schemas.RegisterRequest,
    request: Request,
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> JSONResponse:
    user = await service.register_user(data, conn)

    # Issue tokens immediately on registration — no separate login step
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
            "expires_in": settings.lm_jwt_access_token_expire_minutes * 60,
            "user": schemas.UserResponse(**user).model_dump(),
        },
    )
    _set_refresh_cookie(resp, refresh_token)
    return resp


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive tokens",
)
async def login(
    data: schemas.LoginRequest,
    request: Request,
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
) -> JSONResponse:
    user = await service.authenticate_user(data.email, data.password, conn)

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
            "expires_in": settings.lm_jwt_access_token_expire_minutes * 60,
            "user": schemas.UserResponse(**user).model_dump(),
        },
    )
    _set_refresh_cookie(resp, refresh_token)
    return resp


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Exchange refresh token for new access token",
)
async def refresh(
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    # Cookie is read automatically by FastAPI when declared as a parameter
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
            "expires_in": settings.lm_jwt_access_token_expire_minutes * 60,
        },
    )
    _set_refresh_cookie(resp, new_refresh_token)
    return resp


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Invalidate tokens and clear session",
)
async def logout(
    request: Request,
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    lm_refresh_token: str | None = Cookie(default=None),
) -> JSONResponse:
    # Blacklist the access token if present in the Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:]
        await blacklist_access_token(access_token, redis)

    # Revoke the refresh token if present
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

@router.post(
    "/password/reset",
    status_code=status.HTTP_200_OK,
    summary="Request password reset email",
)
async def request_password_reset(
    data: schemas.PasswordResetRequest,
    conn: asyncpg.Connection = Depends(get_db),
) -> JSONResponse:
    # Always return success — never confirm whether email exists (prevents enumeration)
    # TODO: integrate SendGrid email sending (PRD §38.3) in P3 extension
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "If that email is registered, a reset link has been sent"},
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/user/me  (GDPR erasure, PRD §10.5)
# ---------------------------------------------------------------------------

@user_router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="GDPR erasure — anonymize account and delete personal data",
)
async def gdpr_erase(
    request: Request,
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    lm_refresh_token: str | None = Cookie(default=None),
) -> JSONResponse:
    # Extract user_id from the JWT — the user must be authenticated to erase
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Authentication required")

    token = auth_header[7:]
    if await is_token_blacklisted(token, redis):
        raise UnauthorizedError("Token has been revoked")

    payload = decode_access_token(token)
    user_id = payload["sub"]

    await service.gdpr_erase_user(user_id, conn)

    # Blacklist the access token and clear cookies
    await blacklist_access_token(token, redis)

    resp = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Account data has been anonymized per GDPR request"},
    )
    _clear_refresh_cookie(resp)
    return resp
