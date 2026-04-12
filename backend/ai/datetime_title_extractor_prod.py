"""
Production-Ready DateTime and Title Extractor

Extracts meeting datetime and title from natural language email subject and body.
Uses dateparser library for robust date/time parsing.

Author: InboxIQ
Version: 1.0
"""

import re
from typing import Dict, Optional
from datetime import datetime
import dateparser


def extract_datetime_and_title(
    subject: str = "",
    body: str = ""
) -> Dict[str, Optional[str]]:
    """
    Extract datetime and title from email subject and body text.
    
    This function parses natural language date/time expressions from email content
    and extracts or infers a meaningful title. The function prioritizes the subject
    line for the title and searches both subject and body for datetime information.
    
    Args:
        subject (str): Email subject line. Defaults to empty string.
        body (str): Email body text. Defaults to empty string.
    
    Returns:
        Dict with keys:
            - datetime (str | None): Extracted datetime in ISO 8601 format 
                                    (e.g., "2026-04-05T17:00:00"), or None if not found
            - title (str): Email subject, or inferred title from body, or default
    
    Examples:
        >>> extract_datetime_and_title(
        ...     subject="Team Sync Tomorrow at 2 PM",
        ...     body="Let's discuss project status."
        ... )
        {
            'datetime': '2026-04-04T14:00:00',
            'title': 'Team Sync Tomorrow at 2 PM'
        }
        
        >>> extract_datetime_and_title(
        ...     subject="",
        ...     body="Can we meet next Monday morning around 10 AM?"
        ... )
        {
            'datetime': '2026-04-07T10:00:00',
            'title': 'Meeting Request'
        }
        
        >>> extract_datetime_and_title(
        ...     subject="Project Discussion",
        ...     body="No specific time mentioned."
        ... )
        {
            'datetime': None,
            'title': 'Project Discussion'
        }
    
    Notes:
        - Datetime parsing uses dateparser with PREFER_DATES_FROM='future'
        - Subject line is preferred for title
        - If no subject, extracts first sentence from body as title
        - If no date found in text, returns None for datetime
        - Handles empty, None, or whitespace-only input safely
        - All returned datetimes are naive (no timezone info)
    """
    # Handle empty input
    if not subject and not body:
        return {
            "datetime": None,
            "title": "Untitled",
        }
    
    # Extract and infer title
    title = _extract_title(subject, body)
    
    # Extract datetime from subject and body
    combined_text = f"{subject} {body}".strip()
    datetime_str = _extract_datetime(combined_text)
    
    return {
        "datetime": datetime_str,
        "title": title,
    }


