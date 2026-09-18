@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe scripts\check_samples.py --mode offline
if errorlevel 1 goto done
.venv\Scripts\python.exe scripts\demo.py
:done
pause
