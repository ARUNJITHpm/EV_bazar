"""SQLAlchemy models - one module per table group (STACK.md section 2).

Import every model module here so ``Base.metadata`` is fully populated by
the time Alembic autogenerate runs. A model that is not imported here is a
migration that silently does not get written.
"""

from __future__ import annotations

from app.models.api_usage import BILLABLE_STATUSES, ApiUsageEvent, UsageStatus
from app.models.base import Base
from app.models.charger_status import (
    ChargerStatusEvent,
    ConnectorState,
    ConnectorStatus,
    PollOutcome,
    PollRawPayload,
    PollRun,
    Transition,
)
from app.models.geocode import GeocodeCache
from app.models.price_cards import ProviderPriceCard
from app.models.reference import (
    District,
    DistrictNameCrosswalk,
    Pincode,
    ReferenceLayer,
    State,
)
from app.models.schema_version import SchemaVersion

__all__ = [
    "BILLABLE_STATUSES",
    "ApiUsageEvent",
    "Base",
    "ChargerStatusEvent",
    "ConnectorState",
    "ConnectorStatus",
    "District",
    "DistrictNameCrosswalk",
    "GeocodeCache",
    "Pincode",
    "PollOutcome",
    "PollRawPayload",
    "PollRun",
    "ProviderPriceCard",
    "ReferenceLayer",
    "SchemaVersion",
    "State",
    "Transition",
    "UsageStatus",
]
