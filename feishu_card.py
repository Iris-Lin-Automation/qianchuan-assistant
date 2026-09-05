"""
飞书卡片消息构建与推送模块（Card JSON 2.0）。

升级点：
1. column_set 多列指标色块
2. ROI 目标进度条（官方 chart.linearProgress）
3. header text_tag 彩色状态标签
4. 底部不放外链按钮（看板看本机 HTML，避免失效跳转）
5. collapsible_panel 折叠区分亮点与预警
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from config import config

logger = logging.getLogger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    """尽量从字符串/数字解析浮点值。"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group()) if match else default


def _diff_meta(diff: str, higher_is_better: bool = True) -> tuple[str, str, bool]:
    """解析环比文案，返回 (箭头, 颜色, 是否有利)。"""
    diff_str = (diff or "").strip()
    is_positive = diff_str.startswith("+") or diff_str.startswith("↑")
    is_negative = diff_str.startswith("-") or diff_str.startswith("↓")

    if is_positive:
        arrow = "▲"
    elif is_negative:
        arrow = "▼"
    else:
        arrow = "—"

    good = (is_positive and higher_is_better) or (is_negative and not higher_is_better)
    color = "green" if good else "red"
    return arrow, color, good


def _metric_column(
    title: str,
    value: str,
    diff: str,
    *,
    higher_is_better: bool = True,
    bg: str = "grey",
) -> dict[str, Any]:
    """带背景色的指标列（卡片化指标框）。"""
    arrow, color, _ = _diff_meta(diff, higher_is_better)
    return {
        "tag": "column",
        "width": "weighted",
        "weight": 1,
        "background_style": bg,
        "padding": "12px 8px",
        "vertical_align": "top",
        "elements": [
            {
                "tag": "markdown",
                "content": (
                    f"<font color='grey'>{title}</font>\n"
                    f"**{value}**\n"
                    f"<font color='{color}'>{arrow} {diff}</font>"
                ),
                "text_align": "center",
            }
        ],
    }


def _text_tag(content: str, color: str) -> dict[str, Any]:
    """彩色状态标签（text_tag）。"""
    return {
        "tag": "text_tag",
        "text": {"tag": "plain_text", "content": content},
        "color": color,
    }


def _build_status_tags(data: dict[str, Any]) -> list[dict[str, Any]]:
    """根据 ROI / 预警 / 爆款计划生成最多 3 个标题标签。"""
    tags: list[dict[str, Any]] = []

    roi = _to_float(data.get("roi_value", data.get("roi")), 0.0)
    goal = _to_float(data.get("roi_goal"), 2.5)
    warning = str(data.get("warning") or "")
    has_warning = bool(warning) and ("暂无异常" not in warning)

    if roi >= goal:
        tags.append(_text_tag("🟢 目标达成", "green"))
    else:
        tags.append(_text_tag("🟡 未达目标", "orange"))

    if has_warning:
        tags.append(_text_tag("🔴 异常预警", "red"))
    else:
        tags.append(_text_tag("🟢 运行平稳", "turquoise"))

    # 是否有爆款计划
    hot = False
    for plan in data.get("plans") or data.get("top_plans") or []:
        tag = str(plan.get("tag") or "")
        name = str(plan.get("name") or "")
        if "🔥" in tag or "爆款" in name or "主力" in tag:
            hot = True
            break
    if hot:
        tags.append(_text_tag("🔥 爆款计划", "orange"))

    return tags[:3]


def _roi_progress_percent(data: dict[str, Any]) -> tuple[float, float, float]:
    """
    计算 ROI 目标进度。

    Returns:
        (当前 ROI, 目标 ROI, 进度 0~1，可超过 1 但展示会截断到 1)
    """
    roi = _to_float(data.get("roi_value", data.get("roi")), 0.0)
    goal = _to_float(data.get("roi_goal"), 0.0)

    # 兜底：从 goal_status 中解析“目标 2.50”
    if goal <= 0:
        match = re.search(r"目标\s*([0-9]+(?:\.[0-9]+)?)", str(data.get("goal_status", "")))
        goal = float(match.group(1)) if match else 2.5

    ratio = (roi / goal) if goal > 0 else 0.0
    return roi, goal, ratio


