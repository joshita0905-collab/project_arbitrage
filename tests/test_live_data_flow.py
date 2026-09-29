from __future__ import annotations

import json
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend import main
from backend.services.portfolio_service import PortfolioDataService
from backend.services import market_data_service


class TestMarketProvider:
    def get_fx_snapshot(self, base_currency: str, quote_currency: str) -> dict[str, Any]:
        return {
            "currency_pair": f"{base_currency}/{quote_currency}",
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "spot_rate": 10.125,
            "market_move_pct": 0.25,
            "latest_date": "2026-09-28",
            "previous_date": "2026-09-25",
            "previous_rate": 10.1,
            "historical_daily_moves": [
                {"date": "2026-09-24", "market_move_pct": 0.1},
                {"date": "2026-09-25", "market_move_pct": 0.2},
            ],
            "source": "test-only market provider",
            "retrieved_at": "2026-09-29T00:00:00+00:00",
        }


def test_frankfurter_provider_uses_dated_api_rates(monkeypatch) -> None:
    payload = {
        "amount": 1.0,
        "base": "USD",
        "start_date": "2026-09-25",
        "end_date": "2026-09-28",
        "rates": {
            "2026-09-25": {"INR": 95.82},
            "2026-09-28": {"INR": 95.98},
        },
    }
    requested: dict[str, Any] = {}

    def fake_urlopen(request, timeout):
        requested["url"] = request.full_url
        requested["timeout"] = timeout
        return BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(market_data_service, "urlopen", fake_urlopen)
    result = market_data_service.FrankfurterMarketDataProvider("https://api.frankfurter.dev/v1").get_fx_snapshot("usd", "inr")

    assert "/2026-" in requested["url"]
    assert "base=USD" in requested["url"]
    assert result["spot_rate"] == 95.98
    assert result["previous_rate"] == 95.82
    assert result["market_move_pct"] == round((95.98 / 95.82 - 1) * 100, 6)
    assert result["latest_date"] == "2026-09-28"
    assert result["source"] == market_data_service.FrankfurterMarketDataProvider.source


def test_exposure_amount_round_trips_as_exact_decimal(tmp_path: Path) -> None:
    store = PortfolioDataService(tmp_path / "portfolio.sqlite3")
    assert store.list_exposures() == []

    saved = store.add_exposure({
        "entity": "User Entered Test Entity",
        "currency": "USD",
        "amount": "1234567.890123",
        "maturity_days": 42,
        "hedged_pct": "37.125",
    })
    reopened = PortfolioDataService(tmp_path / "portfolio.sqlite3").list_exposures()

    assert saved["amount"] == "1234567.890123"
    assert reopened[0]["amount"] == "1234567.890123"
    assert Decimal(reopened[0]["amount"]) == Decimal("1234567.890123")
    assert reopened[0]["source"] == "user_entered"


