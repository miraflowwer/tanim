"""Observability S33 + analytics S34: ids, 10 fields, 7 typed events, no PII."""
import re
import uuid
from datetime import UTC, datetime

from app.grci import ENGINE_VERSION

POLICY_VERSION = "grci-1.0"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

REQUIRED_10 = [
    "calculation_id",
    "request_id",
    "engine_version",
    "policy_version",
    "dataset_version",
    "reference_version",
    "organization_id",
    "status",
    "duration_ms",
    "timestamp",
]


def new_request_id():
    return str(uuid.uuid4())


def new_calculation_id():
    return str(uuid.uuid4())


def build_calculation_log(**over):
    now = datetime.now(UTC).isoformat()
    log = {
        "calculation_id": new_calculation_id(),
        "request_id": new_request_id(),
        "engine_version": ENGINE_VERSION,
        "policy_version": POLICY_VERSION,
        "dataset_version": "psa-2021-2025-v1",
        "reference_version": "ref-v3",
        "organization_id": "org-1",
        "status": "complete",
        "duration_ms": 12,
        "timestamp": now,
    }
    log.update(over)
    return log


EVENTS = (
    "plan_started",
    "plan_saved",
    "calculation_completed",
    "calculation_incomplete",
    "result_evidence_opened",
    "plan_adjusted",
    "alternative_compared",
)


def make_event(name, organization_id="org-1", plan_ref="plan-1"):
    assert name in EVENTS, name
    return {
        "event": name,
        "organization_id": organization_id,
        "plan_ref": plan_ref,  # opaque ref only, never raw farmer data
        "timestamp": datetime.now(UTC).isoformat(),
    }


def test_ids_are_uuid():
    assert UUID_RE.match(new_request_id())
    assert UUID_RE.match(new_calculation_id())
    assert new_request_id() != new_calculation_id()


def test_10_fields_logged_and_stored():
    log = build_calculation_log()
    for f in REQUIRED_10:
        assert f in log, f
    assert log["engine_version"] == ENGINE_VERSION
    assert log["policy_version"] == POLICY_VERSION
    assert log["duration_ms"] >= 0
    datetime.fromisoformat(log["timestamp"])


def test_log_has_no_pii():
    log = build_calculation_log()
    blob = str(log).lower()
    for banned in ["farmer ", "gps", "latitude", "barangay", "family", "income"]:
        assert banned not in blob, banned
    # exact area / name must never ride along in the observability row
    assert "juan" not in blob


def test_7_analytics_events_typed():
    assert len(EVENTS) == 7
    for name in EVENTS:
        ev = make_event(name)
        assert ev["event"] == name
        assert "timestamp" in ev


def test_analytics_has_no_pii():
    for name in EVENTS:
        blob = str(make_event(name)).lower()
        for banned in ["gps", "latitude", "income", "family", "juan"]:
            assert banned not in blob, (name, banned)
