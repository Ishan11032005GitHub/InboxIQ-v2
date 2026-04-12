"""
Production-Ready Google Calendar Event Creator

Creates Google Calendar events from datetime and title with robust error handling.
Supports system timezone detection and graceful API error handling.

Author: InboxIQ
Version: 1.0
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import time
import tzlocal
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_calendar_event(
    title: str,
    datetime_iso: str,
    credentials: Optional[Credentials] = None,
    duration_minutes: int = 30,
) -> Dict[str, Optional[str]]:
    """
    Create a Google Calendar event from title and ISO datetime.
    
    This function creates a calendar event with automatic end time calculation
    and system timezone detection. It includes comprehensive error handling
    and logging for debugging.
    
    Args:
        title (str): Event summary/title (e.g., "Team Sync")
        datetime_iso (str): Start datetime in ISO 8601 format 
                           (e.g., "2026-04-05T14:00:00")
        credentials (Credentials, optional): OAuth2 credentials. If None, 
                                             attempts to load from token.json.
                                             Can be a mock object for testing.
        duration_minutes (int): Event duration in minutes. Defaults to 30.
    
    Returns:
        Dict with keys:
            - status (str): "success" if event created, "failed" otherwise
            - event_link (str | None): Google Calendar event link if successful
            - error (str | None): Error message if failed
    
    Examples:
        >>> from google.oauth2.credentials import Credentials
        >>> from backend.auth.google_auth import load_credentials
        >>> 
        >>> creds = load_credentials()
        >>> result = create_calendar_event(
        ...     title="Team Sync",
        ...     datetime_iso="2026-04-05T14:00:00",
        ...     credentials=creds
        ... )
        >>> if result['status'] == 'success':
        ...     print(f"Event created: {result['event_link']}")
        ... else:
        ...     print(f"Error: {result['error']}")
    
    Notes:
        - End time is automatically calculated as start time + duration_minutes
        - Uses system timezone (detected via tzlocal)
        - Gracefully handles API errors with detailed logging
        - Returns detailed error messages for debugging
        - Safe handling of invalid datetime formats
    """
    logger.info(f"Creating calendar event: title='{title}', datetime='{datetime_iso}'")
    
    # Validate inputs
    if not title or not title.strip():
        error_msg = "Event title cannot be empty"
        logger.error(error_msg)
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }
    
    if not datetime_iso or not datetime_iso.strip():
        error_msg = "Datetime cannot be empty"
        logger.error(error_msg)
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }
    
    # Parse ISO datetime
    try:
        start_datetime = datetime.fromisoformat(datetime_iso)
        logger.debug(f"Parsed start datetime: {start_datetime}")
    except ValueError as e:
        error_msg = f"Invalid datetime format. Expected ISO 8601: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }
    
    # Calculate end datetime
    end_datetime = start_datetime + timedelta(minutes=duration_minutes)
    logger.debug(f"Calculated end datetime: {end_datetime}")
    
    # Get system timezone
    try:
        tz = tzlocal.get_localzone()
        timezone_str = str(tz)
        logger.debug(f"System timezone: {timezone_str}")
    except Exception as e:
        timezone_str = "UTC"
        logger.warning(f"Could not detect system timezone, using UTC: {str(e)}")
    
    # Load credentials if not provided
    if credentials is None:
        try:
            from backend.auth.google_auth import load_credentials
            credentials = load_credentials()
            if credentials is None:
                error_msg = "Not authenticated. Please login first."
                logger.error(error_msg)
                return {
                    "status": "failed",
                    "event_link": None,
                    "error": error_msg,
                }
            logger.debug("Loaded credentials from token.json")
        except Exception as e:
            error_msg = f"Failed to load credentials: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "event_link": None,
                "error": error_msg,
            }
    
    # Create calendar event
    try:
        service = build("calendar", "v3", credentials=credentials)
        logger.debug("Built Google Calendar service")
        
        event = {
            "summary": title.strip(),
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": timezone_str,
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": timezone_str,
            },
        }
        
        logger.debug(f"Event object: {event}")
        
        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            sendNotifications=False,
        ).execute()
        
        event_id = created_event.get("id")
        event_link = created_event.get("htmlLink")
        
        logger.info(f"✓ Event created successfully. ID: {event_id}")
        
        return {
            "status": "success",
            "event_link": event_link,
            "error": None,
        }
        
    except HttpError as e:
        error_msg = f"Google Calendar API error: {e.resp.status} {e.resp.reason}"
        logger.error(error_msg)
        logger.debug(f"Full error: {str(e)}")
        
        # Handle specific API errors
        if e.resp.status == 401:
            error_msg = "Authentication failed. Please re-login."
        elif e.resp.status == 403:
            error_msg = "Access denied. Check calendar permissions."
        elif e.resp.status == 429:
            error_msg = "Rate limit exceeded. Try again later."
        
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }
        
    except Exception as e:
        error_msg = f"Unexpected error creating calendar event: {str(e)}"
        logger.error(error_msg)
        logger.debug(f"Full error: {str(e)}", exc_info=True)
        
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }


def create_calendar_event_mock(
    title: str,
    datetime_iso: str,
    duration_minutes: int = 30,
) -> Dict[str, Optional[str]]:
    """
    Mock version of create_calendar_event for testing without API access.
    
    Creates a mock response that mimics the real API response structure.
    Useful for testing the integration without requiring Google credentials.
    
    Args:
        title (str): Event summary/title
        datetime_iso (str): Start datetime in ISO 8601 format
        duration_minutes (int): Event duration in minutes. Defaults to 30.
    
    Returns:
        Dict: Mock response with same structure as create_calendar_event
    
    Example:
        >>> result = create_calendar_event_mock(
        ...     title="Team Sync",
        ...     datetime_iso="2026-04-05T14:00:00"
        ... )
        >>> print(result['status'])
        'success'
    """
    logger.info(f"[MOCK] Creating calendar event: title='{title}', datetime='{datetime_iso}'")
    
    # Validate inputs
    if not title or not title.strip():
        error_msg = "Event title cannot be empty"
        logger.error(error_msg)
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }
    
    if not datetime_iso or not datetime_iso.strip():
        error_msg = "Datetime cannot be empty"
        logger.error(error_msg)
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }
    
    # Parse and validate datetime
    try:
        start_datetime = datetime.fromisoformat(datetime_iso)
        logger.debug(f"[MOCK] Parsed start datetime: {start_datetime}")
    except ValueError as e:
        error_msg = f"Invalid datetime format. Expected ISO 8601: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "event_link": None,
            "error": error_msg,
        }
    
    # Generate mock event ID
    mock_event_id = f"mock_{int(time.time())}"
    mock_event_link = f"https://calendar.google.com/calendar/event?eid={mock_event_id}"
    
    logger.info(f"[MOCK] ✓ Event created successfully. ID: {mock_event_id}")
    
    return {
        "status": "success",
        "event_link": mock_event_link,
        "error": None,
    }


# Test cases
if __name__ == "__main__":
    print("=" * 80)
    print("PRODUCTION-READY CALENDAR EVENT CREATOR - TEST RESULTS")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "Valid event with default duration",
            "title": "Team Sync",
            "datetime": "2026-04-05T14:00:00",
            "expect_success": True,
        },
        {
            "name": "Event with custom duration",
            "title": "Project Meeting",
            "datetime": "2026-04-06T10:30:00",
            "duration": 60,
            "expect_success": True,
        },
        {
            "name": "Empty title",
            "title": "",
            "datetime": "2026-04-05T14:00:00",
            "expect_success": False,
        },
        {
            "name": "Empty datetime",
            "title": "Team Sync",
            "datetime": "",
            "expect_success": False,
        },
        {
            "name": "Invalid datetime format",
            "title": "Team Sync",
            "datetime": "2026-04-05 not-a-time",
            "expect_success": False,
        },
        {
            "name": "Future date",
            "title": "Annual Planning",
            "datetime": "2027-01-15T09:00:00",
            "expect_success": True,
        },
    ]
    
    passed = 0
    failed = 0
    
    print("\n[TESTING MOCK VERSION - NO API REQUIRED]\n")
    
    for i, test in enumerate(test_cases, 1):
        title = test["title"]
        datetime_iso = test["datetime"]
        duration = test.get("duration", 30)
        expect_success = test["expect_success"]
        
        result = create_calendar_event_mock(
            title=title,
            datetime_iso=datetime_iso,
            duration_minutes=duration,
        )
        
        success = result["status"] == "success"
        test_passed = success == expect_success
        status = "✓ PASS" if test_passed else "✗ FAIL"
        
        print(f"Test {i}: {test['name']}")
        print(f"  Title: {title!r}")
        print(f"  DateTime: {datetime_iso!r}")
        print(f"  Result: {status}")
        print(f"    status: {result['status']} (expected: {'success' if expect_success else 'failed'})")
        if result['error']:
            print(f"    error: {result['error']}")
        if result['event_link']:
            print(f"    link: {result['event_link']}")
        print()
        
        if test_passed:
            passed += 1
        else:
            failed += 1
    
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    print("\n" + "=" * 80)
    print("USAGE EXAMPLES")
    print("=" * 80)
    
    print("""
1. Create event with real credentials:
   
   from backend.auth.google_auth import load_credentials
   from backend.calendar.create_event_prod import create_calendar_event
   
   creds = load_credentials()
   result = create_calendar_event(
       title="Team Sync",
       datetime_iso="2026-04-05T14:00:00",
       credentials=creds
   )
   
   if result['status'] == 'success':
       print(f"Event created: {result['event_link']}")

2. Create event with mock (no credentials needed):
   
   from backend.calendar.create_event_prod import create_calendar_event_mock
   
   result = create_calendar_event_mock(
       title="Team Sync",
       datetime_iso="2026-04-05T14:00:00"
   )
   
   if result['status'] == 'success':
       print(f"Event created: {result['event_link']}")

3. Create with custom duration:
   
   result = create_calendar_event(
       title="Extended Planning Session",
       datetime_iso="2026-04-05T14:00:00",
       credentials=creds,
       duration_minutes=90
   )
    """)