def test_live_api_flow_persists_assessment_decision_and_audit(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioDataService(tmp_path / "portfolio.sqlite3")
    monkeypatch.setattr(main, "portfolio_data", store)
    monkeypatch.setattr(main, "market_data_provider", TestMarketProvider())
    retained: list[dict[str, Any]] = []
    monkeypatch.setattr(
        main.hindsight_memory_service,
        "recall_memories",
        lambda query, limit=5, **kwargs: [{"id": "memory-1", "text": "test recall", "tags": ["live"]}],
    )
    monkeypatch.setattr(
        main.hindsight_memory_service,
        "retain_memory",
        lambda memory, **kwargs: retained.append(memory) or {"status": "ok"},
    )
    monkeypatch.setattr(main.groq_risk_service, "assess", lambda payload, **kwargs: {
        "risk_level": "LOW",
        "risk_score": 1,
        "executive_summary": "Test-only reasoning fixture.",
        "historical_analogues": [],
        "policy_flags": [],
        "proposed_actions": [],
        "uncertainties": [],
    })

    client = TestClient(main.app)
    assert client.post("/api/exposures", json={
        "entity": "API Test Entity",
        "currency": "USD",
        "amount": "100000.123456",
        "maturity_days": 60,
        "hedged_pct": "40.25",
    }).status_code == 201
    assert client.post("/api/policies", json={
        "name": "API test FX limit",
        "category": "fx",
        "threshold": "1.25",
        "severity": "high",
        "require_human_escalation": True,
        "description": "Test-only policy input.",
    }).status_code == 201

    assessment_response = client.post("/api/assess", json={"assessment_id": "test-assessment-1"})
    assert assessment_response.status_code == 200, assessment_response.text
    assessment = assessment_response.json()
    assert assessment["market"]["source"] == "test-only market provider"
    assert assessment["risk_calculation"]["risk_calculation"]["inputs"]["exposure_size"] == 100000.123456
    assert assessment["risk_score"] != 1
    assert assessment["data_provenance"]["exposures"] == "user_entered"
    assert retained[0]["event_type"] == "risk_assessment"

    decision_response = client.post("/api/decision", json={
        "decision": "ESCALATE",
        "rationale": "Test-only human review record.",
        "notes": "No financial action is executed.",
        "assessment_id": "test-assessment-1",
    })
    assert decision_response.status_code == 200, decision_response.text
    assert retained[1]["event_type"] == "human_decision"
    assert retained[1]["decision"] == "ESCALATE"

    audit_response = client.get("/api/audit")
    assert audit_response.status_code == 200
    assert audit_response.json()[-1]["payload"]["decision"] == "ESCALATE"
    assert PortfolioDataService(tmp_path / "portfolio.sqlite3").list_audit_events()[-1]["payload"]["assessment_id"] == "test-assessment-1"


def test_assessment_requires_persisted_exposure_and_policy_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "portfolio_data", PortfolioDataService(tmp_path / "empty.sqlite3"))
    response = TestClient(main.app).post("/api/assess", json={})
    assert response.status_code == 409
    assert "No exposure data" in response.json()["detail"]


