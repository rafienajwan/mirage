"""Manage MIRAGE operator accounts: create, list, disable, enable, reset, set-role."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from typing import TextIO

from app.core.passwords import hash_password, validate_password
from app.services.operators import create_operator, normalize_username
from app.storage import store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create an operator")
    create.add_argument("username")
    create.add_argument("--role", choices=["analyst", "admin"], default="analyst")
    reset = sub.add_parser("reset-password", help="set a new password")
    reset.add_argument("username")
    for command in (create, reset):
        command.add_argument(
            "--password-stdin",
            action="store_true",
            help="read the password from stdin instead of prompting",
        )

    sub.add_parser("list", help="list operators")
    for name in ("disable", "enable"):
        sub.add_parser(name, help=f"{name} an operator").add_argument("username")
    role = sub.add_parser("set-role", help="change an operator's role")
    role.add_argument("username")
    role.add_argument("role", choices=["analyst", "admin"])
    return parser


def _read_password(from_stdin: bool, stdin: TextIO) -> str:
    if from_stdin:
        return stdin.readline().rstrip("\r\n")
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        raise ValueError("Passwords do not match")
    return password


async def _run(args: argparse.Namespace, stdin: TextIO) -> None:
    if args.command == "list":
        for record in await store.list_operators():
            state = "disabled" if record.disabled else "enabled"
            print(f"{record.username} {record.role} {state}")
        return
    if args.command == "create":
        await create_operator(
            args.username, _read_password(args.password_stdin, stdin), args.role
        )
        print(f"Created {normalize_username(args.username)}")
        return

    name = normalize_username(args.username)
    if await store.get_operator(name) is None:
        raise ValueError(f"Operator not found: {name}")
    if args.command == "reset-password":
        password = _read_password(args.password_stdin, stdin)
        validate_password(password)
        await store.update_operator(name, password_hash=hash_password(password))
    elif args.command == "set-role":
        await store.update_operator(name, role=args.role)
    else:
        await store.update_operator(name, disabled=args.command == "disable")
    print(f"Updated {name}")


def main(argv: list[str] | None = None, stdin: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        asyncio.run(_run(args, stdin or sys.stdin))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
