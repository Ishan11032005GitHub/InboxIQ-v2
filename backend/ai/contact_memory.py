import json
from datetime import datetime
from email.utils import parseaddr
from typing import Any

from sqlalchemy.orm import Session

from backend.db.models import ContactMemory, ThreadState


def _memory_id(user_id: str, sender_email: str) -> str:
    return f"{user_id}:{sender_email.lower()}"


def _parse_sender(sender: str | None) -> tuple[str, str]:
    name, email = parseaddr(sender or "")
    email = (email or sender or "unknown@inboxiq.local").strip().lower()
    display_name = (name or email).strip()
    return display_name, email


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []


def _thread_messages(email: dict[str, Any]) -> list[dict[str, Any]]:
    thread = email.get("conversation_thread")
    if isinstance(thread, str):
        try:
            thread = json.loads(thread)
        except json.JSONDecodeError:
            thread = None
    if isinstance(thread, list) and thread:
        return [message for message in thread if isinstance(message, dict)]
    return [{"role": "received", "sender": email.get("sender", ""), "body": email.get("body", "")}]


def _preferred_tone(label: str | None, priority: str | None) -> str:
    label = (label or "").lower()
    priority = (priority or "").lower()
    if priority == "high" or label in {"security", "work", "job alert"}:
        return "clear and professional"
    if label in {"newsletter", "notification", "promotion"}:
        return "brief and low-friction"
    return "warm and concise"


def update_contact_memory(
    db: Session,
    user_id: str,
    email: dict[str, Any],
    thread_state: ThreadState | None = None,
) -> ContactMemory | None:
    sender = email.get("sender")
    display_name, sender_email = _parse_sender(sender)
    if not sender_email or sender_email == "you":
        return None

    thread_id = (
        (thread_state.thread_id if thread_state else None)
        or email.get("thread_id")
        or email.get("threadId")
        or email.get("id")
    )
    if not thread_id:
        return None

    memory = db.query(ContactMemory).filter_by(id=_memory_id(user_id, sender_email)).first()
    if not memory:
        memory = ContactMemory(
            id=_memory_id(user_id, sender_email),
            user_id=user_id,
            sender_email=sender_email,
            display_name=display_name,
            interaction_count=0,
            thread_count=0,
            importance_score=0,
            recurring_topics=json.dumps([]),
            observed_thread_ids=json.dumps([]),
            last_contacted_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(memory)
        db.flush()

    observed_threads = set(_json_list(memory.observed_thread_ids))
    topics = _json_list(memory.recurring_topics)
    topic = (thread_state.topic if thread_state else None) or email.get("subject") or "Untitled thread"
    messages = _thread_messages(email)
    external_messages = [message for message in messages if (message.get("role") or "received") != "sent"]

    if thread_id not in observed_threads:
        observed_threads.add(thread_id)
        memory.interaction_count = float(memory.interaction_count or 0) + max(1, len(external_messages))
        if topic not in topics:
            topics.append(topic)

    urgency = float(thread_state.urgency_score or 0) if thread_state else 0
    priority_boost = 20 if (email.get("priority") or "").lower() == "high" else 0
    memory.display_name = display_name or memory.display_name
    memory.thread_count = float(len(observed_threads))
    memory.importance_score = min(100.0, max(float(memory.importance_score or 0), urgency + priority_boost))
    memory.preferred_tone = _preferred_tone(email.get("label"), email.get("priority"))
    memory.recurring_topics = json.dumps(topics[-8:])
    memory.observed_thread_ids = json.dumps(sorted(observed_threads))
    memory.last_contacted_at = datetime.utcnow()
    memory.updated_at = datetime.utcnow()
    memory.summary = (
        f"{memory.display_name or memory.sender_email} has appeared in {int(memory.thread_count or 0)} "
        f"thread(s). Preferred reply style: {memory.preferred_tone}."
    )
    return memory


def serialize_contact_memory(memory: ContactMemory | None) -> dict[str, Any] | None:
    if not memory:
        return None
    return {
        "id": memory.id,
        "sender_email": memory.sender_email,
        "display_name": memory.display_name,
        "interaction_count": int(memory.interaction_count or 0),
        "thread_count": int(memory.thread_count or 0),
        "importance_score": memory.importance_score or 0,
        "response_latency_hours": memory.response_latency_hours,
        "recurring_topics": _json_list(memory.recurring_topics),
        "preferred_tone": memory.preferred_tone,
        "summary": memory.summary,
        "last_contacted_at": memory.last_contacted_at.isoformat() if memory.last_contacted_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }
