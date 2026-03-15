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
# argon2id is the current gold standard for password hashing.
# It's memory-hard (resistant to GPU cracking) and time-hard.
# pwdlib wraps it with a clean interface and handles the salt automatically.
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
        # Any exception means the hash is malformed or the password is wrong.
        # We treat both identically — no information leak.
        return False


# ---------------------------------------------------------------------------
# JWT access tokens — RS256
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, role: str, subscription_tier: str) -> str:
    """
    Creates a signed RS256 JWT access token.

    Payload contains exactly what the PRD specifies (§37.1):
    user_id, role, subscription_tier, issued_at.

    The API Gateway verifies this token before forwarding any request
    to a service — services never verify JWTs themselves.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.lm_jwt_access_token_expire_minutes)

    payload = {
        "sub": user_id,               # subject — the user's UUID
        "role": role,                 # learner | admin | institution_admin
        "tier": subscription_tier,    # free | pro
        "iat": now,                   # issued at
        "exp": expire,                # expiry
        "type": "access",             # prevents refresh tokens being used as access tokens
    }

    return jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm="RS256",
    )


def decode_access_token(token: str) -> dict:
    """
    Verifies and decodes a JWT access token using the RS256 public key.

    Raises jwt.ExpiredSignatureError if expired.
    Raises jwt.InvalidTokenError if signature is invalid or malformed.
    Callers handle these exceptions and return 401.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_public_key,
        algorithms=["RS256"],
    )

    # Extra check — don't accept refresh tokens presented as access tokens
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token type is not 'access'")

    return payload


# ---------------------------------------------------------------------------
# Refresh tokens — opaque random string
# ---------------------------------------------------------------------------

def generate_refresh_token() -> tuple[str, str]:
    """
    Generates a cryptographically random refresh token.

    Returns a tuple of (raw_token, token_hash).
    - raw_token: sent to the client in an HTTP-only cookie (never stored)
    - token_hash: SHA-256 hex digest stored in the DB for lookup

    We store only the hash so that even if the DB is compromised,
    an attacker can't use the tokens — they'd need the raw values.
    """
    # 256-bit random string — PRD §37.1 "opaque 256-bit random string"
    raw_token = secrets.token_urlsafe(32)   # 32 bytes = 256 bits, url-safe base64
    token_hash = _hash_token(raw_token)
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    """Hashes a raw refresh token for DB lookup."""
    return _hash_token(raw_token)


def _hash_token(token: str) -> str:
    """SHA-256 hex digest — 64 characters, matches DB column VARCHAR(64)."""
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# JWT blacklist — Redis
# ---------------------------------------------------------------------------

async def blacklist_access_token(token: str, redis) -> None:
    """
    Adds a JWT to the Redis blacklist on logout.

    Key: lm:jwt_blacklist:{token_hash}
    TTL: set to the token's remaining lifetime so Redis auto-expires it.

    We store the hash of the token, not the raw token — defense in depth.
    """
    try:
        payload = decode_access_token(token)
        exp = payload.get("exp", 0)
        now = datetime.now(timezone.utc).timestamp()
        ttl_seconds = max(int(exp - now), 1)   # at least 1 second TTL

        token_hash = _hash_token(token)
        key = f"lm:jwt_blacklist:{token_hash}"
        await redis.set(key, "1", ex=ttl_seconds)
    except Exception:
        # If we can't blacklist (token already expired, Redis down, etc.),
        # we don't raise — logout should always succeed from the user's perspective.
        pass


async def is_token_blacklisted(token: str, redis) -> bool:
    """
    Checks if a JWT has been blacklisted (logged out).
    Returns True if blacklisted, False if valid.
    """
    try:
        token_hash = _hash_token(token)
        key = f"lm:jwt_blacklist:{token_hash}"
        return await redis.exists(key) > 0
    except Exception:
        # If Redis is down, fail open — don't block all requests.
        # The token's expiry is still enforced by JWT verification.
        return False
