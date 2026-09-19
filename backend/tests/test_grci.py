"""Unit tests: domain calculations, eligibility (PRD §§12, 13, 35)."""
import pytest
from app.grci import estimate_production, is_eligible, supply_load


def test_s_equals_a_times_y():
    assert estimate_production(2.0, 4.0)["s_mt"] == pytest.approx(8.0)


def test_uncertainty_range():
    r = estimate_production(area_ha=10.0, yield_mt_per_ha=3.0, area_margin_ha=2.0)
    assert (r["a_low_ha"], r["a_high_ha"]) == (pytest.approx(8.0), pytest.approx(12.0))
    assert (r["s_low_mt"], r["s_high_mt"]) == (pytest.approx(24.0), pytest.approx(36.0))


def test_uncertainty_clamped_at_zero():
    r = estimate_production(area_ha=1.0, yield_mt_per_ha=2.0, area_margin_ha=5.0)
    assert r["a_low_ha"] == pytest.approx(0.0)
    assert r["s_low_mt"] == pytest.approx(0.0)


def test_l_fixture_0_372():
    # S=9.3 MT (3.1 ha x 3.0 MT/ha), R=25.0 MT -> L=0.372
    s = estimate_production(3.1, 3.0)["s_mt"]
    assert supply_load(s, 25.0) == pytest.approx(0.372)


def test_l_rejects_missing_reference():
    with pytest.raises(ValueError):
        supply_load(9.3, 0)


@pytest.mark.parametrize(
    "rtype,vstate,expected",
    [
        ("local_committed_demand", "reviewed_verified", True),
        ("local_historical_absorption", "reviewed_verified", True),
        ("national_utilization_context", "reviewed_verified", False),  # context only
        ("historical_production_baseline", "reviewed_verified", False),  # baseline only
        ("demo_coordination_baseline", "synthetic_demo", False),  # never real R
        ("local_committed_demand", "user_provided_unverified", False),
        ("local_committed_demand", "stale", False),
        ("local_committed_demand", "superseded", False),
        ("local_committed_demand", "synthetic_demo", False),
        ("local_committed_demand", "official_context", False),
    ],
)
def test_eligibility_matrix(rtype, vstate, expected):
    assert is_eligible(rtype, vstate) is expected
