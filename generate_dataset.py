import json
import random

# -------------------------------
# LABELS
# -------------------------------
labels = [
    "job_alert", "newsletter", "promotion",
    "event_invite", "work", "security",
    "notification", "general"
]

# -------------------------------
# BASE SENTENCES (NEUTRAL TEXT)
# -------------------------------
base_sentences = [
    "Please check the details below",
    "Let me know your thoughts",
    "Sharing this for your reference",
    "We should connect soon",
    "Here is something important",
    "Just wanted to inform you",
    "See the update below",
    "This might interest you",
    "Kindly review and respond",
    "Following up on this",
]

# -------------------------------
# KEYWORDS (SIGNAL)
# -------------------------------
keywords = {
    "job_alert": ["hiring", "role", "position", "internship"],
    "newsletter": ["newsletter", "digest", "weekly update"],
    "promotion": ["offer", "sale", "discount", "deal"],
    "event_invite": ["webinar", "event", "register", "session"],
    "work": ["meeting", "deadline", "project", "call"],
    "security": ["password", "verify", "security", "alert"],
    "notification": ["notification", "update", "activity"],
    "general": []  # IMPORTANT: no keywords
}

# -------------------------------
# SENDERS (REALISM)
# -------------------------------
senders = [
    "hr@company.com",
    "noreply@service.com",
    "alerts@github.com",
    "jobs@linkedin.com",
    "team@startup.com",
    "support@platform.com",
    "info@random.com"
]


# -------------------------------
# EMAIL GENERATOR
# -------------------------------
def generate_email(label):

    subject = random.choice(base_sentences)
    sender = random.choice(senders)

    body_parts = []

    # ✅ ALWAYS include correct signal (if exists)
    if keywords[label]:
        body_parts.append(random.choice(keywords[label]))

    # ⚠️ SOMETIMES include wrong signal (controlled noise)
    if random.random() < 0.3:
        wrong_label = random.choice(labels)
        if wrong_label != label and keywords[wrong_label]:
            body_parts.append(random.choice(keywords[wrong_label]))

    # ✅ add neutral text (structure realism)
    for _ in range(random.randint(2, 4)):
        body_parts.append(random.choice(base_sentences))

    random.shuffle(body_parts)

    body = ". ".join(body_parts)

    return {
        "subject": subject,
        "sender": sender,
        "body": body,
        "label": label
    }


# -------------------------------
# DATASET CREATION
# -------------------------------
dataset = []

for label in labels:
    for _ in range(400):   # 400 per class → 3200 total
        dataset.append(generate_email(label))

random.shuffle(dataset)

# -------------------------------
# SAVE
# -------------------------------
with open("data/email_dataset.json", "w") as f:
    json.dump(dataset, f, indent=2)

print("Dataset generated:", len(dataset))
