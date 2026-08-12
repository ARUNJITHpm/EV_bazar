"""Resolve coordinates to a district - PART 1.4.

    uv run python -m scripts.resolve_point 9.9312 76.2673
    uv run python -m scripts.resolve_point 9.9312 76.2673 --pincode 680001
    uv run python -m scripts.resolve_point --selftest
    uv run python -m scripts.resolve_point --audit

``--selftest`` runs a fixed set of real coordinates with known answers - the
cheap ground truth PLAN 1 asks for, in miniature. ``--audit`` checks the loaded
polygons for overlaps, which is the data bug the resolver refuses on rather
than works around. Run it after every reference reload.
"""

from __future__ import annotations

import argparse
import sys

from app.db import SessionLocal
from app.domain.resolution.geography import Resolution, find_overlapping_districts, resolve

#: Real places with answers a human can check on a map. Deliberately includes
#: the awkward ones: a coastal city, a state border, and open sea.
SELFTEST: tuple[tuple[str, float, float, str | None], ...] = (
    ("Kochi, Kerala", 9.9312, 76.2673, "Ernakulam"),
    ("Thiruvananthapuram", 8.5241, 76.9366, "Thiruvananthapuram"),
    ("Bengaluru, MG Road", 12.9716, 77.5946, "Bengaluru Urban"),
    ("Chennai, Marina", 13.0500, 80.2824, "Chennai"),
    ("Coimbatore", 11.0168, 76.9558, "Coimbatore"),
    ("Hyderabad", 17.3850, 78.4867, "Hyderabad"),
    ("Leh, Ladakh", 34.1526, 77.5771, "Leh Ladakh"),
    # Walayar: the NH-544 crossing on the Kerala/Tamil Nadu line. Two SERCs
    # within a few hundred metres, which is exactly the case the ambiguity
    # flag exists for.
    ("Walayar (KL/TN border)", 10.8280, 76.8460, None),
    ("Arabian Sea", 12.0000, 70.0000, None),
)


def show(label: str, res: Resolution) -> None:
    district = res.district.name if res.district else "—"
    state = res.district.state_name if res.district else ""
    print(f"{label}")
    print(f"  district     {district} {f'({res.lgd_district_code})' if res.resolved else ''}")
    if state:
        print(f"  state        {state}")
    print(f"  method       {res.method}")
    print(f"  confidence   {res.confidence}")
    print(f"  ambiguous    {res.boundary_ambiguous}")
    if res.pincode_at_point:
        print(f"  pin at point {', '.join(res.pincode_at_point)}")
    if res.expected_pincode:
        print(f"  pin supplied {res.expected_pincode}  conflict={res.pin_conflict}")
    for reason in res.reasons:
        print(f"  · {reason}")


def selftest() -> int:
    failures = 0
    with SessionLocal() as session:
        for label, lat, lng, expected in SELFTEST:
            res = resolve(session, lat, lng)
            got = res.district.name if res.district else None
            ok = expected is None or got == expected
            failures += not ok
            flag = "OK " if ok else "XX "
            amb = " ambiguous" if res.boundary_ambiguous else ""
            print(
                f"  {flag} {label:<26} -> {str(got):<22} {res.method:<13} {res.confidence:<7}{amb}"
            )
            if res.neighbour is not None:
                print(
                    f"        neighbour: {res.neighbour.name} "
                    f"({res.neighbour.state_name}) at {res.neighbour.distance_m:.0f} m"
                )
    print(f"\nunexpected results: {failures}")
    return 1 if failures else 0


#: Square metres. Below this an "overlap" is digitisation noise on a shared
#: edge - two draughtsmen tracing the same line - not two districts claiming
#: the same ground. Reported, because a growing pile of slivers means the
#: source changed; not a failure, because no site is a square metre wide.
SLIVER_M2 = 1000.0


def _area(m2: float) -> str:
    return f"{m2:.2f} m²" if m2 < 10_000 else f"{m2 / 1e6:.3f} km²"


def audit() -> int:
    with SessionLocal() as session:
        overlaps = find_overlapping_districts(session)
    if not overlaps:
        print("no overlapping district polygons - every point belongs to at most one district")
        return 0

    material = [o for o in overlaps if o[4] >= SLIVER_M2]
    slivers = [o for o in overlaps if o[4] < SLIVER_M2]

    if slivers:
        print(f"{len(slivers)} shared-edge sliver(s), below {SLIVER_M2:.0f} m² - noise, not a bug:")
        for a_code, a_name, b_code, b_name, area in slivers[:20]:
            print(f"  {a_name} ({a_code}) x {b_name} ({b_code}): {_area(area)}")

    if not material:
        print("\nno material overlaps - every point belongs to at most one district")
        return 0

    print(f"\n{len(material)} MATERIAL OVERLAP(S). Sites inside these are attributed by coin toss:")
    for a_code, a_name, b_code, b_name, area in material[:20]:
        print(f"  {a_name} ({a_code}) x {b_name} ({b_code}): {_area(area)}")
    print("\nFix the source polygons. The resolver refuses these rather than guessing.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Point -> district (PLAN 1.4)")
    parser.add_argument("lat", nargs="?", type=float)
    parser.add_argument("lng", nargs="?", type=float)
    parser.add_argument("--pincode", help="PIN the customer supplied, for the cross-check")
    parser.add_argument("--selftest", action="store_true", help="known coordinates, known answers")
    parser.add_argument("--audit", action="store_true", help="check the polygons for overlaps")
    args = parser.parse_args(argv)

    if args.audit:
        return audit()
    if args.selftest:
        return selftest()
    if args.lat is None or args.lng is None:
        parser.print_help()
        return 2

    with SessionLocal() as session:
        show(
            f"{args.lat}, {args.lng}",
            resolve(session, args.lat, args.lng, expected_pincode=args.pincode),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
