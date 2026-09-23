import sys
import os
import argparse
import logging
import yaml
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

from theme import MHY_RED, MHY_DARK, MHY_CARD, MHY_BORDER, MHY_TEXT, MHY_SUB, setup_ttk_style
from db import init_db, save_config, load_config, add_log, get_conn, GAMES
from views.dashboard import DashboardMixin
from views.ai import AIMixin
from views.versions import VersionsMixin
from views.report import ReportMixin
from views.plans import PlansMixin
from views.first_run import FirstRunMixin

# PyInstaller 打包检测
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent


def load_yaml_config(path=None):
    if path is None:
        path = BASE_DIR / "config.yaml"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_args():
    p = argparse.ArgumentParser(description="米游社运营助手 v3.0")
    p.add_argument("--config", type=str, default=None, help="自定义配置文件路径")
    p.add_argument("--demo", action="store_true", help="演示模式")
    p.add_argument("--log-level", type=str, default=None, help="日志级别")
    return p.parse_args()


args = parse_args()
_config = load_yaml_config(args.config)

# 命令行参数覆盖
if args.demo:
    _config["demo_mode"] = True
if args.log_level:
    _config["log_level"] = args.log_level

# 初始化日志
log_dir = BASE_DIR / "logs"
try:
    log_dir.mkdir(exist_ok=True)
    log_file = str(log_dir / "app.log")
    log_level = getattr(logging, _config.get("log_level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        filename=log_file,
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filemode="a",
        encoding="utf-8",
    )
except Exception:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)
logger.info("=" * 50)
logger.info("米游社运营助手 v3.0 启动")
logger.info(f"配置文件: {args.config or 'config.yaml'}")
logger.info(f"日志级别: {_config.get('log_level', 'INFO')}")


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

init_db()


