@echo off
chcp 65001 >nul
echo ===================================================
echo   Khởi động StudyRAG Backend (FastAPI - Port 8000)
echo ===================================================
cd /d "%~dp0backend"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
python -m uvicorn app.main:app --reload --port 8000
pause
