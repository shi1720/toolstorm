"""Generate browser package and executed fixture. Fail CI if they drift."""

from __future__ import annotations

import json
from pathlib import Path

from toolstorm.demo import POLICIES, SCENARIOS, run_comparison

ROOT = Path(__file__).resolve().parent.parent
files = {
    f"toolstorm/{p.name}": p.read_text()
    for p in sorted((ROOT / "src/toolstorm").glob("*.py"))
    if p.name not in {"pytest_plugin.py", "cli.py", "__main__.py"}
}
(ROOT / "public/engine.bundle.json").write_text(json.dumps(files, ensure_ascii=True))
(ROOT / "lib/catalog.json").write_text(
    json.dumps({"scenarios": SCENARIOS, "policies": POLICIES}, indent=2) + "\n"
)
(ROOT / "lib/default-run.json").write_text(json.dumps(run_comparison(), indent=2) + "\n")
print(f"Bundled {len(files)} Python modules and an executed comparison fixture.")
