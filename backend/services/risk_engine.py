from __future__ import annotations

from decimal import Decimal
from typing import Any


def calculate_risk_assessment(
    shock: dict[str, Any],
    exposures: list[dict[str, Any]],
    policies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    exposure_size = sum((Decimal(str(item["amount"])) for item in exposures), Decimal(0))
    hedged_exposure = sum(
        Decimal(str(item["amount"])) * Decimal(str(item["hedged_pct"])) / Decimal(100)
        for item in exposures
    )
    hedge_coverage_pct = hedged_exposure / exposure_size * Decimal(100) if exposure_size else Decimal(0)
    market_move = abs(Decimal(str(shock["market_move_pct"])))
    maturity_risk = (
        sum(
            max(Decimal(0), Decimal(1) - Decimal(item["maturity_days"]) / Decimal(365))
            * Decimal(str(item["amount"]))
            for item in exposures
        )
        / exposure_size
        * Decimal(100)
        if exposure_size
        else Decimal(0)
    )
    market_component = min(Decimal(100), market_move * Decimal(10))
    hedge_gap_component = max(Decimal(0), Decimal(100) - hedge_coverage_pct)
    maturity_component = min(Decimal(100), max(Decimal(0), maturity_risk))
    policy_inputs = policies or []
    policy_pressure = Decimal(0)
    for policy in policy_inputs:
        threshold = Decimal(str(policy["threshold"]))
        category = policy.get("category")
        if category == "fx":
            pressure = market_move / threshold * Decimal(100)
        elif category == "hedge":
            denominator = Decimal(100) - threshold
            pressure = (
                (Decimal(100) - hedge_coverage_pct) / denominator * Decimal(100)
                if denominator > 0
                else Decimal(100)
            )
        elif category == "exposure":
            pressure = exposure_size / threshold * Decimal(100)
        else:
            continue
        policy_pressure = max(policy_pressure, min(Decimal(100), max(Decimal(0), pressure)))

    score = min(
        Decimal(100),
        max(
            Decimal(0),
            market_component * Decimal("0.40")
            + hedge_gap_component * Decimal("0.30")
            + maturity_component * Decimal("0.15")
            + policy_pressure * Decimal("0.15"),
        ),
    )

    if score >= Decimal(80):
        risk_level = "CRITICAL"
    elif score >= Decimal(60):
        risk_level = "HIGH"
    elif score >= Decimal(35):
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_level": risk_level,
        "risk_score": round(float(score), 2),
        "exposure_size": float(exposure_size),
        "hedge_coverage": round(float(hedge_coverage_pct), 2),
        "market_movement_severity": round(float(market_component), 2),
        "maturity_risk": round(float(maturity_risk), 2),
        "risk_calculation": {
            "formula": "40% market-move component + 30% unhedged-exposure component + 15% near-maturity component + 15% policy-pressure component",
            "inputs": {
                "market_move_pct": round(float(market_move), 6),
                "spot_rate": shock.get("spot_rate"),
                "exposure_size": float(exposure_size),
                "hedge_coverage_pct": round(float(hedge_coverage_pct), 2),
                "weighted_near_maturity_pct": round(float(maturity_risk), 2),
                "policies": [
                    {
                        "name": policy.get("name"),
                        "category": policy.get("category"),
                        "threshold": float(policy["threshold"]),
                    }
                    for policy in policy_inputs
                ],
            },
            "components": {
                "market_move": round(float(market_component), 2),
                "unhedged_exposure": round(float(hedge_gap_component), 2),
                "near_maturity": round(float(maturity_component), 2),
                "policy_pressure": round(float(policy_pressure), 2),
            },
        },
        "summary": f"Calculated {risk_level.lower()} risk from the current {shock.get('currency_pair', 'FX')} reference-rate change, saved exposure inputs, and {len(policy_inputs)} configured policy limits.",
    }
