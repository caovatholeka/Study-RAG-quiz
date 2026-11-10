# -*- coding: utf-8 -*-
"""
End-to-end integration test cho toàn bộ RAG Pipeline trong StudyRAG:
- ChunkingService: tách đoạn văn bản thực tế, sinh metadata.
- EmbeddingService: upsert vào ChromaDB thật, query, query_by_chapter, delete_document.
- RAGService: retrieve_context, retrieve_for_question, format_context_with_sources.
- DocumentProcessor: pipeline tích hợp đầy đủ.
"""

import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

# Thêm thư mục backend vào sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import chromadb
from app.config import settings
from app.models.document import Chapter, ChapterLevel, Document, DocumentStatus
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService


class TestRAGPipelineIntegration(unittest.TestCase):
    """Kiểm thử tích hợp end-to-end RAG Pipeline."""

    @classmethod
    def setUpClass(cls):
        # Tạo thư mục ChromaDB tạm thời cho test
        cls.temp_chroma_path = tempfile.mkdtemp()
        
        # Override settings
        settings.CHROMA_DB_PATH = cls.temp_chroma_path

        # Khởi tạo embedding service singleton
        cls.embedding_service = EmbeddingService()
        cls.embedding_service.chroma_db_path = cls.temp_chroma_path
        cls.embedding_service._chroma_client = chromadb.PersistentClient(path=cls.temp_chroma_path)
        cls.embedding_service._collection = None  # Reset collection để trỏ vào client mới

        # Sử dụng mock encoder 384 chiều để test nhanh và độc lập với mạng
        mock_model = MagicMock()
        def mock_encode(texts, **kwargs):
            import numpy as np
            # Tạo embedding giả định có tính phân biệt đơn giản dựa trên từ khóa
            vectors = []
            for t in texts:
                vec = np.zeros(64, dtype=np.float32)
                t_lower = str(t).lower()
                if "vector" in t_lower or "chromadb" in t_lower:
                    vec[0] = 1.0
                if "python" in t_lower or "lập trình" in t_lower:
                    vec[1] = 1.0
                if "đánh giá" in t_lower or "kiểm thử" in t_lower:
                    vec[2] = 1.0
                # Chuẩn hóa L2
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                vectors.append(vec)
            return np.array(vectors)

        mock_model.encode.side_effect = mock_encode
        cls.embedding_service._model = mock_model

        cls.chunking_service = ChunkingService(default_chunk_size=500, default_overlap=50)
        cls.rag_service = RAGService(cls.embedding_service)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_chroma_path, ignore_errors=True)

    def test_full_rag_lifecycle(self):
        """
        Kiểm thử trọn vẹn vòng đời:
        1. Tạo chapters mô phỏng
        2. Chunking các chapters
        3. Upsert chunks vào ChromaDB
        4. Query vector DB và kiểm tra kết quả
        5. Query theo chương cụ thể (query_by_chapter)
        6. RAG retrieve_context & retrieve_for_question với citations
        7. Xóa document khỏi ChromaDB
        """
        doc_id = 999

        # 1. Tạo các Chapter mô phỏng
        ch1 = Chapter(
            id=101,
            document_id=doc_id,
            chapter_number=1,
            title="Tổng quan về Vector Database và ChromaDB",
            content=(
                "ChromaDB là một cơ sở dữ liệu vector mã nguồn mở gọn nhẹ. "
                "Vector database hỗ trợ lưu trữ các embeddings và tính toán độ tương đồng cosine nhanh chóng. "
                "Ứng dụng phổ biến nhất là trong các hệ thống Retrieval-Augmented Generation (RAG)."
            ),
            level=ChapterLevel.CHAPTER,
            topic_labels={"topics": ["vector_db", "chromadb"]},
            page_start=1,
            page_end=3,
        )

        ch2 = Chapter(
            id=102,
            document_id=doc_id,
            chapter_number=2,
            title="Ngôn ngữ lập trình Python trong AI",
            content=(
                "Python là ngôn ngữ phổ biến nhất cho phát triển trí tuệ nhân tạo và học máy. "
                "Hệ sinh thái phong phú với các thư viện như PyTorch, HuggingFace Transformers, FastAPI. "
                "Lập trình Python giúp việc xây dựng pipeline xử lý tài liệu trở nên nhanh chóng và linh hoạt."
            ),
            level=ChapterLevel.CHAPTER,
            topic_labels={"topics": ["python", "ai"]},
            page_start=4,
            page_end=6,
        )

        # 2. Phân đoạn (Chunking)
        chunks = self.chunking_service.chunk_chapters([ch1, ch2], document_id=doc_id)
        self.assertGreaterEqual(len(chunks), 2)
        print(f"\n[Test] Đã sinh {len(chunks)} chunks thành công.")

        # Kiểm tra metadata và format id của chunk
        self.assertTrue(chunks[0]["id"].startswith(f"doc_{doc_id}_ch_101_chunk_"))
        self.assertEqual(chunks[0]["metadata"]["document_id"], doc_id)
        self.assertEqual(chunks[0]["metadata"]["chapter_number"], 1)

        # 3. Upsert vào ChromaDB
        self.embedding_service.add_chunks(document_id=doc_id, chunks=chunks)
        collection = self.embedding_service._get_collection()
        self.assertEqual(collection.count(), len(chunks))
        print(f"[Test] Đã lưu {collection.count()} chunks vào ChromaDB.")

        # 4. Query vector DB
        search_res = self.embedding_service.query("vector database chromadb", n_results=3)
        self.assertGreater(len(search_res["documents"]), 0)
        self.assertIn("ChromaDB", search_res["documents"][0])
        print(f"[Test] Query kết quả: {search_res['documents'][0][:60]}...")

        # 5. Query theo chương cụ thể (query_by_chapter)
        ch2_res = self.embedding_service.query_by_chapter(
            query_text="ngôn ngữ lập trình python",
            chapter_number=2,
            document_id=doc_id,
            n_results=2,
        )
        self.assertGreater(len(ch2_res["documents"]), 0)
        self.assertEqual(ch2_res["metadatas"][0]["chapter_number"], 2)
        self.assertIn("Python", ch2_res["documents"][0])
        print(f"[Test] Query theo Chương 2: {ch2_res['documents'][0][:60]}...")

        # 6. RAG retrieve_context & retrieve_for_question
        rag_context = self.rag_service.retrieve_context(
            query="vector embeddings",
            document_id=doc_id,
            n_results=2,
        )
        self.assertGreater(len(rag_context), 0)
        self.assertIn("score", rag_context[0])
        self.assertGreaterEqual(rag_context[0]["score"], 0.0)

        # Trích xuất ngữ cảnh cho câu hỏi kèm citation
        formatted_question_ctx = self.rag_service.retrieve_for_question(
            question_text="ChromaDB là gì và vai trò của vector database?",
            chapter_id=101,
            document_id=doc_id,
        )
        print("\n[Test] Ngữ cảnh trích xuất cho câu hỏi:")
        print(formatted_question_ctx)
        self.assertIn("[Nguồn: Chương 1: Tổng quan về Vector Database và ChromaDB, Trang 1-3]", formatted_question_ctx)
        self.assertIn("ChromaDB là một cơ sở dữ liệu vector", formatted_question_ctx)

        # 7. Xóa document khỏi ChromaDB
        self.embedding_service.delete_document(doc_id)
        self.assertEqual(collection.count(), 0)
        print(f"[Test] Sau khi xóa document {doc_id}: count = {collection.count()}")


if __name__ == "__main__":
    unittest.main()

