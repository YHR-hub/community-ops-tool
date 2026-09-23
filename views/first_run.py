from datetime import datetime
import customtkinter as ctk
from tkinter import font
from theme import MHY_RED, MHY_DARK, MHY_CARD, MHY_BORDER, MHY_TEXT, MHY_SUB
from db import save_config, load_config


class FirstRunMixin:
    def _check_first_run(self):
        is_first = load_config("is_first_run", "true")
        if is_first != "false":
            self._show_first_run_guide()

    def _show_first_run_guide(self):
        steps = [
            {
                "title": "欢迎使用米游社运营助手 v3.0",
                "desc": "面向原神、星穹铁道、绝区零、崩坏3的本地化社区运营工具",
                "shortcut": "",
                "icon": "🎮",
            },
            {
                "title": "📊 数据工作台 (Ctrl+1)",
                "desc": "录入每日运营数据，自动生成看板\n包含DAU折线图、趋势预测、双轴对比",
                "shortcut": "Ctrl+1",
                "icon": "📊",
            },
            {
                "title": "🤖 AI 运营顾问 (Ctrl+2)",
                "desc": "7 种预设场景 + 词云分析\n支持 DeepSeek / GPT 等模型",
                "shortcut": "Ctrl+2",
                "icon": "🤖",
            },
            {
                "title": "📅 版本管理 (Ctrl+3)",
                "desc": "版本看板、任务清单、甘特图\n健康度评分、风险矩阵、预算跟踪",
                "shortcut": "Ctrl+3",
                "icon": "📅",
            },
            {
                "title": "📝 运营报告 (Ctrl+4)",
                "desc": "一键生成智能报告、AI润色\n支持导出为 PDF（含雷达图、风险矩阵）",
                "shortcut": "Ctrl+4",
                "icon": "📝",
            },
        ]

        self.guide = ctk.CTkToplevel(self)
        self.guide.title("首次使用引导")
        self.guide.geometry("580x480")
        self.guide.transient(self)
        self.guide.grab_set()
        self.guide.configure(fg_color=MHY_DARK)
        self.guide.attributes("-alpha", 0.95)

        self.guide_step = 0
        self.guide_steps = steps

        self.guide_container = ctk.CTkFrame(self.guide, fg_color="transparent")
        self.guide_container.pack(fill="both", expand=True, padx=30, pady=30)

        self.guide_icon = ctk.CTkLabel(self.guide_container, text="🎮",
                                        font=("Microsoft YaHei", 60))
        self.guide_icon.pack(pady=(30, 20))

        self.guide_title = ctk.CTkLabel(self.guide_container, text="",
                                         font=("Microsoft YaHei", 20, "bold"), text_color="white")
        self.guide_title.pack(pady=(0, 10))

        self.guide_desc = ctk.CTkLabel(self.guide_container, text="",
                                        font=("Microsoft YaHei", 14), text_color=MHY_SUB,
                                        justify="center")
        self.guide_desc.pack(pady=(0, 10))

        self.guide_shortcut = ctk.CTkFrame(self.guide_container, fg_color=MHY_RED, corner_radius=8)
        self.guide_shortcut_label = ctk.CTkLabel(self.guide_shortcut, text="",
                                                   font=("Microsoft YaHei", 12, "bold"), text_color="white")
        self.guide_shortcut_label.pack(padx=16, pady=4)

        # 步进
        btn_row = ctk.CTkFrame(self.guide_container, fg_color="transparent")
        btn_row.pack(pady=(20, 10))

        self.guide_dots = ctk.CTkFrame(btn_row, fg_color="transparent")
        self.guide_dots.pack(side="left", padx=20)
        self.dot_labels = []

        self.guide_prev_btn = ctk.CTkButton(btn_row, text="‹ 上一步", fg_color=MHY_BORDER,
                                             hover_color="#3a3a4e", text_color=MHY_TEXT,
                                             command=self._guide_prev, width=90)
        self.guide_next_btn = ctk.CTkButton(btn_row, text="下一步 ›", fg_color=MHY_RED,
                                             hover_color="#e0415c", command=self._guide_next, width=90)
        self.guide_next_btn.pack(side="right", padx=10)
        self.guide_prev_btn.pack(side="right", padx=5)

        for i in range(len(steps)):
            dot = ctk.CTkLabel(self.guide_dots, text="○" if i > 0 else "●",
                               font=("Microsoft YaHei", 14), text_color=MHY_RED if i == 0 else MHY_SUB)
            dot.pack(side="left", padx=3)
            self.dot_labels.append(dot)

        self._render_guide_step(0)

    def _render_guide_step(self, step):
        s = self.guide_steps[step]
        self.guide_icon.configure(text=s["icon"])
        self.guide_title.configure(text=s["title"])
        self.guide_desc.configure(text=s["desc"])
        if s["shortcut"]:
            self.guide_shortcut_label.configure(text=s["shortcut"])
            self.guide_shortcut.pack(before=self.guide_desc)
        else:
            self.guide_shortcut.pack_forget()

        for i, dot in enumerate(self.dot_labels):
            dot.configure(text="●" if i <= step else "○",
                          text_color=MHY_RED if i <= step else MHY_SUB)

        self.guide_prev_btn.configure(
            state="normal" if step > 0 else "disabled",
            fg_color=MHY_BORDER if step > 0 else "#1a1a2e"
        )
        if step == len(self.guide_steps) - 1:
            self.guide_next_btn.configure(text="✓ 开始使用", fg_color="#2ecc71", hover_color="#27ae60")
        else:
            self.guide_next_btn.configure(text="下一步 ›", fg_color=MHY_RED, hover_color="#e0415c")

    def _guide_next(self):
        if self.guide_step < len(self.guide_steps) - 1:
            self.guide_step += 1
            self._render_guide_step(self.guide_step)
        else:
            save_config("is_first_run", "false")
            self.guide.destroy()

    def _guide_prev(self):
        if self.guide_step > 0:
            self.guide_step -= 1
            self._render_guide_step(self.guide_step)
