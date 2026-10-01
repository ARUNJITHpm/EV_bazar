"""Read-only public-context coverage for stored report payloads.

Old reports are inspected without defaults or reassembly. This module deliberately
does not import or depend on the unpublished twelve-section console rebuild.
"""
from collections.abc import Mapping
from typing import Any


def public_context_gaps(payload: Mapping[str, Any]) -> tuple[str, ...]:
    context = payload.get("public_context")
    if not isinstance(context, dict):
        return ("public context absent from this stored report",)
    sources = context.get("sources", [])
    return tuple(
        f"{source['dataset']}: {source['status']}"
        for source in sources
        if source.get("status") != "available"
    )
