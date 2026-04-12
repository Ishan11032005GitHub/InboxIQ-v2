from spam_inference import predict_spam

emails = [
    {
        "subject": "You Won $1000 Prize!",
        "body": "Congratulations you won $1000 click here now"
    },
    {
        "subject": "Meeting Agenda",
        "body": "Hi team, please find the meeting agenda attached"
    },
    {
        "subject": "Security Alert: Account Suspended",
        "body": "URGENT: Your account has been suspended verify immediately"
    },
    {
        "subject": "Lunch Tomorrow?",
        "body": "Hey Ishan, are we meeting tomorrow?"
    }
]

for e in emails:
    text = e["subject"] + " " + e["body"]

    print("Subject:", e["subject"])
    print("Spam probability:", predict_spam(e["body"]))
    print()