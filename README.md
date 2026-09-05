# 千川/抖店 × 飞书自动化经营日报（即买即用版）

每天早上自动：多账号采集 → 清洗算 ROI → 群里推送交互式卡片（可选本地看板）。

## 极简交付（推荐）

如果你只想快速交付客户，不折腾插件，直接走这条：

1. `一键安装依赖.bat`
2. `启动控制台.bat`（填 Webhook）
3. `影刀调用Python.bat`（影刀最后一步调用）

补充：
- 一键演示：`一键极简演示.bat`
- 客户说明：`客户只看这个_极简版.md`

## 小白用户怎么用

1. 双击 `一键安装依赖.bat`
2. 双击 `启动控制台.bat`
3. 填入飞书 Webhook → 保存 → 立即推送日报
4. 安装「每天 08:00」定时任务，电脑挂机即可

### 影刀全自动（推荐生产）

详见 `docs/影刀RPA对接说明.md`：

1. 影刀 08:00 导出 Excel → `data/today.xlsx`
2. 影刀最后一步运行 `影刀调用Python.bat`
3. 等价命令：`python main.py --file ./data/today.xlsx`

### 客户包 vs 飞书插件开发（插件是可选）

见 `docs/交付边界_客户包与开发插件.md` 与 `extension/README.md`

```
qianchuan-feishu-analytics/
├── extension/          ← 飞书数据表视图插件（本仓库内一起改）
├── main.py
├── app_gui.py
└── 影刀调用Python.bat
```

- 客户：`scripts\pack_customer.ps1`（默认不含 extension / node_modules）  
- 插件调试：`cd extension\dashboard` → `npm install` → `npm run start`

详细图文：`docs/用户使用手册.md`  
仪表盘方案 A：`docs/多维表格仪表盘配置指南.md`  
交付话术/SOP：`docs/交付说明.md`  
拍案例视频：`docs/录屏脚本.md`

## 能力对照（客户需求）

| 需求 | 状态 |
|------|------|
| 定时触发（早 8:00） | ✅ Windows 任务计划 + 控制台一键安装 |
| 挂机运行 | ✅ worker 静默任务 + 日志 |
| 静默采集编排 | ✅ `rpa_runner.py`（演示可录屏；正式可接真实 RPA） |
| 计算综合 ROI / 付费占比 | ✅ `cleaner.py` + `pipeline.py` |
| 飞书多维表格 | ✅ 预览同步（CSV/JSON），可升级 OpenAPI |
| 精美交互卡片日/周/月 | ✅ Card JSON 2.0 |
| 零终端傻瓜操作 | ✅ GUI 控制台 + BAT |

## 开发者入口（可选）

```powershell
.\.venv\Scripts\python worker_job.py --mode auto
.\.venv\Scripts\python app_gui.py
```
