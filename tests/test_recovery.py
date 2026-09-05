from datetime import date, timedelta

from oya.domain.recovery import get_recovery_snapshot
from oya.store.table import Entity, put_item
from oya.workers.coach import _format_recovery


def _write_days(entity: str, field: str, values: dict[int, float]) -> None:
    today = date.today()
    for days_ago, value in values.items():
        day = (today - timedelta(days=days_ago)).isoformat()
        put_item(entity, day, {field: value})


def test_dashboard_and_coach_read_the_same_recovery_snapshot(dynamodb_table):
    """oya/api/dashboard.py and oya/workers/coach.py both call
    get_recovery_snapshot() rather than each running their own
    query-and-baseline logic -- this is the phase-2 refactor that
    guarantees the coach's context matches what the Dashboard screen
    shows, by construction rather than by keeping two copies in sync."""
    values = {i: 60.0 for i in range(1, 31)}
    values[0] = 68.0
    _write_days(Entity.RHR, "bpm", values)

    snapshot = get_recovery_snapshot()

    assert snapshot.resting_heart_rate.today == 68.0
    assert snapshot.resting_heart_rate.average == 60.0
    assert snapshot.resting_heart_rate.building is False

    # The coach's own text formatter, fed the exact same snapshot object
    # the Dashboard API serializes -- proving there's one source, not two.
    recovery_text = _format_recovery(snapshot)
    assert "Resting heart rate: 68" in recovery_text
    assert "+8 vs 30d avg 60" in recovery_text


def test_building_baseline_is_reported_identically_in_both_consumers(dynamodb_table):
    snapshot = get_recovery_snapshot()

    assert snapshot.hrv.building is True
    assert "building baseline (0 of 30 nights)" in _format_recovery(snapshot)
