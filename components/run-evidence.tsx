'use client';
import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  Check,
  ChevronRight,
  Copy,
  Download,
  X,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { CopyButton } from './copy-button';
import type { Call, Comparison, Policy, Run } from '@/lib/types';
import catalog from '@/lib/catalog.json';
import { install } from '@/lib/product';

const pretty = (value: unknown) => JSON.stringify(value, null, 2) ?? 'null';
const time = (n: number) => `${Math.round(n * 1000)} ms`;
export function finding(run: Run): {
  title: string;
  detail: string;
  tone: string;
} {
  if (!run.stats.faults)
    return {
      title: 'No failure was injected',
      detail:
        'This run did not exercise recovery. Check the probability and call budget, then run again.',
      tone: 'neutral',
    };
  if (run.stats.effects > 1)
    return {
      title: `${run.stats.effects} shipments for 1 order`,
      detail:
        'The first shipment committed before its confirmation was lost. Retrying without an idempotency key committed another shipment.',
      tone: 'fail',
    };
  if (run.stats.effects === 1 && !run.outcome.completed)
    return {
      title: '1 shipment committed. No confirmation received.',
      detail:
        'The write succeeded, but the policy stopped after losing its acknowledgement. An error response does not mean the write failed.',
      tone: 'fail',
    };
  if (run.contract.passed && !run.outcome.completed)
    return {
      title: 'Stopped without claiming completion',
      detail:
        'Inventory stayed unavailable. The policy respected the call budget and did not create a shipment.',
      tone: 'pass',
    };
  if (run.contract.passed)
    return {
      title: '1 shipment. All recovery checks passed.',
      detail:
        run.scenario === 'lost_ack'
          ? 'The retry reused the original write key. The service returned the existing receipt without committing a second shipment.'
          : catalog.scenarios[run.scenario].lesson,
      tone: 'pass',
    };
  return {
    title: run.outcome.completed
      ? 'Shipment confirmed, with failed checks'
      : 'No shipment confirmed',
    detail: run.contract.checks
      .filter((c) => !c.passed)
      .map((c) => c.detail)
      .join(' '),
    tone: 'fail',
  };
}
function download(run: Run) {
  const url = URL.createObjectURL(
    new Blob([pretty(run) + '\n'], { type: 'application/json' }),
  );
  const link = document.createElement('a');
  link.href = url;
  link.download = `toolstorm-${run.scenario}-${run.policy}-seed${run.seed}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function RunEvidence({
  comparison,
  policy,
  onPolicy,
  hydrated,
  provenance,
  stale,
  onShare,
}: {
  comparison: Comparison;
  policy: Policy;
  onPolicy: (policy: Policy) => void;
  hydrated: boolean;
  provenance: string;
  stale: boolean;
  onShare: () => Promise<string>;
}) {
  const [selected, setSelected] = useState<Call | null>(null);
  const [filter, setFilter] = useState('all');
  const [shareMessage, setShareMessage] = useState('');
  const run = comparison.runs.find((r) => r.policy === policy)!;
  const result = finding(run);
  const snippet = `${install}\n\n# Run this scenario against all three scripted policies:\ntoolstorm demo --scenario ${comparison.scenario} --policy all \\\n  --seed ${comparison.config.seed} --probability ${comparison.config.probability} --max-calls ${comparison.config.max_calls}\n\n# Save and check the selected policy:\ntoolstorm demo --scenario ${comparison.scenario} --policy ${policy} \\\n  --seed ${comparison.config.seed} --probability ${comparison.config.probability} --max-calls ${comparison.config.max_calls} \\\n  --output incident.json --fail-on-contract\ntoolstorm check incident.json --max-calls ${comparison.config.max_calls}`;
  const tools = [...new Set(run.report.calls.map((c) => c.tool))];
  return (
    <section className="results" aria-label="Comparison results">
      <div className="result-caption">
        <span>
          <span className="record-dot" />
          {provenance}
        </span>
        <span>
          Seed {comparison.config.seed} ·{' '}
          {Math.round(comparison.config.probability * 100)}% probability ·{' '}
          {comparison.config.max_calls} call limit
        </span>
      </div>
      {stale && (
        <output className="stale-notice">
          Settings changed. Results below are for{' '}
          <strong>
            {catalog.scenarios[comparison.scenario].short.toLowerCase()}
          </strong>
          . Run the comparison to update them.
        </output>
      )}
      <section
        className={`finding ${result.tone}`}
        aria-label="Selected policy outcome"
      >
        <div className="finding-title">
          <span>{catalog.policies[policy].name}</span>
          <h2>{result.title}</h2>
          <p>{result.detail}</p>
        </div>
        <div className="finding-count">
          <strong>
            {run.stats.effects}
            <small>/ 1</small>
          </strong>
          <span>committed / requested</span>
        </div>
      </section>
      <div className="comparison-table-wrap">
        <table className="comparison-table">
          <caption>
            Compare recovery policies{' '}
            <span>Select a policy to inspect its calls and checks.</span>
          </caption>
          <thead>
            <tr>
              <th scope="col">Recovery policy</th>
              <th scope="col">Confirmation</th>
              <th scope="col">Shipments</th>
              <th scope="col">Recorded calls</th>
              <th scope="col">Simulated time</th>
              <th scope="col">Checks</th>
            </tr>
          </thead>
          <tbody>
            {comparison.runs.map((r) => (
              <tr
                key={r.policy}
                className={policy === r.policy ? 'selected-policy' : ''}
              >
                <th scope="row">
                  <button
                    aria-label={catalog.policies[r.policy].name}
                    disabled={!hydrated}
                    aria-pressed={policy === r.policy}
                    onClick={() => {
                      onPolicy(r.policy);
                      setFilter('all');
                      setSelected(null);
                    }}
                  >
                    <span className="policy-indicator" aria-hidden="true" />
                    <span>
                      {catalog.policies[r.policy].name}
                      <small>{catalog.policies[r.policy].description}</small>
                    </span>
                  </button>
                </th>
                <td>{r.outcome.completed ? 'Received' : 'Not received'}</td>
                <td
                  className={r.stats.effects > 1 ? 'bad-count' : 'effect-count'}
                >
                  {r.stats.effects}
                  <small> / 1 requested</small>
                </td>
                <td>
                  {r.stats.calls}
                  {r.report.budget_rejections > 0 && (
                    <small className="refused-count">
                      +{r.report.budget_rejections} refused
                    </small>
                  )}
                </td>
                <td>{time(r.stats.elapsed)}</td>
                <td>
                  <span
                    className={`check-status ${r.contract.passed ? 'pass' : r.stats.faults ? 'fail' : 'neutral'}`}
                  >
                    {r.contract.passed ? <Check size={14} /> : <X size={14} />}{' '}
                    {r.contract.passed ? 'Passed' : 'Failed'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="evidence-heading">
        <h3>Run evidence</h3>
        <div className="action-group">
          <button
            className="text-button"
            disabled={!hydrated}
            onClick={async () => setShareMessage(await onShare())}
          >
            <Copy size={15} /> Copy settings link
          </button>
          <button
            className="text-button"
            disabled={!hydrated}
            onClick={() => download(run)}
          >
            <Download size={16} /> Export selected result
          </button>
        </div>
      </div>
      {shareMessage && (
        <output className="share-message">{shareMessage}</output>
      )}
      <Tabs className="evidence" defaultValue="trace">
        <TabsList variant="line">
          <TabsTrigger disabled={!hydrated} value="trace">
            Call trace <span className="tab-count">{run.stats.calls}</span>
          </TabsTrigger>
          <TabsTrigger disabled={!hydrated} value="contracts">
            Checks{' '}
            <span className="tab-count">{run.contract.checks.length}</span>
          </TabsTrigger>
          <TabsTrigger disabled={!hydrated} value="code">
            Python example
          </TabsTrigger>
        </TabsList>
        <TabsContent value="trace">
          <div className="trace-toolbar">
            <div className="tool-filters" aria-label="Filter calls by tool">
              {['all', ...tools].map((name) => (
                <button
                  disabled={!hydrated}
                  key={name}
                  aria-pressed={filter === name}
                  onClick={() => setFilter(name)}
                >
                  {name === 'all' ? 'All tools' : name}
                </button>
              ))}
            </div>
            <span>Times are simulated</span>
          </div>
          <ol className="trace-list">
            {run.report.calls
              .filter((c) => filter === 'all' || c.tool === filter)
              .map((c) => {
                const effects = run.report.effects.filter(
                  (e) => e.call_id === c.id,
                );
                return (
                  <li key={c.id}>
                    <button
                      className="trace-row"
                      disabled={!hydrated}
                      onClick={() => setSelected(c)}
                    >
                      <span className="trace-index">
                        {String(c.id).padStart(2, '0')}
                      </span>
                      <span className="trace-time">
                        +{c.started.toFixed(2)}s
                      </span>
                      <span className="trace-call">
                        <strong>{c.tool}</strong>
                        <span>
                          Attempt {c.ordinal} ·{' '}
                          {c.executed ? 'executed' : 'not executed'}
                          {c.injected
                            ? ` · ${c.kind?.replaceAll('_', ' ')}`
                            : ''}
                        </span>
                        {effects.map((e) => (
                          <span
                            className="commit-note"
                            key={`${e.call_id}-${e.identity}`}
                          >
                            <ArrowRight size={13} />
                            Shipment committed · {e.key}
                          </span>
                        ))}
                      </span>
                      <span
                        className={`trace-result ${c.error ? 'fail-text' : ''}`}
                      >
                        {c.error?.type ?? 'Returned'}
                        {effects.length > 0 && c.error && (
                          <small>after commit</small>
                        )}
                      </span>
                      <ChevronRight size={16} />
                    </button>
                  </li>
                );
              })}
          </ol>
          <div className="trace-footnote">
            {run.report.budget_rejections > 0 && (
              <span>
                {run.report.budget_rejections} additional attempt(s) refused by
                the call limit.{' '}
              </span>
            )}
            {run.stats.faults} fault{run.stats.faults === 1 ? '' : 's'} injected
            · {run.stats.effects} committed shipment
            {run.stats.effects === 1 ? '' : 's'} · Select a call to inspect its
            inputs and output.
          </div>
        </TabsContent>
        <TabsContent value="contracts">
          <div className="contract-list">
            {run.contract.checks.map((c) => (
              <div className="contract-row" key={c.name}>
                {c.passed ? (
                  <Check size={18} />
                ) : (
                  <X size={18} className="fail-text" />
                )}
                <div>
                  <strong>{c.name.replaceAll('_', ' ')}</strong>
                  <p>{c.detail}</p>
                </div>
                <span className={c.passed ? 'pass-text' : 'fail-text'}>
                  {c.passed ? 'Passed' : 'Failed'}
                </span>
              </div>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="code">
          <div className="console-code">
            <p>
              Run this exact configuration locally. The example uses the same
              Python package as this lab.
            </p>
            <div className="code-wrap">
              <CopyButton text={snippet} />
              <pre>
                <code>{snippet}</code>
              </pre>
            </div>
            <Link href="/docs">
              Wrap your own Python tools <ArrowRight size={15} />
            </Link>
          </div>
        </TabsContent>
      </Tabs>
      <details className="run-context">
        <summary>What this experiment measures</summary>
        <p>
          The fixture tries to ship one order. Inventory reads and shipment
          commits happen in memory. Three scripted policies receive the same
          fault rules; each runs independently. Timing is simulated by
          VirtualClock, so these values are not performance benchmarks.
        </p>
        <p>
          A passed contract means the recorded evidence met this scenario’s
          checks. It does not measure a language model or prove that a real
          service is safe. The export includes the configuration, calls,
          effects, checks, and digest from this result.
        </p>
        <p className="digest">
          ToolStorm {comparison.engine_version} · Report SHA-256{' '}
          <code>{run.digest}</code>
        </p>
      </details>
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
                {selected.injected
                  ? `Injected fault: ${selected.kind?.replaceAll('_', ' ')}.`
                  : 'No fault was injected.'}
              </DialogDescription>
              <div className="call-meta">
                <span>
                  Simulated start <b>{time(selected.started)}</b>
                </span>
                <span>
                  Simulated duration <b>{time(selected.elapsed)}</b>
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
    </section>
  );
}
