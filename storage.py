"""
数据入库（演示版）。

真实系统中这里会写入：
- 飞书多维表格（作为“可视化数据源”）
- 或者你的数仓/数据库（PostgreSQL / ClickHouse / BigQuery 等）

在当前演示目标下，我们用本地 SQLite 落库，便于回溯并支撑“日报/周报”计算。
同时提供一个简单的导出函数，模拟“同步到飞书多维表格”。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from cleaner import StoreDayMetrics


DB_PATH = Path(__file__).resolve().parent / "data" / "qianchuan_analytics.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS store_day_metrics (
                dt TEXT NOT NULL,
                store_id TEXT NOT NULL,
                store_name TEXT NOT NULL,
                spend REAL NOT NULL,
                impressions INTEGER NOT NULL,
                clicks INTEGER NOT NULL,
                orders INTEGER NOT NULL,
                gmv REAL NOT NULL,
                roi REAL NOT NULL,
                cpa REAL NOT NULL,
                paid_share REAL NOT NULL,
                ctr REAL NOT NULL,
                refund_rate REAL NOT NULL,
                raw_json TEXT,
                PRIMARY KEY (dt, store_id)
            )
            """
        )


def upsert_store_day_metrics(
    metrics: StoreDayMetrics, raw_snapshot: dict[str, Any] | None = None
) -> None:
    """将聚合后的店铺日指标写入 SQLite（带 upsert）。"""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO store_day_metrics (
                dt, store_id, store_name, spend, impressions, clicks, orders, gmv,
                roi, cpa, paid_share, ctr, refund_rate, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dt, store_id) DO UPDATE SET
                store_name=excluded.store_name,
                spend=excluded.spend,
                impressions=excluded.impressions,
                clicks=excluded.clicks,
                orders=excluded.orders,
                gmv=excluded.gmv,
                roi=excluded.roi,
                cpa=excluded.cpa,
                paid_share=excluded.paid_share,
                ctr=excluded.ctr,
                refund_rate=excluded.refund_rate,
                raw_json=excluded.raw_json
            """,
            (
                metrics.dt.isoformat(),
                metrics.store_id,
                metrics.store_name,
                metrics.spend,
                metrics.impressions,
                metrics.clicks,
                metrics.orders,
                metrics.gmv,
                metrics.roi,
                metrics.cpa,
                metrics.paid_share,
                metrics.ctr,
                metrics.refund_rate,
                json.dumps(raw_snapshot, ensure_ascii=False) if raw_snapshot is not None else None,
            ),
        )


def query_store_day_metrics(dt: str, store_id: str) -> StoreDayMetrics | None:
    """从本地数据库查询单店铺日指标（用于计算环比/同比）。"""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT dt, store_id, store_name, spend, impressions, clicks, orders, gmv,
                   roi, cpa, paid_share, ctr, refund_rate
            FROM store_day_metrics
            WHERE dt=? AND store_id=?
            """,
            (dt, store_id),
        ).fetchone()
        if row is None:
            return None

        (
            dt_s,
            _store_id,
            store_name,
            spend,
            impressions,
            clicks,
            orders,
            gmv,
            roi,
            cpa,
            paid_share,
            ctr,
            refund_rate,
        ) = row

        # session_rate / conversion_rate / top_plans 在查询时不强依赖，这里用占位估计
        # 用于“出示日报/周报”已足够；真实系统可从原始数据补全。
        return StoreDayMetrics(
            store_id=_store_id,
            store_name=store_name,
            dt=date.fromisoformat(dt_s),
            spend=float(spend),
            impressions=int(impressions),
            clicks=int(clicks),
            orders=int(orders),
            gmv=float(gmv),
            roi=float(roi),
            cpa=float(cpa),
            paid_share=float(paid_share),
            ctr=float(ctr),
            session_rate=0.45,
            conversion_rate=(float(orders) / max(1.0, float(clicks) * 0.45)) if clicks else 0.0,
            refund_rate=float(refund_rate),
            top_plans=[],
        )

