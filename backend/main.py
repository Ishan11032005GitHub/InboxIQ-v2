import base64
import os
import logging
from datetime import datetime, timedelta

from backend.db import db

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# from streamlit import user
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Cookie, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from backend.auth.google_auth import (
    get_authorization_data,
    exchange_code_for_credentials,
    get_gmail_service,
    load_credentials,
    load_demo_credentials,
    save_credentials,
    get_current_user,
    MOCK_USER,
)

from backend.gmail.gmail_utils import get_unread_emails, send_email
from backend.ai.gemini_utils import process_inbox, generate_reply
from backend.ai.meeting_detector import detect_meeting_intent
from backend.ai.datetime_extractor import extract_datetime
from backend.ai.action_router import get_action_bucket, BUCKET_META   # ← Tier-1
from backend.calendar.calendar_utils import create_calendar_event
from backend.memory.followup_tracker import create_followup_reminder   # ← Tier-1
from backend.memory.feedback_store import save_feedback

from backend.db.db import engine, SessionLocal, get_db
# from backend.db.models import Base
# from backend.db.models import SnoozedEmail, ProcessedEmail, ScheduledEmail, UserSession
from backend.db.db import get_db, SessionLocal

from backend.session import create_session, get_user_from_session

from googleapiclient.discovery import build
from dotenv import load_dotenv

from fastapi import WebSocket
from typing import List

from backend.db.db import engine, Base
from backend.db.models import SnoozedEmail, ScheduledEmail, ProcessedEmail, UserSession, User

# 🔥 FORCE MODEL LOAD FIRST
import backend.db.models   # REQUIRED — registers tables

print("TABLES:", Base.metadata.tables.keys())
# from sqlalchemy.orm import Session

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()


def ensure_sqlite_columns():
    columns_by_table = {
        "scheduled_emails": {
            "email_id": "VARCHAR",
            "event_link": "VARCHAR",
        },
        "snoozed_emails": {
            "remind_at": "DATETIME",
        },
        "user_sessions": {
            "mode": "VARCHAR",
        },
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table, columns in columns_by_table.items():
            if table not in existing_tables:
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table)}
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"))


Base.metadata.create_all(bind=engine)
ensure_sqlite_columns()
# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# ALLOWED_ORIGINS = [
#     "https://inbox-iq-xi.vercel.app",  # prod frontend
#     "http://localhost:3000",            # local dev
#     "http://localhost:5500",            # live server dev
# ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://inbox-iq-v2-bzxp.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# IN-MEMORY EMAIL CACHE
# ---------------------------------------------------------------------------
email_cache: dict = {}

