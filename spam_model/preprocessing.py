import re
from nltk.corpus import stopwords

stop_words = set(stopwords.words("english"))

MAX_LEN = 40


def clean_text(text):

    text = str(text).lower()

    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-zA-Z ]", "", text)

    words = text.split()

    words = [w for w in words if w not in stop_words]

    return words


def encode(tokens, vocab):

    seq = [vocab.get(word,1) for word in tokens]

    if len(seq) < MAX_LEN:
        seq += [0]*(MAX_LEN-len(seq))
    else:
        seq = seq[:MAX_LEN]

    return seq