def _normalize_text(text: str) -> str:
    """
    Normalize text for processing.
    
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


def _extract_title(subject: str = "", body: str = "") -> str:
    """
    Extract or infer a title from subject and body.
    
    Uses subject if available, otherwise extracts from body.
    Falls back to default if no content.
    
    Args:
        subject (str): Email subject line
        body (str): Email body text
    
    Returns:
        str: Extracted or inferred title
    """
    # Prefer subject line as title
    if subject and subject.strip():
        return subject.strip()
    
    # Extract first sentence from body as title
    if body and body.strip():
        # Get first sentence or first 60 chars, whichever is shorter
        first_sentence = _extract_first_sentence(body)
        if first_sentence and len(first_sentence.strip()) > 0:
            return first_sentence.strip()
    
    # Default fallback
    return "Untitled"


def _extract_first_sentence(text: str) -> str:
    """
    Extract the first sentence from text.
    
    Stops at first period, question mark, or exclamation mark.
    Falls back to first 60 characters if no sentence boundary found.
    
    Args:
        text (str): Input text
    
    Returns:
        str: First sentence or first 60 chars
    """
    if not text:
        return ""
    
    # Try to find first sentence ending
    match = re.search(r'([^.!?]*[.!?])', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Fallback: return first 60 characters
    return text[:60].strip()


def _extract_datetime(text: str) -> Optional[str]:
    """
    Extract datetime from natural language text using dateparser.
    
    Searches for date/time expressions and parses them to ISO format.
    Handles various formats like "tomorrow at 5", "next Monday", "April 5th at 3pm".
    
    Args:
        text (str): Input text containing potential datetime expressions
    
    Returns:
        str: ISO 8601 formatted datetime, or None if not found
    """
    if not text or not text.strip():
        return None
    
    try:
        # Try parsing the entire text first
        parsed = dateparser.parse(
            text,
            settings={
                'PREFER_DATES_FROM': 'future',  # Prefer future dates for meetings
                'RETURN_AS_TIMEZONE_AWARE': False,  # Return naive datetime
                'RELATIVE_BASE': datetime.now(),
            }
        )
        
        if parsed:
            return parsed.isoformat()
        
        # If full text parsing fails, try extracting likely datetime phrases
        datetime_phrases = _extract_datetime_phrases(text)
        for phrase in datetime_phrases:
            try:
                parsed = dateparser.parse(
                    phrase,
                    settings={
                        'PREFER_DATES_FROM': 'future',
                        'RETURN_AS_TIMEZONE_AWARE': False,
                        'RELATIVE_BASE': datetime.now(),
                    }
                )
                if parsed:
                    return parsed.isoformat()
            except Exception:
                continue
        
        return None
        
    except Exception:
        # Safely handle any parsing errors
        return None


def _extract_datetime_phrases(text: str) -> list:
    """
    Extract potential datetime phrases from text using regex patterns.
    
    Returns list of likely datetime expressions to parse.
    
    Args:
        text (str): Input text
    
    Returns:
        list: List of potential datetime phrases
    """
    phrases = []
    
    # Patterns for common datetime expressions
    patterns = [
        # Relative dates with times: "tomorrow at 5", "next Monday at 2pm"
        r'\b(?:tomorrow|today|tonight|yesterday|next\s+\w+|this\s+\w+)\s+(?:at|around)?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b',
        # Just relative dates: "tomorrow", "next Monday"
        r'\b(?:tomorrow|today|tonight|yesterday|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|next\s+week|this\s+week)\b',
        # Specific dates: "April 5th", "April 5", "4/5/2026"
        r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?\b',
        r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
        # Times: "5pm", "5 pm", "5:30 am"
        r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b',
        # Time descriptions: "morning", "afternoon", "evening"
        r'\b(?:morning|afternoon|evening|night|noon|midnight)\b',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            phrase = match.group(0).strip()
            if phrase and phrase not in phrases and len(phrase) > 1:
                phrases.append(phrase)
    
    return phrases


# Test cases
if __name__ == "__main__":
    test_cases = [
        {
            "name": "Subject with date and time",
            "subject": "Team Sync Tomorrow at 2 PM",
            "body": "Let's discuss project status.",
            "expect_datetime": True,
            "expect_title": "Team Sync Tomorrow at 2 PM",
        },
        {
            "name": "Body with datetime, no subject",
            "subject": "",
            "body": "Can we meet next Monday morning around 10 AM?",
            "expect_datetime": True,
            "expect_title": "Can we meet next Monday morning around 10 AM?",
        },
        {
            "name": "Specific date in subject",
            "subject": "Meeting on April 15th at 3:30 PM",
            "body": "See you then!",
            "expect_datetime": True,
            "expect_title": "Meeting on April 15th at 3:30 PM",
        },
        {
            "name": "No datetime, with subject",
            "subject": "Project Discussion",
            "body": "No specific time mentioned.",
            "expect_datetime": False,
            "expect_title": "Project Discussion",
        },
        {
            "name": "Empty input",
            "subject": "",
            "body": "",
            "expect_datetime": False,
            "expect_title": "Untitled",
        },
        {
            "name": "Body only, no datetime",
            "subject": "",
            "body": "This is a message about the project.",
            "expect_datetime": False,
            "expect_title": "This is a message about the project.",
        },
        {
            "name": "Multiple datetime references",
            "subject": "Rescheduled: Tuesday at 2pm instead of Monday",
            "body": "We moved the meeting from Monday to Tuesday at 2pm.",
            "expect_datetime": True,
            "expect_title": "Rescheduled: Tuesday at 2pm instead of Monday",
        },
        {
            "name": "Time without date",
            "subject": "Quick sync",
            "body": "Can you do 3:00 PM today?",
            "expect_datetime": True,
            "expect_title": "Quick sync",
        },
    ]
    
    print("=" * 80)
    print("PRODUCTION-READY DATETIME & TITLE EXTRACTOR - TEST RESULTS")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        result = extract_datetime_and_title(test["subject"], test["body"])
        
        # Check datetime extraction
        has_datetime = result["datetime"] is not None
        datetime_correct = has_datetime == test["expect_datetime"]
        
        # Check title
        title_correct = result["title"] == test["expect_title"]
        
        test_passed = datetime_correct and title_correct
        status = "✓ PASS" if test_passed else "✗ FAIL"
        
        print(f"\nTest {i}: {test['name']}")
        print(f"  Subject: {test['subject']!r}")
        print(f"  Body: {test['body'][:50]!r}{'...' if len(test['body']) > 50 else ''}")
        print(f"  Result: {status}")
        print(f"    datetime: {result['datetime']} (expected: {test['expect_datetime']})")
        print(f"    title: {result['title']!r} (expected: {test['expect_title']!r})")
        
        if test_passed:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
