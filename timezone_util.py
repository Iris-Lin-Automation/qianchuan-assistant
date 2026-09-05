"""
时区工具：自动识别本机时区，并支持手动选择。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

# 控制台常用时区（置顶），其余可从系统列表补充
PREFERRED_TIMEZONES = [
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Taipei",
    "Asia/Tokyo",
    "Asia/Singapore",
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "Europe/London",
    "Europe/Paris",
    "UTC",
]


def detect_local_timezone() -> str:
    """读取电脑本地时区名称；失败则回退 Asia/Shanghai。"""
    try:
        local = datetime.now().astimezone().tzinfo
        key = getattr(local, "key", None)
        if key:
            return str(key)
        # Windows 有时只有 abbreviation，再尝试 tzlocal 风格
        name = str(local)
        if "/" in name:
            return name
    except Exception:
        pass
    return "Asia/Shanghai"


def list_timezone_choices() -> list[str]:
    """返回下拉可选时区：常用优先 + 本机检测到的时区。"""
    local = detect_local_timezone()
    choices = [local] + [z for z in PREFERRED_TIMEZONES if z != local]
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for z in choices:
        if z not in seen:
            seen.add(z)
            out.append(z)
    return out


def now_in_tz(tz_name: str | None = None) -> datetime:
    """返回指定时区的当前时间。"""
    name = tz_name or detect_local_timezone()
    try:
        return datetime.now(ZoneInfo(name))
    except Exception:
        return datetime.now().astimezone()


def format_now(tz_name: str | None = None) -> str:
    """形如 2026-07-27 20:15:03 (Asia/Shanghai)。"""
    name = tz_name or detect_local_timezone()
    dt = now_in_tz(name)
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({name})"
