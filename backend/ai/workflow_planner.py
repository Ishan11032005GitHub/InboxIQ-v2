import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.db.models import ExecutionLog, PendingAction
from backend.db.models import WorkflowTask


RISK_BY_ACTION = {
    "draft_reply": "medium",
    "schedule_meeting": "medium",
    "send_followup": "high",
    "snooze_thread": "low",
    "create_task": "low",
    "escalate_thread": "high",
    "label_email": "low",
    "archive_email": "medium",
}


def _action_id(user_id: str, thread_id: str, action_type: str) -> str:
    return f"{user_id}:{thread_id}:{action_type}"


def _thread_state(email: dict[str, Any]) -> dict[str, Any]:
    state = email.get("thread_state")
    return state if isinstance(state, dict) else {}


def _proposal_for(email: dict[str, Any]) -> dict[str, Any] | None:
    state = _thread_state(email)
    status = state.get("current_status")
    pending_action = state.get("pending_action")
    confidence = float(state.get("confidence_score") or 0.6)
    urgency = float(state.get("urgency_score") or 0)

    if status == "resolved":
        return None

    action_type = pending_action
    if not action_type:
        if status == "awaiting_user":
            action_type = "draft_reply"
        elif status == "followup_required":
            action_type = "send_followup"
        elif status == "action_required":
            action_type = "create_task"

    if not action_type:
        return None

    topic = state.get("topic") or email.get("subject") or "this thread"
    reasoning = (
        f"Thread '{topic}' is {status.replace('_', ' ') if status else 'active'}"
        f" with urgency {round(urgency)} and confidence {round(confidence * 100)}%."
    )

    if action_type == "schedule_meeting":
        reasoning = f"Meeting intent detected in '{topic}'. Suggest scheduling before the thread stalls."
    elif action_type == "draft_reply":
        reasoning = f"Thread '{topic}' appears to be awaiting your response. Suggest drafting a contextual reply."
    elif action_type == "send_followup":
        reasoning = f"Thread '{topic}' is waiting externally and follow-up is due or likely useful."
    elif action_type == "create_task":
        reasoning = f"Thread '{topic}' contains action-oriented language. Suggest creating a task for tracking."

    return {
        "action_type": action_type,
        "reasoning": reasoning,
        "confidence_score": confidence,
        "risk_level": RISK_BY_ACTION.get(action_type, "medium"),
        "payload": {
            "email_id": email.get("id"),
            "thread_id": state.get("thread_id") or email.get("thread_id") or email.get("id"),
            "topic": topic,
            "status": status,
            "urgency_score": urgency,
        },
    }


def propose_action_for_email(db: Session, user_id: str, email: dict[str, Any]) -> PendingAction | None:
    proposal = _proposal_for(email)
    if not proposal:
        return None

    thread_id = proposal["payload"]["thread_id"]
    action_type = proposal["action_type"]
    action_id = _action_id(user_id, thread_id, action_type)

    existing = db.query(PendingAction).filter_by(id=action_id).first()
    if existing:
        if existing.status in {"pending", "approved", "executed"}:
            return existing
        existing.status = "pending"
        existing.reasoning = proposal["reasoning"]
        existing.confidence_score = proposal["confidence_score"]
        existing.risk_level = proposal["risk_level"]
        existing.payload = json.dumps(proposal["payload"])
        existing.created_at = datetime.utcnow()
        return existing

    action = PendingAction(
        id=action_id,
        user_id=user_id,
        thread_id=thread_id,
        email_id=email.get("id"),
        action_type=action_type,
        reasoning=proposal["reasoning"],
        confidence_score=proposal["confidence_score"],
        risk_level=proposal["risk_level"],
        status="pending",
        payload=json.dumps(proposal["payload"]),
        created_at=datetime.utcnow(),
    )
    db.add(action)
    return action


def serialize_pending_action(action: PendingAction) -> dict[str, Any]:
    try:
        payload = json.loads(action.payload) if action.payload else {}
    except json.JSONDecodeError:
        payload = {}

    return {
        "id": action.id,
        "user_id": action.user_id,
        "thread_id": action.thread_id,
        "email_id": action.email_id,
        "action_type": action.action_type,
        "reasoning": action.reasoning,
        "confidence_score": action.confidence_score,
        "risk_level": action.risk_level,
        "status": action.status,
        "payload": payload,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "executed_at": action.executed_at.isoformat() if action.executed_at else None,
    }


def serialize_workflow_task(task: WorkflowTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "user_id": task.user_id,
        "thread_id": task.thread_id,
        "email_id": task.email_id,
        "title": task.title,
        "status": task.status,
        "source_action_id": task.source_action_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def log_action_event(
    db: Session,
    user_id: str,
    action: PendingAction,
    status: str,
    message: str,
) -> ExecutionLog:
    log = ExecutionLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        thread_id=action.thread_id,
        action_id=action.id,
        action_type=action.action_type,
        status=status,
        message=message,
        created_at=datetime.utcnow(),
    )
    db.add(log)
    return log
