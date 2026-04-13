#gemini_utils.py

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from google import genai

from backend.ai.classifier import predict_email

load_dotenv()

MODEL = "models/gemini-2.5-flash"
_client = None


def get_client():
    global _client

    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    _client = genai.Client(api_key=api_key)
    return _client


def rule_engine(sender: str, subject: str, body: str = "") -> Optional[Dict[str, str]]:
    s = (sender or "").lower()
    sub = (subject or "").lower()
    b = (body or "").lower()

    if any(word in sub for word in ["security", "verify", "alert", "password"]):
        return {"label": "security", "priority": "high"}

    if "github" in s:
        return {"label": "notification", "priority": "low"}

    if "unsubscribe" in b:
        return {"label": "newsletter", "priority": "low"}

    return None


def priority_rules(subject: str, sender: str, body: str, label: str) -> str:
    text = f"{subject or ''} {body or ''}".lower()

    if label in ["newsletter", "promotion", "job_alert", "event_invite"]:
        return "low"

    if any(word in text for word in ["urgent", "asap", "server down", "production", "immediately"]):
        return "high"

    if any(word in text for word in ["meeting", "review", "deadline", "call"]):
        return "medium"

    return "low"


def process_inbox(email_list: List[Dict[str, str]]) -> List[Dict[str, str]]:
    results = []
    seen = set()

    for email in email_list:
        unique_id = email.get("id") or f"{email.get('subject', '')}_{email.get('sender', '')}"

        if unique_id in seen:
            continue
        seen.add(unique_id)

        # Keep the classifier enabled, but never let a model/runtime failure
        # break inbox processing.
        try:
            label = predict_email(
                email.get("subject", ""),
                email.get("sender", ""),
                email.get("body", "")
            )
        except Exception:
            label = "general"

        rule = rule_engine(
            email.get("sender", ""),
            email.get("subject", ""),
            email.get("body", "")
        )

        if rule:
            label = rule["label"]

        priority = priority_rules(
            email.get("subject", ""),
            email.get("sender", ""),
            email.get("body", ""),
            label
        )

        item = dict(email)
        item["label"] = label
        item["priority"] = priority
        item["reply"] = ""

        results.append(item)

    return results


def generate_reply(email: Dict[str, str], tone: str = "professional") -> str:
    client = get_client()
    if client is None:
        return "Gemini API key is not configured."

    prompt = f"""
Write an email reply.

Tone: {tone}

EMAIL

From: {email.get("sender", "")}
Subject: {email.get("subject", "")}

Body:
{(email.get("body", "") or "")[:800]}

Write a clear reply. Do not include a signature.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    return response.text.strip() if getattr(response, "text", None) else "Unable to generate reply."
