import os
import json
import logging

from fastapi import HTTPException, Cookie, Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

from dotenv import load_dotenv
load_dotenv()

from backend.db.db import SessionLocal
from backend.db.models import User
from backend.session import get_user_from_session

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

MOCK_USER = {
    "user_id": "demo-user",
    "email": "demo@inboxiq.com",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _get_redirect_uri() -> str:
    uri = os.getenv("REDIRECT_URI", "http://127.0.0.1:10000/auth/callback")
    logger.debug("REDIRECT_URI = %s", uri)
    return uri


def _get_client_config() -> dict:
    return {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_get_redirect_uri()],
        }
    }


# ---------------------------------------------------------------------------
# create_flow
# ---------------------------------------------------------------------------

def create_flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=_get_redirect_uri(),
        state=state,
    )
    logger.debug("Flow created | state=%s | redirect_uri=%s", state, _get_redirect_uri())
    return flow


# ---------------------------------------------------------------------------
# get_authorization_data
# ---------------------------------------------------------------------------

def get_authorization_data() -> dict:
    flow = create_flow()

    auth_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
    )

    code_verifier: str | None = getattr(flow, "code_verifier", None)

    logger.info("Authorization URL generated | state=%s", state)
    logger.debug("auth_url=%s", auth_url)
    logger.debug(
        "PKCE | code_verifier present=%s | verifier=%s",
        code_verifier is not None,
        code_verifier,
    )

    return {
        "auth_url": auth_url,
        "state": state,
        "code_verifier": code_verifier,
    }


# ---------------------------------------------------------------------------
# exchange_code_for_credentials
# ---------------------------------------------------------------------------

def exchange_code_for_credentials(
    authorization_response_url: str,
    state: str,
    code_verifier: str | None = None,
) -> Credentials:
    flow = create_flow(state=state)

    if code_verifier:
        flow.code_verifier = code_verifier
        logger.debug("PKCE | code_verifier restored onto flow")
    else:
        logger.warning("PKCE | code_verifier cookie is empty – token exchange may fail.")

    logger.debug(
        "Exchanging code | state=%s | response_url=%s",
        state,
        authorization_response_url,
    )

    flow.fetch_token(authorization_response=authorization_response_url)

    creds = flow.credentials

    logger.debug(
        "Token response | token_present=%s | refresh_token_present=%s | expiry=%s",
        bool(creds.token),
        bool(creds.refresh_token),
        creds.expiry,
    )

    if not creds or not creds.token:
        raise ValueError(
            "Token exchange completed but access token is empty. "
            "Check GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / REDIRECT_URI."
        )

    return creds


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def save_credentials(user_id: str, creds: Credentials) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id, email=user_id)
        user.tokens = creds.to_json()
        db.add(user)
        db.commit()
        logger.debug("Credentials saved for user=%s", user_id)
    finally:
        db.close()


def load_credentials(user_id: str) -> Credentials | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.tokens:
            logger.warning("No stored credentials for user=%s", user_id)
            return None

        creds = Credentials.from_authorized_user_info(
            json.loads(user.tokens), SCOPES
        )

        if creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token for user=%s", user_id)
            creds.refresh(GoogleRequest())
            save_credentials(user_id, creds)

        return creds
    finally:
        db.close()


# ---------------------------------------------------------------------------
# load_demo_credentials
# ---------------------------------------------------------------------------

def load_demo_credentials():
    raw = os.getenv("DEMO_GOOGLE_CREDENTIALS")
    if not raw:
        return None

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_current_user(session_id: str = Cookie(default=None)) -> dict:
    if not session_id:
        raise HTTPException(status_code=401, detail="No session cookie")

    session = get_user_from_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return session


# ---------------------------------------------------------------------------
# Service builders
# ---------------------------------------------------------------------------

def get_gmail_service(credentials: Credentials):
    return build("gmail", "v1", credentials=credentials)
