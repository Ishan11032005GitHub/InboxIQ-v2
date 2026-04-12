"""
Production-Ready FastAPI Email Action Endpoint

Orchestrates meeting detection, datetime extraction, and calendar event creation.
Provides structured workflow with comprehensive logging and error handling.

Author: InboxIQ
Version: 1.0
"""

import logging
from typing import Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
from google.oauth2.credentials import Credentials

from backend.ai.meeting_detector_prod import detect_meeting_intent
from backend.ai.datetime_title_extractor_prod import extract_datetime_and_title
from backend.calendar.create_event_prod import create_calendar_event

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class EmailActionRequest(BaseModel):
    """Request model for email action endpoint"""
    subject: str = Field(..., description="Email subject line", min_length=0)
    body: str = Field(..., description="Email body text", min_length=0)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Team Sync Tomorrow at 2 PM",
                "body": "Let's discuss the project status."
            }
        }
    )


class MeetingIntentInfo(BaseModel):
    """Meeting intent detection info"""
    is_meeting: bool
    confidence: float
    matched_keywords: list


class DateTimeInfo(BaseModel):
    """DateTime extraction info"""
    datetime: Optional[str] = None
    title: str


class CalendarEventInfo(BaseModel):
    """Calendar event creation info"""
    status: str  # "success" or "failed"
    event_link: Optional[str] = None
    error: Optional[str] = None


class EmailActionResponse(BaseModel):
    """Response model for email action endpoint"""
    action: str = Field(
        ...,
        description="Action taken: calendar_event_created, meeting_detected_calendar_failed, meeting_detected_no_datetime, or analysis_complete"
    )
    details: Dict = Field(..., description="Detailed information about the action taken")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "calendar_event_created",
                "details": {
                    "meeting_intent": {
                        "is_meeting": True,
                        "confidence": 0.95,
                        "matched_keywords": ["sync", "call"]
                    },
                    "datetime_extraction": {
                        "datetime": "2026-04-04T14:00:00",
                        "title": "Team Sync"
                    },
                    "calendar_event": {
                        "status": "success",
                        "event_link": "https://calendar.google.com/..."
                    }
                }
            }
        }
    )


# ============================================================================
# CORE LOGIC
# ============================================================================

