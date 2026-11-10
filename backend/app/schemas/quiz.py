# -*- coding: utf-8 -*-
"""
Pydantic schemas cho quiz: câu hỏi, phiên làm bài, và kết quả.
Định nghĩa cấu trúc dữ liệu request/response cho API quiz.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field


# ===== Question Schemas =====

class QuestionResponse(BaseModel):
    """
    Response câu hỏi trong khi làm quiz.
    KHÔNG bao gồm đáp án đúng và giải thích.
    """
    id: int
    question_text: str
    options: Dict[str, str]  # {"A": "...", "B": "...", "C": "...", "D": "..."}
    difficulty: str
    topic_tag: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QuestionWithAnswerResponse(BaseModel):
    """
    Response câu hỏi kèm đáp án đúng và giải thích.
    Dùng cho trang kết quả sau khi nộp bài.
    """
    id: int
    question_text: str
    options: Dict[str, str]
    correct_answer: str
    difficulty: str
    explanation: Optional[str] = None
    topic_tag: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ===== Quiz Session Schemas =====

class QuizStartRequest(BaseModel):
    """Request bắt đầu phiên quiz."""
    chapter_ids: Optional[List[int]] = None
    topic_tags: Optional[List[str]] = None
    num_questions: int = Field(default=10, ge=1, le=50, description="Số câu hỏi")
    mode: str = Field(default="chapter", description="Chế độ quiz: chapter/topic/full")


class QuizStartResponse(BaseModel):
    """Response khi bắt đầu phiên quiz."""
    session_id: int
    total_questions: int
    mode: str
    questions: List[QuestionResponse]


class AnswerItem(BaseModel):
    """Một câu trả lời trong danh sách nộp bài."""
    question_id: int
    answer: str = Field(..., pattern=r"^[A-D]$", description="Đáp án: A, B, C hoặc D")


class QuizSubmitRequest(BaseModel):
    """Request nộp bài quiz."""
    session_id: int
    answers: List[AnswerItem]


class DetailedResult(BaseModel):
    """Kết quả chi tiết cho từng câu hỏi."""
    question_id: int
    question_text: str
    options: Dict[str, str]
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: Optional[str] = None


class QuizResultResponse(BaseModel):
    """Response kết quả quiz sau khi nộp bài."""
    session_id: int
    score: float
    total_questions: int
    correct_count: int
    percentage: float
    mode: str
    started_at: datetime
    finished_at: datetime
    results: List[DetailedResult]


class QuizSessionResponse(BaseModel):
    """Response thông tin phiên quiz (cho danh sách lịch sử)."""
    id: int
    user_id: Optional[str] = None
    document_id: int
    chapter_ids: List[int]
    mode: str
    score: Optional[float] = None
    total_questions: int
    started_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QuizSessionListResponse(BaseModel):
    """Response danh sách các phiên quiz."""
    total: int
    sessions: List[QuizSessionResponse]
