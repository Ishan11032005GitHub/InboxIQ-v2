import json
import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

DATASET_PATH = "data/email_dataset.json"
MODEL_DIR = "model"


# -------------------------------
# BUILD TEXT (IMPORTANT)
# -------------------------------
def build_text(email):
    return f"{email['subject']} {email['sender']} {email['body']}"


# -------------------------------
# LOAD + CLEAN DATA
# -------------------------------
def load_data():

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = []
    labels = []

    for email in data:
        text = f"{email['subject']} {email['sender']} {email['body']}"
        texts.append(text)
        labels.append(email["label"])

    return texts, labels


# -------------------------------
# TRAIN
# -------------------------------
def train():

    print("Loading dataset...")
    texts, labels = load_data()

    print(f"Total samples: {len(texts)}")

    if len(texts) < 50:
        raise ValueError("Dataset too small. Your Enron pipeline is broken.")

    # -------------------------------
    # SPLIT
    # -------------------------------

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    # -------------------------------
    # TF-IDF
    # -------------------------------
    print("Vectorizing text...")

    vectorizer = TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 2),
        stop_words="english",
        min_df=2
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # -------------------------------
    # MODEL
    # -------------------------------
    print("Training model...")

    model = LogisticRegression(
        max_iter=2000,
        class_weight="balanced"
    )

    model.fit(X_train_vec, y_train)

    # -------------------------------
    # EVALUATION
    # -------------------------------
    print("Evaluating...")

    y_pred = model.predict(X_test_vec)

    acc = accuracy_score(y_test, y_pred)

    print("\nAccuracy:", round(acc * 100, 2), "%")
    print("\nClassification Report:\n")
    print(classification_report(y_test, y_pred))

    # -------------------------------
    # SAVE
    # -------------------------------
    import os
    os.makedirs(MODEL_DIR, exist_ok=True)

    joblib.dump(model, os.path.join(MODEL_DIR, "email_model.pkl"))
    joblib.dump(vectorizer, os.path.join(MODEL_DIR, "vectorizer.pkl"))

    print("\nModel saved to /model")


if __name__ == "__main__":
    train()