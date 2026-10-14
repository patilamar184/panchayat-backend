"""Command line tools. First administrator setup:

    python -m app.cli create-admin --email admin@example.com --full-name "Site Admin"

The password is typed at a hidden prompt (or read from PANCHAYAT_ADMIN_PASSWORD for
non-interactive use). There is intentionally no public endpoint that creates admins.
"""

import argparse
import getpass
import os
import sys

from app.db.session import get_session_factory
from app.core.errors import DomainError
from app.models import UserRole
from app.services import users


def create_admin(args: argparse.Namespace) -> int:
    password = os.environ.get("PANCHAYAT_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Admin password (min 8 characters): ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
    if not 8 <= len(password) <= 128:
        print("Password must be 8 to 128 characters.", file=sys.stderr)
        return 1
    with get_session_factory()() as db:
        try:
            user = users.create_user(
                db,
                email=args.email,
                password=password,
                full_name=args.full_name,
                role=UserRole.admin,
            )
        except DomainError as exc:
            print(exc.detail, file=sys.stderr)
            return 1
    print(f"Administrator created: {user.email} (id {user.id})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="Create an administrator account")
    p.add_argument("--email", required=True)
    p.add_argument("--full-name", required=True)
    p.set_defaults(func=create_admin)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
