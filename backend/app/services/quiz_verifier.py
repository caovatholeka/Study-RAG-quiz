# -*- coding: utf-8 -*-
"""
Dịch vụ xác thực câu hỏi trắc nghiệm (QuizVerifier) cho StudyRAG.
Áp dụng quy trình xác thực 3 bước:
1. RAG Retrieve: Truy xuất ngữ cảnh tài liệu liên quan (top 3 chunks).
2. Fuzzy Matching: So khớp đáp án với ngữ cảnh nguồn bằng rapidfuzz (ngưỡng 70%).
3. LLM Verification: Nếu độ khớp < 70%, gọi Gemini xác thực và tự động điều chỉnh đáp án.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from rapidfuzz import fuzz

from app.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService
from app.utils.prompts import QUIZ_VERIFICATION_PROMPT

logger = logging.getLogger(__name__)


class QuizVerifier:
    """
    Xác thực câu hỏi và đáp án quiz theo quy trình 3 bước đảm bảo độ chính xác theo tài liệu nguồn.
    """

    def __init__(
        self,
        rag_service: RAGService,
        embedding_service: EmbeddingService,
        api_key: Optional[str] = None,
    ) -> None:
        """
        Khởi tạo QuizVerifier.

        Args:
            rag_service: Instance của RAGService để truy xuất ngữ cảnh.
            embedding_service: Instance của EmbeddingService.
            api_key: Gemini API key. Mặc định lấy từ settings.GEMINI_API_KEY.
        """
        self.rag_service = rag_service
        self.embedding_service = embedding_service
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model = getattr(settings, "LLM_MODEL", "gemini-2.0-flash")

        if not self.api_key:
            logger.warning(
                "GEMINI_API_KEY chưa được cấu hình. Bước 3 LLM verification sẽ fallback."
            )
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"QuizVerifier khởi tạo google.genai Client với model '{self.model}'.")
            except Exception as e:
                logger.error(f"Lỗi khởi tạo Gemini Client trong QuizVerifier: {e}", exc_info=True)
                self.client = None

    def verify_questions(
        self,
        questions: List[Dict[str, Any]],
        chapter_id: int,
        document_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Xác thực một danh sách câu hỏi trắc nghiệm (batch verification).

        Args:
            questions: Danh sách câu hỏi dạng dict.
            chapter_id: ID của chương.
            document_id: ID của tài liệu.

        Returns:
            List[Dict[str, Any]]: Danh sách câu hỏi kèm cờ is_verified (True/False).
        """
        if not questions:
            return []

        logger.info(
            f"Bắt đầu pipeline xác thực {len(questions)} câu hỏi cho chapter_id={chapter_id}, doc_id={document_id}..."
        )

        verified_list: List[Dict[str, Any]] = []
        for idx, q in enumerate(questions):
            try:
                verified_q = self._verify_single(q, chapter_id=chapter_id, document_id=document_id)
                verified_list.append(verified_q)
            except Exception as e:
                logger.error(f"Lỗi khi xác thực câu hỏi #{idx + 1}: {e}", exc_info=True)
                # Fallback: giữ câu hỏi và đánh dấu chưa xác thực
                q_copy = dict(q)
                q_copy["is_verified"] = False
                verified_list.append(q_copy)

        verified_count = sum(1 for q in verified_list if q.get("is_verified", False))
        logger.info(
            f"Hoàn thành xác thực: {verified_count}/{len(questions)} câu hỏi đạt chuẩn."
        )
        return verified_list

    def _verify_single(
        self,
        question: Dict[str, Any],
        chapter_id: int,
        document_id: int,
    ) -> Dict[str, Any]:
        """
        Quy trình xác thực 3 bước cho 1 câu hỏi đơn lẻ:
        - Bước 1: RAG retrieve ngữ cảnh liên quan (top 3 chunks).
        - Bước 2: Fuzzy matching đáp án đúng với ngữ cảnh bằng rapidfuzz (threshold 70%).
        - Bước 3: Nếu < 70% -> gọi LLM verify bằng QUIZ_VERIFICATION_PROMPT, sửa đáp án nếu sai.

        Returns:
            Dict[str, Any]: Câu hỏi kèm cờ is_verified và đáp án đã cập nhật (nếu có).
        """
        q_result = dict(question)
        question_text = str(q_result.get("question") or "").strip()
        correct_letter = str(q_result.get("correct_answer") or "A").strip().upper()
        options = q_result.get("options", {})
        answer_text = str(options.get(correct_letter) or "").strip()

        # ===== Bước 1: RAG Retrieve Context (Top 3 chunks) =====
        retrieved_chunks = self.rag_service.retrieve_context(
            query=f"{question_text} {answer_text}",
            document_id=document_id,
            chapter_number=None,
            n_results=3,
        )

        if not retrieved_chunks:
            # Fallback nếu retrieve_context rỗng: thử truy vấn bằng question_text
            retrieved_chunks = self.rag_service.retrieve_context(
                query=question_text,
                document_id=document_id,
                n_results=3,
            )

        source_context = self.rag_service.format_context_with_sources(retrieved_chunks)
        source_raw_text = " ".join(c.get("text", "") for c in retrieved_chunks)

        # Nếu hoàn toàn không có tài liệu nguồn từ ChromaDB
        if not source_raw_text.strip():
            logger.warning(
                f"Không tìm thấy ngữ cảnh nào trong vector DB cho câu hỏi: '{question_text[:40]}...'"
            )
            # Nếu có giải thích kèm theo, thử so khớp với explanation hoặc chuyển sang LLM
            q_result["is_verified"] = False
            return q_result

        # ===== Bước 2: Fuzzy Matching (Threshold 70%) =====
        fuzzy_score = self._fuzzy_verify(answer_text=answer_text, source_text=source_raw_text)
        logger.debug(f"Fuzzy score cho câu hỏi '{question_text[:30]}...': {fuzzy_score:.1f}%")

        if fuzzy_score >= 70.0:
            logger.info(
                f"Bước 2: Fuzzy match thành công ({fuzzy_score:.1f}% >= 70%) cho câu: '{question_text[:30]}...'"
            )
            q_result["is_verified"] = True
            return q_result

        # ===== Bước 3: LLM Verification & Correction (< 70%) =====
        logger.info(
            f"Bước 2: Fuzzy match {fuzzy_score:.1f}% < 70%. Chuyển sang Bước 3: LLM Verification..."
        )

        llm_res = self._llm_verify(question=q_result, source_context=source_context)
        is_valid = llm_res.get("is_valid", False)

        if is_valid:
            logger.info(f"Bước 3: LLM xác nhận đáp án '{correct_letter}' là chính xác.")
            q_result["is_verified"] = True
        else:
            # LLM xác định đáp án chưa đúng -> kiểm tra đáp án sửa đổi
            suggested_letter = str(llm_res.get("correct_answer") or "").strip().upper()
            # Trích xuất ký tự đơn A, B, C, D từ suggested_letter nếu chứa text thừa
            match_letter = re.search(r"\b([A-D])\b", suggested_letter)
            clean_letter = match_letter.group(1) if match_letter else suggested_letter

            if clean_letter in options:
                logger.info(
                    f"Bước 3: LLM sửa đáp án từ '{correct_letter}' sang '{clean_letter}'."
                )
                q_result["correct_answer"] = clean_letter
                new_explanation = llm_res.get("explanation")
                if new_explanation:
                    q_result["explanation"] = new_explanation
                q_result["is_verified"] = True
            else:
                logger.warning(
                    f"Bước 3: LLM từ chối đáp án nhưng không cung cấp lựa chọn hợp lệ: '{suggested_letter}'."
                )
                q_result["is_verified"] = False

        return q_result

    def _fuzzy_verify(self, answer_text: str, source_text: str) -> float:
        """
        Tính toán độ tương đồng một phần (partial_ratio) giữa đáp án và văn bản tài liệu nguồn.

        Args:
            answer_text: Nội dung của phương án trả lời đúng.
            source_text: Chuỗi văn bản ngữ cảnh nguồn ghép từ các chunk.

        Returns:
            float: Điểm số từ 0.0 đến 100.0.
        """
        if not answer_text or not source_text:
            return 0.0

        # Làm sạch chuỗi
        clean_ans = answer_text.strip().lower()
        clean_src = source_text.strip().lower()

        try:
            score = float(fuzz.partial_ratio(clean_ans, clean_src))
            return score
        except Exception as e:
            logger.error(f"Lỗi tính fuzzy ratio: {e}")
            return 0.0

    def _llm_verify(self, question: Dict[str, Any], source_context: str) -> Dict[str, Any]:
        """
        Gọi Google Gemini để kiểm định câu hỏi và đáp án dựa trên QUIZ_VERIFICATION_PROMPT.

        Args:
            question: Dict chứa câu hỏi và các phương án.
            source_context: Chuỗi ngữ cảnh tài liệu kèm trích dẫn nguồn.

        Returns:
            Dict[str, Any]: {"is_valid": bool, "verdict": "YES"/"NO", "correct_answer": str, "explanation": str}.
        """
        if self.client is None:
            if not self.api_key:
                self.api_key = getattr(settings, "GEMINI_API_KEY", "")
            if not self.api_key:
                logger.warning("Không có GEMINI_API_KEY để thực hiện _llm_verify.")
                return {"is_valid": False, "verdict": "NO", "correct_answer": "", "explanation": "Không có API key."}
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Không thể khởi tạo Gemini Client trong _llm_verify: {e}")
                return {"is_valid": False, "verdict": "NO", "correct_answer": "", "explanation": str(e)}

        q_text = str(question.get("question") or "")
        options = question.get("options", {})
        correct_letter = str(question.get("correct_answer") or "A").strip().upper()
        correct_content = options.get(correct_letter, "")

        options_formatted = "\n".join(f"{k}. {v}" for k, v in sorted(options.items()))
        full_question_info = f"{q_text}\nCác phương án:\n{options_formatted}"
        full_correct_info = f"{correct_letter}: {correct_content}"

        prompt = QUIZ_VERIFICATION_PROMPT.format(
            source_context=source_context,
            question=full_question_info,
            correct_answer=full_correct_info,
        )

        config = types.GenerateContentConfig(
            temperature=0.2,  # Nhiệt độ thấp cho tác vụ kiểm định chính xác
            response_mime_type="application/json",
        )

        max_retries = 3
        backoff = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    return self._parse_llm_verification_response(response.text, default_letter=correct_letter)
                return {"is_valid": False, "verdict": "NO", "correct_answer": correct_letter, "explanation": "Rỗng."}
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = (
                    "429" in err_str
                    or "resource_exhausted" in err_str
                    or "rate limit" in err_str
                    or "quota" in err_str
                )
                if is_rate_limit and attempt < max_retries:
                    wait_time = backoff * (2 ** (attempt - 1))
                    logger.warning(f"Rate limit khi verify câu hỏi. Thử lại sau {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    if attempt == max_retries:
                        logger.error(f"_llm_verify thất bại sau {max_retries} lần: {e}")
                        return {
                            "is_valid": False,
                            "verdict": "NO",
                            "correct_answer": correct_letter,
                            "explanation": f"Lỗi gọi LLM: {e}",
                        }
                    time.sleep(backoff)

        return {"is_valid": False, "verdict": "NO", "correct_answer": correct_letter, "explanation": "Thất bại."}

    def _parse_llm_verification_response(
        self,
        response_text: str,
        default_letter: str = "A",
    ) -> Dict[str, Any]:
        """
        Parse và chuẩn hóa kết quả JSON từ LLM Verification.
        """
        cleaned = response_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Không thể parse JSON từ _llm_verify ({e}): {cleaned[:100]}")
            # Fallback parse theo text
            is_yes = bool(re.search(r"\bYES\b", cleaned, re.IGNORECASE))
            return {
                "verdict": "YES" if is_yes else "NO",
                "is_valid": is_yes,
                "correct_answer": default_letter,
                "explanation": cleaned,
            }

        verdict = str(data.get("verdict") or "").strip().upper()
        is_valid = bool(data.get("is_valid", False))

        if "YES" in verdict:
            is_valid = True
        elif "NO" in verdict:
            is_valid = False

        correct_ans = str(data.get("correct_answer") or default_letter).strip().upper()
        explanation = str(data.get("explanation") or "").strip()

        return {
            "verdict": "YES" if is_valid else "NO",
            "is_valid": is_valid,
            "correct_answer": correct_ans,
            "explanation": explanation,
        }

