from fastapi import FastAPI
from pydantic import BaseModel

from spam_model.spam_inference import predict_spam

app = FastAPI()

class Email(BaseModel):
    text: str


@app.post("/spam-check")
def spam_check(email: Email):

    prob = predict_spam(email.text)

    return {
        "spam_probability": prob,
        "is_spam": prob > 0.5
    }