@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" worker_job.py --mode daily
) else (
  python worker_job.py --mode daily
)
echo.
pause
