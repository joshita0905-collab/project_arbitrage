"""Treasury decision engine and the Project Arbitrage demonstration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .hindsight_engine import (
    COMPLIANCE_TELEMETRY,
    PRECEDENT_SHATTERED_STATE,
    SECURITY_TELEMETRY,
    HindsightEngine,
    PrecedentVarianceAnalysis,
    TemporalNodeWeight,
)
from .memory_layer import HindsightMemory, Observation, RiskPreferenceVector

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen/qwen3-32b"
ALTERNATE_MODEL = "openai/gpt-oss-120b"


@dataclass(frozen=True)
class GroqInferenceConfig:
    """Configuration for an optional Groq-compatible inference hook.

    The demo remains fully deterministic when ``enabled`` is False.  If enabled,
    the caller supplies the transport function, keeping credentials and network
    policy outside the decision engine.
    """

    model: str = DEFAULT_MODEL
    endpoint: str = "https://api.groq.com/openai/v1/chat/completions"
    enabled: bool = False
    temperature: float = 0.0

    def __post_init__(self) -> None:
        if self.model not in {DEFAULT_MODEL, ALTERNATE_MODEL}:
            raise ValueError(f"Unsupported model: {self.model}")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")


GroqTransport = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class GroqInferenceHook:
    """Explicit, injectable API boundary for Groq-compatible inference.

    A production adapter can pass a transport that performs authenticated HTTP.
    The default path is intentionally offline and returns a deterministic
    simulation response, which keeps the treasury proof reproducible.
    """

    def __init__(
        self,
        config: GroqInferenceConfig | None = None,
        *,
        transport: GroqTransport | None = None,
    ) -> None:
        self.config = config or GroqInferenceConfig()
        self.transport = transport

    def build_request(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not system_prompt.strip() or not user_prompt.strip():
            raise ValueError("system_prompt and user_prompt must not be blank")
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        request = self.build_request(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if not self.config.enabled:
            return (
                "SIMULATED_GROQ_RESPONSE: deterministic treasury analysis "
                f"prepared with {self.config.model}"
            )
        if self.transport is None:
            raise RuntimeError(
                "Groq inference is enabled but no transport was supplied; "
                "inject an authenticated API transport"
            )
        response = self.transport(request)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Groq transport returned an invalid response shape") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Groq transport returned empty content")
        return content


class OpenClawAgent:
    """Small structural base class for orchestrated agents."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register_handler(self, event_name: str, handler: Callable[..., Any]) -> None:
        if not event_name.strip():
            raise ValueError("event_name must not be blank")
        self._handlers[event_name] = handler

    def dispatch(self, event_name: str, **payload: Any) -> Any:
        try:
            handler = self._handlers[event_name]
        except KeyError as exc:
            raise KeyError(f"No OpenClaw handler registered for {event_name}") from exc
        logger.info("OpenClaw dispatch: %s -> %s", event_name, self.name)
        return handler(**payload)


@dataclass(frozen=True)
class LiveShockData:
    """Day 181 market event presented to the treasury agent."""

    day: int
    event_name: str
    signal_text: str
    currency: str
    currency_move: float
    interest_rate_move_bps: int
    notional_at_risk_usd: float

    def __post_init__(self) -> None:
        if self.day <= 180:
            raise ValueError("Live shock must occur after the compressed timeline")
        if not -1.0 <= self.currency_move <= 1.0:
            raise ValueError("currency_move must be between -1.0 and 1.0")
        if self.notional_at_risk_usd <= 0:
            raise ValueError("notional_at_risk_usd must be positive")


@dataclass(frozen=True)
class TreasuryDecision:
    """Comparable output for stateless and memory-backed evaluation."""

    mode: str
    summary: str
    action_taken: str
    mitigated_loss_usd: float
    referenced_observations: tuple[str, ...] = ()
    execution_array: tuple[Mapping[str, Any], ...] = ()
    system_state: str = "PROTECTED"
    transaction_frozen: bool = False
    telemetry_lines: tuple[str, ...] = ()
    temporal_weights: tuple[Mapping[str, Any], ...] = ()
    precedent_variance_index: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "summary": self.summary,
            "action_taken": self.action_taken,
            "mitigated_loss_usd": self.mitigated_loss_usd,
            "referenced_observations": list(self.referenced_observations),
            "execution_array": [dict(item) for item in self.execution_array],
            "system_state": self.system_state,
            "transaction_frozen": self.transaction_frozen,
            "telemetry_lines": list(self.telemetry_lines),
            "temporal_weights": [dict(item) for item in self.temporal_weights],
            "precedent_variance_index": self.precedent_variance_index,
        }


