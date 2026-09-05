"""
主业务流水线（演示版）。

覆盖客户提出的关键工作流闭环：
1) 多账号采集（模拟轮询拉取千川/抖店数据）
2) 数据清洗与归集（按店铺聚合、计算 ROI/CPA/付费占比）
3) 同步数据到“飞书多维表格”（此处为本地预览桩，便于你录视频）
4) 构建“个性化日报/周报”飞书交互式卡片并推送（Webhook）
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

from cleaner import aggregate_store_day, funnel_lines
from collectors import collect_store_day_raw, raw_to_serializable
from config import config
from data_analyzer import MetricInput, analyze
from feishu_card import send_daily_report, send_monthly_report, send_weekly_report
from feishu_table import sync_daily_metrics
from mock_accounts import StoreConfig, get_demo_store_configs
from report_templates import (
    build_weekly_actions,
    daily_template_for,
    grade_from_level,
    weekly_template_for,
)
from rpa_runner import run_silent_rpa_collect
from storage import upsert_store_day_metrics

logger = logging.getLogger(__name__)


def _table_url() -> str:
    # 卡片不再外链仪表盘/千川后台；保留字段兼容旧调用。
    return ""


def _pct_diff(current: float, baseline: float | None) -> str:
    if baseline is None or baseline == 0:
        return "N/A"
    pct = (current - baseline) / abs(baseline) * 100.0
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _fmt_money(x: float) -> str:
    return f"{x:,.2f}"


def _fmt_float(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}"


def _mood_from_roi(roi: float, goal_roi: float) -> str:
    if roi >= goal_roi * 1.12:
        return "🔥 爆发"
    if roi >= goal_roi:
        return "回升"
    if roi >= goal_roi * 0.88:
        return "维持"
    return "⚠️ 偏离目标"


def _pick_highlights_and_warnings(analysis: dict[str, Any]) -> tuple[str, str]:
    alerts: list[str] = analysis.get("alerts", [])
    # analyze 里的字符串包含“需关注 / 同比承压 / 有利波动”
    warning_items = [a for a in alerts if ("需关注" in a or "同比承压" in a)]
    good_items = [a for a in alerts if "有利波动" in a]

    highlights = "；".join(good_items[:2]) if good_items else "关键指标保持在目标附近，ROI 稳定运行。"
    warning = "；".join(warning_items[:3]) if warning_items else "暂无异常预警。"
    return highlights, warning


def run_daily(
    dt: date,
    *,
    dry_run_card: bool = True,
    dry_run_table: bool = True,
    with_rpa: bool = True,
) -> list[dict[str, Any]]:
    """对指定日期生成日报并推送（每个店铺一张）。"""
    if with_rpa:
        run_silent_rpa_collect(dt)

    stores = get_demo_store_configs()

    logger.info("采集：%s（多店铺千川模拟轮询）", dt.isoformat())
    raw_today = collect_store_day_raw(stores, dt)

    # 归集
    metrics_today = {r.store.store_id: aggregate_store_day(r, dt) for r in raw_today}

    # 原始数据用于入库留痕（演示用；用于你回溯/解释口径）
    serialized_today = raw_to_serializable(raw_today)
    snapshot_map = {x["store_id"]: x for x in serialized_today}

    # 入库（本地）
    for r in raw_today:
        upsert_store_day_metrics(
            metrics_today[r.store.store_id],
            raw_snapshot=snapshot_map.get(r.store.store_id),
        )

    # 同步到“飞书多维表格”（本地预览桩）
    sync_daily_metrics(metrics_today.values(), dry_run=dry_run_table)

    # 计算环比/同比：需要前一天与去年同期
    prev_dt = dt - timedelta(days=1)
    yoy_dt = dt - timedelta(days=365)

    raw_prev = collect_store_day_raw(stores, prev_dt)
    metrics_prev = {r.store.store_id: aggregate_store_day(r, prev_dt) for r in raw_prev}

    raw_yoy = collect_store_day_raw(stores, yoy_dt)
    metrics_yoy = {r.store.store_id: aggregate_store_day(r, yoy_dt) for r in raw_yoy}

    results: list[dict[str, Any]] = []
    for store in stores:
        m = metrics_today[store.store_id]
        prev = metrics_prev[store.store_id]
        yoy = metrics_yoy[store.store_id]

        analysis = analyze(
            metrics=[
                MetricInput(
                    name="千川消耗",
                    current=m.spend,
                    previous=prev.spend,
                    last_year=yoy.spend,
                    unit="currency",
                    higher_is_better=False,
                ),
                MetricInput(
                    name="成交 GMV",
                    current=m.gmv,
                    previous=prev.gmv,
                    last_year=yoy.gmv,
                    unit="currency",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="综合 ROI",
                    current=m.roi,
                    previous=prev.roi,
                    last_year=yoy.roi,
                    unit="number",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="转化成本 CPA",
                    current=m.cpa,
                    previous=prev.cpa,
                    last_year=yoy.cpa,
                    unit="currency",
                    higher_is_better=False,
                ),
            ],
            report_date=dt.isoformat(),
        )

        grade = grade_from_level(analysis["level"])
        template = daily_template_for(store, dt)

        goal_reached = m.roi >= store.roi_goal
        if goal_reached:
            goal_status = f"ROI 目标 {store.roi_goal:.2f} 已达成 ✅"
        else:
            goal_status = f"ROI 目标 {store.roi_goal:.2f} 未达成（当前 {m.roi:.2f}）⚠️"

        highlights, warning = _pick_highlights_and_warnings(analysis)

        # 计划表现 TOP（卡片展示需要 spend/gmv/roi 为字符串）
        plans: list[dict[str, Any]] = []
        for p in m.top_plans:
            tag: str
            if float(p["roi"]) >= store.roi_goal * 1.12:
                tag = "🔥 主力"
            elif float(p["roi"]) >= store.roi_goal:
                tag = "✅ 达标"
            elif float(p["roi"]) >= store.roi_goal * 0.88:
                tag = "⚠️ 贴线"
            else:
                tag = "❌ 拖后腿"
            plans.append(
                {
                    "name": p["name"],
                    "spend": _fmt_money(float(p["spend"])),
                    "gmv": _fmt_money(float(p["gmv"])),
                    "roi": _fmt_float(float(p["roi"]), 2),
                    "tag": tag,
                }
            )

        card_data: dict[str, Any] = {
            "date": dt.isoformat(),
            "header_color": template["header_color"],
            "subtitle": template["subtitle"],
            "grade": grade,
            "goal_status": goal_status,
            "spend": _fmt_money(m.spend),
            "spend_diff": _pct_diff(m.spend, prev.spend),
            "gmv": _fmt_money(m.gmv),
            "gmv_diff": _pct_diff(m.gmv, prev.gmv),
            "roi": _fmt_float(m.roi, 2),
            "roi_value": float(m.roi),
            "roi_goal": float(store.roi_goal),
            "roi_diff": _pct_diff(m.roi, prev.roi),
            "cpa": _fmt_float(m.cpa, 2),
            "cpa_diff": _pct_diff(m.cpa, prev.cpa),
            "plans": plans,
            "funnel": funnel_lines(m),
            "highlights": highlights,
            "warning": warning,
            "suggestion": analysis["summary"]["suggestion"],
            "table_url": _table_url(),
        }

        logger.info("推送日报：%s（dry_run_card=%s）", store.store_name, dry_run_card)
        send_res = send_daily_report(card_data, dry_run=dry_run_card)
        results.append(
            {
                "store_id": store.store_id,
                "store_name": store.store_name,
                "analysis_level": analysis["level"],
                "feishu_send_result": send_res,
                "card_data": card_data,
            }
        )

    return results


def _week_range(week_end: date) -> tuple[date, date]:
    # 以周一到周日作为展示范围（周日结束）
    start = week_end - timedelta(days=6)
    return start, week_end


def run_weekly(week_end: date, *, dry_run_card: bool = True, dry_run_table: bool = True) -> list[dict[str, Any]]:
    """对指定周生成周报并推送（每个店铺一张）。"""
    stores = get_demo_store_configs()
    ws, we = _week_range(week_end)
    week_range = f"{ws.strftime('%Y-%m-%d')} ~ {we.strftime('%m-%d')}"

    logger.info("采集：周报区间 %s", week_range)

    # 当前周逐日采集并聚合
    daily_metrics: dict[str, list[Any]] = {s.store_id: [] for s in stores}
    for i in range(7):
        dt = ws + timedelta(days=i)
        raw_day = collect_store_day_raw(stores, dt)
        for r in raw_day:
            daily_metrics[r.store.store_id].append(aggregate_store_day(r, dt))

    # 上周逐日采集并聚合
    prev_end = ws - timedelta(days=1)
    prev_ws, prev_we = _week_range(prev_end)
    prev_week_metrics: dict[str, list[Any]] = {s.store_id: [] for s in stores}
    for i in range(7):
        dt = prev_ws + timedelta(days=i)
        raw_day = collect_store_day_raw(stores, dt)
        for r in raw_day:
            prev_week_metrics[r.store.store_id].append(aggregate_store_day(r, dt))

    # 去年同期（同样 7 天）
    yoy_end = week_end - timedelta(days=365)
    yoy_ws, yoy_we = _week_range(yoy_end)
    yoy_week_metrics: dict[str, list[Any]] = {s.store_id: [] for s in stores}
    for i in range(7):
        dt = yoy_ws + timedelta(days=i)
        raw_day = collect_store_day_raw(stores, dt)
        for r in raw_day:
            yoy_week_metrics[r.store.store_id].append(aggregate_store_day(r, dt))

    results: list[dict[str, Any]] = []
    for store in stores:
        m_days = daily_metrics[store.store_id]
        prev_days = prev_week_metrics[store.store_id]
        yoy_days = yoy_week_metrics[store.store_id]

        # 汇总
        spend = sum(m.spend for m in m_days)
        gmv = sum(m.gmv for m in m_days)
        orders = sum(m.orders for m in m_days)
        roi = gmv / spend if spend > 0 else 0.0
        cpa = spend / orders if orders > 0 else 0.0
        paid_share = sum(m.paid_share for m in m_days) / 7.0 if m_days else 0.0

        spend_prev = sum(m.spend for m in prev_days)
        gmv_prev = sum(m.gmv for m in prev_days)
        orders_prev = sum(m.orders for m in prev_days)
        roi_prev = gmv_prev / spend_prev if spend_prev > 0 else 0.0
        cpa_prev = spend_prev / orders_prev if orders_prev > 0 else 0.0

        spend_yoy = sum(m.spend for m in yoy_days)
        gmv_yoy = sum(m.gmv for m in yoy_days)
        orders_yoy = sum(m.orders for m in yoy_days)
        roi_yoy = gmv_yoy / spend_yoy if spend_yoy > 0 else 0.0
        cpa_yoy = spend_yoy / orders_yoy if orders_yoy > 0 else 0.0

        analysis = analyze(
            metrics=[
                MetricInput(
                    name="千川消耗",
                    current=spend,
                    previous=spend_prev,
                    last_year=spend_yoy,
                    unit="currency",
                    higher_is_better=False,
                ),
                MetricInput(
                    name="成交 GMV",
                    current=gmv,
                    previous=gmv_prev,
                    last_year=gmv_yoy,
                    unit="currency",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="综合 ROI",
                    current=roi,
                    previous=roi_prev,
                    last_year=roi_yoy,
                    unit="number",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="转化成本 CPA",
                    current=cpa,
                    previous=cpa_prev,
                    last_year=cpa_yoy,
                    unit="currency",
                    higher_is_better=False,
                ),
            ],
            report_date=week_end.isoformat(),
        )

        grade = grade_from_level(analysis["level"])
        template = weekly_template_for(store, week_range=week_range)

        highlights, warning = _pick_highlights_and_warnings(analysis)

        # 每日走势
        daily_trend = []
        for d in m_days:
            mood = _mood_from_roi(d.roi, store.roi_goal)
            day_label = d.dt.strftime("%a %m-%d")
            daily_trend.append(
                {
                    "day": day_label,
                    "spend": _fmt_money(d.spend),
                    "gmv": _fmt_money(d.gmv),
                    "roi": _fmt_float(d.roi, 2),
                    "mood": mood,
                }
            )

        # 周计划贡献榜（用本周 ROI / GMV 作为排序依据；演示口径）
        # 由于计划名称每天可能变化，这里做“本周聚合 top4”
        plan_bucket: dict[str, dict[str, Any]] = {}
        for d in m_days:
            for p in d.top_plans:
                name = p["name"]
                bucket = plan_bucket.get(name)
                if bucket is None:
                    plan_bucket[name] = {
                        "name": name,
                        "spend": 0.0,
                        "gmv": 0.0,
                        "roi": 0.0,
                    }
                    bucket = plan_bucket[name]
                bucket["spend"] += float(p["spend"])
                bucket["gmv"] += float(p["gmv"])

        for name, b in plan_bucket.items():
            b["roi"] = b["gmv"] / b["spend"] if b["spend"] > 0 else 0.0

        top_plans = sorted(plan_bucket.values(), key=lambda x: x["gmv"], reverse=True)[:4]
        top_plans_cards = []
        for i, p in enumerate(top_plans, start=1):
            share = p["gmv"] / gmv if gmv > 0 else 0.0
            top_plans_cards.append(
                {
                    "name": p["name"],
                    "roi": _fmt_float(float(p["roi"]), 2),
                    "gmv": _fmt_money(float(p["gmv"])),
                    "share": f"{share * 100:.1f}%",
                }
            )

        vs_last_week = [
            f"千川消耗 {_pct_diff(spend, spend_prev)}（本周）",
            f"GMV {_pct_diff(gmv, gmv_prev)}，增速快于/慢于消耗（演示）",
            f"ROI {roi_prev:.2f} -> {roi:.2f}（环比 { _pct_diff(roi, roi_prev) }）",
            f"CPA {_pct_diff(cpa, cpa_prev)}（越低越好）",
            f"千川付费占比 {paid_share * 100:.1f}%（演示口径）",
        ]

        actions = build_weekly_actions(analysis["level"], store, roi)
        summary = (
            f"{analysis['summary']['overview']}\n"
            f"本周千川付费占比：{paid_share * 100:.1f}%；重点亮点：{highlights}"
        )

        card_data: dict[str, Any] = {
            "week_range": week_range,
            "header_color": template["header_color"],
            "subtitle": template["subtitle"],
            "grade": grade,
            "summary": summary,
            "spend": _fmt_money(spend),
            "spend_diff": _pct_diff(spend, spend_prev),
            "gmv": _fmt_money(gmv),
            "gmv_diff": _pct_diff(gmv, gmv_prev),
            "roi": _fmt_float(roi, 2),
            "roi_value": float(roi),
            "roi_goal": float(store.roi_goal),
            "roi_diff": _pct_diff(roi, roi_prev),
            "cpa": _fmt_float(cpa, 2),
            "cpa_diff": _pct_diff(cpa, cpa_prev),
            "orders": f"{orders:,}",
            "orders_diff": _pct_diff(float(orders), float(orders_prev)),
            "daily_trend": daily_trend,
            "top_plans": top_plans_cards,
            "vs_last_week": vs_last_week,
            "actions": actions,
            "highlights": highlights,
            "warning": warning,
            "table_url": _table_url(),
        }

        logger.info("推送周报：%s（dry_run_card=%s）", store.store_name, dry_run_card)
        send_res = send_weekly_report(card_data, dry_run=dry_run_card)
        results.append(
            {
                "store_id": store.store_id,
                "store_name": store.store_name,
                "analysis_level": analysis["level"],
                "feishu_send_result": send_res,
                "card_data": card_data,
            }
        )

    return results


def run_monthly(
    month_end: date,
    *,
    dry_run_card: bool = True,
    dry_run_table: bool = True,
    with_rpa: bool = False,
) -> list[dict[str, Any]]:
    """生成近 30 天月报并推送（每个店铺一张）。"""
    if with_rpa:
        run_silent_rpa_collect(month_end)

    stores = get_demo_store_configs()
    start = month_end - timedelta(days=29)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=29)
    month_label = f"{start.strftime('%Y-%m-%d')} ~ {month_end.strftime('%m-%d')}"

    logger.info("采集：月报区间 %s", month_label)

    def _collect_range(s: date, e: date) -> dict[str, list[Any]]:
        bucket: dict[str, list[Any]] = {x.store_id: [] for x in stores}
        cur = s
        while cur <= e:
            raw = collect_store_day_raw(stores, cur)
            for r in raw:
                bucket[r.store.store_id].append(aggregate_store_day(r, cur))
            cur += timedelta(days=1)
        return bucket

    cur_map = _collect_range(start, month_end)
    prev_map = _collect_range(prev_start, prev_end)

    results: list[dict[str, Any]] = []
    for store in stores:
        days = cur_map[store.store_id]
        prev_days = prev_map[store.store_id]

        spend = sum(d.spend for d in days)
        gmv = sum(d.gmv for d in days)
        orders = sum(d.orders for d in days)
        roi = gmv / spend if spend > 0 else 0.0
        cpa = spend / orders if orders > 0 else 0.0

        spend_prev = sum(d.spend for d in prev_days)
        gmv_prev = sum(d.gmv for d in prev_days)
        orders_prev = sum(d.orders for d in prev_days)
        roi_prev = gmv_prev / spend_prev if spend_prev > 0 else 0.0
        cpa_prev = spend_prev / orders_prev if orders_prev > 0 else 0.0

        analysis = analyze(
            metrics=[
                MetricInput(
                    name="千川消耗",
                    current=spend,
                    previous=spend_prev,
                    unit="currency",
                    higher_is_better=False,
                ),
                MetricInput(
                    name="成交 GMV",
                    current=gmv,
                    previous=gmv_prev,
                    unit="currency",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="综合 ROI",
                    current=roi,
                    previous=roi_prev,
                    unit="number",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="转化成本 CPA",
                    current=cpa,
                    previous=cpa_prev,
                    unit="currency",
                    higher_is_better=False,
                ),
            ],
            report_date=month_end.isoformat(),
        )
        highlights, warning = _pick_highlights_and_warnings(analysis)
        grade = grade_from_level(analysis["level"])
        actions = build_weekly_actions(analysis["level"], store, roi)

        week_breakdown = []
        for i in range(4):
            ws = start + timedelta(days=i * 7)
            we = min(ws + timedelta(days=6), month_end)
            chunk = [d for d in days if ws <= d.dt <= we]
            if not chunk:
                continue
            w_spend = sum(d.spend for d in chunk)
            w_gmv = sum(d.gmv for d in chunk)
            w_roi = w_gmv / w_spend if w_spend > 0 else 0.0
            week_breakdown.append(
                {
                    "label": f"第{i + 1}周 {ws.strftime('%m-%d')}~{we.strftime('%m-%d')}",
                    "spend": _fmt_money(w_spend),
                    "gmv": _fmt_money(w_gmv),
                    "roi": _fmt_float(w_roi, 2),
                }
            )

        card_data: dict[str, Any] = {
            "month_label": month_label,
            "header_color": "indigo",
            "subtitle": f"店铺：{store.store_name} · 月度经营复盘",
            "grade": grade,
            "summary": analysis["summary"]["overview"],
            "spend": _fmt_money(spend),
            "spend_diff": _pct_diff(spend, spend_prev),
            "gmv": _fmt_money(gmv),
            "gmv_diff": _pct_diff(gmv, gmv_prev),
            "roi": _fmt_float(roi, 2),
            "roi_value": float(roi),
            "roi_goal": float(store.roi_goal),
            "roi_diff": _pct_diff(roi, roi_prev),
            "cpa": _fmt_float(cpa, 2),
            "cpa_diff": _pct_diff(cpa, cpa_prev),
            "orders": f"{orders:,}",
            "orders_diff": _pct_diff(float(orders), float(orders_prev)),
            "week_breakdown": week_breakdown,
            "top_plans": [],
            "highlights": highlights,
            "warning": warning,
            "actions": actions,
            "table_url": _table_url(),
        }

        logger.info("推送月报：%s（dry_run_card=%s）", store.store_name, dry_run_card)
        send_res = send_monthly_report(card_data, dry_run=dry_run_card)
        results.append(
            {
                "store_id": store.store_id,
                "store_name": store.store_name,
                "analysis_level": analysis["level"],
                "feishu_send_result": send_res,
                "card_data": card_data,
            }
        )

    return results


def run_from_excel(
    file_path: str,
    *,
    dry_run_card: bool = False,
    dry_run_table: bool | None = None,
    report_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    影刀闭环入口：读取 RPA 导出的 Excel → 算 ROI → 入库/看板 → 推飞书卡片。

    默认真实推送（dry_run_card=False），适合影刀无人值守最后一步调用。
    """
    from excel_loader import load_excel_store_metrics

    if dry_run_table is None:
        dry_run_table = not config.bitable_api_ready()

    bundles = load_excel_store_metrics(file_path, report_date=report_date)
    metrics_list = [b.today for b in bundles]
    sync_daily_metrics(metrics_list, dry_run=dry_run_table)

    for b in bundles:
        upsert_store_day_metrics(b.today, raw_snapshot={"source": "yingdao_excel", "file": str(file_path)})

    results: list[dict[str, Any]] = []
    for b in bundles:
        m = b.today
        prev = b.previous
        goal = b.roi_goal
        dt = m.dt

        analysis = analyze(
            metrics=[
                MetricInput(
                    name="千川消耗",
                    current=m.spend,
                    previous=prev.spend if prev else None,
                    unit="currency",
                    higher_is_better=False,
                ),
                MetricInput(
                    name="成交 GMV",
                    current=m.gmv,
                    previous=prev.gmv if prev else None,
                    unit="currency",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="综合 ROI",
                    current=m.roi,
                    previous=prev.roi if prev else None,
                    unit="number",
                    higher_is_better=True,
                ),
                MetricInput(
                    name="转化成本 CPA",
                    current=m.cpa,
                    previous=prev.cpa if prev else None,
                    unit="currency",
                    higher_is_better=False,
                ),
            ],
            report_date=dt.isoformat(),
        )
        highlights, warning = _pick_highlights_and_warnings(analysis)
        grade = grade_from_level(analysis["level"])
        goal_reached = m.roi >= goal
        goal_status = (
            f"ROI 目标 {goal:.2f} 已达成 ✅"
            if goal_reached
            else f"ROI 目标 {goal:.2f} 未达成（当前 {m.roi:.2f}）⚠️"
        )

        plans: list[dict[str, Any]] = []
        for p in m.top_plans:
            if float(p["roi"]) >= goal * 1.12:
                tag = "🔥 主力"
            elif float(p["roi"]) >= goal:
                tag = "✅ 达标"
            elif float(p["roi"]) >= goal * 0.88:
                tag = "⚠️ 贴线"
            else:
                tag = "❌ 拖后腿"
            plans.append(
                {
                    "name": p["name"],
                    "spend": _fmt_money(float(p["spend"])),
                    "gmv": _fmt_money(float(p["gmv"])),
                    "roi": _fmt_float(float(p["roi"]), 2),
                    "tag": tag,
                }
            )

        card_data: dict[str, Any] = {
            "date": dt.isoformat(),
            "header_color": "turquoise",
            "subtitle": f"店铺：{m.store_name} · 影刀导出自动日报",
            "grade": grade,
            "goal_status": goal_status,
            "spend": _fmt_money(m.spend),
            "spend_diff": _pct_diff(m.spend, prev.spend if prev else None),
            "gmv": _fmt_money(m.gmv),
            "gmv_diff": _pct_diff(m.gmv, prev.gmv if prev else None),
            "roi": _fmt_float(m.roi, 2),
            "roi_value": float(m.roi),
            "roi_goal": float(goal),
            "roi_diff": _pct_diff(m.roi, prev.roi if prev else None),
            "cpa": _fmt_float(m.cpa, 2),
            "cpa_diff": _pct_diff(m.cpa, prev.cpa if prev else None),
            "plans": plans,
            "funnel": funnel_lines(m),
            "highlights": highlights,
            "warning": warning,
            "suggestion": analysis["summary"]["suggestion"],
            "table_url": _table_url(),
        }

        logger.info("影刀Excel日报推送：%s", m.store_name)
        send_res = send_daily_report(card_data, dry_run=dry_run_card)
        results.append(
            {
                "store_id": m.store_id,
                "store_name": m.store_name,
                "analysis_level": analysis["level"],
                "feishu_send_result": send_res,
                "card_data": card_data,
            }
        )

    return results

