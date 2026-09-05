"""
静默定时任务入口（给 Windows 任务计划程序调用）。

默认每天 08:00：RPA 采集 → 清洗计算 → 飞书入库预览 → 推送日报卡片。
周一额外推送周报；每月 1 号额外推送月报。
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# 保证从任意工作目录启动都能导入项目模块
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import config
from pipeline import run_daily, run_monthly, run_weekly

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _setup_logging() -> None:
    log_file = LOG_DIR / f"worker_{date.today().isoformat()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="千川/抖店自动化静默任务")
    p.add_argument(
        "--mode",
        choices=["auto", "daily", "weekly", "monthly"],
        default="auto",
        help="auto=日报(+周一周报/+月初月报)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="仅演练，不真实推送飞书",
    )
    return p.parse_args()


def main() -> int:
    _setup_logging()
    logger = logging.getLogger("worker")
    args = parse_args()

    dry = args.dry_run or config.DEBUG_MODE
    today = date.today()
    logger.info("静默任务启动 mode=%s dry_run=%s date=%s", args.mode, dry, today)

    if not dry:
        config.validate()

    if args.mode in ("auto", "daily"):
        run_daily(today, dry_run_card=dry, dry_run_table=True, with_rpa=True)

    if args.mode == "weekly" or (args.mode == "auto" and today.weekday() == 0):
        run_weekly(today, dry_run_card=dry, dry_run_table=True)

    if args.mode == "monthly" or (args.mode == "auto" and today.day == 1):
        run_monthly(today, dry_run_card=dry, dry_run_table=True)

    logger.info("静默任务完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logging.getLogger("worker").exception("静默任务失败：%s", exc)
        sys.exit(1)
