metrics = {
    "emails_processed":0,
    "spam_detected":0,
    "replies_generated":0
}

def update_metric(name):
    metrics[name]+=1