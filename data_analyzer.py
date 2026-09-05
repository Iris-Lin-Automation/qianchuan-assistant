"""
数据分析与诊断预警模块。

接收千川/抖店原始指标数据，计算环比、同比变化，
并基于阈值输出诊断等级与预警文案。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from config import config


@dataclass(frozen=True)
class MetricInput:
    """单指标输入结构。"""

    name: str
    current: float
    previous: float | None = None  # 环比对照（上一周期）
    last_year: float | None = None  # 同比对照（去年同期）
    unit: str = "number"  # number | currency | percent
    higher_is_better: bool = True  # False 表示指标越低越好（如成本、退款率）


def calc_change_rate(current: float, baseline: float | None) -> float | None:
    """
    计算变化率（百分比）。

    Returns:
        变化百分比；基线缺失或为 0 时返回 None。
    """
    if baseline is None:
        return None
    if baseline == 0:
        # 基线为 0 时，若当前也为 0 则无变化；否则视为无法用百分比表达
        return 0.0 if current == 0 else None
    return (current - baseline) / abs(baseline) * 100.0


def _is_adverse(change_rate: float | None, higher_is_better: bool) -> bool:
    """判断变化方向是否不利。"""
    if change_rate is None:
        return False
    if higher_is_better:
        return change_rate < 0
    return change_rate > 0


def _severity_level(alerts: list[str], adverse_count: int) -> str:
    """
    根据预警数量判定整体等级。

    - good: 无预警且存在正向表现
    - normal: 无预警
    - warning: 存在预警
    - critical: 多指标同时异常
    """
    if adverse_count >= 3 or len(alerts) >= 3:
        return "critical"
    if alerts:
        return "warning"
    return "good"


def _build_suggestion(level: str, alerts: list[str]) -> str:
    """根据诊断等级生成行动建议。"""
    if level == "critical":
        return (
            "多项核心指标异常，建议立即复盘投放计划与商品转化链路，"
            "优先检查出价策略、素材衰减与落地页转化率。"
        )
    if level == "warning":
        focus = "；".join(alerts[:2]) if alerts else "关注波动指标"
        return f"存在局部波动（{focus}）。建议小步调优投放预算与人群包，并跟踪 24h 内变化。"
    return "指标整体健康，可适度加大优质计划预算，持续沉淀高转化素材。"


def analyze(
    metrics: list[MetricInput] | list[dict[str, Any]],
    report_date: str | None = None,
    threshold_percent: float | None = None,
) -> dict[str, Any]:
    """
    对原始指标执行环比/同比分析与诊断预警。

    Args:
        metrics: MetricInput 列表，或等价字典列表。
        report_date: 报告日期，默认今天。
        threshold_percent: 预警阈值（百分比），默认读取配置。

    Returns:
        结构化分析结果，可供飞书卡片模块直接消费。
    """
    threshold = (
        threshold_percent
        if threshold_percent is not None
        else config.ALERT_THRESHOLD_PERCENT
    )
    report_date = report_date or date.today().isoformat()

    normalized: list[MetricInput] = []
    for item in metrics:
        if isinstance(item, MetricInput):
            normalized.append(item)
        else:
            normalized.append(MetricInput(**item))

    metric_rows: list[dict[str, Any]] = []
    alerts: list[str] = []
    adverse_alerts: list[str] = []

    for m in normalized:
        mom = calc_change_rate(m.current, m.previous)
        yoy = calc_change_rate(m.current, m.last_year)

        row = {
            "name": m.name,
            "current": m.current,
            "previous": m.previous,
            "last_year": m.last_year,
            "mom": mom,
            "yoy": yoy,
            "unit": m.unit,
            "higher_is_better": m.higher_is_better,
        }
        metric_rows.append(row)

        # 环比超阈值预警
        if mom is not None and abs(mom) >= threshold:
            direction = "上升" if mom > 0 else "下降"
            adverse = _is_adverse(mom, m.higher_is_better)
            if adverse:
                msg = (
                    f"「{m.name}」环比{direction} {abs(mom):.2f}%"
                    f"（阈值 {threshold:g}%），需关注"
                )
                alerts.append(msg)
                adverse_alerts.append(msg)
            else:
                # 有利大幅波动也提示，但不计入不利等级
                alerts.append(
                    f"「{m.name}」环比{direction} {abs(mom):.2f}%（有利波动，可放大优势）"
                )

        # 同比超阈值且不利时追加预警
        if yoy is not None and abs(yoy) >= threshold and _is_adverse(yoy, m.higher_is_better):
            direction = "上升" if yoy > 0 else "下降"
            msg = (
                f"「{m.name}」同比{direction} {abs(yoy):.2f}%"
                f"（阈值 {threshold:g}%），同比承压"
            )
            alerts.append(msg)
            adverse_alerts.append(msg)

    # 去重预警文案，保持顺序
    unique_alerts = list(dict.fromkeys(alerts))
    unique_adverse = list(dict.fromkeys(adverse_alerts))
    level = _severity_level(unique_adverse, len(unique_adverse))

    if level == "critical":
        overview = "诊断结果：严重预警。多指标同步异常，建议立刻排查投放与货盘。"
    elif level == "warning":
        overview = "诊断结果：存在波动预警。建议针对性优化异常指标。"
    else:
        overview = "诊断结果：整体表现良好，核心指标处于可控区间。"

    return {
        "report_date": report_date,
        "level": level,
        "threshold_percent": threshold,
        "metrics": metric_rows,
        "alerts": unique_alerts,
        "summary": {
            "overview": overview,
            "suggestion": _build_suggestion(level, unique_alerts),
            "metric_count": len(metric_rows),
            "alert_count": len(unique_alerts),
        },
    }
