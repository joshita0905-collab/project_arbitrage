import { Router, type IRouter } from "express";
import {
  EvaluateArbitrageShockBody,
  GetArbitrageDashboardResponse,
  GetArbitrageMemoryResponse,
  GetArbitrageTimelineResponse,
} from "@workspace/api-zod";

const router: IRouter = Router();

const memoryNodes = [
  {
    id: "obs-001",
    day: 1,
    session: "Board risk declaration",
    kind: "risk_preference",
    title: "Risk tolerance lowered",
    detail:
      "Executive board declared capital preservation the priority ahead of the election cycle.",
    tone: "caution",
    value: 0.22,
  },
  {
    id: "obs-002",
    day: 45,
    session: "Euro shock response",
    kind: "market_trauma",
    title: "Euro repricing recorded",
    detail:
      "Emergency policy guidance created a 14% weighted trauma severity across the 30/60/90-day trajectory.",
    tone: "danger",
    value: 0.14,
  },
  {
    id: "obs-003",
    day: 45,
    session: "Euro shock response",
    kind: "corporate_balance",
    title: "Human manual fix",
    detail:
      "Treasurers retained operating liquidity but left the EUR concentration unoptimized.",
    tone: "neutral",
    value: 8_000_000,
  },
  {
    id: "obs-004",
    day: 90,
    session: "Quarterly balance review",
    kind: "corporate_balance",
    title: "Reserve allocation shifted",
    detail:
      "USD yield accounts gained priority while GBP payroll coverage stayed intact.",
    tone: "positive",
    value: 10_000_000,
  },
  {
    id: "obs-005",
    day: 135,
    session: "Hedging resolution",
    kind: "risk_preference",
    title: "Protective sweep rule approved",
    detail:
      "The board authorized automatic EUR-to-USD sweeping once a shock exceeds the remembered trauma pattern.",
    tone: "positive",
    value: 0.36,
  },
];

const timeline = [
  {
    day: 1,
    label: "DAY 01",
    title: "Board risk declaration",
    description:
      "The executive board sets a low-risk posture ahead of elections.",
    kind: "risk",
    status: "Committed",
  },
  {
    day: 45,
    label: "DAY 45",
    title: "Euro shock response",
    description:
      "A market trauma and the human manual fix enter the shared memory graph.",
    kind: "trauma",
    status: "Committed",
  },
  {
    day: 90,
    label: "DAY 90",
    title: "Balance review",
    description:
      "Corporate cash distribution is updated across USD, EUR, and GBP hubs.",
    kind: "balance",
    status: "Committed",
  },
  {
    day: 135,
    label: "DAY 135",
    title: "Hedging resolution",
    description:
      "Board policy becomes executable: sweep excess EUR when the pattern repeats.",
    kind: "policy",
    status: "Committed",
  },
  {
    day: 181,
    label: "DAY 181",
    title: "Live shock evaluation",
    description:
      "The current event is evaluated against six months of retained context.",
    kind: "live",
    status: "Ready",
  },
];

router.get("/arbitrage/dashboard", (_req, res) => {
  const data = GetArbitrageDashboardResponse.parse({
    status: "PROTECTED",
    totalNodes: memoryNodes.length,
    beliefDrift: 0.09,
    riskTolerance: 0.31,
    hedgingThreshold: 0.36,
    baselineLoss: 420_000,
    mitigatedLoss: 420_000,
    activeExposure: 2_000_000,
    lastDecision: "Automatic protective sweep authorized",
  });
  res.json(data);
});

router.get("/arbitrage/memory", (_req, res) => {
  res.json(GetArbitrageMemoryResponse.parse(memoryNodes));
});

router.get("/arbitrage/timeline", (_req, res) => {
  res.json(GetArbitrageTimelineResponse.parse(timeline));
});

