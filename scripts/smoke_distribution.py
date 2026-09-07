"""Install each built distribution in a fresh environment, outside the checkout."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def smoke(artifact: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="toolstorm-install-") as directory:
        work = Path(directory)
        environment = work / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        clean = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", str(artifact.resolve())],
            cwd=work,
            env=clean,
            check=True,
        )
        code = """
import importlib.metadata as metadata
from pathlib import Path
import toolstorm
from toolstorm.demo import run_demo
assert str(Path(toolstorm.__file__).resolve()).startswith(str(Path('venv').resolve()))
distribution = metadata.distribution('toolstorm')
assert toolstorm.__version__ == distribution.version
assert not any('extra ==' not in requirement for requirement in (distribution.requires or []))
assert any(
    ep.group == 'pytest11' and ep.value == 'toolstorm.pytest_plugin'
    for ep in distribution.entry_points
)
result = run_demo('lost_ack', 'resilient')
assert result['contract']['passed'] and result['stats']['effects'] == 1
print('Installed package verified:', distribution.version)
"""
        subprocess.run([str(python), "-c", code], cwd=work, env=clean, check=True)
        subprocess.run(
            [str(python), "-m", "toolstorm", "demo", "--policy", "resilient", "--fail-on-contract"],
            cwd=work,
            env=clean,
            check=True,
        )


if __name__ == "__main__":
    artifacts = sorted(
        Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/python").glob("toolstorm-*")
    )
    if not artifacts:
        raise SystemExit("No built distributions found")
    for artifact in artifacts:
        if artifact.name.endswith((".whl", ".tar.gz")):
            smoke(artifact)
