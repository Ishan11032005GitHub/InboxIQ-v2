#calendar_utils.py

"""
Google Calendar API Module

Creates and manages Google Calendar events using OAuth2 credentials.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta  # ✅ UPDATED (added timedelta)
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


def get_calendar_service(credentials: Credentials):
    return build("calendar", "v3", credentials=credentials)


def create_calendar_event(
    credentials: Credentials,
    summary: str,
    start_datetime: str,   # ISO 8601: "2026-04-06T17:00:00"
    end_datetime: str,     # ISO 8601: "2026-04-06T18:00:00"
    timezone: str = "Asia/Kolkata",
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    calendar_id: str = "primary",
) -> Dict:
    """
    Create a Google Calendar event on the authenticated user's primary calendar.

    Returns
    -------
    dict
        success (bool), event_id, event_link, error, raw_response
    """
    try:
        service = get_calendar_service(credentials)

        event: dict = {
            "summary": summary,
            "start": {"dateTime": start_datetime, "timeZone": timezone},
            "end":   {"dateTime": end_datetime,   "timeZone": timezone},
        }

        if description:
            event["description"] = description

        if location:
            event["location"] = location

        if attendees:
            event["attendees"] = [{"email": e} for e in attendees]
            event["conferenceData"] = {
                "createRequest": {
                    "requestId": f"inboxiq-{datetime.now().timestamp()}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        logger.debug(
            "create_calendar_event | summary=%s | start=%s | end=%s | tz=%s",
            summary, start_datetime, end_datetime, timezone,
        )

        created = service.events().insert(
            calendarId=calendar_id,
            body=event,
            sendNotifications=bool(attendees),
            conferenceDataVersion=1 if attendees else 0,
        ).execute()

        logger.info(
            "Calendar event created | id=%s | link=%s",
            created.get("id"), created.get("htmlLink"),
        )

        return {
            "success":      True,
            "event_id":     created.get("id"),
            "event_link":   created.get("htmlLink"),
            "error":        None,
            "raw_response": created,
        }

    except Exception as e:
        logger.exception("create_calendar_event failed: %s", e)
        return {
            "success":      False,
            "event_id":     None,
            "event_link":   None,
            "error":        str(e),
            "raw_response": None,
        }


# ✅ NEW FUNCTION — FOLLOW-UP TRACKER
def create_followup_event(
    credentials: Credentials,
    subject: str,
    duration_hours: int = 48,
    timezone: str = "Asia/Kolkata",
) -> Dict:
    """
    Creates a follow-up reminder after X hours.
    """
    try:
        now = datetime.now()
        start = now + timedelta(hours=duration_hours)
        end = start + timedelta(minutes=30)

        start_iso = start.isoformat()
        end_iso   = end.isoformat()

        summary = f"Follow up: {subject}"

        return create_calendar_event(
            credentials=credentials,
            summary=summary,
            start_datetime=start_iso,
            end_datetime=end_iso,
            timezone=timezone,
            description=f"type:followup | subject:{subject}",  # ✅ metadata added
        )

    except Exception as e:
        logger.exception("create_followup_event failed: %s", e)
        return {
            "success": False,
            "event_id": None,
            "event_link": None,
            "error": str(e),
        }


def update_calendar_event(
    credentials: Credentials,
    event_id: str,
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    timezone: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    calendar_id: str = "primary",
) -> Dict:
    try:
        service = get_calendar_service(credentials)
        event   = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        if summary:        event["summary"]           = summary
        if description:    event["description"]       = description
        if location:       event["location"]          = location
        if start_datetime: event["start"]["dateTime"] = start_datetime
        if end_datetime:   event["end"]["dateTime"]   = end_datetime
        if timezone:
            event["start"]["timeZone"] = timezone
            event["end"]["timeZone"]   = timezone

        updated = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
            sendNotifications=True,
        ).execute()

        return {"success": True, "event_id": updated.get("id"), "error": None, "raw_response": updated}

    except Exception as e:
        logger.exception("update_calendar_event failed: %s", e)
        return {"success": False, "event_id": event_id, "error": str(e), "raw_response": None}


def delete_calendar_event(
    credentials: Credentials,
    event_id: str,
    calendar_id: str = "primary",
) -> Dict:
    try:
        service = get_calendar_service(credentials)
        service.events().delete(
            calendarId=calendar_id, eventId=event_id, sendNotifications=True
        ).execute()
        return {"success": True, "event_id": event_id, "error": None}
    except Exception as e:
        logger.exception("delete_calendar_event failed: %s", e)
        return {"success": False, "event_id": event_id, "error": str(e)}


def get_calendar_event(
    credentials: Credentials,
    event_id: str,
    calendar_id: str = "primary",
) -> Dict:
    try:
        service = get_calendar_service(credentials)
        event   = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return {"success": True, "event": event, "error": None}
    except Exception as e:
        logger.exception("get_calendar_event failed: %s", e)
        return {"success": False, "event": None, "error": str(e)}