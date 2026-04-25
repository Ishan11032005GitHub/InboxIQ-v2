import uuid

from backend.db.db import SessionLocal
from backend.db.models import UserSession


def create_session(user_id: str, mode: str = "gmail") -> str:
    session_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(UserSession(session_id=session_id, user_id=user_id, mode=mode))
        db.commit()
    finally:
        db.close()
    return session_id


def get_user_from_session(session_id: str | None) -> dict | None:
    if not session_id:
        return None

    db = SessionLocal()
    try:
        record = db.query(UserSession).filter_by(session_id=session_id).first()
        if not record:
            return None

        return {
            "user_id": record.user_id,
            "mode": record.mode or "gmail",
        }
    finally:
        db.close()
