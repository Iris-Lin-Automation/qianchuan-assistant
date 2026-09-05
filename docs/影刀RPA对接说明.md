# 影刀 RPA × Python 全自动对接说明

## 目标链路（每天 08:00）

```
定时闹钟
  → 影刀无人值守：打开浏览器 → 登录千川/抖店 → 导出 Excel
  → 另存为：项目/data/today.xlsx
  → 影刀最后一步执行：python main.py --file ./data/today.xlsx
  → Python 读表算 ROI → 写看板/多维表 → 飞书群「叮」一声
```

---

## 一、影刀侧怎么配

1. **定时**：每天 08:00 启动流程（影刀定时任务）
2. **浏览器**：使用已保存 Cookie 的 Chrome 用户目录，打开千川/抖店
3. **导出**：点击后台「导出」→ 等待下载完成
4. **另存为**（关键）：
   - 目标路径：`D:\qianchuan-feishu-analytics\data\today.xlsx`
   - 也可先下到默认下载目录，再「移动/重命名」为上面路径
5. **最后一步 - 执行命令**：
   - 工作目录：`D:\qianchuan-feishu-analytics`
   - 命令二选一：
     - `影刀调用Python.bat`（推荐，小白友好）
     - `.venv\Scripts\python.exe main.py --file .\data\today.xlsx`

> 兼容文件名：`data/qianchuan_today.xlsx`（bat 会自动复制为 today.xlsx）

---

## 二、Excel 模板列（影刀导出后建议对齐）

| 列名 | 必填 | 说明 |
|------|------|------|
| 日期 | 建议 | 没有则按今天 |
| 店铺名称 | 建议 | 多店必填 |
| 店铺ID | 可选 | 没有会自动生成 |
| 计划名称 | 可选 | 有则出 TOP 计划 |
| 消耗 | ✅ | 千川消耗 |
| 成交金额 / GMV | ✅ | |
| 展现 | 可选 | |
| 点击 | 可选 | |
| 订单 | 可选 | |
| 其他渠道消耗 | 可选 | 用于付费占比 |
| ROI目标 | 可选 | 默认 2.5 |

同一文件可含**昨日+今日**两天数据，Python 会自动算环比。

项目内可用脚本生成样例：

```bat
.venv\Scripts\python.exe scripts\make_sample_today_xlsx.py
```

---

## 三、Python 侧命令

```bat
REM 影刀标准调用（真实推送飞书）
.venv\Scripts\python.exe main.py --file .\data\today.xlsx

REM 先演练不推送
.venv\Scripts\python.exe main.py --file .\data\today.xlsx --dry-run
```

---

## 四、维护提醒（卖点话术）

若抖音/千川界面改版导致影刀点不到「导出」按钮，只需花约 10 分钟在影刀里重新定位元素；  
**Python 算账与飞书推送不用改**——职责分离，维护成本低。
