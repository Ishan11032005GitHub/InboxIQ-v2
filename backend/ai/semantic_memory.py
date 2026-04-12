from sentence_transformers import SentenceTransformer
import numpy as np
import json
import os

MODEL = SentenceTransformer("all-MiniLM-L6-v2")

MEMORY_FILE = "ai/semantic_memory.json"


# -------------------------------
# LOAD / SAVE
# -------------------------------

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


# -------------------------------
# ADD MEMORY
# -------------------------------

def add_memory(subject, sender, label, priority):

    text = subject + " " + sender
    embedding = MODEL.encode(text).tolist()

    memory = load_memory()

    memory.append({
        "text": text,
        "embedding": embedding,
        "label": label,
        "priority": priority
    })

    save_memory(memory)


# -------------------------------
# COSINE SIMILARITY
# -------------------------------

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# -------------------------------
# FIND SIMILAR
# -------------------------------

def find_similar(subject, sender, threshold=0.75):

    memory = load_memory()

    if not memory:
        return None

    query = subject + " " + sender
    query_embedding = MODEL.encode(query)

    best_match = None
    best_score = 0

    for item in memory:

        score = cosine_similarity(query_embedding, item["embedding"])

        if score > best_score:
            best_score = score
            best_match = item

    if best_score > threshold:
        return {
            "label": best_match["label"],
            "priority": best_match["priority"]
        }

    return None