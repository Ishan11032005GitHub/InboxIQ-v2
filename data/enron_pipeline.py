import os
import json
import re


# -------------------------------
# LOAD ENRON EMAILS
# -------------------------------
def load_enron(root_dir):
    emails = []

    for root, _, files in os.walk(root_dir):
        for file in files:
            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="latin-1") as f:
                    emails.append(f.read())
            except:
                continue

    return emails


# -------------------------------
# PARSE EMAIL
# -------------------------------
def parse_email(raw):

    lines = raw.split("\n")

    subject = ""
    sender = ""
    body = []
    is_body = False

    for line in lines:

        if line.startswith("Subject:"):
            subject = line.replace("Subject:", "").strip()

        elif line.startswith("From:"):
            sender = line.replace("From:", "").strip()

        elif line.strip() == "":
            is_body = True
            continue

        elif is_body:
            body.append(line)

    return {
        "subject": subject,
        "sender": sender,
        "body": " ".join(body)
    }


# -------------------------------
# CLEAN TEXT
# -------------------------------
def clean_text(text):
    text = text.lower()
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"[^a-zA-Z ]", " ", text)
    return text.strip()


# -------------------------------
# WEAK LABELING
# -------------------------------
def weak_label(email):

    text = (email["subject"] + " " + email["body"]).lower()
    sender = email["sender"].lower()

    if any(k in text for k in ["meeting", "call", "deadline"]):
        return "work"

    if any(k in text for k in ["unsubscribe", "newsletter", "digest"]):
        return "newsletter"

    if any(k in text for k in ["discount", "offer", "sale"]):
        return "promotion"

    if any(k in text for k in ["hiring", "apply", "job"]):
        return "job_alert"

    if any(k in text for k in ["security", "password", "verify"]):
        return "security"

    if "github" in sender or "linkedin" in sender:
        return "notification"

    return "general"


# -------------------------------
# FILTER
# -------------------------------
def is_valid(email):
    return len(email["body"]) > 20 and email["subject"] != ""


# -------------------------------
# BUILD DATASET
# -------------------------------
def build_dataset(root_dir, save_path="data/enron_dataset.json"):

    raw_emails = load_enron(root_dir)

    dataset = []

    for raw in raw_emails:

        parsed = parse_email(raw)

        if not is_valid(parsed):
            continue

        parsed["subject"] = clean_text(parsed["subject"])
        parsed["body"] = clean_text(parsed["body"])

        label = weak_label(parsed)

        dataset.append({
            "subject": parsed["subject"],
            "sender": parsed["sender"],
            "body": parsed["body"],
            "label": label
        })

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    print(f"Saved {len(dataset)} samples to {save_path}")