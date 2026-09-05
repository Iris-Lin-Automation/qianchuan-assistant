@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app_gui.py
) else (
  python app_gui.py
)

if errorlevel 1 (
  echo.
  echo 启动失败。请先双击「一键安装依赖.bat」
  pause
)
