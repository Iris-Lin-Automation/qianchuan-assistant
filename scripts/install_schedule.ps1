# 千川飞书自动化 · 安装 Windows 定时任务
param(
    [int]$Hour = 8,
    [int]$Minute = 0,
    [string]$PythonPath,
    [string]$WorkerPath
)

$ErrorActionPreference = "Stop"
$TaskName = "QianchuanFeishuDailyReport"

if (-not (Test-Path $PythonPath)) {
    throw "找不到 Python：$PythonPath"
}
if (-not (Test-Path $WorkerPath)) {
    throw "找不到 worker：$WorkerPath"
}

$WorkDir = Split-Path -Parent $WorkerPath
$Arg = "`"$WorkerPath`" --mode auto"
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $Arg -WorkingDirectory $WorkDir
$Trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($Hour).AddMinutes($Minute).ToString("HH:mm"))
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null

Write-Output "OK: 已安装定时任务 [$TaskName]，每天 ${Hour}:$($Minute.ToString('00')) 自动执行。"
Write-Output "提示：请保持电脑开机，或放到云电脑挂机。"
