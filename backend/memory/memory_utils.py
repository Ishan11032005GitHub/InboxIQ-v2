import json
import os

MEMORY_FILE = "thread_memory.json"


def load_memory():

    if not os.path.exists(MEMORY_FILE):
        return {}

    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(memory):

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def update_thread(thread_id, email):

    memory = load_memory()

    if thread_id not in memory:
        memory[thread_id] = []

    memory[thread_id].append(email)

    save_memory(memory)