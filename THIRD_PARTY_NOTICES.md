# Third-party notices

ToolStorm's Python core uses the Python standard library and has no runtime package dependencies.

The website was initialized with the OpenAI Sites starter and includes generated shadcn/Base UI components. These components and their dependencies retain their respective upstream licenses. Key projects include:

- [React](https://github.com/facebook/react) — MIT
- [Vinext](https://github.com/cloudflare/vinext) — MIT
- [shadcn/ui](https://github.com/shadcn-ui/ui) — MIT
- [Base UI](https://github.com/mui/base-ui) — MIT
- [Lucide](https://github.com/lucide-icons/lucide) — ISC
- [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) — MIT
- [Pyodide](https://github.com/pyodide/pyodide) — MPL-2.0, with additional licenses for its included runtime and packages
- [Geist fonts](https://github.com/vercel/geist-font) — SIL Open Font License 1.1

Pyodide is loaded as an external, unmodified browser runtime. Development/CI dependencies include pytest, Hypothesis, coverage.py, Ruff, mypy, Playwright, axe-core, and the Cloudflare toolchain. Consult each package's included license for the authoritative terms. The repository's MIT license applies to original ToolStorm code.
