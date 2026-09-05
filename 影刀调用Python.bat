@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "data\today.xlsx" (
  if exist "data\qianchuan_today.xlsx" (
    copy /Y "data\qianchuan_today.xlsx" "data\today.xlsx" >nul
  ) else (
    echo 未找到 data\today.xlsx
    echo 请确认影刀已将报表保存到这个位置。
    exit /b 2
  )
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py --file .\data\today.xlsx
) else (
  python main.py --file .\data\today.xlsx
)

exit /b %ERRORLEVEL%
