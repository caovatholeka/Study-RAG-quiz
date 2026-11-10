# -*- coding: utf-8 -*-
"""
Router cho quản lý chương/mục trong tài liệu.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Chapter, Document
from app.schemas.document import (
    ChapterResponse,
    ChapterListResponse,
    ChapterContentResponse,
)

router = APIRouter(prefix="/api/chapters", tags=["Chapters"])


def _build_chapter_tree(chapters: list, parent_id=None) -> list:
    """Xây dựng cây chương/mục từ danh sách phẳng."""
    tree = []
    for chapter in chapters:
        if chapter.parent_id == parent_id:
            children = _build_chapter_tree(chapters, chapter.id)
            chapter_resp = ChapterResponse.model_validate(chapter)
            chapter_resp.children = children
            tree.append(chapter_resp)
    return tree


@router.get("/document/{document_id}", response_model=ChapterListResponse)
async def list_chapters(document_id: int, db: Session = Depends(get_db)):
    """Lấy danh sách chương của tài liệu (dạng cây phân cấp)."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")

    chapters = (
        db.query(Chapter)
        .filter(Chapter.document_id == document_id)
        .order_by(Chapter.chapter_number)
        .all()
    )

    tree = _build_chapter_tree(chapters)

    return ChapterListResponse(
        document_id=document_id,
        total_chapters=len(chapters),
        chapters=tree,
    )


@router.get("/{chapter_id}", response_model=ChapterContentResponse)
async def get_chapter(chapter_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết chương (bao gồm nội dung)."""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
    return ChapterContentResponse.model_validate(chapter)


@router.get("/{chapter_id}/content")
async def get_chapter_content(chapter_id: int, db: Session = Depends(get_db)):
    """Lấy nội dung chương (chỉ text, dùng để đọc trực tiếp)."""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
    return {
        "chapter_id": chapter.id,
        "title": chapter.title,
        "content": chapter.content or "",
        "chapter_number": chapter.chapter_number,
    }

