@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  极简演示：生成样例数据 -> 推送飞书 -> 打开本地看板
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 未找到 .venv，请先双击「一键安装依赖.bat」
  pause
  exit /b 1
)

echo [1/3] 生成样例 Excel（data\today.xlsx）...
".venv\Scripts\python.exe" scripts\make_sample_today_xlsx.py
if errorlevel 1 (
  echo 生成样例失败
  pause
  exit /b 1
)

echo.
echo [2/3] 推送飞书群卡片...
call "影刀调用Python.bat"
if errorlevel 1 (
  echo 推送失败，请检查 Webhook 与网络
  pause
  exit /b 1
)

echo.
echo [3/3] 打开本地可视化看板...
if exist "data\dashboard.html" (
  start "" "data\dashboard.html"
  echo 已打开 data\dashboard.html
) else (
  echo 未找到 dashboard.html，请先执行一次日报流程
)

echo.
echo 完成。现在去飞书群看卡片，或看本地图表。
pause
