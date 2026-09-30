"""Phone number + one-time code sign-in for station owners.

The provider sits behind ``OtpProvider`` so a real SMS gateway can be dropped in
without touching the endpoints. No provider name or API key lives in this repo.
``DevStubOtp`` accepts ``000000`` and is only ever handed out outside prod
(``app.api.internal.owner`` refuses sign-in in prod until a real provider is
wired), so the stub cannot open a production account by accident.
"""

from __future__ import annotations

import hmac
import re
from typing import Protocol

DEV_CODE = "000000"


class OtpProvider(Protocol):
    def send(self, phone: str) -> None:
        """Send a code to ``phone`` (E.164, ``+91XXXXXXXXXX``)."""

    def verify(self, phone: str, code: str) -> bool:
        """True when ``code`` is the live code for ``phone``."""


class DevStubOtp:
    """Development stand-in: sends nothing, accepts ``000000``."""

    def send(self, phone: str) -> None:
        return None

    def verify(self, phone: str, code: str) -> bool:
        return hmac.compare_digest(code.strip(), DEV_CODE)


_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def normalise_phone(raw: str) -> str | None:
    """``+91`` and ten digits, or None if this is not an Indian mobile number."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return f"+91{digits}" if _INDIAN_MOBILE.match(digits) else None


def mask_phone(phone: str) -> str:
    """What the browser is shown: the last four digits, the rest hidden."""
    return "+91 " + "•" * 6 + phone[-4:]
