from __future__ import annotations

from decimal import Decimal
from typing import Any


def evaluate_policies(shock: dict[str, Any], exposures: list[dict[str, Any]], policies: list[dict[str, Any]]) -> dict[str, Any]:
    triggered: list[dict[str, Any]] = []
    thresholds: list[str] = []
    requires_human_escalation = False

    exposure_size = sum((Decimal(str(item["amount"])) for item in exposures), Decimal(0))
    hedge_coverage = (
        sum(
            Decimal(str(item["amount"])) * Decimal(str(item["hedged_pct"])) / Decimal(100)
            for item in exposures
        )
        / exposure_size
        * Decimal(100)
        if exposure_size
        else Decimal(0)
    )
    market_move = abs(Decimal(str(shock["market_move_pct"])))

    for policy in policies:
        category = policy.get("category", "")
        threshold = Decimal(str(policy["threshold"]))
        should_trigger = False
        evidence = []

        if category in {"fx", "currency", "market"}:
            should_trigger = market_move >= threshold
            evidence = [f"market_move_pct {market_move:.2f}% >= threshold {threshold:.2f}%"]
        elif category == "hedge":
            should_trigger = hedge_coverage <= threshold
            evidence = [f"hedge_coverage {hedge_coverage:.2f}% <= threshold {threshold:.2f}%"]
        elif category == "exposure":
            should_trigger = exposure_size >= threshold
            evidence = [f"exposure_size {exposure_size:,.2f} >= threshold {threshold:,.2f}"]

        if should_trigger:
            triggered.append({
                "id": policy.get("id"),
                "name": policy.get("name"),
                "category": category,
                "threshold": float(threshold),
                "severity": policy.get("severity", "medium"),
                "evidence": evidence,
            })
            thresholds.append(f"{policy.get('id')}: {policy.get('name')}")
            if policy.get("require_human_escalation"):
                requires_human_escalation = True

    return {
        "triggered_policies": triggered,
        "thresholds_exceeded": thresholds,
        "status": "ASSESSED" if policies else "NO_POLICIES_CONFIGURED",
        "requires_human_escalation": requires_human_escalation,
        "evidence_summary": {
            "market_move_pct": round(float(market_move), 6),
            "hedge_coverage_pct": round(float(hedge_coverage), 6),
            "exposure_size": float(exposure_size),
        },
    }
