import Link from 'next/link';
import { ArrowUpRight, CodeXml, Zap } from 'lucide-react';

export function SiteHeader({
  active = 'lab',
}: {
  active?: 'lab' | 'docs' | 'recipes';
}) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link href="/" className="brand" aria-label="ToolStorm home">
          <span className="brand-icon">
            <Zap size={22} fill="currentColor" />
          </span>
          <span>
            toolstorm<span className="brand-dot">.</span>
          </span>
          <span className="version">v0.1.0</span>
        </Link>
        <nav aria-label="Main navigation">
          <Link href="/" aria-current={active === 'lab' ? 'page' : undefined}>
            The lab
          </Link>
          <Link
            href="/recipes"
            aria-current={active === 'recipes' ? 'page' : undefined}
          >
            Recipes
          </Link>
          <Link
            href="/docs"
            aria-current={active === 'docs' ? 'page' : undefined}
          >
            Documentation
          </Link>
        </nav>
        <a
          className="github-link"
          href="https://github.com/shi1720/toolstorm"
          target="_blank"
          rel="noreferrer"
        >
          <CodeXml size={17} />
          <span>GitHub</span>
          <ArrowUpRight size={15} />
        </a>
      </div>
    </header>
  );
}
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <span>
        <Zap size={14} /> Made for the days your tools aren’t.
      </span>
      <span>
        Python ≥3.10 <i /> MIT license <i />{' '}
        <a href="https://github.com/shi1720/toolstorm">
          Open source <ArrowUpRight size={13} />
        </a>
      </span>
    </footer>
  );
}
