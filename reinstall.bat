@echo off
cd /d "%~dp0"
echo ===================================================
echo   INVENOVA PI 4 SIMULATION - REINSTALLER
echo ===================================================
echo.
echo [WARNING] This will delete the existing '.venv' and reinstall everything.
echo.
set /p DUMMY=Press ENTER to continue or Ctrl+C to cancel...

if exist ".venv" (
    echo [INFO] Removing existing environment...
    rmdir /s /q .venv
)

echo [INFO] Creating Virtual Environment...
python -m venv .venv

echo [INFO] Activating Environment...
call .venv\Scripts\activate.bat

echo [INFO] Installing Dependencies...
pip install -r requirements_pi.txt

echo.
echo [INFO] Checking Piper TTS...
python download_piper.py

echo.
echo [SUCCESS] Reinstallation Complete.
echo You can now use run.bat to start the assistant.
pause
