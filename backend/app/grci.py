"""P0 GRCI domain — thin re-export of scripts/grci.py (single source of truth).

All formulas live in scripts/grci.py: S = A x Y, uncertainty clamp
A_low = max(0, A - M), L = S / R, 5 reference types x 6 verification
states, eligibility, bands/status/provenance. Nothing is duplicated here.
"""

import importlib.util
import pathlib

_engine_path = (
    pathlib.Path(__file__).resolve().parents[2] / "scripts" / "grci.py"
)
_spec = importlib.util.spec_from_file_location(
    "_tanim_grci_engine", _engine_path
)
_engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_engine)

ENGINE_VERSION = _engine.ENGINE_VERSION
REFERENCE_TYPES = tuple(_engine.valid_reference_types())
VERIFICATION_STATES = _engine.VERIFICATION_STATES
ELIGIBLE_TYPES = _engine.ELIGIBLE_TYPES
estimate_production = _engine.estimate_production
supply_load = _engine.supply_load
is_eligible = _engine.is_eligible

ACTIVE_PLAN_STATUSES = _engine.ACTIVE_PLAN_STATUSES
INACTIVE_PLAN_STATUSES = _engine.INACTIVE_PLAN_STATUSES
PLAN_STATUSES = _engine.PLAN_STATUSES
REVIEW_STATES = _engine.REVIEW_STATES
REVIEW_TRANSITIONS = _engine.REVIEW_TRANSITIONS
REFERENCE_REVIEW_STATES = _engine.REFERENCE_REVIEW_STATES
REFERENCE_REVIEW_TRANSITIONS = _engine.REFERENCE_REVIEW_TRANSITIONS
TERMINAL_REVIEW_STATES = _engine.TERMINAL_REVIEW_STATES
ELIGIBLE_VERIFICATION_STATES = _engine.ELIGIBLE_VERIFICATION_STATES
REFERENCE_ELIGIBLE_TYPES = _engine.REFERENCE_ELIGIBLE_TYPES
is_active_plan_status = _engine.is_active_plan_status
is_active_plan = _engine.is_active_plan
active_plans = _engine.active_plans
period_key = _engine.period_key
period_matches = _engine.period_matches
reference_context_key = _engine.reference_context_key
reference_applies = _engine.reference_applies
reference_matches_calculation = _engine.reference_matches_calculation
select_eligible_reference = _engine.select_eligible_reference
next_reference_version = _engine.next_reference_version
transition_reference = _engine.transition_reference
classify_coordination_load = _engine.classify_coordination_load

__all__ = [
    "ACTIVE_PLAN_STATUSES",
    "ELIGIBLE_TYPES",
    "REFERENCE_ELIGIBLE_TYPES",
    "ELIGIBLE_VERIFICATION_STATES",
    "ENGINE_VERSION",
    "INACTIVE_PLAN_STATUSES",
    "PLAN_STATUSES",
    "REFERENCE_TYPES",
    "REFERENCE_REVIEW_STATES",
    "REFERENCE_REVIEW_TRANSITIONS",
    "REVIEW_STATES",
    "REVIEW_TRANSITIONS",
    "TERMINAL_REVIEW_STATES",
    "VERIFICATION_STATES",
    "active_plans",
    "classify_coordination_load",
    "estimate_production",
    "is_active_plan",
    "is_active_plan_status",
    "is_eligible",
    "next_reference_version",
    "period_key",
    "period_matches",
    "reference_applies",
    "reference_context_key",
    "reference_matches_calculation",
    "select_eligible_reference",
    "supply_load",
    "transition_reference",
]


def __getattr__(name):
    return getattr(_engine, name)
