import os
import logging
from datetime import datetime, timedelta

from backend.db import db

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from streamlit import user
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Cookie, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.auth.google_auth import (
    get_authorization_data,
    exchange_code_for_credentials,
    get_gmail_service,
    load_credentials,
    load_demo_credentials,
    save_credentials,
    get_current_user,
    MOCK_USER,
)

from backend.gmail.gmail_utils import get_unread_emails, send_email
from backend.ai.gemini_utils import process_inbox, generate_reply
from backend.ai.meeting_detector import detect_meeting_intent
from backend.ai.datetime_extractor import extract_datetime
from backend.ai.action_router import get_action_bucket, BUCKET_META   # ← Tier-1
from backend.calendar.calendar_utils import create_calendar_event
from backend.memory.followup_tracker import create_followup_reminder   # ← Tier-1
from backend.memory.feedback_store import save_feedback

from backend.db.database import engine, SessionLocal
from backend.db.models import Base, ProcessedEmail, User
from backend.db.models import SnoozedEmail
from backend.db.database import SessionLocal

from backend.session import create_session, get_user_from_session

from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# ALLOWED_ORIGINS = [
#     "https://inbox-iq-xi.vercel.app",  # prod frontend
#     "http://localhost:3000",            # local dev
#     "http://localhost:5500",            # live server dev
# ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# IN-MEMORY EMAIL CACHE
# ---------------------------------------------------------------------------
email_cache: dict = {}

MOCK_EMAILS = [
    {
        "id": "1",
        "subject": "Quick sync",
        "body": "Hey, are you free tomorrow at 5 PM for a call?",
        "sender": "john@example.com",
    },
    {
        "id": "2",
        "subject": "Invoice attached",
        "body": "Please find the invoice for last month.",
        "sender": "finance@example.com",
    },
    {
        "id": "3",
        "subject": "Team Standup Meeting",
        "body": "Hi, let's schedule a quick standup tomorrow at 3 PM to discuss the sprint progress. Please confirm your availability.",
        "sender": "manager@example.com",
    },
]


# ---------------------------------------------------------------------------
# DB INIT
# ---------------------------------------------------------------------------
@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created / verified.")


# ---------------------------------------------------------------------------
# DEMO LOGIN
# ---------------------------------------------------------------------------
@app.get("/demo")
def demo_login():
    session_id = create_session("demo-user")
    response   = JSONResponse({"message": "Demo mode activated"})
    response.set_cookie(key="session_id",value=session_id,httponly=True,samesite="lax",secure=False,max_age=86400)
    return response


# ---------------------------------------------------------------------------
# AUTH STATUS
# ---------------------------------------------------------------------------
@app.get("/auth/status")
def auth_status(session_id: str = Cookie(default=None)):
    if not session_id:
        return {"authenticated": False}
    user_id = get_user_from_session(session_id)
    if not user_id:
        return {"authenticated": False}
    if user_id == "demo-user":
        return {"authenticated": True, "user": "demo-user"}
    creds = load_credentials(user_id)
    return {"authenticated": creds is not None, "user": user_id}


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------
@app.get("/auth/login")
def login():
    data          = get_authorization_data()
    auth_url      = data["auth_url"]
    state         = data["state"]
    code_verifier = data.get("code_verifier") or ""

    logger.info("LOGIN | state=%s | verifier_present=%s", state, bool(code_verifier))

    response = RedirectResponse(url=auth_url)
    response.set_cookie(key="oauth_state",         value=state,         httponly=True, secure=False, samesite="lax", path="/", max_age=600)
    response.set_cookie(key="oauth_code_verifier", value=code_verifier, httponly=True, secure=False, samesite="lax", path="/", max_age=600)
    return response


# ---------------------------------------------------------------------------
# CALLBACK
# ---------------------------------------------------------------------------
@app.get("/auth/callback")
def auth_callback(
    request: Request,
    oauth_state: str         = Cookie(default=None),
    oauth_code_verifier: str = Cookie(default=None),
):
    logger.info("CALLBACK | url=%s", str(request.url))

    if not oauth_state:
        raise HTTPException(400, "oauth_state cookie missing.")
    if not oauth_code_verifier:
        raise HTTPException(400, "oauth_code_verifier cookie missing.")

    try:
        creds = exchange_code_for_credentials(
            authorization_response_url=str(request.url),
            state=oauth_state,
            code_verifier=oauth_code_verifier,
        )

        oauth2_service = build("oauth2", "v2", credentials=creds)
        user_info      = oauth2_service.userinfo().get().execute()
        email: str     = user_info["email"]
        logger.info("CALLBACK | email=%s", email)

        save_credentials(email, creds)
        session_id = create_session(email)

        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500/frontend/index.html")
        response = RedirectResponse(url=frontend_url)
        response.set_cookie(key="session_id",value=session_id,httponly=True,samesite="lax",secure=False,max_age=86400)
        response.delete_cookie("oauth_state",         path="/")
        response.delete_cookie("oauth_code_verifier", path="/")
        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("CALLBACK | failed: %s", exc)
        raise HTTPException(500, f"OAuth failed: {exc}")


