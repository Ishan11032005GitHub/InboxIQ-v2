from sqlalchemy import Column, DateTime, String, Text

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


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    tokens = Column(Text)
