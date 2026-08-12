"""Operator authentication for the console - PART C.0.

One operator, one password, a signed httpOnly session cookie. No SSO, no roles
table, no user table at all until there is a second operator - PLAN C.0 says
so explicitly, and an access-control system with one user in it is mostly a
surface for bugs.

Hashing uses ``hashlib.scrypt`` from the standard library rather than bcrypt or
argon2. Not because it is better - it is a deliberate memory-hard KDF and
entirely adequate here - but because a single-operator console does not earn a
new dependency, and a dependency that never gets updated is its own risk.

Nothing in this module reads settings or touches a database, so it is testable
on its own and the FastAPI layer stays thin.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

#: scrypt cost parameters. n is the memory/CPU knob; 2**14 keeps a single
#: verification around a few tens of milliseconds, which is irrelevant for one
#: login a day and expensive for anyone working through a wordlist.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32

#: What the session cookie is for. Changing this string invalidates every
#: existing session, which is the cheap way to force everyone out.
SESSION_SALT = "evsite-console-session"
COOKIE_NAME = "evsite_console"


class PasswordHashError(ValueError):
    """A stored hash could not be parsed. Treated as a misconfiguration, not
    as a failed login - refusing everyone loudly beats admitting everyone
    quietly."""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Produce a self-describing hash string.

    ``scrypt$n$r$p$salt$hash`` - the parameters travel with the hash so they
    can be raised later without invalidating existing passwords.
    """
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check against a stored hash."""
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            raise PasswordHashError(f"unsupported password hash scheme {scheme!r}")
        expected = _unb64(digest_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except PasswordHashError:
        raise
    except Exception as exc:  # noqa: BLE001 - any malformed hash is the same problem
        raise PasswordHashError(f"could not parse the stored password hash: {exc}") from exc

    return hmac.compare_digest(candidate, expected)


def make_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=SESSION_SALT)


def issue_session(secret_key: str, *, operator: str) -> str:
    """Mint a signed, timestamped session token.

    The token carries no privileges - there is only one operator - so it is
    effectively a signed "yes, someone logged in, at this time". Expiry is
    checked on read, not baked in, so shortening the window logs everyone out
    immediately rather than at their next renewal.
    """
    return make_serializer(secret_key).dumps({"operator": operator})


def read_session(secret_key: str, token: str, *, max_age_seconds: int) -> str | None:
    """Return the operator name, or None if the token is invalid or expired."""
    try:
        data = make_serializer(secret_key).loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    operator = data.get("operator")
    return operator if isinstance(operator, str) else None
