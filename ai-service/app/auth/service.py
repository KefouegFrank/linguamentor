"""
app/auth/service.py

Auth business logic — all database operations for the auth system.

Kept separate from the router so logic is testable in isolation.
The router handles HTTP concerns (cookies, headers, status codes).
This module handles only data and business rules.

All DB queries use raw asyncpg — not SQLAlchemy ORM.
"""

import uuid
from datetime import datetime, timedelta, timezone

import asyncpg

from app.auth.schemas import RegisterRequest
from app.auth.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.config import get_settings
from app.exceptions import NotFoundError, UnauthorizedError, ValidationError

# ---------------------------------------------------------------------------
# Lockout constants
# ---------------------------------------------------------------------------
# 5 failed attempts triggers a 15-minute lockout.
# Balances security against user frustration — exam prep users
# often access the platform under stress and may mistype passwords.
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


async def register_user(
    data: RegisterRequest,
    conn: asyncpg.Connection,
) -> dict:
    """
    Creates a new user account.

    Steps:
    1. Check email not already taken
    2. Hash password with argon2id
    3. Insert user row
    4. Create learner_profile row (one-to-one, always created on register)
    5. Create skill_vector row (initialized to zeros)

    Returns the created user dict.
    Raises ValidationError if email is already registered.
    """
    existing = await conn.fetchval(
        """
        SELECT id FROM linguamentor.users
        WHERE lower(email) = lower($1) AND deleted_at IS NULL
        """,
        data.email,
    )
    if existing:
        raise ValidationError("An account with this email already exists")

    user_id = uuid.uuid4()
    password_hash = hash_password(data.password)

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO linguamentor.users
                (id, email, display_name, password_hash, role, subscription_tier)
            VALUES ($1, $2, $3, $4, 'learner', 'free')
            """,
            user_id,
            data.email.lower(),
            data.display_name,
            password_hash,
        )

        # Learner profile — defaults per PRD §14.1
        await conn.execute(
            """
            INSERT INTO linguamentor.learner_profiles
                (id, user_id, target_language, accent_target, default_persona, track)
            VALUES ($1, $2, 'en', 'en-US', 'companion', 'fluency')
            """,
            uuid.uuid4(),
            user_id,
        )

        # Skill vector — all dimensions start at 0.0 (PRD §23.1)
        await conn.execute(
            """
            INSERT INTO linguamentor.skill_vectors (id, user_id)
            VALUES ($1, $2)
            """,
            uuid.uuid4(),
            user_id,
        )

    return {
        "id": str(user_id),
        "email": data.email.lower(),
        "display_name": data.display_name,
        "role": "learner",
        "subscription_tier": "free",
        "email_verified": False,
    }


async def authenticate_user(
    email: str,
    password: str,
    conn: asyncpg.Connection,
) -> dict:
    """
    Verifies email and password. Returns user dict on success.

    Security properties:
    - Timing-safe: verify_password always runs even if user doesn't exist
    - Account lockout: 5 failed attempts → 15-minute lockout
    - Failed counter resets on successful login
    - Never reveals whether the email exists

    Raises UnauthorizedError on any failure.
    Raises a special lockout error with retry_after when account is locked.
    """
    row = await conn.fetchrow(
        """
        SELECT id, email, display_name, password_hash, role,
               subscription_tier, email_verified, mfa_enabled,
               failed_login_attempts, locked_until
        FROM linguamentor.users
        WHERE lower(email) = lower($1) AND deleted_at IS NULL
        """,
        email,
    )

    # Run verify_password even if row is None — prevents timing attacks
    # that could enumerate registered emails by measuring response time
    stored_hash = row["password_hash"] if row else "$argon2id$v=19$m=65536,t=3,p=4$placeholder$placeholder"
    password_valid = verify_password(password, stored_hash)

    if not row or not password_valid:
        # Increment failure counter if the user exists
        if row:
            await _record_failed_login(str(row["id"]), conn)
        raise UnauthorizedError("Invalid email or password")

    # Check lockout — must happen after password verification to
    # avoid leaking that the account exists via different error messages
    now = datetime.now(timezone.utc)
    if row["locked_until"] and row["locked_until"] > now:
        remaining = int((row["locked_until"] - now).total_seconds())
        raise UnauthorizedError(
            f"Account temporarily locked. Try again in {remaining // 60 + 1} minutes."
        )

    # Successful login — reset failure counter
    await conn.execute(
        """
        UPDATE linguamentor.users
        SET failed_login_attempts = 0,
            locked_until = NULL,
            updated_at = NOW()
        WHERE id = $1
        """,
        row["id"],
    )

    return {
        "id": str(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "subscription_tier": row["subscription_tier"],
        "email_verified": row["email_verified"],
        "mfa_enabled": row["mfa_enabled"],
    }


async def _record_failed_login(user_id: str, conn: asyncpg.Connection) -> None:
    """
    Increments the failed login counter. Locks the account if
    the threshold is reached.

    Called internally — never exposed to callers directly.
    """
    new_attempts = await conn.fetchval(
        """
        UPDATE linguamentor.users
        SET failed_login_attempts = failed_login_attempts + 1,
            updated_at = NOW()
        WHERE id = $1
        RETURNING failed_login_attempts
        """,
        uuid.UUID(user_id),
    )

    # Apply lockout if threshold reached
    if new_attempts >= _MAX_FAILED_ATTEMPTS:
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
        await conn.execute(
            """
            UPDATE linguamentor.users
            SET locked_until = $1, updated_at = NOW()
            WHERE id = $2
            """,
            locked_until,
            uuid.UUID(user_id),
        )


async def create_refresh_token_record(
    user_id: str,
    device_label: str | None,
    conn: asyncpg.Connection,
) -> str:
    """
    Generates a new refresh token and stores its hash in the DB.
    Returns the raw token (to be sent to client in HTTP-only cookie).
    The raw token is never stored — only its SHA-256 hash.
    """
    settings = get_settings()
    raw_token, token_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )

    await conn.execute(
        """
        INSERT INTO linguamentor.refresh_tokens
            (id, user_id, token_hash, device_label, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        uuid.uuid4(),
        uuid.UUID(user_id),
        token_hash,
        device_label,
        expires_at,
    )

    return raw_token


