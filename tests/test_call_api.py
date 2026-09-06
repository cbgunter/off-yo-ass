from unittest.mock import patch

from oya.clock import eastern_date
from oya.prompts.coach import CoachResponse, Prescription
from oya.store.table import Entity, get_latest, put_item, query_all

_CALL_FIELDS = {
    "headline": "Resting heart rate is 8 bpm over your 30-day average.",
    "prescription": {
        "activity": "walk",
        "duration_min": 30,
        "intensity": "easy",
        "window": "17:30-18:30",
    },
    "why": "Sleep was short.",
    "fallback": "A short walk works too.",
    "skip_ok": False,
    "overridden": False,
    "override_count": 0,
}

_FAKE_OVERRIDE = CoachResponse(
    headline="Stress is 15 points over your 30-day average.",
    prescription=Prescription(
        activity="row_c2", duration_min=20, intensity="easy", window="18:00-18:30"
    ),
    why="High stress, short sleep.",
    fallback="Ten minutes on the erg still counts.",
    skip_ok=False,
)


def _seed_today_call(overridden: bool = False, override_count: int = 0) -> str:
    today = eastern_date()
    put_item(
        Entity.CALL,
        today,
        {**_CALL_FIELDS, "overridden": overridden, "override_count": override_count},
    )
    return today


def test_call_today_is_none_when_nothing_generated_yet(authed_client):
    res = authed_client.get("/api/call/today")
    assert res.status_code == 200
    assert res.json() is None


def test_call_today_returns_the_stored_call(authed_client):
    _seed_today_call()
    res = authed_client.get("/api/call/today")
    body = res.json()
    assert body["headline"] == "Resting heart rate is 8 bpm over your 30-day average."
    assert body["prescription"]["activity"] == "walk"


def test_call_today_returns_the_most_recent_call_regardless_of_date(authed_client):
    """The standing call is whatever the coach wrote last -- it must stay
    on screen through the evening and into the next morning, not vanish
    when the calendar date rolls over."""
    put_item(Entity.CALL, "2026-09-01", {**_CALL_FIELDS, "headline": "Old call."})
    put_item(Entity.CALL, "2026-09-02", {**_CALL_FIELDS, "headline": "Newer call."})

    res = authed_client.get("/api/call/today")
    assert res.json()["headline"] == "Newer call."


def test_call_today_is_not_checked_in_before_a_response(authed_client):
    _seed_today_call()
    assert authed_client.get("/api/call/today").json()["checked_in"] is False


def test_call_today_reports_checked_in_after_a_checkin(authed_client):
    _seed_today_call()
    authed_client.post("/api/call/checkin", json={"result": "did_it"})
    assert authed_client.get("/api/call/today").json()["checked_in"] is True


def test_call_today_reports_checked_in_after_not_tonight(authed_client):
    _seed_today_call()
    authed_client.post("/api/call/not-tonight")
    assert authed_client.get("/api/call/today").json()["checked_in"] is True


def test_override_reopens_the_checkin(authed_client):
    _seed_today_call()
    authed_client.post("/api/call/checkin", json={"result": "no", "skip_reason": "too_tired"})

    with patch("oya.api.call.generate_call", return_value=_FAKE_OVERRIDE):
        assert authed_client.post("/api/call/override").json()["checked_in"] is False

    assert authed_client.get("/api/call/today").json()["checked_in"] is False


def test_bedtime_is_none_before_any_nudge(authed_client):
    assert authed_client.get("/api/call/bedtime").json() is None


def test_bedtime_returns_the_latest_nudge(authed_client):
    put_item(Entity.BEDTIME, "2026-09-01", {"body": "Old nudge."})
    put_item(Entity.BEDTIME, "2026-09-02", {"body": "First thing tomorrow is at 9:00."})

    res = authed_client.get("/api/call/bedtime")
    assert res.json()["body"] == "First thing tomorrow is at 9:00."


def test_checkin_writes_an_outcome(authed_client):
    res = authed_client.post("/api/call/checkin", json={"result": "did_it"})
    assert res.status_code == 204
    items = query_all(Entity.OUTCOME)
    assert len(items) == 1
    assert items[0]["result"] == "did_it"


def test_checkin_rejects_unknown_result(authed_client):
    res = authed_client.post("/api/call/checkin", json={"result": "kinda"})
    assert res.status_code == 400


def test_checkin_rejects_unknown_skip_reason(authed_client):
    res = authed_client.post(
        "/api/call/checkin", json={"result": "no", "skip_reason": "the_dog_ate_it"}
    )
    assert res.status_code == 400


def test_checkin_accepts_a_valid_skip_reason(authed_client):
    res = authed_client.post(
        "/api/call/checkin", json={"result": "no", "skip_reason": "too_tired"}
    )
    assert res.status_code == 204
    assert query_all(Entity.OUTCOME)[0]["skip_reason"] == "too_tired"


def test_feel_writes_an_entry(authed_client):
    res = authed_client.post("/api/call/feel", json={"feel": "brutal"})
    assert res.status_code == 204
    assert query_all(Entity.FEEL)[0]["feel"] == "brutal"


def test_feel_rejects_unknown_value(authed_client):
    res = authed_client.post("/api/call/feel", json={"feel": "meh"})
    assert res.status_code == 400


def test_not_tonight_records_an_override_outcome(authed_client):
    res = authed_client.post("/api/call/not-tonight")
    assert res.status_code == 204
    outcome = query_all(Entity.OUTCOME)[0]
    assert outcome["result"] == "no"
    assert outcome["skip_reason"] == "override"


def test_override_replaces_todays_call_without_a_real_claude_call(authed_client):
    today = _seed_today_call(overridden=False, override_count=0)

    with patch("oya.api.call.generate_call", return_value=_FAKE_OVERRIDE) as mock_generate:
        res = authed_client.post("/api/call/override")

    assert res.status_code == 200
    body = res.json()
    assert body["headline"] == "Stress is 15 points over your 30-day average."
    assert body["overridden"] is True

    # The original prescription's activity ("walk") was excluded from the
    # regeneration request -- confirms /override actually avoids repeating
    # the rejected suggestion, not just replacing the stored call.
    mock_generate.assert_called_once_with(exclude_activity="walk")

    stored = get_latest(Entity.CALL, sk=today)[0]
    assert stored["headline"] == "Stress is 15 points over your 30-day average."
    assert stored["overridden"] is True
    assert stored["override_count"] == 1


def test_call_endpoints_require_sign_in(client):
    assert client.get("/api/call/today").status_code == 401
    assert client.post("/api/call/checkin", json={"result": "did_it"}).status_code == 401
