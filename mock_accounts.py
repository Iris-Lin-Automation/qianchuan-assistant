"""
用于演示的“多账号/多店铺”配置。

实际项目中，这些配置通常来自：
- 你的业务系统数据库（店铺/账号映射）
- 或配置中心（例如 .env、yaml、后台管理页面）
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountConfig:
    """千川账户配置（演示用）。"""

    account_id: str
    account_name: str


@dataclass(frozen=True)
class StoreConfig:
    """抖店配置（演示用）。"""

    store_id: str
    store_name: str
    qianchuan_accounts: list[AccountConfig]
    roi_goal: float


def get_demo_store_configs() -> list[StoreConfig]:
    """返回 2 个抖店 + 每个抖店多个千川账户。"""

    return [
        StoreConfig(
            store_id="STORE_001",
            store_name="小野茶语旗舰店",
            roi_goal=2.50,
            qianchuan_accounts=[
                AccountConfig(account_id="QC_1001", account_name="千川账号-主投"),
                AccountConfig(account_id="QC_1002", account_name="千川账号-精细化"),
                AccountConfig(account_id="QC_1003", account_name="千川账号-测款"),
            ],
        ),
        StoreConfig(
            store_id="STORE_002",
            store_name="夏日轻茶旗舰店",
            roi_goal=2.30,
            qianchuan_accounts=[
                AccountConfig(account_id="QC_2001", account_name="千川账号-全店智投"),
                AccountConfig(account_id="QC_2002", account_name="千川账号-人群扩量"),
            ],
        ),
    ]