class App(ctk.CTk, DashboardMixin, AIMixin, VersionsMixin, ReportMixin, PlansMixin, FirstRunMixin):
    def __init__(self):
        super().__init__()
        self.title("米游社运营助手 v3.1 — 米哈游全游戏运营决策系统")
        self.geometry("1200x780")
        self.minsize(1000, 680)
        self.config_data = _config
        self.auto_risk_enabled = False
        self.auto_risk_job = None

        setup_ttk_style()

        self._build_sidebar()
        self._build_main_area()

        self.current_view = None
        self._ai_saved_content = ""

        saved_geo = load_config("win_geometry")
        if saved_geo:
            try:
                self.geometry(saved_geo)
            except:
                pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 演示模式：预填丰富数据
        if self.config_data.get("demo_mode", False):
            self._init_demo_data()

        # 首次运行引导
        self.after(300, self._check_first_run)

        # F11 大屏模式
        self._fullscreen = False
        self.bind("<F11>", lambda e: self._toggle_fullscreen())

        last_view = load_config("last_view", "dashboard")
        {"dashboard": self.show_dashboard, "ai": self.show_ai,
         "versions": self.show_versions, "report": self.show_report}.get(last_view, self.show_dashboard)()
        self._refresh_log()

        logger.info("主窗口初始化完成")

    def _init_demo_data(self):
        try:
            from seed_demo import seed_demo
            seed_demo()
            logger.info("演示模式: 数据已就绪")
        except Exception as e:
            logger.warning(f"演示模式初始化异常: {e}")

    def _show_splash(self):
        import tkinter as tk
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        splash.configure(bg="#0f0f1a")
        w, h = 500, 300
        ws = splash.winfo_screenwidth()
        hs = splash.winfo_screenheight()
        x = (ws - w) // 2
        y = (hs - h) // 2
        splash.geometry(f"{w}x{h}+{x}+{y}")
        splash.attributes("-alpha", 0.95)

        canvas = tk.Canvas(splash, bg="#0f0f1a", highlightthickness=0, width=w, height=h)
        canvas.pack()
        canvas.create_rectangle(0, 0, w, 120, fill="#ff4d6a", outline="")
        canvas.create_text(w // 2, 60, text="米游社运营助手", fill="white",
                           font=("Microsoft YaHei", 28, "bold"))
        canvas.create_text(w // 2, 140, text="v3.1 — 米哈游全游戏运营决策系统",
                           fill="#8888aa", font=("Microsoft YaHei", 14))
        canvas.create_text(w // 2, 180, text="正在加载...",
                           fill="#ff4d6a", font=("Microsoft YaHei", 12))
        # 进度条模拟
        bar_bg = canvas.create_rectangle(50, 230, w - 50, 240, fill="#1a1a2e", outline="")
        bar_fill = canvas.create_rectangle(50, 230, 50, 240, fill="#ff4d6a", outline="")

        def animate(frame=0):
            if frame <= 40:
                progress = min(1.0, frame / 40)
                new_w = 50 + (w - 100) * progress
                canvas.coords(bar_fill, 50, 230, new_w, 240)
                splash.after(50, lambda: animate(frame + 1))
            else:
                splash.destroy()

        splash.after(100, animate)
        return splash

    def _toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)
        self._toast("大屏模式" if self._fullscreen else "窗口模式")

    # ── Sidebar ──
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=MHY_DARK)
        self.sidebar.pack(side="left", fill="y")

        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(35, 30))
        ctk.CTkLabel(logo_frame, text="🎮", font=("Microsoft YaHei", 36)).pack()
        ctk.CTkLabel(logo_frame, text="米哈游运营助手", font=("Microsoft YaHei", 17, "bold"),
                     text_color="white").pack(pady=(5, 2))
        ctk.CTkLabel(logo_frame, text="miHoYo Ops Tool v3.1", font=("Microsoft YaHei", 10),
                     text_color=MHY_SUB).pack()

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=MHY_BORDER)
        sep.pack(fill="x", padx=20, pady=5)

        nav_btns = [
            ("📊  数据工作台", self.show_dashboard),
            ("🤖  AI 运营顾问", self.show_ai),
            ("📅  版本管理", self.show_versions),
            ("📝  运营报告", self.show_report),
        ]
        self.nav_btns = []
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=10)
        for text, cmd in nav_btns:
            btn = ctk.CTkButton(nav_frame, text=text, command=cmd,
                                fg_color="transparent", text_color=MHY_TEXT,
                                hover_color=MHY_RED,
                                anchor="w", height=46, font=("Microsoft YaHei", 14),
                                corner_radius=8)
            btn.pack(fill="x", pady=3)
            self.nav_btns.append(btn)

        self.nav_strip = ctk.CTkFrame(self.sidebar, fg_color="transparent", width=4, height=36)
        self.nav_strip.place(x=8, y=0)

        self.log_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.log_frame.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(self.log_frame, text="最近操作", font=("Microsoft YaHei", 10, "bold"),
                     text_color=MHY_SUB).pack(anchor="w")
        self.log_label = ctk.CTkLabel(self.log_frame, text="暂无操作记录",
                                       font=("Microsoft YaHei", 9), text_color="#555",
                                       anchor="w", justify="left")
        self.log_label.pack(fill="x", pady=(2, 0))

        sep2 = ctk.CTkFrame(self.sidebar, height=1, fg_color=MHY_BORDER)
        sep2.pack(fill="x", padx=20, pady=5)

        search_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=(5, 10))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="搜索版本 / 活动 / 报告...",
                                          height=30, width=180)
        self.search_entry.pack(fill="x", padx=5)
        self.search_entry.bind("<Return>", lambda e: self._global_search())
        ctk.CTkButton(search_frame, text="🔍 搜索", fg_color=MHY_RED, hover_color="#e0415c",
                      height=28, font=("Microsoft YaHei", 10),
                      command=self._global_search).pack(fill="x", padx=5, pady=(3, 0))
        ctk.CTkButton(search_frame, text="📊 版本对比", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                      height=28, text_color=MHY_TEXT, font=("Microsoft YaHei", 10),
                      command=self._show_version_compare).pack(fill="x", padx=5, pady=(3, 0))

        # 自动风险检测开关
        auto_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        auto_frame.pack(fill="x", padx=5, pady=(8, 0))
        ctk.CTkLabel(auto_frame, text="自动风险检测", font=("Microsoft YaHei", 10),
                     text_color=MHY_SUB).pack(side="left")
        self.auto_risk_switch = ctk.CTkSwitch(auto_frame, text="",
                                               command=self._toggle_auto_risk,
                                               width=36, progress_color=MHY_RED)
        self.auto_risk_switch.pack(side="right")

        status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        status_frame.pack(side="bottom", fill="x", padx=15, pady=20)
        ctk.CTkLabel(status_frame, text="● 数据本地存储", font=("Microsoft YaHei", 11),
                     text_color="#2ecc71").pack(anchor="w")
        ctk.CTkLabel(status_frame, text="v3.1 · 2026-06-26 · SQLite", font=("Microsoft YaHei", 10),
                      text_color=MHY_SUB).pack(anchor="w")

        # 备份/恢复
        tool_row = ctk.CTkFrame(status_frame, fg_color="transparent")
        tool_row.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(tool_row, text="💾 备份", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                       text_color=MHY_TEXT, width=55, height=24, font=("Microsoft YaHei", 9),
                       command=self._backup_database).pack(side="left", padx=2)
        ctk.CTkButton(tool_row, text="📥 恢复", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                       text_color=MHY_TEXT, width=55, height=24, font=("Microsoft YaHei", 9),
                       command=self._restore_database).pack(side="left", padx=2)
        ctk.CTkButton(tool_row, text="📅 日历", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                       text_color=MHY_TEXT, width=55, height=24, font=("Microsoft YaHei", 9),
                       command=self._export_ics).pack(side="left", padx=2)

    def _build_main_area(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="#12121e")
        self.main_frame.pack(side="right", fill="both", expand=True)

    def _backup_database(self):
        import zipfile, shutil
        from tkinter import filedialog as fd
        src = str(BASE_DIR / "data" / "ops_data.db")
        if not os.path.exists(src):
            messagebox.showwarning("提示", "数据库文件不存在")
            return
        fp = fd.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP", "*.zip")],
                                   title="备份数据库", initialfile=f"ops_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip")
        if not fp:
            return
        with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(src, "ops_data.db")
        logger.info(f"数据库已备份至: {fp}")
        self._toast("备份完成")

    def _restore_database(self):
        import zipfile, shutil
        from tkinter import filedialog as fd
        if not messagebox.askyesno("确认恢复", "恢复将覆盖当前数据库，此操作不可撤销。\n是否继续？"):
            return
        fp = fd.askopenfilename(filetypes=[("ZIP", "*.zip")], title="选择备份文件")
        if not fp:
            return
        dst = str(BASE_DIR / "data" / "ops_data.db")
        try:
            with zipfile.ZipFile(fp, "r") as zf:
                zf.extract("ops_data.db", str(BASE_DIR / "data"))
            messagebox.showinfo("成功", "数据库已恢复，请重启应用")
            logger.info("数据库已从备份恢复")
        except Exception as e:
            messagebox.showerror("错误", f"恢复失败: {e}")

    def _export_ics(self):
        from tkinter import filedialog as fd
        fp = fd.asksaveasfilename(defaultextension=".ics", filetypes=[("iCalendar", "*.ics")],
                                   title="导出运营日历", initialfile=f"运营日历_{datetime.now().strftime('%Y%m%d')}.ics")
        if not fp:
            return
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MHY Ops//CN"]
        try:
            with get_conn() as c:
                vers = c.execute("SELECT game,version,start_date,end_date FROM versions ORDER BY start_date").fetchall()
                for g, v, s, e in vers:
                    if not s:
                        continue
                    dt_start = s.replace("-", "") + "T090000"
                    dt_end = (e.replace("-", "") if e else s.replace("-", "")) + "T100000"
                    lines.append("BEGIN:VEVENT")
                    lines.append(f"SUMMARY:{g} {v} 版本上线")
                    lines.append(f"DTSTART:{dt_start}")
                    lines.append(f"DTEND:{dt_end}")
                    lines.append(f"DESCRIPTION:{g} 游戏版本 {v} 正式上线")
                    lines.append("END:VEVENT")
            lines.append("END:VCALENDAR")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("\r\n".join(lines))
            self._toast(f"已导出 {len(vers)} 个版本事件")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # ── 自动风险检测 ──
    def _toggle_auto_risk(self):
        self.auto_risk_enabled = self.auto_risk_switch.get()
        if self.auto_risk_enabled:
            logger.info("自动风险检测已开启")
            self._schedule_auto_risk()
        else:
            logger.info("自动风险检测已关闭")
            if self.auto_risk_job:
                self.after_cancel(self.auto_risk_job)
                self.auto_risk_job = None

    def _schedule_auto_risk(self):
        if not self.auto_risk_enabled:
            return
        self._check_auto_risks()
        self.auto_risk_job = self.after(300000, self._schedule_auto_risk)  # 5分钟

    def _check_auto_risks(self):
        try:
            with get_conn() as c:
                rows = c.execute("""
                    SELECT character_name, usage_rate
                    FROM char_usage ORDER BY character_name, update_time DESC
                """).fetchall()
            if len(rows) < 3:
                return
            char_data = {}
            for name, rate in rows:
                if name not in char_data:
                    char_data[name] = []
                char_data[name].append(rate)
            alerts = []
            for name, rates in char_data.items():
                if len(rates) >= 2 and rates[0] < 0.5 and rates[0] < rates[-1]:
                    alerts.append(name)
            if alerts:
                logger.info(f"自动风险检测: 发现使用率偏低角色 {alerts}")
                self.after(0, lambda: self._notify_auto_risk(alerts))
        except Exception as e:
            logger.exception("自动风险检测异常")

    def _notify_auto_risk(self, names):
        msg = "以下角色使用率持续偏低:\n" + "\n".join(names)
        try:
            messagebox.showwarning("自动风险检测", msg)
        except:
            pass

    # ── Shared Utilities ──
    def clear_main(self, on_done=None):
        if self.current_view == "ai" and hasattr(self, 'ai_result'):
            try:
                self._ai_saved_content = self.ai_result.get("1.0", "end-1c")
            except:
                self._ai_saved_content = ""
        overlay = ctk.CTkFrame(self.main_frame, fg_color="#12121e")
        overlay.place(relwidth=1, relheight=1)
        def finish():
            overlay.destroy()
            for w in self.main_frame.winfo_children():
                w.destroy()
            for btn in self.nav_btns:
                btn.configure(fg_color="transparent")
            if on_done:
                on_done()
        self.after(30, finish)

    def highlight_nav(self, idx):
        for i, btn in enumerate(self.nav_btns):
            btn.configure(fg_color=MHY_RED if i == idx else "transparent")
        btn = self.nav_btns[idx]
        y = btn.winfo_y() + btn.winfo_height() // 2 - 18
        self.nav_strip.configure(fg_color=MHY_RED)
        self.nav_strip.place(x=8, y=y)

    def _toast(self, msg, color="#2ecc71"):
        toast = ctk.CTkFrame(self, fg_color=color, corner_radius=8)
        toast.place(relx=0.98, rely=0.05, anchor="ne")
        ctk.CTkLabel(toast, text=msg, font=("Microsoft YaHei", 12),
                     text_color="white").pack(padx=20, pady=8)
        self.after(2000, toast.destroy)

    def _quick_save(self):
        if self.current_view == "ai":
            self._save_ai_config(silent=True)
            self._toast("配置已保存")
        elif self.current_view == "report":
            self._save_report()
        elif self.current_view == "dashboard":
            self._toast("使用 Ctrl+1~4 切换模块")

    def _on_close(self):
        logger.info("应用关闭")
        if self.auto_risk_job:
            self.after_cancel(self.auto_risk_job)
        save_config("last_view", self.current_view or "dashboard")
        save_config("win_geometry", self.geometry())
        self.destroy()

    def _handle_undo(self):
        try:
            from undo_manager import get_undo_manager
            mgr = get_undo_manager()
            if mgr.can_undo():
                desc = mgr.undo(get_conn())
                self._toast(f"已撤销: {desc}")
                self._save_log("撤销", desc or "")
                if self.current_view == "versions":
                    self._refresh_versions()
                elif self.current_view == "report":
                    pass
        except Exception as e:
            logger.exception("撤销异常")
            self._toast(f"撤销失败: {e}", "#e74c3c")

    def _handle_redo(self):
        try:
            from undo_manager import get_undo_manager
            mgr = get_undo_manager()
            if mgr.can_redo():
                desc = mgr.redo(get_conn())
                self._toast(f"已重做: {desc}")
                self._save_log("重做", desc or "")
                if self.current_view == "versions":
                    self._refresh_versions()
        except Exception as e:
            logger.exception("重做异常")
            self._toast(f"重做失败: {e}", "#e74c3c")

    def _save_log(self, action, detail=""):
        add_log(action, detail)
        logger.info(f"操作: {action} - {detail}")
        self._refresh_log()

    def _refresh_log(self):
        try:
            with get_conn() as c:
                rows = c.execute("SELECT action,detail FROM activity_log ORDER BY id DESC LIMIT 3").fetchall()
            if rows:
                lines = []
                for action, detail in rows:
                    line = action if not detail else f"{action}: {detail}"
                    lines.append(line[:35])
                self.log_label.configure(text="\n".join(lines), text_color=MHY_SUB)
        except:
            pass

    # ── Global Search ──
    def _global_search(self):
        q = self.search_entry.get().strip()
        if not q:
            return
        results = []
        try:
            with get_conn() as c:
                for r in c.execute("SELECT game,version,start_date,status FROM versions WHERE game LIKE ? OR version LIKE ?",
                                    (f"%{q}%", f"%{q}%")).fetchall():
                    results.append(f"[版本] {r[0]} {r[1]} | {r[2]} | {r[3]}")
                for r in c.execute("SELECT name,game,type,start_date FROM events WHERE name LIKE ? OR type LIKE ?",
                                    (f"%{q}%", f"%{q}%")).fetchall():
                    results.append(f"[活动] {r[0]} | {r[1]} | {r[2]} | {r[3]}")
                for r in c.execute("SELECT title,type,created_at FROM reports WHERE title LIKE ? OR content LIKE ? LIMIT 10",
                                    (f"%{q}%", f"%{q}%")).fetchall():
                    results.append(f"[报告] {r[0]} | {r[1]} | {r[2]}")
        except:
            results = ["搜索出错"]
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"搜索结果：{q}")
        dialog.geometry("650x450")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=MHY_CARD)
        ctk.CTkLabel(dialog, text=f"搜索「{q}」找到 {len(results)} 条结果",
                     font=("Microsoft YaHei", 14, "bold"), text_color="white").pack(pady=(15, 10))
        frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        if not results:
            ctk.CTkLabel(frame, text="没有找到相关结果", font=("Microsoft YaHei", 13),
                         text_color=MHY_SUB).pack(pady=40)
        for line in results:
            ctk.CTkLabel(frame, text=line, font=("Microsoft YaHei", 12),
                         text_color=MHY_TEXT, anchor="w").pack(fill="x", pady=3)


if __name__ == "__main__":
    try:
        app = App()
        app._show_splash()
        app.bind_all("<Control-Key-1>", lambda e: app.show_dashboard())
        app.bind_all("<Control-Key-2>", lambda e: app.show_ai())
        app.bind_all("<Control-Key-3>", lambda e: app.show_versions())
        app.bind_all("<Control-Key-4>", lambda e: app.show_report())
        app.bind_all("<Control-f>", lambda e: app.search_entry.focus_set())
        app.bind_all("<Control-s>", lambda e: app._quick_save())
        app.bind_all("<Control-z>", lambda e: app._handle_undo())
        app.bind_all("<Control-y>", lambda e: app._handle_redo())
        app.bind_all("<F11>", lambda e: app._toggle_fullscreen())
        app.mainloop()
    except Exception as e:
        logger.exception("应用启动异常")
        raise
