@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  一键体验：样例数据 -^> 推送到飞书群 -^> 打开看板
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [提示] 尚未安装运行环境，正在自动安装依赖...
  call "一键安装依赖.bat"
  if not exist ".venv\Scripts\python.exe" (
    echo 安装失败。请确认已安装 Python 3.10+，再重试。
    pause
    exit /b 1
  )
)

echo [0/3] 检查样例所需组件...
".venv\Scripts\python.exe" -c "import pandas, openpyxl" 1>nul 2>nul
if errorlevel 1 (
  echo 正在向本软件环境安装 pandas / openpyxl ...
  ".venv\Scripts\python.exe" -m pip install "pandas>=2.0.0,<3.0.0" "openpyxl>=3.1.0,<4.0.0"
  if errorlevel 1 (
    echo 安装失败。请先双击「一键安装依赖.bat」
    pause
    exit /b 1
  )
)

echo [1/3] 准备样例数据...
".venv\Scripts\python.exe" scripts\make_sample_today_xlsx.py
if errorlevel 1 (
  echo 准备失败。请再双击「一键安装依赖.bat」后重试。
  pause
  exit /b 1
)

echo.
echo [2/3] 推送到飞书群...
call "影刀调用Python.bat"
if errorlevel 1 (
  echo 推送失败：请先打开「启动控制台.bat」填写飞书群机器人地址并保存。
  pause
  exit /b 1
)

echo.
echo [3/3] 打开经营看板...
if exist "data\dashboard.html" (
  start "" "data\dashboard.html"
) else (
  echo 看板稍后可在控制台打开
)

echo.
echo 完成。请到飞书群查看日报卡片。
pause
