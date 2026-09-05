"""
全局配置模块。

使用 python-dotenv 从项目根目录的 .env 文件读取配置项，
并提供统一的访问入口与基础校验。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    """应用配置集合。"""

    FEISHU_WEBHOOK_URL: str = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    FEISHU_BITABLE_URL: str = os.getenv("FEISHU_BITABLE_URL", "").strip()

    # 飞书开放平台应用（写入多维表格）
    FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "").strip()
    FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "").strip()
    FEISHU_BITABLE_APP_TOKEN: str = os.getenv("FEISHU_BITABLE_APP_TOKEN", "").strip()
    FEISHU_BITABLE_TABLE_ID: str = os.getenv("FEISHU_BITABLE_TABLE_ID", "").strip()

    REPORT_TITLE_PREFIX: str = os.getenv(
        "REPORT_TITLE_PREFIX", "千川/抖店数据日报"
    ).strip()
    ALERT_THRESHOLD_PERCENT: float = _get_float("ALERT_THRESHOLD_PERCENT", 20.0)
    DEBUG_MODE: bool = _get_bool("DEBUG_MODE", False)

    # 定时任务时区与时间（默认读取本机时区，由控制台写入）
    SCHEDULE_TIMEZONE: str = os.getenv("SCHEDULE_TIMEZONE", "").strip()
    SCHEDULE_HOUR: int = _get_int("SCHEDULE_HOUR", 8)
    SCHEDULE_MINUTE: int = _get_int("SCHEDULE_MINUTE", 0)

    @classmethod
    def validate(cls) -> None:
        if not cls.DEBUG_MODE and not cls.FEISHU_WEBHOOK_URL:
            raise ValueError(
                "缺少 FEISHU_WEBHOOK_URL。"
                "请复制 .env.example 为 .env 并填写飞书 Webhook 地址，"
                "或将 DEBUG_MODE 设为 true 进行本地调试。"
            )

    @classmethod
    def bitable_api_ready(cls) -> bool:
        return bool(
            cls.FEISHU_APP_ID
            and cls.FEISHU_APP_SECRET
            and cls.FEISHU_BITABLE_APP_TOKEN
            and cls.FEISHU_BITABLE_TABLE_ID
        )


config = Config()
