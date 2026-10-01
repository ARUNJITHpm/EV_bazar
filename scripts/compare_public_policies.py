"""Offline human-review diff against an explicit subsidy_rules JSON export.

python -m scripts.compare_public_policies --snapshot FILE --public-root DIR
    --sha256 RELEASE_DIGEST --subsidy-rules-json FILE

The JSON export is an array of rows from subsidy_rules (see models/tariffs.py).
No DB connection, writes, amount parsing, fuzzy matches or rule application.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.domain.public_reference import PublicReference, Row


def compare(policies: tuple[Row, ...], rules: list[Row]) -> list[Row]:
    findings: list[Row] = []
    matched: set[int] = set()
    for policy in policies:
        candidates = [
            (index, rule)
            for index, rule in enumerate(rules)
            if rule.get("source_url") == policy.get("source_url")
        ]
        if not candidates:
            findings.append({"kind": "policy_without_source_match", "policy": policy})
        for index, rule in candidates:
            matched.add(index)
            # URL match is a review candidate, never proof of matching clauses,
            # monetary terms, state codes, hardware or eligibility.
            differences: Row = {
                field: {"policy": policy.get(left), "rule": rule.get(right)}
                for field, left, right in (
                    ("valid_from", "valid_from", "effective_from"),
                    ("valid_to", "valid_to", "effective_to"),
                    ("eligibility", "eligibility", "conditions"),
                )
                if policy.get(left) != rule.get(right)
            }
            findings.append(
                {
                    "kind": "source_match_requires_human_review",
                    "policy": policy,
                    "rule": rule,
                    "differences": differences,
                    "amount_comparison": "not_parsed; verify manually",
                }
            )
    for index, rule in enumerate(rules):
        if index not in matched:
            findings.append({"kind": "rule_without_policy_source_match", "rule": rule})
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--subsidy-rules-json", type=Path, required=True)
    args = parser.parse_args()
    reference = PublicReference.load(args.snapshot, args.public_root, expected_sha256=args.sha256)
    result = reference.lookup("state_ev_policies")
    if result.status == "pending":
        raise SystemExit("Policy dataset pending; no comparison performed")
    rules = json.loads(args.subsidy_rules_json.read_text(encoding="utf-8"))
    if not isinstance(rules, list) or any(not isinstance(row, dict) for row in rules):
        raise SystemExit("subsidy_rules export must be an array of objects")
    print(
        json.dumps(
            {
                "versions": result.versions,
                "snapshot_sha256": result.snapshot_sha256,
                "review_only": True,
                "findings": compare(result.rows, rules),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
