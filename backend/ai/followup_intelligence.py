from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.ai.workflow_planner import log_workflow_event
from backend.db.models import ThreadState, WorkflowTask


FOLLOWUP_STATUSES = {"followup_required", "stalled"}


def _task_id(user_id: str, thread_id: str) -> str:
    return f"{user_id}:{thread_id}:followup"


def _action_id(user_id: str, thread_id: str) -> str:
    return f"{user_id}:{thread_id}:send_followup"


def _due_at_for(state: ThreadState) -> datetime:
    if state.followup_due:
        return state.followup_due
    if state.waiting_since:
        return state.waiting_since + timedelta(days=2)
    return datetime.utcnow()


def should_create_followup_task(state: ThreadState, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    if state.current_status in FOLLOWUP_STATUSES:
        return True
    if state.current_status != "awaiting_external":
        return False
    return bool(state.followup_due and state.followup_due <= now)


def ensure_followup_task(
    db: Session,
    user_id: str,
    state: ThreadState,
    email_id: str | None = None,
) -> WorkflowTask | None:
    if not should_create_followup_task(state):
        return None

    task_id = _task_id(user_id, state.thread_id)
    task = db.query(WorkflowTask).filter_by(id=task_id).first()
    due_at = _due_at_for(state)
    topic = state.topic or "Untitled thread"
    title = f"Follow up: {topic}"
    description = (
        "This thread appears to be waiting on an external response. "
        "Review the conversation and send a contextual follow-up if it is still unresolved."
    )

    if task:
        if task.status == "completed":
            return task
        task.title = title
        task.description = description
        task.due_at = due_at
        task.email_id = email_id or task.email_id
        return task

    task = WorkflowTask(
        id=task_id,
        user_id=user_id,
        thread_id=state.thread_id,
        email_id=email_id,
        title=title,
        description=description,
        status="open",
        source_action_id=_action_id(user_id, state.thread_id),
        due_at=due_at,
        created_at=datetime.utcnow(),
    )
    db.add(task)
    log_workflow_event(
        db,
        user_id,
        "followup_detected",
        "task_created",
        f"Created follow-up task for thread: {topic}",
        thread_id=state.thread_id,
        action_id=task.source_action_id,
    )
    db.flush()
    return task
