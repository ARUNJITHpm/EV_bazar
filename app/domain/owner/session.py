"""Signed owner session cookie. Carries an account id and nothing else."""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "evsite_owner"
_SALT = "evsite-owner-session"


def issue(secret_key: str, account_id: int) -> str:
    return URLSafeTimedSerializer(secret_key, salt=_SALT).dumps({"account": account_id})


def read(secret_key: str, token: str, *, max_age_seconds: int) -> int | None:
    try:
        data = URLSafeTimedSerializer(secret_key, salt=_SALT).loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    account = data.get("account") if isinstance(data, dict) else None
    return account if isinstance(account, int) else None
