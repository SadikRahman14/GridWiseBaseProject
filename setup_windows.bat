@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3.12 -m venv .venv
if not errorlevel 1 goto install
py -3 -m venv .venv
if not errorlevel 1 goto install
:usepython
python -m venv .venv
if errorlevel 1 goto failed
:install
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed
if not exist .env copy /y .env.example .env >nul
echo.
echo Setup complete. Run demo_windows.bat for the offline optimizer demo.
echo For the full API: configure Ollama or a hosted model, then run start_windows.bat.
pause
exit /b 0
:failed
echo.
echo Setup failed. Install 64-bit Python 3.12, check internet access, and try again.
pause
exit /b 1
