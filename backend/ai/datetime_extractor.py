"""
Date/Time Extraction Module

Extracts dates and times from natural language email text using dateparser.
Handles various formats like "tomorrow at 5", "next Monday morning", etc.
Returns structured dict with ISO datetime format.
"""

from typing import Dict, Optional
from datetime import datetime
import dateparser
import re


def _clean_text(text: str) -> str:
    """Clean and normalize text for date parsing."""
    if not text:
        return ""
    # Remove extra whitespace
    text = " ".join(text.split())
    return text.lower().strip()


def _parse_with_dateparser(text: str) -> Optional[datetime]:
    """
    Parse natural language date/time string using dateparser library.
    
    Args:
        text (str): Natural language date/time string
        
    Returns:
        datetime object or None if parsing fails
    """
    if not text:
        return None
    
    try:
        # Parse with relaxed settings to handle various formats
        parsed = dateparser.parse(
            text,
            settings={
                'PREFER_DATES_FROM': 'future',  # Prefer future dates for upcoming meetings
                'RETURN_AS_TIMEZONE_AWARE': False,  # Return naive datetime
                'RELATIVE_BASE': datetime.now(),
            }
        )
        return parsed
    except Exception:
        return None


def _extract_time_phrases(text: str) -> list:
    """
    Extract potential date/time phrases from text using regex patterns.
    
    Returns list of potential date/time strings to parse.
    """
    phrases = []
    
    # Common patterns for time references
    patterns = [
        # Relative dates with times: "tomorrow at 5", "next Monday at 2pm"
        r'\b(?:tomorrow|today|tonight|yesterday|next\s+\w+|this\s+\w+)\s+(?:at|around)?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b',
        # Just relative dates: "tomorrow", "next Monday"
        r'\b(?:tomorrow|today|tonight|yesterday|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|next\s+week|this\s+week)\b',
        # Time with period of day: "5pm", "5 pm", "morning", "afternoon"
        r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b',
        r'\b(?:morning|afternoon|evening|night|noon|midnight)\b',
        # Date formats: "2024-03-15", "03/15/2024", "March 15"
        r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\w+\s+\d{1,2}(?:st|nd|rd|th)?)\b',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            phrase = match.group(0).strip()
            if phrase and phrase not in phrases:
                phrases.append(phrase)
    
    return phrases


def extract_datetime(text: str = "") -> Dict[str, any]:
    """
    Extract date and time from natural language email text.
    
    Args:
        text (str): Email subject or body text containing date/time references
        
    Returns:
        Dict with keys:
            - datetime (str): ISO format datetime string, or None if not found
            - raw_datetime (str): The parsed datetime object as string, or None
            - found (bool): Whether a date/time was found and parsed
            - confidence (str): 'high', 'medium', 'low' based on match quality
            - extracted_phrase (str): The original text phrase that was matched
            
    Example:
        >>> result = extract_datetime("Let's meet tomorrow at 5 PM")
        >>> result
        {
            'datetime': '2026-04-04T17:00:00',
            'raw_datetime': '2026-04-04 17:00:00',
            'found': True,
            'confidence': 'high',
            'extracted_phrase': 'tomorrow at 5 pm'
        }
    """
    if not text:
        return {
            "datetime": None,
            "raw_datetime": None,
            "found": False,
            "confidence": "low",
            "extracted_phrase": None,
        }
    
    cleaned = _clean_text(text)
    
    # Try to parse the entire text first (highest confidence)
    parsed = _parse_with_dateparser(cleaned)
    if parsed:
        return {
            "datetime": parsed.isoformat(),
            "raw_datetime": str(parsed),
            "found": True,
            "confidence": "high",
            "extracted_phrase": cleaned,
        }
    
    # Extract individual time phrases and try to parse them (medium confidence)
    phrases = _extract_time_phrases(cleaned)
    
    for phrase in phrases:
        parsed = _parse_with_dateparser(phrase)
        if parsed:
            return {
                "datetime": parsed.isoformat(),
                "raw_datetime": str(parsed),
                "found": True,
                "confidence": "medium",
                "extracted_phrase": phrase,
            }
    
    # No match found
    return {
        "datetime": None,
        "raw_datetime": None,
        "found": False,
        "confidence": "low",
        "extracted_phrase": None,
    }


def extract_all_datetimes(text: str = "") -> Dict[str, any]:
    """
    Extract ALL date/time references from text (not just the first one).
    
    Args:
        text (str): Email text to extract from
        
    Returns:
        Dict with keys:
            - datetimes (list): List of dicts, each with datetime info
            - count (int): Number of dates/times found
            
    Example:
        >>> result = extract_all_datetimes("Meet tomorrow at 5 and again next Friday at 2pm")
        >>> result
        {
            'datetimes': [
                {'datetime': '2026-04-04T17:00:00', 'extracted_phrase': 'tomorrow at 5'},
                {'datetime': '2026-04-11T14:00:00', 'extracted_phrase': 'next Friday at 2pm'}
            ],
            'count': 2
        }
    """
    if not text:
        return {"datetimes": [], "count": 0}
    
    cleaned = _clean_text(text)
    phrases = _extract_time_phrases(cleaned)
    
    datetimes = []
    seen_datetimes = set()  # Avoid duplicates
    
    for phrase in phrases:
        parsed = _parse_with_dateparser(phrase)
        if parsed:
            iso_str = parsed.isoformat()
            # Avoid duplicate datetime entries
            if iso_str not in seen_datetimes:
                datetimes.append({
                    "datetime": iso_str,
                    "raw_datetime": str(parsed),
                    "extracted_phrase": phrase,
                })
                seen_datetimes.add(iso_str)
    
    return {
        "datetimes": datetimes,
        "count": len(datetimes),
    }


# Test cases
if __name__ == "__main__":
    test_cases = [
        {
            "text": "Let's meet tomorrow at 5 PM",
            "expected_found": True,
            "expected_phrase": "tomorrow at 5 pm",
        },
        {
            "text": "Call next Monday morning around 10 AM",
            "expected_found": True,
            "expected_phrase": "next Monday morning around 10 am",
        },
        {
            "text": "Schedule a meeting for March 15th at 2:30 PM",
            "expected_found": True,
        },
        {
            "text": "Let's do this today",
            "expected_found": True,
        },
        {
            "text": "No specific time mentioned in this email",
            "expected_found": False,
        },
        {
            "text": "Meet tomorrow at 5 and again next Friday at 2pm",
            "multi_extract": True,
        },
    ]
    
    print("=" * 70)
    print("SINGLE DATETIME EXTRACTION TESTS")
    print("=" * 70)
    for i, test in enumerate(test_cases[:-1], 1):
        result = extract_datetime(test["text"])
        expected = test.get("expected_found", False)
        status = "✓" if result["found"] == expected else "✗"
        print(f"\n{status} Test {i}: {test['text']}")
        print(f"  Found: {result['found']}, Confidence: {result['confidence']}")
        if result["found"]:
            print(f"  DateTime: {result['datetime']}")
            print(f"  Phrase: {result['extracted_phrase']}")
    
    print("\n" + "=" * 70)
    print("MULTIPLE DATETIME EXTRACTION TEST")
    print("=" * 70)
    test = test_cases[-1]
    result = extract_all_datetimes(test["text"])
    print(f"\nText: {test['text']}")
    print(f"Found {result['count']} datetime(s):")
    for dt in result["datetimes"]:
        print(f"  - {dt['datetime']} (from '{dt['extracted_phrase']}')")