# ---------------------------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------------------------
@app.post("/auth/logout")
def logout():
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("session_id",          path="/")
    response.delete_cookie("oauth_state",         path="/")
    response.delete_cookie("oauth_code_verifier", path="/")
    return response


# ---------------------------------------------------------------------------
# GET EMAILS
# ---------------------------------------------------------------------------
@app.get("/emails")
def get_emails(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]

    if user_id == "demo-user":
        emails = [dict(e) for e in MOCK_EMAILS]
    else:
        creds = load_credentials(user_id)
        if not creds:
            raise HTTPException(status_code=401, detail="Not authenticated")

        service = get_gmail_service(creds)
        payload = get_unread_emails(service)

        try:
            emails = process_inbox(payload["emails"])
        except:
            emails = payload["emails"]

    # cache
    for e in emails:
        email_cache[e["id"]] = e

    db = SessionLocal()

    # ✅ LOAD PROCESSED STATE
    processed = db.query(ProcessedEmail).filter(
        ProcessedEmail.user_id == user_id
    ).all()

    processed_map = {p.id: p for p in processed}

    # APPLY STATE
    for e in emails:
        if e["id"] in processed_map:
            p = processed_map[e["id"]]
            e["action_bucket"] = p.action_bucket
            if p.reply:
                e["reply"] = p.reply

    # ✅ CRITICAL FIX: FILTER SNOOZED EMAILS
    snoozed = db.query(SnoozedEmail).filter(
        SnoozedEmail.user_id == user_id,
        SnoozedEmail.remind_at > datetime.now()
    ).all()

    snoozed_ids = set(s.id for s in snoozed)

    active_emails = [e for e in emails if e["id"] not in snoozed_ids]

    db.close()

    return {"emails": active_emails}


@app.post("/email/unsnooze")
async def unsnooze(request: Request, user: dict = Depends(get_current_user)):
    data = await request.json()
    email_id = data.get("id")

    db = SessionLocal()
    db.query(SnoozedEmail).filter_by(id=email_id).delete()
    db.commit()
    db.close()

    return {"status": "unsnoozed"}


# ---------------------------------------------------------------------------
# HELPER — resolve credentials
# ---------------------------------------------------------------------------
def _resolve_credentials(user_id: str):
    if user_id == "demo-user":
        creds = load_demo_credentials()
        if not creds:
            logger.warning("_resolve_credentials | DEMO_GOOGLE_CREDENTIALS not set")
        return creds
    return load_credentials(user_id)


# ---------------------------------------------------------------------------
# INTELLIGENT EMAIL PIPELINE
# ---------------------------------------------------------------------------
@app.post("/email/process")
async def process_email(request: Request, user: dict = Depends(get_current_user)):

    data = await request.json()
    email_id = data.get("id")

    if email_id not in email_cache:
        raise HTTPException(status_code=404, detail="Email not found")

    email = email_cache[email_id]

    label = email.get("label", "general")
    priority = email.get("priority", "low")

    intent = detect_meeting_intent(email["subject"], email["body"])
    dt = extract_datetime(email["subject"] + " " + email["body"])

    # ----------------------
    # CALENDAR
    # ----------------------
    if intent["is_meeting"] and dt["found"]:
        creds = _resolve_credentials(user["user_id"])

        start_iso = dt["datetime"]
        end_iso = (datetime.fromisoformat(start_iso) + timedelta(hours=1)).isoformat()

        event = create_calendar_event(
            credentials=creds,
            summary=email["subject"],
            start_datetime=start_iso,
            end_datetime=end_iso,
        )

        if event["success"]:

            # ✅ FIXED DB SAVE
            db = SessionLocal()

            existing = db.query(ProcessedEmail).filter_by(
                id=email_id,
                user_id=user["user_id"]
            ).first()

            if existing:
                existing.action_bucket = "SCHEDULED"
            else:
                db.add(ProcessedEmail(
                    id=email_id,
                    user_id=user["user_id"],
                    action_bucket="SCHEDULED"
                ))

            db.commit()
            db.close()

            return {
                "type": "calendar",
                "status": "done",
                "action_bucket": "SCHEDULED",
                "bucket_meta": BUCKET_META["SCHEDULED"],
            }

    # ----------------------
    # REPLY
    # ----------------------
    try:
        reply = generate_reply(email, "professional")
    except Exception as e:
        logger.error(f"Gemini failed: {e}")
        reply = "⚠️ AI reply unavailable right now. Please try again."
        
    bucket = get_action_bucket(label, priority, False, email["subject"], email["body"])

    # ✅ SAVE REPLY
    db = SessionLocal()

    existing = db.query(ProcessedEmail).filter_by(
        id=email_id,
        user_id=user["user_id"]
    ).first()

    if existing:
        existing.reply = reply
        existing.action_bucket = bucket
    else:
        db.add(ProcessedEmail(
            id=email_id,
            user_id=user["user_id"],
            action_bucket=bucket,
            reply=reply
        ))

    db.commit()
    db.close()

    return {
        "type": "reply",
        "status": "done",
        "reply": reply,
        "action_bucket": bucket,
        "bucket_meta": BUCKET_META[bucket],
    }


