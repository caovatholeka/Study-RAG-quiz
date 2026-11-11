# -*- coding: utf-8 -*-
"""
Router cho quản lý tài liệu: upload, list, detail, delete.
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.logging_config import get_recent_logs, LOG_FILE
from app.models.document import Document, DocumentStatus
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# Các định dạng file được hỗ trợ
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def _get_file_extension(filename: str) -> str:
    """Lấy phần mở rộng file (lowercase)."""
    return os.path.splitext(filename)[1].lower()


def _process_document_background(document_id: int):
    """
    Background task xử lý tài liệu sau khi upload.
    Parse → Extract structure → Chunk → Embed → Generate quiz.
    """
    from app.database import SessionLocal
    from app.services.document_processor import DocumentProcessor

    logger.info(f"🚀 [BACKGROUND] Bắt đầu pipeline xử lý tài liệu ID={document_id}...")
    db = SessionLocal()
    try:
        processor = DocumentProcessor()
        processor.process_document(document_id, db)
        logger.info(f"🏁 [BACKGROUND] Hoàn tất pipeline xử lý tài liệu ID={document_id} thành công!")
    except Exception as e:
        logger.error(f"❌ [BACKGROUND] Lỗi khi xử lý tài liệu ID={document_id}: {e}", exc_info=True)
        try:
            db.rollback()
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.ERROR
                db.commit()
        except Exception as rollback_err:
            logger.error(f"❌ [BACKGROUND] Lỗi khi rollback cho tài liệu ID={document_id}: {rollback_err}")
    finally:
        db.close()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload tài liệu học tập (PDF, DOCX, TXT).
    File sẽ được lưu và xử lý trong background.
    """
    logger.info(f"📥 [UPLOAD] Tiếp nhận file upload: '{file.filename}'...")

    # Validate file extension
    ext = _get_file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"⚠️ [UPLOAD] Định dạng file không được hỗ trợ: '{ext}' ({file.filename})")
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file không được hỗ trợ: {ext}. "
                   f"Chỉ chấp nhận: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Tạo tên file unique
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Lưu file
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"💾 [UPLOAD] Đã lưu file vào đĩa: {file_path} ({len(content):,} bytes)")

    # Tạo record trong DB
    document = Document(
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        status=DocumentStatus.PROCESSING,
        file_type=ext.lstrip("."),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info(
        f"✅ [UPLOAD] Đã tạo Document ID={document.id} ('{document.original_filename}'). Chuyển sang xử lý nền..."
    )

    # Trigger background processing
    background_tasks.add_task(_process_document_background, document.id)

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        status=document.status.value,
        file_type=document.file_type,
        message="Tài liệu đã được upload và đang được xử lý.",
    )


@router.get("/logs", tags=["Documents"])
async def get_document_logs(lines: int = 100):
    """Xem log hệ thống gần nhất theo thời gian thực."""
    logs = get_recent_logs(lines=lines)
    return {
        "log_file": str(LOG_FILE),
        "lines_count": len(logs),
        "logs": logs,
    }


@router.get("/", response_model=DocumentListResponse)
async def list_documents(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả tài liệu."""
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return DocumentListResponse(
        total=len(documents),
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết một tài liệu."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=200)
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Xóa tài liệu và toàn bộ dữ liệu liên quan."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")

    # Xóa file vật lý
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    # Xóa vectors trong ChromaDB
    try:
        from app.services.embedding_service import EmbeddingService
        embedding_service = EmbeddingService()
        embedding_service.delete_document(document_id)
    except Exception:
        pass  # ChromaDB có thể chưa được khởi tạo

    # Xóa record (cascade sẽ xóa chapters, questions, etc.)
    db.delete(document)
    db.commit()

    return {"message": "Đã xóa tài liệu thành công.", "document_id": document_id}

