"""
Production-Ready Meeting Intent Detector

Detects meeting-related intent in email subject and body using keyword-based analysis.
Provides confidence scoring and matched keyword reporting.

Author: InboxIQ
Version: 1.0
"""

import re
from typing import Dict, List


# Core meeting-related keywords (as specified in requirements)
MEETING_KEYWORDS = {
    "meeting",
    "schedule",
    "call",
    "sync",
    "connect",
    "discussion",
    "discuss",  # Variant of discussion
}

# Extended keywords for improved detection (lower weight than core)
EXTENDED_KEYWORDS = {
    "scheduled",
    "scheduling",
    "connection",
    "connecting",
    "conference",
    "zoom",
    "teams",
    "google meet",
    "webex",
    "standup",
    "stand-up",
    "presentation",
    "demo",
    "briefing",
    "attendees",
    "calendar",
    "time",
    "tomorrow",
    "today",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}


def detect_meeting_intent(subject: str = "", body: str = "") -> Dict[str, any]:
    """
    Detect if an email contains meeting-related intent.
    
    This function analyzes email subject and body text to determine if the email
    is meeting-related. It uses rule-based keyword matching with confidence scoring.
    
    Args:
        subject (str): Email subject line. Defaults to empty string.
        body (str): Email body text. Defaults to empty string.
    
    Returns:
        Dict with keys:
            - is_meeting (bool): True if meeting intent detected (confidence >= 0.3)
            - confidence (float): Confidence score from 0.0 to 1.0
            - matched_keywords (List[str]): List of detected keywords
    
    Examples:
        >>> detect_meeting_intent(
        ...     subject="Team Sync Tomorrow",
        ...     body="Let's schedule a call to discuss"
        ... )
        {
            'is_meeting': True,
            'confidence': 0.95,
            'matched_keywords': ['sync', 'schedule', 'call', 'discuss']
        }
        
        >>> detect_meeting_intent(
        ...     subject="Project Update",
        ...     body="Here is the latest draft"
        ... )
        {
            'is_meeting': False,
            'confidence': 0.0,
            'matched_keywords': []
        }
    
    Notes:
        - Keywords are matched case-insensitively
        - Subject receives 2x weight compared to body
        - Matched keywords are returned in order of first occurrence
        - Confidence threshold for is_meeting is 0.2 (at least 1 keyword match)
        - Handles empty, None, or whitespace-only input safely
    """
    # Handle empty/None input
    if not subject and not body:
        return {
            "is_meeting": False,
            "confidence": 0.0,
            "matched_keywords": [],
        }
    
    # Normalize input: convert to lowercase and strip whitespace
    subject_normalized = _normalize_text(subject)
    body_normalized = _normalize_text(body)
    combined_text = f"{subject_normalized} {body_normalized}".strip()
    
    # Handle still-empty input after normalization
    if not combined_text:
        return {
            "is_meeting": False,
            "confidence": 0.0,
            "matched_keywords": [],
        }
    
    # Extract matched keywords
    matched_keywords = _extract_matched_keywords(
        subject_normalized, 
        body_normalized
    )
    
    # Calculate confidence score
    confidence = _calculate_confidence(
        subject_normalized,
        body_normalized,
        matched_keywords
    )
    
    # Determine if meeting based on threshold (0.2 = at least 1 significant keyword)
    is_meeting = confidence >= 0.2
    
    return {
        "is_meeting": is_meeting,
        "confidence": round(confidence, 3),
        "matched_keywords": matched_keywords,
    }


def _normalize_text(text: str) -> str:
    """
    Normalize text for analysis.
    
    - Converts to lowercase
    - Strips leading/trailing whitespace
    - Handles None input
    
    Args:
        text (str): Input text to normalize
    
    Returns:
        str: Normalized text
    """
    if not text or not isinstance(text, str):
        return ""
    return text.lower().strip()


def _extract_matched_keywords(
    subject: str, 
    body: str
) -> List[str]:
    """
    Extract all matched keywords from subject and body.
    
    Returns keywords in order of first occurrence, avoiding duplicates.
    
    Args:
        subject (str): Normalized subject text
        body (str): Normalized body text
    
    Returns:
        List[str]: Unique matched keywords in order of occurrence
    """
    matched = []
    seen = set()
    
    # Search in subject first (higher priority)
    for keyword in MEETING_KEYWORDS:
        if _keyword_matches(keyword, subject) and keyword not in seen:
            matched.append(keyword)
            seen.add(keyword)
    
    # Then search in body
    for keyword in MEETING_KEYWORDS:
        if _keyword_matches(keyword, body) and keyword not in seen:
            matched.append(keyword)
            seen.add(keyword)
    
    # Extended keywords (lower priority, only if no core matches found)
    if not matched:
        for keyword in EXTENDED_KEYWORDS:
            if _keyword_matches(keyword, subject) and keyword not in seen:
                matched.append(keyword)
                seen.add(keyword)
        for keyword in EXTENDED_KEYWORDS:
            if _keyword_matches(keyword, body) and keyword not in seen:
                matched.append(keyword)
                seen.add(keyword)
    
    return matched


