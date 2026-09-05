"""Today's food totals against the user's own 30-day average -- the same
honesty rule oya/domain/baselines.py already applies to Garmin recovery
metrics, aimed at eating instead. Reuses compute_baseline() and the
MetricSnapshot shape from oya/domain/recovery.py verbatim, so the
dashboard, the API, and the coach all read one number.

Recovery metrics are one row per day, so oya/domain/recovery.py's
_metric_snapshot can split "history, then today" directly off a query.
Food is several rows a day, so this module aggregates by day first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from oya.domain.baselines import Baseline, compute_baseline
from oya.domain.recovery import MetricSnapshot
from oya.store.table import Entity, query_range

# Unlike Garmin's dense daily sync, food logging will have real gaps --
# a missed meal, a day nobody bothered. compute_baseline needs 30 *logged*
# days, so the lookback has to be wider than 30 calendar days or a single
# gap would make a full baseline permanently unreachable.
BASELINE_WINDOW_DAYS = 60


@dataclass(frozen=True)
class Meal:
    when: str
    description: str
    photo_id: str | None
    items: list[dict]
    total_calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    confidence: str
    notes: str


@dataclass(frozen=True)
class FoodSnapshot:
    calories: MetricSnapshot
    meals: list[Meal]


def _to_meal(item: dict) -> Meal:
    return Meal(
        when=item["sk"],
        description=item.get("description", ""),
        photo_id=item.get("photo_id"),
        items=[dict(i) for i in item.get("items", [])],
        total_calories=int(item.get("total_calories", 0)),
        protein_g=float(item.get("protein_g", 0)),
        carbs_g=float(item.get("carbs_g", 0)),
        fat_g=float(item.get("fat_g", 0)),
        confidence=item.get("confidence", "low"),
        notes=item.get("notes", ""),
    )


def _daily_totals(items: list[dict]) -> dict[str, float]:
    """sk is an ISO timestamp -- its first 10 characters are the date."""
    totals: dict[str, float] = {}
    for item in items:
        day = item["sk"][:10]
        totals[day] = totals.get(day, 0.0) + float(item.get("total_calories", 0))
    return totals


def get_food_snapshot(today: date | None = None) -> FoodSnapshot:
    today = today or datetime.now(UTC).date()
    start = today - timedelta(days=BASELINE_WINDOW_DAYS)
    # query_range's `between` is a string comparison against a full ISO
    # timestamp -- using today's own date as the end would exclude every
    # meal logged today (any time-of-day suffix sorts after the bare
    # date), so the end has to be the *next* day instead.
    end = today + timedelta(days=1)

    items = query_range(Entity.MEAL, start.isoformat(), end.isoformat())

    today_str = today.isoformat()
    todays_meals = [_to_meal(i) for i in items if i["sk"][:10] == today_str]

    daily_totals = _daily_totals(items)
    todays_total = daily_totals.pop(today_str, 0.0)
    # Days with no logged meals are excluded entirely, never counted as
    # zero -- an unlogged day is missing data, not a fast. Averaging zeros
    # in would drag the baseline down and make every honestly logged day
    # look inflated by comparison, which is worse than no number at all.
    history = list(daily_totals.values())

    result = compute_baseline(todays_total if todays_meals else None, history)

    if isinstance(result, Baseline):
        calories = MetricSnapshot(
            label="Calories",
            unit="cal",
            today=result.today,
            average=result.average,
            delta=result.delta,
            delta_pct=result.delta_pct,
            days=result.days,
            building=False,
        )
    else:
        calories = MetricSnapshot(
            label="Calories",
            unit="cal",
            today=result.today,
            average=None,
            delta=None,
            delta_pct=None,
            days=result.days,
            building=True,
        )

    return FoodSnapshot(calories=calories, meals=todays_meals)
