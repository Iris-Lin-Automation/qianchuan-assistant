"""
日报/周报的个性化模板（演示版）。

客户往往希望不同店铺/不同团队看到“不同风格”的报告。
本模块集中管理这些定制化字段，避免把硬编码散落在流水线里。
"""

from __future__ import annotations

from datetime import date

from mock_accounts import StoreConfig


def daily_template_for(store: StoreConfig, dt: date) -> dict:
    header_color = "turquoise" if store.store_id.endswith("1") else "green"
    subtitle = f"店铺：{store.store_name} · 千川 ROI/效率日报"
    goal_status = f"ROI 目标 {store.roi_goal:.2f} 已达成 ✅"  # pipeline 会按 roi 是否达成二次覆盖
    return {
        "header_color": header_color,
        "subtitle": subtitle,
        "goal_status": goal_status,
    }


def weekly_template_for(store: StoreConfig, week_range: str) -> dict:
    header_color = "purple" if store.store_id.endswith("1") else "blue"
    subtitle = f"店铺：{store.store_name} · 周经营复盘"
    return {
        "header_color": header_color,
        "subtitle": subtitle,
        "week_range": week_range,
    }


def grade_from_level(level: str) -> str:
    if level == "critical":
        return "C（需要紧急复盘）"
    if level == "warning":
        return "B（有波动，需要跟进）"
    return "A（稳定达标）"


def build_weekly_actions(level: str, store: StoreConfig, roi: float) -> list[str]:
    if level == "critical":
        return [
            f"下周一前优先处理低 ROI 计划，确保店铺 ROI 回到 {store.roi_goal:.2f} 以上。",
            "复盘素材衰减与落地页转化链路，针对性调整人群包与出价策略。",
            "建立 ROI 护栏：当周中 ROI 连续 2 天低于目标，自动降速并触发复核。",
        ]
    if level == "warning":
        return [
            "聚焦波动最大的计划：以 ROI 为核心指标做小步调优（预算 10%-20% 梯度）。",
            "保留高转化素材并加大同人群相似投放，放大优势同时控制风险。",
            f"在下周二前完成一次素材/人群 A/B 测试，验证后再扩量（目标 ROI {store.roi_goal:.2f}）。",
        ]
    return [
        "达标状态下优先扩量高转化计划，避免在转化端出现回落。",
        "沉淀周五高 ROI 素材与人群包，形成可复用策略资产。",
        f"若 ROI 连续 3 天稳定高于 {max(store.roi_goal, roi):.2f}，可适度加大预算 15%-25%。",
    ]

