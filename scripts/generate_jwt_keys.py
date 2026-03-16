"""
Generates an RS256 key pair for local development JWT signing.

Usage:
    python scripts/generate_jwt_keys.py

Writes:
    secrets/jwt_private.pem  — kept local, never committed
    secrets/jwt_public.pem   — kept local, never committed

In production, keys are generated once, stored in HashiCorp Vault,
and injected into pods at startup. This script is for local dev only.
"""

from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Resolve secrets/ relative to the monorepo root, not wherever
# this script happens to be run from
_MONOREPO_ROOT = Path(__file__).parent.parent
_SECRETS_DIR = _MONOREPO_ROOT / "secrets"
_SECRETS_DIR.mkdir(exist_ok=True)

private_key_path = _SECRETS_DIR / "jwt_private.pem"
public_key_path = _SECRETS_DIR / "jwt_public.pem"

# Don't overwrite existing keys — would invalidate all active sessions
if private_key_path.exists() or public_key_path.exists():
    print("Keys already exist — not overwriting.")
    print(f"  Private: {private_key_path}")
    print(f"  Public:  {public_key_path}")
    print("Delete them manually if you want to regenerate.")
    exit(0)

print("Generating 2048-bit RSA key pair...")

private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

# Private key — no passphrase for local dev
# In production: stored in Vault, never written to disk
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)

public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

private_key_path.write_bytes(private_pem)
public_key_path.write_bytes(public_pem)

print(f"  ✅ Private key: {private_key_path}")
print(f"  ✅ Public key:  {public_key_path}")
print()
print("These files are gitignored. Never commit them.")
print("Add the paths to your .env files:")
print(f"  LM_JWT_PRIVATE_KEY_PATH=../../secrets/jwt_private.pem")
print(f"  LM_JWT_PUBLIC_KEY_PATH=../../secrets/jwt_public.pem")
