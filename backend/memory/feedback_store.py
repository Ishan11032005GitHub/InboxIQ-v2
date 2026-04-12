import hashlib
import json
import os
from typing import Dict, List

FEEDBACK_FILE = "data/feedback.json"


def _ensure_dir():
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)


def _hash_email(email: Dict[str, str]) -> str:
    text = f"{email.get('subject', '')}_{email.get('sender', '')}_{email.get('body', '')}"
    return hashlib.md5(text.encode()).hexdigest()


def load_feedback() -> List[Dict[str, str]]:
    if not os.path.exists(FEEDBACK_FILE):
        return []

    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_feedback(email: Dict[str, str], correct_label: str) -> None:
    _ensure_dir()
    data = load_feedback()
    email_id = _hash_email(email)

    for item in data:
        if item["id"] == email_id:
            item["label"] = correct_label
            break
    else:
        data.append({
            "id": email_id,
            "subject": email.get("subject", ""),
            "sender": email.get("sender", ""),
            "body": email.get("body", ""),
            "label": correct_label
        })

    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