def test_decision_is_persisted_when_hindsight_retention_fails(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioDataService(tmp_path / "decision.sqlite3")
    monkeypatch.setattr(main, "portfolio_data", store)
    store.save_assessment("decision-test", {
        "shock": {"market_move_pct": 0.25},
        "exposures": [{"amount": "1000", "hedged_pct": "50"}],
        "policies": [],
        "guardrail": {"guardrail_status": "PRECEDENT_INTACT", "manual_override_required": False},
    })

    def fail_retention(*args, **kwargs):
        raise RuntimeError("test-only unavailable provider")

    monkeypatch.setattr(main.hindsight_memory_service, "retain_memory", fail_retention)
    response = TestClient(main.app).post("/api/decision", json={
        "decision": "ESCALATE",
        "rationale": "Test-only persistence verification.",
        "assessment_id": "decision-test",
    })

    assert response.status_code == 200
    assert response.json()["hindsight_status"] == "unavailable"
    persisted = PortfolioDataService(tmp_path / "decision.sqlite3").list_audit_events()
    assert persisted[-1]["payload"]["decision"] == "ESCALATE"
    assert persisted[-1]["payload"]["hindsight_retention"] == "unavailable"


def test_guardrail_blocks_approval_without_manual_override(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioDataService(tmp_path / "guardrail.sqlite3")
    monkeypatch.setattr(main, "portfolio_data", store)
    store.save_assessment("guardrail-test", {
        "shock": {"market_move_pct": 0.25},
        "exposures": [{"amount": "1000", "hedged_pct": "50"}],
        "policies": [],
        "guardrail": {"guardrail_status": "PRECEDENT_SHATTERED", "manual_override_required": True},
    })

    response = TestClient(main.app).post("/api/decision", json={
        "decision": "APPROVE",
        "rationale": "Test-only prohibited approval.",
        "assessment_id": "guardrail-test",
    })

    assert response.status_code == 409
    assert "manual override" in response.json()["detail"]
    assert store.list_audit_events() == []


def test_simulated_cycle_is_persisted_and_duplicate_submissions_are_idempotent(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cycle.sqlite3"
    store = PortfolioDataService(database_path)
    monkeypatch.setattr(main, "portfolio_data", store)
    store.save_assessment("cycle-test", {
        "created_at": "2026-09-29T00:00:00+00:00",
        "shock": {"scenario": "Test-only live-market fixture", "currency_pair": "USD/INR", "market_move_pct": 0.25},
        "market": {"currency_pair": "USD/INR", "market_move_pct": 0.25, "source": "test-only provider"},
        "exposures": [{"entity": "TEST ONLY", "amount": "1000", "currency": "USD", "hedged_pct": "50"}],
        "policies": [],
        "guardrail": {"guardrail_status": "PRECEDENT_INTACT", "manual_override_required": False},
        "hindsight_memories": [],
        "hindsight_recall_status": "no_match",
        "risk_level": "LOW",
        "risk_score": 12.5,
    })
    retained: list[dict[str, Any]] = []
    monkeypatch.setattr(
        main.hindsight_memory_service,
        "retain_memory",
        lambda memory, **kwargs: retained.append(memory) or {"operation_id": f"test-operation-{len(retained)}"},
    )
    client = TestClient(main.app)
    decision_payload = {
        "decision": "APPROVE",
        "rationale": "Test-only approval for simulated action coverage.",
        "assessment_id": "cycle-test",
    }
    premature_action = client.post("/api/actions/simulate", json={
        "assessment_id": "cycle-test",
        "action": "Test-only action before human approval.",
    })
    assert premature_action.status_code == 409

    first_decision = client.post("/api/decision", json=decision_payload)
    duplicate_decision = client.post("/api/decision", json=decision_payload)
    conflicting_decision = client.post("/api/decision", json=decision_payload | {"decision": "REJECT"})
    assert first_decision.status_code == 200
    assert duplicate_decision.status_code == 200
    assert duplicate_decision.json()["created"] is False
    assert conflicting_decision.status_code == 409
    assert len(retained) == 1

    action_payload = {
        "assessment_id": "cycle-test",
        "action": "Test-only simulated exposure adjustment",
    }
    first_action = client.post("/api/actions/simulate", json=action_payload)
    duplicate_action = client.post("/api/actions/simulate", json=action_payload)
    conflicting_action = client.post(
        "/api/actions/simulate",
        json=action_payload | {"action": "Different test-only action"},
    )
    assert first_action.status_code == 200
    assert first_action.json()["simulation_only"] is True
    assert first_action.json()["protected_amount"] is None
    assert first_action.json()["hindsight_retention_status"] == "retained"
    assert duplicate_action.json() == first_action.json()
    assert conflicting_action.status_code == 409
    assert len(retained) == 2
    assert retained[-1]["event_type"] == "completed_treasury_cycle"

    records_response = client.get("/api/records")
    detail_response = client.get("/api/records/cycle-test")
    audit_response = client.get("/api/audit")
    reopened = PortfolioDataService(database_path)
    persisted = reopened.get_assessment("cycle-test")
    assert records_response.status_code == 200
    assert records_response.json()[0]["decision"] == "APPROVE"
    assert records_response.json()[0]["outcome"] is not None
    assert detail_response.json()["simulated_action"]["action_id"] == first_action.json()["action_id"]
    assert [event["event"] for event in audit_response.json()] == ["human_decision", "simulated_action"]
    assert persisted["human_decision"]["decision"] == "APPROVE"
    assert persisted["simulated_action"]["hindsight_retention_status"] == "retained"


def test_memory_overview_reports_unavailable_without_hindsight_credentials(monkeypatch) -> None:
    monkeypatch.setattr(main.hindsight_memory_service, "list_memory_records", lambda: (_ for _ in ()).throw(RuntimeError("not configured")))

    response = TestClient(main.app).get("/api/memory")

    assert response.status_code == 502
    assert "memory listing failed" in response.json()["detail"]


def test_cors_preflight_allows_only_configured_frontend_origin() -> None:
    client = TestClient(main.app)
    allowed = client.options(
        "/api/assess",
        headers={
            "Origin": main.settings.frontend_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    denied = client.options(
        "/api/assess",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == main.settings.frontend_origin
    assert "access-control-allow-origin" not in denied.headers
