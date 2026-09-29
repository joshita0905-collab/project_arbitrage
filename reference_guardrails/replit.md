# Project Arbitrage

An auditable treasury-agent simulation that compares stateless decisions with a
Hindsight-style temporal memory graph.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string
- `python -m project_arbitrage.treasury_core` — run the treasury memory demo
- `python -m unittest discover -s tests -v` — run the Python unit tests

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `project_arbitrage/memory_layer.py` — typed Hindsight-style memory ledger
- `project_arbitrage/treasury_core.py` — OpenClaw-shaped agent and Day 181 prover
- `tests/test_project_arbitrage.py` — deterministic regression tests
- `README.md` — demo and architecture notes

## Architecture decisions

- The Hindsight layer is local and deterministic by default so the comparison can
  be replayed without an external service or credential.
- Observations are immutable typed envelopes and are deduplicated by a stable
  content fingerprint across session boundaries.
- The stateless and memory-backed evaluators share the same shock input so the
  mitigation delta is attributable to retained context rather than prompt drift.
- Precedent-shatter detection is a hard transaction guardrail: an event above
  2.5x the worst retained trauma freezes execution instead of extrapolating an
  old policy into a black-swan event.
- Temporal importance uses both node-type confidence and exponential age decay,
  so fresh policy resolutions outrank stale market context without deleting it.

## Product

Project Arbitrage demonstrates how a treasury agent can connect prior market
traumas, balance history, and executive risk preferences before executing a
protective currency sweep.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
