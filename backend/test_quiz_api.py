# -*- coding: utf-8 -*-
"""
Kiểm thử tích hợp các endpoint API Quiz của StudyRAG qua FastAPI TestClient.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Thêm thư mục backend vào sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.document import Chapter, ChapterLevel, Document, DocumentStatus
from app.models.quiz import Question, QuestionDifficulty, QuizMode, QuizSession


class TestQuizAPI(unittest.TestCase):
    """Kiểm thử các REST endpoints của Quiz Router."""

    @classmethod
    def setUpClass(cls):
        # Database SQLite in-memory dùng StaticPool để chia sẻ chung 1 in-memory DB giữa các connection
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)

    def setUp(self):
        self.db = self.TestingSessionLocal()

        # Tạo Document mẫu
        self.doc = Document(
            filename="sample.pdf",
            original_filename="Tài liệu API Test.pdf",
            file_path="/tmp/sample.pdf",
            status=DocumentStatus.READY,
            file_type="pdf",
            total_chapters=1,
        )
        self.db.add(self.doc)
        self.db.commit()

        # Tạo Chapter mẫu
        self.chapter = Chapter(
            document_id=self.doc.id,
            chapter_number=1,
            title="Chương 1: API Testing",
            content="FastAPI là một web framework hiện đại, hiệu năng cao cho Python.",
            level=ChapterLevel.CHAPTER,
            topic_labels={"topics": ["FastAPI", "Testing"]},
        )
        self.db.add(self.chapter)
        self.db.commit()

        # Tạo Questions mẫu
        self.q1 = Question(
            chapter_id=self.chapter.id,
            question_text="FastAPI viết bằng ngôn ngữ nào?",
            options={"A": "Java", "B": "Python", "C": "C++", "D": "Go"},
            correct_answer="B",
            difficulty=QuestionDifficulty.EASY,
            explanation="FastAPI là framework viết bằng Python.",
            topic_tag="FastAPI",
            is_verified=True,
        )
        self.q2 = Question(
            chapter_id=self.chapter.id,
            question_text="FastAPI sử dụng Pydantic để làm gì?",
            options={"A": "Render CSS", "B": "Data validation", "C": "Kết nối Wi-Fi", "D": "Nén video"},
            correct_answer="B",
            difficulty=QuestionDifficulty.MEDIUM,
            explanation="Pydantic dùng để xác thực kiểu dữ liệu.",
            topic_tag="Testing",
            is_verified=True,
        )
        self.db.add_all([self.q1, self.q2])
        self.db.commit()

    def tearDown(self):
        self.db.query(Question).delete()
        self.db.query(Chapter).delete()
        self.db.query(Document).delete()
        self.db.commit()
        self.db.close()

    def test_start_quiz_endpoint(self):
        """POST /api/quiz/start"""
        payload = {
            "chapter_ids": [self.chapter.id],
            "num_questions": 2,
            "mode": "chapter",
        }
        res = self.client.post("/api/quiz/start", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertIn("session_id", data)
        self.assertEqual(data["total_questions"], 2)
        self.assertEqual(len(data["questions"]), 2)
        # Đáp án đúng không được trả về trong lúc làm bài
        self.assertNotIn("correct_answer", data["questions"][0])

    def test_submit_quiz_endpoint(self):
        """POST /api/quiz/submit"""
        # 1. Bắt đầu phiên
        start_res = self.client.post("/api/quiz/start", json={
            "chapter_ids": [self.chapter.id],
            "num_questions": 2,
            "mode": "chapter",
        })
        session_id = start_res.json()["session_id"]

        # 2. Nộp bài: q1 đúng (B), q2 sai (A)
        submit_payload = {
            "session_id": session_id,
            "answers": [
                {"question_id": self.q1.id, "answer": "B"},
                {"question_id": self.q2.id, "answer": "A"},
            ]
        }
        submit_res = self.client.post("/api/quiz/submit", json=submit_payload)
        self.assertEqual(submit_res.status_code, 200, submit_res.text)
        data = submit_res.json()
        self.assertEqual(data["session_id"], session_id)
        self.assertEqual(data["correct_count"], 1)
        self.assertEqual(data["total_questions"], 2)
        self.assertEqual(data["score"], 5.0)
        self.assertEqual(data["percentage"], 50.0)
        self.assertEqual(len(data["results"]), 2)

    def test_get_sessions_history_endpoints(self):
        """GET /api/quiz/sessions và GET /api/quiz/sessions/{id}"""
        # Bắt đầu và nộp bài
        start_res = self.client.post("/api/quiz/start", json={
            "chapter_ids": [self.chapter.id],
            "num_questions": 1,
            "mode": "chapter",
        })
        session_id = start_res.json()["session_id"]
        self.client.post("/api/quiz/submit", json={
            "session_id": session_id,
            "answers": [{"question_id": self.q1.id, "answer": "B"}],
        })

        # List sessions
        list_res = self.client.get("/api/quiz/sessions")
        self.assertEqual(list_res.status_code, 200)
        sessions_data = list_res.json()
        self.assertTrue(sessions_data["total"] >= 1)

        # Get session detail
        detail_res = self.client.get(f"/api/quiz/sessions/{session_id}")
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["session_id"], session_id)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_get_explanation_endpoint(self, mock_emb):
        """GET /api/quiz/explanation/{question_id}"""
        res = self.client.get(f"/api/quiz/explanation/{self.q1.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["question_id"], self.q1.id)
        self.assertIn("FastAPI là framework viết bằng Python.", data["explanation"])

    @patch("app.routers.quiz._generate_quiz_background")
    def test_generate_quiz_endpoint(self, mock_bg):
        """POST /api/quiz/generate/{document_id}"""
        res = self.client.post(f"/api/quiz/generate/{self.doc.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["document_id"], self.doc.id)
        self.assertIn("Đang tạo câu hỏi quiz", data["message"])
        mock_bg.assert_called_once_with(self.doc.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
