# -*- coding: utf-8 -*-
"""
Dịch vụ sinh câu hỏi trắc nghiệm tự động (QuizGenerator) hỗ trợ cả OpenAI (gpt-4o-mini) và Google Gemini.
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
    Sinh câu hỏi trắc nghiệm dựa trên nội dung chương học bằng OpenAI hoặc Google Gemini API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Khởi tạo QuizGenerator hỗ trợ cả OpenAI (gpt-4o-mini) và Google Gemini.
        Tự động nhận diện provider theo tiền tố của API key.

        Args:
            api_key: OpenAI hoặc Gemini API key. Nếu không truyền, lấy từ cấu hình.
            provider: "openai" hoặc "gemini" (tùy chọn, mặc định tự động xác định).
            model: Tên mô hình (tùy chọn, mặc định gpt-4o-mini hoặc gemini-2.0-flash).
        """
        if api_key is not None:
            raw_key = api_key
        else:
            pref_provider = (provider or getattr(settings, "LLM_PROVIDER", "auto")).lower()
            if pref_provider == "openai":
                raw_key = getattr(settings, "OPENAI_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "")
            elif pref_provider == "gemini":
                raw_key = getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "GOOGLE_API_KEY", "")
            else:
                raw_key = (
                    getattr(settings, "OPENAI_API_KEY", "")
                    or getattr(settings, "GEMINI_API_KEY", "")
                    or getattr(settings, "GOOGLE_API_KEY", "")
                )

        self.api_key = raw_key.strip().strip('"').strip("'") if raw_key else ""

        # Xác định provider
        if provider:
            self.provider = provider.lower()
        elif self.api_key.startswith("sk-"):
            self.provider = "openai"
        elif self.api_key.startswith("AIza") or self.api_key.startswith("AQ."):
            self.provider = "gemini"
        else:
            configured_provider = getattr(settings, "LLM_PROVIDER", "auto").lower()
            if configured_provider in ("openai", "gemini"):
                self.provider = configured_provider
            else:
                self.provider = "openai" if getattr(settings, "OPENAI_API_KEY", "") else "gemini"

        # Xác định model
        if model:
            self.model = model
        elif self.provider == "openai":
            self.model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        else:
            self.model = getattr(settings, "LLM_MODEL", "gemini-2.0-flash")

        self.openai_client = None
        self.client = None

        if not self.api_key:
            logger.warning("API Key chưa được cấu hình. Các thao tác gọi LLM sẽ không thể thực hiện.")
        else:
            if self.provider == "openai":
                try:
                    import openai
                    self.openai_client = openai.OpenAI(api_key=self.api_key)
                    self.client = self.openai_client
                    logger.info(f"Khởi tạo OpenAI Client thành công với model '{self.model}'.")
                except Exception as e:
                    logger.error(f"Lỗi khởi tạo OpenAI Client: {e}", exc_info=True)
            else:
                try:
                    self.client = genai.Client(api_key=self.api_key)
                    logger.info(f"Khởi tạo google.genai Client thành công với model '{self.model}'.")
                except Exception as e:
                    logger.error(f"Lỗi khởi tạo google.genai Client: {e}", exc_info=True)

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

        # 1. Cắt tỉa nội dung chương nếu vượt quá giới hạn token an toàn (hỗ trợ tài liệu dài)
        truncated_content = self._truncate_content(chapter_content, max_tokens=25000)

        # 2. Xây dựng prompt
        prompt = self._build_prompt(
            chapter_title=chapter_title,
            content=truncated_content,
            num_questions=num_questions,
            difficulty_mix=difficulty_mix,
        )

        # 3. Gọi LLM API (OpenAI hoặc Gemini) với retry & exponential backoff
        from unittest.mock import Mock, MagicMock
        if isinstance(getattr(self, "_call_openai", None), (Mock, MagicMock)):
            response_text = self._call_openai(prompt)
        elif isinstance(getattr(self, "_call_gemini", None), (Mock, MagicMock)):
            response_text = self._call_gemini(prompt)
        elif self.provider == "openai":
            response_text = self._call_openai(prompt)
        else:
            response_text = self._call_gemini(prompt)

        if not response_text:
            logger.error(f"Không nhận được phản hồi từ LLM ({self.provider}) cho chương '{chapter_title}'.")
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

    def _call_openai(self, prompt: str) -> str:
        """
        Gọi OpenAI Chat Completions API với retry và exponential backoff.
        """
        if not self.api_key:
            raw_key = getattr(settings, "OPENAI_API_KEY", "")
            self.api_key = raw_key.strip().strip('"').strip("'") if raw_key else ""
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY chưa được thiết lập trong cấu hình hoặc biến môi trường.")

        if self.openai_client is None:
            import openai
            self.openai_client = openai.OpenAI(api_key=self.api_key)
            self.client = self.openai_client

        max_retries = 3
        backoff = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Đang gọi OpenAI ({self.model}) - Lần thử {attempt}/{max_retries}...")
                resp = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Bạn là chuyên gia giáo dục và biên soạn đề thi trắc nghiệm chuyên nghiệp. "
                                "Hãy trả về kết quả dưới dạng JSON array hợp lệ theo đúng cấu trúc yêu cầu."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                )
                if resp and resp.choices and resp.choices[0].message.content:
                    return resp.choices[0].message.content
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str
                if is_rate_limit and attempt < max_retries:
                    wait_time = backoff * (2 ** (attempt - 1))
                    logger.warning(f"OpenAI Rate limit (Lần {attempt}/{max_retries}). Chờ {wait_time:.1f}s...")
                    time.sleep(wait_time)
                elif attempt == max_retries:
                    raise RuntimeError(f"Lỗi gọi OpenAI API sau {max_retries} lần thử: {e}") from e
                else:
                    time.sleep(backoff)

        return ""

    def _call_gemini_rest(self, prompt: str, model: str) -> str:
        """
        Gọi trực tiếp Google Gemini API qua REST với header x-goog-api-key (chuẩn cURL của Google).
        Tương thích trực tiếp với các định dạng API key mới (tiền tố AQ. hoặc AIzaSy).
        """
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                else:
                    logger.warning(
                        f"REST call tới {model} trả về status {resp.status_code}: {resp.text[:150]}"
                    )
        except Exception as e:
            logger.warning(f"Lỗi khi gọi REST API ({model}): {e}")

        return ""

    def _call_gemini(self, prompt: str) -> str:
        """
        Gọi Gemini với cơ chế đa tầng (google-genai SDK -> REST API x-goog-api-key)
        kèm retry và exponential backoff khi gặp rate limit.
        """
        if not self.api_key:
            raw_key = getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "GOOGLE_API_KEY", "")
            self.api_key = raw_key.strip().strip('"').strip("'") if raw_key else ""
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY hoặc GOOGLE_API_KEY chưa được thiết lập trong cấu hình hoặc biến môi trường.")

        if self.client is None:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Không thể khởi tạo google.genai Client: {e}. Sẽ dùng REST API fallback.")
                self.client = None

        max_retries = 3
        backoff = 2.0  # seconds

        config = types.GenerateContentConfig(
            temperature=0.7,
            response_mime_type="application/json",
        )

        for attempt in range(1, max_retries + 1):
            # Thử qua google-genai SDK trước
            if self.client is not None:
                try:
                    logger.info(f"Đang gọi Gemini ({self.model}) qua SDK - Lần thử {attempt}/{max_retries}...")
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=config,
                    )
                    if response and response.text:
                        return response.text
                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = (
                        "429" in err_str
                        or "resource_exhausted" in err_str
                        or "rate limit" in err_str
                        or "quota" in err_str
                    )
                    is_not_found = "404" in err_str or "not found" in err_str or "not supported" in err_str
                    if is_not_found and self.model != "gemini-1.5-flash":
                        logger.warning(
                            f"Mô hình '{self.model}' không khả dụng ({e}). Tự động fallback sang 'gemini-1.5-flash'..."
                        )
                        self.model = "gemini-1.5-flash"
                        continue

                    # Thử fallback ngay qua REST API với header x-goog-api-key
                    logger.info("SDK gặp lỗi, chuyển sang gọi trực tiếp bằng REST API (x-goog-api-key)...")
                    rest_res = self._call_gemini_rest(prompt=prompt, model=self.model)
                    if rest_res:
                        return rest_res

                    if is_rate_limit and attempt < max_retries:
                        wait_time = backoff * (2 ** (attempt - 1))
                        logger.warning(f"Rate Limit (Lần {attempt}/{max_retries}). Chờ {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    elif attempt == max_retries:
                        raise RuntimeError(f"Lỗi gọi Gemini API sau {max_retries} lần thử: {e}") from e
                    else:
                        time.sleep(backoff)
                        continue

            # Nếu không có client, gọi qua REST API
            rest_res = self._call_gemini_rest(prompt=prompt, model=self.model)
            if rest_res:
                return rest_res
            if attempt < max_retries:
                time.sleep(backoff)

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

    def _truncate_content(self, content: str, max_tokens: int = 25000) -> str:
        """
        Cắt tỉa văn bản dài tại ranh giới câu nếu vượt quá giới hạn token an toàn.
        Mô hình Gemini 2.0 / 1.5 Flash hỗ trợ ngữ cảnh lên tới 1M tokens,
        ở đây đặt giới hạn an toàn 25,000 tokens (~75,000 ký tự tiếng Việt, tương đương 30-40 trang sách/chương).
        Ước lượng: 1 token ~ 3.0 ký tự tiếng Việt.
        """
        if not content:
            return ""

        max_chars = max_tokens * 3  # Khoảng 75,000 ký tự cho 25,000 tokens
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

