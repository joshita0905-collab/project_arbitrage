from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Exposure(BaseModel):
    id: str | None = None
    entity: str
    currency: str
    amount: float
    maturity_days: int
    hedged_pct: float
    risk_bucket: str


class Policy(BaseModel):
    id: str
    name: str
    category: str
    threshold: float
    severity: str
    require_human_escalation: bool
    description: str | None = None


class Shock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str
    currency_pair: str
    market_move_pct: float
    spot_rate: float = Field(gt=0)
    market_date: str
    source: str
    retrieved_at: str
    shock_type: Literal["fx"] = "fx"
    note: str | None = None


class ExposureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: str = Field(min_length=1, max_length=120)
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    maturity_days: int = Field(ge=0, le=3650)
    hedged_pct: Decimal = Field(ge=0, le=100, max_digits=6, decimal_places=3)


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    category: Literal["fx", "hedge", "exposure"]
    threshold: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    severity: Literal["low", "medium", "high", "critical"]
    require_human_escalation: bool
    description: str | None = Field(default=None, max_length=500)


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str | None = Field(default=None, min_length=1, max_length=64)


class RiskAssessment(BaseModel):
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score: float = Field(ge=0, le=100)
    summary: str
    exposure_size: float
    hedge_coverage: float
    market_movement_severity: float
    maturity_risk: float
    policy_flags: list[str] = []
    historical_analogues: list[str] = []
    proposed_actions: list[str] = []
    uncertainties: list[str] = []
    requires_human_approval: bool = True
    safety_boundary: str = "No autonomous execution of trades, hedges, transfers, or payments. Human approval is required."
    recommendation: str = "HUMAN_REVIEW_REQUIRED"


class GroqAssessmentResponse(BaseModel):
    risk_level: str
    risk_score: float = Field(ge=0, le=100)
    executive_summary: str
    historical_analogues: list[str] = []
    policy_flags: list[str] = []
    guardrail_status: str = "PRECEDENT_INTACT"
    proposed_actions: list[str] = []
    uncertainties: list[str] = []
    recommendation: str = "HUMAN_REVIEW_REQUIRED"
    requires_human_approval: bool = True
    memory_learning: str = ""


class DecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVE", "REJECT", "ESCALATE"]
    rationale: str = Field(min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    assessment_id: str = Field(min_length=1, max_length=64)


class SimulatedActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=2000)


class HealthStatus(BaseModel):
    status: str
    mock_mode: bool
    configured: dict[str, bool]
    version: str = "0.1.0"
