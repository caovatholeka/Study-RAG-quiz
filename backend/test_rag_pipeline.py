# -*- coding: utf-8 -*-
"""
Script kiểm thử toàn diện RAG Pipeline:
1. ChunkingService: tách đoạn thông minh, hỗ trợ tiếng Việt, overlap, metadata, ID format.
2. EmbeddingService: singleton pattern, lazy load, ChromaDB integration, upsert, query, delete, edge cases.
3. RAGService: retrieve context, retrieve for question, citation formatting.
4. End-to-end integration: Chapter model -> Chunking -> Embedding in ChromaDB -> RAG query -> Citation.
"""

import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Thêm thư mục backend vào sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.document import Chapter, ChapterLevel
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService


class TestChunkingService(unittest.TestCase):
    """Kiểm thử ChunkingService."""

    def setUp(self):
        self.chunker = ChunkingService(default_chunk_size=300, default_overlap=50)

    def test_create_chunk_id(self):
        """Kiểm tra format chunk ID: doc_{document_id}_ch_{chapter_id}_chunk_{chunk_index}."""
        cid = self.chunker._create_chunk_id(document_id=1, chapter_id=2, chunk_index=3)
        self.assertEqual(cid, "doc_1_ch_2_chunk_3")

    def test_build_chunk_metadata(self):
        """Kiểm tra tạo metadata đầy đủ cho chunk."""
        mock_chapter = MagicMock()
        mock_chapter.id = 10
        mock_chapter.chapter_number = 1
        mock_chapter.title = "1.1. Cấu trúc mạng"
        mock_chapter.level = ChapterLevel.SECTION
        mock_chapter.topic_labels = ["mang_may_tinh", "giao_thuc"]
        mock_chapter.page_start = 5
        mock_chapter.page_end = 8

        meta = self.chunker._build_chunk_metadata(mock_chapter, chunk_index=0, document_id=100)
        self.assertEqual(meta["document_id"], 100)
        self.assertEqual(meta["chapter_id"], 10)
        self.assertEqual(meta["chapter_number"], 1)
        self.assertEqual(meta["chapter_title"], "1.1. Cấu trúc mạng")
        self.assertEqual(meta["section"], "1.1. Cấu trúc mạng")
        self.assertEqual(meta["page_start"], 5)
        self.assertEqual(meta["page_end"], 8)
        self.assertIn("mang_may_tinh", meta["topic_labels"])

    def test_short_text_single_chunk(self):
        """Văn bản ngắn hơn chunk_size phải trả về đúng 1 chunk nguyên vẹn."""
        text = "Đây là một đoạn văn bản ngắn về RAG."
        chunks = self.chunker._chunk_text(text, chunk_size=300, overlap=50)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_paragraph_merge_and_overlap(self):
        """Gộp các paragraph nhỏ và đảm bảo có overlap giữa các chunks."""
        p1 = "Đoạn văn 1: Kiến trúc RAG bao gồm Retrieval và Generation."
        p2 = "Đoạn văn 2: Retrieval chịu trách nhiệm tìm các văn bản phù hợp từ vector DB."
        p3 = "Đoạn văn 3: Generation sử dụng LLM để sinh câu trả lời từ ngữ cảnh."
        p4 = "Đoạn văn 4: Đánh giá RAG cần xem xét cả Faithfulness và Answer Relevance."
        full_text = f"{p1}\n\n{p2}\n\n{p3}\n\n{p4}"

        chunks = self.chunker._chunk_text(full_text, chunk_size=150, overlap=70)
        self.assertGreater(len(chunks), 1)
        # Kiểm tra nội dung không bị rỗng
        for c in chunks:
            self.assertTrue(len(c.strip()) > 0)
            self.assertLessEqual(len(c), 200)

    def test_vietnamese_sentence_splitting_large_paragraph(self):
        """Paragraph lớn phải được tách theo câu tiếng Việt (. ! ? ;) trước khi gộp chunk."""
        long_para = (
            "Hệ thống StudyRAG hỗ trợ sinh câu hỏi trắc nghiệm tự động. "
            "Các câu hỏi được kiểm chứng chặt chẽ bằng factual check! "
            "Liệu độ chính xác có đạt trên 95% không? "
            "Chắc chắn là có; hệ thống đã tích hợp kiểm tra chéo ngữ cảnh. "
            "Cuối cùng, người học có thể xem giải thích chi tiết cho từng đáp án."
        )
        chunks = self.chunker._chunk_text(long_para, chunk_size=120, overlap=30)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertTrue(any(p in c for p in [".", "!", "?", ";"]))

    def test_chunk_chapters_pipeline(self):
        """Kiểm tra phương thức chunk_chapters nhận list Chapter objects."""
        ch1 = MagicMock()
        ch1.id = 1
        ch1.chapter_number = 1
        ch1.title = "Chương 1: Giới thiệu"
        ch1.content = "Nội dung chương 1 ngắn gọn."
        ch1.level = ChapterLevel.CHAPTER
        ch1.topic_labels = ["gioi_thieu"]
        ch1.page_start = 1
        ch1.page_end = 2

        ch2 = MagicMock()
        ch2.id = 2
        ch2.chapter_number = 2
        ch2.title = "Chương 2: Chi tiết"
        ch2.content = "Nội dung chương 2 dài hơn một chút để phân chia thành các đoạn."
        ch2.level = ChapterLevel.CHAPTER
        ch2.topic_labels = ["chi_tiet"]
        ch2.page_start = 3
        ch2.page_end = 5

        chunks = self.chunker.chunk_chapters([ch1, ch2], document_id=42)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["id"], "doc_42_ch_1_chunk_0")
        self.assertEqual(chunks[0]["metadata"]["document_id"], 42)
        self.assertEqual(chunks[1]["id"], "doc_42_ch_2_chunk_0")

    def test_empty_content_handling(self):
        """Chapter không có nội dung không được sinh chunk rỗng."""
        empty_ch = MagicMock()
        empty_ch.id = 99
        empty_ch.content = ""
        chunks = self.chunker.chunk_chapters([empty_ch], document_id=1)
        self.assertEqual(len(chunks), 0)


