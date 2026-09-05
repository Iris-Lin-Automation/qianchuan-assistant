# 打可直接卖给客户的交付包（极简、无开发者内容）
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\scripts\pack_customer.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $Root "release"
$Stamp = Get-Date -Format "yyyyMMdd"
$ZipName = "千川飞书自动化_客户交付包_$Stamp.zip"
$ZipPath = Join-Path $OutDir $ZipName

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$temp = Join-Path $env:TEMP ("qianchuan_customer_" + $Stamp)
if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
$productRoot = Join-Path $temp "千川经营助手"
New-Item -ItemType Directory -Force -Path $productRoot | Out-Null

function Copy-One($rel) {
  $src = Join-Path $Root $rel
  if (-not (Test-Path $src)) { Write-Warning "缺少: $rel"; return }
  $dst = Join-Path $productRoot $rel
  $parent = Split-Path $dst -Parent
  if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  Copy-Item $src $dst -Recurse -Force
}

# ---- 核心程序 ----
$pyFiles = @(
  "main.py", "app_gui.py", "pipeline.py", "config.py", "excel_loader.py",
  "feishu_card.py", "feishu_table.py", "feishu_bitable.py", "cleaner.py",
  "collectors.py", "data_analyzer.py", "report_templates.py", "storage.py",
  "worker_job.py", "scheduler_runner.py", "rpa_runner.py", "mock_accounts.py",
  "demo_simulator.py", "timezone_util.py", "requirements.txt"
)
foreach ($f in $pyFiles) { Copy-One $f }

# ---- 客户入口按钮 ----
$bats = @(
  "一键安装依赖.bat",
  "启动控制台.bat",
  "影刀调用Python.bat",
  "立即推送日报.bat",
  "一键体验演示.bat"
)
# 若尚无「一键体验演示」，后面会生成
foreach ($f in $bats) {
  if (Test-Path (Join-Path $Root $f)) { Copy-One $f }
}

# ---- 脚本（仅定时 + 样例）----
New-Item -ItemType Directory -Force -Path (Join-Path $productRoot "scripts") | Out-Null
Copy-One "scripts\install_schedule.ps1"
Copy-One "scripts\uninstall_schedule.ps1"
Copy-One "scripts\make_sample_today_xlsx.py"

# ---- 数据目录模板 ----
$dataDir = Join-Path $productRoot "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
# 只放样板说明，不带你本机历史日志/密钥数据
"请将影刀导出的报表保存为 today.xlsx" | Set-Content -Encoding UTF8 (Join-Path $dataDir "请把导出文件放这里.txt")

# ---- 客户文档（只保留会用得到的、无开发者话术）----
$docsDir = Join-Path $productRoot "使用说明"
New-Item -ItemType Directory -Force -Path $docsDir | Out-Null
Copy-Item (Join-Path $Root "docs\客户使用手册.md") (Join-Path $docsDir "使用手册.md") -Force
Copy-Item (Join-Path $Root "docs\客户影刀对接说明.md") (Join-Path $docsDir "影刀对接说明.md") -Force

# ---- 空白配置模板（绝不打包你的真实 webhook）----
$envExample = @"
# 千川经营助手配置（请用「启动控制台」填写，一般不用手改）
FEISHU_WEBHOOK_URL=
FEISHU_BITABLE_URL=
DEBUG_MODE=false
SCHEDULE_HOUR=8
SCHEDULE_MINUTE=0
REPORT_TITLE_PREFIX=千川经营日报
ALERT_THRESHOLD_PERCENT=20
"@
$envExample | Set-Content -Encoding UTF8 (Join-Path $productRoot ".env.example")

# ---- 开箱说明 ----
$startTxt = @"
【千川经营助手 · 开箱即用】

第 1 步：双击「一键安装依赖.bat」（首次需要）
第 2 步：双击「启动控制台.bat」
第 3 步：填写飞书群机器人地址 → 保存配置
第 4 步：双击「一键体验演示.bat」看效果（可选）

日常使用：
· 影刀每天导出 Excel 保存为 data\today.xlsx
· 影刀最后一步调用「影刀调用Python.bat」
· 或在控制台点「立即推送日报 / 开启每日定时」

可视化：
· 控制台点「打开经营看板」即可（本地图表）

需要帮助：请查看「使用说明」文件夹
"@
$startTxt | Set-Content -Encoding UTF8 (Join-Path $productRoot "00_请先阅读.txt")

# ---- 体验演示 bat（客户向文案，UTF-8 BOM 防乱码）----
$demoBat = @'
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
'@
$utf8bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText((Join-Path $productRoot "一键体验演示.bat"), $demoBat, $utf8bom)

# 覆盖客户向 bat，并加 BOM
$installSrc = Join-Path $Root "一键安装依赖.bat"
if (Test-Path $installSrc) {
  $t = [System.IO.File]::ReadAllText($installSrc)
  [System.IO.File]::WriteAllText((Join-Path $productRoot "一键安装依赖.bat"), $t, $utf8bom)
}

# ---- 干净版 影刀 / 立即推送 文案覆盖（去掉开发字样）----
$yingdaoBat = @'
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
'@
$yingdaoBat | Set-Content -Encoding ASCII (Join-Path $productRoot "影刀调用Python.bat")

$pushBat = @'
@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" worker_job.py --mode daily
) else (
  python worker_job.py --mode daily
)
echo.
echo 推送已结束，请到飞书群查看。
pause
'@
$pushBat | Set-Content -Encoding ASCII (Join-Path $productRoot "立即推送日报.bat")

# 清掉可能复制进来的 __pycache__
Get-ChildItem $productRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $temp\* -DestinationPath $ZipPath -Force
Remove-Item $temp -Recurse -Force

Write-Output "OK: $ZipPath"
