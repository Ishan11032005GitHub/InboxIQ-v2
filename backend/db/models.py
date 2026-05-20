from sqlalchemy import Column, DateTime, Float, String, Text

from backend.db.db import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    mode = Column(String, nullable=False, default="gmail")


class ProcessedEmail(Base):
    __tablename__ = "processed_emails"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    action_bucket = Column(String)
    reply = Column(String)
    event_link = Column(String)
    reply_sent = Column(String)
    reply_sent_at = Column(DateTime)
    conversation_thread = Column(Text)


class SnoozedEmail(Base):
    __tablename__ = "snoozed_emails"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    email_id = Column(String)
    remind_at = Column(DateTime)


class ScheduledEmail(Base):
    __tablename__ = "scheduled_emails"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    email_id = Column(String)
    event_link = Column(String)


class ThreadState(Base):
    __tablename__ = "thread_states"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    topic = Column(String)
    participants = Column(Text)
    current_status = Column(String)
    pending_action = Column(String)
    urgency_score = Column(Float)
    waiting_since = Column(DateTime)
    followup_due = Column(DateTime)
    confidence_score = Column(Float)
    summarized_context = Column(Text)
    extracted_entities = Column(Text)
    updated_at = Column(DateTime)


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    email_id = Column(String)
    action_type = Column(String, nullable=False)
    reasoning = Column(Text)
    confidence_score = Column(Float)
    risk_level = Column(String)
    status = Column(String, nullable=False, default="pending")
    payload = Column(Text)
    retry_count = Column(Float, nullable=False, default=0)
    last_error = Column(Text)
    validated_at = Column(DateTime)
    created_at = Column(DateTime)
    executed_at = Column(DateTime)


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    thread_id = Column(String)
    action_id = Column(String)
    action_type = Column(String)
    status = Column(String)
    message = Column(Text)
    created_at = Column(DateTime)


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    thread_id = Column(String)
    email_id = Column(String)
    title = Column(String)
    description = Column(Text)
    status = Column(String, nullable=False, default="open")
    source_action_id = Column(String)
    due_at = Column(DateTime)
    created_at = Column(DateTime)
    completed_at = Column(DateTime)


class ContactMemory(Base):
    __tablename__ = "contact_memories"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    sender_email = Column(String, nullable=False)
    display_name = Column(String)
    interaction_count = Column(Float, nullable=False, default=0)
    thread_count = Column(Float, nullable=False, default=0)
    importance_score = Column(Float)
    response_latency_hours = Column(Float)
    recurring_topics = Column(Text)
    preferred_tone = Column(String)
    summary = Column(Text)
    observed_thread_ids = Column(Text)
    last_contacted_at = Column(DateTime)
    updated_at = Column(DateTime)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    tokens = Column(Text)
