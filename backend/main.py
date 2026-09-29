from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.models import AssessmentRequest, DecisionRecord, ExposureInput, PolicyInput, SimulatedActionRequest
from backend.services.groq_service import groq_risk_service
from backend.services.guardrail_service import evaluate_guardrails
from backend.services.hindsight_service import hindsight_memory_service
from backend.services.market_data_service import FrankfurterMarketDataProvider, MarketDataUnavailable
from backend.services.policy_engine import evaluate_policies
from backend.services.portfolio_service import configure_portfolio_data_service
from backend.services.risk_engine import calculate_risk_assessment

app = FastAPI(title="Project Arbitrage", version="0.1.0")
logger = logging.getLogger("project_arbitrage.api")
market_data_provider = FrankfurterMarketDataProvider(settings.market_data_api_url)
portfolio_data = configure_portfolio_data_service(settings.portfolio_database_path)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _retention_reference(response: dict[str, Any]) -> dict[str, Any]:
    return {
        key: response[key]
        for key in ("operation_id", "operation_ids", "items_count", "async")
        if response.get(key) is not None
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    market_configured = bool(settings.market_data_api_url and settings.market_base_currency and settings.market_quote_currency)
    return {
        "status": "ok",
        "mock_mode": settings.use_mock_ai,
        "configured": {
            "groq": settings.groq_configured,
            "hindsight": settings.hindsight_configured,
            "market_data": market_configured,
        },
        "provider_status": {
            "groq": "NOT RUN YET" if settings.groq_configured else "UNAVAILABLE",
            "hindsight": "NOT RUN YET" if settings.hindsight_configured else "UNAVAILABLE",
            "market_data": "NOT CHECKED" if market_configured else "UNAVAILABLE",
        },
        "market_data_source": FrankfurterMarketDataProvider.source if market_configured else "unconfigured",
        "market_pair": f"{settings.market_base_currency}/{settings.market_quote_currency}" if market_configured else None,
        "frontend_origin": settings.frontend_origin,
        "safety_boundary": "No autonomous execution of trades, hedges, transfers, or payments. Human approval required.",
    }


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    try:
        market = market_data_provider.get_fx_snapshot(settings.market_base_currency, settings.market_quote_currency)
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"LIVE MARKET DATA UNAVAILABLE: {exc}") from exc
    exposures = portfolio_data.list_exposures()
    policies = portfolio_data.list_policies()
    records = portfolio_data.list_assessment_records(limit=10000)
    return {
        "market": market,
        "exposure_count": len(exposures),
        "policy_count": len(policies),
        "current_exposure_source": "user_entered" if exposures else "not_configured",
        "market_status": "connected",
        "record_counts": {
            "events": len(records),
            "decisions": sum(record["decision"] is not None for record in records),
            "outcomes": sum(record["outcome"] is not None for record in records),
        },
        "recent_records": records[:5],
    }


@app.get("/api/exposures")
def exposures() -> list[dict[str, Any]]:
    return portfolio_data.list_exposures()


@app.post("/api/exposures", status_code=201)
def add_exposure(payload: ExposureInput) -> dict[str, Any]:
    if payload.currency.upper() != settings.market_base_currency:
        raise HTTPException(
            status_code=422,
            detail=f"Exposure currency must match the configured market base currency ({settings.market_base_currency}).",
        )
    return portfolio_data.add_exposure(payload.model_dump())


@app.get("/api/policies")
def policies() -> list[dict[str, Any]]:
    return portfolio_data.list_policies()


@app.post("/api/policies", status_code=201)
def add_policy(payload: PolicyInput) -> dict[str, Any]:
    return portfolio_data.add_policy(payload.model_dump())


