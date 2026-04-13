# backend/session.py  — full file replacement
import uuid
from backend.db.database import SessionLocal
from backend.db.models import UserSession

def create_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(UserSession(session_id=session_id, user_id=user_id))
        db.commit()
    finally:
        db.close()
    return session_id

def get_user_from_session(session_id: str | None) -> str | None:
    if not session_id:
        return None
    db = SessionLocal()
    try:
        record = db.query(UserSession).filter_by(session_id=session_id).first()
        return record.user_id if record else None
    finally:
        db.close()