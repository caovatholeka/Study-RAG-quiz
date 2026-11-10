# -*- coding: utf-8 -*-
"""
Dịch vụ RAG (Retrieval-Augmented Generation) cho StudyRAG.
Truy xuất ngữ cảnh liên quan, định dạng nguồn trích dẫn phục vụ sinh câu hỏi và trả lời.
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class RAGService:
    """
    Dịch vụ RAG điều phối truy xuất ngữ cảnh và định dạng trích dẫn nguồn tài liệu.
    """

    def __init__(self, embedding_service: EmbeddingService) -> None:
        """
        Khởi tạo RAGService với EmbeddingService.

        Args:
            embedding_service: Instance của EmbeddingService.
        """
        self.embedding_service = embedding_service

    def retrieve_context(
        self,
        query: str,
        document_id: int,
        chapter_number: Optional[int] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Truy xuất các chunk ngữ cảnh liên quan nhất từ ChromaDB.

        Args:
            query: Câu hỏi hoặc từ khóa truy vấn.
            document_id: ID tài liệu cần tra cứu.
            chapter_number: Số thứ tự chương (nếu muốn giới hạn trong 1 chương cụ thể).
            n_results: Số lượng kết quả tối đa cần lấy.

        Returns:
            List[Dict[str, Any]]: Danh sách các chunk tìm được, mỗi dict gồm {text, metadata, score}.
        """
        if not query or not query.strip():
            logger.warning("Query rỗng khi gọi retrieve_context.")
            return []

        try:
            if chapter_number is not None:
                raw_results = self.embedding_service.query_by_chapter(
                    query_text=query,
                    chapter_number=chapter_number,
                    document_id=document_id,
                    n_results=n_results,
                )
            else:
                where_filter = {"document_id": int(document_id)}
                raw_results = self.embedding_service.query(
                    query_text=query,
                    n_results=n_results,
                    where=where_filter,
                )

            documents = raw_results.get("documents", [])
            metadatas = raw_results.get("metadatas", [])
            distances = raw_results.get("distances", [])

            retrieved: List[Dict[str, Any]] = []

            for doc_text, meta, dist in zip(documents, metadatas, distances):
                # Cosine distance trong ChromaDB: score tương đồng = 1.0 - distance
                if dist is not None:
                    score = round(max(0.0, min(1.0, 1.0 - float(dist))), 4)
                else:
                    score = 1.0

                retrieved.append({
                    "text": doc_text,
                    "metadata": meta if isinstance(meta, dict) else {},
                    "score": score,
                })

            logger.info(
                f"Truy xuất thành công {len(retrieved)} chunks cho query='{query[:30]}...' "
                f"(doc_id={document_id}, chapter_number={chapter_number})"
            )
            return retrieved

        except Exception as e:
            logger.error(f"Lỗi khi retrieve_context cho doc_id={document_id}: {e}", exc_info=True)
            return []

    def retrieve_for_question(
        self,
        question_text: str,
        chapter_id: int,
        document_id: int,
    ) -> str:
        """
        Lấy ngữ cảnh tài liệu cho một câu hỏi, nối các chunks phù hợp nhất thành 1 chuỗi có kèm trích dẫn nguồn.

        Args:
            question_text: Nội dung câu hỏi.
            chapter_id: ID của chương câu hỏi thuộc về.
            document_id: ID tài liệu.

        Returns:
            str: Chuỗi ngữ cảnh đã định dạng nguồn trích dẫn.
        """
        if not question_text or not question_text.strip():
            logger.warning("question_text rỗng khi gọi retrieve_for_question.")
            return ""

        results: List[Dict[str, Any]] = []

        # 1. Thử lọc theo chapter_id trước
        if chapter_id and chapter_id > 0:
            where_chapter = {
                "$and": [
                    {"document_id": int(document_id)},
                    {"chapter_id": int(chapter_id)},
                ]
            }
            raw = self.embedding_service.query(
                query_text=question_text,
                n_results=5,
                where=where_chapter,
            )
            docs = raw.get("documents", [])
            metas = raw.get("metadatas", [])
            dists = raw.get("distances", [])
            for doc_text, meta, dist in zip(docs, metas, dists):
                score = round(max(0.0, min(1.0, 1.0 - float(dist))), 4) if dist is not None else 1.0
                results.append({"text": doc_text, "metadata": meta or {}, "score": score})

        # 2. Nếu không tìm thấy trong chapter_id hoặc chapter_id = 0, fallback tìm trong cả document
        if not results:
            logger.info(f"Fallback tìm kiếm trên toàn bộ document_id={document_id} cho câu hỏi.")
            results = self.retrieve_context(
                query=question_text,
                document_id=document_id,
                n_results=5,
            )

        return self.format_context_with_sources(results)

    def format_context_with_sources(self, results: List[Dict[str, Any]]) -> str:
        """
        Định dạng danh sách chunks kèm nguồn trích dẫn:
        Ví dụ:
        [Nguồn: Chương X: Tên Chương, Mục Y]
        nội dung chunk...

        Args:
            results: Danh sách các dict chunk {text, metadata, score}.

        Returns:
            str: Chuỗi văn bản ngữ cảnh hoàn chỉnh với nguồn trích dẫn.
        """
        if not results:
            return ""

        formatted_blocks: List[str] = []

        for item in results:
            text = (item.get("text") or "").strip()
            if not text:
                continue

            metadata = item.get("metadata", {})
            chapter_num = metadata.get("chapter_number")
            chapter_title = str(metadata.get("chapter_title") or "").strip()
            section = str(metadata.get("section") or "").strip()

            source_parts: List[str] = []

            # Thông tin chương
            if chapter_num:
                if chapter_title:
                    source_parts.append(f"Chương {chapter_num}: {chapter_title}")
                else:
                    source_parts.append(f"Chương {chapter_num}")
            elif chapter_title:
                source_parts.append(f"Chương: {chapter_title}")

            # Thông tin mục/section
            if section:
                source_parts.append(f"Mục {section}")

            # Thông tin trang
            page_start = metadata.get("page_start")
            page_end = metadata.get("page_end")
            if page_start and page_start > 0:
                if page_end and page_end > page_start:
                    source_parts.append(f"Trang {page_start}-{page_end}")
                else:
                    source_parts.append(f"Trang {page_start}")

            citation = f"[Nguồn: {', '.join(source_parts)}]" if source_parts else "[Nguồn: Tài liệu]"
            formatted_blocks.append(f"{citation}\n{text}")

        return "\n\n---\n\n".join(formatted_blocks)

