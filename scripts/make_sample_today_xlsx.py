"""生成影刀对接用的样例 Excel：data/today.xlsx"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "today.xlsx"


def main() -> None:
    try:
        import pandas as pd
    except ImportError:
        raise SystemExit("请先：pip install pandas openpyxl")

    today = date.today()
    yesterday = today - timedelta(days=1)

    rows = [
        # 昨日（用于环比）
        {
            "日期": yesterday.isoformat(),
            "店铺ID": "STORE_001",
            "店铺名称": "小野茶语旗舰店",
            "计划名称": "计划B-爆款种草",
            "消耗": 6800,
            "展现": 2100000,
            "点击": 72000,
            "订单": 190,
            "GMV": 22800,
            "其他渠道消耗": 5200,
            "ROI目标": 2.5,
        },
        {
            "日期": yesterday.isoformat(),
            "店铺ID": "STORE_001",
            "店铺名称": "小野茶语旗舰店",
            "计划名称": "计划D-素材测试",
            "消耗": 2100,
            "展现": 480000,
            "点击": 12000,
            "订单": 28,
            "GMV": 3100,
            "其他渠道消耗": 0,
            "ROI目标": 2.5,
        },
        {
            "日期": yesterday.isoformat(),
            "店铺ID": "STORE_002",
            "店铺名称": "夏日轻茶旗舰店",
            "计划名称": "计划A-全店智投",
            "消耗": 9200,
            "展现": 1800000,
            "点击": 54000,
            "订单": 150,
            "GMV": 19800,
            "其他渠道消耗": 4100,
            "ROI目标": 2.3,
        },
        # 今日
        {
            "日期": today.isoformat(),
            "店铺ID": "STORE_001",
            "店铺名称": "小野茶语旗舰店",
            "计划名称": "计划B-爆款种草",
            "消耗": 7240,
            "展现": 2300000,
            "点击": 81000,
            "订单": 220,
            "GMV": 24860,
            "其他渠道消耗": 5600,
            "ROI目标": 2.5,
        },
        {
            "日期": today.isoformat(),
            "店铺ID": "STORE_001",
            "店铺名称": "小野茶语旗舰店",
            "计划名称": "计划A-新品冷启",
            "消耗": 4180,
            "展现": 980000,
            "点击": 31000,
            "订单": 95,
            "GMV": 11920,
            "其他渠道消耗": 0,
            "ROI目标": 2.5,
        },
        {
            "日期": today.isoformat(),
            "店铺ID": "STORE_001",
            "店铺名称": "小野茶语旗舰店",
            "计划名称": "计划D-素材测试",
            "消耗": 2202,
            "展现": 520000,
            "点击": 14000,
            "订单": 26,
            "GMV": 3250,
            "其他渠道消耗": 0,
            "ROI目标": 2.5,
        },
        {
            "日期": today.isoformat(),
            "店铺ID": "STORE_002",
            "店铺名称": "夏日轻茶旗舰店",
            "计划名称": "计划A-全店智投",
            "消耗": 10120,
            "展现": 1950000,
            "点击": 61000,
            "订单": 168,
            "GMV": 23600,
            "其他渠道消耗": 4300,
            "ROI目标": 2.3,
        },
        {
            "日期": today.isoformat(),
            "店铺ID": "STORE_002",
            "店铺名称": "夏日轻茶旗舰店",
            "计划名称": "计划C-人群扩量",
            "消耗": 5300,
            "展现": 1100000,
            "点击": 29000,
            "订单": 88,
            "GMV": 12100,
            "其他渠道消耗": 0,
            "ROI目标": 2.3,
        },
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(OUT, index=False, engine="openpyxl")
    # 兼容别名
    alt = ROOT / "data" / "qianchuan_today.xlsx"
    pd.DataFrame(rows).to_excel(alt, index=False, engine="openpyxl")
    print(f"OK -> {OUT}")
    print(f"OK -> {alt}")


if __name__ == "__main__":
    main()
