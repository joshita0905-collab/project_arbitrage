import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  Bell,
  BrainCircuit,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Crosshair,
  Database,
  Gauge,
  Globe2,
  Layers3,
  Menu,
  PanelLeftClose,
  Play,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  TrendingDown,
  X,
  Zap,
} from 'lucide-react';
import {
  getGetArbitrageDashboardQueryKey,
  getGetArbitrageMemoryQueryKey,
  getGetArbitrageTimelineQueryKey,
  useEvaluateArbitrageShock,
  useGetArbitrageDashboard,
  useGetArbitrageMemory,
  useGetArbitrageTimeline,
  type ArbitrageEvaluation,
  type Decision,
  type MemoryNode,
  type ShockInput,
  type TimelineSession,
} from '@workspace/api-client-react';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import './index.css';

const queryClient = new QueryClient();

const formatMoney = (value: number) =>
  value >= 1_000_000
    ? `$${(value / 1_000_000).toFixed(1)}m`
    : `$${Math.round(value / 1_000)}k`;

const formatPercent = (value: number) =>
  `${(Math.abs(value) <= 1 ? value * 100 : value).toFixed(1)}%`;

const toneClass = (tone: string) => {
  if (tone === 'positive' || tone === 'success') return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (tone === 'danger' || tone === 'negative') return 'text-red-700 bg-red-50 border-red-200';
  if (tone === 'warning') return 'text-amber-800 bg-amber-50 border-amber-200';
  return 'text-slate-700 bg-slate-50 border-slate-200';
};

function StatusPill({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 text-[10px] font-bold uppercase tracking-[0.16em] ${toneClass(tone)}`}>
      {tone === 'positive' ? <Check size={11} strokeWidth={3} /> : null}
      {children}
    </span>
  );
}

function SectionLabel({ eyebrow, title, detail }: { eyebrow: string; title: string; detail?: string }) {
  return (
    <div className="flex items-end justify-between gap-4 border-b border-border pb-3">
      <div>
        <p className="mono mb-1 text-[10px] font-medium uppercase tracking-[0.22em] text-muted-foreground">{eyebrow}</p>
        <h2 className="display-font text-xl font-semibold tracking-tight text-foreground">{title}</h2>
      </div>
      {detail ? <span className="mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{detail}</span> : null}
    </div>
  );
}

function LoadingRows({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3" aria-label="Loading data" data-testid="state-loading">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="animate-pulse rounded-md border border-border bg-muted/50 p-4">
          <div className="mb-3 h-2.5 w-1/3 rounded bg-border" />
          <div className="h-3 w-4/5 rounded bg-border" />
        </div>
      ))}
    </div>
  );
}

function QueryError({ onRetry, label }: { onRetry: () => void; label: string }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-5 text-sm text-red-800" data-testid={`state-error-${label}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle size={17} className="mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Unable to load {label}</p>
          <p className="mt-1 text-red-700/80">The console could not reach the latest treasury context.</p>
          <button type="button" onClick={onRetry} className="focus-ring mt-3 inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] underline underline-offset-4" data-testid={`button-retry-${label}`}>
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, note, accent = 'amber', icon: Icon }: { label: string; value: string; note: string; accent?: 'amber' | 'blue' | 'teal' | 'red'; icon: typeof Gauge }) {
  const accents = {
    amber: 'text-amber-700 bg-amber-100',
    blue: 'text-sky-700 bg-sky-100',
    teal: 'text-teal-700 bg-teal-100',
    red: 'text-red-700 bg-red-100',
  };
  return (
    <article className="group relative overflow-hidden rounded-md border border-card-border bg-card p-4 transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_hsl(224_30%_15%/0.08)]" data-testid={`metric-${label.toLowerCase().replaceAll(' ', '-')}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="mono text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
        <span className={`rounded-md p-2 ${accents[accent]}`}><Icon size={15} /></span>
      </div>
      <p className="display-font mt-5 text-[27px] font-semibold tracking-[-0.04em] text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{note}</p>
      <div className={`absolute bottom-0 left-0 h-[3px] w-full origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100 ${accent === 'amber' ? 'bg-primary' : accent === 'blue' ? 'bg-secondary' : accent === 'teal' ? 'bg-accent' : 'bg-destructive'}`} />
    </article>
  );
}

function DecisionCard({ decision, label, highlighted = false }: { decision: Decision; label: string; highlighted?: boolean }) {
  return (
    <article className={`rounded-md border p-4 ${highlighted ? 'border-teal-200 bg-teal-50/70' : 'border-border bg-background/60'}`} data-testid={`decision-${label.toLowerCase()}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="mono text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
        <StatusPill tone={decision.tone}>{decision.tone === 'positive' ? 'Protected' : decision.tone === 'danger' ? 'Exposed' : 'Within policy'}</StatusPill>
      </div>
      <p className="mt-4 text-sm font-semibold leading-6 text-foreground">{decision.summary}</p>
      <div className="mt-4 flex items-end justify-between gap-4 border-t border-border/70 pt-3">
        <div>
          <p className="mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">Expected loss</p>
          <p className={`mt-1 display-font text-2xl font-semibold ${decision.loss > 0 ? 'text-red-700' : 'text-teal-700'}`}>{formatMoney(decision.loss)}</p>
        </div>
        <p className="max-w-[180px] text-right text-xs leading-5 text-muted-foreground">{decision.action}</p>
      </div>
      {decision.references.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {decision.references.map((reference) => <span key={reference} className="mono rounded-sm bg-card px-2 py-1 text-[9px] text-muted-foreground">{reference}</span>)}
        </div>
      ) : null}
    </article>
  );
}

