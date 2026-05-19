import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.db.models import PendingAction, ProcessedEmail, SnoozedEmail, WorkflowTask


EXECUTABLE_ACTIONS = {
    "create_task",
    "snooze_thread",
    "draft_reply",
    "schedule_meeting",
}


def _payload_for(action: PendingAction) -> dict[str, Any]:
    if not action.payload:
        return {}
    try:
        return json.loads(action.payload)
    except json.JSONDecodeError:
        return {}


def _task_id(action: PendingAction) -> str:
    return f"task:{action.id}"


def _snooze_id(user_id: str, email_id: str) -> str:
    return f"{user_id}:{email_id}"


def execute_action(db: Session, action: PendingAction) -> dict[str, Any]:
    if action.status != "approved":
        raise ValueError("Action must be approved before execution.")

    if action.action_type not in EXECUTABLE_ACTIONS:
        raise ValueError(f"Action '{action.action_type}' is not executable yet.")

    payload = _payload_for(action)
    email_id = action.email_id or payload.get("email_id") or action.thread_id

    if action.action_type == "create_task":
        return _execute_create_task(db, action, payload, email_id)

    if action.action_type == "snooze_thread":
        return _execute_snooze_thread(db, action, payload, email_id)

    if action.action_type == "draft_reply":
        return _execute_draft_reply(db, action, payload, email_id)

    if action.action_type == "schedule_meeting":
        return _execute_schedule_meeting(db, action, payload, email_id)

    raise ValueError("Unsupported action.")


def _execute_create_task(
    db: Session,
    action: PendingAction,
    payload: dict[str, Any],
    email_id: str,
) -> dict[str, Any]:
    task = db.query(WorkflowTask).filter_by(id=_task_id(action)).first()
    if not task:
        task = WorkflowTask(
            id=_task_id(action),
            user_id=action.user_id,
            thread_id=action.thread_id,
            email_id=email_id,
            title=f"Follow up: {payload.get('topic') or action.thread_id}",
            status="open",
            source_action_id=action.id,
            created_at=datetime.utcnow(),
        )
        db.add(task)

    return {
        "message": "Task created.",
        "task": {
            "id": task.id,
            "title": task.title,
            "status": task.status,
        },
    }


def _execute_snooze_thread(
    db: Session,
    action: PendingAction,
    payload: dict[str, Any],
    email_id: str,
) -> dict[str, Any]:
    remind_at = datetime.utcnow() + timedelta(days=1)
    record_id = _snooze_id(action.user_id, email_id)

    db.query(SnoozedEmail).filter(
        SnoozedEmail.user_id == action.user_id,
        or_(SnoozedEmail.email_id == email_id, SnoozedEmail.id == email_id, SnoozedEmail.id == record_id),
    ).delete()

    db.merge(
        SnoozedEmail(
            id=record_id,
            user_id=action.user_id,
            email_id=email_id,
            remind_at=remind_at,
        )
    )

    processed = db.query(ProcessedEmail).filter_by(id=email_id).first()
    if not processed:
        processed = ProcessedEmail(id=email_id, user_id=action.user_id)
        db.add(processed)
    processed.action_bucket = "SNOOZED"

    return {
        "message": "Thread snoozed for tomorrow.",
        "remind_at": remind_at.isoformat(),
    }


def _execute_draft_reply(
    db: Session,
    action: PendingAction,
    payload: dict[str, Any],
    email_id: str,
) -> dict[str, Any]:
    return {
        "message": "Draft reply action is ready. Use Generate Reply in the thread to create the draft.",
        "email_id": email_id,
    }


def _execute_schedule_meeting(
    db: Session,
    action: PendingAction,
    payload: dict[str, Any],
    email_id: str,
) -> dict[str, Any]:
    return {
        "message": "Scheduling action is ready. Use Schedule / Event is Scheduled on the thread to confirm calendar details.",
        "email_id": email_id,
    }
