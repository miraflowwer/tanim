"""Unit: PlanIn / ReferenceIn negatives (PRD S10.2, S11.3, S32, S35)."""
import pytest

pytest.importorskip("pydantic")
pytest.importorskip("app.schemas")

from app.schemas import PlanIn, ReferenceIn
from pydantic import ValidationError


def _plan(**over):
    base = {
        "crop_code": "tomato",
        "organization_id": "org-1",
        "area_ha": 2.0,
        "planting_date": "2026-09-01",
        "harvest_period": "2026-12-01",
    }
    base.update(over)
    return base


def _ref(**over):
    base = {
        "crop_code": "tomato",
        "organization_id": "org-1",
        "amount_mt": 100.0,
        "unit": "MT",
        "reference_type": "historical_production_baseline",
        "geography": "CALABARZON",
        "period": "2021-2025",
        "source": "PSA test",
    }
    base.update(over)
    return base


def test_plan_ok():
    p = PlanIn(**_plan())
    assert p.area_ha == 2.0


@pytest.mark.parametrize("area", [0, -1, -0.5])
def test_plan_area_must_be_positive(area):
    with pytest.raises(ValidationError):
        PlanIn(**_plan(area_ha=area))


def test_plan_margin_must_be_non_negative():
    with pytest.raises(ValidationError):
        PlanIn(**_plan(area_margin_ha=-0.1))


def test_plan_harvest_must_not_precede_planting():
    with pytest.raises(ValidationError):
        PlanIn(**_plan(planting_date="2026-12-01", harvest_period="2026-09-01"))


def test_plan_rejects_evidence_fields_from_client():
    with pytest.raises(ValidationError):
        PlanIn(**{**_plan(), "reference_type": "local_committed_demand"})


def test_plan_rejects_extra_fields():
    with pytest.raises(ValidationError):
        PlanIn(**{**_plan(), "demand_mt": 99})


def test_plan_rejects_empty_crop():
    with pytest.raises(ValidationError):
        PlanIn(**_plan(crop_code=""))


def test_reference_ok_defaults_unverified():
    r = ReferenceIn(**_ref())
    assert r.verification_status == "user_provided_unverified"
    assert r.unit == "MT"


@pytest.mark.parametrize("amt", [0, -5])
def test_reference_amount_positive(amt):
    with pytest.raises(ValidationError):
        ReferenceIn(**_ref(amount_mt=amt))


def test_reference_unit_must_be_mt():
    with pytest.raises(ValidationError):
        ReferenceIn(**_ref(unit="KG"))


def test_reference_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ReferenceIn(**_ref(verified=True))


def test_reference_never_auto_verified_by_default():
    # Farmer-submitted candidate must enter as unverified; reviewer promotes later.
    r = ReferenceIn(**_ref(reference_type="local_committed_demand"))
    assert r.verification_status == "user_provided_unverified"
