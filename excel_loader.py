"""
读取影刀 RPA 导出的 Excel，转为店铺日指标。

约定（推荐影刀另存为）：
  ./data/today.xlsx

支持两种表结构（自动识别）：
1) 计划明细行：含「计划名称」列
2) 店铺汇总行：仅店铺级消耗/GMV 等

列名支持常见别名（千川后台导出中英文混用）。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cleaner import StoreDayMetrics

logger = logging.getLogger(__name__)

# 标准列 -> 可能别名
COLUMN_ALIASES: dict[str, list[str]] = {
    "dt": ["日期", "统计日期", "数据日期", "date", "日"],
    "store_id": ["店铺ID", "店铺id", "store_id", "店铺编码"],
    "store_name": ["店铺名称", "店铺", "店名", "store_name", "商家名称"],
    "account": ["千川账户", "账户", "广告主", "账户名称"],
    "plan_name": ["计划名称", "计划", "广告计划", "plan_name"],
    "spend": ["消耗", "千川消耗", "花费", "广告消耗", "spend", "总消耗"],
    "impressions": ["展现", "展示", "曝光", "展现量", "impressions", "展示数"],
    "clicks": ["点击", "点击量", "clicks", "点击数"],
    "orders": ["订单", "成交订单", "订单量", "转化数", "orders", "成交笔数"],
    "gmv": ["GMV", "成交金额", "支付金额", "成交GMV", "gmv", "销售额"],
    "other_spend": ["其他渠道消耗", "非千川消耗", "自然流量成本", "other_spend"],
    "roi_goal": ["ROI目标", "目标ROI", "roi_goal"],
}


@dataclass
class ExcelStoreBundle:
    """单个店铺：今日指标 + 可选昨日对照。"""

    today: StoreDayMetrics
    previous: StoreDayMetrics | None = None
    roi_goal: float = 2.5


def _norm_header(name: Any) -> str:
    text = str(name or "").strip().lower()
    text = text.replace(" ", "").replace("_", "").replace("\n", "")
    return text


def _build_header_map(columns: list[Any]) -> dict[str, str]:
    """标准字段名 -> 实际列名。"""
    normalized = {_norm_header(c): c for c in columns}
    mapping: dict[str, str] = {}
    for std, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _norm_header(alias)
            if key in normalized:
                mapping[std] = normalized[key]
                break
    return mapping


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("¥", "").replace("%", "")
    if text == "" or text.lower() in {"nan", "none", "-"}:
        return default
    try:
        return float(text)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(m.group()) if m else default


def _to_int(value: Any, default: int = 0) -> int:
    return int(round(_to_float(value, float(default))))


def _parse_date(value: Any, fallback: date | None = None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None or str(value).strip() == "":
        return fallback or date.today()
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return fallback or date.today()


def _row_get(row: dict[str, Any], header_map: dict[str, str], key: str, default: Any = None) -> Any:
    col = header_map.get(key)
    if col is None:
        return default
    return row.get(col, default)


def _metrics_from_agg(
    *,
    store_id: str,
    store_name: str,
    dt: date,
    spend: float,
    gmv: float,
    impressions: int,
    clicks: int,
    orders: int,
    other_spend: float,
    plans: list[dict],
) -> StoreDayMetrics:
    roi = gmv / spend if spend > 0 else 0.0
    cpa = spend / orders if orders > 0 else 0.0
    total = spend + max(other_spend, 0.0)
    paid_share = spend / total if total > 0 else 1.0
    ctr = clicks / impressions if impressions > 0 else 0.0
    session_rate = 0.45
    sessions = clicks * session_rate
    conversion_rate = orders / sessions if sessions > 0 else 0.0
    refund_rate = 0.06

    # top plans by gmv
    top = sorted(plans, key=lambda p: float(p.get("gmv", 0)), reverse=True)[:4]
    top_plans = []
    for i, p in enumerate(top, start=1):
        share = float(p["gmv"]) / gmv if gmv > 0 else 0.0
        top_plans.append(
            {
                "name": p["name"],
                "spend": float(p["spend"]),
                "gmv": float(p["gmv"]),
                "roi": float(p["gmv"]) / float(p["spend"]) if float(p["spend"]) > 0 else 0.0,
                "share": f"{share * 100:.1f}%",
                "rank": i,
            }
        )

    return StoreDayMetrics(
        store_id=store_id,
        store_name=store_name,
        dt=dt,
        spend=float(spend),
        impressions=int(impressions),
        clicks=int(clicks),
        orders=int(orders),
        gmv=float(gmv),
        roi=float(roi),
        cpa=float(cpa),
        paid_share=float(paid_share),
        ctr=float(ctr),
        session_rate=float(session_rate),
        conversion_rate=float(conversion_rate),
        refund_rate=float(refund_rate),
        top_plans=top_plans,
    )


def load_excel_store_metrics(
    file_path: str | Path,
    *,
    report_date: date | None = None,
) -> list[ExcelStoreBundle]:
    """
    读取影刀导出的 Excel，按店铺聚合为 StoreDayMetrics。

    若同一文件含多日，取 report_date（默认文件内最新日 / 今天）。
    若存在前一日数据，自动填充 previous 用于环比。
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("请先安装 pandas/openpyxl：pip install pandas openpyxl") from exc

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到影刀导出文件：{path}")

    # 读第一个工作表
    df = pd.read_excel(path, engine="openpyxl")
    if df.empty:
        raise ValueError(f"Excel 无数据：{path}")

    header_map = _build_header_map(list(df.columns))
    required = ["spend", "gmv"]
    missing = [k for k in required if k not in header_map]
    if missing:
        raise ValueError(
            f"Excel 缺少必要列（或无法识别别名）：{missing}。"
            f"当前列={list(df.columns)}。"
            "请按 docs/影刀RPA对接说明.md 的模板导出。"
        )

    rows = df.to_dict(orient="records")
    # 解析所有行到按 (store, dt) 聚合
    buckets: dict[tuple[str, str, date], dict[str, Any]] = {}

    for raw in rows:
        store_name = str(_row_get(raw, header_map, "store_name", "默认店铺") or "默认店铺").strip()
        store_id = str(_row_get(raw, header_map, "store_id", "") or "").strip()
        if not store_id:
            store_id = f"STORE_{abs(hash(store_name)) % 100000:05d}"

        dt = _parse_date(_row_get(raw, header_map, "dt"), fallback=report_date or date.today())
        key = (store_id, store_name, dt)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "store_id": store_id,
                "store_name": store_name,
                "dt": dt,
                "spend": 0.0,
                "gmv": 0.0,
                "impressions": 0,
                "clicks": 0,
                "orders": 0,
                "other_spend": 0.0,
                "roi_goal": _to_float(_row_get(raw, header_map, "roi_goal"), 2.5),
                "plans": [],
            }
            buckets[key] = bucket

        spend = _to_float(_row_get(raw, header_map, "spend"))
        gmv = _to_float(_row_get(raw, header_map, "gmv"))
        impressions = _to_int(_row_get(raw, header_map, "impressions"))
        clicks = _to_int(_row_get(raw, header_map, "clicks"))
        orders = _to_int(_row_get(raw, header_map, "orders"))
        other_spend = _to_float(_row_get(raw, header_map, "other_spend"))

        bucket["spend"] += spend
        bucket["gmv"] += gmv
        bucket["impressions"] += impressions
        bucket["clicks"] += clicks
        bucket["orders"] += orders
        bucket["other_spend"] += other_spend

        plan_name = _row_get(raw, header_map, "plan_name")
        if plan_name and str(plan_name).strip():
            bucket["plans"].append(
                {
                    "name": str(plan_name).strip(),
                    "spend": spend,
                    "gmv": gmv,
                }
            )

    if not buckets:
        raise ValueError("未能从 Excel 解析出任何店铺数据")

    # 按店铺分组日期
    by_store: dict[str, list[dict[str, Any]]] = {}
    for (_sid, _sname, _dt), b in buckets.items():
        by_store.setdefault(_sid, []).append(b)

    bundles: list[ExcelStoreBundle] = []
    for store_id, items in by_store.items():
        items_sorted = sorted(items, key=lambda x: x["dt"])
        # 目标日：指定日 / 最新日
        if report_date is not None:
            today_item = next((x for x in items_sorted if x["dt"] == report_date), items_sorted[-1])
        else:
            today_item = items_sorted[-1]

        prev_item = None
        for x in reversed(items_sorted):
            if x["dt"] < today_item["dt"]:
                prev_item = x
                break

        today_m = _metrics_from_agg(
            store_id=today_item["store_id"],
            store_name=today_item["store_name"],
            dt=today_item["dt"],
            spend=today_item["spend"],
            gmv=today_item["gmv"],
            impressions=today_item["impressions"],
            clicks=today_item["clicks"],
            orders=today_item["orders"],
            other_spend=today_item["other_spend"],
            plans=today_item["plans"],
        )
        prev_m = None
        if prev_item is not None:
            prev_m = _metrics_from_agg(
                store_id=prev_item["store_id"],
                store_name=prev_item["store_name"],
                dt=prev_item["dt"],
                spend=prev_item["spend"],
                gmv=prev_item["gmv"],
                impressions=prev_item["impressions"],
                clicks=prev_item["clicks"],
                orders=prev_item["orders"],
                other_spend=prev_item["other_spend"],
                plans=prev_item["plans"],
            )

        bundles.append(
            ExcelStoreBundle(
                today=today_m,
                previous=prev_m,
                roi_goal=float(today_item.get("roi_goal") or 2.5),
            )
        )

    logger.info("Excel 解析完成：%s，店铺数=%s", path, len(bundles))
    return bundles


# 供外部复用
__all__ = ["ExcelStoreBundle", "load_excel_store_metrics"]
