"""米游社运营助手 - 芙宁娜主题版
Mixin架构：CTk + DashboardMixin + AIMixin + VersionsMixin + ReportMixin + PlansMixin + MarketingMixin + SocialTrendMixin + SettingsMixin
设计原则：芙宁娜个性化融入细节（色板/图标/语录），数据面板保持干净
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import sys, os, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from theme import setup_ttk_style, BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM, ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER
from views import (
    DashboardMixin, AIMixin, VersionsMixin, ReportMixin,
    PlansMixin, MarketingMixin, SocialTrendMixin, SettingsMixin
)

# ── 芙宁娜语录（切换模块时随机显示）──
FURINA_QUOTES = [
    "哼哼~这可是全场最精彩的演出！",
    "我可是芙宁娜！区区数据难不倒我！",
    "让开让开，聚光灯该打在我身上了！",
    "诸位，好戏才刚刚开始呢。",
    "水面之上，一切皆为舞台。",
    "这只是序章而已，精彩还在后头！",
    "身为水之神，这点小事不在话下。",
    "今天的观众反应不错嘛~",
    "不愧是我！数据一目了然！",
    "掌声在哪里？我可是做了了不起的事！",
    "嗯？你以为我会失败？太天真了。",
    "全场欢呼吧！运营数据尽在掌握！",
]

# ── 芙宁娜风格导航图标（水元素+歌剧院主题）──
FURINA_ICONS = {
    "数据看板": "💧",   # 水元素
    "AI顾问":   "🎭",   # 戏剧面具
    "版本管理": "📜",   # 卷轴
    "运营报告": "✒️",   # 羽毛笔
    "排期预算": "⚖️",   # 天平
    "内容工厂": "🎪",   # 演出
    "趋势雷达": "🔮",   # 水晶球
    "AI设置":   "⚙️",   # 齿轮
}

# ── 模块提示语（状态栏显示）──
MODULE_HINTS = {
    "数据看板": "💧 水面之上，数据尽收眼底",
    "AI顾问":   "🎭 让AI为这场演出添彩",
    "版本管理": "📜 每一场演出都需要精心编排",
    "运营报告": "✒️ 用文字记录每一场辉煌",
    "排期预算": "⚖️ 正义的天平不会倾斜",
    "内容工厂": "🎪 最精彩的内容即将登场",
    "趋势雷达": "🔮 未来的一切已在我掌中",
    "AI设置":   "⚙️ 让好戏的引擎为你所用",
}

# ── 统一字号常量 ──
FONT_TITLE = ("Microsoft YaHei", 13, "bold")
FONT_SUB   = ("Microsoft YaHei", 9, "italic")
FONT_NAV   = ("Microsoft YaHei", 12)
FONT_HINT  = ("Microsoft YaHei", 8)
FONT_STATUS = ("Microsoft YaHei", 9)
FONT_TOAST = ("Microsoft YaHei", 11, "bold")
FONT_ABOUT = ("Microsoft YaHei", 9)


class OpsApp(
    DashboardMixin, AIMixin, VersionsMixin, ReportMixin,
    PlansMixin, MarketingMixin, SocialTrendMixin, SettingsMixin, ctk.CTk
):
    def __init__(self):
        super().__init__()
        self.title("✦ 米游社运营助手 · 芙宁娜版 ✦")
        self.geometry("1280x800")
        self.minsize(1000, 600)
        self.configure(fg_color=BG_DARK)
        # 窗口图标
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass
        db.init_db()
        setup_ttk_style()
        self._build_layout()
        self._nav_to("数据看板")
        db.save_log("app_start", "")
        self._furina_toast(random.choice(FURINA_QUOTES))

    def _build_layout(self):
        # ══════════════════════════════════════════
        # 侧边栏（芙宁娜风格：深蓝底+金色点缀）
        # ══════════════════════════════════════════
        self._sidebar = ctk.CTkFrame(self, width=210, fg_color=BG_CARD, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # ── Logo区域 ──
        header = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        header.pack(fill="x", pady=(20, 0))

        # 水滴标志
        drop = tk.Canvas(header, width=36, height=44, bg=BG_CARD, highlightthickness=0)
        drop.pack(pady=(0, 6))
        drop.create_polygon(18, 2, 32, 24, 26, 38, 18, 42, 10, 38, 4, 24,
                            fill=ACCENT_LIGHT, outline=GOLD, width=2)
        drop.create_oval(11, 16, 20, 26, fill=ACCENT_LIGHT, outline="")

        ctk.CTkLabel(header, text="米游社运营助手", font=FONT_TITLE,
                     text_color=GOLD, fg_color=BG_CARD).pack()
        ctk.CTkLabel(header, text="「众水的歌者」", font=FONT_SUB,
                     text_color=ACCENT_LIGHT, fg_color=BG_CARD).pack(pady=(2, 0))

        # ── 金色分隔线 ──
        sep = tk.Canvas(self._sidebar, height=1, bg=BG_CARD, highlightthickness=0)
        sep.pack(fill="x", padx=24, pady=12)
        sep.create_line(0, 0, 200, 0, fill=GOLD, width=1)

        # ── 导航按钮 ──
        self._nav_btns = []
        navs = [
            ("数据看板", "水面之上，数据尽收眼底"),
            ("AI顾问",   "让好戏永不停歇"),
            ("版本管理", "每一场演出都有序章"),
            ("运营报告", "用羽毛笔记录辉煌"),
            ("排期预算", "正义的天平不会倾斜"),
            ("内容工厂", "最精彩的舞台在这里"),
            ("趋势雷达", "未来已在我掌中"),
            ("AI设置",   "让好戏的引擎为你所用"),
        ]
        for name, hint in navs:
            icon = FURINA_ICONS[name]
            btn = ctk.CTkButton(
                self._sidebar, text=f"  {icon}  {name}", width=190, height=40,
                fg_color=BG_CARD, hover_color=BG_INPUT, text_color=FG_TEXT,
                corner_radius=10, anchor="w", font=FONT_NAV,
                command=lambda n=name: self._nav_to(n)
            )
            btn.pack(pady=4, padx=10)
            self._nav_btns.append((btn, name))

        # ── 底部区域 ──
        bottom = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=10, pady=12)

        sep2 = tk.Canvas(bottom, height=1, bg=BG_CARD, highlightthickness=0)
        sep2.pack(fill="x", pady=(0, 10))
        sep2.create_line(0, 0, 200, 0, fill=GOLD, width=1)

        ctk.CTkLabel(bottom, text="—— 芙宁娜 · Focalors ——",
                     font=FONT_HINT, text_color=GOLD, fg_color=BG_CARD).pack(pady=(0, 6))
        ctk.CTkButton(bottom, text="⚖️ 关于", width=80, fg_color=BG_INPUT,
                      hover_color=ACCENT, text_color=FG_DIM, font=FONT_ABOUT,
                      command=self._show_about).pack(pady=2)

        # ══════════════════════════════════════════
        # 主内容区（干净，无水印干扰数据阅读）
        # ══════════════════════════════════════════

        # 先打包状态栏（占底部空间）
        self._statusbar = ctk.CTkLabel(
            self, text="✦ 水面之上，一切皆为舞台 ✦",
            font=FONT_STATUS, text_color=FG_DIM,
            fg_color=BG_CARD, anchor="w", padx=16, height=24
        )
        self._statusbar.pack(side="bottom", fill="x")

        # 再打包内容区（填充剩余空间）
        self._content = ctk.CTkFrame(self, fg_color=BG_DARK)
        self._content.pack(side="right", fill="both", expand=True)

        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-s>", lambda e: self._toast("已保存"))

    # ══════════════════════════════════════════
    # 导航逻辑
    # ══════════════════════════════════════════
    def _nav_to(self, name):
        # 清空当前内容
        for w in self._content.winfo_children():
            w.destroy()
        # 更新按钮状态
        for btn, n in self._nav_btns:
            if n == name:
                btn.configure(fg_color=BG_INPUT, text_color=GOLD_LIGHT,
                             border_width=1, border_color=GOLD, hover_color=ACCENT)
                self._statusbar.configure(text=f"✦ {MODULE_HINTS.get(name, name)} ✦")
            else:
                btn.configure(fg_color=BG_CARD, text_color=FG_TEXT,
                             border_width=0, hover_color=BG_INPUT)
        # 加载模块
        mapping = {
            "数据看板": self.create_dashboard,
            "AI顾问": self.create_ai,
            "版本管理": self.create_versions,
            "运营报告": self.create_report,
            "排期预算": self.create_plans,
            "内容工厂": self.create_marketing,
            "趋势雷达": self.create_social_trend,
            "AI设置": self.create_settings,
        }
        fn = mapping.get(name)
        if fn:
            def _run():
                try:
                    fn(self._content)
                except Exception as e:
                    import traceback
                    err = traceback.format_exc()
                    print(f"[ERROR] {name}: {err}")
                    ctk.CTkLabel(self._content, text=f"❌ 模块加载失败: {name}\n\n{e}",
                                 font=("Microsoft YaHei", 12), text_color="#ff6b6b",
                                 fg_color=BG_DARK, wraplength=600, justify="left").pack(padx=40, pady=40)
            self.after(10, _run)
            self._furina_toast(random.choice(FURINA_QUOTES))
        db.save_log("nav", name)

    # ══════════════════════════════════════════
    # 芙宁娜风格Toast通知
    # ══════════════════════════════════════════
    def _furina_toast(self, msg, duration=3000):
        if hasattr(self, "_toast_lbl") and self._toast_lbl.winfo_exists():
            self._toast_lbl.destroy()
        self._toast_lbl = ctk.CTkLabel(
            self, text=f"🎭 {msg}",
            fg_color=GOLD, text_color="#0d1b2a",
            corner_radius=8, padx=18, pady=7, font=FONT_TOAST
        )
        self._toast_lbl.place(relx=0.5, rely=0.93, anchor="center")
        self.after(duration, lambda: self._toast_lbl.destroy() if self._toast_lbl.winfo_exists() else None)

    def _toast(self, msg, duration=2000):
        self._furina_toast(msg, duration)

    def _save_log(self, action, detail=""):
        db.save_log(action, detail)

    def _focus_search(self):
        self._furina_toast("让我看看有什么有趣的数据~")

    def _show_about(self):
        messagebox.showinfo(
            "✦ 关于 ✦",
            "米游社运营助手 · 芙宁娜版\n"
            "v2.0 运营+营销双线升级版\n\n"
            "「水面之上，一切皆为舞台。」\n"
            "—— 芙宁娜 · Focalors\n\n"
            "Python 3.11 + CustomTkinter + SQLite\n"
            "运营+营销双线 · 8大模块 · 3000+行代码\n\n"
            "支持AI后端：DeepSeek / OpenAI / Ollama"
        )


if __name__ == "__main__":
    app = OpsApp()
    app.mainloop()
