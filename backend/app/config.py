# -*- coding: utf-8 -*-
"""
Cấu hình ứng dụng StudyRAG.
Sử dụng pydantic-settings để quản lý cấu hình từ biến môi trường và file .env.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình chính của ứng dụng StudyRAG."""

    # === Database ===
    DATABASE_URL: str = "sqlite:///./study_rag.db"

    # === Google Gemini API ===
    GEMINI_API_KEY: str = ""

    # === ChromaDB ===
    CHROMA_DB_PATH: str = "./chroma_db"

    # === Embedding Model ===
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"

    # === LLM Model ===
    LLM_MODEL: str = "gemini-2.0-flash"

    # === Upload ===
    UPLOAD_DIR: str = "./uploads"

    # === Quiz ===
    MAX_QUESTIONS_PER_CHAPTER: int = 15

    # === Chunking ===
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Singleton instance
settings = Settings()
