"""
Example: Testing the /email/action endpoint
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.routes.email_action import setup_email_action_route
import json

# Create FastAPI app and register route
app = FastAPI()
setup_email_action_route(app)
client = TestClient(app)

print("=" * 80)
print("EMAIL ACTION ENDPOINT - INTEGRATION EXAMPLES")
print("=" * 80)

# Example 1: No meeting intent
print("\n[Example 1] No Meeting Intent")
print("-" * 80)
response = client.post(
    "/email/action",
    json={
        "subject": "Project Update",
        "body": "Here is the latest version of the document."
    }
)
result = response.json()
print(f"Status: {response.status_code}")
print(f"Action: {result['action']}")
print(f"Message: {result['details']['message']}")

# Example 2: Meeting intent but no datetime
print("\n[Example 2] Meeting Intent (No DateTime)")
print("-" * 80)
response = client.post(
    "/email/action",
    json={
        "subject": "Let's sync",
        "body": "Can we schedule a call to discuss the project?"
    }
)
result = response.json()
print(f"Status: {response.status_code}")
print(f"Action: {result['action']}")
print(f"Message: {result['details']['message']}")
print(f"Keywords: {result['details']['meeting_intent']['matched_keywords']}")

# Example 3: Meeting intent with datetime (but no credentials)
print("\n[Example 3] Meeting Intent With DateTime (No Credentials)")
print("-" * 80)
response = client.post(
    "/email/action",
    json={
        "subject": "Team Sync Tomorrow at 2 PM",
        "body": "Let's discuss the project status."
    }
)
result = response.json()
print(f"Status: {response.status_code}")
print(f"Action: {result['action']}")
print(f"Message: {result['details']['message']}")
print(f"DateTime Extracted: {result['details']['datetime_extraction']['datetime']}")
print(f"Title: {result['details']['datetime_extraction']['title']}")
print(f"Confidence: {result['details']['meeting_intent']['confidence']}")

# Example 4: Complex email
print("\n[Example 4] Complex Email (Multiple Keywords)")
print("-" * 80)
response = client.post(
    "/email/action",
    json={
        "subject": "Quarterly Planning Session - April 8th at 10 AM",
        "body": "Hi team, let's schedule a meeting to discuss our Q2 goals. Please join our Zoom call at 10 AM tomorrow."
    }
)
result = response.json()
print(f"Status: {response.status_code}")
print(f"Action: {result['action']}")
print(f"DateTime: {result['details']['datetime_extraction']['datetime']}")
print(f"Keywords Found: {result['details']['meeting_intent']['matched_keywords']}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
The /email/action endpoint provides a complete workflow:

1. **Meeting Intent Detection**: Analyzes email for keywords
2. **DateTime Extraction**: Parses natural language dates/times
3. **Calendar Creation**: Automatically creates calendar events

Response actions:
- 'calendar_event_created' → Full success (requires OAuth credentials)
- 'meeting_detected_calendar_failed' → Meeting found, but calendar creation failed
- 'meeting_detected_no_datetime' → Meeting found, but no datetime  
- 'analysis_complete' → Email analyzed, no meeting intent

Each response includes detailed information about what was detected.
""")
