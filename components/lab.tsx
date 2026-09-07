'use client';
import Link from 'next/link';
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  Loader2,
  Play,
  RotateCcw,
  X,
} from 'lucide-react';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Slider } from '@/components/ui/slider';
import { SiteHeader, SiteFooter } from './site-header';
import { RunEvidence } from './run-evidence';
import { CopyButton } from './copy-button';
import { useEngine } from '@/lib/use-engine';
import { install } from '@/lib/product';
import type { Comparison, Config, Policy, Scenario } from '@/lib/types';
import catalog from '@/lib/catalog.json';
import example from '@/lib/default-run.json';

const subscribe = () => () => {};
const phases: Record<Scenario, string> = {
  lost_ack: 'After a write commits',
  rate_limit: 'Before a read',
  schema_drift: 'Instead of a valid response',
  timeout: 'Before a read executes',
  latency: 'Before a read returns',
  blackout: 'On every inventory read',
};
export function Lab({
  initialConfig,
  initialPolicy,
}: {
  initialConfig: Config;
  initialPolicy: Policy;
}) {
  const [config, setConfig] = useState(initialConfig);
  const [seed, setSeed] = useState(String(initialConfig.seed));
  const [budget, setBudget] = useState(String(initialConfig.max_calls));
  const [comparison, setComparison] = useState<Comparison>(
    example as Comparison,
  );
  const [policy, setPolicy] = useState(initialPolicy);
  const [running, setRunning] = useState(false);
  const [executed, setExecuted] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const errorPanel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (error) errorPanel.current?.focus();
  }, [error]);
  const attempt = useRef(0);
  const active = useRef(false);
  const engine = useEngine();
  const hydrated = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const disabled = running || !hydrated;
  const scenario = catalog.scenarios[config.scenario];
  const numericValid =
    /^\d+$/.test(seed) &&
    Number(seed) <= 999999 &&
    /^\d+$/.test(budget) &&
    Number(budget) >= 1 &&
    Number(budget) <= 20;
  const draft = { ...config, seed: Number(seed), max_calls: Number(budget) };
  const stale =
    !numericValid ||
    draft.scenario !== comparison.config.scenario ||
    draft.seed !== comparison.config.seed ||
    draft.max_calls !== comparison.config.max_calls ||
    draft.probability !== comparison.config.probability;
  function change(patch: Partial<Config>) {
    setConfig((c) => ({ ...c, ...patch }));
    setError('');
    setNotice('');
  }
  async function execute() {
    if (active.current) return;
    if (!numericValid) {
      setError(
        'Enter a whole-number seed from 0 to 999999 and a call limit from 1 to 20.',
      );
      return;
    }
    active.current = true;
    const id = ++attempt.current;
    setRunning(true);
    setError('');
    setNotice('');
    try {
      const result = await engine.run(draft);
      if (id !== attempt.current) return;
      setComparison(result);
      setExecuted(true);
      setNotice('Comparison complete. All three policies ran in your browser.');
    } catch (e) {
      if (id === attempt.current)
        setError(
          e instanceof Error
            ? e.message
            : 'The comparison could not finish. Try again.',
        );
    } finally {
      if (id === attempt.current) {
        active.current = false;
        setRunning(false);
      }
    }
  }
  function cancel() {
    ++attempt.current;
    active.current = false;
    engine.stop();
    setRunning(false);
    setError('');
    setNotice('Run cancelled. The previous result is still available.');
  }
  async function share() {
    // Share the displayed result's configuration, so a copied link never describes stale draft settings.
    const c = comparison.config;
    const url = new URL(window.location.href);
    url.search = new URLSearchParams({
      scenario: c.scenario,
      seed: String(c.seed),
      p: String(c.probability),
      budget: String(c.max_calls),
      policy,
    }).toString();
    url.hash = '';
    try {
      await navigator.clipboard.writeText(url.href);
      setNotice(
        'Settings link copied. The recipient can run this comparison; results are not included.',
      );
    } catch {
      setNotice(
        'Clipboard unavailable. Copy the settings link from your address bar.',
      );
    }
    // Preserve the router state when replacing the address; no new history entry.
    window.history.replaceState(window.history.state, '', url);
  }
  return (
    <>
      <SiteHeader />
      <main id="main" className="lab-main">
        <div className="page-intro">
          <div>
            <p className="page-kicker">Python library & interactive lab</p>
            <h1>Test recovery from tool failures.</h1>
            <p>
              Inject a failure. Compare recovery code. Check what actually
              committed.
            </p>
          </div>
          <Link href="/docs">
            Use in your tests <ArrowUpRight size={17} />
          </Link>
        </div>
        <noscript>
          <p className="noscript-notice">
            JavaScript is required to run and inspect comparisons. The recorded
            example below remains readable.{' '}
            <Link href="/docs">Run the Python example locally.</Link>
          </p>
        </noscript>
        <section className="workspace" aria-label="Interactive failure lab">
          <aside className="scenario-panel">
            <h2>Failure scenario</h2>
            <RadioGroup
              aria-label="Failure scenario"
              value={config.scenario}
              onValueChange={(value) => change({ scenario: value as Scenario })}
              disabled={disabled}
              className="scenario-list"
            >
              {(Object.keys(catalog.scenarios) as Scenario[]).map(
                (id, index) => (
                  <label
                    className={`scenario-option ${config.scenario === id ? 'chosen' : ''}`}
                    key={id}
                  >
                    <RadioGroupItem
                      value={id}
                      aria-label={catalog.scenarios[id].short}
                      className="scenario-radio"
                    />
                    <span className="scenario-number">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span>
                      <strong>{catalog.scenarios[id].short}</strong>
                      <small>{phases[id]}</small>
                    </span>
                  </label>
                ),
              )}
            </RadioGroup>
            <div className="sidebar-note">
              <p>One order. Three policies.</p>
              <span>
                Each run uses an isolated inventory and shipping fixture.
              </span>
              <Link href="/recipes">
                About these scenarios <ArrowRight size={14} />
              </Link>
            </div>
          </aside>
          <div className="workbench">
            <div className="incident-header">
              <div>
                <p className="incident-id">
                  {scenario.code} <span>/ {phases[config.scenario]}</span>
                </p>
                <h2>{scenario.title}</h2>
                <p>{scenario.description}</p>
              </div>
              <div className="run-action">
                <button
                  className="primary-button"
                  disabled={disabled}
                  onClick={execute}
                >
                  {running ? (
                    <Loader2 className="spin" size={16} />
                  ) : (
                    <Play size={15} fill="currentColor" />
                  )}
                  {running
                    ? engine.status === 'loading'
                      ? 'Starting Python…'
                      : 'Running…'
                    : 'Run comparison'}
                </button>
                {running && (
                  <button className="text-button" onClick={cancel}>
                    Cancel run
                  </button>
                )}
                <span>
                  {engine.status === 'ready'
                    ? 'Python ready in this browser'
                    : 'No account or API key'}
                </span>
              </div>
            </div>
            {error && (
              <div
                className="error-notice"
                role="alert"
                ref={errorPanel}
                tabIndex={-1}
              >
                <div>
                  <strong>Comparison not completed</strong>
                  <p>{error}</p>
                </div>
                <button
                  className="secondary-button"
                  onClick={execute}
                  disabled={disabled}
                >
                  Retry comparison
                </button>
                <button
                  className="text-button"
                  aria-label="Dismiss error"
                  onClick={() => setError('')}
                >
                  <X size={16} />
                </button>
              </div>
            )}
            <div className="run-options">
              <div className="probability-control">
                <label id="probability-label">
                  Fault probability{' '}
                  <output>{Math.round(config.probability * 100)}%</output>
                </label>
                <Slider
                  aria-labelledby="probability-label"
                  min={0}
                  max={100}
                  step={5}
                  value={[config.probability * 100]}
                  disabled={disabled}
                  onValueChange={(values) =>
                    change({
                      probability:
                        (Array.isArray(values) ? values[0] : values) / 100,
                    })
                  }
                />
              </div>
              <label>
                Random seed
                <input
                  aria-label="Random seed"
                  inputMode="numeric"
                  type="text"
                  value={seed}
                  disabled={disabled}
                  onChange={(e) => {
                    setSeed(e.target.value);
                    setError('');
                  }}
                  aria-invalid={!/^\d+$/.test(seed) || Number(seed) > 999999}
                  maxLength={6}
                />
              </label>
              <label>
                Call limit
                <input
                  aria-label="Call limit"
                  inputMode="numeric"
                  type="text"
                  value={budget}
                  disabled={disabled}
                  onChange={(e) => {
                    setBudget(e.target.value);
                    setError('');
                  }}
                  aria-invalid={
                    !/^\d+$/.test(budget) ||
                    Number(budget) < 1 ||
                    Number(budget) > 20
                  }
                  maxLength={2}
                />
              </label>
              <button
                className="reset-button"
                disabled={disabled}
                aria-label="Reset run options"
                title="Reset seed, probability, and call limit"
                onClick={() => {
                  setSeed('42');
                  setBudget('8');
                  change({ probability: 1 });
                }}
              >
                <RotateCcw size={16} />
              </button>
            </div>
            <div className="run-feedback" aria-live="polite">
              {running && (
                <p>
                  First run downloads Python (about 13 MB). Computation stays in
                  your browser.
                </p>
              )}
              {notice && (
                <p>
                  {notice}
                  <button
                    aria-label="Dismiss notification"
                    onClick={() => setNotice('')}
                  >
                    <X size={14} />
                  </button>
                </p>
              )}
            </div>
            <RunEvidence
              key={`${comparison.runs[0].digest}-${executed}`}
              comparison={comparison}
              policy={policy}
              onPolicy={setPolicy}
              hydrated={hydrated}
              provenance={
                executed
                  ? 'Executed in your browser'
                  : 'Recorded Python example'
              }
              stale={stale}
              onShare={share}
            />
          </div>
        </section>
        <section className="library-strip">
          <div>
            <h2>Bring the failure into your test suite.</h2>
            <p>
              Wrap a Python function, record committed effects, and keep the
              recovery as a regression test. Sync and async. No runtime
              dependencies.
            </p>
            <Link href="/docs">
              Read the quickstart <ArrowRight size={16} />
            </Link>
          </div>
          <div className="install-block">
            <span>Install the tagged release</span>
            <div className="code-wrap">
              <CopyButton text={install} label="Copy install command" />
              <pre>
                <code>{install}</code>
              </pre>
            </div>
          </div>
        </section>
        <p className="honesty-note">
          The lab runs scripted recovery policies against in-memory tools. No
          language model calls or real shipments.
        </p>
      </main>
      <SiteFooter />
    </>
  );
}