def _build_progress_bar(data: dict[str, Any]) -> dict[str, Any]:
    """
    ROI 目标进度条。

    飞书官方没有独立 progress_bar 标签，进度可视化使用
    Card JSON 2.0 的 chart + linearProgress（条形进度）。
    """
    roi, goal, ratio = _roi_progress_percent(data)
    shown = min(max(ratio, 0.0), 1.0)
    pct_text = f"{ratio * 100:.0f}%"

    return {
        "tag": "chart",
        "element_id": "roi_progress",
        "aspect_ratio": "4:1",
        "color_theme": "brand",
        "preview": False,
        "chart_spec": {
            "type": "linearProgress",
            "title": {
                "text": f"ROI 目标进度  {roi:.2f} / {goal:.2f}（{pct_text}）"
            },
            "data": {
                "values": [
                    {
                        "type": "ROI 达成率",
                        "value": shown,
                        "text": pct_text,
                    }
                ]
            },
            "direction": "horizontal",
            "xField": "value",
            "yField": "type",
            "seriesField": "type",
            "axes": [
                {
                    "orient": "left",
                    "domainLine": {"visible": False},
                }
            ],
        },
    }


def _open_url_button(title: str, url: str, *, btn_type: str = "default") -> dict[str, Any]:
    """构建可点击跳转按钮。"""
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": title},
        "type": btn_type,
        "width": "fill",
        "behaviors": [
            {
                "type": "open_url",
                "default_url": url,
                "pc_url": url,
                "android_url": url,
                "ios_url": url,
            }
        ],
    }


def _action_buttons(data: dict[str, Any]) -> dict[str, Any] | None:
    """卡片底部不再放外链按钮（仪表盘 / 千川后台均易失效）。"""
    return None


def _elements(*parts: Any) -> list[Any]:
    """组装卡片元素，自动跳过空按钮等。"""
    return [p for p in parts if p is not None]


def _collapsible_panel(
    *,
    element_id: str,
    title: str,
    content: str,
    header_color: str,
    expanded: bool = True,
) -> dict[str, Any]:
    """折叠面板：用于亮点 / 预警分区。"""
    return {
        "tag": "collapsible_panel",
        "element_id": element_id,
        "expanded": expanded,
        "background_color": "grey",
        "header": {
            "title": {"tag": "markdown", "content": f"**{title}**"},
            "background_color": header_color,
            "vertical_align": "center",
            "padding": "4px 8px 4px 8px",
            "icon": {
                "tag": "standard_icon",
                "token": "down-small-ccm_outlined",
                "color": "white",
                "size": "16px 16px",
            },
            "icon_position": "right",
            "icon_expanded_angle": -180,
        },
        "border": {"color": "grey", "corner_radius": "5px"},
        "padding": "8px 8px 8px 8px",
        "vertical_spacing": "8px",
        "elements": [
            {
                "tag": "markdown",
                "content": content or "暂无内容",
            }
        ],
    }


def _footer_note(text: str) -> dict[str, Any]:
    """JSON 2.0 不再推荐 note，改用灰色小字 markdown。"""
    return {
        "tag": "markdown",
        "content": f"<font color='grey'>{text}</font>",
    }


