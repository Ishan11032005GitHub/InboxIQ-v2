import base64
import re
from email.mime.text import MIMEText
from html import unescape
from typing import Any, Dict, List
from datetime import datetime

from backend.db.database import SessionLocal
from backend.db.models import SnoozedEmail


def _decode_base64(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _html_to_text(html: str) -> str:
    if not html:
        return ""

    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n", html)
    html = re.sub(r"(?i)</div>", "\n", html)
    html = re.sub(r"(?i)</li>", "\n", html)
    html = re.sub(r"(?i)</tr>", "\n", html)
    html = re.sub(r"(?i)</h[1-6]>", "\n", html)

    html = re.sub(r"(?s)<.*?>", " ", html)
    text = unescape(html)

    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def get_unread_emails(service, max_results=5, page_token=None):

    # ✅ LOAD SNOOZED EMAILS
    db = SessionLocal()
    snoozed_map = {
        s.id: s.remind_at
        for s in db.query(SnoozedEmail).all()
    }
    now = datetime.now()

    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX', 'UNREAD'],
        maxResults=max_results,
        pageToken=page_token
    ).execute()

    messages = results.get('messages', [])
    next_page_token = results.get('nextPageToken')

    emails = []

    for msg in messages:
        email_id = msg['id']

        # ❌ FILTER SNOOZED EMAILS
        if email_id in snoozed_map and snoozed_map[email_id] > now:
            continue

        msg_data = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()

        headers = msg_data['payload'].get('headers', [])

        subject = ""
        sender = ""

        for h in headers:
            if h['name'] == 'Subject':
                subject = h['value']
            elif h['name'] == 'From':
                sender = h['value']

        body = ""

        if 'parts' in msg_data['payload']:
            for part in msg_data['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        else:
            data = msg_data['payload']['body'].get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')

        emails.append({
            "id": email_id,
            "subject": subject,
            "sender": sender,
            "body": body[:2000]
        })

    db.close()  # ✅ IMPORTANT

    return {
        "emails": emails,
        "next_page_token": next_page_token
    }


def send_email(service, to: str, subject: str, body: str) -> None:
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()