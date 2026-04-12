import uuid

sessions = {}

def create_session(user_id):
    session_id = str(uuid.uuid4())
    sessions[session_id] = user_id
    return session_id

def get_user_from_session(session_id):
    return sessions.get(session_id)