MOCK_EMAILS = [
    # ── SCHEDULING EMAILS (30 emails) ────────────────────────────────────
    {
        "id": "m001",
        "subject": "1:1 this week?",
        "body": "Hey, can we find 30 mins this week for our usual 1:1? I'm free Thursday or Friday afternoon. Let me know what works.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m002",
        "subject": "Sprint planning — Monday 10 AM",
        "body": "Team, sprint planning is scheduled for Monday at 10 AM IST. Please come prepared with your estimates. Zoom link in the calendar invite.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m003",
        "subject": "Interview slot confirmation needed",
        "body": "Hi, we'd like to schedule your technical interview for the SDE-2 role. Are you available this Wednesday at 3 PM or Thursday at 11 AM?",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m004",
        "subject": "Project kickoff call — can you join?",
        "body": "We're kicking off the new analytics project next Tuesday at 2 PM. It'll be a 45-minute Zoom call. Please confirm your availability.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m005",
        "subject": "Reschedule our sync?",
        "body": "Hey, something came up and I need to reschedule our sync from Tuesday. Would Wednesday at 4 PM or Thursday at 10 AM work for you?",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m006",
        "subject": "Team standup — new time",
        "body": "Starting next week, our daily standup moves to 9:30 AM IST. Please update your calendars. The Zoom link remains the same.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m007",
        "subject": "Demo call with the client on Friday",
        "body": "We have a product demo scheduled with Accenture on Friday at 11 AM. Can you join? I'll need you to walk them through the dashboard features.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m008",
        "subject": "Quarterly review — save the date",
        "body": "Q2 quarterly reviews are happening on July 15th from 10 AM to 1 PM. Please block your calendar. We'll send a detailed agenda closer to the date.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m009",
        "subject": "Can we hop on a quick call?",
        "body": "Hi, I had a few questions about the API integration we discussed. Would you be free for a 15-minute call today or tomorrow morning?",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m010",
        "subject": "Doctor appointment reminder",
        "body": "This is a reminder that your appointment with Dr. Sharma is scheduled for tomorrow at 10:30 AM at Fortis Hospital. Please arrive 10 minutes early.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "high",
    },
    {
        "id": "m011",
        "subject": "Zoom call — product roadmap discussion",
        "body": "Hey team, let's get on a Zoom call this Thursday at 3 PM to walk through the H2 product roadmap. I'll share the deck beforehand.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m012",
        "subject": "Interview feedback session",
        "body": "Can we schedule a 30-minute debrief after the candidate interviews on Friday? Thinking 5 PM would work. Let me know.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m013",
        "subject": "Mentor session — this week?",
        "body": "Hi! Would love to connect for our monthly mentoring session. Are you free anytime Thursday or Friday? Even 30 minutes would be great.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m014",
        "subject": "Workshop on system design — register now",
        "body": "We're hosting an internal workshop on distributed systems design this Saturday at 11 AM. Limited seats — please confirm your attendance by Thursday.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "event_invite", "priority": "medium",
    },
    {
        "id": "m015",
        "subject": "Client call moved to 4 PM today",
        "body": "Quick heads up — the call with Razorpay has been moved from 2 PM to 4 PM today. The Google Meet link is the same as before.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m016",
        "subject": "Onboarding session for new joiners",
        "body": "The onboarding session for July batch is scheduled for Monday July 3rd at 10 AM in Conference Room B. Please be on time.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m017",
        "subject": "Architecture review meeting",
        "body": "We need to review the new microservices architecture before we proceed. Can we set up a 1-hour call this week? Tuesday or Wednesday afternoon preferred.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m018",
        "subject": "Lunch sync tomorrow?",
        "body": "Hey, want to grab lunch tomorrow and catch up? I'm free around 1 PM. Let me know if that works or if you'd prefer a quick video call instead.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m019",
        "subject": "Stand-up cancelled — async update please",
        "body": "Tomorrow's morning stand-up is cancelled due to a conflict. Please drop your update in the Slack channel by 9:30 AM. We'll resume Thursday.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m020",
        "subject": "Placement interview scheduled",
        "body": "Congratulations! You've been shortlisted. Your interview with Microsoft is scheduled for July 12th at 2 PM via Teams. Please confirm receipt.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "job_alert", "priority": "high",
    },
    {
        "id": "m021",
        "subject": "Team offsite planning call",
        "body": "We're planning the Q3 team offsite and need everyone's input. Can we get on a 30-minute call this Friday at 5 PM to finalize the dates and location?",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m022",
        "subject": "Conference call with Singapore team",
        "body": "We have a sync with the Singapore engineering team on Wednesday at 11:30 AM IST. Please join via the Zoom link that will be sent in a separate invite.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m023",
        "subject": "Hackathon kickoff — Sunday 9 AM",
        "body": "The 24-hour internal hackathon kicks off this Sunday at 9 AM. Opening ceremony in Auditorium A. Teams should be finalized by Saturday evening.",
        "sender": "ishan11032005@gmail.com",
        "label": "event_invite", "priority": "medium",
    },
    {
        "id": "m024",
        "subject": "Code review session tomorrow",
        "body": "Can we do a live code review session tomorrow afternoon? I want to walk through the new auth module together. Around 3 PM works for me.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m025",
        "subject": "Follow-up: proposal review meeting",
        "body": "Just checking in — are we still on for the proposal review this Thursday at 11 AM? Please confirm so I can send calendar invites to the stakeholders.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m026",
        "subject": "Webinar: Cloud cost optimization",
        "body": "You're registered for the AWS cost optimization webinar on July 20th at 3 PM IST. A joining link will be sent 1 hour before the session.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "event_invite", "priority": "low",
    },
    {
        "id": "m027",
        "subject": "Design review — mobile screens",
        "body": "The design review for the new mobile onboarding screens is set for Tuesday at 2 PM. Figma link is attached. We need final sign-off before dev handoff.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m028",
        "subject": "Parent-teacher meeting — July 8th",
        "body": "This is a reminder that the parent-teacher meeting is scheduled for Saturday July 8th from 10 AM to 12 PM at the school premises.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "medium",
    },
    {
        "id": "m029",
        "subject": "Investor update call next week",
        "body": "We have our monthly investor update call scheduled for next Tuesday at 4 PM. Please prepare a 5-minute update on your team's progress.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m030",
        "subject": "Training session — new deployment pipeline",
        "body": "A hands-on training session for the new CI/CD pipeline is scheduled for Friday at 2 PM in the DevOps room. Attendance is mandatory for all backend engineers.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },

    # ── REPLY-ONLY EMAILS (70 emails) ─────────────────────────────────────
    {
        "id": "m031",
        "subject": "Re: PR review request",
        "body": "Hey, I've pushed the changes you suggested. Can you take another look at the auth middleware when you get a chance? No rush.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m032",
        "subject": "Invoice #INV-2024-089",
        "body": "Please find attached the invoice for the consulting services rendered in June 2024. Total amount: ₹45,000. Please process by July 10th.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "medium",
    },
    {
        "id": "m033",
        "subject": "Your OTP for login",
        "body": "Your one-time password is 847291. This OTP is valid for 10 minutes. Do not share this with anyone.",
        "sender": "ishan11032005@gmail.com",
        "label": "security", "priority": "high",
    },
    {
        "id": "m034",
        "subject": "Feedback on your submission",
        "body": "Hi, I reviewed your assignment submission. Overall solid work. A few minor improvements needed on the database normalization section. Happy to elaborate if needed.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m035",
        "subject": "Welcome to the team!",
        "body": "Hi Ishan, welcome aboard! We're thrilled to have you join the engineering team. Your onboarding kit has been sent to your registered address. Reach out anytime.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "low",
    },
    {
        "id": "m036",
        "subject": "GitHub PR #412 merged",
        "body": "Your pull request #412 'Fix: race condition in session handler' has been merged into main. Great catch — the fix looks clean.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m037",
        "subject": "Subscription renewal notice",
        "body": "Your JetBrains All Products Pack subscription renews on July 31st. The amount of ₹24,999 will be charged to your card ending in 4821.",
        "sender": "ishan11032005@gmail.com",
        "label": "promotion", "priority": "low",
    },
    {
        "id": "m038",
        "subject": "Question about your blog post",
        "body": "Hi Ishan, I read your article on Redis caching patterns and had a question — do you recommend write-through or write-behind for high-throughput systems? Thanks.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m039",
        "subject": "Your package has been shipped",
        "body": "Your order #ORD-884721 has been shipped via Delhivery. Expected delivery: July 5th. Track your package using code DL993847214IN.",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m040",
        "subject": "Action required: expense report",
        "body": "Your June expense report is pending approval. Please submit all receipts before July 7th to avoid delays in reimbursement.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m041",
        "subject": "New login detected on your account",
        "body": "A login was detected from a new device (Windows, Chrome, Delhi) on July 2nd at 11:43 PM. If this was you, no action needed. Otherwise, secure your account.",
        "sender": "ishan11032005@gmail.com",
        "label": "security", "priority": "high",
    },
    {
        "id": "m042",
        "subject": "Internship offer letter",
        "body": "Dear Ishan, please find attached your offer letter for the Software Engineering Intern position at Razorpay. Kindly sign and return by July 10th.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m043",
        "subject": "Re: thesis draft review",
        "body": "Ishan, I've gone through chapters 3 and 4. The literature review is strong but the methodology section needs more justification for your sampling approach.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m044",
        "subject": "Stack Overflow weekly digest",
        "body": "This week's top questions: How to optimize PostgreSQL queries for large datasets? Best practices for async error handling in Node.js. Vue 3 vs React in 2024.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "newsletter", "priority": "low",
    },
    {
        "id": "m045",
        "subject": "Your LeetCode streak — 30 days!",
        "body": "Congratulations! You've maintained a 30-day solving streak on LeetCode. You've solved 47 problems this month. Keep going — you're in the top 8% this week.",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m046",
        "subject": "Reimbursement processed",
        "body": "Your reimbursement of ₹3,240 for travel expenses has been processed and will reflect in your account within 2-3 business days.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m047",
        "subject": "Research paper accepted!",
        "body": "Congratulations! Your paper 'Optimizing Transformer Inference on Edge Devices' has been accepted at IEEE COMPSAC 2024. Camera-ready submission due July 20th.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m048",
        "subject": "Follow up on the proposal",
        "body": "Hi Ishan, just following up on the project proposal I sent last week. Have you had a chance to review it? Happy to answer any questions.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m049",
        "subject": "AWS bill for June 2024",
        "body": "Your AWS bill for June is $142.37. Top services: EC2 ($89.20), S3 ($31.40), RDS ($21.77). Full breakdown attached.",
        "sender": "ishan11032005@gmail.com",
        "label": "general", "priority": "medium",
    },
    {
        "id": "m050",
        "subject": "Codeforces round results",
        "body": "Codeforces Round #912 results are out. You solved 4/6 problems and gained +48 rating points. New rating: 1834. Well done!",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m051",
        "subject": "GSoC application update",
        "body": "Your Google Summer of Code application to the TensorFlow organization has moved to the review stage. Results will be announced on May 1st.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m052",
        "subject": "Referral bonus credited",
        "body": "A referral bonus of ₹5,000 has been credited to your account for referring Priya Sharma. The amount will appear in your next payslip.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m053",
        "subject": "GitHub Copilot: new features",
        "body": "GitHub Copilot now supports multi-file edits, slash commands in chat, and deeper IDE integration. Check out the changelog for the full list of improvements.",
        "sender": "ishan11032005@gmail.com",
        "label": "newsletter", "priority": "low",
    },
    {
        "id": "m054",
        "subject": "Reminder: fee payment due",
        "body": "This is a reminder that your semester fee of ₹82,500 is due by July 15th. Late payments will incur a fine of ₹500 per day after the deadline.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "high",
    },
    {
        "id": "m055",
        "subject": "Your resume feedback",
        "body": "Ishan, I looked over your resume. The projects section is strong. I'd suggest reordering — put GSOC before the college projects. Also, quantify your impact more.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m056",
        "subject": "Password changed successfully",
        "body": "Your account password was changed on July 2nd at 3:22 PM. If you didn't make this change, please contact support immediately.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "security", "priority": "high",
    },
    {
        "id": "m057",
        "subject": "Project dependency update",
        "body": "Dependabot has detected 3 outdated dependencies in your repo: express (4.18 → 4.19), lodash (4.17.20 → 4.17.21), axios (1.4 → 1.6). Please review and merge.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m058",
        "subject": "Flipkart Big Billion Days — early access",
        "body": "As a Flipkart Plus member, you get 6-hour early access to Big Billion Days starting Oct 7th at 8 PM. Electronics, fashion, and more at up to 80% off.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "promotion", "priority": "low",
    },
    {
        "id": "m059",
        "subject": "Hackathon team registration confirmed",
        "body": "Your team 'NullPointers' has been successfully registered for Smart India Hackathon 2024. Problem statements will be released on August 1st.",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "medium",
    },
    {
        "id": "m060",
        "subject": "Monthly newsletter — The Pragmatic Engineer",
        "body": "This month: how Stripe builds internal tools, the rise of platform engineering, and an inside look at how Figma scales its backend. Enjoy the read.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "newsletter", "priority": "low",
    },
    {
        "id": "m061",
        "subject": "Database migration complete",
        "body": "The PostgreSQL to Aurora migration has completed successfully. All tables verified, zero data loss. Prod is live on the new cluster as of 2:14 AM.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m062",
        "subject": "Scholarship disbursement",
        "body": "The Merit Scholarship amount of ₹25,000 for the academic year 2024-25 has been credited to your account. Keep up the excellent academic performance.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "medium",
    },
    {
        "id": "m063",
        "subject": "Can you review this design doc?",
        "body": "Hey Ishan, I've drafted a design doc for the new notification service. Would love your thoughts before I share it with the wider team. Link: notion.so/notif-service-v2",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m064",
        "subject": "New job alert: SDE-2 at Google",
        "body": "A new job matching your profile has been posted: Software Engineer II at Google Bangalore. Skills required: Go, Kubernetes, distributed systems. Apply by Aug 15.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "job_alert", "priority": "medium",
    },
    {
        "id": "m065",
        "subject": "API rate limit warning",
        "body": "Your application 'InboxIQ-prod' has used 85% of its monthly API quota. At the current rate, you'll hit the limit in ~4 days. Consider upgrading your plan.",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "high",
    },
    {
        "id": "m066",
        "subject": "Thanks for speaking at DevFest",
        "body": "Hi Ishan, thank you so much for your talk at DevFest Guwahati. The audience loved it — 4.8/5 average rating. We'd love to have you back next year!",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m067",
        "subject": "LinkedIn: 3 new connection requests",
        "body": "You have 3 pending connection requests from Ananya Sharma (Google), Rohan Gupta (Microsoft), and Prateek Jain (Razorpay). Accept or ignore?",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m068",
        "subject": "Vercel deployment failed",
        "body": "Your deployment to Vercel failed at the build step. Error: Module not found 'react-router-dom'. This might be a missing dependency in package.json.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m069",
        "subject": "Request for recommendation letter",
        "body": "Hi Professor, I'm applying for the MS CS program at Carnegie Mellon. I would be honoured if you could write a recommendation letter for me. Deadline: Sep 1st.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m070",
        "subject": "Notion AI — new features update",
        "body": "Notion AI can now summarize meeting notes, generate action items from docs, and auto-tag pages. Available to all paid plans starting today.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "newsletter", "priority": "low",
    },
    {
        "id": "m071",
        "subject": "Payment successful — Coursera",
        "body": "Your payment of $49 for the 'Machine Learning Specialization' on Coursera has been processed. You now have full access to all course materials.",
        "sender": "ishan11032005@gmail.com",
        "label": "general", "priority": "low",
    },
    {
        "id": "m072",
        "subject": "Bug report: production issue",
        "body": "Hi, we're seeing 500 errors on the /api/v2/users endpoint in production since the last deploy. Error rate ~3%. Logs attached. Needs urgent attention.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m073",
        "subject": "Semester result declared",
        "body": "Your semester 6 results have been declared on the IIIT Guwahati portal. CGPA: 9.1. Rank in batch: 3. Congratulations on an outstanding performance!",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "medium",
    },
    {
        "id": "m074",
        "subject": "Open source contribution merged",
        "body": "Your PR to the FastAPI repository has been merged! Thanks for the fix on the WebSocket timeout handling. You're now listed as a contributor.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m075",
        "subject": "SBI account statement — June 2024",
        "body": "Your account statement for June 2024 is ready. Opening balance: ₹34,200. Closing balance: ₹51,780. Download the detailed statement from NetBanking.",
        "sender": "ishan11032005@gmail.com",
        "label": "general", "priority": "low",
    },
    {
        "id": "m076",
        "subject": "Question on your GitHub project",
        "body": "Hi Ishan, I found your NLP-based resume parser on GitHub. It's really well structured. Quick question — does it support regional language resumes?",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m077",
        "subject": "Your Medium article is trending",
        "body": "Your article 'Building scalable FastAPI apps with async SQLAlchemy' has received 2.4K views this week and is trending in the Python and Backend Dev tags.",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m078",
        "subject": "Internship stipend credited",
        "body": "Your stipend of ₹40,000 for the month of June has been credited to your account. If you have any queries, contact the HR team.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m079",
        "subject": "Suspicious login attempt blocked",
        "body": "We blocked a login attempt to your account from IP 185.220.101.47 (Tor exit node). Your account is safe. We recommend enabling 2FA if you haven't already.",
        "sender": "ishan11032005@gmail.com",
        "label": "security", "priority": "high",
    },
    {
        "id": "m080",
        "subject": "Hackerrank badge earned",
        "body": "You've earned the 5-star Gold Badge in Problem Solving on HackerRank. Your profile now ranks in the top 5% globally. Keep it up!",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m081",
        "subject": "Can you help with this ML problem?",
        "body": "Hey Ishan, I'm stuck on a class imbalance issue in my fraud detection model. SMOTE doesn't seem to be helping much. Do you have any suggestions?",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m082",
        "subject": "Your cloud certification passed!",
        "body": "Congratulations! You've passed the AWS Solutions Architect – Associate exam with a score of 847/1000. Your certificate will be available within 5 business days.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "medium",
    },
    {
        "id": "m083",
        "subject": "Feedback request — InboxIQ demo",
        "body": "Hi, thanks for demoing InboxIQ last week. I'd love to hear your feedback. What features worked well? What felt missing? Even a few lines would help a lot.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m084",
        "subject": "New follower on GitHub",
        "body": "Tanvir Ahmed and 4 others are now following you on GitHub. Your repository 'fastapi-boilerplate' was starred 12 times this week.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m085",
        "subject": "System maintenance tonight",
        "body": "Scheduled maintenance will occur tonight from 2 AM to 4 AM IST. The internal dashboard and CI/CD pipelines will be unavailable during this window.",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "medium",
    },
    {
        "id": "m086",
        "subject": "Collaboration request: research paper",
        "body": "Hi Ishan, I'm working on a paper about LLM fine-tuning for code generation. Given your background, would you be interested in co-authoring? No strict deadline yet.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m087",
        "subject": "Your Razorpay payment link expired",
        "body": "The payment link sent to your customer for ₹12,500 has expired without payment. You can generate a new link from your Razorpay dashboard.",
        "sender": "ishan11032005@gmail.com",
        "label": "general", "priority": "medium",
    },
    {
        "id": "m088",
        "subject": "Swiggy order delivered",
        "body": "Your order from Burger King (Burger + Fries + Coke) has been delivered. Hope you enjoyed your meal! Rate your experience.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "notification", "priority": "low",
    },
    {
        "id": "m089",
        "subject": "New comment on your PR",
        "body": "Rahul Verma commented on your PR #89: 'This approach will cause issues with concurrent writes. Consider using a distributed lock here.'",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m090",
        "subject": "Travel booking confirmation",
        "body": "Your flight from Guwahati to Delhi on July 15th (IndiGo 6E-441, 6:20 AM) is confirmed. PNR: XKTQ92. Check-in opens 48 hours before departure.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "medium",
    },
    {
        "id": "m091",
        "subject": "Referral for SDE role at Atlassian",
        "body": "Hey Ishan, I work at Atlassian and we're hiring for SDE roles. I can refer you directly. Send me your updated resume and I'll push it through this week.",
        "sender": "ishan11032005@gmail.com",
        "label": "job_alert", "priority": "high",
    },
    {
        "id": "m092",
        "subject": "Coursera certificate issued",
        "body": "Your certificate for 'Deep Learning Specialization' by deeplearning.ai has been issued. Share it on LinkedIn to showcase your new skills.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
    {
        "id": "m093",
        "subject": "Important: update your KYC",
        "body": "Your KYC documents on file are expiring on July 31st. Please upload updated Aadhaar and PAN card copies to avoid service interruption.",
        "sender": "ishan11032005@gmail.com",
        "label": "notification", "priority": "high",
    },
    {
        "id": "m094",
        "subject": "Project report submission reminder",
        "body": "This is a reminder that your final project report is due on July 20th by 11:59 PM. Submissions after the deadline will not be accepted.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "high",
    },
    {
        "id": "m095",
        "subject": "Thank you for your purchase",
        "body": "Thank you for purchasing a MacBook Pro M3 from Apple Store. Order #APL-2024-88721. Estimated delivery: July 8-10. You'll receive a tracking link shortly.",
        "sender": "ishan11032005@gmail.com",
        "label": "general", "priority": "low",
    },
    {
        "id": "m096",
        "subject": "Weekly digest — Hacker News",
        "body": "Top stories this week: OpenAI launches GPT-5, Cloudflare announces free Workers AI tier, Rust overtakes Python as most loved language for 9th year running.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "newsletter", "priority": "low",
    },
    {
        "id": "m097",
        "subject": "Ping: quick question on the infra",
        "body": "Hey, quick question — are we using Redis for session storage in prod or is it still in-memory? Need to know before I push the horizontal scaling config.",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m098",
        "subject": "Your Figma file was shared",
        "body": "Sneha Kapoor shared 'InboxIQ — UI v3.1' with you on Figma. You have editor access. Open the file to view the latest design updates.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "work", "priority": "medium",
    },
    {
        "id": "m099",
        "subject": "Slack: you were mentioned",
        "body": "@ishan you were mentioned in #backend-team: 'Can you check if the Kafka consumer lag has gone down after yesterday's fix? Looks like there's still some backlog.'",
        "sender": "ishan11032005@gmail.com",
        "label": "work", "priority": "high",
    },
    {
        "id": "m100",
        "subject": "Congratulations on completing the challenge!",
        "body": "You successfully completed the 30-day system design challenge. Your final submission scored 91/100. Certificate and badge have been added to your profile.",
        "sender": "ishan.tiwari23b@iiitg.ac.in",
        "label": "general", "priority": "low",
    },
]


# from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# ---------------------------------------------------------------------------
# DB INIT
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup():
    import backend.db.models
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()

    # 🔥 LOAD MOCK INTO CACHE
    for email in MOCK_EMAILS:
        email_cache[email["id"]] = email


# ---------------------------------------------------------------------------
# DEMO LOGIN
# ---------------------------------------------------------------------------
from fastapi.responses import JSONResponse
from fastapi import Response

@app.get("/demo")
def demo_login(response: Response):
    session_id = create_session(user_id="demo-user", mode="demo")

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=86400,
    )

    return {"success": True}


# ---------------------------------------------------------------------------
# AUTH STATUS
# ---------------------------------------------------------------------------
@app.get("/auth/status")
def auth_status(session_id: str = Cookie(None)):
    session = get_user_from_session(session_id)

    if not session:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user": session["user_id"],
        "mode": session["mode"]
    }


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------
@app.get("/auth/login")
def login():
    data          = get_authorization_data()
    auth_url      = data["auth_url"]
    state         = data["state"]
    code_verifier = data.get("code_verifier") or ""

    logger.info("LOGIN | state=%s | verifier_present=%s", state, bool(code_verifier))

    response = RedirectResponse(url=auth_url)
    response.set_cookie(key="oauth_state",         value=state,         httponly=True, secure=False, samesite="lax", path="/", max_age=600)
    response.set_cookie(key="oauth_code_verifier", value=code_verifier, httponly=True, secure=False, samesite="lax", path="/", max_age=600)
    return response