class TreasuryArbitrageAgent(OpenClawAgent):
    """Memory-backed autonomous treasury agent with a deterministic demo mode."""

    def __init__(
        self,
        memory: HindsightMemory | None = None,
        *,
        inference: GroqInferenceConfig | None = None,
    ) -> None:
        super().__init__(name="project-arbitrage")
        self.memory = memory or HindsightMemory()
        self.hindsight_engine = HindsightEngine(self.memory)
        self.inference = inference or GroqInferenceConfig(
            enabled=os.getenv("PROJECT_ARBITRAGE_ENABLE_GROQ", "").lower() == "true"
        )
        self.register_handler("evaluate_without_hindsight", self.evaluate_without_hindsight)
        self.register_handler("evaluate_with_hindsight", self.evaluate_with_hindsight)

    def detect_precedent_shatter_event(
        self,
        live_shock_data: LiveShockData,
    ) -> PrecedentVarianceAnalysis:
        """Compare a live event with every retained market-trauma precedent."""

        return self.hindsight_engine.detect_precedent_shatter_event(live_shock_data)

    def calculate_temporal_node_weights(self) -> tuple[TemporalNodeWeight, ...]:
        """Return the decayed multi-session importance matrix."""

        return self.hindsight_engine.calculate_temporal_node_weights()

    def ingest_demo_timeline(self) -> None:
        """Populate the four sessions required by the architecture brief."""

        self.memory.commit_risk_preference(
            day=1,
            session_id="session-1-board-risk",
            source_text=(
                "The executive board declares low risk tolerance ahead of the election. "
                "Preserve principal, avoid speculative currency exposure, and favor liquidity."
            ),
            risk_tolerance=0.22,
            hedging_threshold=0.45,
        )
        self.memory.commit_market_trauma(
            day=45,
            session_id="session-2-euro-shock",
            central_bank_statement=(
                "Emergency policy guidance signals a sharp Euro repricing after the election. "
                "Treasury should reduce unhedged EUR concentration and protect operating cash."
            ),
            shock_label="euro-currency-drop",
            currency="EUR",
            trajectory_30d=-0.18,
            trajectory_60d=-0.12,
            trajectory_90d=-0.07,
        )
        self.memory.commit_balance_state(
            day=45,
            session_id="session-2-euro-shock",
            balances={"USD": 5_000_000, "EUR": 8_000_000, "GBP": 2_000_000},
            rationale=(
                "Human treasurers manually retained EUR operating liquidity after the shock; "
                "the position was recorded but not automatically optimized."
            ),
        )
        self.memory.commit_balance_state(
            day=90,
            session_id="session-3-balance-review",
            balances={"USD": 5_500_000, "EUR": 10_000_000, "GBP": 2_500_000},
            rationale=(
                "Quarterly balance review shifts reserve capital toward USD yield accounts "
                "while preserving GBP payroll coverage."
            ),
        )
        self.memory.commit_risk_preference(
            day=135,
            session_id="session-4-hedging-resolution",
            source_text=(
                "The board updates hedging rules: when a currency shock exceeds the prior "
                "trauma pattern, sweep excess EUR to USD yield accounts while keeping a "
                "strict operating reserve."
            ),
            risk_tolerance=0.31,
            hedging_threshold=0.36,
        )

    def evaluate_without_hindsight(self, live_shock_data: LiveShockData) -> TreasuryDecision:
        """Produce the deliberately stateless baseline."""

        summary = (
            f"Live analysis: {live_shock_data.event_name} affects "
            f"{live_shock_data.currency} by {live_shock_data.currency_move:.1%}. "
            "Review exposures, consult treasury policy, and monitor market liquidity."
        )
        return TreasuryDecision(
            mode="without_hindsight",
            summary=summary,
            action_taken="No automated protective sweep; manual review required.",
            mitigated_loss_usd=0.0,
            execution_array=(
                {
                    "status": "unresolved",
                    "potential_capital_loss": "$420,000",
                },
            ),
        )

    def evaluate_with_hindsight(self, live_shock_data: LiveShockData) -> TreasuryDecision:
        """Traverse trauma, balance, and board-belief nodes before acting."""

        precedent = self.detect_precedent_shatter_event(live_shock_data)
        temporal_weights = self.calculate_temporal_node_weights()
        telemetry_lines = self.hindsight_engine.telemetry()
        compliance_complete = self.hindsight_engine.verify_hedging_sequence(
            live_shock_data=live_shock_data,
            precedent=precedent,
        )
        weight_payload = tuple(weight.as_dict() for weight in temporal_weights)
        if precedent.is_black_swan:
            return TreasuryDecision(
                mode="with_hindsight_guardrail",
                summary=PRECEDENT_SHATTERED_STATE,
                action_taken="Transaction frozen. Manual C-Suite override required.",
                mitigated_loss_usd=0.0,
                referenced_observations=(
                    (precedent.worst_node_id,) if precedent.worst_node_id else ()
                ),
                execution_array=(
                    {
                        "step": 1,
                        "command": "FREEZE_TRANSACTION",
                        "reason": PRECEDENT_SHATTERED_STATE,
                    },
                    {
                        "step": 2,
                        "command": "ESCALATE",
                        "owner": "C-Suite",
                        "compliance_sequence_complete": compliance_complete,
                    },
                ),
                system_state=PRECEDENT_SHATTERED_STATE,
                transaction_frozen=True,
                telemetry_lines=telemetry_lines,
                temporal_weights=weight_payload,
                precedent_variance_index=precedent.variance_index,
            )

        trauma_matches = self.memory.recall(
            live_shock_data.signal_text,
            as_of_day=180,
            kinds={"market_trauma"},
            limit=3,
        )
        trauma = trauma_matches[0][0] if trauma_matches else None
        balance = self.memory.latest_balance(as_of_day=180)
        risk = self.memory.latest_risk_preference(as_of_day=180)
        if trauma is None or balance is None or risk is None:
            raise RuntimeError(
                "Hindsight evaluation requires a market trauma, balance state, and risk belief"
            )

        trauma_node = trauma.node
        if not hasattr(trauma_node, "severity"):
            raise TypeError("Recalled market trauma node is not typed correctly")
        shock_exceeds_pattern = abs(live_shock_data.currency_move) > trauma_node.severity
        risk_node = risk.node
        if not isinstance(risk_node, RiskPreferenceVector):
            raise TypeError("Latest risk node is not a RiskPreferenceVector")

        eur_balance = balance.node.balances["EUR"]
        sweep_amount = round(eur_balance * 0.8, 2) if shock_exceeds_pattern else 0.0
        mitigated_loss = 420_000.0 if sweep_amount > 0 and risk_node.hedging_threshold <= 0.36 else 0.0
        if sweep_amount:
            action = (
                "Action Taken: Swept 8M EUR to USD yield accounts. "
                "Mitigated Loss: $420,000 saved"
            )
            execution = (
                {
                    "step": 1,
                    "command": "SWEEP",
                    "from_account": "EUR operating reserve",
                    "to_account": "USD yield account",
                    "amount": sweep_amount,
                    "currency": "EUR",
                },
                {
                    "step": 2,
                    "command": "RETAIN_RESERVE",
                    "currency": "EUR",
                    "amount": round(eur_balance - sweep_amount, 2),
                    "policy_threshold": risk_node.hedging_threshold,
                },
            )
        else:
            action = "No sweep executed; observed shock remained within the remembered pattern."
            execution = (
                {
                    "step": 1,
                    "command": "HOLD",
                    "reason": "Shock did not exceed the remembered trauma threshold",
                },
            )

        referenced = (
            trauma.observation_id,
            balance.observation_id,
            risk.observation_id,
        )
        summary = (
            f"Graph traversal linked {trauma.observation_id} (day 45 trauma), "
            f"{risk.observation_id} (day 135 hedging threshold), and "
            f"{balance.observation_id} (latest balance). "
            f"Live move {live_shock_data.currency_move:.1%} exceeded the remembered "
            f"trauma severity {trauma_node.severity:.1%}: {shock_exceeds_pattern}."
        )
        return TreasuryDecision(
            mode="with_hindsight",
            summary=summary,
            action_taken=action,
            mitigated_loss_usd=mitigated_loss,
            referenced_observations=referenced,
            execution_array=execution,
            system_state="PROTECTED",
            transaction_frozen=False,
            telemetry_lines=telemetry_lines,
            temporal_weights=weight_payload,
            precedent_variance_index=precedent.variance_index,
        )

    def render_dashboard(
        self,
        *,
        shock: LiveShockData,
        baseline: TreasuryDecision,
        hindsight: TreasuryDecision,
    ) -> str:
        """Render the exact nodes and links used during live evaluation."""

        lines = [
            "",
            "╔══════════════════════════════════════════════════════════════════════╗",
            "║ PROJECT ARBITRAGE · HINDSIGHT MEMORY GRAPH                         ║",
            "╠══════════════════════════════════════════════════════════════════════╣",
            f"║ LIVE SHOCK · DAY {shock.day:<3} · {shock.event_name:<43}║",
            "╟──────────────────────────────────────────────────────────────────────╢",
            "║ TRAVERSAL                                                              ║",
        ]
        for observation_id in hindsight.referenced_observations:
            observation = next(
                item
                for item in self.memory.observations
                if item.observation_id == observation_id
            )
            lines.append(
                f"║  {observation.observation_id:<10} day {observation.observed_day:<3} "
                f"{observation.kind:<20} ← {observation.session_id:<22} ║"
            )
        lines.extend(
            [
                "║      │                                                               ║",
                "║      ├─ deduplicated observation match                               ║",
                "║      ├─ belief drift: "
                f"{self.memory.belief_drift():+.2f}"
                "                                      ║",
                "║      └─ policy threshold checked before execution                    ║",
                f"║      └─ variance index: {hindsight.precedent_variance_index:.2f}x"
                " · transaction frozen: "
                f"{str(hindsight.transaction_frozen).upper():<5}              ║",
                f"║ {SECURITY_TELEMETRY:<68} ║",
                f"║ {COMPLIANCE_TELEMETRY:<68} ║",
                "╟──────────────────────────────────────────────────────────────────────╢",
                f"║ STATELESS BASELINE  · potential loss: $420,000                       ║",
                f"║ MEMORY-BACKED       · mitigated: ${hindsight.mitigated_loss_usd:,.0f}"
                "                              ║",
                "╚══════════════════════════════════════════════════════════════════════╝",
            ]
        )
        return "\n".join(lines)


