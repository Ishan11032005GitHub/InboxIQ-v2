import json
import random

OUTPUT_FILE = "data/email_dataset.json"
NUM_SAMPLES = 500

labels = [
    "job_alert",
    "promotion",
    "newsletter",
    "event_invite",
    "notification",
    "work",
    "security",
    "general"
]

# REALISTIC SUBJECT POOL (MESSY + OVERLAPPING)
subjects_pool = [
    ("We are hiring for backend roles – apply now", "job_alert"),
    ("Internship opportunity + webinar invite", "job_alert"),
    ("Join our AI webinar this weekend", "event_invite"),
    ("50% off on courses – limited seats for workshop", "promotion"),
    ("Your LinkedIn post got 120 impressions", "notification"),
    ("GitHub: Your PR #42 was merged", "notification"),
    ("Weekly AI newsletter – top trends", "newsletter"),
    ("Top startups hiring this week", "newsletter"),
    ("Security alert: suspicious login detected", "security"),
    ("Verify your account immediately", "security"),
    ("Meeting tomorrow regarding project update", "work"),
    ("Client deadline extended – review required", "work"),
    ("Let’s catch up this weekend", "general"),
    ("Dinner plan and trip details", "general"),
    ("Exclusive deal for AI webinar participants", "promotion"),
    ("Job alert: hiring + free course access", "job_alert"),
]

senders_pool = [
    ("noreply@linkedin.com", "newsletter"),
    ("jobs@company.com", "job_alert"),
    ("careers@startup.ai", "job_alert"),
    ("notifications@github.com", "notification"),
    ("security@google.com", "security"),
    ("alerts@bank.com", "security"),
    ("offers@udemy.com", "promotion"),
    ("deals@amazon.com", "promotion"),
    ("newsletter@techdaily.com", "newsletter"),
    ("events@kaggle.com", "event_invite"),
    ("team@company.com", "work"),
    ("manager@company.com", "work"),
    ("friend@gmail.com", "general"),
    ("family@yahoo.com", "general"),
]

bodies_pool = [
    ("We are actively hiring engineers. Apply today.", "job_alert"),
    ("Join our webinar and learn Gen AI concepts.", "event_invite"),
    ("Huge discount available. Limited time only.", "promotion"),
    ("Here are your weekly updates and insights.", "newsletter"),
    ("Your pull request has been successfully merged.", "notification"),
    ("Unusual login detected. Please verify.", "security"),
    ("Let’s discuss this in tomorrow’s meeting.", "work"),
    ("Hope you're doing well. Let's catch up soon.", "general"),
    ("Free course access with job application.", "job_alert"),
    ("Register now. Limited seats for workshop.", "event_invite"),
    ("You received new engagement on your post.", "notification"),
    ("Please review the attached file before deadline.", "work"),
]

def noisy_label(subject_label, sender_label, body_label):
    return subject_label


def generate_email():

    subject, s_label = random.choice(subjects_pool)
    sender, se_label = random.choice(senders_pool)
    body, b_label = random.choice(bodies_pool)

    label = noisy_label(s_label, se_label, b_label)

    return {
        "subject": subject,
        "sender": sender,
        "body": body,
        "label": label
    }


def generate_dataset():
    data = []

    for label in labels:
        for _ in range(NUM_SAMPLES // len(labels)):
            data.append(generate_email_with_label(label))

    random.shuffle(data)
    return data

def generate_email_with_label(label):

    subject, _ = random.choice([s for s in subjects_pool if s[1] == label])
    sender, _ = random.choice([s for s in senders_pool if s[1] == label])
    body, _ = random.choice([b for b in bodies_pool if b[1] == label])

    return {
        "subject": subject,
        "sender": sender,
        "body": body,
        "label": label
    }


if __name__ == "__main__":

    dataset = generate_dataset()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    print(f"Generated {len(dataset)} realistic noisy emails → {OUTPUT_FILE}")

