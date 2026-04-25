import os
import re
import json
import logging
from typing import Dict
from google import genai

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Circuit breaker — disabled after first 429 until process restarts
_llm_available = True

STRONG_KEYWORDS = {
    "meeting": 0.95, "call": 0.90, "conference": 0.95,
    "sync": 0.85, "standup": 0.95, "stand-up": 0.95,
    "video call": 0.95, "video conference": 0.95,
    "meeting request": 0.98, "briefing": 0.85, "debrief": 0.85,
    "interview": 0.95, "appointment": 0.95,
}
MODERATE_KEYWORDS = {
    "schedule": 0.70, "reschedule": 0.75, "calendar": 0.70,
    "zoom": 0.85, "teams": 0.80, "google meet": 0.85, "webex": 0.85,
    "attendees": 0.75, "discuss": 0.55, "agenda": 0.75,
}
TIME_KEYWORDS = {
    "tomorrow": 0.40, "today": 0.40, "next week": 0.40,
    "am": 0.30, "pm": 0.30, "o'clock": 0.35,
}

def _keyword_matches(text: str, kw_dict: Dict) -> list:
    text = text.lower()
    return [v for k, v in kw_dict.items() if re.search(r'\b' + re.escape(k) + r'\b', text)]

def _rule_based_detect(subject: str, body: str) -> Dict:
    ss = _keyword_matches(subject, STRONG_KEYWORDS)
    sm = _keyword_matches(subject, MODERATE_KEYWORDS)
    st = _keyword_matches(subject, TIME_KEYWORDS)
    bs = _keyword_matches(body,    STRONG_KEYWORDS)
    bm = _keyword_matches(body,    MODERATE_KEYWORDS)
    bt = _keyword_matches(body,    TIME_KEYWORDS)
    score = (
        sum(ss) * 1.0 + sum(sm) * 0.8 + sum(st) * 0.3 +
        sum(bs) * 0.7 + sum(bm) * 0.5 + sum(bt) * 0.2
    )
    confidence = min(score / 3.0, 1.0)
    if ss or bs:
        confidence = min(confidence + 0.1, 1.0)
    return {"is_meeting": confidence >= 0.4, "confidence": round(confidence, 3)}

def _llm_detect(subject: str, body: str) -> Dict:
    prompt = f"""You are an email classifier. Does this email need a meeting/call scheduled?

Subject: {subject}
Body: {body}

Reply ONLY with JSON: {{"needs_meeting": true, "confidence": 0.95}}

true if: meeting/call proposed, specific time for discussion, interview/appointment/standup.
false if: newsletter, invoice, payment, security alert, no scheduling needed."""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    text   = response.text.strip().replace("```json", "").replace("```", "").strip()
    result = json.loads(text)
    return {
        "is_meeting": bool(result.get("needs_meeting", False)),
        "confidence": round(float(result.get("confidence", 0.5)), 3),
    }

def detect_meeting_intent(subject: str = "", body: str = "") -> Dict:
    global _llm_available

    if not subject and not body:
        return {"is_meeting": False, "confidence": 0.0}

    if _llm_available:
        try:
            result = _llm_detect(subject, body)
            logger.debug(f"LLM meeting detection: {result}")
            return result
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                _llm_available = False
                logger.warning("LLM quota exhausted — switching to rule-based for this session")
            else:
                logger.warning(f"LLM detection failed: {e}")

    result = _rule_based_detect(subject, body)
    logger.debug(f"Rule-based: {result}")
    return result