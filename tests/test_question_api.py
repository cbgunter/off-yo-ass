from unittest.mock import MagicMock, patch

from oya.api.notes import NoteParse
from oya.store.table import Entity, put_item


def test_latest_question_is_none_when_nothing_generated_yet(authed_client):
    res = authed_client.get("/api/question/latest")
    assert res.status_code == 200
    assert res.json() is None


def test_latest_question_reports_unanswered(authed_client):
    put_item(Entity.QUESTION, "2026-06-14", {"question": "What's Thursday's problem?"})
    res = authed_client.get("/api/question/latest")
    body = res.json()
    assert body["question"] == "What's Thursday's problem?"
    assert body["week_ending"] == "2026-06-14"
    assert body["answered"] is False


def test_answering_marks_it_answered_and_stores_a_note(authed_client):
    put_item(Entity.QUESTION, "2026-06-14", {"question": "What's Thursday's problem?"})

    parsed = NoteParse(type="schedule", expires_in_days=30, pinned=False)
    mock_client = MagicMock()
    mock_client.messages.parse.return_value = MagicMock(parsed_output=parsed)

    with patch("oya.api.notes.Anthropic", return_value=mock_client):
        res = authed_client.post(
            "/api/question/answer", json={"text": "Thursday is late meetings."}
        )
    assert res.status_code == 204

    latest = authed_client.get("/api/question/latest").json()
    assert latest["answered"] is True

    notes = authed_client.get("/api/notes").json()
    assert any(n["text"] == "Thursday is late meetings." for n in notes)


def test_question_endpoints_require_sign_in(client):
    assert client.get("/api/question/latest").status_code == 401
    assert client.post("/api/question/answer", json={"text": "hi"}).status_code == 401
