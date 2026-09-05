import base64
import uuid
from unittest.mock import MagicMock, patch

import boto3

from oya.prompts.meal import FoodItem, MealAnalysis
from oya.store.table import Entity, query_all
from tests.conftest import TEST_BUCKET_NAME

FAKE_ANALYSIS = MealAnalysis(
    items=[FoodItem(name="Grilled chicken", portion="about 6 oz", calories=280)],
    total_calories=650,
    protein_g=45.0,
    carbs_g=60.0,
    fat_g=18.0,
    confidence="medium",
    notes="Assumed grilled, not fried.",
)


def _mock_anthropic(parsed: MealAnalysis = FAKE_ANALYSIS):
    client = MagicMock()
    client.messages.parse.return_value = MagicMock(parsed_output=parsed)
    return client


def test_analyze_requires_photo_or_description(authed_client):
    res = authed_client.post("/api/meals/analyze", json={})
    assert res.status_code == 400


def test_analyze_with_description_only_returns_analysis_and_no_photo(authed_client):
    with patch("oya.api.meals.Anthropic", return_value=_mock_anthropic()):
        res = authed_client.post(
            "/api/meals/analyze", json={"description": "Chicken breast and rice"}
        )
    assert res.status_code == 200
    body = res.json()
    assert body["photo_id"] is None
    assert body["analysis"]["total_calories"] == 650
    assert body["analysis"]["items"][0]["name"] == "Grilled chicken"


def test_analyze_with_a_photo_uploads_it_and_returns_a_photo_id(authed_client):
    photo_bytes = b"fake-jpeg-bytes"
    photo_base64 = base64.b64encode(photo_bytes).decode()

    with patch("oya.api.meals.Anthropic", return_value=_mock_anthropic()):
        res = authed_client.post(
            "/api/meals/analyze", json={"photo_base64": photo_base64, "description": ""}
        )
    assert res.status_code == 200
    photo_id = res.json()["photo_id"]
    uuid.UUID(photo_id)  # does not raise

    s3 = boto3.client("s3", region_name="us-east-1")
    stored = s3.get_object(Bucket=TEST_BUCKET_NAME, Key=f"meals/{photo_id}.jpg")
    assert stored["Body"].read() == photo_bytes


def test_analyze_sanitizes_a_dirty_notes_field(authed_client):
    dirty = FAKE_ANALYSIS.model_copy(update={"notes": "Great job on this meal!"})
    with patch("oya.api.meals.Anthropic", return_value=_mock_anthropic(dirty)):
        res = authed_client.post("/api/meals/analyze", json={"description": "A meal"})
    assert res.json()["analysis"]["notes"] == "Estimate based on the photo and description."


def test_save_meal_writes_a_meal_entity(authed_client):
    res = authed_client.post(
        "/api/meals",
        json={"description": "Chicken and rice", "analysis": FAKE_ANALYSIS.model_dump()},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["total_calories"] == 650

    items = query_all(Entity.MEAL)
    assert len(items) == 1
    assert items[0]["description"] == "Chicken and rice"
    assert int(items[0]["total_calories"]) == 650


def test_save_meal_rejects_an_invalid_photo_id(authed_client):
    res = authed_client.post(
        "/api/meals",
        json={
            "photo_id": "../../etc/passwd",
            "description": "x",
            "analysis": FAKE_ANALYSIS.model_dump(),
        },
    )
    assert res.status_code == 400
    assert query_all(Entity.MEAL) == []


def test_today_meals_lists_what_was_saved(authed_client):
    authed_client.post(
        "/api/meals",
        json={"description": "Chicken and rice", "analysis": FAKE_ANALYSIS.model_dump()},
    )
    res = authed_client.get("/api/meals/today")
    assert res.status_code == 200
    body = res.json()
    assert len(body["meals"]) == 1
    assert body["meals"][0]["total_calories"] == 650
    # Fewer than 30 days of history -- the honesty rule applies to food
    # the same as every Garmin metric.
    assert body["calories"]["building"] is True


def test_get_photo_returns_the_stored_bytes(authed_client):
    photo_bytes = b"fake-jpeg-bytes"
    photo_base64 = base64.b64encode(photo_bytes).decode()
    with patch("oya.api.meals.Anthropic", return_value=_mock_anthropic()):
        analyze_res = authed_client.post(
            "/api/meals/analyze", json={"photo_base64": photo_base64}
        )
    photo_id = analyze_res.json()["photo_id"]

    res = authed_client.get(f"/api/meals/photo/{photo_id}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert res.content == photo_bytes


def test_get_photo_rejects_a_non_uuid_id(authed_client):
    res = authed_client.get("/api/meals/photo/not-a-uuid")
    assert res.status_code == 400


def test_get_photo_404s_for_an_unknown_id(authed_client):
    res = authed_client.get(f"/api/meals/photo/{uuid.uuid4()}")
    assert res.status_code == 404


def test_meals_endpoints_require_sign_in(client):
    assert client.post("/api/meals/analyze", json={"description": "x"}).status_code == 401
    assert (
        client.post(
            "/api/meals", json={"description": "x", "analysis": FAKE_ANALYSIS.model_dump()}
        ).status_code
        == 401
    )
    assert client.get("/api/meals/today").status_code == 401
    assert client.get(f"/api/meals/photo/{uuid.uuid4()}").status_code == 401
