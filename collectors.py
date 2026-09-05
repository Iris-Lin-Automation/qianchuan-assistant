"""
多账号采集（演示版）。

真实场景里这里会：
- 处理账号登录态（cookie / token / 刷新）
- 调用千川/抖店 API 或抓取中台接口
- 拉取维度：店铺 / 计划 / 推广单元 / 日期

在你当前“没有真实权限/数据”的情况下，这里用确定性随机数模拟：
消耗、展现、点击、订单、GMV 等指标，并保持趋势一致，方便你录制视频演示工作流。
"""

from __future__ import annotations

import math
import random
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from mock_accounts import AccountConfig, StoreConfig

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class PlanDayMetrics:
    plan_id: str
    plan_name: str
    spend: float
    impressions: int
    clicks: int
    orders: int
    gmv: float

    @property
    def roi(self) -> float:
        return self.gmv / self.spend if self.spend > 0 else 0.0


@dataclass(frozen=True)
class AccountDayRaw:
    account: AccountConfig
    plans: list[PlanDayMetrics]

    @property
    def spend(self) -> float:
        return sum(p.spend for p in self.plans)

    @property
    def impressions(self) -> int:
        return sum(p.impressions for p in self.plans)

    @property
    def clicks(self) -> int:
        return sum(p.clicks for p in self.plans)

    @property
    def orders(self) -> int:
        return sum(p.orders for p in self.plans)

    @property
    def gmv(self) -> float:
        return sum(p.gmv for p in self.plans)


@dataclass(frozen=True)
class StoreDayRaw:
    store: StoreConfig
    qc_accounts: list[AccountDayRaw]
    other_channel_spend: float
    other_channel_gmv: float
    other_channel_orders: int

    @property
    def qc_spend(self) -> float:
        return sum(a.spend for a in self.qc_accounts)

    @property
    def qc_impressions(self) -> int:
        return sum(a.impressions for a in self.qc_accounts)

    @property
    def qc_clicks(self) -> int:
        return sum(a.clicks for a in self.qc_accounts)

    @property
    def qc_orders(self) -> int:
        return sum(a.orders for a in self.qc_accounts)

    @property
    def qc_gmv(self) -> float:
        return sum(a.gmv for a in self.qc_accounts)

    @property
    def total_spend(self) -> float:
        return self.qc_spend + self.other_channel_spend

    @property
    def paid_share(self) -> float:
        return self.qc_spend / self.total_spend if self.total_spend > 0 else 0.0


def _seed_for(store_id: str, account_id: str, dt: date) -> int:
    # 保证“同一天同账号 -> 同一组模拟数据”，方便你录视频复现。
    return hash((store_id, account_id, dt.isoformat())) & 0xFFFFFFFF


def _trend_multiplier(dt: date) -> float:
    # 用简单周期 + 小幅漂移模拟运营波动（每月/每周节奏有感）。
    t = dt.toordinal()
    cycle = 30
    wobble = math.sin(2 * math.pi * (t % cycle) / cycle)
    weekly = math.sin(2 * math.pi * (t % 7) / 7)
    return 1.0 + 0.08 * wobble + 0.03 * weekly


def _generate_plan_metrics(
    *,
    rng: random.Random,
    store_goal_roi: float,
    plan_weight: float,
    plan_quality: float,
    dt: date,
    plan_index: int,
) -> PlanDayMetrics:
    # 计划花费（与计划权重 + 周期趋势相关）
    trend = _trend_multiplier(dt)
    base_spend_unit = rng.uniform(6500, 14000) * trend
    spend = max(50.0, base_spend_unit * plan_weight)

    # 基于“目标 ROI”反推转化率，确保结果更贴近真实业务
    cpm = rng.uniform(2.5, 6.0)  # 每千次展示成本
    ctr = rng.uniform(0.015, 0.05)  # 点击率
    session_rate = rng.uniform(0.35, 0.65)  # 点击 -> 进店
    aov = rng.uniform(85, 160)  # 客单价

    roi_target = max(0.6, store_goal_roi * plan_quality * trend)
    cv_rate = (roi_target * cpm) / (1000.0 * ctr * session_rate * aov)
    # 防止极端情况
    cv_rate = min(max(cv_rate, 0.002), 0.04)

    impressions = int(max(1000, spend * 1000.0 / cpm))
    clicks = int(max(10, impressions * ctr))
    sessions = clicks * session_rate
    orders = int(max(1, sessions * cv_rate))
    gmv = orders * aov

    plan_id = f"PLAN_{rng.randrange(10000, 99999)}"
    plan_name = f"计划{chr(65 + plan_index)}-{rng.choice(['爆款种草', '新品冷启', '人群扩量', '素材测试', '人群复投'])}"

    # 避免订单与 spend/ROI 过不一致导致显示怪异：轻微抖动
    gmv = gmv * rng.uniform(0.95, 1.05)

    return PlanDayMetrics(
        plan_id=plan_id,
        plan_name=plan_name,
        spend=float(spend),
        impressions=impressions,
        clicks=clicks,
        orders=orders,
        gmv=float(gmv),
    )


