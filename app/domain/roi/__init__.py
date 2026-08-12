"""PART 3b - the ROI engine.

    ####################################################################
    #  PURE. NO IMPORTS FROM ANYWHERE ELSE IN THE APPLICATION.         #
    ####################################################################

No DB session. No HTTP client. No ``datetime.now()``. No config import.
No globals. Inputs in, dict out. If this code needs a value, that value
becomes a field on the input dataclass - it is never fetched.

This is enforced in CI by the import-linter contract "ROI engine is pure"
in ``pyproject.toml``. AGENTS.md: do not weaken the contract to make a
change compile.

Why it matters: no model may ever output a financial number. Payback, IRR,
NPV and revenue come only from here. That means a wrong financial number is
always traceable to a bad tariff PDF or a bad geocode - never to a model
that "just felt like it". This module is the reason the product is
auditable, and purity is the only thing keeping it that way.
"""
