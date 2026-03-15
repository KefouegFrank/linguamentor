"""
app/auth/service.py

Auth business logic — all database operations for the auth system.

Kept separate from the router so the logic is testable in isolation.
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
    # Check for duplicate email — case-insensitive
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

    # Insert user — single transaction covers all three inserts
    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO linguamentor.users
                (id, email, display_name, password_hash, role, subscription_tier)
            VALUES ($1, $2, $3, $4, 'learner', 'free')
            """,
            user_id,
            data.email.lower(),    # normalize to lowercase
            data.display_name,
            password_hash,
        )

        # Learner profile — created immediately on registration.
        # Defaults match PRD §14.1: fluency track, companion persona, en-US accent.
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
    }


async def authenticate_user(
    email: str,
    password: str,
    conn: asyncpg.Connection,
) -> dict:
    """
    Verifies email and password, returns the user dict on success.

    Timing-safe: we always run verify_password even if the user
    doesn't exist, to prevent timing attacks that could enumerate
    registered emails.

    Raises UnauthorizedError on any failure — never reveals whether
    the email exists or not.
    """
    row = await conn.fetchrow(
        """
        SELECT id, email, display_name, password_hash, role, subscription_tier
        FROM linguamentor.users
        WHERE lower(email) = lower($1) AND deleted_at IS NULL
        """,
        email,
    )

    # Run verify_password even if row is None — constant time
    stored_hash = row["password_hash"] if row else "$argon2id$v=19$m=65536,t=3,p=4$placeholder"
    password_valid = verify_password(password, stored_hash)

    if not row or not password_valid:
        raise UnauthorizedError("Invalid email or password")

    return {
        "id": str(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "subscription_tier": row["subscription_tier"],
    }


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
        days=settings.lm_jwt_refresh_token_expire_days
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
    1. Look up the presented token by its hash
    2. Verify it's not expired or revoked
    3. Revoke it immediately
    4. Issue a new token
    5. Return the new token and the associated user

    Returns (new_raw_token, user_dict).
    Raises UnauthorizedError if token is invalid, expired, or revoked.

    If a revoked token is presented, it may indicate token theft —
    we revoke ALL tokens for the user as a safety measure.
    """
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(timezone.utc)

    row = await conn.fetchrow(
        """
        SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked_at, rt.device_label,
               u.email, u.display_name, u.role, u.subscription_tier
        FROM linguamentor.refresh_tokens rt
        JOIN linguamentor.users u ON u.id = rt.user_id
        WHERE rt.token_hash = $1 AND u.deleted_at IS NULL
        """,
        token_hash,
    )

    if not row:
        raise UnauthorizedError("Invalid refresh token")

    # Token theft detection — if this token was already revoked,
    # someone might be replaying it. Revoke all tokens for safety.
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
        raise UnauthorizedError("Refresh token has already been used — please log in again")

    if row["expires_at"] < now:
        raise UnauthorizedError("Refresh token has expired — please log in again")

    user_id = str(row["user_id"])

    async with conn.transaction():
        # Revoke the used token immediately — rotation
        await conn.execute(
            """
            UPDATE linguamentor.refresh_tokens
            SET revoked_at = $1, last_used_at = $1
            WHERE id = $2
            """,
            now,
            row["id"],
        )

        # Issue a new token for the same device
        new_raw_token = await create_refresh_token_record(
            user_id=user_id,
            device_label=row["device_label"],
            conn=conn,
        )

    user = {
        "id": user_id,
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "subscription_tier": row["subscription_tier"],
    }

    return new_raw_token, user


async def revoke_refresh_token(
    raw_token: str,
    conn: asyncpg.Connection,
) -> None:
    """
    Revokes a specific refresh token on logout.
    Silent if the token doesn't exist — logout is always 'successful'
    from the user's perspective.
    """
    token_hash = hash_refresh_token(raw_token)
    await conn.execute(
        """
        UPDATE linguamentor.refresh_tokens
        SET revoked_at = NOW()
        WHERE token_hash = $1 AND revoked_at IS NULL
        """,
        token_hash,
    )


async def revoke_all_user_tokens(
    user_id: str,
    conn: asyncpg.Connection,
) -> None:
    """
    Revokes all refresh tokens for a user.
    Called on password change and account deletion.
    """
    await conn.execute(
        """
        UPDATE linguamentor.refresh_tokens
        SET revoked_at = NOW()
        WHERE user_id = $1 AND revoked_at IS NULL
        """,
        uuid.UUID(user_id),
    )


async def gdpr_erase_user(
    user_id: str,
    conn: asyncpg.Connection,
) -> None:
    """
    GDPR right-to-erasure (PRD §10.5, DELETE /api/v1/user/me).

    What we do:
    - Anonymize PII in the users table (email → anonymized, display_name → NULL)
    - Soft-delete the user (set deleted_at)
    - Revoke all refresh tokens
    - ai_model_runs rows keep their data but user_reference_id is cleared
      (they're immutable audit records — PRD §52 says no delete permitted)

    Audio blob deletion is handled by a background job (not implemented here).
    """
    uid = uuid.UUID(user_id)
    now = datetime.now(timezone.utc)

    async with conn.transaction():
        # Anonymize PII — replace email with a non-reversible placeholder
        anonymized_email = f"deleted_{uid.hex[:12]}@anonymized.invalid"
        await conn.execute(
            """
            UPDATE linguamentor.users
            SET email = $1,
                display_name = NULL,
                password_hash = 'DELETED',
                deleted_at = $2,
                updated_at = $2
            WHERE id = $3
            """,
            anonymized_email,
            now,
            uid,
        )

        # Revoke all tokens
        await revoke_all_user_tokens(user_id, conn)

        # Anonymize AIModelRun references — audit trail preserved,
        # personal link severed (PRD §10.5)
        await conn.execute(
            """
            UPDATE linguamentor.ai_model_runs
            SET user_reference_id = NULL
            WHERE user_reference_id = $1
            """,
            uid,
        )