def get_email_from_cache_or_db(email_id, db):
    # 1. try cache
    if email_id in email_cache:
        return dict(email_cache[email_id])

    # 2. try DB (processed emails table)
    record = db.query(ProcessedEmail).filter_by(id=email_id).first()

    if record:
        return {
            "id": record.id,
            "subject": "Scheduled Email",
            "sender": "",
            "body": "",
            "label": "general",
            "priority": "low"
        }

    return None


def get_mock_or_cached_email(email_id: str) -> dict | None:
    if email_id in email_cache:
        return dict(email_cache[email_id])

    email = next((item for item in MOCK_EMAILS if item["id"] == email_id), None)
    return dict(email) if email else None

# ---------------------------------------------------------------------------
# CALLBACK
# ---------------------------------------------------------------------------
@app.get("/auth/callback")
def auth_callback(
    request: Request,
    oauth_state: str         = Cookie(default=None),
    oauth_code_verifier: str = Cookie(default=None),
):
    logger.info("CALLBACK | url=%s", str(request.url))

    if not oauth_state:
        raise HTTPException(400, "oauth_state cookie missing.")
    if not oauth_code_verifier:
        raise HTTPException(400, "oauth_code_verifier cookie missing.")

    try:
        creds = exchange_code_for_credentials(
            authorization_response_url=str(request.url),
            state=oauth_state,
            code_verifier=oauth_code_verifier,
        )

        oauth2_service = build("oauth2", "v2", credentials=creds)
        user_info      = oauth2_service.userinfo().get().execute()
        email: str     = user_info["email"]
        logger.info("CALLBACK | email=%s", email)

        save_credentials(email, creds)
        session_id = create_session(user_id=email, mode="gmail")

        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500/frontend/index.html")
        response = RedirectResponse(url=frontend_url)
        response.set_cookie(key="session_id",value=session_id,httponly=True,samesite="lax",secure=False,max_age=86400)
        response.delete_cookie("oauth_state",         path="/")
        response.delete_cookie("oauth_code_verifier", path="/")
        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("CALLBACK | failed: %s", exc)
        raise HTTPException(500, f"OAuth failed: {exc}")


