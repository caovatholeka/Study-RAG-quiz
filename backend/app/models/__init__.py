# -*- coding: utf-8 -*-
"""
Import tất cả models để SQLAlchemy nhận diện.
"""

from app.models.document import Document, Chapter, DocumentStatus, ChapterLevel
from app.models.quiz import Question, QuizSession, QuizAnswer, QuestionDifficulty, QuizMode

__all__ = [
    "Document",
    "Chapter",
    "DocumentStatus",
    "ChapterLevel",
    "Question",
    "QuizSession",
    "QuizAnswer",
    "QuestionDifficulty",
    "QuizMode",
]
