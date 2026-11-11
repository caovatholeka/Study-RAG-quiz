# -*- coding: utf-8 -*-
"""
Router cho quiz: bắt đầu, nộp bài, xem kết quả, generate câu hỏi.
"""

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
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


# Quản lý tiến trình sinh câu hỏi nền: {document_id: {"is_generating": bool, "progress_message": str, "started_at": str, "error": Optional[str]}}
active_quiz_tasks: dict = {}


def _generate_quiz_background(document_id: int, num_questions: int = None):
    """Background task generate quiz cho tài liệu."""
    from app.database import SessionLocal
    from app.services.quiz_service import QuizService
    from app.services.quiz_generator import QuizGenerator
    from app.services.quiz_verifier import QuizVerifier
    from app.services.embedding_service import EmbeddingService
    from app.services.rag_service import RAGService

    active_quiz_tasks[document_id] = {
        "is_generating": True,
        "progress_message": "Đang chuẩn bị nội dung và kết nối AI...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }

    def update_progress(msg: str):
        if document_id in active_quiz_tasks:
            active_quiz_tasks[document_id]["progress_message"] = msg

    db = SessionLocal()
    try:
        embedding_svc = EmbeddingService()
        rag_svc = RAGService(embedding_svc)
        generator = QuizGenerator()
        verifier = QuizVerifier(rag_svc, embedding_svc)
        quiz_svc = QuizService()

        # Giới hạn an toàn: nếu không chỉ định num_questions, mặc định 10 câu cho toàn bộ tài liệu (tránh bùng nổ khi tài liệu có nhiều chương)
        target_questions = num_questions if num_questions is not None else 10

        total = quiz_svc.generate_quiz_for_document(
            document_id=document_id,
            db=db,
            quiz_generator=generator,
            quiz_verifier=verifier,
            num_questions_per_chapter=target_questions,
            progress_callback=update_progress,
        )
        active_quiz_tasks[document_id]["is_generating"] = False
        active_quiz_tasks[document_id]["progress_message"] = f"Hoàn tất! Đã tạo và lưu {total} câu hỏi vào CSDL."
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error generating quiz for document {document_id}: {e}")
        active_quiz_tasks[document_id]["is_generating"] = False
        active_quiz_tasks[document_id]["error"] = str(e)
    finally:
        db.close()


@router.get("/check-key")
async def check_key():
    """
    Kiểm tra trạng thái cấu hình và kết nối LLM API Key (OpenAI hoặc Google Gemini).
    """
    provider = getattr(settings, "LLM_PROVIDER", "auto").lower()
    openai_key = getattr(settings, "OPENAI_API_KEY", "")
    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "GOOGLE_API_KEY", "")

    # Xác định provider thực tế được ưu tiên
    active_provider = "openai" if (provider == "openai" or (provider == "auto" and openai_key)) else "gemini"

    # 1. Kiểm tra OpenAI
    if active_provider == "openai":
        if not openai_key:
            return {
                "configured": False,
                "valid": False,
                "provider": "openai",
                "masked_key": None,
                "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                "message": "Chưa tìm thấy OPENAI_API_KEY trong file .env.",
            }

        clean_key = openai_key.strip().strip('"').strip("'")
        masked_key = f"{clean_key[:7]}...{clean_key[-4:]}" if len(clean_key) > 12 else "***"
        model_name = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

        try:
            import openai
            client = openai.OpenAI(api_key=clean_key)
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Say 'OK'"}],
                max_tokens=10,
            )
            reply = resp.choices[0].message.content.strip() if resp.choices else "OK"
            return {
                "configured": True,
                "valid": True,
                "provider": "openai",
                "masked_key": masked_key,
                "model": model_name,
                "method": "OpenAI Python SDK",
                "message": "Kết nối OpenAI API thành công! API Key hợp lệ và sẵn sàng.",
                "test_response": reply,
            }
        except Exception as e:
            return {
                "configured": True,
                "valid": False,
                "provider": "openai",
                "masked_key": masked_key,
                "model": model_name,
                "message": f"Máy chủ OpenAI từ chối key hoặc gặp lỗi: {e}",
            }

    # 2. Kiểm tra Google Gemini
    if not gemini_key:
        return {
            "configured": False,
            "valid": False,
            "provider": "gemini",
            "masked_key": None,
            "model": settings.LLM_MODEL,
            "message": "Chưa tìm thấy GEMINI_API_KEY hoặc GOOGLE_API_KEY trong file .env.",
        }

    clean_key = gemini_key.strip().strip('"').strip("'")
    masked_key = f"{clean_key[:6]}...{clean_key[-4:]}" if len(clean_key) > 10 else "***"
    model_name = settings.LLM_MODEL or "gemini-1.5-flash"

    # Thử Phương thức 1: SDK google-genai
    try:
        from google import genai
        client = genai.Client(api_key=clean_key)
        resp = client.models.generate_content(
            model=model_name,
            contents="Say 'OK'",
        )
        return {
            "configured": True,
            "valid": True,
            "provider": "gemini",
            "masked_key": masked_key,
            "model": model_name,
            "method": "google-genai SDK",
            "message": "Kết nối Google Gemini API thành công! API Key hợp lệ.",
            "test_response": resp.text.strip() if resp and resp.text else "OK",
        }
    except Exception as sdk_err:
        # Thử Phương thức 2: Direct REST API qua x-goog-api-key
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            headers = {"Content-Type": "application/json", "x-goog-api-key": clean_key}
            payload = {"contents": [{"parts": [{"text": "Say 'OK'"}]}]}
            with httpx.Client(timeout=15.0) as http_client:
                r = http_client.post(url, headers=headers, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    txt = candidates[0]["content"]["parts"][0]["text"] if candidates else "OK"
                    return {
                        "configured": True,
                        "valid": True,
                        "provider": "gemini",
                        "masked_key": masked_key,
                        "model": model_name,
                        "method": "Direct REST API (x-goog-api-key)",
                        "message": "Kết nối Google Gemini qua REST API (x-goog-api-key) thành công!",
                        "test_response": txt.strip(),
                    }
                else:
                    return {
                        "configured": True,
                        "valid": False,
                        "provider": "gemini",
                        "masked_key": masked_key,
                        "model": model_name,
                        "message": f"Máy chủ Google từ chối key ({r.status_code}): {r.text[:200]}",
                    }
        except Exception as rest_err:
            return {
                "configured": True,
                "valid": False,
                "provider": "gemini",
                "masked_key": masked_key,
                "model": model_name,
                "message": f"SDK lỗi: {sdk_err}; REST lỗi: {rest_err}",
            }


@router.get("/stats/{document_id}")
async def get_quiz_stats(document_id: int, db: Session = Depends(get_db)):
    """
    Lấy thông tin số lượng câu hỏi hiện có trong CSDL SQLite và tiến trình sinh câu hỏi của tài liệu.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")

    # Đếm số câu hỏi trong DB
    questions_query = (
        db.query(Question)
        .join(Chapter)
        .filter(Chapter.document_id == document_id)
    )
    total_questions = questions_query.count()
    verified_questions = questions_query.filter(Question.is_verified == True).count()

    task_info = active_quiz_tasks.get(document_id, {
        "is_generating": False,
        "progress_message": "",
        "error": None,
    })

    return {
        "document_id": document_id,
        "total_questions": total_questions,
        "verified_questions": verified_questions,
        "is_generating": bool(task_info.get("is_generating", False)),
        "progress_message": str(task_info.get("progress_message", "")),
        "error": task_info.get("error"),
    }


@router.post("/generate/{document_id}")
async def generate_quiz(
    document_id: int,
    background_tasks: BackgroundTasks,
    num_questions: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Trigger tạo câu hỏi quiz cho tài liệu.
    Xử lý trong background, hỗ trợ số câu hỏi tùy chọn.
    """
    has_key = bool(
        getattr(settings, "OPENAI_API_KEY", "")
        or getattr(settings, "GEMINI_API_KEY", "")
        or getattr(settings, "GOOGLE_API_KEY", "")
    )
    if not has_key:
        raise HTTPException(
            status_code=400,
            detail="Chưa cấu hình API Key (OpenAI hoặc Google Gemini). Vui lòng điền OPENAI_API_KEY hoặc GEMINI_API_KEY trong file .env trước khi tạo câu hỏi.",
        )

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=400,
            detail="Tài liệu chưa sẵn sàng hoặc gặp lỗi trong quá trình xử lý.",
        )

    # Kiểm tra xem tài liệu có nội dung chữ để tạo đề hay không
    chapters = db.query(Chapter).filter(Chapter.document_id == document_id).all()
    total_chars = sum(len((c.content or "").strip()) for c in chapters)
    if total_chars < 50:
        raise HTTPException(
            status_code=400,
            detail=(
                "Tài liệu này không có nội dung văn bản (0 ký tự). "
                "Có thể do file PDF là ảnh chụp / scan. Vui lòng tải file PDF có chữ hoặc chuyển đổi OCR trước khi tạo đề."
            ),
        )

    # Kiểm tra đã có câu hỏi chưa
    existing_count = (
        db.query(Question)
        .join(Chapter)
        .filter(Chapter.document_id == document_id)
        .count()
    )

    # Nếu task đang chạy cho document này, không tạo thêm task trùng lặp
    if active_quiz_tasks.get(document_id, {}).get("is_generating", False):
        return {
            "message": "Quá trình sinh câu hỏi đang được tiến hành trong background.",
            "document_id": document_id,
            "existing_questions": existing_count,
            "is_generating": True,
        }

    if num_questions is not None:
        background_tasks.add_task(_generate_quiz_background, document_id, num_questions)
    else:
        background_tasks.add_task(_generate_quiz_background, document_id)

    return {
        "message": "Đang tạo câu hỏi quiz trong background.",
        "document_id": document_id,
        "existing_questions": existing_count,
        "is_generating": True,
    }

