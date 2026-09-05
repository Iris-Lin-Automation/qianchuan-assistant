"""
飞书多维表格（Bitable）OpenAPI 客户端。

写入日指标记录，供飞书仪表盘生成柱状图 / 折线图 / 漏斗图。
配置齐全时真实写入；否则仅由上层模块写本地预览。
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

import requests

from config import config

logger = logging.getLogger(__name__)

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
BATCH_CREATE_URL = (
    "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
)


class FeishuBitableClient:
    """飞书多维表格写入客户端。"""

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
        app_token: str | None = None,
        table_id: str | None = None,
    ) -> None:
        self.app_id = (app_id or config.FEISHU_APP_ID).strip()
        self.app_secret = (app_secret or config.FEISHU_APP_SECRET).strip()
        self.app_token = (app_token or config.FEISHU_BITABLE_APP_TOKEN).strip()
        self.table_id = (table_id or config.FEISHU_BITABLE_TABLE_ID).strip()
        self._token: str | None = None
        self._token_expire_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret and self.app_token and self.table_id)

    def get_tenant_access_token(self) -> str:
        if self._token and time.time() < self._token_expire_at - 60:
            return self._token

        resp = requests.post(
            TOKEN_URL,
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败：{data}")
        self._token = data["tenant_access_token"]
        self._token_expire_at = time.time() + int(data.get("expire", 7200))
        return self._token

    def batch_create(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("多维表格 API 未配置完整（APP_ID/SECRET/APP_TOKEN/TABLE_ID）")
        if not records:
            return {"code": 0, "msg": "empty"}

        token = self.get_tenant_access_token()
        url = BATCH_CREATE_URL.format(app_token=self.app_token, table_id=self.table_id)
        payload = {"records": [{"fields": r} for r in records]}
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != 0:
            raise RuntimeError(f"多维表格写入失败：{result}")
        logger.info("多维表格写入成功：%s 条", len(records))
        return result


def metrics_to_bitable_fields(row: dict[str, Any]) -> dict[str, Any]:
    """
    转为飞书多维表格字段（中文列名，便于仪表盘直接选用）。

    请在多维表格中建同名列：
    日期(日期) / 店铺名称(文本) / 千川消耗(数字) / 成交GMV(数字) /
    综合ROI(数字) / 转化成本CPA(数字) / 付费占比(数字) /
    展现量 / 点击量 / 订单量 / CTR / 退款率 / 评级(文本)
    """
    dt = row.get("dt")
    if isinstance(dt, date) and not isinstance(dt, datetime):
        ts_ms = int(datetime(dt.year, dt.month, dt.day).timestamp() * 1000)
        dt_text = dt.isoformat()
    elif isinstance(dt, str):
        d = date.fromisoformat(dt[:10])
        ts_ms = int(datetime(d.year, d.month, d.day).timestamp() * 1000)
        dt_text = d.isoformat()
    else:
        ts_ms = int(time.time() * 1000)
        dt_text = datetime.now().date().isoformat()

    return {
        "日期": ts_ms,
        "日期文本": dt_text,
        "店铺ID": str(row.get("store_id", "")),
        "店铺名称": str(row.get("store_name", "")),
        "千川消耗": float(row.get("spend", 0)),
        "成交GMV": float(row.get("gmv", 0)),
        "综合ROI": float(row.get("roi", 0)),
        "转化成本CPA": float(row.get("cpa", 0)),
        "付费占比": float(row.get("paid_share", 0)),
        "展现量": int(row.get("impressions", 0)),
        "点击量": int(row.get("clicks", 0)),
        "订单量": int(row.get("orders", 0)),
        "CTR": float(row.get("ctr", 0)),
        "退款率": float(row.get("refund_rate", 0)),
        "评级": str(row.get("grade", "")),
    }
