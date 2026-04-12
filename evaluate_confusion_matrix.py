import json
import os
import joblib
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

DATASET_PATH = "data/email_dataset.json"
MODEL_PATH = "backend/model/email_model.pkl"
VECTORIZER_PATH = "backend/model/vectorizer.pkl"
OUTPUT_PATH = "confusion_matrix.png"


# -------------------------------
# BUILD TEXT
# -------------------------------
def build_text(email):
    subject = email.get("subject", "")
    sender = email.get("sender", "")
    body = email.get("body", "")
    return f"{subject} {sender} {body}"


# -------------------------------
# LOAD DATA
# -------------------------------
def load_data():
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = []
    labels = []

    for email in data:
        if "label" not in email:
            continue
        texts.append(build_text(email))
        labels.append(email["label"])

    return texts, labels


# -------------------------------
# LOAD MODEL
# -------------------------------
def load_saved_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    if not os.path.exists(VECTORIZER_PATH):
        raise FileNotFoundError(f"Vectorizer not found: {VECTORIZER_PATH}")

    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)

    return model, vectorizer


# -------------------------------
# EVALUATE
# -------------------------------
def evaluate():
    print("Loading dataset...")
    texts, labels = load_data()

    print(f"Total samples: {len(texts)}")

    if len(texts) < 10:
        raise ValueError("Dataset too small for evaluation.")

    # Same split setup as training
    _, X_test, _, y_test = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels
    )

    print("Loading saved model...")
    model, vectorizer = load_saved_model()

    print("Vectorizing test data...")
    X_test_vec = vectorizer.transform(X_test)

    print("Running predictions...")
    y_pred = model.predict(X_test_vec)

    acc = accuracy_score(y_test, y_pred)

    print("\nAccuracy:", round(acc * 100, 2), "%")
    print("\nClassification Report:\n")
    print(classification_report(y_test, y_pred))

    labels_order = sorted(list(set(y_test) | set(y_pred)))

    cm = confusion_matrix(y_test, y_pred, labels=labels_order)

    plt.figure(figsize=(10, 8))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels_order)
    disp.plot(xticks_rotation=45, cmap="Blues", values_format="d")
    plt.title("Confusion Matrix")
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
    plt.show()

    print(f"\nConfusion matrix saved as: {OUTPUT_PATH}")


if __name__ == "__main__":
    evaluate()
