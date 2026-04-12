import json


def review_draft(email, ai_response):

    print("\n--------------------------------")
    print("New Email")
    print("--------------------------------")

    print("From:", email["sender"])
    print("Subject:", email["subject"])
    print("\nBody:\n", email["body"])

    result = json.loads(ai_response)

    print("\nAI Classification:", result["urgency"])

    if not result["reply_needed"]:
        print("\nNo reply suggested")
        return False

    print("\n--- Draft Reply ---")

    print("Subject:", result["reply_subject"])
    print("Body:\n", result["reply_body"])

    decision = input("\nSend this reply? (y/n/edit): ")

    if decision == "y":
        return result

    if decision == "edit":

        subject = input("New Subject: ")
        body = input("New Body: ")

        return {
            "reply_subject": subject,
            "reply_body": body
        }

    return False