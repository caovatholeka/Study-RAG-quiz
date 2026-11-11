# -*- coding: utf-8 -*-
"""
Service điều phối pipeline xử lý tài liệu (DocumentProcessor).
Quy trình: Lấy DB -> Parse -> Trích xuất cấu trúc -> Lưu Chapters vào DB -> Chunking/Embedding -> Hoàn tất.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.document import Chapter, ChapterLevel, Document, DocumentStatus
from app.services.document_parser import DocumentParser
from app.services.structure_extractor import ChapterNode, StructureExtractor

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Điều phối toàn bộ quy trình xử lý tài liệu học tập từ khi upload tới khi sẵn sàng tra cứu RAG.
    """

    def __init__(
        self,
        parser: Optional[DocumentParser] = None,
        extractor: Optional[StructureExtractor] = None,
    ):
        self.parser = parser or DocumentParser()
        self.extractor = extractor or StructureExtractor()

    def process_document(self, document_id: int, db: Session) -> Document:
        """
        Pipeline chính xử lý tài liệu:
        1. Lấy Document từ DB bằng document_id
        2. Cập nhật status = PROCESSING
        3. Parse tài liệu (PDF/DOCX/TXT) thành ParsedDocument
        4. Trích xuất cây cấu trúc chương/mục (ChapterNode)
        5. Xóa chapter cũ (nếu có) và lưu cây chapter mới vào DB
        6. Gọi ChunkingService và EmbeddingService để vector hóa (nếu có)
        7. Cập nhật status = READY, total_chapters = count
        8. Nếu có lỗi -> cập nhật status = ERROR

        Args:
            document_id: ID của tài liệu trong DB.
            db: SQLAlchemy Session.

        Returns:
            Document đã được cập nhật trạng thái.
        """
        logger.info(f"Bắt đầu pipeline xử lý tài liệu ID: {document_id}")

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Không tìm thấy tài liệu với ID {document_id}")
            raise ValueError(f"Không tìm thấy tài liệu với ID {document_id}")

        try:
            # 1. Cập nhật trạng thái đang xử lý
            document.status = DocumentStatus.PROCESSING
            db.commit()
            db.refresh(document)

            # 2. Parse file theo định dạng
            logger.info(f"📄 [1/4 PARSER] Bắt đầu đọc file: {document.file_path} (loại: {document.file_type})")
            parsed_doc = self.parser.parse(document.file_path, document.file_type)
            page_info = f"{parsed_doc.metadata.get('total_pages', 1)} trang" if document.file_type == 'pdf' else 'file văn bản'
            total_extracted_text = sum(len(b.text.strip()) for b in parsed_doc.blocks)
            logger.info(
                f"📄 [1/4 PARSER] Hoàn tất trích xuất: {len(parsed_doc.blocks)} khối văn bản ({total_extracted_text:,} ký tự) từ {page_info}."
            )

            if not parsed_doc.blocks or total_extracted_text == 0:
                err_msg = (
                    f"Tài liệu '{document.original_filename}' không chứa lớp văn bản điện tử nào (0 ký tự từ {page_info}). "
                    "Đây là file PDF scan / chụp ảnh hoàn toàn. Vui lòng sử dụng file PDF có text layer (bôi đen chữ được) "
                    "hoặc chuyển đổi OCR thành file Word/PDF trước khi tải lên."
                )
                logger.error(f"❌ [1/4 PARSER] {err_msg}")
                raise ValueError(err_msg)

            # 3. Trích xuất cấu trúc cây chương/mục
            logger.info("🌳 [2/4 STRUCTURE] Phân tích cấu trúc tiêu đề, chương, phần, mục...")
            chapter_tree = self.extractor.extract(parsed_doc)

            # 4. Xóa chapter cũ trước khi lưu mới (tránh trùng lặp khi re-process)
            existing_chapters = db.query(Chapter).filter(Chapter.document_id == document_id).all()
            if existing_chapters:
                logger.info(f"🌳 [2/4 STRUCTURE] Xóa {len(existing_chapters)} chapter cũ của tài liệu {document_id}")
                db.query(Chapter).filter(Chapter.document_id == document_id).delete()
                db.flush()

            # 5. Lưu cây chapter vào DB
            saved_count = self._save_chapters(document_id, chapter_tree, db, parent_id=None)
            logger.info(f"🌳 [2/4 STRUCTURE] Đã lưu thành công {saved_count} chương/mục vào cơ sở dữ liệu.")

            # 6. Gọi ChunkingService và EmbeddingService để vector hóa (nếu có)
            try:
                from app.services.chunking_service import ChunkingService
                from app.services.embedding_service import EmbeddingService

                logger.info("🧩 [3/4 VECTOR/RAG] Đang cắt nhỏ văn bản (Chunking) & tạo Vector Embeddings...")
                chunking_service = ChunkingService()
                embedding_service = EmbeddingService()

                # Tương thích linh hoạt với interface của các service
                chunks = None
                if hasattr(chunking_service, "process_document"):
                    chunks = chunking_service.process_document(document_id, db)
                elif hasattr(chunking_service, "chunk_document"):
                    chunks = chunking_service.chunk_document(document_id, db)

                if hasattr(embedding_service, "process_chunks") and chunks:
                    embedding_service.process_chunks(chunks)
                elif hasattr(embedding_service, "embed_document"):
                    embedding_service.embed_document(document_id, db)

                chunk_count = len(chunks) if chunks else "N/A"
                logger.info(f"🧩 [3/4 VECTOR/RAG] Hoàn tất: Đã lưu {chunk_count} chunks vào ChromaDB.")
            except (ImportError, ModuleNotFoundError) as ie:
                logger.warning(f"ChunkingService hoặc EmbeddingService chưa tồn tại hoặc chưa cài đặt đầy đủ: {ie}")
            except Exception as ve:
                logger.warning(f"Lỗi trong quá trình vector hóa tài liệu {document_id}: {ve}", exc_info=True)

            # 7. Cập nhật trạng thái READY và tổng số chương
            document.status = DocumentStatus.READY
            document.total_chapters = saved_count
            db.commit()
            db.refresh(document)
            logger.info(
                f"🎉 [4/4 READY] Xử lý tài liệu ID={document_id} ('{document.original_filename}') THÀNH CÔNG 100%! "
                f"Status: READY, Tổng số chương/mục: {saved_count}."
            )
            return document

        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi xử lý tài liệu ID {document_id}: {e}", exc_info=True)
            try:
                db.rollback()
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = DocumentStatus.ERROR
                    db.commit()
            except Exception as rollback_err:
                logger.error(f"Lỗi khi rollback hoặc cập nhật trạng thái ERROR: {rollback_err}")
            raise e

    def _save_chapters(
        self,
        document_id: int,
        chapters: List[ChapterNode],
        db: Session,
        parent_id: Optional[int] = None,
    ) -> int:
        """
        Đệ quy lưu cây ChapterNode vào DB, tạo đối tượng Chapter cho mỗi node,
        và thiết lập quan hệ parent_id cho các node con.

        Args:
            document_id: ID tài liệu sở hữu.
            chapters: Danh sách các ChapterNode ở cấp hiện tại.
            db: Database session.
            parent_id: ID của chapter cha (None nếu là root level).

        Returns:
            Tổng số chapter/section/subsection đã được lưu.
        """
        level_map = {
            "chapter": ChapterLevel.CHAPTER,
            "section": ChapterLevel.SECTION,
            "subsection": ChapterLevel.SUBSECTION,
        }

        total_saved = 0

        for node in chapters:
            level_enum = level_map.get(node.level.lower(), ChapterLevel.CHAPTER)

            chapter = Chapter(
                document_id=document_id,
                chapter_number=node.number,
                title=node.title,
                content=node.content or "",
                level=level_enum,
                parent_id=parent_id,
                topic_labels={"topics": node.topic_labels, "labels": node.topic_labels},
                page_start=node.page_start,
                page_end=node.page_end,
            )
            db.add(chapter)
            db.flush()  # Flush để sinh ra chapter.id ngay lập tức cho các node con

            total_saved += 1

            if node.children:
                total_saved += self._save_chapters(
                    document_id=document_id,
                    chapters=node.children,
                    db=db,
                    parent_id=chapter.id,
                )

        return total_saved

