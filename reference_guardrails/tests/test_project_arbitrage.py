import unittest

from project_arbitrage.memory_layer import HindsightMemory
from project_arbitrage.hindsight_engine import PRECEDENT_SHATTERED_STATE
from project_arbitrage.treasury_core import (
    GroqInferenceConfig,
    GroqInferenceHook,
    LiveShockData,
    TreasuryArbitrageAgent,
)


class ProjectArbitrageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = TreasuryArbitrageAgent()
        self.agent.ingest_demo_timeline()
        self.shock = LiveShockData(
            day=181,
            event_name="sudden-interest-rate-cut-and-euro-crash",
            signal_text="Massive sudden interest rate cut triggers a currency crash and Euro repricing.",
            currency="EUR",
            currency_move=-0.32,
            interest_rate_move_bps=-125,
            notional_at_risk_usd=420_000,
        )

    def test_four_sessions_commit_typed_memory(self) -> None:
        self.assertEqual(self.agent.memory.node_count, 5)
        self.assertEqual(
            [item.kind for item in self.agent.memory.observations],
            [
                "risk_preference",
                "market_trauma",
                "corporate_balance",
                "corporate_balance",
                "risk_preference",
            ],
        )

    def test_duplicate_observations_are_deduplicated(self) -> None:
        memory = HindsightMemory()
        first = memory.commit_market_trauma(
            day=45,
            session_id="s",
            central_bank_statement="Euro repricing after emergency policy guidance",
            shock_label="euro-currency-drop",
            currency="EUR",
            trajectory_30d=-0.18,
            trajectory_60d=-0.12,
            trajectory_90d=-0.07,
        )
        second = memory.commit_market_trauma(
            day=45,
            session_id="another-session",
            central_bank_statement="Euro repricing after emergency policy guidance",
            shock_label="euro-currency-drop",
            currency="EUR",
            trajectory_30d=-0.18,
            trajectory_60d=-0.12,
            trajectory_90d=-0.07,
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(memory.node_count, 1)

    def test_hindsight_saves_the_expected_loss(self) -> None:
        baseline = self.agent.evaluate_without_hindsight(self.shock)
        hindsight = self.agent.evaluate_with_hindsight(self.shock)
        self.assertEqual(baseline.mitigated_loss_usd, 0)
        self.assertEqual(hindsight.mitigated_loss_usd, 420_000)
        self.assertIn("Swept 8M EUR to USD yield accounts", hindsight.action_taken)
        self.assertEqual(
            hindsight.referenced_observations,
            ("obs-002", "obs-004", "obs-005"),
        )
        self.assertFalse(hindsight.transaction_frozen)
        self.assertIn(
            "[SECURITY LAYER] Precedent Variance Index Analysis: Active",
            hindsight.telemetry_lines,
        )
        self.assertIn(
            "[COMPLIANCE LAYER] Cross-Session Multi-Asset Hedging Verification Sequence Complete.",
            hindsight.telemetry_lines,
        )

    def test_temporal_importance_prefers_fresh_policy_over_old_trauma(self) -> None:
        weights = {
            weight.observation_id: weight
            for weight in self.agent.calculate_temporal_node_weights()
        }
        self.assertGreater(weights["obs-005"].importance, weights["obs-002"].importance)
        self.assertEqual(weights["obs-005"].kind, "risk_preference")

    def test_black_swan_shatters_precedent_and_freezes_transaction(self) -> None:
        black_swan = LiveShockData(
            day=181,
            event_name="unremembered-currency-collapse",
            signal_text="Unremembered currency collapse exceeds every prior trauma.",
            currency="EUR",
            currency_move=-0.40,
            interest_rate_move_bps=-300,
            notional_at_risk_usd=2_000_000,
        )
        analysis = self.agent.detect_precedent_shatter_event(black_swan)
        decision = self.agent.evaluate_with_hindsight(black_swan)
        self.assertTrue(analysis.is_black_swan)
        self.assertGreater(analysis.variance_index, 2.5)
        self.assertEqual(decision.system_state, PRECEDENT_SHATTERED_STATE)
        self.assertTrue(decision.transaction_frozen)
        self.assertEqual(decision.mitigated_loss_usd, 0)
        self.assertIn("Manual C-Suite override", decision.action_taken)

    def test_groq_hook_is_offline_by_default_and_injectable(self) -> None:
        hook = GroqInferenceHook()
        response = hook.complete(
            system_prompt="You are a treasury analyst.",
            user_prompt="Assess the shock.",
        )
        self.assertIn("SIMULATED_GROQ_RESPONSE", response)

        requests = []

        def transport(request):
            requests.append(request)
            return {"choices": [{"message": {"content": "transported result"}}]}

        enabled_hook = GroqInferenceHook(
            GroqInferenceConfig(enabled=True),
            transport=transport,
        )
        self.assertEqual(
            enabled_hook.complete(
                system_prompt="You are a treasury analyst.",
                user_prompt="Assess the shock.",
            ),
            "transported result",
        )
        self.assertEqual(requests[0]["model"], "qwen/qwen3-32b")


if __name__ == "__main__":
    unittest.main()