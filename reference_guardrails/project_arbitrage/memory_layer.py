"""Hindsight-style temporal memory primitives for Project Arbitrage.

The real Vectorize Hindsight product is represented here by a local, deterministic
ledger.  The ledger keeps typed observations, deduplicates repeated observations
across sessions, computes compact text vectors, and recalls evidence by semantic
overlap plus temporal proximity.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES = ("USD", "EUR", "GBP")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOP_WORDS
    )


def text_vector(text: str) -> dict[str, float]:
    """Return a normalized bag-of-words vector suitable for local similarity."""

    counts = Counter(_tokens(text))
    magnitude = math.sqrt(sum(value * value for value in counts.values()))
    if magnitude == 0:
        return {}
    return {token: count / magnitude for token, count in counts.items()}


def cosine_similarity(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    """Calculate cosine similarity for sparse vectors."""

    if not left or not right:
        return 0.0
    return sum(value * right.get(key, 0.0) for key, value in left.items())


def _fingerprint(*parts: str) -> str:
    normalized = "|".join(part.strip().lower() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class MarketTraumaNode:
    """A macro shock and its observed currency impact trajectory."""

    node_id: str
    observed_day: int
    central_bank_statement: str
    shock_label: str
    currency: str
    trajectory_30d: float
    trajectory_60d: float
    trajectory_90d: float
    source_session: str
    text_vector: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.observed_day <= 180:
            raise ValueError("Market trauma observations must be within days 0-180")
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {self.currency}")
        trajectories = (
            self.trajectory_30d,
            self.trajectory_60d,
            self.trajectory_90d,
        )
        if any(not -1.0 <= value <= 1.0 for value in trajectories):
            raise ValueError("Currency trajectories must be between -1.0 and 1.0")

    @property
    def severity(self) -> float:
        """Weight recent and projected impact into a single comparable score."""

        return min(
            1.0,
            abs(self.trajectory_30d) * 0.5
            + abs(self.trajectory_60d) * 0.3
            + abs(self.trajectory_90d) * 0.2,
        )


@dataclass(frozen=True)
class CorporateBalanceState:
    """A point-in-time treasury balance distribution across currency accounts."""

    state_id: str
    observed_day: int
    balances: Mapping[str, float]
    source_session: str
    rationale: str

    def __post_init__(self) -> None:
        if not 0 <= self.observed_day <= 180:
            raise ValueError("Balance observations must be within days 0-180")
        if set(self.balances) != set(SUPPORTED_CURRENCIES):
            raise ValueError("Balances must contain exactly USD, EUR, and GBP")
        if any(value < 0 for value in self.balances.values()):
            raise ValueError("Balances cannot be negative")

    @property
    def total_value_usd(self) -> float:
        """Return the represented balance value; conversion is intentionally explicit."""

        return sum(self.balances.values())

    def currency_share(self, currency: str) -> float:
        total = self.total_value_usd
        return 0.0 if total == 0 else self.balances[currency] / total


@dataclass(frozen=True)
class RiskPreferenceVector:
    """An executive risk tolerance belief inferred from a board text input."""

    vector_id: str
    observed_day: int
    risk_tolerance: float
    hedging_threshold: float
    source_text: str
    source_session: str
    text_vector: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.observed_day <= 180:
            raise ValueError("Risk observations must be within days 0-180")
        for name, value in (
            ("risk_tolerance", self.risk_tolerance),
            ("hedging_threshold", self.hedging_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0")


@dataclass(frozen=True)
class Observation:
    """An immutable ledger envelope around any typed Hindsight memory node."""

    observation_id: str
    observed_day: int
    session_id: str
    kind: str
    content: str
    fingerprint: str
    node: MarketTraumaNode | CorporateBalanceState | RiskPreferenceVector
    created_on: date


class HindsightMemory:
    """A bounded, deduplicated observation ledger with lightweight recall."""

    def __init__(
        self,
        *,
        timeline_days: int = 180,
        anchor_date: date = date(2026, 1, 1),
    ) -> None:
        if timeline_days < 1:
            raise ValueError("timeline_days must be positive")
        self.timeline_days = timeline_days
        self.anchor_date = anchor_date
        self._observations: list[Observation] = []
        self._fingerprints: set[str] = set()
        self._belief_history: list[RiskPreferenceVector] = []

    @property
    def observations(self) -> tuple[Observation, ...]:
        return tuple(self._observations)

    @property
    def node_count(self) -> int:
        return len(self._observations)

    def _commit(
        self,
        *,
        day: int,
        session_id: str,
        kind: str,
        content: str,
        node: MarketTraumaNode | CorporateBalanceState | RiskPreferenceVector,
        fingerprint: str,
    ) -> Observation | None:
        if not 0 <= day <= self.timeline_days:
            raise ValueError(f"day must be between 0 and {self.timeline_days}")
        if fingerprint in self._fingerprints:
            logger.info("Skipped duplicate Hindsight observation %s", fingerprint)
            return None
        observation = Observation(
            observation_id=f"obs-{len(self._observations) + 1:03d}",
            observed_day=day,
            session_id=session_id,
            kind=kind,
            content=content,
            fingerprint=fingerprint,
            node=node,
            created_on=self.anchor_date + timedelta(days=day),
        )
        self._observations.append(observation)
        self._fingerprints.add(fingerprint)
        if isinstance(node, RiskPreferenceVector):
            self._belief_history.append(node)
        logger.info(
            "Committed Hindsight observation %s (%s, day %s)",
            observation.observation_id,
            kind,
            day,
        )
        return observation

    def commit_market_trauma(
        self,
        *,
        day: int,
        session_id: str,
        central_bank_statement: str,
        shock_label: str,
        currency: str,
        trajectory_30d: float,
        trajectory_60d: float,
        trajectory_90d: float,
    ) -> Observation | None:
        """Commit a market trauma, or return None for an exact duplicate."""

        node_id = f"trauma-{day}-{currency.lower()}"
        node = MarketTraumaNode(
            node_id=node_id,
            observed_day=day,
            central_bank_statement=central_bank_statement,
            shock_label=shock_label,
            currency=currency,
            trajectory_30d=trajectory_30d,
            trajectory_60d=trajectory_60d,
            trajectory_90d=trajectory_90d,
            source_session=session_id,
            text_vector=text_vector(central_bank_statement),
        )
        return self._commit(
            day=day,
            session_id=session_id,
            kind="market_trauma",
            content=central_bank_statement,
            node=node,
            fingerprint=_fingerprint(
                "market_trauma",
                shock_label,
                currency,
                central_bank_statement,
            ),
        )

    def commit_balance_state(
        self,
        *,
        day: int,
        session_id: str,
        balances: Mapping[str, float],
        rationale: str,
    ) -> Observation | None:
        """Commit a currency balance state with a stable value fingerprint."""

        normalized_balances = {
            currency: round(float(balances[currency]), 2)
            for currency in SUPPORTED_CURRENCIES
        }
        node = CorporateBalanceState(
            state_id=f"balance-{day}",
            observed_day=day,
            balances=normalized_balances,
            source_session=session_id,
            rationale=rationale,
        )
        balance_signature = ",".join(
            f"{currency}:{normalized_balances[currency]:.2f}"
            for currency in SUPPORTED_CURRENCIES
        )
        return self._commit(
            day=day,
            session_id=session_id,
            kind="corporate_balance",
            content=rationale,
            node=node,
            fingerprint=_fingerprint("corporate_balance", str(day), balance_signature),
        )

    def commit_risk_preference(
        self,
        *,
        day: int,
        session_id: str,
        source_text: str,
        risk_tolerance: float,
        hedging_threshold: float,
    ) -> Observation | None:
        """Commit an executive belief vector and preserve its drift history."""

        node = RiskPreferenceVector(
            vector_id=f"risk-{day}",
            observed_day=day,
            risk_tolerance=round(risk_tolerance, 4),
            hedging_threshold=round(hedging_threshold, 4),
            source_text=source_text,
            source_session=session_id,
            text_vector=text_vector(source_text),
        )
        return self._commit(
            day=day,
            session_id=session_id,
            kind="risk_preference",
            content=source_text,
            node=node,
            fingerprint=_fingerprint("risk_preference", source_text),
        )

    def recall(
        self,
        query: str,
        *,
        as_of_day: int,
        kinds: Iterable[str] | None = None,
        limit: int = 5,
    ) -> list[tuple[Observation, float]]:
        """Rank relevant memories by text overlap and temporal proximity."""

        if limit < 1:
            raise ValueError("limit must be positive")
        allowed_kinds = set(kinds) if kinds is not None else None
        query_vector = text_vector(query)
        ranked: list[tuple[Observation, float]] = []
        for observation in self._observations:
            if allowed_kinds is not None and observation.kind not in allowed_kinds:
                continue
            age = abs(as_of_day - observation.observed_day)
            temporal_score = max(0.0, 1.0 - min(age, self.timeline_days) / self.timeline_days)
            semantic_score = cosine_similarity(query_vector, text_vector(observation.content))
            score = semantic_score * 0.75 + temporal_score * 0.25
            ranked.append((observation, score))
        ranked.sort(key=lambda item: (item[1], item[0].observed_day), reverse=True)
        return ranked[:limit]

    def latest_balance(self, *, as_of_day: int) -> Observation | None:
        states = [
            observation
            for observation in self._observations
            if observation.kind == "corporate_balance"
            and observation.observed_day <= as_of_day
        ]
        return max(states, key=lambda item: item.observed_day, default=None)

    def latest_risk_preference(self, *, as_of_day: int) -> Observation | None:
        states = [
            observation
            for observation in self._observations
            if observation.kind == "risk_preference"
            and observation.observed_day <= as_of_day
        ]
        return max(states, key=lambda item: item.observed_day, default=None)

    def belief_drift(self) -> float:
        """Return absolute risk-tolerance drift from the first to latest belief."""

        if len(self._belief_history) < 2:
            return 0.0
        return self._belief_history[-1].risk_tolerance - self._belief_history[0].risk_tolerance

    def graph_snapshot(self) -> list[dict[str, Any]]:
        """Return JSON-friendly node data for a terminal or API visualization."""

        snapshot: list[dict[str, Any]] = []
        for observation in self._observations:
            snapshot.append(
                {
                    "observation_id": observation.observation_id,
                    "day": observation.observed_day,
                    "session": observation.session_id,
                    "kind": observation.kind,
                    "fingerprint": observation.fingerprint,
                    "node": asdict(observation.node),
                }
            )
        return snapshot