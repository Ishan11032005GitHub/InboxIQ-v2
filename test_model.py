from backend.ai.classifier import predict_email, predict_with_confidence

samples = [
    {
        "subject": "Summer Intern at Haleon and 10 more jobs for you",
        "sender": "noreply@glassdoor.com",
        "body": "Apply now for internship roles in Gurgaon. New job matches available."
    },
    {
        "subject": "Verify your account immediately",
        "sender": "security@bank.com",
        "body": "Please verify your password and login activity immediately."
    },
    {
        "subject": "Weekly product newsletter",
        "sender": "newsletter@company.com",
        "body": "Unsubscribe anytime. Here is your weekly digest."
    },
    {
        "subject": "Project meeting tomorrow",
        "sender": "manager@company.com",
        "body": "We have a review call tomorrow regarding the project deadline."
    }
]

for i, email in enumerate(samples, start=1):
    label = predict_email(email["subject"], email["sender"], email["body"])
    pred, conf = predict_with_confidence(email["subject"], email["sender"], email["body"])

    print(f"\n--- Sample {i} ---")
    print("Subject:", email["subject"])
    print("Predicted label:", label)
    print("Predicted label + confidence:", pred, round(conf, 4))