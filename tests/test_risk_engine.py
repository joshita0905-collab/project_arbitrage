from backend.services.risk_engine import calculate_risk_assessment


def test_calculate_risk_assessment_returns_numeric_summary():
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

    result = calculate_risk_assessment(shock, exposures)

    assert "risk_score" in result
    assert "risk_level" in result
    assert "exposure_size" in result
    assert "hedge_coverage" in result
    assert "market_movement_severity" in result
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert result["exposure_size"] > 0


def test_policy_thresholds_are_included_in_risk_score_and_inputs():
    shock = {"currency_pair": "USD/INR", "market_move_pct": 1.0, "spot_rate": 95.0}
    exposures = [{"amount": 1000, "maturity_days": 180, "hedged_pct": 50}]
    strict_policy = [{"name": "FX limit", "category": "fx", "threshold": 1.0}]
    permissive_policy = [{"name": "FX limit", "category": "fx", "threshold": 10.0}]

    strict = calculate_risk_assessment(shock, exposures, strict_policy)
    permissive = calculate_risk_assessment(shock, exposures, permissive_policy)

    assert strict["risk_score"] > permissive["risk_score"]
    assert strict["risk_calculation"]["inputs"]["policies"] == [
        {"name": "FX limit", "category": "fx", "threshold": 1.0}
    ]
    assert strict["risk_calculation"]["components"]["policy_pressure"] == 100
