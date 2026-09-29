from backend.services.policy_engine import evaluate_policies


def test_evaluate_policies_detects_triggered_rules():
    shock = {
        "scenario": "USD/INR shock",
        "currency_pair": "USD/INR",
        "market_move_pct": 8.5,
        "rate_move_bp": 80,
        "shock_type": "fx",
    }

    exposures = [
        {
            "currency": "USD",
            "amount": 1500000,
            "maturity_days": 180,
            "hedged_pct": 35,
        }
    ]

    policies = [
        {
            "id": "FX-001",
            "name": "FX alert threshold",
            "category": "fx",
            "threshold": 7.0,
            "severity": "high",
            "require_human_escalation": True,
        },
        {
            "id": "FX-002",
            "name": "Hedge coverage floor",
            "category": "hedge",
            "threshold": 50,
            "severity": "medium",
            "require_human_escalation": False,
        },
    ]

    result = evaluate_policies(shock, exposures, policies)

    assert "triggered_policies" in result
    assert "requires_human_escalation" in result
    assert "thresholds_exceeded" in result
    assert isinstance(result["triggered_policies"], list)
    assert result["requires_human_escalation"] is True
