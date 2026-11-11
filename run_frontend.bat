@echo off
chcp 65001 >nul
echo ===================================================
echo   Khởi động StudyRAG Frontend (Vite - Port 5173)
echo ===================================================
cd /d "%~dp0frontend"
call npm run dev
pause
