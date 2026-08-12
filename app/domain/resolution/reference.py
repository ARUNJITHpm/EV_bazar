"""The reference-layer registry - PART 1.2.

Which layers we load, where each comes from, and under what licence. Code
rather than a config file for the same reason the polling registry is: adding
a dataset should be a reviewable diff with a licence recorded next to it.

Everything here is GeoParquet from the india-geodata mirror, which matters for
one reason worth stating: **the district polygons already carry LGD codes**
(``dist_lgd``). PLAN 1.2 assumed we would be matching shapefile names to LGD
names by hand for the primary layer; we do not have to. The hand-verified
crosswalk is still needed - VAHAN, tariff orders and census extracts all speak
names - but not for the geometry itself.
"""

from __future__ import annotations

from dataclasses import dataclass

_RELEASES = "https://github.com/yashveeeeeeer/india-geodata/releases/download"


@dataclass(frozen=True)
class LayerSpec:
    """One downloadable reference layer."""

    name: str
    url: str
    licence: str
    #: What this layer is actually for, in one line. If a layer cannot be
    #: given a reason, it should not be downloaded.
    purpose: str
    #: Columns to read. Never "all": these files are tens to hundreds of MB
    #: and column pruning is most of the reason for using Parquet.
    columns: tuple[str, ...]
    note: str | None = None


#: The geometry column, by GeoParquet convention. WKB, EPSG:4326.
GEOMETRY_COLUMN = "geometry"


LAYERS: tuple[LayerSpec, ...] = (
    LayerSpec(
        name="states",
        url=f"{_RELEASES}/admin/states/LGD_States.parquet",
        licence="Open Government Data (India) via india-geodata mirror",
        purpose="State polygons keyed to LGD state codes; the tariff regime boundary.",
        # Upper-case here, lower-case in the districts build. The publisher is
        # not consistent between layers, so the casing is pinned per layer
        # rather than guessed.
        columns=("STNAME", "STCODE11", "State_LGD", GEOMETRY_COLUMN),
    ),
    LayerSpec(
        name="districts",
        url=f"{_RELEASES}/admin/districts/LGD_Districts.parquet",
        licence="Open Government Data (India) via india-geodata mirror",
        purpose="The join key of the entire system: pin -> lgd_district_code.",
        columns=(
            "dtname",
            "stname",
            "dtcode11",
            "stcode11",
            "dist_lgd",
            "state_lgd",
            "year_stat",
            GEOMETRY_COLUMN,
        ),
        note=(
            "785 features. Includes post-2011 districts (Telangana 2014, Ladakh 2019, "
            "later UP/AP/Assam splits) - see year_stat. Two J&K rows covering "
            "PoK-administered areas carry no LGD code and are skipped on load."
        ),
    ),
    LayerSpec(
        name="pincodes",
        url=f"{_RELEASES}/postal/boundaries/Datagov_Pincode_Boundaries.parquet",
        licence="data.gov.in, Government Open Data Licence - India",
        purpose="Cross-check a geocode's district (PLAN 1.4: PIN disagrees -> trust PIN).",
        columns=("Pincode", "Office_Name", "Circle", "Region", "Division", GEOMETRY_COLUMN),
        note=(
            "19,312 features. Chosen over the 270 MB PincodeBoundaries build: this is "
            "the data.gov.in release and a fifteenth the size. Carries India Post's own "
            "circle/region/division hierarchy and NO district column - a postal circle "
            "is not a state, so the district cross-check is done spatially, not by name."
        ),
    ),
)

BY_NAME: dict[str, LayerSpec] = {layer.name: layer for layer in LAYERS}