async def rotate_refresh_token(
    raw_token: str,
    conn: asyncpg.Connection,
) -> tuple[str, dict]:
    """
    Implements refresh token rotation (PRD §37.1):
    1. Look up token by hash
    2. Verify not expired or revoked
    3. Revoke it immediately
    4. Issue a new token
    5. Return (new_token, user_dict)

    Theft detection: if a revoked token is presented, revoke ALL
    tokens for the user as a precaution.
    """
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(timezone.utc)

    row = await conn.fetchrow(
        """
        SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked_at, rt.device_label,
               u.email, u.display_name, u.role, u.subscription_tier, u.email_verified
        FROM linguamentor.refresh_tokens rt
        JOIN linguamentor.users u ON u.id = rt.user_id
        WHERE rt.token_hash = $1 AND u.deleted_at IS NULL
        """,
        token_hash,
    )

    if not row:
        raise UnauthorizedError("Invalid refresh token")

    # Theft detection — revoked token reuse = possible replay attack
    if row["revoked_at"] is not None:
        await conn.execute(
            """
            UPDATE linguamentor.refresh_tokens
            SET revoked_at = $1
            WHERE user_id = $2 AND revoked_at IS NULL
            """,
            now,
            row["user_id"],
        )
        raise UnauthorizedError("Refresh token reuse detected — please log in again")

    if row["expires_at"] < now:
        raise UnauthorizedError("Refresh token expired — please log in again")

    user_id = str(row["user_id"])

    async with conn.transaction():
        # Revoke the used token
        await conn.execute(
            """
            UPDATE linguamentor.refresh_tokens
            SET revoked_at = $1, last_used_at = $1
            WHERE id = $2
            """,
            now,
            row["id"],
        )
        new_raw_token = await create_refresh_token_record(
            user_id=user_id,
            device_label=row["device_label"],
            conn=conn,
        )

    return new_raw_token, {
        "id": user_id,
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "subscription_tier": row["subscription_tier"],
        "email_verified": row["email_verified"],
    }


