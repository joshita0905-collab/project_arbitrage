from __future__ import annotations

from typing import Any


def evaluate_guardrails(current_shock: dict[str, Any], historical_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return whether the current shock exceeds the worst retained historical precedent.

    The guardrail acts as a hard safety layer: if the current market move exceeds the most severe
    historical event by more than 2.5x, the transaction path must be frozen and escalated.
    """
    worst_historical = 0.0
    for event in historical_events:
        worst_historical = max(worst_historical, float(event.get("market_move_pct", 0.0) or 0.0))

    live_move = abs(float(current_shock.get("market_move_pct", 0.0) or 0.0))
    if not historical_events:
        return {
            "guardrail_status": "INSUFFICIENT_REFERENCE_DATA",
            "manual_override_required": True,
            "live_move_pct": round(live_move, 6),
            "worst_historical_move_pct": None,
            "precedent_variance_index": None,
            "safety_message": "No live historical FX series is available; human review is required without a precedent comparison.",
        }
    variance_index = (live_move / worst_historical) if worst_historical else 0.0
    is_precedent_shatter = worst_historical > 0 and variance_index > 2.5

    return {
        "guardrail_status": "PRECEDENT_SHATTERED" if is_precedent_shatter else "PRECEDENT_INTACT",
        "manual_override_required": is_precedent_shatter,
        "live_move_pct": round(live_move, 2),
        "worst_historical_move_pct": round(worst_historical, 2),
        "precedent_variance_index": round(variance_index, 2),
        "safety_message": (
            "PRECEDENT SHATTERED: Manual C-Suite override required due to historic volatility anomaly."
            if is_precedent_shatter
            else "Policy path remains within retained historical precedent."
        ),
    }
