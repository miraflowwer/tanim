"""Framework independent domain policy tests.

These tests call the authoritative Python domain module directly. They do not
reimplement the policy in a test helper.
"""
from datetime import date

import pytest

from app.grci import (
    ACTIVE_PLAN_STATUSES,
    REVIEW_TRANSITIONS,
    classify_coordination_load,
    period_key,
    period_matches,
    reference_matches_calculation,
    transition_reference,
)


def _reference(**overrides):
    reference = {
        "id": "ref-1",
        "org_id": "org-1",
        "crop_code": "tomato",
        "geography": "CALABARZON",
        "period": "2026-H2",
        "reference_type": "local_committed_demand",
        "verification_status": "reviewed_verified",
        "review": "verified",
        "effective_from": date(2026, 1, 1),
        "effective_to": date(2027, 1, 1),
        "version": 1,
    }
    reference.update(overrides)
    return reference


def test_period_dates_and_compact_half_year_are_exactly_canonicalized():
    assert period_key(date(2026, 12, 1)) == "2026-H2"
    assert period_key("2026H2") == "2026-H2"
    assert period_matches("2026-H2", date(2026, 12, 1))
    assert not period_matches("2026-H1", date(2026, 12, 1))


def test_reference_matches_all_tenant_context_and_validity_predicates():
    kwargs = {
        "organization_id": "org-1",
        "crop_code": "tomato",
        "geography": "CALABARZON",
        "harvest_period": date(2026, 12, 1),
        "calculation_date": date(2026, 9, 19),
    }
    assert reference_matches_calculation(_reference(), **kwargs)
    for field, value in (
        ("org_id", "org-2"),
        ("crop_code", "eggplant"),
        ("geography", "NCR"),
        ("period", "2026-H1"),
        ("effective_from", date(2026, 10, 1)),
        ("effective_to", date(2026, 9, 18)),
        ("verification_status", "synthetic_demo"),
        ("review", "draft"),
    ):
        assert not reference_matches_calculation(_reference(**{field: value}), **kwargs)


def test_active_statuses_and_review_transition_graph_are_domain_constants():
    assert ACTIVE_PLAN_STATUSES == frozenset({"draft", "planned"})
    assert REVIEW_TRANSITIONS["draft"] == frozenset({"under_review"})
    record = _reference(review="draft", verification_status="user_provided_unverified")
    transition_reference(record, "under_review", actor_user_id="coord-1", at="t1")
    transition_reference(record, "verified", actor_user_id="reviewer-1", at="t2")
    assert record["review"] == "verified"
    assert len(record["review_history"]) == 2
    with pytest.raises(ValueError):
        transition_reference(record, "draft")


def test_coordination_load_classification_is_single_policy():
    thresholds = {"elevated_load": 0.7, "high_load": 1.0}
    assert classify_coordination_load(0.69, thresholds) == "within_reference"
    assert classify_coordination_load(0.7, thresholds) == "elevated_coordination_load"
    assert classify_coordination_load(1.0, thresholds) == "high_coordination_load"
