"""In-memory P0 store: deterministic seeds, no external DB (PRD §43.1: fragile demo avoided).

Production Pilot Phase A replaces this with SQLAlchemy/Postgres (models.py +
alembic 0001 already sketch the schema); the API contract stays the same.
"""
from datetime import date

# This adapter is intentionally explicit: production deployments must select
# SQLAlchemy/PostgreSQL rather than silently treating this seed store as durable.
STORE_MODE = "development-inmemory"

REGISTRY_VERSION = 7

CROPS: dict = {}
YIELDS: dict = {}
ORGS: dict = {}
USERS: dict = {}
FARMS: dict = {}
PLANS: dict = {}
REFERENCES: dict = {}
POLICIES: list = []
CALCULATIONS: dict = {}
DATA_SOURCES: dict = {}
PRICES: list = []
WEATHER: dict = {}
CLIMATE: list = []
SUITABILITY: list = []
EXPORTS: dict = {}


def reset_store() -> None:
    """Re-seed everything. Tests call this per-test for determinism."""
    CROPS.clear()
    CROPS.update({
        "tomato": {"code": "tomato", "name": "Tomato", "version": 3, "is_active": True},
        "eggplant": {"code": "eggplant", "name": "Eggplant", "version": 2, "is_active": True},
        # Registered but no yield reference -> exercises yield_unavailable (§30).
        "ampalaya": {"code": "ampalaya", "name": "Ampalaya", "version": 1, "is_active": True},
    })
    YIELDS.clear()
    YIELDS.update({
        ("tomato", "CALABARZON"): {
            "id": "yield-tomato-cal", "crop_code": "tomato", "geography": "CALABARZON",
            "period": "2021-2025", "yield_mt_per_ha": 3.0, "version": 2, "source": "PSA",
        },
        ("eggplant", "CALABARZON"): {
            "id": "yield-eggplant-cal", "crop_code": "eggplant", "geography": "CALABARZON",
            "period": "2021-2025", "yield_mt_per_ha": 2.5, "version": 1, "source": "PSA",
        },
    })
    ORGS.clear()
    ORGS.update({
        "org-1": {"id": "org-1", "name": "San Bartolome Coop", "default_geography": "CALABARZON"},
        "org-2": {"id": "org-2", "name": "Sitio Malinis Assoc", "default_geography": "CALABARZON"},
    })
    USERS.clear()
    USERS.update({
        "farmer-1": {"id": "farmer-1", "email": "farmer1@example.ph", "org_roles": {"org-1": "farmer"}},
        "coord-1": {"id": "coord-1", "email": "coord1@example.ph", "org_roles": {"org-1": "coordinator"}},
        "reviewer-1": {"id": "reviewer-1", "email": "reviewer1@example.ph", "org_roles": {"org-1": "reviewer"}},
        "admin-1": {"id": "admin-1", "email": "admin1@example.ph", "org_roles": {"org-1": "org_admin"}},
        "platform-1": {"id": "platform-1", "email": "ops@example.ph", "org_roles": {}, "is_platform": True},
        "farmer-2": {"id": "farmer-2", "email": "farmer2@example.ph", "org_roles": {"org-2": "farmer"}},
    })
    FARMS.clear()
    FARMS.update({
        "farm-1": {"id": "farm-1", "org_id": "org-1", "owner_user_id": "farmer-1",
                   "name": "Bukid 1", "total_area_ha": 3.5,
                   "municipality": "Calamba", "region": "CALABARZON"},
    })
    PLANS.clear()
    PLANS.update({
        "plan-tomato-1": _plan("plan-tomato-1", "org-1", "farm-1", "farmer-1", "tomato",
                               3.1, 0.0, date(2026, 9, 1), date(2026, 12, 1)),
        "plan-eggplant-1": _plan("plan-eggplant-1", "org-1", "farm-1", "farmer-1", "eggplant",
                                 2.0, 0.0, date(2026, 9, 1), date(2026, 12, 1)),
        # org-2 holds only a synthetic demo reference -> insufficient_evidence.
        "plan-org2-tomato": _plan("plan-org2-tomato", "org-2", None, "farmer-2", "tomato",
                                  1.5, 0.0, date(2026, 9, 1), date(2026, 12, 1)),
    })
    REFERENCES.clear()
    REFERENCES.update({
        "ref-tomato-1": {
            "id": "ref-tomato-1", "org_id": "org-1", "crop_code": "tomato",
            "reference_type": "local_committed_demand", "amount_mt": 25.0, "unit": "MT",
            "geography": "CALABARZON", "period": "2026-H2", "source": "Coop procurement records",
            "evidence_note": "Signed buyer commitments, Q4 2026.",
            "verification_status": "reviewed_verified", "review": "verified",
            "reviewer_id": "reviewer-1", "effective_from": date(2026, 1, 1),
            "effective_to": date(2027, 1, 1), "version": 3, "verified_at": "2026-09-18",
            "flags": [],
        },
        # Synthetic demo baseline: must never enter prod calc (§13, §37).
        "ref-tomato-synth": {
            "id": "ref-tomato-synth", "org_id": "org-1", "crop_code": "tomato",
            "reference_type": "demo_coordination_baseline", "amount_mt": 30.0, "unit": "MT",
            "geography": "CALABARZON", "period": "demo", "source": "Seeded demo fixture",
            "evidence_note": "Synthetic demo baseline — context only.",
            "verification_status": "synthetic_demo", "review": "draft",
            "reviewer_id": None, "effective_from": date(2026, 1, 1),
            "effective_to": None, "version": 1, "verified_at": None, "flags": [],
        },
        # Expired verified reference: ineligible, but signals stale (not missing).
        "ref-eggplant-old": {
            "id": "ref-eggplant-old", "org_id": "org-1", "crop_code": "eggplant",
            "reference_type": "local_committed_demand", "amount_mt": 40.0, "unit": "MT",
            "geography": "CALABARZON", "period": "2024-H2", "source": "Coop procurement records",
            "evidence_note": "Expired buying program.",
            "verification_status": "stale", "review": "expired",
            "reviewer_id": "reviewer-1", "effective_from": date(2024, 1, 1),
            "effective_to": date(2025, 1, 1), "version": 2, "verified_at": "2024-06-01",
            "flags": [],
        },
        "ref-org2-synth": {
            "id": "ref-org2-synth", "org_id": "org-2", "crop_code": "tomato",
            "reference_type": "demo_coordination_baseline", "amount_mt": 20.0, "unit": "MT",
            "geography": "CALABARZON", "period": "demo", "source": "Seeded demo fixture",
            "evidence_note": "Synthetic demo baseline — context only.",
            "verification_status": "synthetic_demo", "review": "draft",
            "reviewer_id": None, "effective_from": date(2026, 1, 1),
            "effective_to": None, "version": 1, "verified_at": None, "flags": [],
        },
    })
    # Make the reference scope and immutable review lineage explicit even in
    # deterministic development fixtures. The production adapter uses the same
    # field names and domain predicates.
    for _reference in REFERENCES.values():
        _reference.setdefault("planning_period", _reference.get("period"))
        _reference.setdefault("predecessor_id", None)
        _reference.setdefault("successor_id", None)
        _reference.setdefault("review_history", [])
    REFERENCES["ref-tomato-1"]["review_history"] = [
        {"from": "draft", "to": "under_review", "actor_user_id": "coord-1",
         "at": "2026-09-15T00:00:00+00:00", "note": None},
        {"from": "under_review", "to": "verified", "actor_user_id": "reviewer-1",
         "at": "2026-09-18T00:00:00+00:00", "note": "seeded fixture review"},
    ]

    POLICIES.clear()
    POLICIES.append({
        "id": "policy-v1", "version": 1,
        "thresholds": {"elevated_load": 0.7, "high_load": 1.0},
        "created_by": "platform-1", "created_at": "2026-09-01T00:00:00+00:00",
    })
    CALCULATIONS.clear()
    DATA_SOURCES.clear()
    DATA_SOURCES.update({
        "psa-yield": {
            "key": "psa-yield", "name": "PSA yield reference", "kind": "yield",
            "expected_refresh": "annual", "dataset_version": "psa-2021-2025-v1",
            "last_verified": "2026-09-18",
            "versions": [{"version": 1, "fetched_at": "2026-09-17T00:00:00+00:00",
                          "promoted_at": "2026-09-18T00:00:00+00:00",
                          "checksum": "seed", "payload_ref": "psa-2021-2025"}],
        },
    })
    PRICES.clear()
    PRICES.append({
        "crop_code": "tomato", "geography": "CALABARZON", "observed_on": "2026-09-10",
        "price": 45.0, "currency": "PHP", "series_id": "psa-tomato-calabarzon",
        "source": "PSA", "note": "Context only — never a demand reference.",
    })
    WEATHER.clear()
    WEATHER.update({
        "geography": "CALABARZON", "summary": "Fair, isolated rain showers",
        "retrieved_at": "2026-09-19T06:00:00+00:00", "source": "Open-Meteo adapter (seed)",
        "note": "Short-term context only — not part of the coordination result.",
    })
    CLIMATE.clear()
    CLIMATE.append({
        "geography": "CALABARZON", "period": "OND 2026", "outlook": "Near-normal rainfall",
        "source_date": "2026-09-01", "source": "PAGASA outlook (seed)",
    })
    SUITABILITY.clear()
    SUITABILITY.append({
        "crop_code": "tomato", "geography": "CALABARZON", "layer_id": "nccag-tomato-cal",
        "suitability_class": "Moderately suitable", "source": "NCCAG layer (seed)",
    })
    EXPORTS.clear()


def _plan(pid, org, farm, owner, crop, area, margin, planting, harvest):
    rev = {"revision_number": 1, "area_ha": area, "area_margin_ha": margin,
           "planting_date": planting, "harvest_period": harvest,
           "created_by": owner, "created_at": "2026-09-10T00:00:00+00:00"}
    return {"id": pid, "org_id": org, "farm_id": farm, "crop_code": crop,
            "owner_user_id": owner, "status": "planned",
            "revisions": [rev], "current_revision": 1,
            "created_at": "2026-09-10T00:00:00+00:00"}


reset_store()
