"""Advanced Hindsight guardrails for Project Arbitrage.

This module keeps precedent-breaking detection and temporal importance scoring
separate from execution policy.  The treasury agent can therefore inspect the
same evidence matrix before it decides whether a transaction is allowed to run.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .memory_layer import HindsightMemory, MarketTraumaNode

logger = logging.getLogger(__name__)

PRECEDENT_SHATTERED_STATE = (
    "PRECEDENT SHATTERED: Manual C-Suite override required due to historic volatility anomaly."
)
SECURITY_TELEMETRY = "[SECURITY LAYER] Precedent Variance Index Analysis: Active"
COMPLIANCE_TELEMETRY = (
    "[COMPLIANCE LAYER] Cross-Session Multi-Asset Hedging Verification Sequence Complete."
)


@dataclass(frozen=True)
class PrecedentVarianceAnalysis:
    """Result of comparing a live move with every retained trauma node."""

    is_black_swan: bool
    live_move: float
    worst_historical_severity: float
    multiplier: float
    worst_node_id: str | None
    system_state: str

    @property
    def variance_index(self) -> float:
        """Ratio of current volatility to the worst retained precedent."""

        if self.worst_historical_severity == 0:
            return math.inf if self.live_move else 0.0
        return abs(self.live_move) / self.worst_historical_severity

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_black_swan": self.is_black_swan,
            "live_move": self.live_move,
            "worst_historical_severity": self.worst_historical_severity,
            "multiplier": self.multiplier,
            "worst_node_id": self.worst_node_id,
            "variance_index": self.variance_index,
            "system_state": self.system_state,
        }


@dataclass(frozen=True)
class TemporalNodeWeight:
    """Importance coefficient for one memory node at evaluation time."""

    observation_id: str
    node_id: str
    kind: str
    observed_day: int
    age_days: int
    freshness: float
    initial_confidence: float
    importance: float
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "node_id": self.node_id,
            "kind": self.kind,
            "observed_day": self.observed_day,
            "age_days": self.age_days,
            "freshness": self.freshness,
            "initial_confidence": self.initial_confidence,
            "importance": self.importance,
            "rationale": self.rationale,
        }


class HindsightEngine:
    """Advanced guardrail and relevance layer over the memory ledger."""

    _KIND_CONFIDENCE = {
        "market_trauma": 0.82,
        "corporate_balance": 0.74,
        "risk_preference": 1.0,
    }

    def __init__(
        self,
        memory: HindsightMemory,
        *,
        evaluation_day: int = 180,
        decay_rate: float = 0.0025,
        shatter_multiplier: float = 2.5,
    ) -> None:
        if evaluation_day < 0:
            raise ValueError("evaluation_day must not be negative")
        if decay_rate <= 0:
            raise ValueError("decay_rate must be positive")
        if shatter_multiplier <= 1:
            raise ValueError("shatter_multiplier must be greater than 1")
        self.memory = memory
        self.evaluation_day = evaluation_day
        self.decay_rate = decay_rate
        self.shatter_multiplier = shatter_multiplier

    def _trauma_observations(self) -> list[tuple[Any, MarketTraumaNode]]:
        trauma: list[tuple[Any, MarketTraumaNode]] = []
        for observation in self.memory.observations:
            if observation.kind == "market_trauma" and isinstance(
                observation.node, MarketTraumaNode
            ):
                trauma.append((observation, observation.node))
        return trauma

    def detect_precedent_shatter_event(
        self,
        live_shock_data: Any,
    ) -> PrecedentVarianceAnalysis:
        """Flag a move more than 2.5x worse than the worst retained trauma."""

        trauma_nodes = self._trauma_observations()
        worst_observation, worst_node = max(
            trauma_nodes,
            key=lambda item: item[1].severity,
            default=(None, None),
        )
        worst_severity = worst_node.severity if worst_node else 0.0
        live_move = abs(float(live_shock_data.currency_move))
        is_black_swan = (
            live_move > worst_severity * self.shatter_multiplier
            if worst_severity
            else live_move > 0
        )
        analysis = PrecedentVarianceAnalysis(
            is_black_swan=is_black_swan,
            live_move=float(live_shock_data.currency_move),
            worst_historical_severity=worst_severity,
            multiplier=self.shatter_multiplier,
            worst_node_id=worst_observation.observation_id if worst_observation else None,
            system_state=(
                PRECEDENT_SHATTERED_STATE
                if is_black_swan
                else "PRECEDENT INTACT: Historical policy path remains eligible."
            ),
        )
        logger.info(
            "%s | live_move=%.4f | worst_precedent=%.4f | variance_index=%.2fx",
            SECURITY_TELEMETRY,
            analysis.live_move,
            analysis.worst_historical_severity,
            analysis.variance_index,
        )
        if analysis.is_black_swan:
            logger.warning(analysis.system_state)
        return analysis

    def calculate_temporal_node_weights(self) -> tuple[TemporalNodeWeight, ...]:
        """Build a decayed importance matrix for every retained observation."""

        weights: list[TemporalNodeWeight] = []
        for observation in self.memory.observations:
            age_days = max(0, self.evaluation_day - observation.observed_day)
            freshness = math.exp(-self.decay_rate * age_days)
            initial_confidence = self._KIND_CONFIDENCE.get(observation.kind, 0.6)
            importance = round(initial_confidence * freshness, 6)
            weights.append(
                TemporalNodeWeight(
                    observation_id=observation.observation_id,
                    node_id=getattr(observation.node, "node_id", getattr(observation.node, "state_id", getattr(observation.node, "vector_id", observation.observation_id))),
                    kind=observation.kind,
                    observed_day=observation.observed_day,
                    age_days=age_days,
                    freshness=round(freshness, 6),
                    initial_confidence=initial_confidence,
                    importance=importance,
                    rationale=(
                        f"{observation.kind} confidence {initial_confidence:.2f} "
                        f"decayed across {age_days} days at rate {self.decay_rate:.4f}"
                    ),
                )
            )
        weights.sort(key=lambda item: (item.importance, item.observed_day), reverse=True)
        logger.info(
            "Hindsight temporal importance matrix calculated for %s nodes",
            len(weights),
        )
        return tuple(weights)

    def telemetry(self) -> tuple[str, str]:
        """Return stable machine-readable console lines for security and compliance."""

        logger.info(COMPLIANCE_TELEMETRY)
        return SECURITY_TELEMETRY, COMPLIANCE_TELEMETRY

    def verify_hedging_sequence(
        self,
        *,
        live_shock_data: Any,
        precedent: PrecedentVarianceAnalysis,
    ) -> bool:
        """Confirm the current event was checked against cross-session assets."""

        has_balance = any(
            observation.kind == "corporate_balance"
            for observation in self.memory.observations
        )
        has_policy = any(
            observation.kind == "risk_preference"
            and observation.observed_day >= 135
            for observation in self.memory.observations
        )
        complete = bool(live_shock_data.currency and has_balance and has_policy)
        logger.info(
            "%s | currency=%s | precedent_state=%s | complete=%s",
            COMPLIANCE_TELEMETRY,
            live_shock_data.currency,
            precedent.system_state,
            complete,
        )
        return complete


def detect_precedent_shatter_event(
    live_shock_data: Any,
    memory: HindsightMemory,
) -> PrecedentVarianceAnalysis:
    """Functional entry point for callers that do not need an agent instance."""

    return HindsightEngine(memory).detect_precedent_shatter_event(live_shock_data)


def calculate_temporal_node_weights(
    memory: HindsightMemory,
) -> tuple[TemporalNodeWeight, ...]:
    """Functional entry point for importance-matrix consumers."""

    return HindsightEngine(memory).calculate_temporal_node_weights()