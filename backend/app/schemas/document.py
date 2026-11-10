# -*- coding: utf-8 -*-
"""
Pydantic schemas cho tài liệu (Document) và chương (Chapter).
Định nghĩa cấu trúc dữ liệu request/response cho API.
"""

from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict


# ===== Document Schemas =====

class DocumentUploadResponse(BaseModel):
    """Response sau khi upload tài liệu thành công."""
    id: int
    filename: str
    original_filename: str
    status: str
    file_type: str
    message: str

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """Response chi tiết một tài liệu."""
    id: int
    user_id: Optional[str] = None
    filename: str
    original_filename: str
    file_path: str
    status: str
    file_type: str
    total_chapters: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """Response danh sách tài liệu."""
    total: int
    documents: List[DocumentResponse]


# ===== Chapter Schemas =====

class ChapterResponse(BaseModel):
    """Response thông tin chương (không bao gồm nội dung đầy đủ)."""
    id: int
    document_id: int
    chapter_number: int
    title: str
    level: str
    parent_id: Optional[int] = None
    topic_labels: Optional[Any] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    created_at: datetime
    children: List["ChapterResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class ChapterListResponse(BaseModel):
    """Response danh sách chương dạng cây."""
    document_id: int
    total_chapters: int
    chapters: List[ChapterResponse]


class ChapterContentResponse(BaseModel):
    """Response nội dung chi tiết chương."""
    id: int
    document_id: int
    chapter_number: int
    title: str
    content: Optional[str] = None
    level: str
    parent_id: Optional[int] = None
    topic_labels: Optional[Any] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