# ---------------------------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------------------------
@app.post("/auth/logout")
def logout():
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("session_id",          path="/")
    response.delete_cookie("oauth_state",         path="/")
    response.delete_cookie("oauth_code_verifier", path="/")
    return response

# ── MODULE-LEVEL MEETING CACHE (computed once per server start) ──────────
_meeting_cache: dict[str, bool] = {}

def _get_needs_meeting(email_id: str, subject: str, body: str) -> bool:
    if email_id in _meeting_cache:
        return _meeting_cache[email_id]

    text_value = f"{subject} {body}".lower()
    meeting_terms = (
        "appointment",
        "calendar",
        "call",
        "interview",
        "meeting",
        "schedule",
        "sync",
        "zoom",
    )
    _meeting_cache[email_id] = any(term in text_value for term in meeting_terms)
    return _meeting_cache[email_id]


logger.info("Meeting detection for mock emails uses local keyword matching")


@app.get("/emails")
def get_emails(session_id: str = Cookie(None)):
    session = get_user_from_session(session_id)

    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 🔥 DEMO MODE
    if session["mode"] == "demo":
        emails = [
            {
                **email,
                "needs_meeting": _get_needs_meeting(
                    email["id"],
                    email.get("subject", ""),
                    email.get("body", ""),
                ),
            }
            for email in MOCK_EMAILS
        ]
        return {"emails": emails}

    # 🔥 REAL GMAIL MODE
    creds = load_credentials(session["user_id"])

    if not creds:
        raise HTTPException(status_code=401, detail="No credentials")

    service = get_gmail_service(creds)
    emails = get_unread_emails(service)

    return {"emails": emails}


