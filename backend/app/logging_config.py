# -*- coding: utf-8 -*-
"""
Cấu hình hệ thống ghi log tập trung (Logging Configuration) cho StudyRAG.
Ghi log đồng thời ra cả Console và File (logs/studyrag.log) với mã hóa UTF-8.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import List

_CURRENT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CURRENT_DIR.parent
_ROOT_DIR = _BACKEND_DIR.parent

# Thư mục chứa log
LOG_DIR = _BACKEND_DIR / "logs"
LOG_FILE = LOG_DIR / "studyrag.log"

LOG_FORMAT = "[%(asctime)s] [%(levelname)-7s] [%(name)s]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging():
    """Khởi tạo và cấu hình logging cho toàn bộ ứng dụng."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 1. File Handler (Ghi vào logs/studyrag.log, xoay vòng tối đa 5 file x 10MB)
    has_file_handler = any(
        isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == str(LOG_FILE)
        for h in root_logger.handlers
    )
    if not has_file_handler:
        file_handler = RotatingFileHandler(
            str(LOG_FILE),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)

    # 2. Console Handler
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in root_logger.handlers
    )
    if not has_stream_handler:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)

    # Đặt mức log cho các thư viện bên thứ 3 để tránh spam log
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.info(f" Hệ thống ghi log đã được khởi tạo. File log: {LOG_FILE}")


def get_recent_logs(lines: int = 100) -> List[str]:
    """Đọc N dòng log gần nhất từ file logs/studyrag.log."""
    if not LOG_FILE.exists():
        return ["Chưa có dữ liệu log. File log sẽ được tạo tự động khi có hoạt động."]

    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return [line.rstrip("\r\n") for line in all_lines[-lines:]]
    except Exception as e:
        return [f"Không thể đọc file log: {e}"]
