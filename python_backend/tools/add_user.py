import argparse
import os
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create or update a user in the Pharmaspot backend DB")
    parser.add_argument("--username", required=True, help="Username (unique)")
    parser.add_argument("--password", required=True, help="Plaintext password (will be hashed)")
    parser.add_argument("--fullname", default="", help="Full name")
    parser.add_argument("--id", type=int, default=None, help="Explicit numeric ID (optional)")
    parser.add_argument("--perm-products", action="store_true", help="Grant products permission")
    parser.add_argument("--perm-transactions", action="store_true", help="Grant transactions permission")
    parser.add_argument("--perm-users", action="store_true", help="Grant users/admin permission")
    parser.add_argument("--perm-settings", action="store_true", help="Grant settings permission")

    args = parser.parse_args(argv)

    # Ensure APPNAME is set so DB path matches the running API defaults
    os.environ.setdefault("APPNAME", "pharmaspot")

    # Make the repository root importable when running as a script path
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Late imports to ensure env and sys.path are applied
    from python_backend.app.database import SessionLocal, engine, Base
    from python_backend.app.models import User
    from python_backend.app.security import hash_password

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()

        if user:
            user.fullname = args.fullname or ""
            user.perm_products = bool(args.perm_products)
            user.perm_transactions = bool(args.perm_transactions)
            user.perm_users = bool(args.perm_users)
            user.perm_settings = bool(args.perm_settings)
            if args.password:
                user.password_hash = hash_password(args.password)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Updated user id={user.id} username={user.username}")
        else:
            new_user = User(
                id=args.id if args.id is not None else None,
                username=args.username,
                fullname=args.fullname or "",
                password_hash=hash_password(args.password),
                perm_products=bool(args.perm_products),
                perm_transactions=bool(args.perm_transactions),
                perm_users=bool(args.perm_users),
                perm_settings=bool(args.perm_settings),
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            print(f"Created user id={new_user.id} username={new_user.username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
