@echo off
chcp 65001 >nul
echo ===================================================
echo   Kiểm tra API Key (OpenAI / Gemini) cho StudyRAG
echo ===================================================
cd /d "%~dp0backend"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
python test_gemini_key.py %*
pause