@app.get("/emails/scheduled")
def get_scheduled(session_id: str = Cookie(default=None)):
    session = get_user_from_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = session["user_id"]
    db = SessionLocal()

    try:
        scheduled_list = db.query(ScheduledEmail).filter_by(user_id=user_id).all()

        result = []

        for s in scheduled_list:
            email = get_mock_or_cached_email(s.email_id)
            if not email:
                continue

            email_copy = dict(email)
            email_copy["action_bucket"] = "SCHEDULED"
            email_copy["event_link"] = s.event_link

            result.append(email_copy)

        return {"emails": result}

    finally:
        db.close()

@app.post("/email/unsnooze")
async def unsnooze_email(payload: dict, db: Session = Depends(get_db), session_id: str = Cookie(None)):
    session = get_user_from_session(session_id)
    if not session:
        raise HTTPException(401)

    user_id = session["user_id"]
    email_id = payload.get("id")

    db.query(SnoozedEmail).filter(
        SnoozedEmail.id == email_id,
        SnoozedEmail.user_id == user_id
    ).delete()

    db.commit()

    await manager.broadcast({
        "type": "UNSNOOZED",
        "email_id": email_id
    })

    return {"success": True}

# from fastapi import WebSocket
from typing import List

# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: dict[str, List[WebSocket]] = {}

