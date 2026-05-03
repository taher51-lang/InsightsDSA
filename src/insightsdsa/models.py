"""SQLAlchemy ORM models mapped to the existing ``dsa_tracker`` tables."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True)
    username = Column(String(150), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    userpassword = Column(Text, nullable=True)
    google_id = Column(String(255), nullable=True)
    profile_pic = Column(Text, nullable=True)
    phone_number = Column(String(50), nullable=True)


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    icon = Column(String(50), nullable=True)

    questions = relationship("Question", back_populates="concept")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    difficulty = Column(String(50), nullable=True)
    link = Column(Text, nullable=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=True)

    concept = relationship("Concept", back_populates="questions")


class UserProgress(Base):
    __tablename__ = "user_progress"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), primary_key=True)
    solved_at = Column(DateTime, nullable=True)
    # "interval" is a reserved word in PostgreSQL; the column is quoted in the DB.
    interval_days = Column("interval", Integer, nullable=True)
    ease_factor = Column(Float, nullable=True)
    repetitions = Column(Integer, nullable=True)
    next_review = Column(Date, nullable=True)
    is_solved = Column(Boolean, default=False)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    action = Column(String(50), nullable=True)
    confidence_level = Column(Integer, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    ai_bifurcated_score = Column(Integer, nullable=True)
    clarity_of_thought = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    thread_id = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
