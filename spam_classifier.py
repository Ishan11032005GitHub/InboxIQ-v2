import pandas as pd
import numpy as np
import re
import nltk
import torch
import torch.nn as nn
import torch.optim as optim
import pickle

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from collections import Counter
from nltk.corpus import stopwords

# -----------------------------
# Setup
# -----------------------------

nltk.download("stopwords")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)


# -----------------------------
# Load Dataset
# -----------------------------

df = pd.read_csv(
    r"C:\Users\Asus\Desktop\gmail-ai-agent\spam.csv",
    encoding="latin-1"
)

# Remove useless columns
df = df[["v1", "v2"]]
df.columns = ["label", "text"]

print("Dataset shape:", df.shape)

# Convert labels
df["label"] = df["label"].map({
    "ham": 0,
    "spam": 1
})

print(df["label"].value_counts())


# -----------------------------
# Text Cleaning
# -----------------------------

stop_words = set(stopwords.words("english"))

def clean_text(text):

    text = str(text).lower()

    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-zA-Z ]", "", text)

    words = text.split()

    words = [w for w in words if w not in stop_words]

    return words


df["tokens"] = df["text"].apply(clean_text)


# -----------------------------
# Build Vocabulary
# -----------------------------

all_words = []

for tokens in df["tokens"]:
    all_words.extend(tokens)

word_counts = Counter(all_words)

vocab = {word: i+2 for i,(word,_) in enumerate(word_counts.most_common(10000))}

vocab["<PAD>"] = 0
vocab["<UNK>"] = 1

vocab_size = len(vocab)

print("Vocabulary size:", vocab_size)


# -----------------------------
# Encode Sentences
# -----------------------------

MAX_LEN = 40

def encode(tokens):

    seq = [vocab.get(word,1) for word in tokens]

    if len(seq) < MAX_LEN:
        seq += [0]*(MAX_LEN-len(seq))
    else:
        seq = seq[:MAX_LEN]

    return seq


df["seq"] = df["tokens"].apply(encode)


# -----------------------------
# Train/Test Split
# -----------------------------

X = np.array(df["seq"].tolist())
y = df["label"].values

print("Input shape:", X.shape)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

X_train = torch.tensor(X_train).to(device)
y_train = torch.tensor(y_train).float().to(device)

X_test = torch.tensor(X_test).to(device)
y_test = torch.tensor(y_test).float().to(device)


# -----------------------------
# CNN + LSTM Model
# -----------------------------

class SpamClassifier(nn.Module):

    def __init__(self, vocab_size):

        super().__init__()

        self.embedding = nn.Embedding(
            vocab_size,
            128,
            padding_idx=0
        )

        self.conv = nn.Conv1d(
            in_channels=128,
            out_channels=128,
            kernel_size=3,
            padding=1
        )

        self.lstm = nn.LSTM(
            input_size=128,
            hidden_size=64,
            batch_first=True
        )

        self.fc = nn.Linear(64,1)

    def forward(self,x):

        x = self.embedding(x)

        x = x.permute(0,2,1)

        x = self.conv(x)

        x = x.permute(0,2,1)

        output,(hidden,_) = self.lstm(x)

        hidden = hidden[-1]

        x = self.fc(hidden)

        return x


model = SpamClassifier(vocab_size).to(device)


# -----------------------------
# Training Setup
# -----------------------------

criterion = nn.BCEWithLogitsLoss()

optimizer = optim.Adam(
    model.parameters(),
    lr=0.001
)

EPOCHS = 5
BATCH_SIZE = 64


# -----------------------------
# Training Loop
# -----------------------------

for epoch in range(EPOCHS):

    permutation = torch.randperm(X_train.size(0))

    total_loss = 0
    correct = 0
    total = 0

    for i in range(0, X_train.size(0), BATCH_SIZE):

        indices = permutation[i:i+BATCH_SIZE]

        batch_x = X_train[indices]
        batch_y = y_train[indices]

        optimizer.zero_grad()

        outputs = model(batch_x).squeeze()

        loss = criterion(outputs, batch_y)

        loss.backward()

        optimizer.step()

        total_loss += loss.item()

        probs = torch.sigmoid(outputs)
        preds = (probs > 0.5).int()

        correct += (preds == batch_y.int()).sum().item()
        total += batch_y.size(0)

    avg_loss = total_loss / (X_train.size(0)/BATCH_SIZE)
    acc = correct / total

    print(f"Epoch {epoch+1} | Loss {avg_loss:.4f} | Accuracy {acc:.4f}")


# -----------------------------
# Evaluation
# -----------------------------

with torch.no_grad():

    outputs = model(X_test).squeeze()

    probs = torch.sigmoid(outputs)

    preds = (probs > 0.5).int()

print("\nClassification Report\n")

print(classification_report(
    y_test.cpu(),
    preds.cpu()
))


# -----------------------------
# Save Model
# -----------------------------

torch.save(model.state_dict(), "spam_model.pt")

pickle.dump(vocab, open("vocab.pkl", "wb"))

print("\nModel saved: spam_model.pt")
print("Vocabulary saved: vocab.pkl")