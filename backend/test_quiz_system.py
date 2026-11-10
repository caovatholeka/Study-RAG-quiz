# -*- coding: utf-8 -*-
"""
Bộ kiểm thử toàn diện (Unit & Integration tests) cho Quiz System trong StudyRAG:
- FILE 1: app.utils.prompts
- FILE 2: app.services.quiz_generator (QuizGenerator)
- FILE 3: app.services.quiz_verifier (QuizVerifier)
- FILE 4: app.services.quiz_service (QuizService)
- Router & API Endpoints (/api/quiz/start, /api/quiz/submit, /api/quiz/explanation/{id})
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Thêm thư mục backend vào sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.document import Chapter, ChapterLevel, Document, DocumentStatus
from app.models.quiz import Question, QuestionDifficulty, QuizAnswer, QuizMode, QuizSession
from app.services.embedding_service import EmbeddingService
from app.services.quiz_generator import QuizGenerator
from app.services.quiz_service import QuizService
from app.services.quiz_verifier import QuizVerifier
from app.services.rag_service import RAGService
from app.utils.prompts import (
    EXPLANATION_GENERATION_PROMPT,
    QUIZ_GENERATION_PROMPT,
    QUIZ_VERIFICATION_PROMPT,
    TOPIC_EXTRACTION_PROMPT,
)


class TestPrompts(unittest.TestCase):
    """Kiểm thử tính hợp lệ của các prompt templates trong app.utils.prompts."""

    def test_quiz_generation_prompt_formatting(self):
        """Kiểm tra placeholders của QUIZ_GENERATION_PROMPT."""
        formatted = QUIZ_GENERATION_PROMPT.format(
            chapter_title="Chương 1: Mở đầu",
            content="Nội dung bài học thử nghiệm",
            num_questions=5,
            difficulty_distribution="- Dễ: 2\n- Vừa: 2\n- Khó: 1",
        )
        self.assertIn("Chương 1: Mở đầu", formatted)
        self.assertIn("Nội dung bài học thử nghiệm", formatted)
        self.assertIn("5", formatted)
        self.assertIn("TIẾNG VIỆT", formatted)
        self.assertIn("JSON array", formatted)

    def test_quiz_verification_prompt_formatting(self):
        """Kiểm tra placeholders của QUIZ_VERIFICATION_PROMPT."""
        formatted = QUIZ_VERIFICATION_PROMPT.format(
            source_context="Ngữ cảnh tài liệu nguồn",
            question="RAG là gì?",
            correct_answer="A",
        )
        self.assertIn("Ngữ cảnh tài liệu nguồn", formatted)
        self.assertIn("RAG là gì?", formatted)
        self.assertIn("A", formatted)
        self.assertIn("verdict", formatted)

    def test_explanation_generation_prompt_formatting(self):
        """Kiểm tra placeholders của EXPLANATION_GENERATION_PROMPT."""
        formatted = EXPLANATION_GENERATION_PROMPT.format(
            source_context="Ngữ cảnh nguồn",
            question="Câu hỏi mẫu",
            options="A. Lựa chọn 1\nB. Lựa chọn 2",
            correct_answer="A",
            user_answer="B",
        )
        self.assertIn("Ngữ cảnh nguồn", formatted)
        self.assertIn("Câu hỏi mẫu", formatted)
        self.assertIn("A", formatted)
        self.assertIn("B", formatted)

    def test_topic_extraction_prompt_formatting(self):
        """Kiểm tra placeholders của TOPIC_EXTRACTION_PROMPT."""
        formatted = TOPIC_EXTRACTION_PROMPT.format(
            chapter_title="Chương 2",
            content="Nội dung chương 2",
        )
        self.assertIn("Chương 2", formatted)
        self.assertIn("Nội dung chương 2", formatted)


class TestQuizGenerator(unittest.TestCase):
    """Kiểm thử cho lớp QuizGenerator."""

    def setUp(self):
        self.generator = QuizGenerator(api_key="mock_api_key")

    def test_init_with_and_without_key(self):
        """Kiểm thử khởi tạo có và không có API key."""
        gen_with_key = QuizGenerator(api_key="fake_key_123")
        self.assertIsNotNone(gen_with_key.client)

        gen_no_key = QuizGenerator(api_key="")
        # Không có key thì client = None và không raise crash lúc init
        self.assertIsNone(gen_no_key.client)

    def test_truncate_content(self):
        """Kiểm tra hàm cắt tỉa nội dung tại ranh giới câu."""
        short_text = "Đây là văn bản ngắn. Văn bản hoàn toàn nằm trong giới hạn."
        truncated_short = self.generator._truncate_content(short_text, max_tokens=100)
        self.assertEqual(short_text, truncated_short)

        # Tạo văn bản dài vượt max_tokens
        long_sentence = "Câu số 1 rất dài và mang nhiều ý nghĩa khoa học. "
        long_text = long_sentence * 500  # Rất dài
        truncated_long = self.generator._truncate_content(long_text, max_tokens=50)
        self.assertTrue(len(truncated_long) <= 50 * 3 + 10)
        self.assertTrue(truncated_long.endswith("."))

    def test_build_prompt(self):
        """Kiểm tra xây dựng prompt với các tỷ lệ độ khó."""
        prompt = self.generator._build_prompt(
            chapter_title="Chương 3: Vector Embeddings",
            content="Embedding là phương pháp biểu diễn ngữ nghĩa dưới dạng vector.",
            num_questions=10,
            difficulty_mix={"easy": 0.4, "medium": 0.4, "hard": 0.2},
        )
        self.assertIn("Chương 3: Vector Embeddings", prompt)
        self.assertIn("10", prompt)
        self.assertIn("Dễ (easy): 4 câu", prompt)

    def test_parse_response_clean_json(self):
        """Kiểm tra parse JSON thuần hợp lệ."""
        sample_json = json.dumps([
            {
                "question": "RAG là gì?",
                "options": {
                    "A": "Retrieval-Augmented Generation",
                    "B": "Random Access Generator",
                    "C": "Rapid Application Growth",
                    "D": "Realtime AI Gateway"
                },
                "correct_answer": "A",
                "difficulty": "medium",
                "explanation": "RAG kết hợp truy xuất và sinh ngôn ngữ.",
                "topic_tag": "Tổng quan RAG"
            }
        ])
        parsed = self.generator._parse_response(sample_json)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["question"], "RAG là gì?")
        self.assertEqual(parsed[0]["correct_answer"], "A")
        self.assertEqual(parsed[0]["difficulty"], "medium")

    def test_parse_response_markdown_wrapped(self):
        """Kiểm tra parse JSON bị bọc trong markdown code fence."""
        sample_wrapped = """```json
[
  {
    "question": "ChromaDB là gì?",
    "options": {
      "A": "Vector Database",
      "B": "Relational Database",
      "C": "Message Queue",
      "D": "Operating System"
    },
    "correct_answer": "A",
    "difficulty": "easy",
    "explanation": "ChromaDB là một Vector DB mã nguồn mở.",
    "topic_tag": "Vector DB"
  }
]
```"""
        parsed = self.generator._parse_response(sample_wrapped)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["question"], "ChromaDB là gì?")
        self.assertEqual(parsed[0]["correct_answer"], "A")

    def test_parse_response_invalid_filtered(self):
        """Kiểm tra các câu hỏi thiếu trường bắt buộc hoặc sai định dạng bị loại bỏ."""
        sample_data = json.dumps([
            # Thiếu options D
            {
                "question": "Câu thiếu options",
                "options": {"A": "1", "B": "2", "C": "3"},
                "correct_answer": "A",
            },
            # correct_answer không hợp lệ
            {
                "question": "Câu sai đáp án",
                "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                "correct_answer": "E",
            },
            # Câu chuẩn
            {
                "question": "Câu chuẩn",
                "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                "correct_answer": "B",
                "difficulty": "hard",
            }
        ])
        parsed = self.generator._parse_response(sample_data)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["question"], "Câu chuẩn")
        self.assertEqual(parsed[0]["correct_answer"], "B")

    @patch("app.services.quiz_generator.QuizGenerator._call_gemini")
    def test_generate_questions_mocked(self, mock_call):
        """Kiểm tra quy trình sinh câu hỏi end-to-end với Mock LLM."""
        mock_call.return_value = json.dumps([
            {
                "question": "Mô hình ngôn ngữ lớn là gì?",
                "options": {"A": "LLM", "B": "SQL", "C": "RAM", "D": "CPU"},
                "correct_answer": "A",
                "difficulty": "easy",
                "explanation": "LLM là Large Language Model.",
                "topic_tag": "Khái niệm AI"
            }
        ])
        questions = self.generator.generate_questions(
            chapter_title="Chương 1",
            chapter_content="LLM là viết tắt của Large Language Model.",
            num_questions=1,
        )
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["correct_answer"], "A")


class TestQuizVerifier(unittest.TestCase):
    """Kiểm thử cho lớp QuizVerifier (quy trình xác thực 3 bước)."""

    def setUp(self):
        self.mock_rag = MagicMock(spec=RAGService)
        self.mock_embedding = MagicMock(spec=EmbeddingService)
        self.verifier = QuizVerifier(
            rag_service=self.mock_rag,
            embedding_service=self.mock_embedding,
            api_key="mock_key",
        )

    def test_fuzzy_verify_high_score(self):
        """Kiểm tra fuzzy verify đạt điểm cao khi chuỗi xuất hiện trong tài liệu."""
        answer = "Retrieval-Augmented Generation"
        source = "Hệ thống sử dụng Retrieval-Augmented Generation (RAG) để sinh câu trả lời chính xác."
        score = self.verifier._fuzzy_verify(answer, source)
        self.assertTrue(score >= 70.0)

    def test_fuzzy_verify_low_score(self):
        """Kiểm tra fuzzy verify điểm thấp khi nội dung hoàn toàn khác biệt."""
        answer = "Công nghệ lượng tử siêu dẫn"
        source = "Python là một ngôn ngữ lập trình thông dịch phổ biến trên toàn thế giới."
        score = self.verifier._fuzzy_verify(answer, source)
        self.assertTrue(score < 70.0)

    def test_verify_single_step2_fuzzy_pass(self):
        """Step 2: Nếu fuzzy matching >= 70%, pass ngay không cần gọi LLM."""
        self.mock_rag.retrieve_context.return_value = [
            {"text": "Mô hình Transformer được giới thiệu năm 2017 bởi nhóm Google Brain.", "score": 0.9}
        ]
        self.mock_rag.format_context_with_sources.return_value = "Google Brain 2017"

        question = {
            "question": "Kiến trúc Transformer ra đời năm nào?",
            "options": {"A": "2015", "B": "2017", "C": "2020", "D": "2023"},
            "correct_answer": "B",
            "explanation": "Năm 2017.",
        }

        with patch.object(self.verifier, "_llm_verify") as mock_llm:
            result = self.verifier._verify_single(question, chapter_id=1, document_id=1)
            self.assertTrue(result["is_verified"])
            mock_llm.assert_not_called()

    def test_verify_single_step3_llm_yes(self):
        """Step 3: Fuzzy < 70%, gọi LLM và LLM trả về YES -> pass."""
        self.mock_rag.retrieve_context.return_value = [
            {"text": "Đoạn văn tóm lược trừu tượng về cơ chế chú ý Attention...", "score": 0.8}
        ]
        self.mock_rag.format_context_with_sources.return_value = "Ngữ cảnh gián tiếp"

        question = {
            "question": "Cơ chế chính của Transformer là gì?",
            "options": {"A": "Self-Attention", "B": "Convolution", "C": "Recurrent", "D": "Pooling"},
            "correct_answer": "A",
            "explanation": "Self-attention.",
        }

        # Mock LLM xác thực thành công
        with patch.object(self.verifier, "_llm_verify") as mock_llm:
            mock_llm.return_value = {
                "verdict": "YES",
                "is_valid": True,
                "correct_answer": "A",
                "explanation": "Cơ chế Self-Attention là cốt lõi của Transformer.",
            }
            result = self.verifier._verify_single(question, chapter_id=1, document_id=1)
            self.assertTrue(result["is_verified"])
            self.assertEqual(result["correct_answer"], "A")
            mock_llm.assert_called_once()

    def test_verify_single_step3_llm_correction(self):
        """Step 3: LLM chỉ ra đáp án hiện tại sai và gợi ý đáp án đúng mới -> sửa đáp án."""
        self.mock_rag.retrieve_context.return_value = [
            {"text": "ChromaDB lưu trữ vector embeddings.", "score": 0.8}
        ]
        self.mock_rag.format_context_with_sources.return_value = "ChromaDB vector embeddings."

        question = {
            "question": "ChromaDB dùng để lưu trữ gì?",
            "options": {"A": "Hình ảnh thô", "B": "Vector embeddings", "C": "Video 4K", "D": "Âm thanh"},
            "correct_answer": "A",  # Đáp án sai ban đầu
            "explanation": "Giải thích sai",
        }

        with patch.object(self.verifier, "_llm_verify") as mock_llm:
            mock_llm.return_value = {
                "verdict": "NO",
                "is_valid": False,
                "correct_answer": "B",  # LLM sửa thành B
                "explanation": "ChromaDB là Vector DB chuyên lưu trữ vector embeddings.",
            }
            result = self.verifier._verify_single(question, chapter_id=1, document_id=1)
            self.assertTrue(result["is_verified"])
            self.assertEqual(result["correct_answer"], "B")  # Đã được sửa thành B
            self.assertIn("ChromaDB là Vector DB", result["explanation"])


class TestQuizService(unittest.TestCase):
    """Kiểm thử cho lớp QuizService với SQLite in-memory database."""

    def setUp(self):
        # Database SQLite in-memory cho test
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.quiz_service = QuizService()

        # Tạo Document & Chapter mẫu
        self.doc = Document(
            filename="test_rag.pdf",
            original_filename="Tài liệu kiểm thử RAG.pdf",
            file_path="/tmp/test_rag.pdf",
            status=DocumentStatus.READY,
            file_type="pdf",
            total_chapters=2,
        )
        self.db.add(self.doc)
        self.db.commit()

        self.ch1 = Chapter(
            document_id=self.doc.id,
            chapter_number=1,
            title="Chương 1: Kiến trúc RAG",
            content="RAG bao gồm thành phần truy xuất dữ liệu từ vector database và thành phần sinh văn bản bằng LLM.",
            level=ChapterLevel.CHAPTER,
            topic_labels={"topics": ["RAG", "LLM"]},
        )
        self.ch2 = Chapter(
            document_id=self.doc.id,
            chapter_number=2,
            title="Chương 2: Đánh giá mô hình",
            content="Đánh giá mô hình RAG cần đo lường độ chính xác truy xuất và tính trung thực của câu trả lời sinh ra.",
            level=ChapterLevel.CHAPTER,
            topic_labels={"topics": ["Evaluation", "Metrics"]},
        )
        self.db.add_all([self.ch1, self.ch2])
        self.db.commit()

        # Tạo Questions mẫu
        self.q1 = Question(
            chapter_id=self.ch1.id,
            question_text="Hai thành phần chính của RAG là gì?",
            options={"A": "Truy xuất và Sinh", "B": "Compiler và Linker", "C": "Frontend và Backend", "D": "RAM và ROM"},
            correct_answer="A",
            difficulty=QuestionDifficulty.EASY,
            explanation="RAG gồm Retrieval và Generation.",
            topic_tag="RAG",
            is_verified=True,
        )
        self.q2 = Question(
            chapter_id=self.ch1.id,
            question_text="Chức năng của Vector Database trong RAG là gì?",
            options={"A": "Render HTML", "B": "Lưu trữ và tìm kiếm vector", "C": "Gửi email", "D": "Nén video"},
            correct_answer="B",
            difficulty=QuestionDifficulty.MEDIUM,
            explanation="Vector DB tìm kiếm chunk tương đồng cosine.",
            topic_tag="Vector DB",
            is_verified=True,
        )
        self.q3 = Question(
            chapter_id=self.ch2.id,
            question_text="Độ trung thực (faithfulness) trong RAG đo lường điều gì?",
            options={"A": "Tốc độ mạng", "B": "Sự phù hợp với tài liệu gốc", "C": "Độ dài câu", "D": "Số trang"},
            correct_answer="B",
            difficulty=QuestionDifficulty.HARD,
            explanation="Faithfulness đo mức độ câu trả lời dựa trên context.",
            topic_tag="Evaluation",
            is_verified=True,
        )
        self.db.add_all([self.q1, self.q2, self.q3])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_start_quiz_by_chapter(self):
        """Bắt đầu phiên quiz theo chapter_ids."""
        resp = self.quiz_service.start_quiz(
            chapter_ids=[self.ch1.id],
            num_questions=5,
            db=self.db,
        )
        self.assertIn("session_id", resp)
        self.assertEqual(resp["total_questions"], 2)  # Chapter 1 có 2 câu
        self.assertEqual(len(resp["questions"]), 2)
        # Kiểm tra câu hỏi KHÔNG để lộ đáp án đúng và giải thích
        first_q = resp["questions"][0]
        self.assertNotIn("correct_answer", first_q)
        self.assertNotIn("explanation", first_q)
        self.assertIn("options", first_q)

    def test_start_quiz_by_topic(self):
        """Bắt đầu phiên quiz theo topic_tags."""
        resp = self.quiz_service.start_quiz(
            topic_tags=["Evaluation"],
            num_questions=5,
            db=self.db,
        )
        self.assertIn("session_id", resp)
        self.assertEqual(resp["total_questions"], 1)
        self.assertEqual(resp["mode"], "topic")

    def test_submit_quiz_scoring(self):
        """Nộp bài và kiểm tra thuật ngữ chấm điểm + ghi log QuizAnswer."""
        start_res = self.quiz_service.start_quiz(
            chapter_ids=[self.ch1.id],
            num_questions=2,
            db=self.db,
        )
        session_id = start_res["session_id"]

        # Nộp 1 câu đúng (q1 chọn A), 1 câu sai (q2 chọn C thay vì B)
        answers = [
            {"question_id": self.q1.id, "answer": "A"},
            {"question_id": self.q2.id, "answer": "C"},
        ]

        result = self.quiz_service.submit_quiz(
            session_id=session_id,
            answers=answers,
            db=self.db,
        )

        self.assertEqual(result["session_id"], session_id)
        self.assertEqual(result["correct_count"], 1)
        self.assertEqual(result["total_questions"], 2)
        self.assertEqual(result["score"], 5.0)  # 1/2 * 10 = 5.0
        self.assertEqual(result["percentage"], 50.0)
        self.assertEqual(len(result["results"]), 2)

        # Kiểm tra chi tiết từng câu trong kết quả
        q1_res = next(r for r in result["results"] if r["question_id"] == self.q1.id)
        self.assertTrue(q1_res["is_correct"])
        self.assertEqual(q1_res["user_answer"], "A")
        self.assertEqual(q1_res["correct_answer"], "A")

        q2_res = next(r for r in result["results"] if r["question_id"] == self.q2.id)
        self.assertFalse(q2_res["is_correct"])
        self.assertEqual(q2_res["user_answer"], "C")
        self.assertEqual(q2_res["correct_answer"], "B")

        # Kiểm tra không cho phép nộp bài lại 2 lần trên cùng 1 session
        with self.assertRaises(Exception):
            self.quiz_service.submit_quiz(session_id=session_id, answers=answers, db=self.db)

    def test_get_explanation_with_rag(self):
        """Lấy giải thích câu hỏi kèm nguồn trích dẫn từ RAG."""
        mock_rag = MagicMock(spec=RAGService)
        mock_rag.retrieve_for_question.return_value = "[Nguồn: Chương 1: Kiến trúc RAG]\nRAG gồm Retrieval và Generation."

        exp = self.quiz_service.get_explanation(
            question_id=self.q1.id,
            db=self.db,
            rag_service=mock_rag,
        )
        self.assertIn("RAG gồm Retrieval và Generation.", exp)
        self.assertIn("=== TÀI LIỆU NGUỒN TRÍCH DẪN ===", exp)

    def test_generate_quiz_for_document(self):
        """Kiểm thử luồng sinh quiz cho toàn bộ tài liệu (loop chapters -> gen -> verify -> save)."""
        mock_gen = MagicMock(spec=QuizGenerator)
        mock_gen.generate_questions.return_value = [
            {
                "question": "Câu hỏi tự động?",
                "options": {"A": "Đúng", "B": "Sai", "C": "Chưa rõ", "D": "Khác"},
                "correct_answer": "A",
                "difficulty": "medium",
                "explanation": "Tự động sinh.",
                "topic_tag": "Auto",
            }
        ]

        mock_ver = MagicMock(spec=QuizVerifier)
        mock_ver.verify_questions.return_value = [
            {
                "question": "Câu hỏi tự động?",
                "options": {"A": "Đúng", "B": "Sai", "C": "Chưa rõ", "D": "Khác"},
                "correct_answer": "A",
                "difficulty": "medium",
                "explanation": "Tự động sinh.",
                "topic_tag": "Auto",
                "is_verified": True,
            }
        ]

        # Trước khi sinh: đã có 3 câu mẫu
        count_before = self.db.query(Question).count()
        self.assertEqual(count_before, 3)

        total_saved = self.quiz_service.generate_quiz_for_document(
            document_id=self.doc.id,
            db=self.db,
            quiz_generator=mock_gen,
            quiz_verifier=mock_ver,
        )

        # 2 chapters * 1 câu = 2 câu mới
        self.assertEqual(total_saved, 2)
        count_after = self.db.query(Question).count()
        self.assertEqual(count_after, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

