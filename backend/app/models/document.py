# -*- coding: utf-8 -*-
"""
SQLAlchemy models cho tài liệu (Document) và chương (Chapter).
"""

import enum
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Text, Enum, DateTime, ForeignKey, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentStatus(str, enum.Enum):
    """Trạng thái xử lý tài liệu."""
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class ChapterLevel(str, enum.Enum):
    """Cấp độ của chương/mục."""
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"


class Document(Base):
    """Model cho tài liệu được upload."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.PROCESSING, nullable=False
    )
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    total_chapters: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Quan hệ với Chapter
    chapters: Mapped[List["Chapter"]] = relationship(
        "Chapter", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.original_filename}', status='{self.status}')>"


class Chapter(Base):
    """Model cho chương/mục trong tài liệu."""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    level: Mapped[ChapterLevel] = mapped_column(
        Enum(ChapterLevel), default=ChapterLevel.CHAPTER, nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    topic_labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Quan hệ
    document: Mapped["Document"] = relationship("Document", back_populates="chapters")
    parent: Mapped[Optional["Chapter"]] = relationship(
        "Chapter", remote_side="Chapter.id", backref="children"
    )

    def __repr__(self) -> str:
        return f"<Chapter(id={self.id}, title='{self.title}', level='{self.level}')>"
