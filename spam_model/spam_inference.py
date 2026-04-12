import torch
import pickle
import re
from nltk.corpus import stopwords
import nltk

from spam_model.model import SpamClassifier

nltk.download("stopwords")

device = torch.device("cpu")

stop_words = set(stopwords.words("english"))

MAX_LEN = 120   # MUST match training

# -----------------------------
# Load vocab
# -----------------------------

vocab = pickle.load(open("vocab.pkl","rb"))

# -----------------------------
# Load model
# -----------------------------

model = SpamClassifier(len(vocab))
model.load_state_dict(torch.load("spam_model.pt", map_location=device))
model.eval()

# -----------------------------
# Clean text
# -----------------------------

def clean_text(text):

    text = str(text).lower()

    text = re.sub(r"http\S+","",text)
    text = re.sub(r"[^a-zA-Z ]","",text)

    words = text.split()

    words = [w for w in words if w not in stop_words]

    return words


# -----------------------------
# Encode
# -----------------------------

def encode(tokens):

    seq = [vocab.get(word,1) for word in tokens]

    if len(seq) < MAX_LEN:
        seq += [0]*(MAX_LEN-len(seq))
    else:
        seq = seq[:MAX_LEN]

    return seq


# -----------------------------
# Prediction
# -----------------------------

def predict_spam(text):

    tokens = clean_text(text)

    seq = encode(tokens)

    x = torch.tensor([seq])

    with torch.no_grad():

        output = model(x).squeeze()

        prob = torch.sigmoid(output).item()

    return prob