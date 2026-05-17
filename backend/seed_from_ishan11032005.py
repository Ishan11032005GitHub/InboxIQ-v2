import argparse
import base64
import json
import os
import sys
import time
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path = [
    path for path in sys.path
    if Path(path or ".").resolve() != SCRIPT_DIR
]
sys.path.insert(0, str(PROJECT_ROOT))

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.main import MOCK_EMAILS


SENDER = "ishan11032005@gmail.com"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def load_credentials() -> Credentials:
    raw = os.getenv("ISHAN11032005_GOOGLE_CREDENTIALS")
    if not raw:
        raise RuntimeError("Set ISHAN11032005_GOOGLE_CREDENTIALS to this sender's OAuth token JSON or base64 JSON.")

    try:
        payload = base64.b64decode(raw).decode("utf-8")
        info = json.loads(payload)
    except Exception:
        info = json.loads(raw)

    creds = Credentials.from_authorized_user_info(info, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
    return creds


def send_email(service, recipient: str, subject: str, body: str) -> None:
    message = MIMEText(body)
    message["From"] = SENDER
    message["To"] = recipient
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=SENDER.split("@")[-1])

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Seed InboxIQ demo emails from {SENDER}.")
    parser.add_argument("--to", default=os.getenv("DEMO_GMAIL_USER", "demoinboxiq@gmail.com"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    service = build("gmail", "v1", credentials=load_credentials())
    emails = [email for email in MOCK_EMAILS if email.get("sender") == SENDER][: args.limit]

    for index, email in enumerate(emails, start=1):
        subject = f"[InboxIQ Demo {index:03d}] {email.get('subject') or 'Demo email'}"
        body = email.get("body") or ""
        send_email(service, args.to, subject, body)
        print(f"Sent {index}/{len(emails)}: {subject}")
        time.sleep(args.delay)

    print(f"Done. Sent {len(emails)} emails from {SENDER} to {args.to}.")


if __name__ == "__main__":
    main()
