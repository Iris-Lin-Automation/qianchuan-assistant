"""
飞书可视化数据同步层。

1) 始终写入本地「仪表盘数据源」CSV/JSON（可手工导入多维表格）
2) 生成本地 HTML 可视化看板（柱状/折线/漏斗，演示与验收用）
3) 若配置了飞书应用凭证，则通过 OpenAPI 写入多维表格（方案 A）
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Iterable

from cleaner import StoreDayMetrics
from config import config
from feishu_bitable import FeishuBitableClient, metrics_to_bitable_fields

logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent / "data"
CSV_PATH = OUT_DIR / "bitable_daily_metrics.csv"
JSON_PATH = OUT_DIR / "bitable_daily_metrics.json"
HTML_PATH = OUT_DIR / "dashboard.html"


def _grade_from_roi(roi: float, goal: float = 2.5) -> str:
    if roi >= goal * 1.1:
        return "A"
    if roi >= goal:
        return "B+"
    if roi >= goal * 0.9:
        return "B"
    return "C"


def metrics_to_rows(metrics_list: Iterable[StoreDayMetrics]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for m in metrics_list:
        rows.append(
            {
                "dt": m.dt.isoformat(),
                "store_id": m.store_id,
                "store_name": m.store_name,
                "spend": round(m.spend, 2),
                "gmv": round(m.gmv, 2),
                "roi": round(m.roi, 4),
                "cpa": round(m.cpa, 4),
                "paid_share": round(m.paid_share, 4),
                "impressions": m.impressions,
                "clicks": m.clicks,
                "orders": m.orders,
                "ctr": round(m.ctr, 6),
                "refund_rate": round(m.refund_rate, 6),
                "grade": _grade_from_roi(m.roi),
            }
        )
    return rows


def _write_local_files(rows: list[dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    # 追加合并：同店同日覆盖，保留历史方便图表
    existing: dict[tuple[str, str], dict[str, Any]] = {}
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                existing[(r["dt"], r["store_id"])] = {
                    "dt": r["dt"],
                    "store_id": r["store_id"],
                    "store_name": r["store_name"],
                    "spend": float(r.get("spend") or 0),
                    "gmv": float(r.get("gmv") or 0),
                    "roi": float(r.get("roi") or 0),
                    "cpa": float(r.get("cpa") or 0),
                    "paid_share": float(r.get("paid_share") or 0),
                    "impressions": int(float(r.get("impressions") or 0)),
                    "clicks": int(float(r.get("clicks") or 0)),
                    "orders": int(float(r.get("orders") or 0)),
                    "ctr": float(r.get("ctr") or 0),
                    "refund_rate": float(r.get("refund_rate") or 0),
                    "grade": r.get("grade") or "",
                }

    for r in rows:
        existing[(r["dt"], r["store_id"])] = r

    merged = sorted(existing.values(), key=lambda x: (x["dt"], x["store_id"]))
    fieldnames = list(rows[0].keys())
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in merged:
            writer.writerow(r)

    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    _render_html_dashboard(merged)
    logger.info("本地仪表盘数据已更新：%s / %s / %s", CSV_PATH.name, JSON_PATH.name, HTML_PATH.name)


def _render_html_dashboard(rows: list[dict[str, Any]]) -> None:
    """生成可直接打开的本地可视化看板（Chart.js）。"""
    payload = json.dumps(rows, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>千川经营可视化仪表盘</title>
  <script src="vendor/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --text: #e8eef7;
      --muted: #8b9bb4;
      --accent: #3d8bfd;
      --good: #3dd68c;
      --warn: #f5a524;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1b3a5f 0%, var(--bg) 55%);
      color: var(--text);
    }}
    header {{
      padding: 28px 32px 8px; display: flex; justify-content: space-between; align-items: end;
    }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0.5px; }}
    .sub {{ color: var(--muted); margin-top: 8px; }}
    .kpis {{
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
      padding: 16px 32px 8px;
    }}
    .kpi {{
      background: linear-gradient(180deg, #223149, var(--panel));
      border: 1px solid #2b3b55; border-radius: 14px; padding: 16px 18px;
    }}
    .kpi .label {{ color: var(--muted); font-size: 13px; }}
    .kpi .value {{ font-size: 26px; font-weight: 700; margin-top: 8px; }}
    .grid {{
      display: grid; grid-template-columns: 1.2fr 1fr; gap: 14px;
      padding: 12px 32px 32px;
    }}
    .card {{
      background: var(--panel); border: 1px solid #2b3b55; border-radius: 14px;
      padding: 14px 16px 8px; min-height: 320px;
    }}
    .card h3 {{ margin: 4px 0 10px; font-size: 15px; color: #c9d7ea; font-weight: 600; }}
    canvas {{ width: 100% !important; max-height: 280px; }}
    @media (max-width: 980px) {{
      .kpis, .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>千川 / 抖店经营仪表盘</h1>
      <div class="sub">数据自动同步后渲染 · 可导入飞书多维表格做官方仪表盘</div>
    </div>
    <div class="sub" id="updated"></div>
  </header>
  <section class="kpis">
    <div class="kpi"><div class="label">总消耗</div><div class="value" id="kpiSpend">-</div></div>
    <div class="kpi"><div class="label">总 GMV</div><div class="value" id="kpiGmv">-</div></div>
    <div class="kpi"><div class="label">综合 ROI</div><div class="value" id="kpiRoi">-</div></div>
    <div class="kpi"><div class="label">订单量</div><div class="value" id="kpiOrders">-</div></div>
  </section>
  <section class="grid">
    <div class="card"><h3>GMV / 消耗趋势</h3><canvas id="trend"></canvas></div>
    <div class="card"><h3>店铺 ROI 对比</h3><canvas id="roiBar"></canvas></div>
    <div class="card"><h3>转化漏斗（汇总）</h3><canvas id="funnel"></canvas></div>
    <div class="card"><h3>付费占比</h3><canvas id="paid"></canvas></div>
  </section>
  <script>
    if (typeof Chart === 'undefined') {{
      document.body.insertAdjacentHTML('afterbegin',
        '<div style="margin:16px 32px;padding:12px 14px;border-radius:10px;background:#3a1d1d;border:1px solid #7a3030;color:#ffd0d0;">图表库未加载：请确认同目录存在 data/vendor/chart.umd.min.js</div>');
    }}
    const rows = {payload};
    const money = (n) => '¥' + Number(n).toLocaleString('zh-CN', {{maximumFractionDigits: 0}});
    const byDate = {{}};
    const byStore = {{}};
    let spend=0,gmv=0,orders=0,impr=0,clicks=0;
    for (const r of rows) {{
      const d = r.dt;
      if (!byDate[d]) byDate[d] = {{spend:0,gmv:0}};
      byDate[d].spend += Number(r.spend);
      byDate[d].gmv += Number(r.gmv);
      if (!byStore[r.store_name]) byStore[r.store_name] = {{spend:0,gmv:0,paid:0,n:0}};
      byStore[r.store_name].spend += Number(r.spend);
      byStore[r.store_name].gmv += Number(r.gmv);
      byStore[r.store_name].paid += Number(r.paid_share);
      byStore[r.store_name].n += 1;
      spend += Number(r.spend); gmv += Number(r.gmv); orders += Number(r.orders);
      impr += Number(r.impressions); clicks += Number(r.clicks);
    }}
    const roi = spend ? gmv/spend : 0;
    document.getElementById('kpiSpend').textContent = money(spend);
    document.getElementById('kpiGmv').textContent = money(gmv);
    document.getElementById('kpiRoi').textContent = roi.toFixed(2);
    document.getElementById('kpiOrders').textContent = orders.toLocaleString();
    document.getElementById('updated').textContent = '记录数 ' + rows.length;

    const dates = Object.keys(byDate).sort();
    new Chart(document.getElementById('trend'), {{
      type: 'line',
      data: {{
        labels: dates,
        datasets: [
          {{ label: 'GMV', data: dates.map(d => byDate[d].gmv), borderColor: '#3dd68c', tension: 0.35 }},
          {{ label: '消耗', data: dates.map(d => byDate[d].spend), borderColor: '#3d8bfd', tension: 0.35 }}
        ]
      }},
      options: {{ plugins: {{ legend: {{ labels: {{ color: '#c9d7ea' }} }} }}, scales: {{
        x: {{ ticks: {{ color: '#8b9bb4' }}, grid: {{ color: '#243247' }} }},
        y: {{ ticks: {{ color: '#8b9bb4' }}, grid: {{ color: '#243247' }} }}
      }} }}
    }});

    const stores = Object.keys(byStore);
    new Chart(document.getElementById('roiBar'), {{
      type: 'bar',
      data: {{
        labels: stores,
        datasets: [{{
          label: 'ROI',
          data: stores.map(s => byStore[s].spend ? byStore[s].gmv/byStore[s].spend : 0),
          backgroundColor: '#3d8bfd'
        }}]
      }},
      options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{
        x: {{ ticks: {{ color: '#8b9bb4' }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ color: '#8b9bb4' }}, grid: {{ color: '#243247' }} }}
      }} }}
    }});

    const sessions = Math.round(clicks * 0.5);
    new Chart(document.getElementById('funnel'), {{
      type: 'bar',
      data: {{
        labels: ['展现', '点击', '进店(估)', '订单'],
        datasets: [{{
          data: [impr, clicks, sessions, orders],
          backgroundColor: ['#5b8def', '#3d8bfd', '#35c2ff', '#3dd68c']
        }}]
      }},
      options: {{ indexAxis: 'y', plugins: {{ legend: {{ display: false }} }}, scales: {{
        x: {{ ticks: {{ color: '#8b9bb4' }}, grid: {{ color: '#243247' }} }},
        y: {{ ticks: {{ color: '#c9d7ea' }}, grid: {{ display: false }} }}
      }} }}
    }});

    new Chart(document.getElementById('paid'), {{
      type: 'doughnut',
      data: {{
        labels: stores,
        datasets: [{{
          data: stores.map(s => byStore[s].n ? byStore[s].paid/byStore[s].n : 0),
          backgroundColor: ['#3d8bfd', '#3dd68c', '#f5a524', '#a78bfa']
        }}]
      }},
      options: {{ plugins: {{ legend: {{ labels: {{ color: '#c9d7ea' }} }} }} }}
    }});
  </script>
</body>
</html>
"""
    HTML_PATH.write_text(html, encoding="utf-8")


def sync_daily_metrics(
    metrics_list: Iterable[StoreDayMetrics],
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    同步日指标：
    - 永远更新本地 CSV/JSON/HTML 仪表盘
    - dry_run=False 且 API 已配置时，写入飞书多维表格
    """
    rows = metrics_to_rows(metrics_list)
    _write_local_files(rows)

    result: dict[str, Any] = {
        "local_csv": str(CSV_PATH),
        "local_html": str(HTML_PATH),
        "bitable": None,
    }

    client = FeishuBitableClient()
    if dry_run:
        logger.info(
            "多维表格同步 dry_run：已生成本地看板。配置 APP 凭证后可自动写入飞书。"
        )
        if rows:
            logger.info("字段示例：%s", metrics_to_bitable_fields(rows[0]))
        return result

    if not client.configured:
        logger.warning(
            "未配置 FEISHU_APP_ID/SECRET/BITABLE_APP_TOKEN/TABLE_ID，跳过云端写入；"
            "可先把 %s 导入多维表格。",
            CSV_PATH,
        )
        return result

    fields_list = [metrics_to_bitable_fields(r) for r in rows]
    api_result = client.batch_create(fields_list)
    result["bitable"] = api_result
    return result
