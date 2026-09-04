from unittest.mock import patch


def test_me_without_session_is_401(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_sign_in_rejects_a_real_but_unallowed_google_account(client):
    with patch("oya.api.auth.google_id_token.verify_oauth2_token") as verify:
        verify.return_value = {
            "email": "someone-else@gmail.com",
            "email_verified": True,
            "name": "Someone Else",
        }
        res = client.post("/api/auth/google", json={"id_token": "fake"})
    assert res.status_code == 403


def test_sign_in_rejects_unverified_email(client):
    with patch("oya.api.auth.google_id_token.verify_oauth2_token") as verify:
        verify.return_value = {
            "email": "cbgunter@gmail.com",
            "email_verified": False,
            "name": "Casey",
        }
        res = client.post("/api/auth/google", json={"id_token": "fake"})
    assert res.status_code == 403


def test_sign_in_accepts_allowed_email_and_sets_session(client):
    with patch("oya.api.auth.google_id_token.verify_oauth2_token") as verify:
        verify.return_value = {
            "email": "cbgunter@gmail.com",
            "email_verified": True,
            "name": "Casey",
        }
        res = client.post("/api/auth/google", json={"id_token": "fake"})
    assert res.status_code == 200
    assert res.json() == {"email": "cbgunter@gmail.com", "name": "Casey"}

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "cbgunter@gmail.com"


def test_sign_out_clears_the_session(client):
    with patch("oya.api.auth.google_id_token.verify_oauth2_token") as verify:
        verify.return_value = {
            "email": "cbgunter@gmail.com",
            "email_verified": True,
            "name": "Casey",
        }
        client.post("/api/auth/google", json={"id_token": "fake"})

    res = client.post("/api/auth/sign-out")
    assert res.status_code == 204

    me = client.get("/api/auth/me")
    assert me.status_code == 401
