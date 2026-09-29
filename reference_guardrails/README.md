# Project Arbitrage

Project Arbitrage is a deterministic, auditable simulation of an autonomous
corporate treasury agent. It models the Vectorize Hindsight idea as a typed,
deduplicated memory ledger and compares a stateless response with a
memory-backed protective sweep after a Day 181 Euro shock.

The advanced guardrail layer adds two execution controls: a precedent-shatter
interceptor freezes any move above 2.5x the worst retained market trauma, and a
temporal importance matrix decays older memories while giving fresh policy
resolutions stronger initial confidence.

## Run the demo

```bash
python -m project_arbitrage.treasury_core
```

The demo prints:

- the four historical sessions across a compressed 180-day timeline,
- the exact observations traversed during live evaluation,
- the stateless `$420,000` potential-loss signature,
- the memory-backed `8M EUR → USD` protective sweep and `$420,000` mitigation.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Architecture

- `project_arbitrage/memory_layer.py` contains typed market-trauma,
  corporate-balance, and risk-preference nodes plus sparse-vector recall,
  cross-session deduplication, belief drift, and JSON-friendly snapshots.
- `project_arbitrage/hindsight_engine.py` contains precedent variance analysis,
  black-swan transaction freezes, temporal node weighting, and security /
  compliance telemetry.
- `project_arbitrage/treasury_core.py` contains the OpenClaw-shaped agent
  orchestrator, Groq-compatible inference configuration, the timeline
  simulator, the before/after prover, and the guardrail integration.
- The inference hook is disabled by default so the hackathon demo is
  reproducible without credentials. Set
  `PROJECT_ARBITRAGE_ENABLE_GROQ=true` only when an application transport is
  supplied around the `GroqInferenceConfig` boundary.

## Guardrail behavior

For a normal tracked Euro shock, the engine preserves the existing behavior:

```text
Action Taken: Swept 8M EUR to USD yield accounts. Mitigated Loss: $420,000 saved
```

For a shock more than 2.5x the worst retained trauma, it returns:

```text
PRECEDENT SHATTERED: Manual C-Suite override required due to historic volatility anomaly.
```

The transaction is frozen, no loss mitigation is claimed, and the console emits:

```text
[SECURITY LAYER] Precedent Variance Index Analysis: Active
[COMPLIANCE LAYER] Cross-Session Multi-Asset Hedging Verification Sequence Complete.
```