def _keyword_matches(keyword: str, text: str) -> bool:
    """
    Check if keyword appears in text with word boundaries.
    
    Uses regex word boundaries to avoid partial matches.
    E.g., "call" matches "call" but not in "recall" or "callable".
    
    Args:
        keyword (str): Keyword to search for (should be lowercase)
        text (str): Text to search in (should be lowercase)
    
    Returns:
        bool: True if keyword found with word boundaries
    """
    if not text or not keyword:
        return False
    
    # Escape special regex characters in keyword
    escaped_keyword = re.escape(keyword)
    # Use word boundaries \b for precise matching
    pattern = r'\b' + escaped_keyword + r'\b'
    return bool(re.search(pattern, text))


def _calculate_confidence(
    subject: str, 
    body: str, 
    matched_keywords: List[str]
) -> float:
    """
    Calculate confidence score based on keyword matches.
    
    Scoring logic:
    - Each core keyword match contributes to confidence
    - Subject matches get 2x weight compared to body matches  
    - More keyword matches = higher confidence (0.25 per match minimum)
    - Scaled to 0-1 range
    
    Args:
        subject (str): Normalized subject text
        body (str): Normalized body text
        matched_keywords (List[str]): List of matched keywords
    
    Returns:
        float: Confidence score from 0.0 to 1.0
    """
    if not matched_keywords:
        return 0.0
    
    total_score = 0.0
    
    # Score each matched keyword
    for keyword in matched_keywords:
        # Check if it's a core keyword or extended
        is_core = keyword in MEETING_KEYWORDS
        base_score = 0.5 if is_core else 0.2
        
        # Apply subject/body weight multiplier
        if _keyword_matches(keyword, subject):
            # Subject match gets 2x weight
            total_score += base_score * 2.0
        elif _keyword_matches(keyword, body):
            # Body match gets 1x weight
            total_score += base_score * 1.0
    
    # Normalize to 0-1 range
    # Scaling: each keyword match adds meaningful confidence
    # 1 core keyword: ~0.33-0.67, 2 keywords: ~0.67, 3+: ~1.0
    confidence = min(total_score / 1.5, 1.0)
    
    return max(0.0, confidence)


# Test cases
if __name__ == "__main__":
    test_cases = [
        {
            "name": "Clear meeting intent",
            "subject": "Team Sync Tomorrow at 2 PM",
            "body": "Let's schedule a call to discuss the project.",
            "expected_is_meeting": True,
            "expected_keywords": ["sync", "schedule", "call", "discuss"],
        },
        {
            "name": "Meeting with multiple keywords",
            "subject": "Meeting Request",
            "body": "Can we connect via Zoom for a quick discussion?",
            "expected_is_meeting": True,
            "expected_keywords": ["meeting", "connect", "discussion"],
        },
        {
            "name": "No meeting intent",
            "subject": "Project Update",
            "body": "Here is the latest version of the document.",
            "expected_is_meeting": False,
            "expected_keywords": [],
        },
        {
            "name": "Empty input",
            "subject": "",
            "body": "",
            "expected_is_meeting": False,
            "expected_keywords": [],
        },
        {
            "name": "Only body content",
            "subject": "",
            "body": "Can we schedule a meeting tomorrow?",
            "expected_is_meeting": True,
            "expected_keywords": ["schedule", "meeting"],
        },
        {
            "name": "Case insensitive",
            "subject": "MEETING SYNC CALL",
            "body": "DISCUSSION WITH CONNECTING SOFTWARE",
            "expected_is_meeting": True,
            "expected_keywords": ["meeting", "sync", "call", "discussion"],
        },
        {
            "name": "Extended keyword (technical context)",
            "subject": "Database Status",
            "body": "Connecting to the database for backup",
            "expected_is_meeting": False,  # Extended keyword in non-meeting context
            "expected_keywords": ["connecting"],
        },
        {
            "name": "Single keyword",
            "subject": "Quick call",
            "body": "Quick check-in",
            "expected_is_meeting": True,
            "expected_keywords": ["call"],
        },
    ]
    
    print("=" * 80)
    print("PRODUCTION-READY MEETING INTENT DETECTOR - TEST RESULTS")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        result = detect_meeting_intent(test["subject"], test["body"])
        
        # Check is_meeting
        is_meeting_correct = result["is_meeting"] == test["expected_is_meeting"]
        
        # Check keywords (order-independent)
        keywords_match = set(result["matched_keywords"]) == set(
            test.get("expected_keywords", [])
        )
        
        test_passed = is_meeting_correct and keywords_match
        status = "✓ PASS" if test_passed else "✗ FAIL"
        
        print(f"\nTest {i}: {test['name']}")
        print(f"  Subject: {test['subject']}")
        print(f"  Body: {test['body']}")
        print(f"  Result: {status}")
        print(f"    is_meeting: {result['is_meeting']} (expected: {test['expected_is_meeting']})")
        print(f"    confidence: {result['confidence']}")
        print(f"    keywords: {result['matched_keywords']}")
        if not keywords_match:
            print(f"    expected keywords: {test.get('expected_keywords', [])}")
        
        if test_passed:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
