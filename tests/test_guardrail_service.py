from backend.services.guardrail_service import evaluate_guardrails


def test_guardrail_detects_precedent_shatter():
    historical = [
        {"scenario": "2023 INR volatility spike", "market_move_pct": 7.8, "rate_move_bp": 72},
        {"scenario": "2022 EUR repricing", "market_move_pct": 5.4, "rate_move_bp": 48},
    ]
    current = {"scenario": "black swan shock", "market_move_pct": 21.0, "rate_move_bp": 180}

    result = evaluate_guardrails(current, historical)

    assert result["manual_override_required"] is True
    assert result["guardrail_status"] == "PRECEDENT_SHATTERED"
    assert result["precedent_variance_index"] > 2.5
