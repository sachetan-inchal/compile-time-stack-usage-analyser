@echo off
title Stack Analyzer Dashboard
cd /d "C:\Users\rishi\Desktop\CD EL\compile-time-stack-usage-analyser"

echo ======================================================
echo    Starting Stack Analyzer Frontend Dashboard
echo ======================================================
echo.
echo [1/2] Opening dashboard in your default browser...
start http://localhost:3000

echo [2/2] Starting local web server on port 3000...
echo (Press Ctrl+C in this window to stop the server)
echo.
python server.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Python not found in Windows path. Trying fallback...
    py server.py
)

pause
