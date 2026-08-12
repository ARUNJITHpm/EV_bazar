"""L0 of the geocoding cascade - address normalisation. PURE. PART 1.3.

The cascade is ``normalise -> cache -> nominatim -> ola -> mappls -> google ->
manual``. This is the first step, and it earns its place by doing two cheap
things that make every later step better:

  * It **extracts the 6-digit PIN** before anything strips digits, so the PIN
    survives to cross-check the district later (PLAN 1.4) even when the rest of
    the address is a mess.
  * It **canonicalises spelling** so "Trivandrum", "trivandrum," and
    "Thiruvananthapuram" collapse to one cache key. A geocode is the most
    expensive step in the cascade; the cache only saves money if trivially
    different spellings of the same place hit the same row.

No database, no network, no clock - exactly like ``crosswalk.py``, and for the
same reason: the subtle mistakes are in *what we decide the address says*, and
those are tested exhaustively without standing anything up.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Indian PIN: six digits, first is the region 1-9 (never 0). Anchored so it is
#: not plucked out of the middle of a 10-digit phone number - a real failure on
#: Indian addresses, which routinely carry both.
_PINCODE = re.compile(r"(?<!\d)([1-9]\d{5})(?!\d)")

#: Whole-word abbreviations that ARE part of the place name and help a geocoder.
#: "MG Rd" and "Kalamassery Jn" are landmarks; expanding them matches how the
#: gazetteer spells them.
_EXPAND = {
    "rd": "road",
    "jn": "junction",
    "jn.": "junction",
    "flyr": "flyover",
    "ngr": "nagar",
}

#: Proximity words carry no location of their own - "near Lulu Mall" geocodes to
#: Lulu Mall, and keeping "near" only splits the cache. Stripped whole-word.
_PROXIMITY = {
    "near",
    "nr",
    "opp",
    "opposite",
    "beside",
    "besides",
    "behind",
    "adjacent",
    "abv",
    "above",
    "below",
}

#: Spelling canonicalisation for the cache key (PLAN 1.3). Conservative on
#: purpose: it maps renamed/anglicised **city** spellings to the modern form so
#: the cache coheres, and it deliberately does NOT collapse a city onto its
#: district (Kochi -> Ernakulam) - that would send a district name to the
#: geocoder where a city was meant. District-level aliasing is the crosswalk's
#: job (``crosswalk.py``), and it happens after a coordinate exists.
_CITY_ALIASES = {
    "trivandrum": "thiruvananthapuram",
    "bangalore": "bengaluru",
    "calicut": "kozhikode",
    "cochin": "kochi",
    "quilon": "kollam",
    "trichur": "thrissur",
    "alleppey": "alappuzha",
    "palghat": "palakkad",
    "cannanore": "kannur",
    "madras": "chennai",
    "bombay": "mumbai",
    "gurgaon": "gurugram",
}


@dataclass(frozen=True)
class NormalisedAddress:
    """The address, reduced to what a geocoder and a cache can agree on."""

    #: The cleaned, spelling-canonicalised text sent to a geocoder. May be empty
    #: if the input was only a PIN - the cascade can still query by postcode.
    query: str
    #: The extracted PIN, kept apart so it survives digit-stripping and can both
    #: sharpen the geocode and cross-check the district (PLAN 1.4).
    pincode: str | None
    #: The input exactly as received. Kept because a normalisation we get wrong
    #: is only debuggable if the original survived.
    raw: str

    @property
    def cache_key(self) -> str:
        """L1's primary key.

        Includes the PIN so two genuinely different places that share a name but
        differ by PIN do not collide on one cache row - the query alone is not a
        safe key.
        """
        return f"{self.query}|{self.pincode or ''}"

    @property
    def is_empty(self) -> bool:
        """Nothing to geocode - not even a PIN. The caller should not spend a call."""
        return not self.query and not self.pincode


def extract_pincode(raw: str) -> str | None:
    """The first standalone 6-digit PIN, or None. Pure."""
    match = _PINCODE.search(raw)
    return match.group(1) if match else None


def normalise_address(raw: str) -> NormalisedAddress:
    """Reduce a raw address to a stable query + its PIN.

    Order matters: the PIN is taken **first**, off the raw string, before the
    digit-stripping below could destroy it. Everything after is about making the
    same place spell the same way every time.
    """
    pincode = extract_pincode(raw)

    # Diacritics and case are presentation, not identity (as in crosswalk.py).
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()

    # Punctuation to spaces so "opp." and "rd," tokenise cleanly.
    text = re.sub(r"[^a-z0-9]+", " ", text)

    out: list[str] = []
    for token in text.split():
        if token in _PROXIMITY:
            continue
        if token.isdigit():
            # Door numbers, the PIN, stray phone fragments - none help a
            # gazetteer match and all split the cache. The PIN is already saved.
            continue
        token = _EXPAND.get(token, token)
        token = _CITY_ALIASES.get(token, token)
        out.append(token)

    return NormalisedAddress(query=" ".join(out).strip(), pincode=pincode, raw=raw)
