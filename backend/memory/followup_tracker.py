"""
backend/memory/followup_tracker.py

Creates a lightweight Google Calendar reminder event so the user is
nudged to follow up if they don't hear back after sending a reply.

Default window: 48 hours.
The reminder is a 15-minute event titled:
    "Follow up: {original subject}"
"""

import logging
from datetime import datetime, timedelta
from typing import Dict

from google.oauth2.credentials import Credentials
from backend.calendar.calendar_utils import create_calendar_event

logger = logging.getLogger(__name__)


def create_followup_reminder(
    credentials: Credentials,
    original_subject: str,
    sender_email: str,
    hours: int = 48,
    timezone: str = "Asia/Kolkata",
) -> Dict:
    """
    Schedule a follow-up reminder on Google Calendar.

    Parameters
    ----------
    credentials      : OAuth credentials for the calendar owner
    original_subject : Subject of the email that was replied to
    sender_email     : Who you replied to (shown in description)
    hours            : Hours from now when the reminder fires (default 48)
    timezone         : IANA timezone string

    Returns
    -------
    dict from create_calendar_event:
        success (bool), event_id, event_link, error
    """
    start_dt = datetime.now() + timedelta(hours=hours)
    end_dt   = start_dt + timedelta(minutes=15)

    logger.info(
        "create_followup_reminder | subject=%s | reminder_at=%s",
        original_subject, start_dt.isoformat(),
    )

    result = create_calendar_event(
        credentials=credentials,
        summary=f"Follow up: {original_subject}",
        start_datetime=start_dt.isoformat(),
        end_datetime=end_dt.isoformat(),
        timezone=timezone,
        description=(
            f"You replied to {sender_email}.\n"
            f"If you haven't heard back, follow up now.\n\n"
            f"Original subject: {original_subject}"
        ),
    )

    if result["success"]:
        logger.info("Follow-up reminder created | link=%s", result.get("event_link"))
    else:
        logger.warning("Follow-up reminder failed | error=%s", result.get("error"))

    return result