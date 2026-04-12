import json
import joblib
from sklearn.metrics import confusion_matrix, classification_report
from backend.ai.classifier import load_model

# Load your dataset
DATA_PATH = "data/email_dataset.json"

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

model, vectorizer = load_model()

if model is None:
    print("Model not loaded. Fix this first.")
    exit()

X = []
y_true = []

for email in data:
    text = f"{email['subject']} {email['sender']} {email['body']}"
    X.append(text)
    y_true.append(email["label"])

X_vec = vectorizer.transform(X)

y_pred = model.predict(X_vec)

labels = model.classes_

print("\n=== Classification Report ===\n")
print(classification_report(y_true, y_pred))

print("\n=== Confusion Matrix ===\n")
cm = confusion_matrix(y_true, y_pred, labels=labels)

print("Labels:", labels)
print(cm)

print("\n=== Misclassified Samples ===\n")

for i in range(len(y_true)):
    if y_true[i] != y_pred[i]:
        print("TRUE:", y_true[i])
        print("PRED:", y_pred[i])
        print("TEXT:", X[i][:200])
        print("-" * 50)
