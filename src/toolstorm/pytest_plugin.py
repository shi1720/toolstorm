"""Optional pytest fixture, discovered only when pytest loads its plugins."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import Any

import pytest

from .contracts import Contract
from .engine import Storm
from .faults import Rule


@pytest.fixture
def storm_factory() -> Iterator[Callable[..., Storm]]:
    """Make isolated storms; verify every configured fault fired at teardown.

    Pass require_triggered=False for probabilistic campaigns or baseline tests.
    All other behavioral contracts are explicit assertions owned by the test.
    """
    runs: list[tuple[Storm, bool]] = []

    def factory(
        rules: Sequence[Rule] = (), *, require_triggered: bool = True, **kwargs: Any
    ) -> Storm:
        storm = Storm(rules, **kwargs)
        runs.append((storm, require_triggered))
        return storm

    yield factory
    for storm, required in runs:
        if required and storm.rules:
            Contract(storm.report()).require_triggered().assert_valid()
