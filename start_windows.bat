@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8000/docs in your browser. Press Ctrl+C to stop.
.venv\Scripts\python.exe run.py
pause
