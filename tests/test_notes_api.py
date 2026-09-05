from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from oya.api.notes import NoteParse
from oya.store.table import Entity, put_item


def _mock_anthropic(parsed: NoteParse):
    client = MagicMock()
    client.messages.parse.return_value = MagicMock(parsed_output=parsed)
    return client


def test_add_note_stores_a_temporary_note(authed_client):
    parsed = NoteParse(type="injury", expires_in_days=14, pinned=False)
    with patch("oya.api.notes.Anthropic", return_value=_mock_anthropic(parsed)):
        res = authed_client.post("/api/notes", json={"text": "Back is sore."})

    assert res.status_code == 201
    body = res.json()
    assert body["type"] == "injury"
    assert body["pinned"] is False
    assert body["expires_at"] is not None


def test_add_note_with_pin_never_expires(authed_client):
    parsed = NoteParse(type="preference", expires_in_days=0, pinned=True)
    with patch("oya.api.notes.Anthropic", return_value=_mock_anthropic(parsed)):
        res = authed_client.post("/api/notes", json={"text": "Never suggest golf as exercise."})

    assert res.json()["expires_at"] is None
    assert res.json()["pinned"] is True


def test_list_notes_excludes_expired_ones(authed_client):
    now = datetime.now(UTC)
    put_item(
        Entity.NOTE,
        (now - timedelta(days=20)).isoformat(),
        {
            "text": "Old sore back, long gone.",
            "type": "injury",
            "expires_at": (now - timedelta(days=6)).isoformat(),
            "pinned": False,
        },
    )
    put_item(
        Entity.NOTE,
        now.isoformat(),
        {
            "text": "Denver Tuesday to Thursday.",
            "type": "schedule",
            "expires_at": (now + timedelta(days=3)).isoformat(),
            "pinned": False,
        },
    )

    res = authed_client.get("/api/notes")
    texts = [n["text"] for n in res.json()]
    assert "Denver Tuesday to Thursday." in texts
    assert "Old sore back, long gone." not in texts


def test_list_notes_always_includes_pinned_notes(authed_client):
    put_item(
        Entity.NOTE,
        datetime.now(UTC).isoformat(),
        {"text": "Never suggest golf.", "type": "preference", "expires_at": None, "pinned": True},
    )
    res = authed_client.get("/api/notes")
    assert res.json()[0]["text"] == "Never suggest golf."


def test_notes_require_sign_in(client):
    assert client.get("/api/notes").status_code == 401
    assert client.post("/api/notes", json={"text": "hi"}).status_code == 401
