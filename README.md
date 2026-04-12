# 🚀 InboxIQ – AI Email Assistant

An AI-powered Gmail assistant that classifies, prioritizes, and generates contextual replies for real-world inboxes using a hybrid ML + rule-based pipeline.

---

## 🔥 Why this matters

Managing email is a high-friction, repetitive workflow. InboxIQ reduces manual triage by automating:

- Email classification across real-world categories  
- Priority detection for decision-making  
- Context-aware reply generation  

Built with production constraints in mind: noisy data, ambiguous classes, API limits, and real user workflows.

---

## ⚡ Key Features

- 🔐 Gmail Integration (OAuth2)  
- 🧠 Email Classification (TF-IDF + Logistic Regression + Rules)  
- 📊 Confidence Scoring  
- ✉️ AI Reply Generation (Gemini API)  
- 🔁 Feedback Loop (Retraining Ready)  
- ⏰ Email Scheduling  

---

## 📊 Performance

- Dataset Size: 3200 real emails  
- Model: TF-IDF + Logistic Regression  
- Accuracy: 88.25% across 8 categories  

### Per-Class Accuracy:
- notification: 82.5%  
- event_invite: 93.5%  
- job_alert: 95.0%  
- work: 68.75%  
- promotion: 96.5%  
- general: 76.75%  
- newsletter: 97.5%  
- security: 95.5%  

---

## 🏗️ System Architecture

User → Frontend (Vercel)  
       ↓  
FastAPI Backend (Render)  
       ↓  
Gmail API (Pagination, OAuth2)  
       ↓  
ML Classifier (TF-IDF + LR)  
       ↓  
Rule Engine (Overrides)  
       ↓  
LLM Reply Generator (Gemini)  

---

## ⚙️ Tech Stack

- Backend: FastAPI  
- Frontend: HTML/CSS/JS (Vercel)  
- ML: Scikit-learn  
- APIs: Gmail API, Gemini API  
- Auth: OAuth2  
- Deployment: Render, Vercel  

---

## 🧠 Key Engineering Decisions

- Dropped transformer models (too heavy for this use case)  
- Used TF-IDF + Logistic Regression for speed and interpretability  
- Built hybrid ML + rule system for edge cases  
- Implemented Gmail API pagination for scalability  
- Added HTML-to-text preprocessing  

---

## 🚀 Live Demo

- Live: https://inbox-iq-xi.vercel.app/  
- Repo: https://github.com/Ishan11032005GitHub/InboxIQ  

---

## 🛠️ Run Locally

```bash
git clone https://github.com/Ishan11032005GitHub/InboxIQ
cd InboxIQ
pip install -r requirements.txt
streamlit run app.py
```

---

## 🧩 What’s Next

- Active learning loop  
- Personalization per user  
- Multi-account support  
- Latency optimization  
