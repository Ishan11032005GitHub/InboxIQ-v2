import json
from backend.ai.classifier import predict_email

DATASET_FILE = "data/email_dataset.json"

correct = 0
total = 0

# optional: track per-label performance
label_stats = {}

with open(DATASET_FILE, "r", encoding="utf-8") as f:
    emails = json.load(f)

for email in emails:

    subject = email.get("subject", "")
    sender = email.get("sender", "")
    body = email.get("body", "")

    expected_label = email["label"]

    predicted_label = predict_email(subject, sender, body)

    is_correct = predicted_label == expected_label

    if is_correct:
        correct += 1

    total += 1

    # per-label stats
    if expected_label not in label_stats:
        label_stats[expected_label] = {"correct": 0, "total": 0}

    label_stats[expected_label]["total"] += 1

    if is_correct:
        label_stats[expected_label]["correct"] += 1

    # print each result
    print("\n--------------------------------")
    print("Subject:", subject)
    print("Predicted:", predicted_label, "| Expected:", expected_label)
    print("Result:", "✅" if is_correct else "❌")


# -------------------------------
# FINAL METRICS
# -------------------------------

print("\n==============================")
print("Total Emails:", total)

if total > 0:
    accuracy = (correct / total) * 100
else:
    accuracy = 0

print("Overall Accuracy:", round(accuracy, 2), "%")

print("\n--- Per Label Accuracy ---")

for label, stats in label_stats.items():
    if stats["total"] == 0:
        continue

    acc = (stats["correct"] / stats["total"]) * 100

    print(f"{label}: {round(acc, 2)}% ({stats['correct']}/{stats['total']})")

print("==============================")