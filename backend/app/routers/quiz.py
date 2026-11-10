# -*- coding: utf-8 -*-
"""
Router cho quiz: bắt đầu, nộp bài, xem kết quả, generate câu hỏi.
"""

import random
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Chapter, Document, DocumentStatus
from app.models.quiz import Question, QuizAnswer, QuizSession, QuizMode
from app.schemas.quiz import (
    AnswerItem,
    DetailedResult,
    QuestionResponse,
    QuizResultResponse,
    QuizSessionListResponse,
    QuizSessionResponse,
    QuizStartRequest,
    QuizStartResponse,
    QuizSubmitRequest,
)

from app.services.quiz_service import QuizService

router = APIRouter(prefix="/api/quiz", tags=["Quiz"])


@router.post("/start", response_model=QuizStartResponse)
async def start_quiz(
    request: QuizStartRequest,
    db: Session = Depends(get_db),
):
    """
    Bắt đầu phiên quiz.
    Chọn câu hỏi theo chương hoặc chủ đề, trả về câu hỏi KHÔNG kèm đáp án.
    """
    quiz_svc = QuizService()
    result = quiz_svc.start_quiz(
        chapter_ids=request.chapter_ids,
        topic_tags=request.topic_tags,
        num_questions=request.num_questions,
        db=db,
        mode=request.mode,
    )
    return QuizStartResponse.model_validate(result)


@router.post("/submit", response_model=QuizResultResponse)
async def submit_quiz(
    request: QuizSubmitRequest,
    db: Session = Depends(get_db),
):
    """
    Nộp bài quiz. Chấm điểm và trả về kết quả chi tiết với đáp án + giải thích.
    """
    quiz_svc = QuizService()
    result = quiz_svc.submit_quiz(
        session_id=request.session_id,
        answers=request.answers,
        db=db,
    )
    return QuizResultResponse.model_validate(result)


@router.get("/explanation/{question_id}")
async def get_explanation(
    question_id: int,
    db: Session = Depends(get_db),
):
    """Lấy giải thích chi tiết cho câu hỏi kèm trích dẫn RAG nếu có."""
    from app.services.embedding_service import EmbeddingService
    from app.services.rag_service import RAGService

    embedding_svc = EmbeddingService()
    rag_svc = RAGService(embedding_svc)
    quiz_svc = QuizService()
    explanation = quiz_svc.get_explanation(question_id, db, rag_svc)
    return {"question_id": question_id, "explanation": explanation}


@router.get("/sessions", response_model=QuizSessionListResponse)
async def list_sessions(db: Session = Depends(get_db)):
    """Lấy danh sách các phiên quiz."""
    sessions = db.query(QuizSession).order_by(QuizSession.started_at.desc()).all()
    return QuizSessionListResponse(
        total=len(sessions),
        sessions=[QuizSessionResponse.model_validate(s) for s in sessions],
    )


@router.get("/sessions/{session_id}", response_model=QuizResultResponse)
async def get_session_result(session_id: int, db: Session = Depends(get_db)):
    """Xem lại kết quả phiên quiz."""
    session = db.query(QuizSession).filter(QuizSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên quiz.")
    if not session.finished_at:
        raise HTTPException(status_code=400, detail="Phiên quiz chưa hoàn thành.")

    # Lấy câu trả lời
    answers = db.query(QuizAnswer).filter(QuizAnswer.session_id == session_id).all()
    detailed_results = []
    correct_count = 0

    for ans in answers:
        question = db.query(Question).filter(Question.id == ans.question_id).first()
        if not question:
            continue
        if ans.is_correct:
            correct_count += 1
        detailed_results.append(
            DetailedResult(
                question_id=question.id,
                question_text=question.question_text,
                options=question.options,
                user_answer=ans.user_answer,
                correct_answer=question.correct_answer,
                is_correct=ans.is_correct,
                explanation=question.explanation,
            )
        )

    percentage = (correct_count / session.total_questions * 100) if session.total_questions > 0 else 0

    return QuizResultResponse(
        session_id=session.id,
        score=session.score or 0,
        total_questions=session.total_questions,
        correct_count=correct_count,
        percentage=round(percentage, 2),
        mode=session.mode.value,
        started_at=session.started_at,
        finished_at=session.finished_at,
        results=detailed_results,
    )


def _generate_quiz_background(document_id: int):
    """Background task generate quiz cho tài liệu."""
    from app.database import SessionLocal
    from app.services.quiz_service import QuizService
    from app.services.quiz_generator import QuizGenerator
    from app.services.quiz_verifier import QuizVerifier
    from app.services.embedding_service import EmbeddingService
    from app.services.rag_service import RAGService

    db = SessionLocal()
    try:
        embedding_svc = EmbeddingService()
        rag_svc = RAGService(embedding_svc)
        generator = QuizGenerator()
        verifier = QuizVerifier(rag_svc, embedding_svc)
        quiz_svc = QuizService()

        quiz_svc.generate_quiz_for_document(document_id, db, generator, verifier)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error generating quiz for document {document_id}: {e}")
    finally:
        db.close()


@router.post("/generate/{document_id}")
async def generate_quiz(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger tạo câu hỏi quiz cho tài liệu.
    Xử lý trong background, kiểm tra status qua GET /api/documents/{id}.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=400,
            detail="Tài liệu chưa sẵn sàng. Hãy đợi xử lý xong.",
        )

    # Kiểm tra đã có câu hỏi chưa
    existing_count = (
        db.query(Question)
        .join(Chapter)
        .filter(Chapter.document_id == document_id)
        .count()
    )

    background_tasks.add_task(_generate_quiz_background, document_id)

    return {
        "message": "Đang tạo câu hỏi quiz trong background.",
        "document_id": document_id,
        "existing_questions": existing_count,
    }

