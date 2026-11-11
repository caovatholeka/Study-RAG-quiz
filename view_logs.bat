@echo off
chcp 65001 >nul
echo ===================================================================
echo               STUDYRAG - THEO DÕI LOG THỜI GIAN THỰC
echo ===================================================================
echo Đang mở luồng log trực tiếp (Real-time Logs)...
echo Nhấn Ctrl + C để dừng theo dõi log bất kỳ lúc nào.
echo ===================================================================

set LOG_FILE=%~dp0backend\logs\studyrag.log

if not exist "%~dp0backend\logs" (
    mkdir "%~dp0backend\logs"
)

if not exist "%LOG_FILE%" (
    echo [INFO] Đang chờ ứng dụng khởi tạo file log tại: %LOG_FILE%
    echo Khởi tạo luồng log... > "%LOG_FILE%"
)

powershell -NoProfile -Command "Get-Content -Path '%LOG_FILE%' -Wait -Tail 30 -Encoding UTF8"
pause
