"""
主运行入口（影刀 RPA 闭环友好）。

影刀流程最后一步推荐：
  python main.py --file ./data/today.xlsx

也可：
  python main.py --file ./data/qianchuan_today.xlsx
  python main.py --mode daily   # 无 Excel 时走模拟数据（演示用）
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from config import config
from pipeline import run_daily, run_from_excel, run_weekly
from scheduler_runner import start_daily_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("main")

ROOT = Path(__file__).resolve().parent
DEFAULT_EXCEL_CANDIDATES = [
    ROOT / "data" / "today.xlsx",
    ROOT / "data" / "qianchuan_today.xlsx",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="千川/抖店 × 飞书自动化")
    p.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="影刀导出的 Excel 路径，如 ./data/today.xlsx",
    )
    p.add_argument(
        "--mode",
        type=str,
        default="auto",
        choices=["auto", "demo", "daily", "weekly", "schedule"],
        help="auto=有Excel则读Excel，否则演示；daily/weekly=模拟链路",
    )
    p.add_argument("--date", type=str, default=None, help="报告日期 YYYY-MM-DD")
    p.add_argument("--week-end", type=str, default=None, help="周报结束日期")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="演练：不真实推送飞书卡片",
    )
    p.add_argument(
        "--dry-run-card",
        action="store_true",
        default=None,
        help=argparse.SUPPRESS,
    )
    p.add_argument(
        "--no-dry-run-card",
        dest="force_send",
        action="store_true",
        help="强制真实推送（默认：--file 模式真实推送，演示模式不推送）",
    )
    return p.parse_args()


def _resolve_excel(path: str | None) -> Path | None:
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        return p
    for cand in DEFAULT_EXCEL_CANDIDATES:
        if cand.exists():
            return cand
    return None


def run() -> int:
    args = parse_args()
    excel = _resolve_excel(args.file)
    report_date = date.fromisoformat(args.date) if args.date else None

    # 推送策略：
    # - 显式 --dry-run => 不推送
    # - --file / 自动发现 Excel => 默认真实推送（影刀无人值守）
    # - demo/daily 模拟 => 默认不推送，除非 --no-dry-run-card
    if args.dry_run:
        dry_run_card = True
    elif args.force_send:
        dry_run_card = False
    elif excel is not None and args.mode in ("auto", "daily"):
        dry_run_card = False
    elif args.mode in ("demo", "daily", "weekly") and args.file is None:
        dry_run_card = True if args.dry_run_card is None else bool(args.dry_run_card)
    else:
        dry_run_card = config.DEBUG_MODE

    if not dry_run_card:
        config.validate()

    dry_run_table = not config.bitable_api_ready()

    if args.mode == "schedule":
        start_daily_scheduler(dry_run_card=dry_run_card, dry_run_table=dry_run_table)
        return 0

    # 影刀主路径：读 Excel
    if excel is not None and args.mode in ("auto", "daily"):
        if not excel.exists():
            raise FileNotFoundError(
                f"影刀导出文件不存在：{excel}\n"
                "请确认影刀已将 Excel 另存为 data/today.xlsx"
            )
        logger.info("==== 影刀 Excel 日报：%s ====", excel)
        run_from_excel(
            str(excel),
            dry_run_card=dry_run_card,
            dry_run_table=dry_run_table,
            report_date=report_date,
        )
        logger.info("完成：已计算 ROI 并触发飞书推送")
        return 0

    # 无 Excel：演示/兼容旧入口
    run_dt = report_date or date.today()
    if args.mode in ("auto", "demo", "daily"):
        logger.info("==== 模拟日报（无 Excel）：%s ====", run_dt.isoformat())
        run_daily(
            run_dt,
            dry_run_card=dry_run_card,
            dry_run_table=dry_run_table,
            with_rpa=True,
        )

    if args.mode in ("demo", "weekly"):
        week_end = run_dt if args.week_end is None else date.fromisoformat(args.week_end)
        logger.info("==== 模拟周报：%s ====", week_end.isoformat())
        run_weekly(week_end, dry_run_card=dry_run_card, dry_run_table=dry_run_table)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        logger.error("运行失败：%s", exc)
        sys.exit(1)
