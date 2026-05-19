import base64
import re
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from html import unescape
from typing import Any, Dict, List
from datetime import datetime

from backend.db.db import SessionLocal
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


def _message_to_email(msg_data: dict) -> dict:
    headers = msg_data.get("payload", {}).get("headers", [])

    subject = ""
    sender = ""

    for h in headers:
        if h.get("name") == "Subject":
            subject = h.get("value", "")
        elif h.get("name") == "From":
            sender = h.get("value", "")

    plain_body = ""
    html_body = ""

    def walk_parts(part: dict) -> None:
        nonlocal plain_body, html_body

        mime_type = part.get("mimeType")
        data = part.get("body", {}).get("data")

        if data and mime_type == "text/plain" and not plain_body:
            plain_body = _decode_base64(data)
        elif data and mime_type == "text/html" and not html_body:
            html_body = _html_to_text(_decode_base64(data))

        for child in part.get("parts", []) or []:
            walk_parts(child)

    walk_parts(msg_data.get("payload", {}))
    body = plain_body or html_body

    if "<html" in body.lower() or "<body" in body.lower():
        body = _html_to_text(body)

    return {
        "id": msg_data.get("id"),
        "thread_id": msg_data.get("threadId"),
        "subject": subject,
        "sender": sender,
        "body": body[:2000],
    }


def get_thread_messages(service, thread_id: str) -> list[dict]:
    if not thread_id:
        return []

    thread = service.users().threads().get(
        userId="me",
        id=thread_id,
        format="full",
    ).execute()

    messages = []
    for msg_data in thread.get("messages", []):
        parsed = _message_to_email(msg_data)
        labels = set(msg_data.get("labelIds", []))
        messages.append({
            "id": parsed.get("id"),
            "role": "sent" if "SENT" in labels else "received",
            "sender": parsed.get("sender", ""),
            "subject": parsed.get("subject", ""),
            "body": parsed.get("body", ""),
        })

    return messages


def get_unread_emails(service, max_results=500, page_token=None, max_total=500, unread_only=False):

    # ✅ LOAD SNOOZED EMAILS
    db = SessionLocal()
    snoozed_map = {
        s.id: s.remind_at
        for s in db.query(SnoozedEmail).all()
    }
    now = datetime.now()

    messages = []
    next_page_token = page_token

    label_ids = ['INBOX', 'UNREAD'] if unread_only else ['INBOX']

    while True:
        results = service.users().messages().list(
            userId='me',
            labelIds=label_ids,
            maxResults=max_results,
            pageToken=next_page_token
        ).execute()

        messages.extend(results.get('messages', []))
        next_page_token = results.get('nextPageToken')

        if not next_page_token or len(messages) >= max_total:
            break

    messages = messages[:max_total]

    emails = []
    seen_thread_ids = set()

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

        email = _message_to_email(msg_data)
        thread_id = email.get("thread_id") or email_id
        if thread_id in seen_thread_ids:
            continue
        seen_thread_ids.add(thread_id)

        thread_messages = get_thread_messages(service, thread_id)
        if thread_messages:
            latest_message_id = thread_messages[-1].get("id") or email_id
            if latest_message_id != email_id:
                latest_msg_data = service.users().messages().get(
                    userId='me',
                    id=latest_message_id,
                    format='full'
                ).execute()
                email = _message_to_email(latest_msg_data)

        email["conversation_thread"] = thread_messages
        emails.append(email)

    db.close()  # ✅ IMPORTANT

    return {
        "emails": emails,
        "next_page_token": next_page_token
    }


def send_email(service, to: str, subject: str, body: str, from_email: str | None = None, thread_id: str | None = None) -> dict:
    message = MIMEText(body)
    if from_email:
        message["From"] = from_email
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=(from_email or "inboxiq.local").split("@")[-1])

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    send_body = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id

    return service.users().messages().send(
        userId="me",
        body=send_body
    ).execute()
