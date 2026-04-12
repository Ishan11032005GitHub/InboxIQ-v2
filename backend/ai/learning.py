import json
import os

MEMORY_FILE = "ai/learning_memory.json"


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def add_correction(subject, sender, label, priority):
    memory = load_memory()

    memory.append({
        "subject": subject.lower(),
        "sender": sender.lower(),
        "label": label,
        "priority": priority
    })

    save_memory(memory)


def find_match(subject, sender):
    memory = load_memory()

    sub = subject.lower()
    s = sender.lower()

    for item in memory:
        if item["subject"] in sub or item["sender"] in s:
            return {
                "label": item["label"],
                "priority": item["priority"]
            }

    return None