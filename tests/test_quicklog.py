from oya.store.table import Entity, query_all


def test_log_activity_writes_an_activity_item(authed_client):
    res = authed_client.post(
        "/api/quicklog/activity", json={"activity_type": "wood_splitting", "duration_min": 45}
    )
    assert res.status_code == 204

    items = query_all(Entity.ACTIVITY)
    assert len(items) == 1
    assert items[0]["activity_type"] == "wood_splitting"
    assert items[0]["duration_min"] == 45
    assert items[0]["source"] == "manual"


def test_log_activity_rejects_an_unknown_type(authed_client):
    res = authed_client.post(
        "/api/quicklog/activity", json={"activity_type": "nap", "duration_min": 20}
    )
    assert res.status_code == 400
    assert query_all(Entity.ACTIVITY) == []


def test_log_bp_writes_a_bp_item(authed_client):
    res = authed_client.post("/api/quicklog/bp", json={"systolic": 118, "diastolic": 76})
    assert res.status_code == 204

    items = query_all(Entity.BP)
    assert len(items) == 1
    assert items[0]["systolic"] == 118
    assert items[0]["diastolic"] == 76


def test_quicklog_requires_sign_in(client):
    res = client.post(
        "/api/quicklog/activity", json={"activity_type": "yard_work", "duration_min": 30}
    )
    assert res.status_code == 401
