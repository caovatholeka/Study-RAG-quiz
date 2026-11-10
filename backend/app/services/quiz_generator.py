# -*- coding: utf-8 -*-
"""
Dịch vụ sinh câu hỏi trắc nghiệm tự động (QuizGenerator) sử dụng Google Gemini qua google-genai SDK.
Hỗ trợ sinh hàng loạt (batch generation), cắt tỉa văn bản theo ranh giới câu,
xử lý lỗi rate limit với exponential backoff, và validate định dạng dữ liệu đầu ra.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import errors, types

from app.config import settings
from app.utils.prompts import QUIZ_GENERATION_PROMPT

logger = logging.getLogger(__name__)


class QuizGenerator:
    """
    Sinh câu hỏi trắc nghiệm dựa trên nội dung chương học bằng Google Gemini API (google-genai client).
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Khởi tạo QuizGenerator với API Key.

        Args:
            api_key: Google Gemini API key. Nếu không truyền, lấy từ settings.GEMINI_API_KEY.
        """
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model = getattr(settings, "LLM_MODEL", "gemini-2.0-flash")

        if not self.api_key:
            logger.warning(
                "GEMINI_API_KEY chưa được cấu hình. Các thao tác gọi API sẽ không thể thực hiện."
            )
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Khởi tạo google.genai Client thành công với model '{self.model}'.")
            except Exception as e:
                logger.error(f"Lỗi khởi tạo google.genai Client: {e}", exc_info=True)
                self.client = None

    def generate_questions(
        self,
        chapter_title: str,
        chapter_content: str,
        num_questions: int = 15,
        difficulty_mix: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Sinh danh sách câu hỏi trắc nghiệm trong 1 lệnh gọi API Gemini (Batch generation).

        Args:
            chapter_title: Tiêu đề chương.
            chapter_content: Nội dung văn bản của chương.
            num_questions: Số lượng câu hỏi cần sinh (mặc định 15).
            difficulty_mix: Tỷ lệ phân bổ độ khó (mặc định {"easy": 0.3, "medium": 0.5, "hard": 0.2}).

        Returns:
            List[Dict[str, Any]]: Danh sách các câu hỏi trắc nghiệm đã validate.
        """
        if not chapter_content or not chapter_content.strip():
            logger.warning(f"Chương '{chapter_title}' không có nội dung để sinh câu hỏi.")
            return []

        if difficulty_mix is None:
            difficulty_mix = {"easy": 0.3, "medium": 0.5, "hard": 0.2}

        # 1. Cắt tỉa nội dung chương nếu vượt quá giới hạn token an toàn
        truncated_content = self._truncate_content(chapter_content, max_tokens=4000)

        # 2. Xây dựng prompt
        prompt = self._build_prompt(
            chapter_title=chapter_title,
            content=truncated_content,
            num_questions=num_questions,
            difficulty_mix=difficulty_mix,
        )

        # 3. Gọi Gemini API với retry & exponential backoff
        response_text = self._call_gemini(prompt)
        if not response_text:
            logger.error(f"Không nhận được phản hồi từ Gemini cho chương '{chapter_title}'.")
            return []

        # 4. Parse JSON và validate trường dữ liệu
        questions = self._parse_response(response_text)
        logger.info(
            f"Đã sinh và xác thực thành công {len(questions)}/{num_questions} câu hỏi cho chương '{chapter_title}'."
        )
        return questions

    def _build_prompt(
        self,
        chapter_title: str,
        content: str,
        num_questions: int,
        difficulty_mix: Dict[str, float],
    ) -> str:
        """
        Xây dựng prompt hoàn chỉnh dựa trên template QUIZ_GENERATION_PROMPT.
        """
        easy_pct = difficulty_mix.get("easy", 0.3)
        med_pct = difficulty_mix.get("medium", 0.5)
        hard_pct = difficulty_mix.get("hard", 0.2)

        easy_count = max(1, round(num_questions * easy_pct))
        med_count = max(1, round(num_questions * med_pct))
        hard_count = max(1, num_questions - easy_count - med_count)

        dist_str = (
            f"- Dễ (easy): {easy_count} câu ({int(easy_pct * 100)}%)\n"
            f"- Trung bình (medium): {med_count} câu ({int(med_pct * 100)}%)\n"
            f"- Khó (hard): {hard_count} câu ({int(hard_pct * 100)}%)\n"
            f"Tổng cộng: {num_questions} câu hỏi."
        )

        return QUIZ_GENERATION_PROMPT.format(
            chapter_title=chapter_title,
            content=content,
            num_questions=num_questions,
            difficulty_distribution=dist_str,
        )

    def _call_gemini(self, prompt: str) -> str:
        """
        Gọi client.models.generate_content với cơ chế retry 3 lần và exponential backoff khi gặp rate limit.
        """
        if self.client is None:
            if not self.api_key:
                self.api_key = getattr(settings, "GEMINI_API_KEY", "")
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY chưa được thiết lập trong cấu hình hoặc biến môi trường.")
            self.client = genai.Client(api_key=self.api_key)

        max_retries = 3
        backoff = 2.0  # seconds

        config = types.GenerateContentConfig(
            temperature=0.7,
            response_mime_type="application/json",
        )

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Đang gọi Gemini ({self.model}) - Lần thử {attempt}/{max_retries}...")
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    return response.text
                return ""
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
                    logger.warning(
                        f"Gặp Rate Limit từ Gemini API (Lần {attempt}/{max_retries}). "
                        f"Chờ {wait_time:.1f}s trước khi thử lại... Lỗi: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    if attempt == max_retries:
                        logger.error(
                            f"Gọi Gemini API thất bại sau {max_retries} lần thử: {e}",
                            exc_info=True,
                        )
                        raise RuntimeError(f"Lỗi gọi Gemini API sau {max_retries} lần thử: {e}") from e
                    else:
                        wait_time = backoff * (2 ** (attempt - 1))
                        logger.warning(
                            f"Lỗi API trong lần thử {attempt}/{max_retries}. "
                            f"Chờ {wait_time:.1f}s và thử lại... Lỗi: {e}"
                        )
                        time.sleep(wait_time)

        return ""

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse JSON từ phản hồi LLM, gỡ bỏ markdown code block nếu có, và validate các trường bắt buộc.
        """
        if not response_text or not response_text.strip():
            return []

        cleaned = response_text.strip()
        # Loại bỏ markdown code block nếu bị bọc (```json ... ``` hoặc ``` ... ```)
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as jde:
            logger.warning(f"Lỗi parse JSON trực tiếp: {jde}. Thử tìm kiếm mảng JSON bằng regex...")
            match = re.search(r"\[\s*\{.*\}\s*\]", cleaned, flags=re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception as inner_e:
                    logger.error(f"Trích xuất JSON mảng thất bại: {inner_e}")
                    return []
            else:
                logger.error(f"Không tìm thấy mảng JSON trong phản hồi: {cleaned[:200]}")
                return []

        # Nếu model trả về object bọc {"questions": [...]}, {"quiz": [...]}
        if isinstance(data, dict):
            for k in ("questions", "quiz", "data", "items"):
                if k in data and isinstance(data[k], list):
                    data = data[k]
                    break
            else:
                data = [data]

        if not isinstance(data, list):
            logger.error(f"Dữ liệu phản hồi không phải là danh sách: {type(data)}")
            return []

        validated_questions: List[Dict[str, Any]] = []
        valid_letters = {"A", "B", "C", "D"}
        valid_difficulties = {"easy", "medium", "hard"}

        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue

            question_text = str(item.get("question") or "").strip()
            if not question_text:
                continue

            options = item.get("options")
            if not isinstance(options, dict):
                continue

            # Chuẩn hóa keys options thành A, B, C, D
            norm_options = {}
            for k, v in options.items():
                k_clean = str(k).strip().upper()
                if k_clean in valid_letters:
                    norm_options[k_clean] = str(v).strip()

            # Bắt buộc phải có đủ 4 phương án A, B, C, D
            if not valid_letters.issubset(norm_options.keys()):
                continue

            # Validate correct_answer
            correct_ans = str(item.get("correct_answer") or "").strip().upper()
            if correct_ans not in valid_letters:
                continue

            # Validate difficulty
            diff = str(item.get("difficulty") or "medium").strip().lower()
            if diff not in valid_difficulties:
                diff = "medium"

            explanation = str(item.get("explanation") or "").strip()
            topic_tag = str(item.get("topic_tag") or "").strip()

            validated_questions.append({
                "question": question_text,
                "options": norm_options,
                "correct_answer": correct_ans,
                "difficulty": diff,
                "explanation": explanation,
                "topic_tag": topic_tag,
            })

        return validated_questions

    def _truncate_content(self, content: str, max_tokens: int = 4000) -> str:
        """
        Cắt tỉa văn bản dài tại ranh giới câu để không vượt quá giới hạn token an toàn.
        Ước lượng: 1 token ~ 3.0 ký tự tiếng Việt.
        """
        if not content:
            return ""

        max_chars = max_tokens * 3  # Khoảng 12,000 ký tự cho 4000 tokens
        if len(content) <= max_chars:
            return content

        truncated = content[:max_chars]

        # Tìm vị trí kết thúc câu gần nhất (dấu chấm, chấm than, hỏi chấm, xuống dòng)
        boundary_match = None
        for match in re.finditer(r"[.!?\n]\s+", truncated):
            boundary_match = match

        if boundary_match and boundary_match.end() > max_chars // 2:
            return truncated[: boundary_match.end()].strip()

        return truncated.strip()

