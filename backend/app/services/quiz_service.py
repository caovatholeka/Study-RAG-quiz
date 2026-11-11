# -*- coding: utf-8 -*-
"""
Dịch vụ điều phối nghiệp vụ Quiz (QuizService) cho StudyRAG.
Quản lý:
- Khởi tạo phiên làm bài trắc nghiệm (start_quiz)
- Chấm điểm và lưu kết quả bài làm (submit_quiz)
- Lấy lời giải thích chi tiết kèm trích dẫn RAG (get_explanation)
- Tạo và lưu trữ bộ câu hỏi tự động cho tài liệu (generate_quiz_for_document)
"""

import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Chapter, Document, DocumentStatus
from app.models.quiz import Question, QuestionDifficulty, QuizAnswer, QuizMode, QuizSession
from app.services.quiz_generator import QuizGenerator
from app.services.quiz_verifier import QuizVerifier
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class QuizService:
    """
    Dịch vụ điều phối toàn bộ vòng đời và hoạt động của Quiz trong StudyRAG.
    """

    def start_quiz(
        self,
        document_id: Optional[int] = None,
        chapter_ids: Optional[List[int]] = None,
        topic_tags: Optional[List[str]] = None,
        num_questions: int = 10,
        db: Optional[Session] = None,
        mode: Optional[Union[str, QuizMode]] = None,
    ) -> Dict[str, Any]:
        """
        Bắt đầu phiên quiz. Truy vấn câu hỏi từ DB, chọn ngẫu nhiên, tạo QuizSession
        và trả về danh sách câu hỏi KHÔNG có đáp án đúng.

        Args:
            document_id: ID tài liệu (tùy chọn nếu có chapter_ids/topic_tags).
            chapter_ids: Danh sách chapter_id cần lấy câu hỏi.
            topic_tags: Danh sách chủ đề cần lấy câu hỏi.
            num_questions: Số lượng câu hỏi cần lấy.
            db: Database session.
            mode: Chế độ quiz ("chapter", "topic", "full").

        Returns:
            Dict[str, Any]: {session_id, total_questions, mode, questions: [...]}
        """
        if db is None:
            raise ValueError("Cần cung cấp database session (db) để bắt đầu quiz.")

        # Xây dựng query lọc câu hỏi đã được xác thực (is_verified == True)
        query = db.query(Question).filter(Question.is_verified == True)  # noqa: E712

        resolved_doc_id = document_id
        resolved_chapter_ids = chapter_ids or []
        resolved_mode = QuizMode.CHAPTER

        if chapter_ids:
            query = query.filter(Question.chapter_id.in_(chapter_ids))
            resolved_mode = QuizMode.CHAPTER
            if not resolved_doc_id:
                first_ch = db.query(Chapter).filter(Chapter.id == chapter_ids[0]).first()
                if not first_ch:
                    raise HTTPException(status_code=404, detail="Không tìm thấy chương chỉ định.")
                resolved_doc_id = first_ch.document_id

        elif topic_tags:
            query = query.filter(Question.topic_tag.in_(topic_tags))
            resolved_mode = QuizMode.TOPIC
            all_matching = query.all()
            if not all_matching:
                # Nếu không có câu verified theo topic, thử fallback không filter verified
                query_fallback = db.query(Question).filter(Question.topic_tag.in_(topic_tags))
                all_matching = query_fallback.all()
                if not all_matching:
                    raise HTTPException(
                        status_code=404,
                        detail="Không tìm thấy câu hỏi nào cho các chủ đề này.",
                    )
                query = query_fallback

            first_ch = db.query(Chapter).filter(Chapter.id == all_matching[0].chapter_id).first()
            if first_ch and not resolved_doc_id:
                resolved_doc_id = first_ch.document_id
            resolved_chapter_ids = list(set(q.chapter_id for q in all_matching))

        elif document_id:
            query = query.join(Chapter).filter(Chapter.document_id == document_id)
            resolved_mode = QuizMode.FULL
            all_chapters = db.query(Chapter).filter(Chapter.document_id == document_id).all()
            resolved_chapter_ids = [c.id for c in all_chapters]

        else:
            raise HTTPException(
                status_code=400,
                detail="Phải cung cấp ít nhất một trong các tiêu chí: document_id, chapter_ids hoặc topic_tags.",
            )

        available_questions = query.all()

        # Fallback: nếu chưa có câu hỏi nào có cờ is_verified=True, lấy tất cả câu hỏi chưa verified của chương/doc
        if not available_questions:
            logger.info("Không có câu hỏi is_verified=True. Đang thử fallback lấy câu hỏi hiện có...")
            fallback_query = db.query(Question)
            if chapter_ids:
                fallback_query = fallback_query.filter(Question.chapter_id.in_(chapter_ids))
            elif topic_tags:
                fallback_query = fallback_query.filter(Question.topic_tag.in_(topic_tags))
            elif document_id:
                fallback_query = fallback_query.join(Chapter).filter(Chapter.document_id == document_id)
            available_questions = fallback_query.all()

        if not available_questions:
            raise HTTPException(
                status_code=404,
                detail="Chưa có câu hỏi nào. Hãy generate quiz cho tài liệu trước.",
            )

        # Lấy ngẫu nhiên số lượng câu hỏi theo yêu cầu
        selected_count = min(num_questions, len(available_questions))
        selected_questions = random.sample(available_questions, selected_count)

        # Xác định QuizMode
        if mode:
            try:
                resolved_mode = QuizMode(mode.value if hasattr(mode, "value") else str(mode))
            except Exception:
                pass

        if not resolved_doc_id and selected_questions:
            ch = db.query(Chapter).filter(Chapter.id == selected_questions[0].chapter_id).first()
            if ch:
                resolved_doc_id = ch.document_id

        # Tạo QuizSession record
        session = QuizSession(
            document_id=resolved_doc_id or 0,
            chapter_ids=resolved_chapter_ids,
            mode=resolved_mode,
            total_questions=selected_count,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Chuẩn bị danh sách câu hỏi KHÔNG kèm đáp án đúng
        questions_response = [
            {
                "id": q.id,
                "question_text": q.question_text,
                "options": q.options,
                "difficulty": q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty),
                "topic_tag": q.topic_tag,
            }
            for q in selected_questions
        ]

        logger.info(
            f"Bắt đầu phiên quiz session_id={session.id} với {selected_count} câu hỏi (mode={session.mode.value})."
        )

        return {
            "session_id": session.id,
            "total_questions": selected_count,
            "mode": session.mode.value if hasattr(session.mode, "value") else str(session.mode),
            "questions": questions_response,
        }

    def submit_quiz(
        self,
        session_id: int,
        answers: List[Union[Dict[str, Any], Any]],
        db: Session,
    ) -> Dict[str, Any]:
        """
        Nộp bài quiz, chấm điểm, lưu chi tiết câu trả lời vào QuizAnswer,
        cập nhật phiên quiz và trả về kết quả chi tiết kèm giải thích.

        Args:
            session_id: ID phiên làm bài.
            answers: Danh sách câu trả lời [{question_id, answer}, ...].
            db: Database session.

        Returns:
            Dict[str, Any]: Kết quả chi tiết {session_id, score, total_questions, correct_count, percentage, results: [...]}
        """
        session = db.query(QuizSession).filter(QuizSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên quiz.")
        if session.finished_at:
            raise HTTPException(status_code=400, detail="Phiên quiz này đã kết thúc trước đó.")

        correct_count = 0
        detailed_results: List[Dict[str, Any]] = []

        for item in answers:
            # Hỗ trợ cả dict và Pydantic schema object (AnswerItem)
            q_id = item.get("question_id") if isinstance(item, dict) else getattr(item, "question_id", None)
            user_ans = item.get("answer") if isinstance(item, dict) else getattr(item, "answer", "")
            user_ans = str(user_ans or "").strip().upper()

            question = db.query(Question).filter(Question.id == q_id).first()
            if not question:
                continue

            correct_ans = str(question.correct_answer or "").strip().upper()
            is_correct = (user_ans == correct_ans)
            if is_correct:
                correct_count += 1

            # Lưu vào DB QuizAnswer
            quiz_answer = QuizAnswer(
                session_id=session.id,
                question_id=question.id,
                user_answer=user_ans,
                is_correct=is_correct,
            )
            db.add(quiz_answer)

            detailed_results.append({
                "question_id": question.id,
                "question_text": question.question_text,
                "options": question.options,
                "user_answer": user_ans,
                "correct_answer": correct_ans,
                "is_correct": is_correct,
                "explanation": question.explanation,
            })

        # Cập nhật kết quả phiên quiz
        now = datetime.now(timezone.utc)
        total = session.total_questions if session.total_questions > 0 else len(answers)
        score = (correct_count / total * 10) if total > 0 else 0.0
        percentage = (correct_count / total * 100) if total > 0 else 0.0

        session.score = round(score, 2)
        session.finished_at = now
        db.commit()

        logger.info(
            f"Phiên quiz session_id={session.id} đã hoàn thành. Đúng: {correct_count}/{total} ({percentage:.1f}%), Điểm: {score:.2f}."
        )

        return {
            "session_id": session.id,
            "score": session.score,
            "total_questions": total,
            "correct_count": correct_count,
            "percentage": round(percentage, 2),
            "mode": session.mode.value if hasattr(session.mode, "value") else str(session.mode),
            "started_at": session.started_at,
            "finished_at": now,
            "results": detailed_results,
        }

    def get_explanation(
        self,
        question_id: int,
        db: Session,
        rag_service: Optional[RAGService] = None,
    ) -> str:
        """
        Lấy giải thích đáp án từ DB. Nếu có RAGService, truy xuất thêm ngữ cảnh và trích dẫn nguồn.

        Args:
            question_id: ID câu hỏi.
            db: Database session.
            rag_service: Instance của RAGService (tùy chọn).

        Returns:
            str: Đoạn giải thích chi tiết.
        """
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return "Không tìm thấy câu hỏi trong hệ thống."

        base_explanation = question.explanation or "Chưa có lời giải thích sẵn có."

        if rag_service is not None and question.chapter_id:
            try:
                chapter = db.query(Chapter).filter(Chapter.id == question.chapter_id).first()
                doc_id = chapter.document_id if chapter else 0
                source_context = rag_service.retrieve_for_question(
                    question_text=question.question_text,
                    chapter_id=question.chapter_id,
                    document_id=doc_id,
                )
                if source_context:
                    return (
                        f"{base_explanation}\n\n"
                        f"=== TÀI LIỆU NGUỒN TRÍCH DẪN ===\n"
                        f"{source_context}"
                    )
            except Exception as e:
                logger.error(f"Lỗi khi truy xuất RAG context cho câu hỏi {question_id}: {e}")

        return base_explanation

    def generate_quiz_for_document(
        self,
        document_id: int,
        db: Session,
        quiz_generator: QuizGenerator,
        quiz_verifier: QuizVerifier,
        num_questions_per_chapter: Optional[int] = None,
        progress_callback: Optional[Any] = None,
    ) -> int:
        """
        Duyệt qua tất cả các chương của tài liệu, sinh câu hỏi bằng QuizGenerator,
        xác thực qua QuizVerifier 3 bước và lưu các câu hỏi vào DB.

        Args:
            document_id: ID của tài liệu.
            db: Database session.
            quiz_generator: Instance của QuizGenerator.
            quiz_verifier: Instance của QuizVerifier.
            num_questions_per_chapter: Số câu hỏi mỗi chương (mặc định lấy từ cấu hình).
            progress_callback: Hàm callback cập nhật thông điệp tiến trình (nếu có).

        Returns:
            int: Tổng số câu hỏi đã được tạo và lưu trữ.
        """
        logger.info(f"Bắt đầu quy trình generate quiz cho document_id={document_id}...")
        if progress_callback:
            progress_callback("Đang nạp danh sách chương mục từ cơ sở dữ liệu...")

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Không tìm thấy tài liệu ID={document_id}")
            return 0

        chapters = (
            db.query(Chapter)
            .filter(Chapter.document_id == document_id)
            .order_by(Chapter.chapter_number.asc())
            .all()
        )

        if not chapters:
            logger.warning(f"Tài liệu ID={document_id} không có chương nào để tạo quiz.")
            return 0

        valid_chapters = [c for c in chapters if len((c.content or "").strip()) >= 50]
        if not valid_chapters:
            logger.warning(f"Tài liệu ID={document_id} không có chương nào đủ nội dung để tạo quiz.")
            return 0

        total_saved_questions = 0
        total_target = num_questions_per_chapter  # Mục tiêu tổng số câu cho toàn bộ tài liệu (nếu có)

        for idx, chapter in enumerate(valid_chapters):
            if total_target is not None and total_saved_questions >= total_target:
                break

            content = (chapter.content or "").strip()

            # Tính số câu hỏi cần sinh cho chương này
            if total_target is not None:
                remaining_needed = total_target - total_saved_questions
                remaining_chapters = len(valid_chapters) - idx
                num_to_gen = max(1, (remaining_needed + remaining_chapters - 1) // remaining_chapters)
                num_to_gen = min(num_to_gen, remaining_needed)
            else:
                num_to_gen = getattr(settings, "MAX_QUESTIONS_PER_CHAPTER", 15)

            msg = (
                f"Đang sinh {num_to_gen} câu hỏi cho chương #{chapter.chapter_number}: '{chapter.title}' "
                f"(Đã lưu {total_saved_questions}/{total_target or 'toàn bộ'})..."
            )
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)

            try:
                # 1. Sinh câu hỏi bằng AI
                raw_questions = quiz_generator.generate_questions(
                    chapter_title=chapter.title,
                    chapter_content=content,
                    num_questions=num_to_gen,
                )

                if not raw_questions:
                    logger.warning(f"Không sinh được câu hỏi nào cho chương ID {chapter.id}.")
                    continue

                # 2. Xác thực bằng pipeline 3 bước (RAG -> Fuzzy -> LLM)
                if progress_callback:
                    progress_callback(f"Đang kiểm định {len(raw_questions)} câu hỏi của chương '{chapter.title}'...")

                verified_questions = quiz_verifier.verify_questions(
                    questions=raw_questions,
                    chapter_id=chapter.id,
                    document_id=document_id,
                )

                # Giới hạn không vượt quá target nếu có
                if total_target is not None:
                    allowed_count = max(0, total_target - total_saved_questions)
                    verified_questions = verified_questions[:allowed_count]

                # 3. Lưu vào database
                for q_dict in verified_questions:
                    diff_val = str(q_dict.get("difficulty") or "medium").strip().lower()
                    try:
                        diff_enum = QuestionDifficulty(diff_val)
                    except ValueError:
                        diff_enum = QuestionDifficulty.MEDIUM

                    topic_tag = q_dict.get("topic_tag") or chapter.title

                    question_record = Question(
                        chapter_id=chapter.id,
                        question_text=q_dict.get("question", ""),
                        options=q_dict.get("options", {}),
                        correct_answer=str(q_dict.get("correct_answer", "A")).strip().upper(),
                        difficulty=diff_enum,
                        explanation=q_dict.get("explanation", ""),
                        topic_tag=topic_tag,
                        is_verified=bool(q_dict.get("is_verified", False)),
                    )
                    db.add(question_record)
                    total_saved_questions += 1

                db.commit()
                logger.info(
                    f"Đã lưu thành công {len(verified_questions)} câu hỏi cho chương ID {chapter.id}."
                )
                if progress_callback:
                    progress_callback(f"Đã lưu {len(verified_questions)} câu hỏi cho chương #{chapter.chapter_number}.")

                # Giãn cách 1 giây để an toàn cho rate limit
                time.sleep(1.0)

            except Exception as e:
                db.rollback()
                logger.error(
                    f"Lỗi khi sinh/lưu câu hỏi cho chương ID {chapter.id} ('{chapter.title}'): {e}",
                    exc_info=True,
                )

        final_msg = f"Hoàn thành generate quiz cho document_id={document_id}. Tổng số câu hỏi mới lưu: {total_saved_questions}."
        logger.info(final_msg)
        if progress_callback:
            progress_callback(final_msg)

        return total_saved_questions

