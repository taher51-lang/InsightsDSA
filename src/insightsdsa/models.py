from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=True)
    userpassword = Column(Text, nullable=True)
    name = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    google_id = Column(String(255), unique=True, nullable=True)
    profile_pic = Column(Text, nullable=True)
    # PostgreSQL schemas often use jsonb; JSON maps correctly on Postgres/SQLite/MySQL.
    chat_context = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), unique=True, nullable=False)
    icon = Column(Text, nullable=True)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(32), nullable=True)
    link = Column(Text, nullable=True)
    is_solved = Column(Boolean, default=False)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text, nullable=True)


class UserProgress(Base):
    __tablename__ = "user_progress"
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="user_progress_pkey"),)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    solved_at = Column(DateTime, nullable=True)
    is_solved = Column(Boolean, nullable=True)
    next_review = Column(Date, nullable=True)
    interval_days = Column(Integer, nullable=True)
    ease_factor = Column(Float, nullable=True)
    repetitions = Column(Integer, nullable=True)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    action = Column(String(32), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    confidence_level = Column(Integer, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    ai_bifurcated_score = Column(Float, nullable=True)
    clarity_of_thought = Column(Float, nullable=True)
    ai_mastery_score = Column(Float, nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
