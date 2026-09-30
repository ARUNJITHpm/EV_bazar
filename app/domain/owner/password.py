"""Owner passwords: the rules, and hashing (scrypt, the same as the console's).

There is no password reset yet. A one-time-code method is planned; until then a
forgotten password cannot be recovered by the owner, and the sign-up screen says
so.
"""

from __future__ import annotations

from app.auth import hash_password, verify_password

MIN_LENGTH = 8
MAX_LENGTH = 128

#: Checked against when the number is unknown, so "no such account" and "wrong
#: password" cost the same time and look the same.
_DUMMY_HASH = hash_password("not-a-real-password")


def problem(password: str) -> str | None:
    """Why this password is not acceptable, or None."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    if password.strip() == "":
        return "A password cannot be only spaces."
    return None


def make_hash(password: str) -> str:
    return hash_password(password)


def check(password: str, stored: str | None) -> bool:
    """True when ``password`` matches ``stored``. A missing hash never matches."""
    if stored is None:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, stored)
