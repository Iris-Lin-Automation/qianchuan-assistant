"""
数据清洗与计算（演示版）。

将多千川账户的原始数据按“店铺”聚合：
- 千川总消耗、总 GMV、综合 ROI = GMV / 千川消耗
- CPA = 消耗 / 订单数
- 千川付费占比 paid_share = 千川消耗 /（千川消耗 + 其他渠道消耗）

并派生用于卡片展示的指标：
CTR、进店率、转化率、退款率（模拟口径）、漏斗文本等。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

from collectors import PlanDayMetrics, StoreDayRaw


@dataclass(frozen=True)
class StoreDayMetrics:
    store_id: str
    store_name: str
    dt: date

    spend: float
    impressions: int
    clicks: int
    orders: int
    gmv: float

    roi: float
    cpa: float
    paid_share: float

    ctr: float
    session_rate: float
    conversion_rate: float
    refund_rate: float

    top_plans: list[dict]


def _fmt_int(n: float) -> str:
    return f"{int(round(n)):,}"


def _compute_funnel_from_totals(*, impressions: int, clicks: int, orders: int, rng: random.Random) -> tuple[float, float, float]:
    # session_rate 与 conversion_rate 用于让漏斗“看起来合理”
    ctr = clicks / impressions if impressions > 0 else 0.0
    session_rate = rng.uniform(0.38, 0.58) if clicks > 0 else 0.0
    sessions = clicks * session_rate
    conversion_rate = orders / sessions if sessions > 0 else 0.0
    return ctr, session_rate, conversion_rate


def _compute_refund_rate(*, orders: int, rng: random.Random) -> float:
    # 退款率通常在 3%~12% 区间（演示）
    base = rng.uniform(0.045, 0.095)
    # orders 越大，波动略减弱
    damp = min(1.0, orders / 2000.0)
    return base * (0.7 + 0.3 * damp)


def aggregate_store_day(raw: StoreDayRaw, dt: date) -> StoreDayMetrics:
    """对单店铺日数据进行聚合计算。"""
    spend = raw.qc_spend
    impressions = raw.qc_impressions
    clicks = raw.qc_clicks
    orders = raw.qc_orders
    gmv = raw.qc_gmv
    roi = gmv / spend if spend > 0 else 0.0
    cpa = spend / orders if orders > 0 else 0.0

    rng = random.Random(hash((raw.store.store_id, "Funnel", dt.isoformat())) & 0xFFFFFFFF)
    ctr, session_rate, conversion_rate = _compute_funnel_from_totals(
        impressions=impressions, clicks=clicks, orders=orders, rng=rng
    )
    refund_rate = _compute_refund_rate(orders=orders, rng=rng)

    # top plans：按 GMV 排序
    all_plans: list[PlanDayMetrics] = []
    for acc in raw.qc_accounts:
        all_plans.extend(acc.plans)
    all_plans_sorted = sorted(all_plans, key=lambda p: p.gmv, reverse=True)
    top_plans = []
    for i, p in enumerate(all_plans_sorted[:4], start=1):
        share = p.gmv / gmv if gmv > 0 else 0.0
        top_plans.append(
            {
                "name": p.plan_name,
                "spend": p.spend,
                "gmv": p.gmv,
                "roi": p.roi,
                "share": f"{share * 100:.1f}%",
                "rank": i,
            }
        )

    return StoreDayMetrics(
        store_id=raw.store.store_id,
        store_name=raw.store.store_name,
        dt=dt,
        spend=float(spend),
        impressions=int(impressions),
        clicks=int(clicks),
        orders=int(orders),
        gmv=float(gmv),
        roi=float(roi),
        cpa=float(cpa),
        paid_share=float(raw.paid_share),
        ctr=float(ctr),
        session_rate=float(session_rate),
        conversion_rate=float(conversion_rate),
        refund_rate=float(refund_rate),
        top_plans=top_plans,
    )


def funnel_lines(metrics: StoreDayMetrics) -> list[str]:
    """将指标转成卡片可直接展示的漏斗文案（4 行）。"""
    impressions = metrics.impressions
    clicks = metrics.clicks

    sessions = int(clicks * metrics.session_rate)
    orders = metrics.orders

    ctr_pct = metrics.ctr * 100
    session_pct = (sessions / clicks * 100) if clicks > 0 else 0.0
    order_conv_pct = (orders / sessions * 100) if sessions > 0 else 0.0

    refund_pct = metrics.refund_rate * 100
    aov = metrics.gmv / orders if orders > 0 else 0.0

    return [
        f"展示 {_fmt_int(impressions)}　→　点击 {_fmt_int(clicks)}（CTR {ctr_pct:.2f}%）",
        f"点击 {_fmt_int(clicks)}　→　进店 {_fmt_int(sessions)}（进店率 {session_pct:.1f}%）",
        f"进店 {_fmt_int(sessions)}　→　下单 {orders:,}（转化率 {order_conv_pct:.2f}%）",
        f"客单价 ¥{aov:,.1f}　退款率 {refund_pct:.1f}%（演示：口径模拟）",
    ]

