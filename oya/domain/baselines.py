"""30-day baseline math. Pure logic, no I/O — the most heavily tested
module in the app, per the honesty rule in BRANDING.md: a baseline without
enough history must say so, never fabricate a delta against a handful of
points.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_DAYS = 30


@dataclass(frozen=True)
class Baseline:
    """A real baseline: enough history to trust the delta."""

    today: float
    average: float
    delta: float
    days: int

    @property
    def delta_pct(self) -> float | None:
        if self.average == 0:
            return None
        return (self.delta / self.average) * 100


@dataclass(frozen=True)
class BuildingBaseline:
    """Not enough history yet. The honest state, not a special case —
    every caller has to handle this alongside Baseline."""

    today: float | None
    days: int
    needed: int = MIN_DAYS


def compute_baseline(
    today: float | None, history: list[float], *, min_days: int = MIN_DAYS
) -> Baseline | BuildingBaseline:
    """`history` is prior values (today not included), already windowed by
    the caller to whatever period the baseline should cover — this
    function only decides whether there's *enough* of it, it doesn't do
    any windowing itself.
    """
    days = len(history)

    if today is None or days < min_days:
        return BuildingBaseline(today=today, days=days, needed=min_days)

    average = sum(history) / days
    return Baseline(today=today, average=average, delta=today - average, days=days)
