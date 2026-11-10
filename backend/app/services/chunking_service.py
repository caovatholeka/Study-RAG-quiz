# -*- coding: utf-8 -*-
"""
Dịch vụ phân đoạn văn bản (ChunkingService) cho StudyRAG.
Hỗ trợ chia đoạn thông minh theo cấu trúc chương mục, đoạn văn, câu tiếng Việt và đảm bảo overlap.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class ChunkingService:
    """
    Dịch vụ chia nhỏ tài liệu và chương mục thành các chunk văn bản tối ưu cho truy xuất RAG.
    """

    def __init__(
        self,
        default_chunk_size: Optional[int] = None,
        default_overlap: Optional[int] = None,
    ) -> None:
        self.chunk_size = default_chunk_size or getattr(settings, "CHUNK_SIZE", 1000)
        self.overlap = default_overlap or getattr(settings, "CHUNK_OVERLAP", 100)
        # Regex tách câu hỗ trợ tiếng Việt: dấu . ! ? ; kết thúc câu
        self._sentence_split_regex = re.compile(r'(?<=[.!?;\n])\s+')

    def chunk_chapters(self, chapters: List[Any], document_id: int) -> List[Dict[str, Any]]:
        """
        Nhận danh sách Chapter model objects, chia nhỏ nội dung từng chapter và trả về
        danh sách chunk dicts sẵn sàng embed.

        Mỗi chunk dict có cấu trúc:
            {
                "id": str,
                "text": str,
                "metadata": dict
            }

        Args:
            chapters: Danh sách các đối tượng Chapter.
            document_id: ID của tài liệu.

        Returns:
            List[Dict[str, Any]]: Danh sách các chunk.
        """
        all_chunks: List[Dict[str, Any]] = []

        if not chapters:
            logger.warning(f"Không có chapter nào để chunk cho document_id={document_id}")
            return all_chunks

        logger.info(f"Bắt đầu chunk {len(chapters)} chapters cho document_id={document_id}")

        for chapter in chapters:
            chapter_content = getattr(chapter, "content", "") or ""
            chapter_id = getattr(chapter, "id", 0) or 0

            if not chapter_content.strip():
                continue

            text_chunks = self._chunk_text(
                text=chapter_content,
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )

            for chunk_idx, chunk_text in enumerate(text_chunks):
                chunk_id = self._create_chunk_id(document_id, chapter_id, chunk_idx)
                metadata = self._build_chunk_metadata(chapter, chunk_idx, document_id)

                all_chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": metadata,
                })

        logger.info(f"Đã tạo tổng cộng {len(all_chunks)} chunks cho document_id={document_id}")
        return all_chunks

    def chunk_document(self, document_id: int, db: Any) -> List[Dict[str, Any]]:
        """
        Phương thức hỗ trợ liên kết với DocumentProcessor để chunk tài liệu từ database session.

        Args:
            document_id: ID của tài liệu.
            db: SQLAlchemy Session.

        Returns:
            List[Dict[str, Any]]: Danh sách các chunk của tài liệu.
        """
        from app.models.document import Chapter

        chapters = (
            db.query(Chapter)
            .filter(Chapter.document_id == document_id)
            .order_by(Chapter.id.asc())
            .all()
        )
        return self.chunk_chapters(chapters, document_id)

    def _create_chunk_id(self, document_id: int, chapter_id: int, chunk_index: int) -> str:
        """
        Tạo định danh duy nhất cho chunk theo định dạng chuẩn: doc_{document_id}_ch_{chapter_id}_chunk_{chunk_index}.

        Args:
            document_id: ID tài liệu.
            chapter_id: ID chương.
            chunk_index: Chỉ số chunk trong chương.

        Returns:
            str: Định danh chunk.
        """
        return f"doc_{document_id}_ch_{chapter_id}_chunk_{chunk_index}"

    def _build_chunk_metadata(self, chapter: Any, chunk_index: int, document_id: int) -> Dict[str, Any]:
        """
        Xây dựng metadata cho một chunk từ đối tượng Chapter.

        Args:
            chapter: Đối tượng Chapter.
            chunk_index: Chỉ số chunk trong chương.
            document_id: ID tài liệu.

        Returns:
            Dict[str, Any]: Dict metadata chuẩn cho ChromaDB.
        """
        # Xác định section
        level = getattr(chapter, "level", None)
        level_val = getattr(level, "value", str(level)) if level else "chapter"
        section_name = ""
        if level_val in ("section", "subsection"):
            section_name = getattr(chapter, "title", "") or ""

        # Xử lý topic_labels
        raw_topics = getattr(chapter, "topic_labels", None)
        if isinstance(raw_topics, (dict, list)):
            topic_str = json.dumps(raw_topics, ensure_ascii=False)
        elif raw_topics is not None:
            topic_str = str(raw_topics)
        else:
            topic_str = ""

        return {
            "document_id": int(document_id),
            "chapter_id": int(getattr(chapter, "id", 0) or 0),
            "chapter_number": int(getattr(chapter, "chapter_number", 0) or 0),
            "chapter_title": str(getattr(chapter, "title", "") or ""),
            "section": section_name,
            "topic_labels": topic_str,
            "page_start": int(getattr(chapter, "page_start", 0) or 0),
            "page_end": int(getattr(chapter, "page_end", 0) or 0),
            "chunk_index": int(chunk_index),
        }

    def _split_into_atomic_segments(self, text: str, max_size: int) -> List[str]:
        """
        Chia text thành các đơn vị phân đoạn cơ bản:
        1. Tách theo paragraphs (double newline)
        2. Nếu paragraph vượt quá max_size -> tách tiếp theo câu (hỗ trợ tiếng Việt: . ! ? ;)
        3. Nếu một câu vẫn vượt quá max_size -> tách tiếp theo từ.

        Args:
            text: Nội dung văn bản cần chia.
            max_size: Kích thước tối đa của mỗi đơn vị.

        Returns:
            List[str]: Danh sách các phân đoạn cơ bản.
        """
        # Chuẩn hóa ngắt dòng
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        # 1. Tách theo paragraphs
        raw_paragraphs = [p.strip() for p in re.split(r'\n\s*\n+', normalized) if p.strip()]
        if not raw_paragraphs:
            return []

        segments: List[str] = []

        for para in raw_paragraphs:
            if len(para) <= max_size:
                segments.append(para)
            else:
                # 3. Tách paragraph lớn theo câu
                raw_sentences = [
                    s.strip() for s in self._sentence_split_regex.split(para) if s.strip()
                ]
                for s in raw_sentences:
                    if len(s) <= max_size:
                        segments.append(s)
                    else:
                        # Fallback nếu 1 câu quá dài (không có dấu câu): tách theo từ
                        words = s.split()
                        curr_words: List[str] = []
                        curr_len = 0
                        for w in words:
                            w_len = len(w)
                            if curr_len + w_len + 1 > max_size and curr_words:
                                segments.append(" ".join(curr_words))
                                curr_words = [w]
                                curr_len = w_len
                            else:
                                curr_words.append(w)
                                curr_len += (w_len + 1) if curr_len > 0 else w_len
                        if curr_words:
                            segments.append(" ".join(curr_words))

        return segments

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 100,
    ) -> List[str]:
        """
        Chia text thông minh:
        1. Split theo paragraphs (double newline)
        2. Merge paragraphs nhỏ lại đến khi đạt chunk_size
        3. Split paragraphs lớn theo sentences (regex hỗ trợ tiếng Việt: . ! ? ;)
        4. Đảm bảo overlap giữa các chunks.

        Args:
            text: Chuỗi văn bản cần phân đoạn.
            chunk_size: Kích thước tối đa mỗi chunk (mặc định 1000).
            overlap: Độ dài gối đầu giữa 2 chunk liên tiếp (mặc định 100).

        Returns:
            List[str]: Danh sách các chunk văn bản.
        """
        if not text or not text.strip():
            return []

        clean_text = text.strip()
        if len(clean_text) <= chunk_size:
            return [clean_text]

        segments = self._split_into_atomic_segments(clean_text, chunk_size)
        if not segments:
            return []

        chunks: List[str] = []
        n = len(segments)
        i = 0

        while i < n:
            curr_segments = [segments[i]]
            curr_len = len(segments[i])
            j = i + 1

            # Gộp các segments cho tới khi đạt chunk_size
            while j < n:
                next_seg = segments[j]
                # Sử dụng phân tách "\n\n" giữa các phân đoạn
                added_len = len(next_seg) + 2
                if curr_len + added_len <= chunk_size:
                    curr_segments.append(next_seg)
                    curr_len += added_len
                    j += 1
                else:
                    break

            chunk_text = "\n\n".join(curr_segments).strip()
            if chunk_text:
                chunks.append(chunk_text)

            # Đã duyệt hết tất cả phân đoạn
            if j >= n:
                break

            # Tính toán overlap: lấy các segments cuối của chunk hiện tại sao cho tổng độ dài <= overlap
            overlap_accum_len = 0
            overlap_count = 0
            for seg in reversed(curr_segments):
                seg_cost = len(seg) + 2
                if overlap_accum_len + seg_cost <= overlap:
                    overlap_accum_len += seg_cost
                    overlap_count += 1
                else:
                    break

            # Đảm bảo i luôn tiến lên ít nhất 1 bước để không lặp vô hạn
            if 0 < overlap_count < len(curr_segments):
                i = j - overlap_count
            else:
                i = j

        return chunks