@app.get("/api/memories")
def memories() -> list[dict[str, Any]]:
    try:
        return hindsight_memory_service.recall_memories("project arbitrage treasury risk", limit=5, live_mode=True)
    except Exception as exc:
        logger.error("hindsight_recall_failed exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail=f"Official Hindsight recall failed ({type(exc).__name__}).") from exc


@app.get("/api/memory")
def memory_overview() -> dict[str, Any]:
    try:
        return hindsight_memory_service.list_memory_records()
    except Exception as exc:
        logger.error("hindsight_memory_listing_failed exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail=f"Official Hindsight memory listing failed ({type(exc).__name__}).") from exc


@app.get("/api/records")
def records(limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="Record limit must be between 1 and 500.")
    return portfolio_data.list_assessment_records(limit=limit)


@app.get("/api/records/{record_id}")
def record_detail(record_id: str) -> dict[str, Any]:
    assessment = portfolio_data.get_assessment(record_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Treasury record not found.")
    audit_records = [
        event for event in portfolio_data.list_audit_events(limit=10000)
        if event.get("payload", {}).get("assessment_id") == record_id
    ]
    return assessment | {
        "assessment_id": record_id,
        "record_id": record_id,
        "market_event": assessment.get("market"),
        "agent_analysis": {
            key: assessment.get(key)
            for key in ("executive_summary", "proposed_actions", "uncertainties", "recommendation")
            if assessment.get(key) is not None
        },
        "audit": audit_records,
    }


@app.post("/api/assess")
def assess(payload: AssessmentRequest) -> dict[str, Any]:
    logger.info("assessment_request_received")
    exposures = portfolio_data.list_exposures()
    policies = portfolio_data.list_policies()
    if not exposures:
        raise HTTPException(status_code=409, detail="No exposure data is configured. Add a real exposure in the dashboard before assessing risk.")
    if not policies:
        raise HTTPException(status_code=409, detail="No policies are configured. Add actual policy thresholds before assessing risk.")

    try:
        market = market_data_provider.get_fx_snapshot(settings.market_base_currency, settings.market_quote_currency)
    except MarketDataUnavailable as exc:
        logger.error("assessment_market_data_unavailable exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail=f"LIVE MARKET DATA UNAVAILABLE: {exc}") from exc
    shock = {
        "scenario": f"Live {market['currency_pair']} reference-rate movement",
        "currency_pair": market["currency_pair"],
        "market_move_pct": market["market_move_pct"],
        "spot_rate": market["spot_rate"],
        "market_date": market["latest_date"],
        "source": market["source"],
        "retrieved_at": market["retrieved_at"],
        "shock_type": "fx",
        "note": "Daily change calculated from the latest and prior published business-day reference rates.",
    }

    risk = calculate_risk_assessment(shock, exposures, policies)
    policy_result = evaluate_policies(shock, exposures, policies)
    guardrail = evaluate_guardrails(shock, market["historical_daily_moves"])
    logger.info("assessment_calculated policy_status=%s guardrail_status=%s", policy_result["status"], guardrail["guardrail_status"])
    try:
        memories = hindsight_memory_service.recall_memories(
            f"{shock.get('currency_pair', '')} {shock.get('scenario', '')} treasury risk",
            limit=3,
            live_mode=True,
        )
    except Exception as exc:
        logger.error("assessment_hindsight_recall_failed exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail=f"Official Hindsight recall failed ({type(exc).__name__}).") from exc
    logger.info("assessment_hindsight_recall_complete records=%d", len(memories))

    assessment_payload = {
        "shock": shock,
        "exposure_summary": risk,
        "policies": policy_result,
        "guardrail": guardrail,
        "memories": memories,
        "safety_boundary": "No autonomous execution of trades, hedges, transfers, or payments. Human approval required.",
    }
    try:
        assessment = groq_risk_service.assess(assessment_payload, live_mode=True)
    except Exception as exc:
        logger.error("assessment_groq_failed exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail=f"Groq live assessment failed ({type(exc).__name__}).") from exc
    logger.info("assessment_groq_complete")
    assessment_id = payload.assessment_id or str(uuid4())
    assessment["assessment_id"] = assessment_id
    assessment["shock"] = shock
    assessment["market"] = market
    assessment["risk_calculation"] = risk
    assessment["risk_level"] = risk["risk_level"]
    assessment["risk_score"] = risk["risk_score"]
    assessment["exposures"] = exposures
    assessment["policies"] = policies
    assessment["policy_result"] = policy_result
    assessment["policy_flags"] = policy_result["thresholds_exceeded"]
    assessment["historical_analogues"] = [item.get("text", "") for item in memories]
    assessment["hindsight_memories"] = memories
    assessment["data_provenance"] = {"market": market["source"], "exposures": "user_entered", "policies": "user_entered"}
    assessment["guardrail"] = guardrail
    assessment["requires_human_approval"] = True
    assessment["recommendation"] = (
        "MANUAL_OVERRIDE_REQUIRED" if guardrail["manual_override_required"] else "HUMAN_REVIEW_REQUIRED"
    )
    assessment["guardrail_status"] = guardrail["guardrail_status"]
    assessment["precedent_variance_index"] = guardrail["precedent_variance_index"]
    assessment["hindsight_recall_status"] = "matched" if memories else "no_match"
    assessment["hindsight_recall_count"] = len(memories)
    try:
        retention_result = hindsight_memory_service.retain_memory({
            "event_type": "risk_assessment",
            "scenario": shock.get("scenario", "unknown"),
            "assessment": assessment,
            "outcome": "pending_human_review",
            "guardrail": guardrail,
        },
            context="Live market assessment retained pending human review",
            tags=["project-arbitrage", "live-assessment", "treasury"],
            metadata={"assessment_id": assessment_id, "market_source": market["source"]},
            live_mode=True,
        )
    except Exception as exc:
        logger.error("assessment_hindsight_retention_failed exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail=f"Official Hindsight retention failed ({type(exc).__name__}).") from exc
    logger.info("assessment_hindsight_retention_complete")
    assessment["hindsight_retention_status"] = "retained"
    assessment["hindsight_reference"] = _retention_reference(retention_result)
    assessment["created_at"] = market["retrieved_at"]
    portfolio_data.save_assessment(assessment_id, assessment)

    portfolio_data.append_audit_event("assessment_created", {
        "assessment_id": assessment_id,
        "risk_level": risk["risk_level"],
        "risk_score": risk["risk_score"],
        "market_date": market["latest_date"],
    })
    logger.info("assessment_response_returned assessment_id=%s", assessment_id)

    return assessment


@app.post("/api/decision")
def decision(payload: dict[str, Any]) -> dict[str, Any]:
    logger.info("decision_request_received")
    try:
        record = DecisionRecord.model_validate(payload)
    except Exception as exc:
        logger.warning("decision_validation_failed exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=422, detail="Decision request validation failed.") from exc
    logger.info("decision_validated assessment_id=%s decision=%s", record.assessment_id, record.decision)
    assessment = portfolio_data.get_assessment(record.assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found. Refresh the live assessment before submitting a decision.")
    policy_result = evaluate_policies(assessment["shock"], assessment["exposures"], assessment["policies"])
    guardrail = assessment["guardrail"]
    if record.decision == "APPROVE" and guardrail.get("manual_override_required"):
        raise HTTPException(status_code=409, detail="The live guardrail requires manual override; submit ESCALATE or REJECT instead.")
    if record.decision == "APPROVE" and policy_result["requires_human_escalation"]:
        raise HTTPException(status_code=409, detail="A configured policy requires human escalation; submit ESCALATE or REJECT instead.")
    logger.info("decision_checks_complete policy_status=%s triggered=%d guardrail_status=%s", policy_result["status"], len(policy_result["triggered_policies"]), guardrail["guardrail_status"])
    decision_payload = {
        "event_type": "human_decision",
        "decision": record.decision,
        "rationale": record.rationale,
        "notes": record.notes,
        "assessment_id": record.assessment_id,
        "outcome": "decision_recorded",
        "policy_result": policy_result,
        "guardrail": guardrail,
        "hindsight_retention_status": "pending",
    }
    try:
        saved_decision, created = portfolio_data.record_decision(record.assessment_id, decision_payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Assessment not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if created:
        hindsight_status = "retained"
        retention_reference = None
        try:
            retention_result = hindsight_memory_service.retain_memory(
                decision_payload,
                context="Human decision on live Project Arbitrage assessment",
                tags=["project-arbitrage", "human-decision", record.decision.lower(), "treasury"],
                metadata={"assessment_id": record.assessment_id, "decision": record.decision},
                live_mode=True,
            )
            retention_reference = _retention_reference(retention_result)
            logger.info("decision_hindsight_retention_complete assessment_id=%s", record.assessment_id)
        except Exception as exc:
            logger.error("decision_hindsight_retention_failed exception_class=%s", type(exc).__name__)
            hindsight_status = "unavailable"
        portfolio_data.update_decision_retention(record.assessment_id, hindsight_status, retention_reference)
        saved_decision["hindsight_retention_status"] = hindsight_status
        saved_decision["hindsight_reference"] = retention_reference
    try:
        audit_id = saved_decision["audit_id"]
    except Exception as exc:
        logger.error("decision_audit_persist_failed exception_class=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Decision audit information is unavailable.") from exc

    result = {
        "status": "recorded",
        "decision": record.decision,
        "hindsight_status": saved_decision.get("hindsight_retention_status", "pending"),
        "audit_id": audit_id,
        "timestamp": saved_decision["timestamp"],
        "assessment_id": record.assessment_id,
        "created": created,
        "policy_result": policy_result,
        "guardrail": guardrail,
        "safety_boundary": "No autonomous execution of trades, hedges, transfers, or payments. Human approval required.",
    }
    logger.info("decision_response_returned audit_id=%s", audit_id)
    return result


@app.post("/api/actions/simulate")
def simulate_action(payload: SimulatedActionRequest) -> dict[str, Any]:
    assessment = portfolio_data.get_assessment(payload.assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    decision = assessment.get("human_decision")
    if not decision:
        raise HTTPException(status_code=409, detail="Submit a human decision before simulating an action.")
    if decision.get("decision") != "APPROVE":
        raise HTTPException(status_code=409, detail="A simulated protective action requires an APPROVE decision.")
    if assessment.get("guardrail", {}).get("manual_override_required"):
        raise HTTPException(status_code=409, detail="The guardrail requires manual override; simulation is blocked.")

    action = {
        "action_id": f"ARB-{uuid4().hex[:8].upper()}",
        "assessment_id": payload.assessment_id,
        "action": payload.action,
        "currency_pair": assessment.get("market", {}).get("currency_pair"),
        "status": "simulated_completed",
        "simulation_only": True,
        "outcome": "Simulation recorded. Protected amount was not calculated by the risk model.",
        "protected_amount": None,
        "protected_amount_status": "not_calculated",
        "hindsight_retention_status": "pending",
    }
    try:
        saved_action, created = portfolio_data.record_simulated_action(payload.assessment_id, action)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Assessment not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        return saved_action

    retention_status = "retained"
    retention_reference = None
    try:
        retention_result = hindsight_memory_service.retain_memory(
            {
                "event_type": "completed_treasury_cycle",
                "assessment": assessment,
                "human_decision": decision,
                "simulated_action": saved_action,
                "outcome": saved_action["outcome"],
            },
            context="Completed simulated treasury action and outcome",
            tags=["project-arbitrage", "simulated-action", "treasury-outcome"],
            metadata={"assessment_id": payload.assessment_id, "action_id": saved_action["action_id"]},
            live_mode=True,
        )
        retention_reference = _retention_reference(retention_result)
    except Exception as exc:
        logger.error("simulated_action_hindsight_retention_failed exception_class=%s", type(exc).__name__)
        retention_status = "unavailable"
    portfolio_data.update_action_retention(payload.assessment_id, retention_status, retention_reference)
    saved_action["hindsight_retention_status"] = retention_status
    saved_action["hindsight_reference"] = retention_reference
    return saved_action


@app.get("/api/audit")
def audit() -> list[dict[str, Any]]:
    return portfolio_data.list_audit_events()