def process_email_action(
    email_request: EmailActionRequest,
    credentials: Optional[Credentials] = None
) -> EmailActionResponse:
    """
    Process email for meeting detection, datetime extraction, and calendar creation.
    
    Workflow:
    1. Detect meeting intent from subject/body
    2. If not a meeting → return "analysis_complete"
    3. If meeting → extract datetime and title
    4. If no datetime → return "meeting_detected_no_datetime"
    5. If datetime found → create calendar event
    6. Return action status and details
    
    Args:
        email_request (EmailActionRequest): Email with subject and body
        credentials (Credentials, optional): OAuth2 credentials for calendar creation
    
    Returns:
        EmailActionResponse: Structured response with action and details
    """
    subject = email_request.subject.strip()
    body = email_request.body.strip()
    
    logger.info(f"Processing email action - Subject: {subject[:50]}")
    
    # Step 1: Detect meeting intent
    logger.debug("Step 1: Detecting meeting intent...")
    meeting_result = detect_meeting_intent(subject, body)
    is_meeting = meeting_result["is_meeting"]
    confidence = meeting_result["confidence"]
    matched_keywords = meeting_result["matched_keywords"]
    
    logger.info(
        f"Meeting intent result: is_meeting={is_meeting}, "
        f"confidence={confidence}, keywords={matched_keywords}"
    )
    
    # Step 2: If not meeting, return analysis_complete
    if not is_meeting:
        logger.info("Not a meeting - returning analysis_complete")
        return EmailActionResponse(
            action="analysis_complete",
            details={
                "meeting_intent": {
                    "is_meeting": False,
                    "confidence": confidence,
                    "matched_keywords": []
                },
                "message": "Email analyzed but no meeting intent detected"
            }
        )
    
    # Step 3: Extract datetime and title
    logger.debug("Step 3: Extracting datetime and title...")
    datetime_result = extract_datetime_and_title(subject, body)
    datetime_str = datetime_result["datetime"]
    title = datetime_result["title"]
    
    logger.info(f"DateTime extraction result: datetime={datetime_str}, title={title}")
    
    # Step 4: If no datetime, return meeting_detected_no_datetime
    if not datetime_str:
        logger.info("Meeting detected but no datetime found")
        return EmailActionResponse(
            action="meeting_detected_no_datetime",
            details={
                "meeting_intent": {
                    "is_meeting": True,
                    "confidence": confidence,
                    "matched_keywords": matched_keywords
                },
                "datetime_extraction": {
                    "datetime": None,
                    "title": title
                },
                "message": "Meeting detected but could not extract specific datetime"
            }
        )
    
    # Step 5: Create calendar event
    logger.debug("Step 5: Creating calendar event...")
    try:
        event_result = create_calendar_event(
            title=title,
            datetime_iso=datetime_str,
            credentials=credentials,
            duration_minutes=30
        )
        
        if event_result["status"] == "success":
            logger.info(f"Calendar event created successfully: {event_result['event_link']}")
            return EmailActionResponse(
                action="calendar_event_created",
                details={
                    "meeting_intent": {
                        "is_meeting": True,
                        "confidence": confidence,
                        "matched_keywords": matched_keywords
                    },
                    "datetime_extraction": {
                        "datetime": datetime_str,
                        "title": title
                    },
                    "calendar_event": {
                        "status": "success",
                        "event_link": event_result["event_link"],
                        "error": None
                    },
                    "message": "Meeting detected and calendar event created successfully"
                }
            )
        else:
            logger.warning(f"Calendar event creation failed: {event_result['error']}")
            return EmailActionResponse(
                action="meeting_detected_calendar_failed",
                details={
                    "meeting_intent": {
                        "is_meeting": True,
                        "confidence": confidence,
                        "matched_keywords": matched_keywords
                    },
                    "datetime_extraction": {
                        "datetime": datetime_str,
                        "title": title
                    },
                    "calendar_event": {
                        "status": "failed",
                        "event_link": None,
                        "error": event_result["error"]
                    },
                    "message": f"Meeting detected but calendar creation failed: {event_result['error']}"
                }
            )
    
    except Exception as e:
        logger.error(f"Unexpected error creating calendar event: {str(e)}", exc_info=True)
        return EmailActionResponse(
            action="meeting_detected_calendar_failed",
            details={
                "meeting_intent": {
                    "is_meeting": True,
                    "confidence": confidence,
                    "matched_keywords": matched_keywords
                },
                "datetime_extraction": {
                    "datetime": datetime_str,
                    "title": title
                },
                "calendar_event": {
                    "status": "failed",
                    "event_link": None,
                    "error": str(e)
                },
                "message": f"Meeting detected but calendar creation failed: {str(e)}"
            }
        )


# ============================================================================
# FASTAPI ENDPOINT
# ============================================================================

def setup_email_action_route(app):
    """
    Register the /email/action POST endpoint with FastAPI app.
    
    Args:
        app: FastAPI application instance
    
    Example:
        from fastapi import FastAPI
        from backend.routes.email_action import setup_email_action_route
        
        app = FastAPI()
        setup_email_action_route(app)
    """
    
    @app.post(
        "/email/action",
        response_model=EmailActionResponse,
        summary="Process email for meeting detection and calendar creation",
        tags=["Email Processing"]
    )
    async def email_action(
        request: EmailActionRequest
    ) -> EmailActionResponse:
        """
        Process an email to detect meeting intent, extract datetime, and create calendar event.
        
        **Workflow:**
        
        1. **Meeting Intent Detection**: Analyzes email for meeting-related keywords
        2. **DateTime Extraction**: Extracts date/time from natural language
        3. **Calendar Event Creation**: Creates Google Calendar event if applicable
        
        **Response Actions:**
        
        - `calendar_event_created`: Meeting detected and event created successfully
        - `meeting_detected_calendar_failed`: Meeting detected but calendar creation failed
        - `meeting_detected_no_datetime`: Meeting detected but no datetime found
        - `analysis_complete`: Email analyzed, no meeting intent detected
        
        **Example Request:**
        ```json
        {
            "subject": "Team Sync Tomorrow at 2 PM",
            "body": "Let's discuss the project status and roadmap."
        }
        ```
        
        **Example Response (Success):**
        ```json
        {
            "action": "calendar_event_created",
            "details": {
                "meeting_intent": {
                    "is_meeting": true,
                    "confidence": 0.95,
                    "matched_keywords": ["sync", "call"]
                },
                "datetime_extraction": {
                    "datetime": "2026-04-04T14:00:00",
                    "title": "Team Sync Tomorrow at 2 PM"
                },
                "calendar_event": {
                    "status": "success",
                    "event_link": "https://calendar.google.com/calendar/event?eid=abc123"
                }
            }
        }
        ```
        """
        logger.info(f"Received email action request from {request}")
        
        try:
            # TODO: Extract credentials from session/request when OAuth is fully configured
            # For now, credentials parameter is optional
            response = process_email_action(
                email_request=request,
                credentials=None  # Placeholder for future OAuth integration
            )
            logger.info(f"Email action completed with action: {response.action}")
            return response
        
        except Exception as e:
            logger.error(f"Unexpected error in email_action endpoint: {str(e)}", exc_info=True)
            # Return error response
            return EmailActionResponse(
                action="error",
                details={
                    "error": str(e),
                    "message": "Unexpected error processing email"
                }
            )