async def revoke_refresh_token(raw_token: str, conn: asyncpg.Connection) -> None:
    """Revokes a specific refresh token on logout."""
    token_hash = hash_refresh_token(raw_token)
    await conn.execute(
        """
        UPDATE linguamentor.refresh_tokens
        SET revoked_at = NOW()
        WHERE token_hash = $1 AND revoked_at IS NULL
        """,
        token_hash,
    )


async def revoke_all_user_tokens(user_id: str, conn: asyncpg.Connection) -> None:
    """Revokes all refresh tokens for a user. Called on password change and GDPR erasure."""
    await conn.execute(
        """
        UPDATE linguamentor.refresh_tokens
        SET revoked_at = NOW()
        WHERE user_id = $1 AND revoked_at IS NULL
        """,
        uuid.UUID(user_id),
    )


async def get_active_sessions(
    user_id: str,
    conn: asyncpg.Connection,
) -> list[dict]:
    """
    Returns all active (non-expired, non-revoked) refresh tokens
    for a user. Used by GET /api/v1/user/sessions.

    Raw token values are never returned — only session metadata.
    """
    rows = await conn.fetch(
        """
        SELECT id, device_label, created_at, last_used_at, expires_at
        FROM linguamentor.refresh_tokens
        WHERE user_id = $1
          AND revoked_at IS NULL
          AND expires_at > NOW()
        ORDER BY created_at DESC
        """,
        uuid.UUID(user_id),
    )
    return [
        {
            "session_id": str(row["id"]),
            "device_label": row["device_label"],
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "expires_at": row["expires_at"],
        }
        for row in rows
    ]


async def revoke_session(
    user_id: str,
    session_id: str,
    conn: asyncpg.Connection,
) -> bool:
    """
    Revokes a specific session by its refresh token ID.
    Verifies ownership — users can only revoke their own sessions.
    Returns True if revoked, False if not found or already revoked.
    """
    result = await conn.execute(
        """
        UPDATE linguamentor.refresh_tokens
        SET revoked_at = NOW()
        WHERE id = $1
          AND user_id = $2
          AND revoked_at IS NULL
        """,
        uuid.UUID(session_id),
        uuid.UUID(user_id),
    )
    # asyncpg returns 'UPDATE N' — N is the number of rows affected
    return result == "UPDATE 1"


async def gdpr_erase_user(user_id: str, conn: asyncpg.Connection) -> None:
    """
    GDPR right-to-erasure (PRD §10.5, DELETE /api/v1/user/me).

    - Anonymizes PII in users table
    - Soft-deletes the user
    - Revokes all refresh tokens
    - Clears user_reference_id from ai_model_runs (audit trail preserved)

    Audio blob deletion handled by background job.
    """
    uid = uuid.UUID(user_id)
    now = datetime.now(timezone.utc)

    async with conn.transaction():
        anonymized_email = f"deleted_{uid.hex[:12]}@anonymized.invalid"
        await conn.execute(
            """
            UPDATE linguamentor.users
            SET email = $1,
                display_name = NULL,
                password_hash = 'DELETED',
                mfa_totp_secret = NULL,
                deleted_at = $2,
                updated_at = $2
            WHERE id = $3
            """,
            anonymized_email,
            now,
            uid,
        )

        await revoke_all_user_tokens(user_id, conn)

        # Anonymize AI audit trail — preserve the record, sever the link
        await conn.execute(
            """
            UPDATE linguamentor.ai_model_runs
            SET user_reference_id = NULL
            WHERE user_reference_id = $1
            """,
            uid,
        )
