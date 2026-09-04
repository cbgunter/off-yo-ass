"""Google Sign-In, checked against one allowlisted email, backed by a signed
session cookie. There is no user table — there is exactly one user."""

import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel

from oya.settings import Settings, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class GoogleSignIn(BaseModel):
    id_token: str


class User(BaseModel):
    email: str
    name: str


def _issue_session_cookie(response: Response, user: User, settings: Settings) -> None:
    now = int(time.time())
    ttl_seconds = settings.session_ttl_days * 86400
    payload = {"sub": user.email, "name": user.name, "iat": now, "exp": now + ttl_seconds}
    token = jwt.encode(payload, settings.resolved_session_secret(), algorithm="HS256")
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=ttl_seconds,
        path="/",
    )


@router.post("/google")
def sign_in_with_google(
    body: GoogleSignIn,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> User:
    if not settings.google_client_id:
        raise HTTPException(500, "Google sign-in is not configured.")

    try:
        claims = google_id_token.verify_oauth2_token(
            body.id_token, google_requests.Request(), audience=settings.google_client_id
        )
    except ValueError as exc:
        raise HTTPException(401, "Could not verify Google sign-in.") from exc

    email = (claims.get("email") or "").lower()
    if not claims.get("email_verified") or email != settings.allowed_email.lower():
        # A real, verified Google account that isn't the one account this
        # app is locked to. Still a rejection, not a misconfiguration.
        raise HTTPException(403, "This app is locked to one account.")

    user = User(email=email, name=claims.get("name") or email)
    _issue_session_cookie(response, user, settings)
    return user


def get_current_user(request: Request, settings: Settings = Depends(get_settings)) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(401, "Not signed in.")
    try:
        claims = jwt.decode(token, settings.resolved_session_secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Session expired. Sign in again.") from exc
    return User(email=claims["sub"], name=claims.get("name", claims["sub"]))


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/sign-out", status_code=204)
def sign_out(response: Response, settings: Settings = Depends(get_settings)) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
