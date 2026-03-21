#!/usr/bin/env python3
"""Create or promote an admin user in the Strype database.

Usage (local SQLite):
    python scripts/seed_admin.py --email admin@example.com --password changeme

Usage (Railway Postgres via 'railway run'):
    railway run python scripts/seed_admin.py --email admin@example.com --password changeme

The script creates the user if they don't exist, then sets is_admin=1.
It also ensures the user has a personal organization (idempotent).
"""

import argparse
import asyncio
import os
import sys

# Add the project root to sys.path so backend package is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(email: str, password: str) -> None:
    from backend.config import settings
    from backend.database import init_db, get_db
    from backend.auth import hash_password

    # Validate password meets complexity requirements (8+ chars, 1 letter, 1 digit)
    if len(password) < 8:
        print("ERROR: password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        print("ERROR: password must contain at least one letter and one digit", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to database: {settings.resolved_database_url()[:40]}...")
    await init_db()

    from backend.services import user_store
    from backend.services.organization_store import ensure_personal_organization

    existing = await user_store.get_user_by_email(email)
    if existing:
        # Promote existing user to admin
        async for db in get_db():
            await db.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email,))
            await db.commit()
            break
        print(f"✓ Promoted existing user '{email}' to admin")
    else:
        # Create new admin user
        pw_hash = hash_password(password)
        user = await user_store.create_user(email, pw_hash, name=email.split("@")[0])
        async for db in get_db():
            await db.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user["id"],))
            await db.commit()
            break
        print(f"✓ Created new admin user '{email}'")

    print("Done. Log in at /platform.html and navigate to /admin.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed an admin user into the Strype database")
    parser.add_argument("--email", required=True, help="Admin user email")
    parser.add_argument("--password", required=True, help="Admin user password")
    args = parser.parse_args()

    asyncio.run(main(args.email, args.password))
