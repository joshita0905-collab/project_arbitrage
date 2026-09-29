import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.services.groq_service import GroqAssessmentResponse, GroqRiskService
from backend.services.hindsight_service import HindsightMemoryService


def test_placeholder_keys_are_not_treated_as_live_credentials():
    groq = GroqRiskService(api_key="your_real_groq_key_here")
    hindsight = HindsightMemoryService(api_key="your_real_hindsight_key_here")

    assert groq.is_configured() is False
    assert hindsight.is_configured() is False
    with pytest.raises(RuntimeError, match="HINDSIGHT_API_KEY is missing"):
        hindsight.recall_memories("test query", limit=2)
    with pytest.raises(RuntimeError, match="HINDSIGHT_API_KEY is missing"):
        hindsight.retain_memory({"event_type": "test-only"})


def test_groq_non_live_assessment_does_not_generate_synthetic_results():
    groq = GroqRiskService(api_key="")

    with pytest.raises(RuntimeError, match="synthetic responses are not available"):
        groq.assess({"shock": {"market_move_pct": 99}})


def test_groq_prompt_distinguishes_market_percentage_from_risk_component():
    groq = GroqRiskService(api_key="test-key")

    prompt = groq._build_system_prompt()

    assert "0.16698 means 0.16698%" in prompt
    assert "risk score contribution, not a market percentage" in prompt


def test_hindsight_recall_scores_are_json_serializable():
    service = HindsightMemoryService(api_key="test-key")
    payload = {
        "scores": SimpleNamespace(final=0.91, reranker=0.75, semantic=0.88, keyword=0.6),
        "nested": [SimpleNamespace(value=1)],
    }
    normalized = service._normalize_for_json(payload)

    assert json.loads(json.dumps(normalized)) == {
        "scores": {"final": 0.91, "reranker": 0.75, "semantic": 0.88, "keyword": 0.6},
        "nested": [{"value": 1}],
    }


def test_hindsight_memory_inventory_keeps_only_app_owned_non_synthetic_units(monkeypatch):
    service = HindsightMemoryService(api_key="test-key")
    items = [
        SimpleNamespace(id="actual", text="Real app assessment", context="assessment", tags=["project-arbitrage"], metadata={}, occurred_start=None, mentioned_at=None, updated_at=None, var_date="2026-09-29", fact_type="world", document_id="doc-1"),
        SimpleNamespace(id="unrelated", text="Diagnostic", context="test", tags=["diagnostic"], metadata={}, occurred_start=None, mentioned_at=None, updated_at=None, var_date="2026-09-28", fact_type="observation", document_id=None),
        SimpleNamespace(id="tagged-synthetic", text="Synthetic", context="test", tags=["project-arbitrage", "synthetic"], metadata={}, occurred_start=None, mentioned_at=None, updated_at=None, var_date="2026-09-27", fact_type="world", document_id="doc-2"),
        SimpleNamespace(id="metadata-synthetic", text="Synthetic metadata", context="test", tags=["project-arbitrage"], metadata={"synthetic": True}, occurred_start=None, mentioned_at=None, updated_at=None, var_date="2026-09-26", fact_type="world", document_id="doc-3"),
    ]

    class FakeClient:
        async def aget_bank_config(self, bank_id):
            return {"bank_id": bank_id}

        async def alist_memories(self, **kwargs):
            return SimpleNamespace(total=len(items), items=items)

    def run_with_fake_client(operation):
        async def run():
            return await operation(FakeClient())

        return asyncio.run(run())

    monkeypatch.setattr(service, "_run_with_client", run_with_fake_client)

    result = service.list_memory_records()

    assert result["total_units"] == 1
    assert result["records"][0]["id"] == "actual"
    assert result["fact_type_counts"] == {"world": 1}
    assert result["category_counts_available"] is False


def test_groq_assessment_coerces_dict_entries_to_strings():
    parsed = GroqAssessmentResponse.model_validate({
        "risk_level": "HIGH",
        "risk_score": 72.5,
        "executive_summary": "Treasury risk is elevated.",
        "historical_analogues": [
            {"id": "a1", "summary": "2023 FX shock analog"},
            {"id": "a2", "text": "1987 rate move analog"},
        ],
        "policy_flags": [{"id": "FX-002", "name": "Hedge coverage floor", "status": "breached"}],
        "proposed_actions": ["Escalate to treasury committee"],
        "uncertainties": ["Timing may vary"],
        "recommendation": "HUMAN_REVIEW_REQUIRED",
        "requires_human_approval": True,
        "memory_learning": "Use historical evidence carefully.",
    })

    assert parsed.historical_analogues == ["2023 FX shock analog", "1987 rate move analog"]
    assert parsed.policy_flags == ["Hedge coverage floor"]