function EvaluatePanel() {
  const [eventName, setEventName] = useState('Euro sovereign spread repricing');
  const [currencyMove, setCurrencyMove] = useState('18');
  const [interestRateMoveBps, setInterestRateMoveBps] = useState('42');
  const [currency, setCurrency] = useState('EUR');
  const [evaluation, setEvaluation] = useState<ArbitrageEvaluation | null>(null);
  const [formError, setFormError] = useState('');
  const evaluate = useEvaluateArbitrageShock();

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!eventName.trim()) {
      setFormError('Name the event before evaluating.');
      return;
    }
    const move = Number(currencyMove);
    const rate = Number(interestRateMoveBps);
    if (!Number.isFinite(move) || !Number.isFinite(rate)) {
      setFormError('Currency and rate moves must be numeric.');
      return;
    }
    setFormError('');
    setEvaluation(null);
    const input: ShockInput = {
      eventName: eventName.trim(),
      currencyMove: move / 100,
      interestRateMoveBps: rate,
      currency,
    };
    evaluate.mutate({ data: input }, {
      onSuccess: (result) => setEvaluation(result),
      onError: () => setFormError('Evaluation failed. Check the event inputs and try again.'),
    });
  };

  return (
    <section className="rounded-md border border-card-border bg-card p-5 sm:p-6" data-testid="panel-evaluate">
      <SectionLabel eyebrow="Live decision" title="Evaluate a treasury shock" detail="POST /evaluate" />
      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(250px,0.75fr)_minmax(420px,1.25fr)]">
        <form onSubmit={submit} className="space-y-4" data-testid="form-evaluate-shock">
          <div>
            <label htmlFor="event-name" className="mono mb-2 block text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Event name</label>
            <input id="event-name" value={eventName} onChange={(event) => setEventName(event.target.value)} className="focus-ring w-full rounded-sm border border-input bg-background px-3 py-2.5 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus:border-primary" data-testid="input-event-name" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="currency-move" className="mono mb-2 block text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Currency move</label>
              <div className="relative">
                <input id="currency-move" type="number" step="0.1" value={currencyMove} onChange={(event) => setCurrencyMove(event.target.value)} className="focus-ring w-full rounded-sm border border-input bg-background px-3 py-2.5 pr-8 text-sm text-foreground" data-testid="input-currency-move" />
                <span className="pointer-events-none absolute right-3 top-2.5 text-sm text-muted-foreground">%</span>
              </div>
            </div>
            <div>
              <label htmlFor="rate-move" className="mono mb-2 block text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Rate move</label>
              <div className="relative">
                <input id="rate-move" type="number" step="1" value={interestRateMoveBps} onChange={(event) => setInterestRateMoveBps(event.target.value)} className="focus-ring w-full rounded-sm border border-input bg-background px-3 py-2.5 pr-12 text-sm text-foreground" data-testid="input-rate-move" />
                <span className="pointer-events-none absolute right-3 top-2.5 text-[11px] text-muted-foreground">bps</span>
              </div>
            </div>
          </div>
          <div>
            <label htmlFor="shock-currency" className="mono mb-2 block text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Base currency</label>
            <select id="shock-currency" value={currency} onChange={(event) => setCurrency(event.target.value)} className="focus-ring w-full rounded-sm border border-input bg-background px-3 py-2.5 text-sm text-foreground" data-testid="select-currency">
              <option value="EUR">EUR · euro</option>
              <option value="GBP">GBP · sterling</option>
              <option value="JPY">JPY · yen</option>
              <option value="CHF">CHF · franc</option>
            </select>
          </div>
          <div className="rounded-sm border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">
            A move above the remembered 14% trauma threshold will trigger the policy path.
          </div>
          {formError ? <p className="text-xs font-semibold text-red-700" role="alert" data-testid="text-evaluate-error">{formError}</p> : null}
          <button type="submit" disabled={evaluate.isPending} className="focus-ring inline-flex w-full items-center justify-center gap-2 rounded-sm bg-primary px-4 py-3 text-xs font-bold uppercase tracking-[0.16em] text-primary-foreground transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_20px_hsl(36_95%_64%/0.24)] disabled:cursor-wait disabled:opacity-60" data-testid="button-evaluate">
            {evaluate.isPending ? <><RefreshCw size={15} className="animate-spin" /> Traversing memory</> : <><Play size={15} fill="currentColor" /> Evaluate shock</>}
          </button>
        </form>

        <div className="panel-grid min-h-[300px] rounded-sm border border-border p-4 sm:p-5" data-testid="result-evaluation">
          {!evaluation && !evaluate.isPending ? (
            <div className="flex h-full min-h-[260px] flex-col items-center justify-center text-center">
              <div className="mb-4 rounded-full border border-primary/30 bg-primary/10 p-3 text-amber-700"><BrainCircuit size={22} /></div>
              <p className="display-font text-lg font-semibold text-foreground">No shock evaluated</p>
              <p className="mt-2 max-w-[300px] text-sm leading-6 text-muted-foreground">Run a scenario to compare the stateless baseline with the retained Hindsight path.</p>
            </div>
          ) : evaluate.isPending ? (
            <div className="space-y-4" data-testid="state-evaluating">
              <div className="flex items-center gap-3 border-b border-border pb-4">
                <span className="pulse-dot h-2.5 w-2.5 rounded-full bg-primary" />
                <p className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Traversing retained context</p>
              </div>
              <LoadingRows count={2} />
            </div>
          ) : evaluation ? (
            <div className="animate-rise">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
                <div>
                  <p className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Evaluation complete</p>
                  <h3 className="mt-1 display-font text-xl font-semibold text-foreground">{evaluation.shock.eventName}</h3>
                  <p className="mono mt-2 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{formatPercent(evaluation.shock.currencyMove)} {evaluation.shock.currency ?? currency} · {evaluation.shock.interestRateMoveBps > 0 ? '+' : ''}{evaluation.shock.interestRateMoveBps} bps</p>
                   <p className={`mono mt-1 text-[10px] uppercase tracking-[0.14em] ${evaluation.transactionFrozen ? 'text-red-700' : 'text-muted-foreground'}`}>{evaluation.varianceIndex.toFixed(2)}× precedent variance index</p>
                </div>
                <StatusPill tone={evaluation.saved > 0 ? 'positive' : 'neutral'}>{evaluation.saved > 0 ? 'Policy matched' : 'No intervention'}</StatusPill>
              </div>
               {evaluation.transactionFrozen ? (
                 <div className="mt-4 flex items-start gap-3 rounded-sm border border-red-300 bg-red-50 p-4 text-red-900" role="alert" data-testid="alert-precedent-shattered">
                   <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-700" />
                   <div>
                     <p className="mono text-[10px] font-bold uppercase tracking-[0.16em] text-red-700">Emergency guardrail active</p>
                     <p className="mt-1 text-sm font-semibold">{evaluation.systemState}</p>
                     <p className="mt-1 text-xs leading-5 text-red-800/80">No asset movement was authorized. The decision is waiting for a manual override.</p>
                   </div>
                 </div>
               ) : null}
              <div className="mt-4 grid gap-3 xl:grid-cols-2">
                <DecisionCard decision={evaluation.baseline} label="Without Hindsight" />
                <DecisionCard decision={evaluation.hindsight} label="With Hindsight" highlighted />
              </div>
              <div className="mt-4 grid grid-cols-[1fr_auto] items-end gap-4 rounded-sm bg-sidebar p-4 text-sidebar-foreground">
                <div>
                  <p className="mono text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/60">Expected loss avoided</p>
                  <p className="display-font mt-1 text-3xl font-semibold tracking-[-0.04em] text-primary" data-testid="value-saved">{formatMoney(evaluation.saved)}</p>
                </div>
                <ShieldCheck size={30} className="text-accent" />
              </div>
              <div className="mt-4">
                <p className="mono mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Execution trace</p>
                <div className="space-y-2">
                  {evaluation.execution.map((step, index) => (
                    <div key={`${step}-${index}`} className="flex items-start gap-2 text-xs text-foreground" data-testid={`execution-step-${index}`}>
                      <Check size={14} className="mt-0.5 shrink-0 text-teal-700" />
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              </div>
               <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2" data-testid="panel-guardrail-telemetry">
                 <div>
                   <p className="mono mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Guardrail telemetry</p>
                   <div className="space-y-1.5">
                     {evaluation.telemetry.map((line) => (
                       <p key={line} className="mono text-[9px] leading-4 text-muted-foreground">{line}</p>
                     ))}
                   </div>
                 </div>
                 <div>
                   <p className="mono mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Importance matrix</p>
                   <div className="space-y-1.5">
                     {evaluation.temporalWeights.slice(0, 3).map((weight) => (
                       <div key={weight.observationId} className="flex items-center justify-between gap-3 text-xs">
                         <span className="text-muted-foreground">{weight.observationId} · day {weight.observedDay}</span>
                         <span className="mono font-medium text-foreground">{weight.importance.toFixed(3)}</span>
                       </div>
                     ))}
                   </div>
                 </div>
               </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function MemoryPanel({ nodes, isLoading, isError, refetch }: { nodes: MemoryNode[] | undefined; isLoading: boolean; isError: boolean; refetch: () => void }) {
  const [filter, setFilter] = useState('All');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const kinds = useMemo(() => ['All', ...Array.from(new Set((nodes ?? []).map((node) => node.kind)))], [nodes]);
  const filtered = (nodes ?? []).filter((node) => filter === 'All' || node.kind === filter);
  const selected = filtered.find((node) => node.id === selectedId) ?? filtered[0];

  return (
    <section className="rounded-md border border-card-border bg-card p-5 sm:p-6" data-testid="panel-memory">
      <SectionLabel eyebrow="Retained context" title="Hindsight memory graph" detail={`${nodes?.length ?? 0} nodes`} />
      <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1">
        <SlidersHorizontal size={14} className="shrink-0 text-muted-foreground" />
        {kinds.map((kind) => (
          <button key={kind} type="button" onClick={() => setFilter(kind)} className={`focus-ring shrink-0 rounded-sm border px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.14em] transition-colors ${filter === kind ? 'border-sidebar bg-sidebar text-sidebar-foreground' : 'border-border bg-background text-muted-foreground hover:border-primary hover:text-foreground'}`} data-testid={`button-memory-filter-${kind.toLowerCase()}`}>
            {kind}
          </button>
        ))}
      </div>
      {isLoading ? <div className="mt-4"><LoadingRows /></div> : isError ? <div className="mt-4"><QueryError onRetry={refetch} label="memory" /></div> : filtered.length === 0 ? (
        <div className="mt-4 rounded-md border border-dashed border-border p-8 text-center" data-testid="state-empty-memory">
          <Database className="mx-auto text-muted-foreground" size={22} />
          <p className="mt-3 text-sm font-semibold">No nodes in this view</p>
          <p className="mt-1 text-xs text-muted-foreground">Choose another memory kind to inspect the retained record.</p>
        </div>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(220px,.9fr)]">
          <div className="space-y-2" role="list" data-testid="list-memory-nodes">
            {filtered.map((node) => (
              <button key={node.id} type="button" onClick={() => setSelectedId(node.id)} className={`focus-ring group w-full rounded-sm border p-3 text-left transition-all duration-200 ${selected?.id === node.id ? 'border-primary bg-amber-50/70 shadow-[inset_3px_0_0_hsl(36_95%_64%)]' : 'border-transparent bg-background/70 hover:border-border hover:bg-background'}`} data-testid={`button-memory-node-${node.id}`}>
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-sm text-[10px] font-bold ${node.tone === 'danger' ? 'bg-red-100 text-red-700' : node.tone === 'positive' ? 'bg-teal-100 text-teal-700' : 'bg-sky-100 text-sky-700'}`}>{String(node.day).padStart(2, '0')}</span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{node.kind} · {node.session}</span>
                      <ChevronRight size={14} className={`shrink-0 text-muted-foreground transition-transform ${selected?.id === node.id ? 'translate-x-0.5 text-primary' : 'group-hover:translate-x-0.5'}`} />
                    </span>
                    <span className="mt-1 block text-sm font-semibold leading-5 text-foreground">{node.title}</span>
                  </span>
                </div>
              </button>
            ))}
          </div>
          {selected ? (
            <div className="rounded-sm border border-border bg-background p-4" data-testid="detail-memory-node">
              <div className="flex items-center justify-between gap-2">
                <span className="mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Node {selected.id}</span>
                <span className="mono text-[10px] text-muted-foreground">DAY {selected.day}</span>
              </div>
              <h3 className="mt-5 display-font text-lg font-semibold leading-6 text-foreground">{selected.title}</h3>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">{selected.detail}</p>
              <div className="mt-5 border-t border-border pt-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Observed value</span>
                  <span className="mono font-medium text-foreground">{selected.value.toFixed(2)}</span>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function TimelinePanel({ sessions, isLoading, isError, refetch }: { sessions: TimelineSession[] | undefined; isLoading: boolean; isError: boolean; refetch: () => void }) {
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const selected = sessions?.find((session) => session.day === selectedDay) ?? sessions?.[sessions.length - 1];
  return (
    <section className="rounded-md border border-card-border bg-card p-5 sm:p-6" data-testid="panel-timeline">
      <SectionLabel eyebrow="Institutional memory" title="Six-month session timeline" detail="DAY 01 — DAY 181" />
      {isLoading ? <div className="mt-5"><LoadingRows count={4} /></div> : isError ? <div className="mt-5"><QueryError onRetry={refetch} label="timeline" /></div> : !sessions?.length ? (
        <div className="mt-5 rounded-md border border-dashed border-border p-8 text-center" data-testid="state-empty-timeline"><Clock3 className="mx-auto text-muted-foreground" size={22} /><p className="mt-3 text-sm font-semibold">Timeline is quiet</p></div>
      ) : (
        <div className="mt-5">
          <div className="relative flex items-start justify-between gap-2 overflow-x-auto pb-2">
            <div className="absolute left-5 right-5 top-4 h-px bg-border" />
            {sessions.map((session) => (
              <button key={session.day} type="button" onClick={() => setSelectedDay(session.day)} className="focus-ring relative z-10 flex min-w-[82px] flex-1 flex-col items-center gap-2 text-center" data-testid={`button-timeline-day-${session.day}`}>
                <span className={`h-3 w-3 rounded-full border-2 transition-transform duration-200 ${selected?.day === session.day ? 'scale-125 border-primary bg-primary' : 'border-muted-foreground/50 bg-card hover:scale-110'}`} />
                <span className={`mono text-[9px] font-medium uppercase tracking-[0.12em] ${selected?.day === session.day ? 'text-foreground' : 'text-muted-foreground'}`}>{session.label}</span>
              </button>
            ))}
          </div>
          {selected ? (
            <div className="mt-5 grid gap-4 rounded-sm border border-border bg-background p-4 sm:grid-cols-[auto_1fr_auto] sm:items-center" data-testid="detail-timeline-session">
              <div className="flex h-11 w-11 items-center justify-center rounded-sm bg-sidebar text-primary"><Layers3 size={19} /></div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">Day {selected.day}</p>
                  <StatusPill tone={selected.status === 'Ready' ? 'positive' : 'neutral'}>{selected.status}</StatusPill>
                </div>
                <h3 className="mt-1 text-sm font-semibold text-foreground">{selected.title}</h3>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{selected.description}</p>
              </div>
              <div className="sm:text-right">
                <p className="mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">{selected.kind}</p>
                <p className="mt-1 text-xs font-medium text-foreground">{selected.label}</p>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function Sidebar({ collapsed, onToggle, mobileOpen, onClose, onNavigate }: { collapsed: boolean; onToggle: () => void; mobileOpen: boolean; onClose: () => void; onNavigate: (label: string) => void }) {
  const nav = [
    { label: 'Decision cockpit', icon: Crosshair, active: true },
    { label: 'Memory graph', icon: BrainCircuit, active: false },
    { label: 'Exposure map', icon: Globe2, active: false },
  ];
  return (
    <>
      {mobileOpen ? <button type="button" aria-label="Close navigation" onClick={onClose} className="fixed inset-0 z-40 bg-slate-950/40 md:hidden" data-testid="button-close-nav-overlay" /> : null}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-[250px] flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform duration-300 md:static md:translate-x-0 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} ${collapsed ? 'md:w-[76px]' : ''}`} data-testid="sidebar">
        <div className="flex h-[76px] items-center justify-between border-b border-sidebar-border px-5">
          <div className={`flex items-center gap-3 overflow-hidden ${collapsed ? 'md:w-8' : ''}`}>
            <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-primary text-primary-foreground"><Zap size={17} fill="currentColor" /><span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-accent" /></div>
            <div className={`${collapsed ? 'md:hidden' : ''}`}>
              <p className="display-font whitespace-nowrap text-sm font-semibold text-sidebar-foreground">Arbitrage</p>
              <p className="mono whitespace-nowrap text-[9px] uppercase tracking-[0.16em] text-sidebar-foreground/50">Treasury console</p>
            </div>
          </div>
          <button type="button" onClick={onToggle} className="focus-ring hidden rounded-sm p-1.5 text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground md:block" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} data-testid="button-toggle-sidebar">
            <PanelLeftClose size={16} className={collapsed ? 'rotate-180' : ''} />
          </button>
          <button type="button" onClick={onClose} className="focus-ring rounded-sm p-1.5 text-sidebar-foreground/60 md:hidden" aria-label="Close navigation" data-testid="button-close-nav"><X size={17} /></button>
        </div>
        <div className="px-3 py-5">
          <p className={`mono mb-3 px-2 text-[9px] uppercase tracking-[0.18em] text-sidebar-foreground/40 ${collapsed ? 'md:hidden' : ''}`}>Workspace</p>
          <nav className="space-y-1">
            {nav.map(({ label, icon: Icon, active }) => (
              <button key={label} type="button" onClick={() => { onNavigate(label); onClose(); }} className={`focus-ring group flex w-full items-center gap-3 rounded-sm px-3 py-2.5 text-left text-xs font-medium transition-colors ${active ? 'bg-sidebar-accent text-sidebar-foreground' : 'text-sidebar-foreground/60 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground'}`} data-testid={`button-nav-${label.toLowerCase().replaceAll(' ', '-')}`}>
                <Icon size={16} className={active ? 'text-primary' : ''} />
                <span className={`${collapsed ? 'md:hidden' : ''}`}>{label}</span>
                {active && !collapsed ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" /> : null}
              </button>
            ))}
          </nav>
        </div>
        <div className={`mt-auto border-t border-sidebar-border p-4 ${collapsed ? 'md:px-3' : ''}`}>
          <div className={`flex items-center gap-3 rounded-sm bg-sidebar-accent p-3 ${collapsed ? 'md:justify-center' : ''}`}>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-bold text-secondary-foreground">AO</div>
            <div className={`${collapsed ? 'md:hidden' : ''}`}>
              <p className="text-xs font-semibold text-sidebar-foreground">Avery Okafor</p>
              <p className="mono mt-0.5 text-[9px] uppercase tracking-[0.12em] text-sidebar-foreground/45">Group treasury</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const dashboard = useGetArbitrageDashboard({ query: { queryKey: getGetArbitrageDashboardQueryKey() } });
  const memory = useGetArbitrageMemory({ query: { queryKey: getGetArbitrageMemoryQueryKey() } });
  const timeline = useGetArbitrageTimeline({ query: { queryKey: getGetArbitrageTimelineQueryKey() } });
  const data = dashboard.data;
  const navigateWithinSurface = (label: string) => {
    if (label === 'Memory graph') document.getElementById('panel-memory')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (label === 'Decision cockpit') window.scrollTo({ top: 0, behavior: 'smooth' });
    if (label === 'Exposure map') document.getElementById('panel-last-decision')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  return (
    <div className="app-shell flex" data-testid="app-dashboard">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} onNavigate={navigateWithinSurface} />
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex h-[76px] items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur-sm sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => setMobileOpen(true)} className="focus-ring rounded-sm border border-border bg-card p-2 text-muted-foreground md:hidden" aria-label="Open navigation" data-testid="button-open-nav"><Menu size={18} /></button>
            <div>
              <p className="mono hidden text-[9px] uppercase tracking-[0.18em] text-muted-foreground sm:block">Treasury / Decision cockpit</p>
              <p className="display-font text-lg font-semibold tracking-tight text-foreground sm:mt-1">Good morning, Avery</p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <span className="hidden items-center gap-2 text-[11px] font-medium text-muted-foreground sm:flex"><span className="h-1.5 w-1.5 rounded-full bg-accent pulse-dot" />Data synced 08:42 UTC</span>
            <div className="relative">
              <button type="button" onClick={() => { setShowAlerts((value) => !value); setShowHelp(false); }} className="focus-ring relative rounded-sm border border-border bg-card p-2.5 text-muted-foreground transition-colors hover:text-foreground" aria-label="Open alerts" data-testid="button-alerts"><Bell size={17} /><span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-primary" /></button>
              {showAlerts ? <div className="absolute right-0 top-12 z-40 w-64 rounded-md border border-border bg-card p-4 shadow-[0_12px_35px_hsl(224_30%_15%/0.15)]" data-testid="popover-alerts"><div className="flex items-start gap-3"><ShieldCheck size={16} className="mt-0.5 text-accent" /><div><p className="text-xs font-semibold text-foreground">Protection is active</p><p className="mt-1 text-xs leading-5 text-muted-foreground">No unacknowledged treasury alerts. Last policy check completed at 08:42 UTC.</p></div></div></div> : null}
            </div>
            <div className="relative">
              <button type="button" onClick={() => { setShowHelp((value) => !value); setShowAlerts(false); }} className="focus-ring rounded-sm border border-border bg-card p-2.5 text-muted-foreground transition-colors hover:text-foreground" aria-label="Open help" data-testid="button-help"><CircleHelp size={17} /></button>
              {showHelp ? <div className="absolute right-0 top-12 z-40 w-64 rounded-md border border-border bg-card p-4 shadow-[0_12px_35px_hsl(224_30%_15%/0.15)]" data-testid="popover-help"><p className="mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Console guide</p><p className="mt-2 text-xs leading-5 text-foreground">Start with Evaluate shock. A move above the retained threshold compares the live event against connected memory nodes.</p></div> : null}
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-[1580px] space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="animate-rise flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <div className="flex items-center gap-2">
                <StatusPill tone="positive"><span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />System {data?.status ?? 'checking'}</StatusPill>
                <span className="mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Policy engine online</span>
              </div>
              <h1 className="display-font mt-4 max-w-[700px] text-4xl font-semibold leading-[1.04] tracking-[-0.055em] text-foreground sm:text-5xl">Make the next move with memory.</h1>
              <p className="mt-3 max-w-[620px] text-sm leading-6 text-muted-foreground">Arbitrage surfaces the decisions that held under pressure, so live treasury shocks arrive with context instead of noise.</p>
            </div>
            <div className="mono flex items-center gap-2 self-start rounded-sm border border-border bg-card px-3 py-2 text-[10px] uppercase tracking-[0.14em] text-muted-foreground sm:self-end"><Activity size={14} className="text-accent" /> Six-month context active</div>
          </div>

          {dashboard.isLoading ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><LoadingRows count={4} /></div> : dashboard.isError ? <QueryError onRetry={() => dashboard.refetch()} label="dashboard" /> : (
            <div className="animate-rise animate-rise-1 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Belief drift" value={formatPercent(data?.beliefDrift ?? 0)} note="Distance from current policy" accent="amber" icon={TrendingDown} />
              <MetricCard label="Active exposure" value={formatMoney(data?.activeExposure ?? 0)} note="Across monitored positions" accent="blue" icon={Globe2} />
              <MetricCard label="Risk tolerance" value={formatPercent(data?.riskTolerance ?? 0)} note="Current decision boundary" accent="teal" icon={Gauge} />
              <MetricCard label="Retained nodes" value={String(data?.totalNodes ?? 0)} note="Linked observations & policy" accent="red" icon={Database} />
            </div>
          )}

          <div className="animate-rise animate-rise-2">
            <EvaluatePanel />
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(420px,.95fr)]">
            <div className="animate-rise animate-rise-3" id="panel-memory">
              <MemoryPanel nodes={memory.data} isLoading={memory.isLoading} isError={memory.isError} refetch={() => memory.refetch()} />
            </div>
            <div className="animate-rise animate-rise-3">
              <TimelinePanel sessions={timeline.data} isLoading={timeline.isLoading} isError={timeline.isError} refetch={() => timeline.refetch()} />
            </div>
          </div>

          {data ? (
            <section className="grid gap-4 rounded-md border border-sidebar-border bg-sidebar p-5 text-sidebar-foreground sm:grid-cols-[1fr_auto] sm:items-center sm:p-6" id="panel-last-decision" data-testid="panel-last-decision">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="mono text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/55">Last decision / retained record</p>
                  <StatusPill tone="positive">Protected</StatusPill>
                </div>
                <p className="mt-3 display-font text-xl font-semibold tracking-tight text-sidebar-foreground">{data.lastDecision}</p>
              </div>
              <div className="flex items-center gap-5 border-t border-sidebar-border pt-4 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
                <div><p className="mono text-[9px] uppercase tracking-[0.16em] text-sidebar-foreground/50">Hedge threshold</p><p className="mt-1 display-font text-2xl font-semibold text-primary">{formatPercent(data.hedgingThreshold)}</p></div>
                <div className="h-9 w-px bg-sidebar-border" />
                <div><p className="mono text-[9px] uppercase tracking-[0.16em] text-sidebar-foreground/50">Baseline</p><p className="mt-1 display-font text-2xl font-semibold text-sidebar-foreground">{formatMoney(data.baselineLoss)}</p></div>
              </div>
            </section>
          ) : null}
          <footer className="flex flex-col justify-between gap-2 border-t border-border pt-4 text-[10px] text-muted-foreground sm:flex-row">
            <span className="mono uppercase tracking-[0.14em]">Arbitrage Treasury Console · Internal decision support</span>
            <span className="mono uppercase tracking-[0.14em]">Build 0.9.4 · Context integrity nominal</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function Router() {
  return (
    <RoutedErrorBoundary>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route component={NotFound} />
      </Switch>
    </RoutedErrorBoundary>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;