import Link from 'next/link';
import type { Metadata } from 'next';
import {
  ArrowRight,
  ArrowUpRight,
  Braces,
  Clock3,
  Gauge,
  Radio,
  Timer,
  Unplug,
} from 'lucide-react';
import { SiteHeader, SiteFooter } from '@/components/site-header';
import catalog from '@/lib/catalog.json';
import type { Scenario } from '@/lib/types';
export const metadata: Metadata = { title: 'Failure recipes — ToolStorm' };
const icons = {
  radio: Radio,
  gauge: Gauge,
  braces: Braces,
  clock: Clock3,
  timer: Timer,
  unplug: Unplug,
};
export default function Recipes() {
  return (
    <>
      <SiteHeader active="recipes" />
      <main className="recipes-main">
        <p className="eyebrow">SIX WAYS TO RUIN A PERFECT DEMO</p>
        <h1>Pick your failure mode.</h1>
        <p className="doc-lede">
          Small, reproducible incidents with a point. Each recipe runs against
          the same shipping workflow and three recovery policies.
        </p>
        <div className="recipe-grid">
          {(Object.keys(catalog.scenarios) as Scenario[]).map((key) => {
            const s = catalog.scenarios[key],
              Icon = icons[s.icon as keyof typeof icons];
            return (
              <Link
                className="recipe-card"
                href={`/?scenario=${key}`}
                key={key}
              >
                <div>
                  <Icon size={25} />
                  <span className="eyebrow">{s.code}</span>
                  <ArrowUpRight size={17} />
                </div>
                <p className="eyebrow">{s.category}</p>
                <h2>{s.title}</h2>
                <p>{s.description}</p>
                <div className="recipe-lesson">
                  <strong>What this tests</strong>
                  <p>{s.lesson}</p>
                </div>
                <span className="recipe-open">
                  Open in the lab <ArrowRight size={16} />
                </span>
              </Link>
            );
          })}
        </div>
        <div className="recipe-bottom">
          <h2>Your edge case belongs here.</h2>
          <p>
            Add a scenario, a broken control, and a recovery contract. The
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
