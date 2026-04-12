from collections import defaultdict

contact_scores = defaultdict(int)

def update_contact(sender):
    contact_scores[sender] += 1

def get_importance(sender):

    score = contact_scores[sender]

    if score > 10:
        return "high"

    if score > 3:
        return "medium"

    return "low"