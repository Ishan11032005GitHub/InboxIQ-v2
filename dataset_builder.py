from ai.classifier import rule_override
import json


def auto_label(email):

    label = rule_override(
        email["subject"],
        email["sender"],
        email["body"]
    )

    return label if label else "general"


def build_dataset(raw_emails):

    dataset = []

    for email in raw_emails:

        label = auto_label(email)

        dataset.append({
            "subject": email["subject"],
            "sender": email["sender"],
            "body": email["body"],
            "label": label
        })

    with open("data/email_dataset.json", "w") as f:
        json.dump(dataset, f, indent=2)