# ---------------------------------------------------------------------------
# SEND EMAIL  + auto follow-up reminder
# ---------------------------------------------------------------------------
@app.post("/send-email")
async def send(request: Request, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    data = await request.json()

    if user.get("user_id") == "demo-user":
        # Still create a follow-up reminder on the demo calendar
        creds = _resolve_credentials("demo-user")
        if creds:
            create_followup_reminder(
                credentials=creds,
                original_subject=data.get("subject", "(no subject)"),
                sender_email=data.get("to", ""),
                hours=48,
                timezone=os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata"),
            )
        return {"status": "sent (demo)", "followup_scheduled": creds is not None}

    creds   = load_credentials(user_id)
    service = get_gmail_service(creds)
    send_email(service, data["to"], data["subject"], data["body"])

    # ── Follow-up Tracker ────────────────────────────────────────────────
    # After every sent reply, schedule a 48-hour follow-up reminder so the
    # user is nudged if there's no response.
    followup_result = create_followup_reminder(
        credentials=creds,
        original_subject=data.get("subject", "(no subject)"),
        sender_email=data.get("to", ""),
        hours=48,
        timezone=os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata"),
    )

    return {
        "status":             "sent",
        "followup_scheduled": followup_result["success"],
        "followup_link":      followup_result.get("event_link"),
    }


# ---------------------------------------------------------------------------
# SNOOZE  — defer an email by creating a Calendar reminder
# ---------------------------------------------------------------------------
# ---------------------- SNOOZE FIX ----------------------
@app.get("/emails/snoozed")
def get_snoozed_emails(user: dict = Depends(get_current_user)):
    db = SessionLocal()

    snoozed = db.query(SnoozedEmail).filter(
        SnoozedEmail.user_id == user["user_id"]
    ).all()

    result = []

    for s in snoozed:
        if s.id in email_cache:
            email = dict(email_cache[s.id])
            email["remind_at"] = s.remind_at.isoformat()
            result.append(email)

    db.close()

    return {"emails": result}

@app.post("/email/snooze")
async def snooze_email(request: Request, user: dict = Depends(get_current_user)):
    data = await request.json()

    email_id = data.get("id")
    duration = data.get("duration")

    if email_id not in email_cache:
        raise HTTPException(status_code=404, detail="Email not found")

    now = datetime.now()

    if duration == "3h":
        remind_at = now + timedelta(hours=3)
    elif duration == "tomorrow":
        remind_at = (now + timedelta(days=1)).replace(hour=9, minute=0)
    elif duration == "next_week":
        remind_at = (now + timedelta(weeks=1)).replace(hour=9, minute=0)
    else:
        remind_at = now + timedelta(hours=3)

    db = SessionLocal()

    existing = db.query(SnoozedEmail).filter_by(
        id=email_id,
        user_id=user["user_id"]
    ).first()

    if existing:
        existing.remind_at = remind_at
    else:
        db.add(SnoozedEmail(
            id=email_id,
            user_id=user["user_id"],
            remind_at=remind_at
        ))

    db.commit()
    db.close()

    return {
        "status": "snoozed",
        "remind_at": remind_at.isoformat()
    }


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=10000, reload=True)