# ============================================================================
# TEST/DEMO
# ============================================================================

# Mock credentials class for testing
class MockCredentials:
    """Mock OAuth2 credentials for testing without real API access"""
    pass


if __name__ == "__main__":
    print("=" * 80)
    print("PRODUCTION-READY EMAIL ACTION ENDPOINT - TEST RESULTS")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "Clear meeting intent with datetime",
            "subject": "Team Sync Tomorrow at 2 PM",
            "body": "Let's discuss the project status.",
            "expect_action": "meeting_detected_calendar_failed",  # No real creds
            "description": "(No real credentials for calendar creation)"
        },
        {
            "name": "Meeting intent but no datetime",
            "subject": "Meeting Request",
            "body": "Let's schedule a call to discuss.",
            "expect_action": "meeting_detected_no_datetime",
            "description": ""
        },
        {
            "name": "No meeting intent",
            "subject": "Project Update",
            "body": "Here is the latest version of the document.",
            "expect_action": "analysis_complete",
            "description": ""
        },
        {
            "name": "Future date meeting",
            "subject": "Planning Session",
            "body": "Can we sync on April 10th at 3pm to plan Q2?",
            "expect_action": "meeting_detected_calendar_failed",  # No real creds
            "description": "(No real credentials for calendar creation)"
        },
        {
            "name": "Empty input handling",
            "subject": "",
            "body": "",
            "expect_action": "analysis_complete",
            "description": ""
        },
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        request = EmailActionRequest(
            subject=test["subject"],
            body=test["body"]
        )
        result = process_email_action(request, credentials=None)
        
        test_passed = result.action == test["expect_action"]
        status = "✓ PASS" if test_passed else "✗ FAIL"
        
        print(f"\nTest {i}: {test['name']} {test.get('description', '')}")
        print(f"  Subject: {test['subject'][:50]!r}{'...' if len(test['subject']) > 50 else ''}")
        print(f"  Body: {test['body'][:50]!r}{'...' if len(test['body']) > 50 else ''}")
        print(f"  Result: {status}")
        print(f"    action: {result.action} (expected: {test['expect_action']})")
        if result.details.get("message"):
            print(f"    message: {result.details['message']}")
        
        if test_passed:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    print("\n" + "=" * 80)
    print("INTEGRATION EXAMPLE")
    print("=" * 80)
    print("""
# In your main FastAPI app (backend/main.py):

from fastapi import FastAPI
from backend.routes.email_action import setup_email_action_route

app = FastAPI()

# Register the email action endpoint
setup_email_action_route(app)

# Now you can POST to /email/action with:
# {
#     "subject": "Team Sync Tomorrow at 2 PM",
#     "body": "Let's discuss the project."
# }

# TESTING WITH FASTAPI TESTCLIENT:
# 
# from fastapi.testclient import TestClient
# 
# client = TestClient(app)
# response = client.post("/email/action", json={
#     "subject": "Team Sync Tomorrow at 2 PM",
#     "body": "Let's discuss the project status."
# })
# 
# print(response.json())
    """)
