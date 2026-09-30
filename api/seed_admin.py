"""
NetGuard AI — Seed the first admin user (api/seed_admin.py)

Run once, manually, from the repo root:
    python -m api.seed_admin

Prompts for a username/password rather than taking them as CLI args, so
credentials never end up in shell history.
"""

import getpass

from sqlalchemy import select

from api.db import SessionLocal, User, init_db
from api.security import hash_password


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        username = input("Admin username: ").strip()
        if not username:
            print("Username cannot be empty.")
            return

        existing = db.scalar(select(User).where(User.username == username))
        if existing is not None:
            print(f"User '{username}' already exists (role={existing.role}).")
            return

        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match.")
            return
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            return

        user = User(username=username, password_hash=hash_password(password), role="admin")
        db.add(user)
        db.commit()
        print(f"Created admin user '{username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()