def collect_store_day_raw(stores: list[StoreConfig], dt: date) -> list[StoreDayRaw]:
    """拉取每个店铺当天的千川/其他渠道原始数据（模拟）。"""
    all_raw: list[StoreDayRaw] = []

    for store in stores:
        logger.info("店铺[%s]（%s）：开始拉取 %s", store.store_name, store.store_id, dt.isoformat())
        store_goal_roi = store.roi_goal
        qc_accounts: list[AccountDayRaw] = []

        for acc_index, account in enumerate(store.qianchuan_accounts):
            logger.info(
                "  千川账户[%s]（%s）：刷新登录态并拉取计划数据（模拟）",
                account.account_name,
                account.account_id,
            )
            rng = random.Random(_seed_for(store.store_id, account.account_id, dt) + acc_index)

            # 每个千川账户模拟 3~5 个计划
            plan_count = rng.randrange(3, 6)
            weights = [rng.random() for _ in range(plan_count)]
            s = sum(weights) or 1.0
            plan_weights = [w / s for w in weights]

            # 计划质量：决定 ROI 高低（用于更好看的“亮点/预警”）
            qualities = [rng.uniform(0.85, 1.25) for _ in range(plan_count)]
            # 稍微让“不同计划”更有差异
            qualities = [min(max(q, 0.7), 1.35) for q in qualities]

            plans: list[PlanDayMetrics] = []
            for i in range(plan_count):
                plans.append(
                    _generate_plan_metrics(
                        rng=rng,
                        store_goal_roi=store_goal_roi,
                        plan_weight=plan_weights[i],
                        plan_quality=qualities[i],
                        dt=dt,
                        plan_index=i,
                    )
                )

            qc_accounts.append(AccountDayRaw(account=account, plans=plans))

        # “其他渠道/非千川”数据，用千川花费做相关模拟
        qc_spend_total = sum(a.spend for a in qc_accounts)
        rng_other = random.Random(hash((store.store_id, "OTHER", dt.isoformat())) & 0xFFFFFFFF)

        other_roi = max(0.5, store_goal_roi * rng_other.uniform(0.75, 1.05))
        other_spend = max(0.0, qc_spend_total * rng_other.uniform(0.55, 1.05))
        other_gmv = other_spend * other_roi
        other_orders = max(1, int(other_gmv / rng_other.uniform(95, 140)))

        all_raw.append(
            StoreDayRaw(
                store=store,
                qc_accounts=qc_accounts,
                other_channel_spend=float(other_spend),
                other_channel_gmv=float(other_gmv),
                other_channel_orders=int(other_orders),
            )
        )

    return all_raw


def raw_to_serializable(raw: list[StoreDayRaw]) -> list[dict[str, Any]]:
    """便于写入日志/调试的原始数据结构转换。"""
    out: list[dict[str, Any]] = []
    for r in raw:
        out.append(
            {
                "store_id": r.store.store_id,
                "store_name": r.store.store_name,
                "qc_spend": r.qc_spend,
                "qc_gmv": r.qc_gmv,
                "qc_orders": r.qc_orders,
                "qc_impressions": r.qc_impressions,
                "qc_clicks": r.qc_clicks,
                "paid_share": r.paid_share,
                "other_spend": r.other_channel_spend,
                "other_gmv": r.other_channel_gmv,
                "other_orders": r.other_channel_orders,
                "qc_accounts": [
                    {
                        "account_id": a.account.account_id,
                        "account_name": a.account.account_name,
                        "plans": [
                            {
                                "plan_id": p.plan_id,
                                "plan_name": p.plan_name,
                                "spend": p.spend,
                                "impressions": p.impressions,
                                "clicks": p.clicks,
                                "orders": p.orders,
                                "gmv": p.gmv,
                            }
                            for p in a.plans
                        ],
                    }
                    for a in r.qc_accounts
                ],
            }
        )
    return out

