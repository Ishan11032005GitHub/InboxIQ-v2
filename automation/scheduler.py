import json
import os
from datetime import datetime

QUEUE_FILE = "scheduled_emails.json"


def load_queue():

    if not os.path.exists(QUEUE_FILE):
        return []

    with open(QUEUE_FILE,"r") as f:
        return json.load(f)


def save_queue(queue):

    with open(QUEUE_FILE,"w") as f:
        json.dump(queue,f,indent=2)


def schedule_email(to,subject,body,send_time):

    queue = load_queue()

    queue.append({
        "to":to,
        "subject":subject,
        "body":body,
        "send_time":send_time.isoformat()
    })

    save_queue(queue)