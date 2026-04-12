import subprocess
import json
import os

FEEDBACK_FILE = "data/feedback.json"
THRESHOLD = 50   # retrain after 50 corrections


def should_retrain():
    if not os.path.exists(FEEDBACK_FILE):
        return False

    with open(FEEDBACK_FILE, "r") as f:
        data = json.load(f)

    return len(data) >= THRESHOLD


def retrain():
    print("🔥 Retraining model...")
    subprocess.run(["python", "train_classifier.py"])
    print("✅ Retrained")


if __name__ == "__main__":
    if should_retrain():
        retrain()