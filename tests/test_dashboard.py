from datetime import date, timedelta

from oya.store.table import Entity, put_item


def _write_days(entity: str, field: str, values: dict[int, float]) -> None:
    """`values` maps "days ago" -> value. 0 is today."""
    today = date.today()
    for days_ago, value in values.items():
        day = (today - timedelta(days=days_ago)).isoformat()
        put_item(entity, day, {field: value})


def test_dashboard_reports_building_with_no_history(authed_client):
    res = authed_client.get("/api/dashboard")
    assert res.status_code == 200
    body = res.json()

    for key in ("sleep", "resting_heart_rate", "hrv", "stress", "body_battery", "steps", "weight"):
        metric = body[key]
        assert metric["building"] is True
        assert metric["today"] is None
        assert metric["days"] == 0

    assert body["blood_pressure"] is None


def test_dashboard_reports_building_with_partial_history(authed_client):
    # 10 days including today is well short of the 30-day minimum.
    _write_days(Entity.RHR, "bpm", {i: 60.0 for i in range(10)})

    res = authed_client.get("/api/dashboard")
    metric = res.json()["resting_heart_rate"]

    assert metric["building"] is True
    assert metric["today"] == 60.0
    assert metric["days"] == 9  # today excluded from the history count


def test_dashboard_computes_a_real_baseline_at_30_days(authed_client):
    # 30 days of prior history at 60 bpm (the minimum), plus today at 68.
    values = {i: 60.0 for i in range(1, 31)}
    values[0] = 68.0
    _write_days(Entity.RHR, "bpm", values)

    res = authed_client.get("/api/dashboard")
    metric = res.json()["resting_heart_rate"]

    assert metric["building"] is False
    assert metric["today"] == 68.0
    assert metric["average"] == 60.0
    assert metric["delta"] == 8.0
    assert metric["days"] == 30


def test_dashboard_blood_pressure_reports_trend(authed_client):
    authed_client.post("/api/quicklog/bp", json={"systolic": 130, "diastolic": 85})
    authed_client.post("/api/quicklog/bp", json={"systolic": 122, "diastolic": 80})

    res = authed_client.get("/api/dashboard")
    bp = res.json()["blood_pressure"]

    assert bp["systolic"] == 122
    assert bp["diastolic"] == 80
    assert bp["delta_systolic"] == -8
    assert bp["delta_diastolic"] == -5


def test_dashboard_requires_sign_in(client):
    res = client.get("/api/dashboard")
    assert res.status_code == 401
