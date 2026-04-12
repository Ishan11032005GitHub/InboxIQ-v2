from auth.google_auth import get_saved_service
from gmail.gmail_utils import get_unread_emails
from ai.gemini_utils import process_inbox


def run_worker():

    # ✅ Correct service source
    service = get_saved_service()

    emails = get_unread_emails(service)

    processed = process_inbox(emails)

    for email in processed:
        print(f"{email['subject']} → {email['label']} ({email['priority']})")


if __name__ == "__main__":
    run_worker()