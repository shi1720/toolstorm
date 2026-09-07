'use client';
import Link from 'next/link';
import { useState } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  Box,
  Braces,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Code2,
  Copy,
  Download,
  FlaskConical,
  Gauge,
  Hash,
  Info,
  Loader2,
  PackageCheck,
  Radio,
  RotateCcw,
  ShieldCheck,
  Terminal,
  Timer,
  Unplug,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Slider } from '@/components/ui/slider';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { SiteHeader, SiteFooter } from './site-header';
import { CopyButton } from './copy-button';
import { useEngine } from '@/lib/use-engine';
import type { Call, Comparison, Config, Policy, Scenario } from '@/lib/types';
import catalog from '@/lib/catalog.json';
import example from '@/lib/default-run.json';

const ICONS = {
  radio: Radio,
  gauge: Gauge,
  braces: Braces,
  clock: Clock3,
  timer: Timer,
  unplug: Unplug,
};
const scenarioNames = Object.keys(catalog.scenarios) as Scenario[];
const policies = Object.keys(catalog.policies) as Policy[];
const install =
  'pip install "toolstorm @ git+https://github.com/shi1720/toolstorm.git@v0.1.0"';

function download(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2) + '\n'], {
      type: 'application/json',
    }),
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const pretty = (value: unknown) => JSON.stringify(value, null, 2) ?? 'null';
const ms = (n: number) => `${Math.round(n * 1000)} ms`;

