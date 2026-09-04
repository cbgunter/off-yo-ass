from datetime import UTC, datetime, timedelta

from oya.domain.source_health import evaluate

NOW = datetime(2026, 6, 15, 8, 0, tzinfo=UTC)


def test_fresh_within_budget():
    check = evaluate(
        "garmin", last_success=NOW - timedelta(hours=10), already_notified=False, now=NOW
    )
    assert check.status == "fresh"
    assert check.should_notify is False


def test_stale_beyond_budget_notifies_once():
    check = evaluate(
        "garmin", last_success=NOW - timedelta(hours=40), already_notified=False, now=NOW
    )
    assert check.status == "stale"
    assert check.should_notify is True
    assert check.message is not None
    assert "36" in check.message


def test_stale_does_not_renotify_once_already_notified():
    check = evaluate(
        "garmin", last_success=NOW - timedelta(hours=72), already_notified=True, now=NOW
    )
    assert check.status == "stale"
    assert check.should_notify is False


def test_never_synced_is_stale():
    check = evaluate("garmin", last_success=None, already_notified=False, now=NOW)
    assert check.status == "stale"
    assert check.should_notify is True


def test_exactly_at_budget_boundary_is_not_yet_stale():
    check = evaluate(
        "garmin", last_success=NOW - timedelta(hours=36), already_notified=False, now=NOW
    )
    assert check.status == "fresh"
