@echo off
cd /d "%~dp0"

echo ===================================================
echo   Setup Forge-Integrated (Pi 4 Simulation)
echo ===================================================

if not exist ".venv" (
    echo [INFO] Creating Virtual Environment...
    python -m venv .venv
)

echo [INFO] Activating Environment...
call .venv\Scripts\activate.bat

echo [INFO] Installing Dependencies...
pip install -r requirements_pi.txt

echo.
echo [INFO] Download Piper TTS (Windows)...
python download_piper.py

echo.
echo [INFO] Download Lite LLM (TinyLlama)...
python download_llm_lite.py


echo.
echo Setup Complete.
pause
