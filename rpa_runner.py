"""
RPA 静默采集编排层（产品演示版）。

真实交付时可把每一步替换为：
- 打开浏览器 / 登录抖店与千川
- 导出报表 CSV
- 解析后交给 cleaner / pipeline

当前为“可演示的静默流程”，保留完整步骤日志，
方便录屏给客户看：到点 → 轮询账号 → 导出 → 计算 → 推送。
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Callable

from mock_accounts import StoreConfig, get_demo_store_configs

logger = logging.getLogger(__name__)


StepCallback = Callable[[str], None]


def _emit(msg: str, on_step: StepCallback | None = None) -> None:
    logger.info(msg)
    if on_step:
        on_step(msg)


def simulate_login_and_export(
    store: StoreConfig,
    dt: date,
    *,
    on_step: StepCallback | None = None,
    delay_sec: float = 0.15,
) -> None:
    """模拟单店铺：登录抖店 + 轮询千川账户 + 导出。"""
    _emit(f"[{store.store_name}] 打开浏览器并进入抖店后台…", on_step)
    time.sleep(delay_sec)
    _emit(f"[{store.store_name}] 校验登录态 / 刷新 Cookie…", on_step)
    time.sleep(delay_sec)
    _emit(f"[{store.store_name}] 导出店铺销售数据（GMV/订单）…", on_step)
    time.sleep(delay_sec)

    for acc in store.qianchuan_accounts:
        _emit(
            f"[{store.store_name}] 切换千川账户 {acc.account_name}（{acc.account_id}）…",
            on_step,
        )
        time.sleep(delay_sec)
        _emit(
            f"[{store.store_name}/{acc.account_name}] 拉取消耗/展现/点击/ROI 并导出…",
            on_step,
        )
        time.sleep(delay_sec)

    _emit(f"[{store.store_name}] 本店数据采集完成 · 日期 {dt.isoformat()}", on_step)


def run_silent_rpa_collect(
    dt: date | None = None,
    *,
    on_step: StepCallback | None = None,
    delay_sec: float = 0.12,
) -> list[StoreConfig]:
    """
    静默执行完整 RPA 采集编排。

    Returns:
        参与采集的店铺配置列表（后续交给 pipeline 做清洗/推送）。
    """
    dt = dt or date.today()
    stores = get_demo_store_configs()
    _emit("=" * 48, on_step)
    _emit(f"RPA 引擎启动 · 目标日期 {dt.isoformat()}", on_step)
    _emit(f"待轮询：{len(stores)} 个抖店 / 多千川账户", on_step)
    _emit("=" * 48, on_step)

    for store in stores:
        simulate_login_and_export(store, dt, on_step=on_step, delay_sec=delay_sec)

    _emit("全部账号采集完成，进入清洗计算与飞书推送…", on_step)
    return stores