export function Lab({
  initialConfig,
  initialPolicy,
}: {
  initialConfig: Config;
  initialPolicy: Policy;
}) {
  const [config, setConfig] = useState<Config>(initialConfig),
    [comparison, setComparison] = useState<Comparison>(example as Comparison),
    [policy, setPolicy] = useState<Policy>(initialPolicy);
  const [running, setRunning] = useState(false),
    [executed, setExecuted] = useState(false),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [selected, setSelected] = useState<Call | null>(null),
    [filter, setFilter] = useState<string | null>(null),
    [tab, setTab] = useState('trace');
  const engine = useEngine();
  const run = comparison.runs.find((r) => r.policy === policy)!;
  const scenario = catalog.scenarios[config.scenario],
    snapshot = catalog.scenarios[comparison.scenario];
  const stale = JSON.stringify(config) !== JSON.stringify(comparison.config);
  const changed = (patch: Partial<Config>) => {
    setConfig((c) => ({ ...c, ...patch }));
    setError('');
  };
  async function runStorm() {
    if (running) return;
    setRunning(true);
    setError('');
    try {
      const result = await engine.run(config);
      setComparison(result);
      setExecuted(true);
      setFilter(null);
      setSelected(null);
      setNotice(
        'All three policies executed. Select a policy to inspect its evidence.',
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not run the storm.');
    } finally {
      setRunning(false);
    }
  }
  async function share() {
    const q = new URLSearchParams({
      scenario: config.scenario,
      seed: String(config.seed),
      p: String(config.probability),
      budget: String(config.max_calls),
      policy,
    });
    const url = new URL(window.location.href);
    url.search = q.toString();
    url.hash = '';
    try {
      await navigator.clipboard.writeText(url.href);
      window.history.replaceState(null, '', url);
      setNotice('Link copied. It shares the configuration, not your result.');
    } catch {
      setNotice(
        'Clipboard unavailable. Copy the configuration link from your address bar.',
      );
      window.history.replaceState(null, '', url);
    }
  }
  const code = `from toolstorm import Storm, Rule, Contract, VirtualClock\n\nstorm = Storm(\n    [Rule(${JSON.stringify(scenario.rules[0].name)},\n          ${JSON.stringify(scenario.rules[0].tool)},\n          ${JSON.stringify(scenario.rules[0].kind)}${'calls' in scenario.rules[0] ? `, calls=(${scenario.rules[0].calls.join(', ')},)` : ''}${'delay' in scenario.rules[0] ? `, delay=${scenario.rules[0].delay}` : ''}${config.probability !== 1 ? `, probability=${config.probability}` : ''}${'replacement' in scenario.rules[0] ? `,\n          replacement={"available": "probably", "warehouse": None}` : ''})],\n    seed=${config.seed}, clock=VirtualClock(), max_calls=${config.max_calls},\n)\n\n# Wrap the tool BEFORE handing it to your agent.\nwrapped_tool = storm.tool(${JSON.stringify(scenario.rules[0].tool)})(your_tool)\n# Run your agent with wrapped_tool, then assert:\nContract(storm.report())\\\n    .require_triggered()\\\n    .no_duplicate_effects()\\\n    .assert_valid()`;
  const calls = run.report.calls.filter(
    (c) => filter === null || c.tool === filter,
  );
  const duplicate = run.stats.effects > 1;
  return (
    <>
      <SiteHeader />
      <main className="lab-main">
        <section className="intro">
          <div>
            <p className="eyebrow">
              <span className="live-dot" /> THE AGENT RESILIENCE LAB
            </p>
            <h1>
              Give your agent
              <br className="mobile-break" /> a <span>bad day.</span>
            </h1>
            <p className="intro-copy">
              Your tools will fail. Find out what happens next.
            </p>
          </div>
          <Link className="intro-note" href="/docs">
            <span className="tiny-icon">
              <FlaskConical size={20} />
            </span>
            <span>
              A little chaos.
              <br />
              <strong>A lot more confidence.</strong>
            </span>
            <ArrowUpRight size={17} />
          </Link>
        </section>
        <section className="workspace" aria-label="Interactive resilience lab">
          <aside className="scenario-panel">
            <div className="section-label">
              <span>01</span> PICK YOUR STORM <span className="count">06</span>
            </div>
            <RadioGroup
              aria-label="Failure scenario"
              value={config.scenario}
              onValueChange={(v) => changed({ scenario: v as Scenario })}
              disabled={running}
              className="scenario-list"
            >
              {scenarioNames.map((id) => {
                const item = catalog.scenarios[id],
                  Icon = ICONS[item.icon as keyof typeof ICONS];
                return (
                  <div
                    className={`scenario-option ${config.scenario === id ? 'chosen' : ''}`}
                    key={id}
                  >
                    <RadioGroupItem
                      id={`scenario-${id}`}
                      value={id}
                      aria-label={item.short}
                      className="scenario-radio"
                    />
                    <span className="scenario-icon">
                      <Icon size={19} />
                    </span>
                    <span>
                      <strong>{item.short}</strong>
                      <small>{item.category.toLowerCase()}</small>
                    </span>
                    {config.scenario === id && (
                      <ChevronRight className="scenario-chevron" size={16} />
                    )}
                  </div>
                );
              })}
            </RadioGroup>
            <div className="controls">
              <div className="section-label">
                <span>02</span> TUNE THE CHAOS
              </div>
              <div className="control-line">
                <span id="probability-label">Fault probability</span>
                <output>{Math.round(config.probability * 100)}%</output>
              </div>
              <Slider
                aria-labelledby="probability-label"
                min={0}
                max={100}
                step={5}
                value={[Math.round(config.probability * 100)]}
                disabled={running}
                onValueChange={(v) =>
                  changed({ probability: (Array.isArray(v) ? v[0] : v) / 100 })
                }
              />
              <div className="range-hints">
                <span>Clear skies</span>
                <span>Perfect storm</span>
              </div>
              <div className="number-controls">
                <label>
                  <span>Random seed</span>
                  <div>
                    <Hash size={14} />
                    <input
                      aria-label="Random seed"
                      type="number"
                      step={1}
                      min={0}
                      max={999999}
                      value={config.seed}
                      disabled={running}
                      onChange={(e) => {
                        const value = Number(e.target.value);
                        if (
                          Number.isSafeInteger(value) &&
                          value >= 0 &&
                          value <= 999999
                        )
                          changed({ seed: value });
                      }}
                    />
                  </div>
                </label>
                <label>
                  <span>Call budget</span>
                  <div>
                    <Gauge size={14} />
                    <input
                      aria-label="Call budget"
                      type="number"
                      min={1}
                      max={20}
                      value={config.max_calls}
                      disabled={running}
                      onChange={(e) => {
                        const value = Number(e.target.value);
                        if (
                          Number.isInteger(value) &&
                          value >= 1 &&
                          value <= 20
                        )
                          changed({ max_calls: value });
                      }}
                    />
                  </div>
                </label>
              </div>
            </div>
            <button
              className="run-button"
              onClick={runStorm}
              disabled={running}
            >
              {running ? (
                <Loader2 className="spin" size={19} />
              ) : (
                <Zap size={19} fill="currentColor" />
              )}
              {running
                ? engine.status === 'loading'
                  ? 'Starting Python…'
                  : 'Running storm…'
                : 'Run the storm'}
              {!running && <ArrowRight size={18} />}
            </button>
            {running ? (
              <button
                className="cancel-button"
                onClick={() => {
                  engine.stop();
                  setRunning(false);
                }}
              >
                Cancel run
              </button>
            ) : (
              <p className="local-note">
                <span className="live-dot" /> Runs locally. No API key.
              </p>
            )}
          </aside>
          <div className="experiment">
            <div className="experiment-heading">
              <div>
                <p className="eyebrow">
                  {scenario.code} <span>/</span> {scenario.category}
                </p>
                <h2>{scenario.title}</h2>
                <p>{scenario.description}</p>
              </div>
              <span className={`severity ${scenario.severity.toLowerCase()}`}>
                <span />
                {scenario.severity}
              </span>
            </div>
            <div className="flow-canvas">
              <div className="canvas-label">
                <span className="eyebrow">THE MISSION</span>
                <span>Ship one care package. Exactly once.</span>
              </div>
              <div className={`flow-graph ${running ? 'is-running' : ''}`}>
                <div className="flow-node agent-node">
                  <span className="node-symbol">
                    <Terminal size={25} />
                  </span>
                  <strong>{catalog.policies[policy].name}</strong>
                  <span>Recovery policy</span>
                  <span className="node-badge">
                    {run.stats.calls} tool{' '}
                    {run.stats.calls === 1 ? 'call' : 'calls'}
                  </span>
                </div>
                <div className="flow-connector">
                  <span>read</span>
                  <div />
                  <ChevronRight size={17} />
                </div>
                <button
                  className={`flow-node tool-node ${filter === 'check_inventory' ? 'focused' : ''}`}
                  onClick={() => {
                    setFilter(
                      filter === 'check_inventory' ? null : 'check_inventory',
                    );
                    setTab('trace');
                  }}
                >
                  <span className="node-symbol">
                    <Box size={25} />
                  </span>
                  <strong>Inventory</strong>
                  <span>check_inventory()</span>
                  <span
                    className={`node-badge ${run.report.calls.some((c) => c.tool === 'check_inventory' && c.injected) ? 'faulted' : ''}`}
                  >
                    {run.report.calls.filter(
                      (c) => c.tool === 'check_inventory' && c.injected,
                    ).length || 'No'}{' '}
                    fault
                    {run.report.calls.filter(
                      (c) => c.tool === 'check_inventory' && c.injected,
                    ).length === 1
                      ? ''
                      : 's'}{' '}
                    injected
                  </span>
                </button>
                <div className="flow-connector">
                  <span>write</span>
                  <div />
                  <ChevronRight size={17} />
                </div>
                <button
                  className={`flow-node tool-node ${duplicate ? 'danger-node' : ''} ${filter === 'create_shipment' ? 'focused' : ''}`}
                  onClick={() => {
                    setFilter(
                      filter === 'create_shipment' ? null : 'create_shipment',
                    );
                    setTab('trace');
                  }}
                >
                  <span className="node-symbol">
                    <PackageCheck size={25} />
                  </span>
                  <strong>Shipping</strong>
                  <span>create_shipment()</span>
                  <span className={`node-badge ${duplicate ? 'faulted' : ''}`}>
                    {run.stats.effects} shipment
                    {run.stats.effects === 1 ? '' : 's'} created
                  </span>
                </button>
              </div>
              <div className="canvas-footer">
                <span>
                  <span className={`status-dot ${executed ? 'green' : ''}`} />
                  {executed
                    ? 'Executed in browser'
                    : 'Recorded Python example'}{' '}
                  · seed {comparison.config.seed}
                </span>
                <span>
                  In-memory tools <span>↗</span> virtual time
                </span>
              </div>
            </div>
            <div className="evidence-top">
              <div className="section-label">
                <span>03</span> INSPECT THE EVIDENCE
              </div>
              <div className="evidence-actions">
                <button onClick={share}>
                  <Copy size={14} />
                  Share config
                </button>
                <button
                  onClick={() =>
                    download(
                      run,
                      `toolstorm-${comparison.scenario}-${policy}.json`,
                    )
                  }
                >
                  <Download size={14} />
                  Export run
                </button>
              </div>
            </div>
            {stale && (
              <div className="stale-notice">
                <RotateCcw size={14} /> Configuration changed. Run the storm to
                refresh results.{' '}
                <span>Showing {snapshot.short.toLowerCase()}.</span>
              </div>
            )}
            <fieldset
              className="policy-cards"
              aria-label="Compare recovery policies"
            >
              {policies.map((p, i) => {
                const r = comparison.runs.find((x) => x.policy === p)!,
                  ok = r.contract.passed;
                return (
                  <button
                    key={p}
                    className={`policy-card ${policy === p ? 'selected' : ''}`}
                    aria-pressed={policy === p}
                    onClick={() => {
                      setPolicy(p);
                      setFilter(null);
                    }}
                  >
                    <div>
                      <span className="policy-index">0{i + 1}</span>
                      <span className={`verdict ${ok ? 'pass' : 'fail'}`}>
                        {ok ? <Check size={12} /> : <X size={12} />}{' '}
                        {ok ? 'PASS' : 'FAIL'}
                      </span>
                    </div>
                    <strong>{catalog.policies[p].name}</strong>
                    <p>{catalog.policies[p].description}</p>
                    <span className="policy-stats">
                      <b>{r.stats.calls}</b>{' '}
                      {r.stats.calls === 1 ? 'call' : 'calls'}
                      <span>·</span>
                      <b className={r.stats.effects > 1 ? 'red' : ''}>
                        {r.stats.effects}
                      </b>{' '}
                      {r.stats.effects === 1 ? 'shipment' : 'shipments'}
                      <span>·</span>
                      {ms(r.stats.elapsed)}
                    </span>
                  </button>
                );
              })}
            </fieldset>
            <Tabs
              className="evidence-console"
              value={tab}
              onValueChange={(v) => setTab(String(v))}
            >
              <div className="console-header">
                <TabsList variant="line">
                  <TabsTrigger value="trace">
                    <Terminal size={15} />
                    Execution trace{' '}
                    <span className="tab-count">{run.stats.calls}</span>
                  </TabsTrigger>
                  <TabsTrigger value="contracts">
                    <ShieldCheck size={15} />
                    Contracts
                  </TabsTrigger>
                  <TabsTrigger value="code">
                    <Code2 size={15} />
                    Try in Python
                  </TabsTrigger>
                </TabsList>
                <span className="console-detail">
                  {catalog.policies[policy].name} <span className="live-dot" />
                </span>
              </div>
              <TabsContent value="trace">
                <div className="trace-body">
                  {filter && (
                    <button
                      className="filter-pill"
                      onClick={() => setFilter(null)}
                    >
                      {filter} <X size={13} />
                    </button>
                  )}
                  <div className="trace-table-head">
                    <span>TIME</span>
                    <span>TOOL / EVENT</span>
                    <span>RESULT</span>
                  </div>
                  {calls.map((c) => (
                    <button
                      className="trace-row"
                      key={c.id}
                      onClick={() => setSelected(c)}
                    >
                      <span className="trace-time">
                        +{c.started.toFixed(2)}s
                      </span>
                      <span className="trace-name">
                        {c.status === 'ok' ? (
                          <CheckCircle2 size={16} />
                        ) : (
                          <XCircle size={16} className="trace-error" />
                        )}
                        <span>
                          {c.tool}
                          <small>
                            attempt {c.ordinal}
                            {c.executed ? ' · executed' : ' · skipped'}
                          </small>
                        </span>
                        {c.fault && (
                          <span className="fault-label">
                            {c.kind?.replaceAll('_', ' ')}
                          </span>
                        )}
                      </span>
                      <span
                        className={`trace-result ${c.status === 'ok' ? '' : 'trace-error'}`}
                      >
                        {c.status === 'ok' ? 'OK' : c.error?.type}
                        <ChevronRight size={14} />
                      </span>
                    </button>
                  ))}
                  {calls.length === 0 && (
                    <p className="empty-trace">This tool was never reached.</p>
                  )}
                  <div className="trace-summary">
                    <span>
                      {duplicate ? (
                        <XCircle size={16} className="trace-error" />
                      ) : (
                        <CheckCircle2 size={16} />
                      )}
                      <strong>
                        {duplicate
                          ? 'Task succeeded. The contract didn’t.'
                          : run.contract.passed
                            ? 'Recovery checks passed.'
                            : run.outcome.completed
                              ? 'Completed, with a failed check.'
                              : 'No confirmed completion.'}
                      </strong>
                    </span>
                    <span>
                      {run.stats.effects} committed · {run.stats.faults}{' '}
                      injected
                    </span>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="contracts">
                <div className="contract-list">
                  {run.contract.checks.map((c) => (
                    <div className="contract-row" key={c.name}>
                      {c.passed ? (
                        <CheckCircle2 size={17} />
                      ) : (
                        <XCircle size={17} className="trace-error" />
                      )}
                      <div>
                        <strong>{c.name}</strong>
                        <p>{c.detail}</p>
                      </div>
                      <span
                        className={c.passed ? 'contract-pass' : 'trace-error'}
                      >
                        {c.passed ? 'PASS' : 'FAIL'}
                      </span>
                    </div>
                  ))}
                </div>
              </TabsContent>
              <TabsContent value="code">
                <div className="console-code">
                  <CopyButton text={code} />
                  <pre>
                    <code>{code}</code>
                  </pre>
                  <p>
                    The snippet configures your selected storm.{' '}
                    <Link href="/docs">
                      See the complete integration <ArrowUpRight size={13} />
                    </Link>
                  </p>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </section>
        <output
          aria-live="polite"
          className={`lab-notification ${notice ? 'visible' : ''}`}
        >
          {notice && (
            <>
              <CheckCircle2 size={16} />
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice('')}
              >
                <X size={15} />
              </button>
            </>
          )}
        </output>
        {error && (
          <div role="alert" className="error-notice">
            <XCircle size={19} />
            <div>
              <strong>The run could not finish.</strong>
              <p>{error}</p>
              <p>
                The recorded example remains available.{' '}
                <Link href="/docs">
                  Run the same scenarios locally with the CLI.
                </Link>
              </p>
            </div>
            <button aria-label="Dismiss error" onClick={() => setError('')}>
              <X size={17} />
            </button>
          </div>
        )}
        <section className="takeaway">
          <div className="takeaway-icon">
            <Info size={21} />
          </div>
          <div>
            <p className="eyebrow">THE PART WORTH REMEMBERING</p>
            <h3>
              {comparison.scenario === 'lost_ack'
                ? 'A green response can hide a red outcome.'
                : snapshot.title}
            </h3>
            <p>{snapshot.lesson}</p>
          </div>
          <Link href="/recipes">
            Explore the recipes <ArrowUpRight size={16} />
          </Link>
        </section>
        <section className="library-strip">
          <div>
            <span className="eyebrow">TAKE THE STORM HOME</span>
            <h2>Small library. Serious failure modes.</h2>
            <p>
              Zero runtime dependencies. Sync + async. Your framework, your
              recovery code.
            </p>
          </div>
          <div>
            <div className="install-command">
              <Terminal size={17} />
              <code>pip install git+…/toolstorm.git@v0.1.0</code>
              <CopyButton text={install} label="Copy install command" />
            </div>
            <Link href="/docs">
              Read the quickstart <ArrowRight size={15} />
            </Link>
          </div>
        </section>
        <p className="honesty-note">
          <ShieldCheck size={15} /> The lab compares scripted recovery policies,
          not language models. Every result is produced by ToolStorm’s Python
          engine. No real shipments, model calls, or performance benchmarks.
        </p>
      </main>
      <SiteFooter />
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent className="call-dialog">
          {selected && (
            <>
              <DialogTitle>
                {selected.tool}
                <span> / attempt {selected.ordinal}</span>
              </DialogTitle>
              <DialogDescription>
                {selected.executed
                  ? 'The underlying tool executed.'
                  : 'The underlying tool did not execute.'}{' '}
                {selected.fault
                  ? `Fault: ${selected.kind?.replaceAll('_', ' ')}.`
                  : 'No fault was applied.'}
              </DialogDescription>
              <div className="call-meta">
                <span>
                  Started <b>{ms(selected.started)}</b>
                </span>
                <span>
                  Duration <b>{ms(selected.elapsed)}</b>
                </span>
                <span>
                  Status <b>{selected.status}</b>
                </span>
              </div>
              <h4>Arguments</h4>
              <pre>{pretty(selected.arguments)}</pre>
              <h4>
                {selected.error ? 'Error (message omitted)' : 'Return value'}
              </h4>
              <pre>{pretty(selected.error ?? selected.output)}</pre>
              {run.report.effects.some((e) => e.call_id === selected.id) && (
                <>
                  <h4>Committed side effects</h4>
                  <pre>
                    {pretty(
                      run.report.effects.filter(
                        (e) => e.call_id === selected.id,
                      ),
                    )}
                  </pre>
                </>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
