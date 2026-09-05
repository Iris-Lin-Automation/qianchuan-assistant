@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在安装运行环境，请稍候...
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo 未检测到 Python。请先安装 Python 3.10 或以上，并勾选 Add python.exe to PATH。
  pause
  exit /b 1
)

REM 若旧的虚拟环境坏了（没有 pip），删掉重建
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pip -V 1>nul 2>nul
  if errorlevel 1 (
    echo 检测到运行环境不完整，正在重建...
    rmdir /s /q ".venv" 2>nul
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo 创建专用运行环境...
  python -m venv .venv
  if errorlevel 1 (
    echo 创建失败。请改用官网 python.org 安装的 Python 3.10+ 再试。
    pause
    exit /b 1
  )
)

REM 有些 Python/conda 生成的 venv 没有 pip，先补上
".venv\Scripts\python.exe" -m pip -V 1>nul 2>nul
if errorlevel 1 (
  echo 正在补全 pip...
  ".venv\Scripts\python.exe" -m ensurepip --upgrade
  if errorlevel 1 (
    echo ensurepip 失败，尝试用系统 Python 安装 pip 到环境...
    python -m pip install --upgrade pip
    python -m pip install virtualenv
    python -m virtualenv --clear .venv
  )
)

".venv\Scripts\python.exe" -m pip -V 1>nul 2>nul
if errorlevel 1 (
  echo 仍无法使用 pip。
  echo 请卸载当前异常 Python，从 https://www.python.org/downloads/ 安装 3.11，
  echo 安装时勾选 Add python.exe to PATH，然后重新打开本目录再点本脚本。
  pause
  exit /b 1
)

echo 安装软件依赖到本软件专用环境...
".venv\Scripts\python.exe" -m pip install -U pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo 依赖安装失败。请检查网络后重试。
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "import pandas, openpyxl, requests, dotenv" 1>nul 2>nul
if errorlevel 1 (
  echo 依赖校验未通过。请把本窗口全文截图发回。
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" copy ".env.example" ".env" >nul
)

echo.
echo 安装完成！请双击「启动控制台.bat」
pause