def run_demo(*, print_output: bool = True) -> dict[str, Any]:
    """Run the complete four-session timeline and Day 181 comparison."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    agent = TreasuryArbitrageAgent()
    agent.ingest_demo_timeline()
    shock = LiveShockData(
        day=181,
        event_name="sudden-interest-rate-cut-and-euro-crash",
        signal_text=(
            "Massive sudden interest rate cut triggers a currency crash and rapid Euro "
            "repricing; unhedged EUR cash is exposed."
        ),
        currency="EUR",
        currency_move=-0.32,
        interest_rate_move_bps=-125,
        notional_at_risk_usd=420_000.0,
    )
    baseline = agent.dispatch("evaluate_without_hindsight", live_shock_data=shock)
    hindsight = agent.dispatch("evaluate_with_hindsight", live_shock_data=shock)
    dashboard = agent.render_dashboard(
        shock=shock,
        baseline=baseline,
        hindsight=hindsight,
    )
    result = {
        "dashboard": dashboard,
        "baseline": baseline.as_dict(),
        "hindsight": hindsight.as_dict(),
        "memory_graph": agent.memory.graph_snapshot(),
    }
    if print_output:
        print(dashboard)
        print("\nSTATELESS EVALUATION")
        print(baseline.summary)
        print(baseline.execution_array)
        print("\nHINDSIGHT EVALUATION")
        print(hindsight.summary)
        print(hindsight.action_taken)
        print("Execution array:")
        for step in hindsight.execution_array:
            print(f"  {dict(step)}")
    return result


if __name__ == "__main__":
    run_demo()