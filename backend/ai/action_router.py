"""
backend/ai/action_router.py

Assigns every email to one of five action buckets AFTER the AI pipeline
has run.  The bucket drives the UI badge and determines which follow-up
actions are offered to the user.

Buckets
-------
NEEDS_REPLY     – email is directed at you and expects a response
NEEDS_ACTION    – high-priority / work email with a task or deadline
NEEDS_MEETING   – meeting intent detected (will move to SCHEDULED after booking)
SCHEDULED       – meeting was successfully booked in Google Calendar
WAITING         – you sent a reply; waiting for the other side to respond
FYI_ONLY        – newsletter / promo / notification; no action required
"""

from typing import Literal

ActionBucket = Literal[
    "NEEDS_REPLY",
    "NEEDS_ACTION",
    "NEEDS_MEETING",
    "SCHEDULED",
    "WAITING",
    "FYI_ONLY",
]

# Labels that require no action from the user
_PASSIVE_LABELS = {"newsletter", "promotion", "job_alert", "event_invite", "notification"}

# Keywords that signal a concrete task or deadline inside the body / subject
_ACTION_KEYWORDS = {
    "deadline", "due", "asap", "urgent", "required", "action required",
    "complete", "submit", "approve", "review", "confirm", "invoice",
    "payment", "task", "deliverable", "by eod", "by cob",
}


def get_action_bucket(
    label: str,
    priority: str,
    is_meeting: bool,
    subject: str = "",
    body: str = "",
) -> ActionBucket:
    """
    Determine the action bucket for an email.

    Parameters
    ----------
    label       : category label from classifier (e.g. "work", "newsletter")
    priority    : "high" | "medium" | "low"
    is_meeting  : True when meeting_detector fired
    subject     : email subject (used for keyword scan)
    body        : email body   (used for keyword scan)

    Returns
    -------
    ActionBucket string
    """
    # 1. Passive content — no action needed
    if label in _PASSIVE_LABELS:
        return "FYI_ONLY"

    # 2. Meeting intent — will be promoted to SCHEDULED by the caller
    #    once the Calendar event is confirmed
    if is_meeting:
        return "NEEDS_MEETING"

    # 3. High-priority / action-keyword emails → NEEDS_ACTION
    text = f"{subject} {body}".lower()
    has_action_keyword = any(kw in text for kw in _ACTION_KEYWORDS)

    if priority == "high" or (label in {"work", "security"} and has_action_keyword):
        return "NEEDS_ACTION"

    # 4. Default — the email is waiting for a reply
    return "NEEDS_REPLY"


# Human-readable display metadata for the frontend
BUCKET_META = {
    "NEEDS_REPLY":   {"icon": "✉️",  "text": "Needs Reply",   "color": "#3b82f6"},
    "NEEDS_ACTION":  {"icon": "⚡",  "text": "Needs Action",  "color": "#ef4444"},
    "NEEDS_MEETING": {"icon": "📅",  "text": "Needs Meeting", "color": "#8b5cf6"},
    "SCHEDULED":     {"icon": "✅",  "text": "Scheduled",     "color": "#16a34a"},
    "WAITING":       {"icon": "⏳",  "text": "Waiting",       "color": "#f59e0b"},
    "FYI_ONLY":      {"icon": "👀",  "text": "FYI Only",      "color": "#6b7280"},
}