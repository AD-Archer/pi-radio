#!/usr/bin/env python3
"""Bootstrap/admin CLI for creating a user account directly, bypassing the
web UI - needed at least once, since there's no admin yet to create the
first one through the app itself.

Usage:
    sudo python3 create_user.py <username> <password> [--role admin|member]
"""
import argparse
import sys

sys.path.insert(0, "/usr/local/bin")
from radio_auth import create_user, init_db  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--role", choices=["admin", "member"], default="admin")
    args = parser.parse_args()

    init_db()
    user_id = create_user(args.username, args.password, role=args.role)
    print(f"Created {args.role} user {args.username!r} (id={user_id})")


if __name__ == "__main__":
    main()
