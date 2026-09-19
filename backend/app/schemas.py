"""Strict request schemas (PRD §§10.2, 11.3, 13, 14.7, 20, 32). Server-side validation only."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

ReferenceType = Literal[
    "local_committed_demand",
    "local_historical_absorption",
    "national_utilization_context",
    "historical_production_baseline",
    "demo_coordination_baseline",
]

VerificationState = Literal[
    "reviewed_verified",
    "user_provided_unverified",
    "official_context",
    "synthetic_demo",
    "stale",
    "superseded",
]

Role = Literal["farmer", "coordinator", "reviewer", "org_admin"]

_strict = ConfigDict(extra="forbid")


class PlanIn(BaseModel):
    """Farmer input only — no evidence fields from client (PRD §10.2)."""

    model_config = _strict

    crop_code: str = Field(min_length=1, max_length=64)
    organization_id: str = Field(min_length=1, max_length=64)
    farm_id: str | None = Field(default=None, max_length=64)
    area_ha: float = Field(gt=0, le=10000)
    area_margin_ha: float = Field(default=0.0, ge=0, le=10000)
    planting_date: date
    harvest_period: date  # period-start date; must not precede planting_date

    @model_validator(mode="after")
    def _check_dates(self):
        if self.harvest_period < self.planting_date:
            raise ValueError("harvest_period must not precede planting_date")
        return self


class PlanPatchIn(BaseModel):
    """Plan adjustment — new revision, never overwrite (PRD §12)."""

    model_config = _strict

    area_ha: float | None = Field(default=None, gt=0, le=10000)
    area_margin_ha: float | None = Field(default=None, ge=0, le=10000)
    planting_date: date | None = None
    harvest_period: date | None = None
    status: Literal["draft", "planned", "harvested", "cancelled"] | None = None

    @model_validator(mode="after")
    def _check_dates(self):
        if self.planting_date and self.harvest_period and self.harvest_period < self.planting_date:
            raise ValueError("harvest_period must not precede planting_date")
        return self


class ReferenceIn(BaseModel):
    """Candidate reference for review workflow (PRD §11.3). Never auto-verified."""

    model_config = _strict

    crop_code: str = Field(min_length=1, max_length=64)
    organization_id: str = Field(min_length=1, max_length=64)
    amount_mt: float = Field(gt=0, le=1e9)
    unit: Literal["MT"] = "MT"
    reference_type: ReferenceType
    geography: str = Field(min_length=1, max_length=128)
    period: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=256)
    evidence_note: str | None = Field(default=None, max_length=2000)
    effective_from: date | None = None
    effective_to: date | None = None

    # These are server-owned properties. Private attrs keep them available to
    # domain callers without exposing them as accepted request fields.
    _verification_status: str = PrivateAttr(default="user_provided_unverified")
    _reviewer_id: str | None = PrivateAttr(default=None)
    _version: int = PrivateAttr(default=1)

    @property
    def verification_status(self) -> str:
        return self._verification_status

    @property
    def reviewer_id(self) -> str | None:
        return self._reviewer_id

    @property
    def version(self) -> int:
        return self._version

    @model_validator(mode="after")
    def _check_window(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class FarmIn(BaseModel):
    """Farm record — exact GPS never required (PRD §19)."""

    model_config = _strict

    organization_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    total_area_ha: float | None = Field(default=None, gt=0, le=100000)
    municipality: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)


class ReviewNoteIn(BaseModel):
    """Reviewer note for submit/verify/reject/flag transitions."""

    model_config = _strict

    note: str | None = Field(default=None, max_length=2000)


class ConsentIn(BaseModel):
    """Explicit consent, one purpose at a time (PRD §8.7)."""

    model_config = _strict

    consent_type: Literal["operational", "research"]
    purpose: str = Field(min_length=1, max_length=512)
    policy_version: str = Field(min_length=1, max_length=64)


class ConsentWithdrawIn(BaseModel):
    model_config = _strict

    consent_type: Literal["operational", "research"]


class PolicyIn(BaseModel):
    """Threshold change — always a new version (PRD §12)."""

    model_config = _strict

    elevated_load: float = Field(gt=0, le=100)
    high_load: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def _check_bands(self):
        if self.high_load <= self.elevated_load:
            raise ValueError("high_load must exceed elevated_load")
        return self


class ExportIn(BaseModel):
    model_config = _strict

    organization_id: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=512)
    include_individuals: bool = False


class RoleChangeIn(BaseModel):
    model_config = _strict

    role: Role


class SessionIn(BaseModel):
    """DEV ONLY login helper — exchange a seeded user id for a dev token."""

    model_config = _strict

    user_id: str = Field(min_length=1, max_length=64)
