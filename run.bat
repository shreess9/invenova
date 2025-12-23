@echo off
cd /d "%~dp0"
echo ===================================================
echo   INVENOVA PI 4 SIMULATION - LAUNCHER
echo ===================================================

if not exist ".venv" (
    echo [ERROR] Virtual Environment not found. Please run reinstall.bat first.
    pause
    exit /b
)

echo Activating Environment...
call .venv\Scripts\activate.bat

echo Starting Assistant (Lite Mode)...
python -u mini_assistant.py

echo.
pause
