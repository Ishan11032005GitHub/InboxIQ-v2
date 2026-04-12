import os
import re
import pickle
import numpy as np
import pandas as pd
from collections import Counter

import torch
import torch.nn as nn
import torch.optim as optim

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from nltk.corpus import stopwords
import nltk

nltk.download("stopwords")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

# ---------------------------------------
# PATHS
# ---------------------------------------

ENRON_PATH = "enron_email_dataset/emails.csv"

SPAMASSASSIN_PATH = "spamassassin_public_corpus"

EASY_HAM = os.path.join(SPAMASSASSIN_PATH, "easy_ham/easy_ham")
HARD_HAM = os.path.join(SPAMASSASSIN_PATH, "hard_ham/hard_ham")
SPAM = os.path.join(SPAMASSASSIN_PATH, "spam_2/spam_2")

# ---------------------------------------
# TEXT CLEANING
# ---------------------------------------

stop_words = set(stopwords.words("english"))

def clean_text(text):

    text = str(text).lower()

    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-zA-Z ]", "", text)

    words = text.split()

    words = [w for w in words if w not in stop_words]

    return words


# ---------------------------------------
# LOAD SPAMASSASSIN
# ---------------------------------------

def load_spamassassin():

    texts = []
    labels = []

    def read_folder(folder, label):

        for file in os.listdir(folder):

            path = os.path.join(folder, file)

            try:
                with open(path, encoding="latin-1", errors="ignore") as f:

                    text = f.read()

                    texts.append(text)
                    labels.append(label)

            except:
                pass

    read_folder(EASY_HAM, 0)
    read_folder(HARD_HAM, 0)
    read_folder(SPAM, 1)

    return texts, labels


# ---------------------------------------
# LOAD ENRON
# ---------------------------------------

def load_enron():

    df = pd.read_csv(ENRON_PATH)

    texts = df["message"].astype(str).tolist()

    labels = [0] * len(texts)

    return texts, labels


# ---------------------------------------
# LOAD DATA
# ---------------------------------------

spam_texts, spam_labels = load_spamassassin()
enron_texts, enron_labels = load_enron()

texts = spam_texts + enron_texts
labels = spam_labels + enron_labels

df = pd.DataFrame({
    "text": texts,
    "label": labels
})

print("Dataset size:", df.shape)
print(df["label"].value_counts())

# ---------------------------------------
# BALANCE DATASET
# ---------------------------------------

spam_df = df[df["label"] == 1]
ham_df = df[df["label"] == 0]

ham_df = ham_df.sample(len(spam_df) * 5, random_state=42)

df = pd.concat([spam_df, ham_df]).sample(frac=1, random_state=42)

print("\nBalanced dataset:")
print(df["label"].value_counts())


# ---------------------------------------
# TOKENIZATION
# ---------------------------------------

df["tokens"] = df["text"].apply(clean_text)


# ---------------------------------------
# BUILD VOCAB
# ---------------------------------------

all_words = []

for tokens in df["tokens"]:
    all_words.extend(tokens)

word_counts = Counter(all_words)

vocab = {word: i+2 for i, (word, _) in enumerate(word_counts.most_common(5000))}

vocab["<PAD>"] = 0
vocab["<UNK>"] = 1

vocab_size = len(vocab)

print("Vocabulary size:", vocab_size)


# ---------------------------------------
# ENCODE
# ---------------------------------------

MAX_LEN = 120

def encode(tokens):

    seq = [vocab.get(word, 1) for word in tokens]

    if len(seq) < MAX_LEN:
        seq += [0]*(MAX_LEN-len(seq))
    else:
        seq = seq[:MAX_LEN]

    return seq


df["seq"] = df["tokens"].apply(encode)


# ---------------------------------------
# TRAIN TEST SPLIT
# ---------------------------------------

X = np.array(df["seq"].tolist())
y = df["label"].values

print("Input shape:", X.shape)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    stratify=y,
    random_state=42
)

X_train = torch.tensor(X_train, dtype=torch.long).to(device)
y_train = torch.tensor(y_train, dtype=torch.float32).to(device)

X_test = torch.tensor(X_test, dtype=torch.long).to(device)
y_test = torch.tensor(y_test, dtype=torch.float32).to(device)


# ---------------------------------------
# MODEL
# ---------------------------------------

class SpamClassifier(nn.Module):

    def __init__(self, vocab_size):

        super().__init__()

        self.embedding = nn.Embedding(vocab_size,128,padding_idx=0)

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

        self.dropout = nn.Dropout(0.3)

        self.fc = nn.Linear(64,1)

    def forward(self,x):

        x = self.embedding(x)

        x = x.permute(0,2,1)

        x = self.conv(x)

        x = x.permute(0,2,1)

        output,(hidden,_) = self.lstm(x)

        hidden = hidden[-1]

        hidden = self.dropout(hidden)

        x = self.fc(hidden)

        return x


model = SpamClassifier(vocab_size).to(device)


# ---------------------------------------
# TRAINING SETUP
# ---------------------------------------

spam_count = (y_train == 1).sum().item()
ham_count = (y_train == 0).sum().item()

pos_weight = torch.tensor([ham_count / spam_count]).to(device)

criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

optimizer = optim.Adam(model.parameters(), lr=0.0003)

EPOCHS = 8
BATCH_SIZE = 64


# ---------------------------------------
# TRAINING LOOP
# ---------------------------------------

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

        torch.nn.utils.clip_grad_norm_(model.parameters(), 5)

        optimizer.step()

        total_loss += loss.item()

        probs = torch.sigmoid(outputs)
        preds = (probs > 0.5).float()

        correct += (preds == batch_y).sum().item()
        total += batch_y.size(0)

    acc = correct / total

    print(f"Epoch {epoch+1} | Loss {total_loss:.4f} | Accuracy {acc:.4f}")


# ---------------------------------------
# EVALUATION
# ---------------------------------------

with torch.no_grad():

    outputs = model(X_test).squeeze()

    probs = torch.sigmoid(outputs)

    preds = (probs > 0.5).int()

print("\nClassification Report\n")

print(classification_report(
    y_test.cpu(),
    preds.cpu()
))


# ---------------------------------------
# SAVE MODEL
# ---------------------------------------

torch.save(model.state_dict(), "spam_model.pt")

pickle.dump(vocab, open("vocab.pkl", "wb"))

print("\nModel saved: spam_model.pt")
print("Vocabulary saved: vocab.pkl")