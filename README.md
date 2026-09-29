# Project Arbitrage

Project Arbitrage is a treasury decision-support application. It fetches current FX reference rates from Frankfurter (ECB reference data), combines them with portfolio exposures and policy thresholds entered by the user, calculates risk locally, calls official Vectorize Hindsight for memory context, and calls Groq for reasoning. It has no trading, hedging, payment, or transfer execution capability.

## Data provenance and persistence

- Market data: Frankfurter's public ECB reference-rate API. The backend requests a dated time series and calculates the latest published business-day percentage change. The UI shows the provider, published date, and retrieval timestamp. No market API key is required.
- Exposures and policies: there is no external treasury feed configured. Users enter the actual values in the dashboard; the backend validates and stores them in SQLite at `backend/data/project_arbitrage.sqlite3` (or `PORTFOLIO_DATABASE_PATH`). Monetary amounts and policy thresholds are stored as decimal text.
- Risk: calculated from the live FX change, persisted exposure inputs, and configured policy thresholds. Each assessment returns the formula and component inputs, including normalized policy pressure. Missing inputs block assessment rather than substituting sample values.
- Historical context and assessment/decision retention: official Hindsight Cloud. Previously seeded records tagged `synthetic` are excluded from recall results; the application does not write synthetic memories.
- Reasoning: Groq's configured model. Live API routes reject mock mode rather than displaying mock output.
- Audit and assessment snapshots: SQLite in the same database. `/api/audit` reads persisted application events; legacy JSONL demo audit records are not used.

The decision flow is: current market retrieval -> saved exposures and policies -> risk calculation -> policy checks -> historical-market guardrails -> official Hindsight recall -> Groq reasoning -> human decision -> SQLite audit persistence -> official Hindsight retention. A decision is accepted only for a server-stored assessment ID; approvals that violate an escalation policy or manual-override guardrail are rejected. The decision remains in the local audit history if Hindsight retention is unavailable, and its retention status is recorded.

## Safety boundary

The application is advisory only. Human approval records a decision and its rationale; it does not execute any financial action. CORS is restricted to `FRONTEND_ORIGIN`.

## Configuration

Keep provider credentials in the ignored backend `.env` file. Never put secrets in frontend configuration.

```env
GROQ_API_KEY=<secret set locally>
HINDSIGHT_API_KEY=<secret set locally>
GROQ_MODEL=openai/gpt-oss-120b
HINDSIGHT_API_URL=https://api.hindsight.vectorize.io
HINDSIGHT_BANK_ID=project-arbitrage
USE_MOCK_AI=false
MARKET_DATA_API_URL=https://api.frankfurter.dev/v1
MARKET_BASE_CURRENCY=USD
MARKET_QUOTE_CURRENCY=INR
FRONTEND_ORIGIN=http://127.0.0.1:8001
PORTFOLIO_DATABASE_PATH=backend/data/project_arbitrage.sqlite3
```

Do not replace the placeholder notation above with a real credential in this tracked file. The actual `.env` remains local and ignored.

## API endpoints

- `GET /api/health` - safe provider configuration state and allowed frontend origin.
- `GET /api/dashboard` - fetches a fresh live market snapshot and returns portfolio/policy counts.
- `GET /api/exposures` - persisted user-entered exposures.
- `POST /api/exposures` - validate and persist a user-entered exposure.
- `GET /api/policies` - persisted user-entered policies.
- `POST /api/policies` - validate and persist a user-entered threshold.
- `GET /api/memories` - official Hindsight recall, excluding synthetic-tagged records.
- `POST /api/assess` - takes an optional assessment ID; market and portfolio facts are fetched server-side.
- `POST /api/decision` - validates a decision linked to a persisted assessment, rechecks policy/guardrail results, retains to Hindsight, then stores the audit event.
- `GET /api/audit` - persistent audit events created by this application.

## Run locally

From `D:\project-arbitrage`, use separate VS Code terminals.

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

Frontend:

```powershell
.\.venv\Scripts\python.exe -m http.server 8001 --bind 127.0.0.1 --directory frontend
```

Open `http://127.0.0.1:8001`. Enter actual exposures and policy thresholds before requesting an assessment. Run tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
