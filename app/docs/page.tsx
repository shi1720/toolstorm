import Link from 'next/link';
import type { Metadata } from 'next';
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Code2,
  FileJson,
  GitBranch,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { SiteHeader, SiteFooter } from '@/components/site-header';
import { CopyButton } from '@/components/copy-button';
export const metadata: Metadata = { title: 'Quickstart — ToolStorm' };
const install =
  'pip install "toolstorm @ git+https://github.com/shi1720/toolstorm.git@v0.1.0"';
const sample = `from toolstorm import Storm, Rule, Contract, ResponseLost, VirtualClock\n\nstorm = Storm(\n    [Rule("lost-ack", "ship", "response_lost", calls=(1,))],\n    seed=42, clock=VirtualClock(),\n)\nshipments = []\nreceipts = {}\n\n@storm.tool("ship")\ndef ship(order: str, key: str):\n    if key in receipts:\n        return receipts[key]\n    shipments.append(order)\n    storm.effect("shipment", order)  # At the actual commit.\n    receipts[key] = {"id": len(shipments)}\n    return receipts[key]\n\ntry:\n    ship("order-1729", key="order-1729")\nexcept ResponseLost:\n    ship("order-1729", key="order-1729")\n\nContract(storm.report())\\\n    .require_triggered()\\\n    .no_duplicate_effects()\\\n    .assert_valid()`;
const replay = `from toolstorm import Cassette\n\nCassette.from_report(storm.report()).save("incident.json")\n\nwith Cassette.load("incident.json").replay() as replay:\n    offline_ship = replay.tool("ship")(ship)\n    try:\n        offline_ship("order-1729", key="order-1729")\n    except ResponseLost:\n        offline_ship("order-1729", key="order-1729")\n# Wrapped live code was never called. Unused calls fail on exit.`;
const kinds = [
  ['timeout', 'Before', 'Skips the tool and raises ToolTimeout.'],
  ['rate_limit', 'Before', 'Skips execution; RateLimited carries retry_after.'],
  ['unavailable', 'Before', 'Skips the tool and raises ToolUnavailable.'],
  [
    'replace',
    'Instead',
    'Returns your JSON payload without executing the tool.',
  ],
  ['latency', 'Before', 'Adds an explicit delay, then executes once.'],
  [
    'response_lost',
    'After',
    'Executes once; drops a successful acknowledgement.',
  ],
];
function Code({ children }: { children: string }) {
  return (
    <div className="doc-code">
      <CopyButton text={children} />
      <pre>
        <code>{children}</code>
      </pre>
    </div>
  );
}
export default function Docs() {
  return (
    <>
      <SiteHeader active="docs" />
      <main className="docs-main">
        <aside className="docs-nav">
          <p className="eyebrow">DOCUMENTATION</p>
          <a href="#quickstart">Quickstart</a>
          <a href="#first-test">Your first recovery test</a>
          <a href="#faults">Fault semantics</a>
          <a href="#replay">Strict offline replay</a>
          <a href="#guarantees">Guarantees & boundaries</a>
          <a href="https://github.com/shi1720/toolstorm/tree/main/docs">
            Full reference <ArrowUpRight size={13} />
          </a>
        </aside>
        <article className="docs-article">
          <p className="eyebrow">
            <BookOpen size={13} /> THE FIELD GUIDE
          </p>
          <h1>
            Make failure
            <br />
            part of the test.
          </h1>
          <p className="doc-lede">
            ToolStorm wraps the tools your agent already uses. You choose the
            failure. Your application decides how to recover. Contracts check
            the evidence.
          </p>
          <section id="quickstart">
            <h2>Up and running in a minute.</h2>
            <p>
              Requires Python 3.10 or newer. The core library has no runtime
              dependencies. Install the tagged release directly from GitHub:
            </p>
            <Code>{install}</Code>
            <p>
              The package is distributed through GitHub for this release; it is
              not published to PyPI.
            </p>
            <Code>
              {
                'toolstorm demo --scenario lost_ack --policy all\n\n# Check one recovery policy in CI:\ntoolstorm demo --policy resilient --fail-on-contract'
              }
            </Code>
            <div className="doc-note">
              <Zap size={18} />
              <span>
                The optimist cannot confirm the shipment. The retry enthusiast
                creates two. The realist retries with the same key and creates
                one.
              </span>
            </div>
          </section>
          <section id="first-test">
            <h2>A write happened. The response didn’t.</h2>
            <p>
              Record the effect where your test service commits it. Reusing the
              same idempotency key turns a retry into a receipt lookup. Change
              the second key to reproduce the duplicate-write bug.
            </p>
            <Code>{sample}</Code>
            <p>
              <code>require_triggered()</code> makes an unvisited or misspelled
              fault fail the test. <code>no_duplicate_effects()</code> checks
              observed commits, not successful tool responses.
            </p>
          </section>
          <section id="faults">
            <h2>Six faults. Explicit semantics.</h2>
            <p>
              Rule order matters: the first eligible probability hit wins. Call
              filters are 1-based per tool. Replacement faults skip live
              execution; lost acknowledgements happen after a successful return.
            </p>
            <div className="doc-table-wrap">
              <table className="doc-table">
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Phase</th>
                    <th>Behavior</th>
                  </tr>
                </thead>
                <tbody>
                  {kinds.map((r) => (
                    <tr key={r[0]}>
                      {r.map((v, i) => (
                        <td key={i}>{i === 0 ? <code>{v}</code> : v}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              <code>VirtualClock</code> skips waiting and tracks requested
              delays. The default <code>RealClock</code> performs real sleeps.
              Neither imposes a live tool deadline: a synthetic timeout is an
              injected failure.
            </p>
          </section>
          <section id="replay">
            <h2>Keep the incident. Lose the dependency.</h2>
            <p>
              A cassette contains redacted, signature-bound calls and returned
              results. Replay supplies those observations in order and never
              falls through to a wrapped live tool.
            </p>
            <Code>{replay}</Code>
            <div className="doc-note">
              <ShieldCheck size={18} />
              <span>
                Extra calls, changed arguments, incomplete captures, and unused
                entries fail. Unrecognized exceptions become RecordedToolError;
                exception text is omitted.
              </span>
            </div>
            <p>
              Replay stubs tool boundaries. It does not re-run their effects or
              reproduce the model’s internal decisions. Redacted credentials
              intentionally compare equal; provide the same Redactor and use
              nonsecret effect identifiers.
            </p>
          </section>
          <section id="guarantees">
            <h2>Clear boundaries make better tests.</h2>
            <div className="guarantee-grid">
              {[
                [
                  GitBranch,
                  'Deterministic fault decisions',
                  'A fixed seed and tool invocation sequence produce the same fault decisions. Explicit keys stabilize probability draws across scheduling changes.',
                ],
                [
                  ShieldCheck,
                  'Explicit side-effect evidence',
                  'Your fixture records commits with storm.effect(). ToolStorm cannot discover arbitrary writes or prevent side effects outside wrapped tools.',
                ],
                [
                  FileJson,
                  'Bounded, inspectable artifacts',
                  'Versioned JSON, no pickle or dynamic imports. Internal consistency checks validate a trace; they do not authenticate its author.',
                ],
                [
                  Code2,
                  'Framework neutral',
                  'Wrap functions before registering them with an agent. Sync and async functions are supported; streaming and generator tools are not.',
                ],
              ].map(([Icon, title, description]) => {
                const I = Icon as typeof Code2;
                return (
                  <div key={String(title)}>
                    <I size={20} />
                    <h3>{String(title)}</h3>
                    <p>{String(description)}</p>
                  </div>
                );
              })}
            </div>
            <p>
              ToolStorm is a beta developer test library, not a production
              traffic proxy, process sandbox, or guarantee of agent safety. Use
              simulated services or isolated test environments when executing
              side-effecting tools.
            </p>
          </section>
          <Link className="doc-next" href="/recipes">
            <span>
              <small>NEXT UP</small>Choose your failure mode.
            </span>
            <ArrowRight size={24} />
          </Link>
        </article>
      </main>
      <SiteFooter />
    </>
  );
}
