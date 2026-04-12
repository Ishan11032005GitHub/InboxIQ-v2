from google import genai
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_email(email):

    prompt = f"""
You are an AI email assistant.

Analyze the email below.

Subject: {email['subject']}

Body:
{email['body'][:2000]}

Return STRICT JSON only.

Example format:

{{
 "urgency": "urgent or not urgent",
 "reply_needed": true or false,
 "reply_subject": "string",
 "reply_body": "string"
}}
"""

    response = client.models.generate_content(
    model="gemini-flash-latest",
    contents=prompt,
    config={
        "response_mime_type": "application/json"
    }
)

    return response.text