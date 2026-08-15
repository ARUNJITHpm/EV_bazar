"""PART 1 - pin or address --> trusted ``lgd_district_code``.

    reference.py   which reference layers we load, and under what licence
    crosswalk.py   foreign district spellings -> LGD code. PURE.
    normalise.py   raw address -> stable query + PIN. PURE. L0 of the cascade.
    geocode.py     the cascade orchestrator. PART 1.3
    cascade.py     assembles the levels; the only place a paid one is built
    manual.py      L6 - the queue a refusal goes to, and the write-back
    providers/     one geocoder each, plus the metering wrapper
    geography.py   coordinates -> district, with the doubts stated. PART 1.4
    sites.py       both verdicts folded into one `sites` row. PART 1.5

Cascade: normalise -> cache -> nominatim -> ola -> mappls -> google -> manual.

The through-line of this package is that it would rather refuse than guess. A
district attributed wrongly produces a report that is wrong in every number
and looks completely normal, so both the name matcher and the point-in-polygon
resolver return "ask a human" as a first-class answer - and L6 is where that
answer goes, which is what makes refusing affordable.
"""

from __future__ import annotations

from app.domain.resolution.cascade import PAID_LEVELS, build_cascade
from app.domain.resolution.crosswalk import (
    Candidate,
    Match,
    canonical_name,
    match_district,
    normalise_name,
)
from app.domain.resolution.geocode import (
    DEFAULT_DISAGREEMENT_M,
    MAX_OPINIONS,
    GeocodeOutcome,
    GeocodeStatus,
    classify_geocode,
    doubt_about,
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
from app.domain.resolution.manual import MANUAL_SOURCE, enqueue, open_jobs
from app.domain.resolution.normalise import (
    NormalisedAddress,
    extract_pincode,
    normalise_address,
)
from app.domain.resolution.providers.base import Geocoder, GeocoderError, GeocodeResult
from app.domain.resolution.providers.google import GoogleGeocoder
from app.domain.resolution.providers.mappls import MapplsGeocoder
from app.domain.resolution.providers.metered import MeteredGeocoder
from app.domain.resolution.providers.nominatim import NominatimGeocoder, parse_search
from app.domain.resolution.providers.ola import OlaGeocoder
from app.domain.resolution.reference import LAYERS, LayerSpec
from app.domain.resolution.sites import (
    SiteFacts,
    choose_pincode,
    combine,
    get_site,
    resolve_site,
    upsert_site,
)

__all__ = [
    "DEFAULT_DISAGREEMENT_M",
    "LAYERS",
    "MANUAL_SOURCE",
    "MAX_OPINIONS",
    "PAID_LEVELS",
    "Candidate",
    "Confidence",
    "DistrictHit",
    "GeocodeOutcome",
    "GeocodeResult",
    "GeocodeStatus",
    "Geocoder",
    "GeocoderError",
    "GoogleGeocoder",
    "LayerSpec",
    "MapplsGeocoder",
    "Match",
    "MeteredGeocoder",
    "Method",
    "NominatimGeocoder",
    "NormalisedAddress",
    "OlaGeocoder",
    "Resolution",
    "SiteFacts",
    "build_cascade",
    "canonical_name",
    "choose_pincode",
    "classify",
    "classify_geocode",
    "combine",
    "doubt_about",
    "enqueue",
    "extract_pincode",
    "find_overlapping_districts",
    "geocode",
    "get_site",
    "haversine_m",
    "match_district",
    "normalise_address",
    "normalise_name",
    "open_jobs",
    "parse_search",
    "resolve",
    "resolve_site",
    "upsert_site",
]
