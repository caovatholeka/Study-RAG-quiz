# -*- coding: utf-8 -*-
"""
SQLAlchemy models cho quiz: câu hỏi, phiên làm bài, và câu trả lời.
"""

import enum
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Enum, DateTime, ForeignKey, JSON, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuestionDifficulty(str, enum.Enum):
    """Độ khó của câu hỏi."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuizMode(str, enum.Enum):
    """Chế độ làm quiz."""
    CHAPTER = "chapter"
    TOPIC = "topic"
    FULL = "full"


class Question(Base):
    """Model cho câu hỏi trắc nghiệm."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict] = mapped_column(JSON, nullable=False)  # {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct_answer: Mapped[str] = mapped_column(String(1), nullable=False)  # A/B/C/D
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        Enum(QuestionDifficulty), default=QuestionDifficulty.MEDIUM, nullable=False
    )
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic_tag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Quan hệ
    chapter = relationship("Chapter", backref="questions")

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, difficulty='{self.difficulty}')>"


class QuizSession(Base):
    """Model cho phiên làm quiz."""

    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chapter_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # Danh sách chapter_id
    mode: Mapped[QuizMode] = mapped_column(
        Enum(QuizMode), default=QuizMode.CHAPTER, nullable=False
    )
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Quan hệ
    document = relationship("Document", backref="quiz_sessions")
    answers: Mapped[List["QuizAnswer"]] = relationship(
        "QuizAnswer", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QuizSession(id={self.id}, mode='{self.mode}', score={self.score})>"


class QuizAnswer(Base):
    """Model cho câu trả lời trong phiên quiz."""

    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    user_answer: Mapped[str] = mapped_column(String(1), nullable=False)  # A/B/C/D
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Quan hệ
    session: Mapped["QuizSession"] = relationship("QuizSession", back_populates="answers")
    question = relationship("Question")

    def __repr__(self) -> str:
        return f"<QuizAnswer(id={self.id}, is_correct={self.is_correct})>"
