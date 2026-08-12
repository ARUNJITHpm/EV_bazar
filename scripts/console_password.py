"""Generate the console password hash and session key - PART C.0.

    uv run python -m scripts.console_password

Prompts (without echoing), prints the two lines to paste into ``.env``, and
never writes them anywhere itself - a script that edits your ``.env`` is a
script that can clobber it.

    echo 'my password' | uv run python -m scripts.console_password --stdin

is available for non-interactive use, at the usual cost of putting the
password in your shell history.
"""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from app.auth import hash_password

#: Below this, a determined guesser with the hash wins. Not a policy for its
#: own sake: this password guards CPO commercial terms.
MIN_LENGTH = 12


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Console password hash (PLAN C.0)")
    parser.add_argument(
        "--stdin", action="store_true", help="read the password from stdin instead of prompting"
    )
    args = parser.parse_args(argv)

    if args.stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Console password: ")
        if password != getpass.getpass("Again: "):
            print("passwords did not match")
            return 1

    if len(password) < MIN_LENGTH:
        print(f"too short: {MIN_LENGTH} characters minimum. This guards CPO commercial terms.")
        return 1

    print()
    print("# Paste into .env - and keep it out of git.")
    print(f"CONSOLE_SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"CONSOLE_PASSWORD_HASH={hash_password(password)}")
    print()
    print("# Rotating CONSOLE_SECRET_KEY invalidates every existing session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
