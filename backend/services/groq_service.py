import json
from typing import Any

from groq import Groq
from pydantic import BaseModel, ValidationError, field_validator

from backend.config import is_placeholder, settings


class GroqAssessmentResponse(BaseModel):
    risk_level: str
    risk_score: float
    executive_summary: str
    historical_analogues: list[str] = []
    policy_flags: list[str] = []
    guardrail_status: str = "PRECEDENT_INTACT"
    proposed_actions: list[str] = []
    uncertainties: list[str] = []
    recommendation: str = "HUMAN_REVIEW_REQUIRED"
    requires_human_approval: bool = True
    memory_learning: str = ""

    @staticmethod
    def _stringify(item: Any) -> str:
        if item is None:
            return ""
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("summary", "text", "name", "message", "title"):
                value = item.get(key)
                if value:
                    return str(value)
            return json.dumps(item, ensure_ascii=True, sort_keys=True, default=str)
        return str(item)

    @field_validator("historical_analogues", "policy_flags", "proposed_actions", "uncertainties", mode="before")
    @classmethod
    def _coerce_list_strings(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [cls._stringify(value)]
        if isinstance(value, (list, tuple)):
            return [cls._stringify(item) for item in value if item is not None and str(item).strip()]
        return [cls._stringify(value)]


class GroqRiskService:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        candidate = api_key if api_key is not None else settings.groq_api_key
        self.api_key = candidate if candidate and not is_placeholder(candidate) else ""
        self.model = model or settings.groq_model
        self.client = Groq(api_key=self.api_key, timeout=30.0) if self.api_key else None

    def is_configured(self) -> bool:
        return bool(self.client and self.api_key)

    def _build_system_prompt(self) -> str:
        return (
            "You are Project Arbitrage, a treasury decision-support AI for a multinational corporation. "
            "Analyze the current market shock, exposure metrics, treasury policies, and Hindsight historical memories. "
            "Historical memories are evidence, not guarantees. Current facts must be separated from historical evidence. "
            "market_move_pct is already expressed in percentage points: 0.16698 means 0.16698%, not 1.6698%. "
            "risk_calculation.components.market_move is a 0-100 risk score contribution, not a market percentage. "
            "Never multiply, rescale, or relabel market_move_pct using the risk component. "
            "Return ONLY valid JSON with fields exactly: risk_level, risk_score, executive_summary, historical_analogues, "
            "policy_flags, guardrail_status, proposed_actions, uncertainties, recommendation, requires_human_approval, memory_learning. "
            "Set recommendation to HUMAN_REVIEW_REQUIRED whenever the case is material or uncertain. "
            "Do not execute trades, hedges, transfers, or payments. Report uncertainty explicitly. "
            "If precedent-shatter conditions are present, set guardrail_status to PRECEDENT_SHATTERED and escalate." 
        )

    def assess(self, payload: dict[str, Any], *, live_mode: bool = False) -> dict[str, Any]:
        if not live_mode:
            raise RuntimeError("Non-live Groq assessment is disabled; synthetic responses are not available.")
        if settings.use_mock_ai:
            raise RuntimeError("Live assessment is disabled while USE_MOCK_AI=true.")

        if not self.is_configured():
            raise RuntimeError("Groq is not configured. Set GROQ_API_KEY and GROQ_MODEL to enable live reasoning.")

        try:
            normalized_payload = json.loads(json.dumps(payload, default=str))
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": json.dumps(normalized_payload, ensure_ascii=True)},
                ],
                temperature=0.1,
                max_tokens=1600,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Groq returned empty content")
            parsed = json.loads(content)
            validated = GroqAssessmentResponse.model_validate(parsed)
            return validated.model_dump()
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError(f"Groq structured response validation failed: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Groq live assessment failed: {exc}") from exc


groq_risk_service = GroqRiskService()
