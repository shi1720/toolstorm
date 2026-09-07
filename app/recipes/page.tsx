import Link from 'next/link';
import type { Metadata } from 'next';
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { SiteHeader, SiteFooter } from '@/components/site-header';
import catalog from '@/lib/catalog.json';
import type { Scenario } from '@/lib/types';
export const metadata: Metadata = { title: 'Failure scenarios — ToolStorm' };
export default function Recipes() {
  return (
    <>
      <SiteHeader active="recipes" />
      <main id="main" className="recipes-main">
        <p className="eyebrow">SCENARIO REFERENCE</p>
        <h1>Six failures worth testing.</h1>
        <p className="doc-lede">
          Each scenario isolates a different recovery problem. All six run
          against the same shipping workflow and three recovery policies.
        </p>
        <div className="recipe-grid">
          {(Object.keys(catalog.scenarios) as Scenario[]).map((key) => {
            const s = catalog.scenarios[key];
            return (
              <Link
                className="recipe-card"
                href={`/?scenario=${key}`}
                key={key}
              >
                <span className="recipe-number">{s.code}</span>
                <div>
                  <h2>{s.title}</h2>
                  <p>{s.description}</p>
                  <span className="recipe-open">
                    Open in the lab <ArrowRight size={16} />
                  </span>
                </div>
                <div className="recipe-lesson">
                  <strong>What this tests</strong>
                  <p>{s.lesson}</p>
                </div>
              </Link>
            );
          })}
        </div>
        <div className="recipe-bottom">
          <h2>Contribute a reproducible failure.</h2>
          <p>
            Add a scenario, a failing baseline, and a recovery contract. The
            library and browser lab share the same Python source.
          </p>
          <a href="https://github.com/shi1720/toolstorm/blob/main/CONTRIBUTING.md">
            Contribution guide <ArrowUpRight size={16} />
          </a>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
