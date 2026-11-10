# -*- coding: utf-8 -*-
"""
Cấu hình kết nối database cho StudyRAG.
Sử dụng SQLAlchemy synchronous engine với SQLite.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from typing import Generator

from app.config import settings


# Tạo engine đồng bộ cho SQLite
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Cần thiết cho SQLite
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class cho tất cả các model SQLAlchemy."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection cho database session.
    Tự động đóng session sau khi request hoàn thành.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
