# -*- coding: utf-8 -*-
"""
StudyRAG API - Hệ thống hỗ trợ học tập và tra cứu.
Entry point cho ứng dụng FastAPI.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.logging_config import setup_logging, get_recent_logs, LOG_FILE

# Cấu hình file log ngay khi server khởi động
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo resources khi app start, cleanup khi app shutdown."""
    # Startup: tạo tables và thư mục upload
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
    print("✅ Database tables created")
    print(f"✅ Upload directory: {settings.UPLOAD_DIR}")
    yield
    # Shutdown
    print("👋 StudyRAG shutting down...")


app = FastAPI(
    title="StudyRAG API",
    description="Hệ thống hỗ trợ học tập và tra cứu tài liệu với RAG và AI Quiz Generation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - cho phép tất cả origins (development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import và include routers
from app.routers import documents, chapters, quiz  # noqa: E402

app.include_router(documents.router)
app.include_router(chapters.router)
app.include_router(quiz.router)

# Mount static files cho uploads
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/", tags=["Root"])
async def root():
    """Endpoint gốc - thông tin API."""
    return {
        "name": "StudyRAG API",
        "version": "1.0.0",
        "description": "Hệ thống hỗ trợ học tập và tra cứu tài liệu",
        "docs": "/docs",
        "endpoints": {
            "documents": "/api/documents",
            "chapters": "/api/chapters",
            "quiz": "/api/quiz",
            "check_key": "/api/quiz/check-key",
            "logs": "/api/logs",
        },
    }


@app.get("/api/logs", tags=["Logs"])
async def get_logs(lines: int = 100):
    """
    Xem log hệ thống gần nhất theo thời gian thực.
    Hữu ích để theo dõi tiến trình upload tài liệu, chunking, embedding, và sinh câu hỏi.
    """
    recent = get_recent_logs(lines=lines)
    return {
        "log_file": str(LOG_FILE),
        "total_lines": len(recent),
        "logs": recent,
    }

