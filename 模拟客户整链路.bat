@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo  客户交付演示：影刀抓数 → Excel → Python → 飞书群推送
echo ========================================================
echo.
echo  说明：
echo  - 影刀「真登录抖店/千川」需在影刀软件里配（本机无法替你点网页）
echo  - 本脚本用「步骤日志 + 样例 Excel」模拟影刀已导出完成
echo  - 然后走与客户相同的：影刀调用Python.bat → 真实推群卡片
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 未找到 .venv，请先运行 一键安装依赖.bat
  pause
  exit /b 1
)

echo -------- [1/3] 模拟影刀：打开浏览器 / 登录抖店 / 导出报表 --------
REM 注意：bat 中 % 需要写成 %%，否则会被 cmd 当作环境变量展开
".venv\Scripts\python.exe" -c "import logging; logging.basicConfig(level=logging.INFO, format='%%(message)s'); from datetime import date; from rpa_runner import run_silent_rpa_collect; run_silent_rpa_collect(date.today(), delay_sec=0.25)"
if errorlevel 1 (
  echo RPA 模拟失败
  pause
  exit /b 1
)

echo.
echo -------- [2/3] 模拟影刀：把导出文件另存为 data\today.xlsx --------
".venv\Scripts\python.exe" scripts\make_sample_today_xlsx.py
if errorlevel 1 (
  echo 生成样例 Excel 失败
  pause
  exit /b 1
)

echo.
echo -------- [3/3] 影刀最后一步：调用 Python 推飞书（真实推送）--------
call "影刀调用Python.bat"
set ERR=%ERRORLEVEL%

echo.
if %ERR%==0 (
  echo ========================================================
  echo  完成。请到飞书群看今日经营卡片。
  echo  本地看板：data\dashboard.html
  echo ========================================================
) else (
  echo 推送失败，错误码 %ERR%
)
echo.
pause
exit /b %ERR%