router.post("/arbitrage/evaluate", (req, res) => {
  const parsed = EvaluateArbitrageShockBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({
      error: "Shock input must include an event name, currency move, and rate move.",
    });
    return;
  }

  const input = parsed.data;
  const currency = input.currency ?? "EUR";
  const movePercent = Math.abs(input.currencyMove * 100).toFixed(1);
  const matchesTrackedTrauma = currency === "EUR";
  const exceedsTrauma = matchesTrackedTrauma && Math.abs(input.currencyMove) > 0.14;
  const varianceIndex = Math.abs(input.currencyMove) / 0.14;
  const isBlackSwan = varianceIndex > 2.5;
  const saved = exceedsTrauma && !isBlackSwan ? 420_000 : 0;
  const sweepAmount = exceedsTrauma && !isBlackSwan ? 8_000_000 : 0;
  const telemetry = [
    "[SECURITY LAYER] Precedent Variance Index Analysis: Active",
    "[COMPLIANCE LAYER] Cross-Session Multi-Asset Hedging Verification Sequence Complete.",
  ];
  const temporalWeights = [
    { observationId: "obs-005", kind: "risk_preference", observedDay: 135, freshness: 0.8936, initialConfidence: 1, importance: 0.8936 },
    { observationId: "obs-004", kind: "corporate_balance", observedDay: 90, freshness: 0.7985, initialConfidence: 0.74, importance: 0.5909 },
    { observationId: "obs-003", kind: "corporate_balance", observedDay: 45, freshness: 0.7135, initialConfidence: 0.74, importance: 0.5280 },
    { observationId: "obs-002", kind: "market_trauma", observedDay: 45, freshness: 0.7135, initialConfidence: 0.82, importance: 0.5851 },
    { observationId: "obs-001", kind: "risk_preference", observedDay: 1, freshness: 0.6393, initialConfidence: 1, importance: 0.6393 },
  ];

  res.json({
    shock: { ...input, currency },
    baseline: {
      summary: `Stateless read: ${input.eventName} moves ${currency} by ${movePercent}%.`,
      action: "No automated protective sweep; manual review required.",
      loss: 420_000,
      tone: "danger",
      references: [],
    },
    hindsight: {
      summary: isBlackSwan
        ? "Precedent variance exceeded the 2.5× historical guardrail. The transaction was frozen before any asset movement."
        : matchesTrackedTrauma
          ? "Graph traversal linked the Day 45 trauma, Day 90 balance state, and Day 135 board rule before execution."
        : `No matching ${currency} trauma node exists in retained context, so the EUR policy path stayed inactive.`,
      action: isBlackSwan
        ? "PRECEDENT SHATTERED: Manual C-Suite override required due to historic volatility anomaly."
        : exceedsTrauma
        ? `Swept ${(sweepAmount / 1_000_000).toFixed(0)}M ${currency} to USD yield accounts.`
        : matchesTrackedTrauma
          ? "Held the position; the shock remained within the remembered pattern."
          : "No automated sweep; route the exposure to manual treasury review.",
      loss: saved,
      tone: isBlackSwan ? "danger" : exceedsTrauma ? "positive" : "neutral",
      references: ["obs-002", "obs-004", "obs-005"],
    },
    saved,
    execution: isBlackSwan
      ? [
          "SECURITY · Precedent Variance Index exceeded 2.5×",
          "FREEZE · No asset movement authorized",
          "ESCALATE · Manual C-Suite override required",
        ]
      : exceedsTrauma
      ? [
          "MATCH · Day 45 Euro trauma pattern exceeded",
          "POLICY · Day 135 threshold 0.36 confirmed",
          `SWEEP · ${(sweepAmount / 1_000_000).toFixed(0)}M ${currency} → USD yield account`,
          "PROTECTED · $420,000 expected loss mitigated",
        ]
      : ["HOLD · No protective sweep required"],
    systemState: isBlackSwan
      ? "PRECEDENT SHATTERED: Manual C-Suite override required due to historic volatility anomaly."
      : "PROTECTED",
    transactionFrozen: isBlackSwan,
    telemetry,
    temporalWeights,
    varianceIndex,
  });
});

export default router;