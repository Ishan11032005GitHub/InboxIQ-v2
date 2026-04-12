#classifier.py

import os
import joblib
from functools import lru_cache
from typing import Tuple


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "model", "email_model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "model", "vectorizer.pkl")


@lru_cache()
def load_model() -> Tuple[object, object]:
    if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VECTORIZER_PATH)
        return model, vectorizer
    return None, None


def _build_text(subject: str, sender: str, body: str) -> str:
    return f"{subject or ''} {sender or ''} {body or ''}"


def predict_email(subject: str, sender: str, body: str) -> str:
    model, vectorizer = load_model()

    if model is None or vectorizer is None:
        return "general"

    text = _build_text(subject, sender, body)
    X = vectorizer.transform([text])
    return str(model.predict(X)[0])


def predict_with_confidence(subject: str, sender: str, body: str) -> Tuple[str, float]:
    model, vectorizer = load_model()

    if model is None or vectorizer is None:
        return "general", 0.5

    text = _build_text(subject, sender, body)
    X = vectorizer.transform([text])

    probs = model.predict_proba(X)[0]
    pred = str(model.classes_[probs.argmax()])
    confidence = float(max(probs))

    return pred, confidence