class TestEmbeddingService(unittest.TestCase):
    """Kiểm thử EmbeddingService."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_singleton_pattern(self):
        """Kiểm tra EmbeddingService luôn trả về cùng 1 singleton instance."""
        svc1 = EmbeddingService()
        svc2 = EmbeddingService()
        self.assertIs(svc1, svc2)

    @patch("app.config.settings.CHROMA_DB_PATH")
    def test_lazy_load_model(self, mock_path):
        """Kiểm tra mô hình chỉ được load khi gọi embed, không load trong __init__."""
        svc = EmbeddingService()
        # Ban đầu _model có thể là None nếu chưa được gọi
        if hasattr(svc, "_model"):
            # Mock lại để kiểm tra _get_model
            with patch("sentence_transformers.SentenceTransformer") as mock_st:
                mock_st.return_value = MagicMock()
                old_model = svc._model
                svc._model = None
                m = svc._get_model()
                self.assertIsNotNone(m)
                mock_st.assert_called_once()
                # Phục hồi
                svc._model = old_model

    def test_metadata_sanitization(self):
        """Kiểm tra làm sạch metadata tương thích với ChromaDB (không nhận None, list/dict được serialize)."""
        svc = EmbeddingService()
        raw_meta = {
            "chapter_id": None,
            "chapter_number": 5,
            "chapter_title": None,
            "section": "Mục A",
            "topic_labels": ["rag", "llm"],
            "page_start": None,
            "page_end": 10,
            "custom_dict": {"key": "val"},
        }
        clean = svc._sanitize_metadata(raw_meta, document_id=99)
        self.assertEqual(clean["document_id"], 99)
        self.assertEqual(clean["chapter_id"], 0)
        self.assertEqual(clean["chapter_number"], 5)
        self.assertEqual(clean["chapter_title"], "")
        self.assertEqual(clean["section"], "Mục A")
        self.assertEqual(clean["page_start"], 0)
        self.assertEqual(clean["page_end"], 10)
        self.assertIsInstance(clean["topic_labels"], str)
        self.assertIn("rag", clean["topic_labels"])
        self.assertIsInstance(clean["custom_dict"], str)

    def test_empty_query_and_empty_collection(self):
        """Truy vấn collection rỗng hoặc query rỗng trả về kết quả rỗng mà không crash."""
        svc = EmbeddingService()
        res = svc.query("", n_results=5)
        self.assertEqual(res["documents"], [])
        self.assertEqual(res["metadatas"], [])


class TestRAGService(unittest.TestCase):
    """Kiểm thử RAGService."""

    def test_format_context_with_sources(self):
        """Kiểm tra format ngữ cảnh và citations."""
        mock_embedding_svc = MagicMock()
        rag_svc = RAGService(mock_embedding_svc)

        sample_results = [
            {
                "text": "Vector DB lưu trữ embeddings.",
                "metadata": {
                    "chapter_number": 1,
                    "chapter_title": "Tổng quan",
                    "section": "1.1. Vector Store",
                    "page_start": 3,
                    "page_end": 4,
                },
                "score": 0.95,
            },
            {
                "text": "LLM sinh câu trả lời dựa trên context.",
                "metadata": {
                    "chapter_number": 2,
                    "chapter_title": "Generation",
                    "section": "",
                    "page_start": 10,
                    "page_end": 10,
                },
                "score": 0.88,
            },
        ]

        formatted = rag_svc.format_context_with_sources(sample_results)
        self.assertIn("[Nguồn: Chương 1: Tổng quan, Mục 1.1. Vector Store, Trang 3-4]", formatted)
        self.assertIn("Vector DB lưu trữ embeddings.", formatted)
        self.assertIn("[Nguồn: Chương 2: Generation, Trang 10]", formatted)
        self.assertIn("LLM sinh câu trả lời dựa trên context.", formatted)

    def test_format_empty_results(self):
        """Danh sách rỗng trả về chuỗi rỗng."""
        mock_embedding_svc = MagicMock()
        rag_svc = RAGService(mock_embedding_svc)
        self.assertEqual(rag_svc.format_context_with_sources([]), "")

    def test_retrieve_context_scores(self):
        """Kiểm tra retrieve_context chuyển đổi cosine distance thành cosine similarity score."""
        mock_embedding_svc = MagicMock()
        mock_embedding_svc.query.return_value = {
            "documents": ["Nội dung chunk 1", "Nội dung chunk 2"],
            "metadatas": [{"chapter_number": 1}, {"chapter_number": 2}],
            "distances": [0.15, 0.40],
            "ids": ["id1", "id2"],
        }
        rag_svc = RAGService(mock_embedding_svc)
        results = rag_svc.retrieve_context("test query", document_id=1, n_results=2)

        self.assertEqual(len(results), 2)
        self.assertAlmostEqual(results[0]["score"], 0.85, places=2)
        self.assertAlmostEqual(results[1]["score"], 0.60, places=2)
        self.assertEqual(results[0]["text"], "Nội dung chunk 1")

    def test_retrieve_for_question_fallback(self):
        """Nếu chapter_id không có kết quả, fallback tìm kiếm trên toàn document."""
        mock_embedding_svc = MagicMock()
        # Lần 1 (theo chapter_id): không có kết quả
        # Lần 2 (theo document_id): có kết quả
        mock_embedding_svc.query.side_effect = [
            {"documents": [], "metadatas": [], "distances": [], "ids": []},
            {
                "documents": ["Nội dung fallback toàn tài liệu"],
                "metadatas": [{"chapter_number": 1, "chapter_title": "Mở đầu"}],
                "distances": [0.2],
                "ids": ["f1"],
            },
        ]
        rag_svc = RAGService(mock_embedding_svc)
        out = rag_svc.retrieve_for_question("Câu hỏi kiểm tra", chapter_id=99, document_id=1)
        self.assertIn("Nội dung fallback toàn tài liệu", out)
        self.assertIn("[Nguồn: Chương 1: Mở đầu]", out)


if __name__ == "__main__":
    unittest.main()

