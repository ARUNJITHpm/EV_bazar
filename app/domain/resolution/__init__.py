"""PART 1 - pin or address --> trusted ``lgd_district_code``.

    reference.py   which reference layers we load, and under what licence
    crosswalk.py   foreign district spellings -> LGD code. PURE.
    normalise.py   raw address -> stable query + PIN. PURE. L0 of the cascade.
    geocode.py     the cascade orchestrator. PART 1.3
    providers/     one geocoder each; nominatim.py is L2 (free). PART 1.3
    geography.py   coordinates -> district, with the doubts stated. PART 1.4

Cascade: normalise -> cache -> nominatim -> ola -> mappls -> google -> manual.
The free levels (normalise, cache, nominatim) are built; the paid ones (ola,
mappls, google) and the manual queue are not yet.

The through-line of this package is that it would rather refuse than guess. A
district attributed wrongly produces a report that is wrong in every number
and looks completely normal, so both the name matcher and the point-in-polygon
resolver return "ask a human" as a first-class answer.
"""

from __future__ import annotations

from app.domain.resolution.crosswalk import (
    Candidate,
    Match,
    canonical_name,
    match_district,
    normalise_name,
)
from app.domain.resolution.geocode import (
    DEFAULT_DISAGREEMENT_M,
    GeocodeOutcome,
    GeocodeStatus,
    classify_geocode,
    geocode,
    haversine_m,
)
from app.domain.resolution.geography import (
    Confidence,
    DistrictHit,
    Method,
    Resolution,
    classify,
    find_overlapping_districts,
    resolve,
)
from app.domain.resolution.normalise import (
    NormalisedAddress,
    extract_pincode,
    normalise_address,
)
from app.domain.resolution.providers.nominatim import (
    GeocodeResult,
    NominatimGeocoder,
    parse_search,
)
from app.domain.resolution.reference import LAYERS, LayerSpec

__all__ = [
    "DEFAULT_DISAGREEMENT_M",
    "LAYERS",
    "Candidate",
    "Confidence",
    "DistrictHit",
    "GeocodeOutcome",
    "GeocodeResult",
    "GeocodeStatus",
    "LayerSpec",
    "Match",
    "Method",
    "NominatimGeocoder",
    "NormalisedAddress",
    "Resolution",
    "canonical_name",
    "classify",
    "classify_geocode",
    "extract_pincode",
    "find_overlapping_districts",
    "geocode",
    "haversine_m",
    "match_district",
    "normalise_address",
    "normalise_name",
    "parse_search",
    "resolve",
]
