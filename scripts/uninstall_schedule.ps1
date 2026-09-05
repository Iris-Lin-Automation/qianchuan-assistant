# 卸载千川飞书自动化定时任务
$ErrorActionPreference = "Continue"
$TaskName = "QianchuanFeishuDailyReport"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $existing) {
    Write-Output "未找到定时任务 [$TaskName]，无需卸载。"
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Output "OK: 已卸载定时任务 [$TaskName]。"
