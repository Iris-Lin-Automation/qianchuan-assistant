"""
演示回放脚本：用模拟数据生成“日报/周报”并走完整链路。

适合你录视频给客户看：你可以把卡片 JSON/推送日志直接录下来，
再展示“数据已写入本地/预览飞书表格”的证据。
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from pipeline import run_daily, run_weekly

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("demo")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--backfill-days", type=int, default=5, help="回放最近 N 天日报")
    p.add_argument("--dry-run-card", action="store_true", default=True, help="仅打印/不真实推送飞书卡片")
    p.add_argument("--no-dry-run-card", dest="dry_run_card", action="store_false", help="真实推送飞书卡片（需 DEBUG_MODE=false）")
    p.add_argument("--dry-run-table", action="store_true", default=True, help="仅生成飞书表格预览文件")
    p.add_argument("--send-weekly", action="store_true", help="额外推送一次周报（默认推送本周末）")
    p.add_argument("--week-end", type=str, default=None, help="周报结束日期，例如 2026-07-26")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    today = date.today()
    start_day = today - timedelta(days=args.backfill_days - 1)
    logger.info("Demo：回放日报 %s ~ %s", start_day.isoformat(), today.isoformat())

    for i in range(args.backfill_days):
        dt = start_day + timedelta(days=i)
        logger.info("==== 推送日报：%s ====", dt.isoformat())
        run_daily(dt, dry_run_card=args.dry_run_card, dry_run_table=args.dry_run_table)

    if args.send_weekly:
        week_end = date.fromisoformat(args.week_end) if args.week_end else today
        logger.info("==== 推送周报：%s ====", week_end.isoformat())
        run_weekly(week_end, dry_run_card=args.dry_run_card, dry_run_table=args.dry_run_table)

    logger.info("Demo 完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logger.error("Demo 运行失败：%s", exc)
        sys.exit(1)

