import json
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.db.models import ProcessedEmail, ThreadState


VALID_STATUSES = {
    "awaiting_user",
    "awaiting_external",
    "action_required",
    "followup_required",
    "stalled",
    "resolved",
}

ACTION_KEYWORDS = {
    "approve",
    "asap",
    "confirm",
    "deadline",
    "due",
    "invoice",
    "payment",
    "review",
    "submit",
    "urgent",
}


def _thread_id_for(email: dict[str, Any]) -> str:
    return email.get("thread_id") or email.get("threadId") or email.get("id") or "unknown-thread"


def _state_id(user_id: str, thread_id: str) -> str:
    return f"{user_id}:{thread_id}"


def _messages_for(email: dict[str, Any]) -> list[dict[str, Any]]:
    thread = email.get("conversation_thread")
    if isinstance(thread, str):
        try:
            thread = json.loads(thread)
        except json.JSONDecodeError:
            thread = None

    if isinstance(thread, list) and thread:
        return [message for message in thread if isinstance(message, dict)]

    return [
        {
            "role": "received",
            "sender": email.get("sender", "Unknown"),
            "subject": email.get("subject", ""),
            "body": email.get("body", ""),
        }
    ]


def _topic_for(email: dict[str, Any], messages: list[dict[str, Any]]) -> str:
    subject = email.get("subject") or ""
    if not subject and messages:
        subject = messages[-1].get("subject") or ""
    subject = re.sub(r"^\s*(re|fw|fwd):\s*", "", subject, flags=re.I)
    return subject.strip() or "Untitled thread"


def _participants_for(messages: list[dict[str, Any]]) -> list[str]:
    participants = []
    seen = set()
    for message in messages:
        sender = (message.get("sender") or "").strip()
        if sender and sender not in seen:
            seen.add(sender)
            participants.append(sender)
    return participants


def _summarize(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return ""

    first = messages[0].get("body", "") or ""
    last = messages[-1].get("body", "") or ""
    if first == last:
        summary = first
    else:
        summary = f"Initial: {first}\n\nLatest: {last}"
    return re.sub(r"\s+", " ", summary).strip()[:900]


def _entities_for(text: str) -> dict[str, list[str]]:
    return {
        "emails": sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)))[:10],
        "urls": sorted(set(re.findall(r"https?://\S+", text)))[:10],
        "dates": sorted(set(re.findall(r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b", text, flags=re.I)))[:10],
    }


def _infer_status(
    email: dict[str, Any],
    processed: ProcessedEmail | None,
    text: str,
) -> tuple[str, str | None, float, datetime | None, datetime | None, float]:
    bucket = (processed.action_bucket if processed else None) or email.get("action_bucket")
    priority = (email.get("priority") or "low").lower()
    needs_meeting = bool(email.get("needs_meeting"))
    reply_sent_at = processed.reply_sent_at if processed and processed.reply_sent_at else None

    if bucket == "SCHEDULED":
        return "resolved", None, 35.0, None, None, 0.9

    if bucket == "SNOOZED":
        return "followup_required", "snooze_thread", 45.0, None, None, 0.8

    if processed and processed.reply_sent:
        followup_due = reply_sent_at + timedelta(days=2) if reply_sent_at else None
        if followup_due and followup_due <= datetime.utcnow():
            return "followup_required", "send_followup", 70.0, reply_sent_at, followup_due, 0.85
        return "awaiting_external", None, 40.0, reply_sent_at, followup_due, 0.85

    has_action_keyword = any(keyword in text for keyword in ACTION_KEYWORDS)
    has_question = "?" in text or any(phrase in text for phrase in ("can you", "could you", "please", "let me know"))

    if needs_meeting or bucket == "NEEDS_MEETING":
        return "action_required", "schedule_meeting", 72.0, None, None, 0.82

    if priority == "high" or bucket == "NEEDS_ACTION" or has_action_keyword:
        return "action_required", "create_task", 80.0, None, None, 0.78

    if bucket in {"FYI_ONLY", "SCHEDULED"}:
        return "resolved", None, 20.0, None, None, 0.72

    if has_question or bucket == "NEEDS_REPLY":
        return "awaiting_user", "draft_reply", 58.0, None, None, 0.74

    return "awaiting_user", "draft_reply", 45.0, None, None, 0.62


def update_thread_state(
    db: Session,
    user_id: str,
    email: dict[str, Any],
    processed: ProcessedEmail | None = None,
) -> ThreadState:
    thread_id = _thread_id_for(email)
    messages = _messages_for(email)
    topic = _topic_for(email, messages)
    participants = _participants_for(messages)
    combined_text = " ".join(
        f"{message.get('subject', '')} {message.get('body', '')}"
        for message in messages
    ).lower()

    status, pending_action, urgency, waiting_since, followup_due, confidence = _infer_status(
        email=email,
        processed=processed,
        text=combined_text,
    )
    if status not in VALID_STATUSES:
        status = "awaiting_user"

    state = db.query(ThreadState).filter_by(id=_state_id(user_id, thread_id)).first()
    if not state:
        state = ThreadState(id=_state_id(user_id, thread_id), user_id=user_id, thread_id=thread_id)
        db.add(state)

    state.topic = topic
    state.participants = json.dumps(participants)
    state.current_status = status
    state.pending_action = pending_action
    state.urgency_score = urgency
    state.waiting_since = waiting_since
    state.followup_due = followup_due
    state.confidence_score = confidence
    state.summarized_context = _summarize(messages)
    state.extracted_entities = json.dumps(_entities_for(combined_text))
    state.updated_at = datetime.utcnow()

    return state


def serialize_thread_state(state: ThreadState | None) -> dict[str, Any] | None:
    if not state:
        return None

    def parse_json(value: str | None, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback

    return {
        "thread_id": state.thread_id,
        "topic": state.topic,
        "participants": parse_json(state.participants, []),
        "current_status": state.current_status,
        "pending_action": state.pending_action,
        "urgency_score": state.urgency_score,
        "waiting_since": state.waiting_since.isoformat() if state.waiting_since else None,
        "followup_due": state.followup_due.isoformat() if state.followup_due else None,
        "confidence_score": state.confidence_score,
        "summarized_context": state.summarized_context,
        "extracted_entities": parse_json(state.extracted_entities, {}),
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }
