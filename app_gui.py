"""
千川经营助手 · 操作台（开箱即用）
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import StringVar, messagebox, scrolledtext, ttk
import tkinter as tk

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timezone_util import detect_local_timezone, format_now

ENV_PATH = ROOT / ".env"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def _load_env_value(key: str, default: str = "") -> str:
    if not ENV_PATH.exists():
        return default
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return default


def _upsert_env(updates: dict[str, str]) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    keys_done: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                keys_done.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in keys_done:
            new_lines.append(f"{k}={v}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("千川经营助手")
        self.geometry("880x640")
        self.minsize(820, 560)

        self.webhook_var = StringVar(value=_load_env_value("FEISHU_WEBHOOK_URL"))
        self.hour_var = StringVar(value=_load_env_value("SCHEDULE_HOUR", "8") or "8")
        self.minute_var = StringVar(value=_load_env_value("SCHEDULE_MINUTE", "0") or "0")
        self.clock_var = StringVar(value="")
        self.local_tz = detect_local_timezone()

        self._build_ui()
        self._tick_clock()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        ttk.Label(
            self,
            text="千川经营助手 · 三步完成：填写配置 → 保存 → 推送日报",
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(anchor="w", **pad)

        ttk.Label(self, textvariable=self.clock_var, foreground="#1a5fb4").pack(
            anchor="w", padx=12
        )

        form = ttk.LabelFrame(self, text="① 填写配置")
        form.pack(fill="x", padx=12, pady=6)

        ttk.Label(form, text="飞书群机器人地址").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(form, textvariable=self.webhook_var, width=72).grid(
            row=0, column=1, columnspan=3, sticky="we", padx=8, pady=4
        )

        ttk.Label(form, text="每天自动推送时间").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(form, textvariable=self.hour_var, width=4).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(form, text="时").grid(row=1, column=1, sticky="w", padx=(40, 0))
        ttk.Entry(form, textvariable=self.minute_var, width=4).grid(
            row=1, column=1, sticky="w", padx=(64, 0)
        )
        ttk.Label(form, text="分（电脑本机时间）").grid(row=1, column=1, sticky="w", padx=(110, 0))

        form.columnconfigure(1, weight=1)

        actions = ttk.LabelFrame(self, text="② 常用操作")
        actions.pack(fill="x", padx=12, pady=6)
        btns = [
            ("保存配置", self.save_config),
            ("打开经营看板", self.open_dashboard),
            ("立即推送日报", lambda: self.run_job("daily")),
            ("开启每日定时", self.install_schedule),
        ]
        for i, (text, cmd) in enumerate(btns):
            ttk.Button(actions, text=text, command=cmd).grid(
                row=0, column=i, sticky="we", padx=6, pady=8
            )
            actions.columnconfigure(i, weight=1)

        status = ttk.LabelFrame(self, text="③ 运行状态")
        status.pack(fill="both", expand=True, padx=12, pady=6)
        self.log = scrolledtext.ScrolledText(status, height=14, font=("Microsoft YaHei UI", 10))
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.append_log("欢迎使用。请先填写飞书群机器人地址并保存。")
        self.append_log("有样例数据时，可直接点「立即推送日报」体验效果。")

    def _tick_clock(self) -> None:
        self.clock_var.set(f"当前时间：{format_now(self.local_tz)}")
        self.after(1000, self._tick_clock)

    def append_log(self, msg: str) -> None:
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.update_idletasks()

    def save_config(self) -> None:
        webhook = self.webhook_var.get().strip()
        if not webhook:
            messagebox.showwarning("提示", "请填写飞书群机器人地址")
            return
        updates = {
            "FEISHU_WEBHOOK_URL": webhook,
            "FEISHU_BITABLE_URL": "",
            "DEBUG_MODE": "false",
            "SCHEDULE_TIMEZONE": self.local_tz,
            "SCHEDULE_HOUR": self.hour_var.get().strip() or "8",
            "SCHEDULE_MINUTE": self.minute_var.get().strip() or "0",
            "REPORT_TITLE_PREFIX": "千川经营日报",
            "ALERT_THRESHOLD_PERCENT": "20",
        }
        _upsert_env(updates)
        for k, v in updates.items():
            os.environ[k] = v
        self.append_log("配置已保存。")
        messagebox.showinfo("成功", "配置已保存")

    def _open_local_file(self, path: Path) -> None:
        """用系统默认方式打开本地文件（Windows 下比 webbrowser 更稳）。"""
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.as_uri())

    def open_dashboard(self) -> None:
        path = ROOT / "data" / "dashboard.html"
        if not path.exists():
            self.append_log("还没有看板，正在生成本地看板…")
            self._seed_dashboard()
            return
        try:
            self._open_local_file(path)
            self.append_log(f"已打开经营看板：{path}")
        except Exception as exc:
            self.append_log(f"打开失败：{exc}")
            messagebox.showerror(
                "打开失败",
                f"无法打开本地看板：\n{path}\n\n{exc}\n\n可手动双击该文件。",
            )

    def _seed_dashboard(self) -> None:
        def _worker() -> None:
            try:
                from datetime import timedelta
                from importlib import reload
                import config as config_mod

                reload(config_mod)
                from collectors import collect_store_day_raw
                from cleaner import aggregate_store_day
                from feishu_table import sync_daily_metrics
                from mock_accounts import get_demo_store_configs

                stores = get_demo_store_configs()
                today = date.today()
                for i in range(29, -1, -1):
                    dt = today - timedelta(days=i)
                    raw = collect_store_day_raw(stores, dt)
                    metrics = [aggregate_store_day(r, dt) for r in raw]
                    sync_daily_metrics(metrics, dry_run=True)
                path = ROOT / "data" / "dashboard.html"
                self.after(0, lambda: self.append_log(f"经营看板已生成：{path}"))
                self.after(0, lambda: self._open_local_file(path))
            except Exception as exc:
                self.after(0, lambda: self.append_log(f"生成失败：{exc}"))
                self.after(0, lambda: messagebox.showerror("失败", str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def run_job(self, mode: str) -> None:
        self.save_config()
        self.append_log("正在推送日报，请稍候…")

        def _worker() -> None:
            try:
                from importlib import reload
                import config as config_mod

                reload(config_mod)
                from pipeline import run_daily

                excel = ROOT / "data" / "today.xlsx"
                if excel.exists():
                    from pipeline import run_from_excel

                    run_from_excel(str(excel), dry_run_card=False, dry_run_table=True)
                else:
                    run_daily(date.today(), dry_run_card=False, dry_run_table=True, with_rpa=True)
                self.after(0, lambda: self.append_log("日报已推送到飞书群，请打开群消息查看。"))
                self.after(0, lambda: messagebox.showinfo("完成", "日报已推送，请到飞书群查看"))
            except Exception as exc:
                self.after(0, lambda: self.append_log(f"推送失败：{exc}"))
                self.after(0, lambda: messagebox.showerror("失败", str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def install_schedule(self) -> None:
        self.save_config()
        hour = int(self.hour_var.get().strip() or "8")
        minute = int(self.minute_var.get().strip() or "0")
        self.append_log(f"正在设置每日 {hour:02d}:{minute:02d} 自动推送…")
        ps1 = ROOT / "scripts" / "install_schedule.ps1"
        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-Hour",
            str(hour),
            "-Minute",
            str(minute),
            "-PythonPath",
            str(PYTHON),
            "-WorkerPath",
            str(ROOT / "worker_job.py"),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore"
            )
            if result.returncode == 0:
                self.append_log("每日定时已开启。请保持电脑开机或使用云电脑。")
                messagebox.showinfo(
                    "成功",
                    f"已开启每日 {hour:02d}:{minute:02d} 自动推送\n请保持电脑开机。",
                )
            else:
                out = ((result.stdout or "") + (result.stderr or "")).strip()
                self.append_log("定时设置失败，可尝试右键以管理员身份运行。")
                messagebox.showerror("失败", out or "设置失败，请尝试管理员权限")
        except Exception as exc:
            messagebox.showerror("失败", str(exc))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
