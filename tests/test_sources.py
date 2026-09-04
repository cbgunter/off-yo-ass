from oya.store.table import Entity, put_item


def test_sources_default_to_not_connected(authed_client):
    res = authed_client.get("/api/sources")
    assert res.status_code == 200
    sources = {s["name"]: s for s in res.json()}

    assert sources["Garmin"]["status"] == "not_connected"
    assert sources["Garmin"]["last_synced"] is None
    for name in ("Google Calendar", "Weather", "Concept2", "Peloton"):
        assert sources[name]["status"] == "not_connected"


def test_sources_reports_garmin_as_connected_when_fresh(authed_client):
    put_item(
        Entity.SOURCE_HEALTH,
        "garmin",
        {"status": "fresh", "last_success": "2026-06-15T09:00:00+00:00", "notified_at": None},
    )

    res = authed_client.get("/api/sources")
    garmin = next(s for s in res.json() if s["name"] == "Garmin")

    assert garmin["status"] == "connected"
    assert garmin["last_synced"] == "2026-06-15T09:00:00+00:00"


def test_sources_reports_garmin_as_stale(authed_client):
    put_item(
        Entity.SOURCE_HEALTH,
        "garmin",
        {"status": "stale", "last_success": "2026-06-01T09:00:00+00:00", "notified_at": "x"},
    )

    res = authed_client.get("/api/sources")
    garmin = next(s for s in res.json() if s["name"] == "Garmin")
    assert garmin["status"] == "stale"


def test_sources_requires_sign_in(client):
    res = client.get("/api/sources")
    assert res.status_code == 401
