'use client';
import type { MouseEvent } from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import { version, repository } from '@/lib/product';
// Home starts a fresh experiment, including drafts that never changed route props.
function resetHome(event: MouseEvent<HTMLAnchorElement>) {
  if (
    window.location.pathname === '/' &&
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  ) {
    event.preventDefault();
    window.location.assign('/');
  }
}
export function SiteHeader({
  active = 'lab',
}: {
  active?: 'lab' | 'docs' | 'recipes';
}) {
  return (
    <header className="site-header">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="header-inner">
        <Link
          href="/"
          className="brand"
          onClick={resetHome}
          aria-label="ToolStorm home"
        >
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          ToolStorm<span className="version">{version}</span>
        </Link>
        <nav aria-label="Main navigation">
          {(
            [
              ['lab', '/', 'Lab'],
              ['recipes', '/recipes', 'Scenarios'],
              ['docs', '/docs', 'Documentation'],
            ] as const
          ).map(([id, href, label]) => (
            <Link
              key={id}
              href={href}
              onClick={id === 'lab' ? resetHome : undefined}
              aria-current={active === id ? 'page' : undefined}
            >
              {label}
            </Link>
          ))}
        </nav>
        <a
          className="github-link"
          href={repository}
          target="_blank"
          rel="noreferrer"
        >
          GitHub <ArrowUpRight size={16} />
        </a>
      </div>
    </header>
  );
}
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <span>ToolStorm · Python tool testing</span>
      <span>
        Python ≥3.10 <span aria-hidden="true">/</span> MIT licensed{' '}
        <a href={repository}>
          Source <ArrowUpRight size={14} />
        </a>
      </span>
    </footer>
  );
}
