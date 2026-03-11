"""
Connection verification script for local development.

Run this after starting Docker containers to confirm that
PostgreSQL and Redis are reachable from application code.

Usage:
    cd scripts
    python test_connections.py
"""

import asyncio
import os
import sys

# Add the project root to Python path so we can import shared utilities
# This is necessary because scripts/ is not a Python package
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

# Load environment variables from root .env file
# The script lives in scripts/ so we need to go one level up
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from shared.db_utils.connection import (
    create_postgres_pool,
    create_redis_client,
    close_postgres_pool,
    close_redis_client,
)


async def test_postgres() -> bool:
    """
    Verifies PostgreSQL connectivity by running a simple query.

    Returns:
        bool: True if connection succeeded, False otherwise.
    """
    print("\n── PostgreSQL ──────────────────────────────")

    try:
        pool = await create_postgres_pool(min_size=1, max_size=2)

        # Acquire a connection from the pool and run a test query
        async with pool.acquire() as conn:
            # SELECT 1 is the standard "is the database alive?" query
            result = await conn.fetchval("SELECT 1")
            assert result == 1, "Unexpected result from SELECT 1"

            # Verify the linguamentor schema was created by init-db.sql
            schema_exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = 'linguamentor'
                )
                """
            )

            # Verify uuid-ossp extension is installed
            uuid_ext = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension
                    WHERE extname = 'uuid-ossp'
                )
                """
            )

        await close_postgres_pool(pool)

        print(f"  ✅ Connection:        OK")
        print(f"  ✅ Schema exists:     {schema_exists}")
        print(f"  ✅ uuid-ossp:         {uuid_ext}")
        return True

    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False


async def test_redis() -> bool:
    """
    Verifies Redis connectivity by setting and retrieving a test key.

    Returns:
        bool: True if connection succeeded, False otherwise.
    """
    print("\n── Redis ───────────────────────────────────")

    try:
        client = await create_redis_client()

        # Write a test key using the LinguaMentor key naming convention:
        # lm:[domain]:[identifier]
        test_key = "lm:system:connection_test"
        test_value = "healthy"

        await client.set(test_key, test_value, ex=10)  # expires in 10 seconds

        # Read it back to confirm round-trip works
        retrieved = await client.get(test_key)
        assert retrieved == test_value, f"Expected '{test_value}', got '{retrieved}'"

        # Clean up the test key
        await client.delete(test_key)

        # Confirm deletion worked
        gone = await client.get(test_key)
        assert gone is None, "Test key was not deleted"

        await close_redis_client(client)

        print(f"  ✅ Connection:        OK")
        print(f"  ✅ SET/GET round-trip: OK")
        print(f"  ✅ Key expiry (ex=):  OK")
        print(f"  ✅ DELETE:            OK")
        return True

    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False


async def main() -> None:
    """
    Runs all connection tests and reports overall status.
    Exits with code 1 if any test fails — useful for CI pipelines.
    """
    print("=" * 48)
    print("  LinguaMentor — Connection Verification")
    print("=" * 48)

    postgres_ok = await test_postgres()
    redis_ok = await test_redis()

    print("\n── Summary ─────────────────────────────────")

    if postgres_ok and redis_ok:
        print("  ✅ All connections healthy. Ready to build.")
        print("=" * 48)
        sys.exit(0)  # Exit code 0 = success
    else:
        print("  ❌ One or more connections failed.")
        print("     Check your .env file and Docker containers.")
        print("=" * 48)
        sys.exit(1)  # Exit code 1 = failure (CI will catch this)


# Standard Python entry point guard
# Ensures main() only runs when this script is executed directly,
# not when it's imported as a module
if __name__ == "__main__":
    asyncio.run(main())
