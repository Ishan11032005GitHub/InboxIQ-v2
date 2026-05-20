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

ACTION_SCHEMAS = {
    "draft_reply": {
        "required": ["email_id", "thread_id"],
        "execution_mode": "human_initiated",
        "verification": "Draft can be generated from the selected thread before sending.",
    },
    "schedule_meeting": {
        "required": ["email_id", "thread_id"],
        "execution_mode": "human_confirmed",
        "verification": "Calendar event must be explicitly confirmed by the user.",
    },
    "send_followup": {
        "required": ["email_id", "thread_id", "topic"],
        "execution_mode": "approval_required",
        "verification": "Follow-up should not duplicate an already completed task or sent reply.",
    },
    "snooze_thread": {
        "required": ["email_id", "thread_id"],
        "execution_mode": "deterministic",
        "verification": "Thread appears once in the snoozed list with a remind time.",
    },
    "create_task": {
        "required": ["thread_id", "topic"],
        "execution_mode": "deterministic",
        "verification": "A single open workflow task exists for this action.",
    },
}


def _action_id(user_id: str, thread_id: str, action_type: str) -> str:
    return f"{user_id}:{thread_id}:{action_type}"


def _thread_state(email: dict[str, Any]) -> dict[str, Any]:
    state = email.get("thread_state")
    return state if isinstance(state, dict) else {}


def _intent_for(action_type: str, status: str | None) -> str:
    if action_type == "schedule_meeting":
        return "meeting_request"
    if action_type == "draft_reply":
        return "reply_needed"
    if action_type == "send_followup":
        return "followup_due"
    if action_type == "create_task":
        return "task_required"
    if action_type == "snooze_thread":
        return "defer_until_later"
    return status or "workflow_action"


def _affected_entities(email: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    extracted = state.get("extracted_entities")
    if not isinstance(extracted, dict):
        extracted = {}
    return {
        "participants": state.get("participants") or [],
        "sender": email.get("sender"),
        "emails": extracted.get("emails") or [],
        "urls": extracted.get("urls") or [],
        "dates": extracted.get("dates") or [],
    }


def _approval_reasoning(
    action_type: str,
    status: str | None,
    confidence: float,
    urgency: float,
    risk_level: str,
) -> dict[str, Any]:
    requires_approval = risk_level in {"medium", "high"} or confidence < 0.82
    return {
        "observed_status": status,
        "recommended_action": action_type,
        "requires_approval": requires_approval,
        "approval_reason": (
            "Risk or confidence requires human approval before execution."
            if requires_approval
            else "Low-risk, high-confidence action can be safely approved."
        ),
        "confidence_percent": round(confidence * 100),
        "urgency_score": round(urgency),
    }


def _workflow_plan_for(
    email: dict[str, Any],
    action_type: str,
    topic: str,
    status: str | None,
    confidence: float,
    urgency: float,
    risk_level: str,
) -> dict[str, Any]:
    schema = ACTION_SCHEMAS.get(action_type, {"required": [], "execution_mode": "manual", "verification": "User verifies outcome."})
    thread_id = email.get("thread_id") or email.get("threadId") or email.get("id")
    return {
        "version": "workflow-plan-v1",
        "schema": {
            "action_type": action_type,
            "required_fields": schema["required"],
            "execution_mode": schema["execution_mode"],
        },
        "observe": {
            "thread_id": thread_id,
            "email_id": email.get("id"),
            "topic": topic,
            "status": status,
            "urgency_score": urgency,
            "confidence_score": confidence,
        },
        "reason": {
            "intent": _intent_for(action_type, status),
            "risk_level": risk_level,
            "confidence_gate": "pass" if confidence >= 0.5 else "blocked",
            "approval_gate": "required" if risk_level in {"medium", "high"} or confidence < 0.82 else "optional",
        },
        "plan": [
            "Validate required fields and confidence gates.",
            "Wait for human approval when risk or confidence requires it.",
            f"Execute deterministic action: {action_type}.",
            "Record execution result and update workflow history.",
        ],
        "execute": {
            "action_type": action_type,
            "deterministic": action_type in {"create_task", "snooze_thread"},
            "side_effects": _side_effects_for(action_type),
        },
        "verify": {
            "expected_outcome": schema["verification"],
            "dedupe_key": f"{thread_id}:{action_type}",
        },
    }


def _side_effects_for(action_type: str) -> list[str]:
    if action_type == "create_task":
        return ["workflow_task_created_or_reused"]
    if action_type == "snooze_thread":
        return ["snoozed_email_upserted", "processed_email_marked_snoozed"]
    if action_type == "draft_reply":
        return ["reply_generation_prompted"]
    if action_type == "schedule_meeting":
        return ["calendar_confirmation_prompted"]
    if action_type == "send_followup":
        return ["followup_task_or_reply_recommended"]
    return ["manual_review"]


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

    risk_level = RISK_BY_ACTION.get(action_type, "medium")

    return {
        "action_type": action_type,
        "reasoning": reasoning,
        "confidence_score": confidence,
        "risk_level": risk_level,
        "payload": {
            "email_id": email.get("id"),
            "thread_id": state.get("thread_id") or email.get("thread_id") or email.get("id"),
            "topic": topic,
            "status": status,
            "extracted_intent": _intent_for(action_type, status),
            "affected_entities": _affected_entities(email, state),
            "approval": _approval_reasoning(
                action_type=action_type,
                status=status,
                confidence=confidence,
                urgency=urgency,
                risk_level=risk_level,
            ),
            "workflow_plan": _workflow_plan_for(
                email=email,
                action_type=action_type,
                topic=topic,
                status=status,
                confidence=confidence,
                urgency=urgency,
                risk_level=risk_level,
            ),
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
        "retry_count": int(action.retry_count or 0),
        "last_error": action.last_error,
        "validated_at": action.validated_at.isoformat() if action.validated_at else None,
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
        "description": task.description,
        "status": task.status,
        "source_action_id": task.source_action_id,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def serialize_execution_log(log: ExecutionLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "user_id": log.user_id,
        "thread_id": log.thread_id,
        "action_id": log.action_id,
        "action_type": log.action_type,
        "status": log.status,
        "message": log.message,
        "created_at": log.created_at.isoformat() if log.created_at else None,
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


def log_workflow_event(
    db: Session,
    user_id: str,
    action_type: str,
    status: str,
    message: str,
    thread_id: str | None = None,
    action_id: str | None = None,
) -> ExecutionLog:
    log = ExecutionLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        thread_id=thread_id,
        action_id=action_id,
        action_type=action_type,
        status=status,
        message=message,
        created_at=datetime.utcnow(),
    )
    db.add(log)
    return log
