"""
app/auth/security.py

Cryptographic operations for the auth system:
  - Password hashing with argon2id (via pwdlib)
  - JWT access token creation and verification (RS256)
  - Refresh token generation and hashing
  - JWT blacklist check via Redis

PRD §37.1 specifies:
  - Access tokens: RS256, 15-minute lifetime
  - Refresh tokens: opaque 256-bit random string, 7-day lifetime
  - Token revocation: Redis blacklist for access tokens,
    DB revocation for refresh tokens
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import get_settings

# ---------------------------------------------------------------------------
# Password hashing — argon2id via pwdlib
# ---------------------------------------------------------------------------
_password_hash = PasswordHash([Argon2Hasher()])


def hash_password(plain_text: str) -> str:
    """Returns an argon2id hash string suitable for storing in the DB."""
    return _password_hash.hash(plain_text)


def verify_password(plain_text: str, hashed: str) -> bool:
    """
    Verifies a password against its stored hash.
    Returns True if they match, False otherwise.
    Never raises — always returns bool.
    """
    try:
        return _password_hash.check(plain_text, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT key cache — loaded once at startup, never re-read from disk
# ---------------------------------------------------------------------------
# Reading PEM files on every request under load is wasteful and adds
# unnecessary disk I/O. We cache the key strings here at module level.
# _init_jwt_keys() is called once from the app lifespan in main.py.
_jwt_private_key: str | None = None
_jwt_public_key: str | None = None


def init_jwt_keys() -> None:
    """
    Loads RS256 key pair from disk into module-level cache.
    Called once during app startup via lifespan in main.py.
    Raises ValueError immediately if keys are missing or unreadable —
    better to fail at boot than to fail on the first auth request.
    """
    global _jwt_private_key, _jwt_public_key
    settings = get_settings()
    # This reads from disk and validates the paths exist
    _jwt_private_key = settings.jwt_private_key
    _jwt_public_key = settings.jwt_public_key


def _get_private_key() -> str:
    """Returns the cached private key, raising if not yet initialised."""
    if _jwt_private_key is None:
        raise RuntimeError("JWT keys not initialised — was init_jwt_keys() called?")
    return _jwt_private_key


def _get_public_key() -> str:
    """Returns the cached public key, raising if not yet initialised."""
    if _jwt_public_key is None:
        raise RuntimeError("JWT keys not initialised — was init_jwt_keys() called?")
    return _jwt_public_key


# ---------------------------------------------------------------------------
# JWT access tokens — RS256
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, role: str, subscription_tier: str) -> str:
    """
    Creates a signed RS256 JWT access token.

    Payload contains exactly what the PRD specifies (§37.1):
    user_id, role, subscription_tier, issued_at, expiry.

    The API Gateway verifies this token before forwarding any request
    to a service — services never verify JWTs themselves.
    This service is the exception: it both creates and verifies tokens
    because it owns the auth domain.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": user_id,
        "role": role,
        "tier": subscription_tier,
        "iat": now,
        "exp": expire,
        "type": "access",    # prevents refresh tokens being used as access tokens
    }

    return jwt.encode(payload, _get_private_key(), algorithm="RS256")


def decode_access_token(token: str) -> dict:
    """
    Verifies and decodes a JWT using the cached RS256 public key.

    Raises jwt.ExpiredSignatureError if expired.
    Raises jwt.InvalidTokenError if signature is invalid or malformed.
    Callers handle these and return 401.
    """
    payload = jwt.decode(token, _get_public_key(), algorithms=["RS256"])

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token type is not 'access'")

    return payload


# ---------------------------------------------------------------------------
# Refresh tokens — opaque random string
# ---------------------------------------------------------------------------

def generate_refresh_token() -> tuple[str, str]:
    """
    Generates a cryptographically random refresh token.

    Returns (raw_token, token_hash).
    raw_token → sent to client in HTTP-only cookie, never stored.
    token_hash → SHA-256 hex stored in DB for lookup.

    Storing only the hash means a compromised DB can't be used
    to replay refresh tokens directly.
    """
    raw_token = secrets.token_urlsafe(32)    # 256-bit random, url-safe base64
    token_hash = _hash_token(raw_token)
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    """Hashes a raw refresh token for DB lookup."""
    return _hash_token(raw_token)


def _hash_token(token: str) -> str:
    """SHA-256 hex digest — 64 chars, matches DB column VARCHAR(64)."""
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# JWT blacklist — Redis
# ---------------------------------------------------------------------------

async def blacklist_access_token(token: str, redis) -> None:
    """
    Adds a JWT to the Redis blacklist on logout.

    Key: lm:jwt_blacklist:{token_hash}
    TTL: token's remaining lifetime — Redis auto-expires it.

    We store the hash, not the raw token — no value leaks into Redis.
    """
    try:
        payload = decode_access_token(token)
        exp = payload.get("exp", 0)
        now = datetime.now(timezone.utc).timestamp()
        ttl_seconds = max(int(exp - now), 1)
        token_hash = _hash_token(token)
        await redis.set(f"lm:jwt_blacklist:{token_hash}", "1", ex=ttl_seconds)
    except Exception:
        # Logout should always succeed from the user's perspective.
        # If we can't blacklist (expired token, Redis down), that's fine —
        # the token will expire naturally anyway.
        pass


async def is_token_blacklisted(token: str, redis) -> bool:
    """
    Returns True if the token has been blacklisted (user logged out).
    Fails open on Redis errors — JWT expiry still provides the safety net.
    """
    try:
        token_hash = _hash_token(token)
        return await redis.exists(f"lm:jwt_blacklist:{token_hash}") > 0
    except Exception:
        return False
