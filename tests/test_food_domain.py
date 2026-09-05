from datetime import date, timedelta

from oya.domain.food import get_food_snapshot
from oya.store.table import Entity, put_item

TODAY = date(2026, 9, 5)


def _log(days_ago: int, calories: float, *, today: date = TODAY, hour: int = 12) -> None:
    when = today - timedelta(days=days_ago)
    put_item(
        Entity.MEAL,
        f"{when.isoformat()}T{hour:02d}:00:00+00:00",
        {
            "description": "test meal",
            "photo_id": None,
            "items": [],
            "total_calories": calories,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "confidence": "high",
            "notes": "",
        },
    )


def test_building_baseline_when_nothing_logged_today(dynamodb_table):
    snapshot = get_food_snapshot(TODAY)
    assert snapshot.calories.building is True
    assert snapshot.calories.today is None
    assert snapshot.meals == []


def test_building_baseline_with_meals_today_but_not_enough_history(dynamodb_table):
    _log(0, 1800)
    snapshot = get_food_snapshot(TODAY)
    assert snapshot.calories.building is True
    assert snapshot.calories.today == 1800
    assert len(snapshot.meals) == 1


def test_full_baseline_after_30_days_of_history(dynamodb_table):
    for days_ago in range(1, 31):
        _log(days_ago, 2000)
    _log(0, 1500)

    snapshot = get_food_snapshot(TODAY)

    assert snapshot.calories.building is False
    assert snapshot.calories.today == 1500
    assert snapshot.calories.average == 2000
    assert snapshot.calories.delta == -500
    assert snapshot.calories.days == 30


def test_unlogged_days_are_excluded_from_history_not_counted_as_zero(dynamodb_table):
    # 30 logged days, spread across a 34-day window with 4 days skipped
    # entirely -- if those gaps were ever averaged in as zero, the average
    # below would come out under 2000. This only fits because the lookback
    # window is wider than the 30-day threshold -- see BASELINE_WINDOW_DAYS.
    logged_days = [d for d in range(1, 35) if d not in (5, 12, 20, 33)]
    assert len(logged_days) == 30
    for days_ago in logged_days:
        _log(days_ago, 2000)
    _log(0, 2000)

    snapshot = get_food_snapshot(TODAY)

    assert snapshot.calories.building is False
    assert snapshot.calories.days == 30
    assert snapshot.calories.average == 2000
    assert snapshot.calories.delta == 0


def test_multiple_meals_in_one_day_are_summed_for_the_baseline(dynamodb_table):
    for days_ago in range(1, 31):
        _log(days_ago, 1000, hour=8)
        _log(days_ago, 1000, hour=18)
    _log(0, 2000)

    snapshot = get_food_snapshot(TODAY)

    assert snapshot.calories.average == 2000
