"""
定时任务运行器（进程内挂机版）。

也可用 Windows 任务计划（推荐给小白用户，控制台一键安装）。
本模块适合：云电脑里长期开着一个 Python 进程。
"""

from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline import run_daily, run_monthly, run_weekly

logger = logging.getLogger(__name__)


def start_daily_scheduler(
    *,
    hour: int = 8,
    minute: int = 0,
    dry_run_card: bool = False,
    dry_run_table: bool = True,
) -> None:
    """默认每天 08:00；周一附周报，每月 1 号附月报。"""
    sched = BlockingScheduler()

    def _job() -> None:
        today = date.today()
        run_daily(
            today,
            dry_run_card=dry_run_card,
            dry_run_table=dry_run_table,
            with_rpa=True,
        )
        if today.weekday() == 0:
            run_weekly(today, dry_run_card=dry_run_card, dry_run_table=dry_run_table)
        if today.day == 1:
            run_monthly(today, dry_run_card=dry_run_card, dry_run_table=dry_run_table)

    sched.add_job(
        _job,
        CronTrigger(hour=hour, minute=minute),
        id="daily_feishu_report",
        replace_existing=True,
        max_instances=1,
    )

    logger.info(
        "启动挂机调度：每天 %02d:%02d（dry_run_card=%s）",
        hour,
        minute,
        dry_run_card,
    )
    sched.start()
