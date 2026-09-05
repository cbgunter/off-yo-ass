#!/usr/bin/env python3
"""One-time Google Calendar OAuth setup. Opens your browser to Google's
consent screen, catches the redirect locally, exchanges the code for a
refresh token, and uploads it to SSM. No password typed anywhere -- you
approve access in your own browser, on your own Google account, once.

Before running this:
  1. In Google Cloud Console, on the OAuth client from phase 0, add
     http://localhost:8080/oauth2callback as an authorized redirect URI.
  2. Push the OAuth consent screen to Production (calendar.readonly isn't
     in the safe-scope list, so a Testing-status app would issue a
     refresh token that expires in 7 days). It can stay unverified --
     that's a warning screen you click through once, as the sole user.
  3. The client secret needs to already be in SSM -- that's a separate,
     one-time step done outside this script.

Usage (from the repo root, using the project's own venv):
    uv run python scripts/bootstrap_calendar.py
"""

from __future__ import annotations

import http.server
import threading
import urllib.parse
import webbrowser

import boto3
import requests

from oya.settings import get_settings

# Public by design -- the same value already baked into the web app's
# built JS bundle, not a secret.
GOOGLE_CLIENT_ID = "958261457576-n3osu30n59d0on6osif5p8go7ufil3p7.apps.googleusercontent.com"

REDIRECT_URI = "http://localhost:8080/oauth2callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None

    def do_GET(self) -> None:
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _CallbackHandler.code = params.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<p>Done. You can close this tab and go back to your terminal.</p>")

    def log_message(self, log_format: str, *args: object) -> None:
        pass  # quiet -- no need to echo every request to the terminal


def _get_authorization_code() -> str:
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    print("Opening your browser to Google's consent screen...")
    print(f"If it doesn't open automatically, visit:\n  {url}\n")
    webbrowser.open(url)

    thread.join(timeout=120)
    if not _CallbackHandler.code:
        raise SystemExit("No authorization code received within 2 minutes.")
    return _CallbackHandler.code


def main() -> None:
    settings = get_settings()
    client_secret = settings.resolved_google_client_secret()

    code = _get_authorization_code()

    response = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    response.raise_for_status()
    refresh_token = response.json().get("refresh_token")
    if not refresh_token:
        raise SystemExit(
            "No refresh token in the response. If you've authorized this app before, "
            "revoke it at https://myaccount.google.com/permissions and try again -- "
            "Google only issues a refresh token on the first consent."
        )

    ssm = boto3.client("ssm")
    ssm.put_parameter(
        Name=settings.google_refresh_token_param,
        Value=refresh_token,
        Type="SecureString",
        Overwrite=True,
    )
    print(f"Done. Refresh token stored in SSM at {settings.google_refresh_token_param}.")


if __name__ == "__main__":
    main()
