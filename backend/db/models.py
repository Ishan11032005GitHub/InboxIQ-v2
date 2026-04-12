from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    tokens = Column(Text)  # store JSON string


# ✅ NEW TABLE (added — nothing else modified)
class SnoozedEmail(Base):
    __tablename__ = "snoozed_emails"

    id = Column(String, primary_key=True)   # Gmail message ID
    user_id = Column(String)
    remind_at = Column(DateTime)