#     async def connect(self, user_id: str, websocket: WebSocket):
#         await websocket.accept()
#         self.active_connections.setdefault(user_id, []).append(websocket)

#     def disconnect(self, user_id: str, websocket: WebSocket):
#         self.active_connections[user_id].remove(websocket)

#     async def send(self, user_id: str, message: dict):
#         for ws in self.active_connections.get(user_id, []):
#             await ws.send_json(message)

# manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()
    except:
        manager.disconnect(websocket)

# ---------------------------------------------------------------------------
# HELPER — resolve credentials
# ---------------------------------------------------------------------------
def _resolve_credentials(user_id: str):
    if user_id == "demo-user":
        # Don't attempt real Google credentials for demo — just return None
        # The caller handles None gracefully with a mock event
        raw = os.getenv("DEMO_GOOGLE_CREDENTIALS")
        if not raw:
            logger.debug("Demo mode: no credentials configured, using mock")
            return None
        creds = load_demo_credentials()
        return creds
    return load_credentials(user_id)


# ---------------------------------------------------------------------------
# INTELLIGENT EMAIL PIPELINE
# ---------------------------------------------------------------------------
@app.post("/email/analyze")
@app.post("/email/process")
async def process_email(request: Request, user: dict = Depends(get_current_user)):
    data = await request.json()
    email_id = data.get("id")

    if email_id not in email_cache:
        raise HTTPException(status_code=404, detail="Email not found")

    email = email_cache[email_id]
    db = SessionLocal()

    try:
        existing_record = db.query(ProcessedEmail).filter_by(
            id=email_id,
            user_id=user["user_id"]
        ).first()

        # 🔥 ONLY GENERATE REPLY (NO SCHEDULING LOGIC)
        try:
            reply = generate_reply(email, "professional")
        except Exception:
            reply = "AI reply unavailable right now."

        if existing_record:
            existing_record.action_bucket = "NEEDS_REPLY"
            existing_record.reply = reply
        else:
            db.add(ProcessedEmail(
                id=email_id,
                user_id=user["user_id"],
                action_bucket="NEEDS_REPLY",
                reply=reply
            ))

        db.commit()

        email_cache[email_id]["reply"] = reply
        email_cache[email_id]["action_bucket"] = "NEEDS_REPLY"

        return {
            "type": "reply",
            "reply": reply,
            "action_bucket": "NEEDS_REPLY",
            "bucket_meta": BUCKET_META["NEEDS_REPLY"],
            "email": email_cache[email_id],
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Processing failed")

    finally:
        db.close()

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

@app.post("/email/schedule")
async def schedule_email(payload: dict, db: Session = Depends(get_db), session_id: str = Cookie(None)):
    session = get_user_from_session(session_id)
    if not session:
        raise HTTPException(401)

    user_id = session["user_id"]
    email_id = payload.get("id")

    email = get_mock_or_cached_email(email_id)
    if not email:
        raise HTTPException(404)

    event_link = None

    record = ScheduledEmail(
        id=email_id,
        email_id=email_id,
        user_id=user_id,
        event_link=event_link
    )

    db.merge(record)
    db.commit()

    await manager.broadcast({
        "type": "SCHEDULED",
        "email_id": email_id,
        "event_link": event_link
    })

    return {"success": True, "event_link": event_link}


@app.post("/email/snooze")
async def snooze_email(payload: dict, db: Session = Depends(get_db), session_id: str = Cookie(None)):
    session = get_user_from_session(session_id)
    if not session:
        raise HTTPException(401)

    user_id = session["user_id"]
    email_id = payload.get("id")

    remind_at = datetime.utcnow() + timedelta(hours=3)

    snoozed = SnoozedEmail(
        id=email_id,
        user_id=user_id,
        remind_at=remind_at
    )

    db.merge(snoozed)
    db.commit()

    await manager.broadcast({
        "type": "SNOOZED",
        "email_id": email_id,
        "remind_at": remind_at.isoformat()
    })

    return {"success": True, "remind_at": remind_at.isoformat()}

@app.get("/emails/snoozed")
def get_snoozed(session_id: str = Cookie(default=None)):
    session = get_user_from_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = session["user_id"]
    db = SessionLocal()

    try:
        emails = db.query(SnoozedEmail).filter_by(user_id=user_id).all()

        result = []

        for e in emails:
            email = get_mock_or_cached_email(e.id)
            if not email:
                continue

            email_copy = dict(email)
            email_copy["remind_at"] = e.remind_at.isoformat()

            result.append(email_copy)

        return {"emails": result}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# SEND EMAIL  + auto follow-up reminder
# ---------------------------------------------------------------------------
@app.post("/send-email")
async def send(request: Request, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    data = await request.json()

    if user.get("user_id") == "demo-user":
        # Still create a follow-up reminder on the demo calendar
        creds = _resolve_credentials("demo-user")
        if creds:
            create_followup_reminder(
                credentials=creds,
                original_subject=data.get("subject", "(no subject)"),
                sender_email=data.get("to", ""),
                hours=48,
                timezone=os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata"),
            )
        return {"status": "sent (demo)", "followup_scheduled": creds is not None}

    creds   = load_credentials(user_id)
    service = get_gmail_service(creds)
    send_email(service, data["to"], data["subject"], data["body"])

    # ── Follow-up Tracker ────────────────────────────────────────────────
    # After every sent reply, schedule a 48-hour follow-up reminder so the
    # user is nudged if there's no response.
    followup_result = create_followup_reminder(
        credentials=creds,
        original_subject=data.get("subject", "(no subject)"),
        sender_email=data.get("to", ""),
        hours=48,
        timezone=os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata"),
    )

    return {
        "status":             "sent",
        "followup_scheduled": followup_result["success"],
        "followup_link":      followup_result.get("event_link"),
    }

def get_email_safe(email_id):
    if email_id in email_cache:
        return dict(email_cache[email_id])

    # fallback to DB record (basic)
    return {
        "id": email_id,
        "subject": "Scheduled email",
        "sender": "",
        "body": ""
    }

@app.post("/email/cancel-schedule")
async def cancel_schedule(payload: dict, db: Session = Depends(get_db), session_id: str = Cookie(None)):
    session = get_user_from_session(session_id)
    if not session:
        raise HTTPException(401)

    user_id = session["user_id"]
    email_id = payload.get("id")

    db.query(ScheduledEmail).filter(
        ScheduledEmail.email_id == email_id,
        ScheduledEmail.user_id == user_id
    ).delete()

    db.commit()

    await manager.broadcast({
        "type": "CANCEL_SCHEDULED",
        "email_id": email_id
    })

    return {"success": True}
# ---------------------------------------------------------------------------
# SNOOZE  — defer an email by creating a Calendar reminder
# ---------------------------------------------------------------------------
# ---------------------- SNOOZE FIX ----------------------


# @app.get("/emails/snoozed")
# def get_snoozed_emails(user: dict = Depends(get_current_user)):
#     db = SessionLocal()

#     snoozed = db.query(SnoozedEmail).filter(
#         SnoozedEmail.user_id == user["user_id"]
#     ).all()

#     result = []

#     for s in snoozed:
#         # ----------------------
#         # 🔥 SAFE FETCH (CRITICAL FIX)
#         # ----------------------
#         email = email_cache.get(s.id, {
#             "id": s.id,
#             "subject": "(Snoozed Email)",
#             "sender": "Unknown",
#             "body": "",
#         })

#         # ----------------------
#         # 🔥 NORMALIZE DATA (avoid frontend issues)
#         # ----------------------
#         if "label" not in email:
#             email["label"] = "general"
#         if "priority" not in email:
#             email["priority"] = "low"

#         email["remind_at"] = s.remind_at.isoformat()

#         result.append(email)

#     db.close()

#     return {"emails": result}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=10000, reload=True)









































































