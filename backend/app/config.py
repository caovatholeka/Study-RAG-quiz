# -*- coding: utf-8 -*-
"""
Cấu hình ứng dụng StudyRAG.
Sử dụng pydantic-settings để quản lý cấu hình từ biến môi trường và file .env.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CURRENT_DIR = Path(__file__).resolve().parent  # app/
_BACKEND_DIR = _CURRENT_DIR.parent              # backend/
_ROOT_DIR = _BACKEND_DIR.parent                 # Study-RAG-quiz/


def _find_env_file() -> str:
    """Tìm file .env trong các thư mục tiềm năng (backend, root, current workdir)."""
    for candidate in [
        _BACKEND_DIR / ".env",
        _ROOT_DIR / ".env",
        Path.cwd() / ".env",
        _CURRENT_DIR / ".env",
    ]:
        if candidate.is_file():
            return str(candidate)
    return str(_BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """Cấu hình chính của ứng dụng StudyRAG."""

    # === Database ===
    DATABASE_URL: str = "sqlite:///./study_rag.db"

    # === LLM Provider & Keys ===
    LLM_PROVIDER: str = "auto"  # "auto", "openai", "gemini"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"

    # === ChromaDB ===
    CHROMA_DB_PATH: str = "./chroma_db"

    # === Embedding Model ===
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"

    # === Upload ===
    UPLOAD_DIR: str = "./uploads"

    # === Quiz ===
    MAX_QUESTIONS_PER_CHAPTER: int = 15

    # === Chunking ===
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100

    @model_validator(mode="after")
    def sync_api_keys(self) -> "Settings":
        """
        Đồng bộ và làm sạch API keys cho OpenAI và Google Gemini.
        Tự động nhận diện provider dựa theo tiền tố key (sk- -> openai, AIza/AQ -> gemini).
        """
        # Làm sạch OpenAI API Key
        openai_key = (
            self.OPENAI_API_KEY
            or os.environ.get("OPENAI_API_KEY", "")
        )
        if openai_key:
            self.OPENAI_API_KEY = str(openai_key).strip().strip('"').strip("'")

        # Làm sạch Gemini API Key
        gemini_key = (
            self.GEMINI_API_KEY
            or self.GOOGLE_API_KEY
            or os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        )
        if gemini_key:
            clean_gemini = str(gemini_key).strip().strip('"').strip("'")
            # Nếu người dùng vô tình dán key OpenAI (bắt đầu bằng sk-) vào GEMINI_API_KEY
            if clean_gemini.startswith("sk-") and not self.OPENAI_API_KEY:
                self.OPENAI_API_KEY = clean_gemini
                self.GEMINI_API_KEY = ""
                self.GOOGLE_API_KEY = ""
            else:
                self.GEMINI_API_KEY = clean_gemini
                self.GOOGLE_API_KEY = clean_gemini

        # Tự động xác định LLM_PROVIDER nếu là "auto"
        provider = str(self.LLM_PROVIDER).strip().lower()
        if provider == "auto" or not provider:
            if self.OPENAI_API_KEY:
                self.LLM_PROVIDER = "openai"
            elif self.GEMINI_API_KEY:
                self.LLM_PROVIDER = "gemini"
            else:
                self.LLM_PROVIDER = "auto"
        else:
            self.LLM_PROVIDER = provider

        # Chuẩn hóa DATABASE_URL nếu dùng SQLite đường dẫn tương đối để luôn trỏ về backend/
        if self.DATABASE_URL.startswith("sqlite:///./"):
            rel_name = self.DATABASE_URL.replace("sqlite:///./", "")
            abs_db_path = (_BACKEND_DIR / rel_name).resolve()
            self.DATABASE_URL = f"sqlite:///{abs_db_path.as_posix()}"

        return self

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton instance
settings = Settings()