def build_daily_card(data: dict[str, Any]) -> dict[str, Any]:
    """构建 Card JSON 2.0 日报卡片。"""
    header_color = data.get("header_color", "turquoise")
    plans_md = "\n".join(
        f"• **{p['name']}**　消耗 ¥{p['spend']}　GMV ¥{p['gmv']}　ROI **{p['roi']}**　{p.get('tag', '')}"
        for p in data.get("plans", [])
    ) or "_暂无计划数据_"
    funnel_md = "\n".join(f"• {row}" for row in data.get("funnel", [])) or "_暂无漏斗数据_"

    card: dict[str, Any] = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True,
            "update_multi": True,
            "width_mode": "fill",
        },
        "header": {
            "template": header_color,
            "title": {
                "tag": "plain_text",
                "content": f"📊 抖音千川 · 日报 | {data['date']}",
            },
            "subtitle": {
                "tag": "plain_text",
                "content": data.get("subtitle", "昨日全天投放表现"),
            },
            "text_tag_list": _build_status_tags(data),
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 8px",
            "vertical_spacing": "8px",
            "elements": _elements(
                {
                    "tag": "markdown",
                    "content": (
                        f"**综合评级**　{data.get('grade', '-')}\n"
                        f"**达成目标**　{data.get('goal_status', '-')}\n\n"
                        "下方为经营摘要。"
                    ),
                },
                {
                    "tag": "markdown",
                    "content": "**一、核心指标一览**",
                },
                {
                    "tag": "column_set",
                    "flex_mode": "trisect",
                    "background_style": "default",
                    "horizontal_spacing": "8px",
                    "columns": [
                        _metric_column(
                            "千川消耗",
                            f"¥{data['spend']}",
                            data.get("spend_diff", "N/A"),
                            higher_is_better=False,
                            bg="grey",
                        ),
                        _metric_column(
                            "成交 GMV",
                            f"¥{data['gmv']}",
                            data.get("gmv_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                        _metric_column(
                            "综合 ROI",
                            str(data["roi"]),
                            data.get("roi_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                    ],
                },
                {
                    "tag": "column_set",
                    "flex_mode": "bisect",
                    "background_style": "default",
                    "horizontal_spacing": "8px",
                    "columns": [
                        _metric_column(
                            "转化成本",
                            f"¥{data.get('cpa', '-')}",
                            data.get("cpa_diff", "N/A"),
                            higher_is_better=False,
                            bg="grey",
                        ),
                        _metric_column(
                            "评级",
                            str(data.get("grade", "-")),
                            data.get("roi_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                    ],
                },
                {
                    "tag": "markdown",
                    "content": "**二、ROI 目标进度**",
                },
                _build_progress_bar(data),
                {
                    "tag": "markdown",
                    "content": f"**三、计划表现 TOP**\n{plans_md}",
                },
                {
                    "tag": "markdown",
                    "content": f"**四、转化漏斗快照**\n{funnel_md}",
                },
                {
                    "tag": "markdown",
                    "content": "**五、智能诊断**",
                },
                _collapsible_panel(
                    element_id="panel_highlight",
                    title="✅ 亮点",
                    content=str(data.get("highlights") or "暂无明显亮点"),
                    header_color="green",
                    expanded=True,
                ),
                _collapsible_panel(
                    element_id="panel_warning",
                    title="⚠️ 预警",
                    content=str(data.get("warning") or "暂无异常预警"),
                    header_color="orange",
                    expanded=True,
                ),
                {
                    "tag": "markdown",
                    "content": f"💡 **建议**：{data.get('suggestion', '持续观察核心指标。')}",
                },
                _action_buttons(data),
                _footer_note("千川经营助手 · 数据周期：昨日 00:00-24:00"),
            ),
        },
    }
    return {"msg_type": "interactive", "card": card}


def build_weekly_card(data: dict[str, Any]) -> dict[str, Any]:
    """构建 Card JSON 2.0 周报卡片。"""
    header_color = data.get("header_color", "purple")
    daily_trend = "\n".join(
        f"• **{d['day']}**　消耗 ¥{d['spend']}　GMV ¥{d['gmv']}　ROI **{d['roi']}**　{d.get('mood', '')}"
        for d in data.get("daily_trend", [])
    ) or "_暂无每日走势_"
    ranking = "\n".join(
        f"{i}. **{p['name']}**　ROI {p['roi']}　GMV ¥{p['gmv']}　占比 {p.get('share', '-')}"
        for i, p in enumerate(data.get("top_plans", []), start=1)
    ) or "_暂无计划贡献_"
    vs_last_week = "\n".join(f"• {row}" for row in data.get("vs_last_week", [])) or "_暂无对比_"
    actions = data.get("actions") or ["持续观察核心指标。", "复盘高转化素材。", "控制异常计划预算。"]

    # 周报也复用状态标签逻辑（用 top_plans 识别爆款）
    tag_source = {
        **data,
        "plans": data.get("top_plans", []),
        "warning": data.get("summary", ""),
    }

    card: dict[str, Any] = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True,
            "update_multi": True,
            "width_mode": "fill",
        },
        "header": {
            "template": header_color,
            "title": {
                "tag": "plain_text",
                "content": f"📈 抖音千川 · 周报 | {data['week_range']}",
            },
            "subtitle": {
                "tag": "plain_text",
                "content": data.get("subtitle", "本周投放经营复盘"),
            },
            "text_tag_list": _build_status_tags(tag_source),
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 8px",
            "vertical_spacing": "8px",
            "elements": _elements(
                {
                    "tag": "markdown",
                    "content": (
                        f"**本周总评**　{data.get('grade', '-')}\n"
                        f"{data.get('summary', '')}"
                    ),
                },
                {
                    "tag": "markdown",
                    "content": "**一、本周核心汇总**",
                },
                {
                    "tag": "column_set",
                    "flex_mode": "trisect",
                    "background_style": "default",
                    "horizontal_spacing": "8px",
                    "columns": [
                        _metric_column(
                            "周消耗",
                            f"¥{data['spend']}",
                            data.get("spend_diff", "N/A"),
                            higher_is_better=False,
                            bg="grey",
                        ),
                        _metric_column(
                            "周 GMV",
                            f"¥{data['gmv']}",
                            data.get("gmv_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                        _metric_column(
                            "周均 ROI",
                            str(data["roi"]),
                            data.get("roi_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                    ],
                },
                {
                    "tag": "column_set",
                    "flex_mode": "bisect",
                    "background_style": "default",
                    "horizontal_spacing": "8px",
                    "columns": [
                        _metric_column(
                            "周均 CPA",
                            f"¥{data.get('cpa', '-')}",
                            data.get("cpa_diff", "N/A"),
                            higher_is_better=False,
                            bg="grey",
                        ),
                        _metric_column(
                            "成交订单",
                            str(data.get("orders", "-")),
                            data.get("orders_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                    ],
                },
                {
                    "tag": "markdown",
                    "content": "**二、ROI 目标进度**",
                },
                _build_progress_bar(data),
                {
                    "tag": "markdown",
                    "content": f"**三、每日走势**\n{daily_trend}",
                },
                {
                    "tag": "markdown",
                    "content": f"**四、计划贡献榜**\n{ranking}",
                },
                {
                    "tag": "markdown",
                    "content": f"**五、较上周对比**\n{vs_last_week}",
                },
                {
                    "tag": "markdown",
                    "content": "**六、诊断分区**",
                },
                _collapsible_panel(
                    element_id="week_highlight",
                    title="✅ 本周亮点",
                    content=str(data.get("highlights") or data.get("summary") or "暂无明显亮点"),
                    header_color="green",
                    expanded=True,
                ),
                _collapsible_panel(
                    element_id="week_warning",
                    title="⚠️ 风险与预警",
                    content=str(data.get("warning") or "暂无异常预警"),
                    header_color="orange",
                    expanded=True,
                ),
                {
                    "tag": "markdown",
                    "content": (
                        "**七、下周行动清单**\n"
                        f"1. {actions[0]}\n"
                        f"2. {actions[1] if len(actions) > 1 else '-'}\n"
                        f"3. {actions[2] if len(actions) > 2 else '-'}"
                    ),
                },
                _action_buttons(data),
                _footer_note("千川经营助手 · 周报周期：周一至周日"),
            ),
        },
    }
    return {"msg_type": "interactive", "card": card}


def send_card(
    card_payload: dict[str, Any], timeout: int = 10, dry_run: bool = False
) -> dict[str, Any]:
    """发送飞书卡片消息。"""
    if dry_run or config.DEBUG_MODE:
        payload_str = json.dumps(card_payload, ensure_ascii=False, indent=2)
        if len(payload_str) > 2000:
            payload_str = payload_str[:2000] + "\n...（已截断）"
        logger.info("[DEBUG] 跳过真实推送，卡片内容如下：\n%s", payload_str)
        return {"code": 0, "msg": "debug_skip", "debug": True}

    config.validate()
    url = config.FEISHU_WEBHOOK_URL

    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(card_payload),
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        logger.exception("飞书卡片推送失败：%s", exc)
        raise RuntimeError(f"飞书卡片推送失败：{exc}") from exc

    status_code = result.get("StatusCode", result.get("code"))
    if status_code not in (0, "0", None):
        raise RuntimeError(f"飞书接口返回异常：{result}")

    logger.info("飞书卡片推送成功：%s", result)
    return result


def send_daily_report(data: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """构建并发送日报。"""
    return send_card(build_daily_card(data), dry_run=dry_run)


def send_weekly_report(data: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """构建并发送周报。"""
    return send_card(build_weekly_card(data), dry_run=dry_run)


def build_monthly_card(data: dict[str, Any]) -> dict[str, Any]:
    """构建 Card JSON 2.0 月报卡片。"""
    header_color = data.get("header_color", "indigo")
    week_rows = "\n".join(
        f"• **{w['label']}**　消耗 ¥{w['spend']}　GMV ¥{w['gmv']}　ROI **{w['roi']}**"
        for w in data.get("week_breakdown", [])
    ) or "_暂无分周数据_"
    actions = data.get("actions") or ["复盘低效计划", "放大高ROI素材", "优化付费占比结构"]

    card: dict[str, Any] = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True,
            "update_multi": True,
            "width_mode": "fill",
        },
        "header": {
            "template": header_color,
            "title": {
                "tag": "plain_text",
                "content": f"📅 抖音千川 · 月报 | {data.get('month_label', '')}",
            },
            "subtitle": {
                "tag": "plain_text",
                "content": data.get("subtitle", "本月投放经营复盘"),
            },
            "text_tag_list": _build_status_tags(
                {
                    **data,
                    "plans": data.get("top_plans", []),
                    "warning": data.get("warning", ""),
                }
            ),
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 8px",
            "vertical_spacing": "8px",
            "elements": _elements(
                {
                    "tag": "markdown",
                    "content": (
                        f"**本月总评**　{data.get('grade', '-')}\n"
                        f"{data.get('summary', '')}"
                    ),
                },
                {"tag": "markdown", "content": "**一、本月核心汇总**"},
                {
                    "tag": "column_set",
                    "flex_mode": "trisect",
                    "horizontal_spacing": "8px",
                    "columns": [
                        _metric_column(
                            "月消耗",
                            f"¥{data['spend']}",
                            data.get("spend_diff", "N/A"),
                            higher_is_better=False,
                            bg="grey",
                        ),
                        _metric_column(
                            "月 GMV",
                            f"¥{data['gmv']}",
                            data.get("gmv_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                        _metric_column(
                            "月均 ROI",
                            str(data["roi"]),
                            data.get("roi_diff", "N/A"),
                            higher_is_better=True,
                            bg="grey",
                        ),
                    ],
                },
                {"tag": "markdown", "content": "**二、ROI 目标进度**"},
                _build_progress_bar(data),
                {"tag": "markdown", "content": f"**三、分周走势**\n{week_rows}"},
                {
                    "tag": "markdown",
                    "content": (
                        f"**四、经营建议**\n"
                        f"1. {actions[0]}\n"
                        f"2. {actions[1] if len(actions) > 1 else '-'}\n"
                        f"3. {actions[2] if len(actions) > 2 else '-'}"
                    ),
                },
                _collapsible_panel(
                    element_id="month_highlight",
                    title="✅ 本月亮点",
                    content=str(data.get("highlights") or "暂无明显亮点"),
                    header_color="green",
                    expanded=True,
                ),
                _collapsible_panel(
                    element_id="month_warning",
                    title="⚠️ 风险与预警",
                    content=str(data.get("warning") or "暂无异常预警"),
                    header_color="orange",
                    expanded=True,
                ),
                _action_buttons(data),
                _footer_note("千川经营助手 · 月报周期：近 30 天"),
            ),
        },
    }
    return {"msg_type": "interactive", "card": card}


def send_monthly_report(data: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """构建并发送月报。"""
    return send_card(build_monthly_card(data), dry_run=dry_run)
