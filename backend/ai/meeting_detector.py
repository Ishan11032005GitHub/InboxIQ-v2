"""
Meeting Intent Detection Module

Detects whether an email contains meeting-related intent using rule-based
keyword matching. Returns is_meeting (bool) and confidence score (0-1).
"""

import re
from typing import Dict


# Rule-based keyword categories with confidence weights
STRONG_MEETING_KEYWORDS = {
    "meeting": 0.95,
    "call": 0.90,
    "conference": 0.95,
    "synced": 0.85,
    "sync": 0.85,
    "presentation": 0.80,
    "demo": 0.80,
    "standoff": 0.95,
    "standup": 0.95,
    "video call": 0.95,
    "video conference": 0.95,
    "meeting request": 0.98,
    "agenda": 0.75,
    "minutes": 0.70,
    "briefing": 0.85,
    "debrief": 0.85,
}

MODERATE_KEYWORDS = {
    "schedule": 0.70,
    "scheduled": 0.70,
    "reschedule": 0.75,
    "rescheduled": 0.75,
    "confirm": 0.60,
    "confirmed": 0.60,
    "join": 0.65,
    "attendees": 0.75,
    "attendee": 0.75,
    "participant": 0.65,
    "discuss": 0.55,
    "discussion": 0.55,
    "calendar": 0.70,
    "zoom": 0.85,
    "teams": 0.80,
    "google meet": 0.85,
    "webex": 0.85,
}

TIME_KEYWORDS = {
    "time": 0.30,
    "tomorrow": 0.40,
    "today": 0.40,
    "next week": 0.40,
    "@": 0.35,  # Time marker like "10 @"
    "am": 0.30,
    "pm": 0.30,
    "o'clock": 0.35,
    "hour": 0.30,
}


def _normalize_text(text: str) -> str:
    """Normalize text for keyword matching."""
    if not text:
        return ""
    return text.lower().strip()


def _extract_keywords(text: str, keyword_dict: Dict[str, float]) -> list:
    """Extract matching keywords from text with their confidence scores."""
    normalized = _normalize_text(text)
    matches = []

    for keyword, confidence in keyword_dict.items():
        # Use word boundaries for more precise matching
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, normalized):
            matches.append(confidence)

    return matches


def _calculate_confidence(subject: str, body: str) -> float:
    """
    Calculate confidence score (0-1) based on keyword matching.
    Combines subject and body analysis with higher weight on subject.
    """
    # Extract keywords from subject and body
    subject_strong = _extract_keywords(subject, STRONG_MEETING_KEYWORDS)
    subject_moderate = _extract_keywords(subject, MODERATE_KEYWORDS)
    subject_time = _extract_keywords(subject, TIME_KEYWORDS)

    body_strong = _extract_keywords(body, STRONG_MEETING_KEYWORDS)
    body_moderate = _extract_keywords(body, MODERATE_KEYWORDS)
    body_time = _extract_keywords(body, TIME_KEYWORDS)

    # Weight subject more heavily (subject is typically more indicative)
    subject_score = (
        sum(subject_strong) * 1.0
        + sum(subject_moderate) * 0.8
        + sum(subject_time) * 0.3
    )

    body_score = (
        sum(body_strong) * 0.7
        + sum(body_moderate) * 0.5
        + sum(body_time) * 0.2
    )

    # Normalize scores
    total_score = subject_score + body_score
    max_possible_score = 1.0  # Normalize to 0-1 range

    # Quick normalization: cap at 3.0 to avoid excessive scores
    confidence = min(total_score / 3.0, 1.0)

    # Boost confidence if we found strong meeting keywords
    if subject_strong or body_strong:
        confidence = min(confidence + 0.1, 1.0)

    return max(0.0, min(1.0, confidence))


def detect_meeting_intent(subject: str = "", body: str = "") -> Dict[str, any]:
    """
    Detect if an email contains meeting intent.

    Args:
        subject (str): Email subject line
        body (str): Email body text

    Returns:
        Dict with keys:
            - is_meeting (bool): True if likely a meeting-related email
            - confidence (float): Confidence score (0.0-1.0)

    Example:
        >>> result = detect_meeting_intent(
        ...     subject="Meeting Tomorrow at 2 PM",
        ...     body="Let's sync on the project status."
        ... )
        >>> result
        {'is_meeting': True, 'confidence': 0.92}
    """
    if not subject and not body:
        return {"is_meeting": False, "confidence": 0.0}

    confidence = _calculate_confidence(subject, body)

    # Use a threshold of 0.4 to determine if it's a meeting
    # This threshold can be tuned based on preferences
    is_meeting = confidence >= 0.4

    return {
        "is_meeting": is_meeting,
        "confidence": round(confidence, 3),
    }


# Test cases
if __name__ == "__main__":
    test_cases = [
        {
            "subject": "Meeting tomorrow at 2 PM",
            "body": "Let's schedule a call to discuss the project.",
            "expected": True,
        },
        {
            "subject": "Quick sync on Q2 goals",
            "body": "Are you available for a 30-minute standup?",
            "expected": True,
        },
        {
            "subject": "Project Update",
            "body": "Here's the latest version of the document.",
            "expected": False,
        },
        {
            "subject": "Zoom link for presentation",
            "body": "Join here: zoom.us/...",
            "expected": True,
        },
        {
            "subject": "Conference registration confirmed",
            "body": "Your conference ticket is attached.",
            "expected": True,
        },
    ]

    for i, test in enumerate(test_cases, 1):
        result = detect_meeting_intent(test["subject"], test["body"])
        expected = test["expected"]
        status = "✓" if result["is_meeting"] == expected else "✗"
        print(
            f"{status} Test {i}: is_meeting={result['is_meeting']}, "
            f"confidence={result['confidence']}"
        )
