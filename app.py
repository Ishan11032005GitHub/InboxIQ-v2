
import streamlit as st
import subprocess

from gmail.gmail_utils import get_unread_emails, send_email
from ai.gemini_utils import process_inbox, generate_reply
from ai.classifier import predict_with_confidence
from memory.feedback_store import save_feedback
from auth.google_auth import login, get_gmail_service

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
st.set_page_config(page_title="InboxIQ", layout="wide")
st.title("📬 InboxIQ — AI Email Assistant")

# ---------------------------------------------------
# AUTH
# ---------------------------------------------------
if "credentials" not in st.session_state:
    st.session_state["credentials"] = login()

credentials = st.session_state["credentials"]
service = get_gmail_service(credentials)

# ---------------------------------------------------
# LOAD EMAILS (LAZY + CACHE)
# ---------------------------------------------------
@st.cache_data(ttl=60)
def load_emails(_token: str):
    svc = get_gmail_service(credentials)
    return get_unread_emails(svc)


if "emails" not in st.session_state:
    st.session_state["emails"] = []

st.info("Click below to fetch your inbox.")

c1, c2 = st.columns([1, 1])

with c1:
    if st.button("📥 Load Emails"):
        with st.spinner("Fetching emails..."):
            st.session_state["emails"] = load_emails(credentials.token)

with c2:
    if st.button("🔄 Refresh Inbox"):
        load_emails.clear()
        with st.spinner("Refreshing emails..."):
            st.session_state["emails"] = load_emails(credentials.token)

emails = st.session_state["emails"]

# ---------------------------------------------------
# COMPOSE EMAIL
# ---------------------------------------------------
st.header("✉️ Compose Email")

compose_to = st.text_input("To")
compose_subject = st.text_input("Subject")
compose_body = st.text_area("Email Body", height=200)

if st.button("Send Email"):
    if compose_to and compose_subject and compose_body:
        try:
            send_email(service, compose_to, compose_subject, compose_body)
            st.success("Email sent.")
        except Exception as e:
            st.error(f"Send failed: {e}")
    else:
        st.warning("Fill all fields.")

st.divider()

# ---------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------
classified_emails = process_inbox(emails) if emails else []

# ---------------------------------------------------
# INBOX
# ---------------------------------------------------
if not emails:
    st.warning("No emails loaded yet.")
elif not classified_emails:
    st.info("No unread emails found.")
else:
    for email in classified_emails:
        email_id = email.get("id", f"{email.get('subject', '')}_{email.get('sender', '')}")
        reply_key = f"reply_{email_id}"
        feedback_key = f"feedback_{email_id}"

        subject = email.get("subject", "(No Subject)")
        sender = email.get("sender", "(Unknown Sender)")
        body = email.get("body", "")

        label, confidence = predict_with_confidence(subject, sender, body)

        st.subheader(subject)
        st.write("From:", sender)
        st.write("Label:", email.get("label", label))
        st.write("Confidence:", round(float(confidence), 2))

        with st.expander("View Email Body"):
            st.write(body[:1000] if body else "(Empty body)")

        # -------------------------
        # FEEDBACK
        # -------------------------
        if confidence < 0.6:
            correct_label = st.selectbox(
                "Correct Label",
                [
                    "job_alert",
                    "promotion",
                    "newsletter",
                    "event_invite",
                    "notification",
                    "work",
                    "security",
                    "general",
                ],
                key=feedback_key,
            )

            if st.button("Save Feedback", key=f"save_{email_id}"):
                try:
                    save_feedback(email, correct_label)

                    if "retraining" not in st.session_state:
                        st.session_state["retraining"] = True
                        try:
                            subprocess.Popen(["python", "retrain.py"])
                        except Exception:
                            pass

                    st.success("Feedback saved. Model updating...")
                except Exception as e:
                    st.error(f"Saving feedback failed: {e}")

        # -------------------------
        # REPLY
        # -------------------------
        if reply_key not in st.session_state:
            st.session_state[reply_key] = ""

        st.text_area("Reply", key=reply_key, height=150)

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Generate Reply", key=f"{email_id}_gen"):
                try:
                    reply = generate_reply(email, "professional")
                    st.session_state[reply_key] = reply
                    st.rerun()
                except Exception as e:
                    st.error(f"Reply generation failed: {e}")

        with c2:
            if st.button("Send Reply", key=f"{email_id}_send"):
                try:
                    send_email(
                        service,
                        sender,
                        f"Re: {subject}" if subject else "Re:",
                        st.session_state[reply_key],
                    )
                    st.success("Sent.")
                except Exception as e:
                    st.error(f"Send failed: {e}")

        st.divider()
