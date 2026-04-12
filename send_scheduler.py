from automation.scheduler import load_queue, save_queue
from auth.google_auth import get_saved_service
from gmail.gmail_utils import send_email
from datetime import datetime
import time


def run_scheduler():

    service = get_saved_service()
    queue = load_queue()

    remaining = []
    now = datetime.utcnow()

    for email in queue:

        send_time = datetime.fromisoformat(email["send_time"])

        if send_time <= now:

            send_email(
                service,
                email["to"],
                email["subject"],
                email["body"]
            )

        else:
            remaining.append(email)

    save_queue(remaining)


if __name__ == "__main__":
    while True:
        run_scheduler()
        time.sleep(30)