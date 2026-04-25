from backend.db.db import SessionLocal
from backend.db.models import UserSession
import uuid


def create_session(user_id: str, mode: str):
    db = SessionLocal()

    session_id = str(uuid.uuid4())

    session = UserSession(
        session_id=session_id,
        user_id=user_id,
        mode=mode
    )

    db.add(session)
    db.commit()
    db.close()

    return session_id
