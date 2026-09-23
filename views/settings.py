"""设置模块 SettingsMixin：统一管理AI后端配置
支持 OpenAI / DeepSeek / Ollama（本地大模型）三种AI后端
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from theme import (
    BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM,
    ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER,
)
import db

# ── 统一字号 ──
F_TITLE  = ("Microsoft YaHei", 16, "bold")
F_SEC    = ("Microsoft YaHei", 12, "bold")
F_LABEL  = ("Microsoft YaHei", 10)
F_SMALL  = ("Microsoft YaHei", 9)
F_TINY   = ("Microsoft YaHei", 8)
F_ENTRY  = ("Microsoft YaHei", 11)
F_BTN    = ("Microsoft YaHei", 11, "bold")

# ── AI后端预设 ──
AI_PRESETS = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder"],
        "desc": "国产大模型，性价比高，中文优秀",
        "icon": "🔮",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        "desc": "国际主流大模型，GPT-4o能力最强",
        "icon": "🌐",
    },
    "Ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": ["（点击下方按钮自动识别本地模型）"],
        "desc": "本地大模型，无需联网，隐私安全",
        "icon": "🦙",
    },
}


class SettingsMixin:
    """设置页面：统一管理AI后端、模型、API Key"""

    def create_settings(self, parent):
        self._settings_frame = ctk.CTkScrollableFrame(parent, fg_color=BG_DARK)
        self._settings_frame.pack(fill="both", expand=True)

        # ── 标题区 ──
        title_bar = ctk.CTkFrame(self._settings_frame, fg_color=BG_DARK)
        title_bar.pack(fill="x", padx=24, pady=(16, 0))
        ctk.CTkLabel(title_bar, text="⚙️  AI 设置", font=F_TITLE,
                     text_color=GOLD, fg_color=BG_DARK).pack(side="left")
        ctk.CTkLabel(title_bar, text="配置AI后端，支持云端API和本地大模型（Ollama）",
                     font=F_SMALL, text_color=FG_DIM,
                     fg_color=BG_DARK).pack(side="left", padx=12)

        # 金色分隔线
        sep = tk.Canvas(self._settings_frame, height=1, bg=BG_DARK, highlightthickness=0)
        sep.pack(fill="x", padx=24, pady=12)
        sep.create_line(0, 0, 1200, 0, fill=GOLD, width=1)

        # ── 两栏网格 ──
        grid = ctk.CTkFrame(self._settings_frame, fg_color=BG_DARK)
        grid.pack(fill="x", padx=24, pady=0)
        grid.columnconfigure(0, weight=1)  # 左栏：后端+Ollama
        grid.columnconfigure(1, weight=2)  # 右栏：配置详情

        # ┌─ 左栏：后端选择 + Ollama识别 ─┐
        col_left = ctk.CTkFrame(grid, fg_color=BG_CARD, corner_radius=12)
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(col_left, text="🔌 选择AI后端", font=F_SEC,
                     text_color=GOLD, fg_color=BG_CARD).pack(pady=(16, 12), padx=16, anchor="w")

        self._settings_backend_var = ctk.StringVar(value=db.load_config("ai_backend", "DeepSeek"))
        self._settings_backend_btns = {}

        for name, info in AI_PRESETS.items():
            frame = ctk.CTkFrame(col_left, fg_color=BG_INPUT, corner_radius=10)
            frame.pack(fill="x", padx=12, pady=4)

            top_row = ctk.CTkFrame(frame, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 0))

            radio = ctk.CTkRadioButton(top_row, text=f"  {info['icon']}  {name}",
                                        variable=self._settings_backend_var,
                                        value=name, fg_color=GOLD, hover_color=GOLD_LIGHT,
                                        font=F_SEC, text_color=FG_TEXT,
                                        command=self._on_backend_change)
            radio.pack(side="left")

            ctk.CTkLabel(frame, text=info["desc"], font=F_TINY,
                         text_color=FG_DIM, wraplength=300,
                         fg_color="transparent").pack(anchor="w", padx=36, pady=(2, 8))

            self._settings_backend_btns[name] = frame

        # 当前后端状态指示
        self._backend_status = ctk.CTkLabel(col_left, text="",
                                             font=F_SMALL, text_color=SUCCESS,
                                             fg_color=BG_CARD, wraplength=300)
        self._backend_status.pack(padx=16, pady=(8, 4), anchor="w")

        # 金色分隔线
        sep_l = tk.Canvas(col_left, height=1, bg=BG_CARD, highlightthickness=0)
        sep_l.pack(fill="x", padx=16, pady=8)
        sep_l.create_line(0, 0, 500, 0, fill=GOLD, width=1)

        # Ollama本地模型识别区
        self._ollama_panel = ctk.CTkFrame(col_left, fg_color=BG_CARD, corner_radius=8)
        self._ollama_panel.pack(fill="x", padx=12, pady=(0, 4))

        ollama_header = ctk.CTkFrame(self._ollama_panel, fg_color="transparent")
        ollama_header.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(ollama_header, text="🦙 本地模型识别", font=F_SEC,
                     text_color=GOLD, fg_color=BG_CARD).pack(side="left")
        ctk.CTkButton(ollama_header, text="🔍 自动识别", width=90, height=28,
                      fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                      font=F_SMALL, command=self._detect_ollama_models).pack(side="right")

        self._ollama_status_lbl = ctk.CTkLabel(self._ollama_panel, text="点击「自动识别」扫描本地模型",
                                                font=F_SMALL, text_color=FG_DIM,
                                                fg_color=BG_CARD, wraplength=300, justify="left")
        self._ollama_status_lbl.pack(anchor="w", padx=12, pady=(0, 4))

        self._ollama_model_frame = ctk.CTkScrollableFrame(self._ollama_panel, fg_color=BG_INPUT,
                                                            height=160, corner_radius=6)
        self._ollama_model_frame.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(self._ollama_model_frame, text="暂无数据\n请先安装Ollama并运行",
                     font=F_SMALL, text_color=FG_DIM).pack(pady=20)

        # ┌─ 右栏：配置详情 ─┐
        col_right = ctk.CTkFrame(grid, fg_color=BG_CARD, corner_radius=12)
        col_right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        ctk.CTkLabel(col_right, text="🔧 配置详情", font=F_SEC,
                     text_color=GOLD, fg_color=BG_CARD).pack(pady=(16, 12), padx=16, anchor="w")

        # API Key
        self._settings_key = self._make_entry_row(col_right, "API Key", "•",
                                                   db.load_config("ai_api_key", ""),
                                                   "输入API Key")

        # Base URL
        self._settings_url = self._make_entry_row(col_right, "Base URL", None,
                                                    db.load_config("ai_base_url", "https://api.deepseek.com/v1"),
                                                    "https://api.deepseek.com/v1")

        # 模型下拉
        ctk.CTkLabel(col_right, text="模型", font=F_LABEL,
                     text_color=FG_TEXT, fg_color=BG_CARD).pack(anchor="w", padx=20, pady=(12, 0))
        self._settings_model_var = ctk.StringVar(value=db.load_config("ai_model", "deepseek-chat"))
        self._settings_model_menu = ctk.CTkOptionMenu(
            col_right, variable=self._settings_model_var,
            values=AI_PRESETS["DeepSeek"]["models"],
            width=300, fg_color=BG_INPUT, text_color=FG_TEXT,
            button_color=ACCENT, button_hover_color=ACCENT_LIGHT,
            dropdown_fg_color=BG_CARD, dropdown_hover_color=BG_INPUT,
            font=F_ENTRY
        )
        self._settings_model_menu.pack(fill="x", padx=20, pady=(4, 8))

        # 自定义模型名
        self._settings_custom_model = self._make_entry_row(
            col_right, "自定义模型名（Ollama专用，留空使用上方选择）", None,
            db.load_config("ai_custom_model", ""), "例如: qwen2.5:14b"
        )

        # 金色分隔线
        sep2 = tk.Canvas(col_right, height=1, bg=BG_CARD, highlightthickness=0)
        sep2.pack(fill="x", padx=20, pady=12)
        sep2.create_line(0, 0, 800, 0, fill=GOLD, width=1)

        # 按钮行
        btn_row = ctk.CTkFrame(col_right, fg_color=BG_CARD)
        btn_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(btn_row, text="💾 保存配置", width=120, fg_color=ACCENT,
                      hover_color=ACCENT_LIGHT, font=F_BTN,
                      command=self._save_settings).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="🧪 测试连接", width=120, fg_color=BG_INPUT,
                      hover_color=SUCCESS, text_color=FG_TEXT,
                      font=F_BTN, command=self._test_ai).pack(side="left")

        # 测试结果区
        ctk.CTkLabel(col_right, text="测试结果", font=F_SMALL,
                     text_color=FG_DIM, fg_color=BG_CARD).pack(anchor="w", padx=20, pady=(4, 2))
        self._settings_test_result = ctk.CTkTextbox(col_right, height=100, fg_color=BG_INPUT,
                                                      text_color=FG_TEXT, font=F_SMALL,
                                                      corner_radius=8)
        self._settings_test_result.pack(fill="x", padx=20, pady=(0, 16))
        self._settings_test_result.insert("end", "等待测试...")

        # ── 底部帮助 ──
        help_frame = ctk.CTkFrame(self._settings_frame, fg_color=BG_CARD, corner_radius=10)
        help_frame.pack(fill="x", padx=24, pady=(12, 16))
        help_text = (
            "💡 使用说明\n\n"
            "☁️  DeepSeek：注册 https://platform.deepseek.com 获取API Key，性价比最高的国产大模型\n"
            "☁️  OpenAI：注册 https://platform.openai.com 获取API Key，GPT-4o能力最强\n"
            "🦙  Ollama：安装 https://ollama.com → 运行 ollama pull qwen2.5:7b → 点击「自动识别」\n"
            "🔑  Ollama无需API Key，模型完全本地运行，隐私安全"
        )
        ctk.CTkLabel(help_frame, text=help_text, font=F_SMALL,
                     text_color=FG_DIM, fg_color=BG_CARD, justify="left",
                     wraplength=900).pack(padx=16, pady=12, anchor="w")

        # 初始化后端状态
        self._on_backend_change()
        return self._settings_frame

    def _make_entry_row(self, parent, label, show, default, placeholder):
        """创建一行：标签 + 输入框"""
        ctk.CTkLabel(parent, text=label, font=F_LABEL,
                     text_color=FG_TEXT, fg_color=BG_CARD).pack(anchor="w", padx=20, pady=(12, 0))
        entry = ctk.CTkEntry(parent, fg_color=BG_INPUT, text_color=FG_TEXT,
                             border_color=BORDER, show=show,
                             placeholder_text=placeholder, font=F_ENTRY,
                             corner_radius=8)
        entry.pack(fill="x", padx=20, pady=(4, 8))
        if default:
            entry.insert(0, default)
        return entry

    def _on_backend_change(self):
        """切换AI后端时更新配置"""
        backend = self._settings_backend_var.get()
        preset = AI_PRESETS.get(backend, AI_PRESETS["DeepSeek"])

        # 更新Base URL
        self._settings_url.delete(0, "end")
        self._settings_url.insert(0, db.load_config(f"ai_base_url_{backend}", preset["base_url"]))

        # 更新模型下拉
        self._settings_model_menu.configure(values=preset["models"])
        saved_model = db.load_config(f"ai_model_{backend}", preset["models"][0])
        self._settings_model_var.set(saved_model)

        # 更新状态指示
        self._backend_status.configure(text=f"当前后端: {preset['icon']} {backend}")

        # Ollama不需要API Key
        if backend == "Ollama":
            self._settings_key.configure(placeholder_text="Ollama无需API Key，可留空")
        else:
            self._settings_key.configure(placeholder_text="输入API Key")

    def _detect_ollama_models(self):
        """自动识别本地Ollama已安装的所有模型"""
        self._ollama_status_lbl.configure(text="🔍 正在扫描本地模型...", text_color=WARNING)

        # 清空列表
        for w in self._ollama_model_frame.winfo_children():
            w.destroy()

        def do_detect():
            """后台线程：只做网络请求，不碰UI"""
            try:
                import urllib.request
                req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    models = data.get("models", [])
                # 回到主线程更新UI
                self.after(0, lambda: self._on_detect_result(models, None))
            except Exception as e:
                self.after(0, lambda: self._on_detect_result(None, str(e)))

        threading.Thread(target=do_detect, daemon=True).start()

    def _on_detect_result(self, models, error):
        """主线程回调：更新Ollama识别结果UI"""
        if error:
            if "URLError" in error or "ConnectionRefused" in error or "10061" in error:
                self._ollama_status_lbl.configure(
                    text="❌ Ollama未运行\n请先安装并启动Ollama服务\nhttps://ollama.com",
                    text_color=DANGER)
            else:
                self._ollama_status_lbl.configure(
                    text=f"❌ 扫描失败: {error[:60]}",
                    text_color=DANGER)
            return

        if not models:
            self._ollama_status_lbl.configure(
                text="⚠️ Ollama运行中，但未安装模型\n请运行: ollama pull qwen2.5:7b",
                text_color=WARNING)
            return

        self._ollama_status_lbl.configure(
            text=f"✅ 发现 {len(models)} 个本地模型",
            text_color=SUCCESS)

        model_names = []
        for m in models:
            name = m.get("name", "unknown")
            size_bytes = m.get("size", 0)
            size_gb = size_bytes / (1024**3)
            modified = m.get("modified_at", "")[:10]
            model_names.append(name)

            # 模型卡片
            card = ctk.CTkFrame(self._ollama_model_frame, fg_color=BG_CARD, corner_radius=8)
            card.pack(fill="x", padx=4, pady=3)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=6)
            ctk.CTkLabel(info_frame, text=f"📦 {name}",
                         font=F_LABEL, text_color=FG_TEXT,
                         fg_color=BG_CARD).pack(anchor="w")
            ctk.CTkLabel(info_frame, text=f"{size_gb:.1f}GB · {modified}",
                         font=F_TINY, text_color=FG_DIM,
                         fg_color=BG_CARD).pack(anchor="w")

            ctk.CTkButton(card, text="使用", width=50, height=26,
                          fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                          font=F_SMALL,
                          command=lambda n=name: self._select_ollama_model(n)).pack(side="right", padx=10, pady=6)

        # 更新模型下拉
        self._settings_model_menu.configure(values=model_names)
        if model_names:
            self._settings_model_var.set(model_names[0])

        db.save_config("ollama_models", json.dumps(model_names))
        db.save_config("ai_model_Ollama", model_names[0])

    def _select_ollama_model(self, model_name):
        """选择一个Ollama模型"""
        self._settings_model_var.set(model_name)
        self._settings_custom_model.delete(0, "end")
        self._settings_custom_model.insert(0, model_name)
        self._settings_backend_var.set("Ollama")
        self._on_backend_change()
        self._toast(f"已选择模型: {model_name}")

    def _save_settings(self):
        """保存所有AI配置"""
        backend = self._settings_backend_var.get()
        api_key = self._settings_key.get().strip()
        base_url = self._settings_url.get().strip()
        model = self._settings_model_var.get()
        custom_model = self._settings_custom_model.get().strip()

        db.save_config("ai_backend", backend)
        db.save_config("ai_api_key", api_key)
        db.save_config("ai_base_url", base_url)
        db.save_config("ai_model", model)
        db.save_config("ai_custom_model", custom_model)
        db.save_config(f"ai_base_url_{backend}", base_url)
        db.save_config(f"ai_model_{backend}", model)

        if custom_model:
            db.save_config("ai_active_model", custom_model)
        else:
            db.save_config("ai_active_model", model)

        self._toast(f"✅ 配置已保存 | 后端: {backend} | 模型: {custom_model or model}")

    def _test_ai(self):
        """测试AI连接"""
        backend = self._settings_backend_var.get()
        api_key = self._settings_key.get().strip()
        base_url = self._settings_url.get().strip()
        model = self._settings_custom_model.get().strip() or self._settings_model_var.get()

        self._settings_test_result.delete("1.0", "end")
        self._settings_test_result.insert("end", f"正在测试 {backend} ({model})...\n")

        def do_test():
            """后台线程：只做网络请求"""
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key or "ollama", base_url=base_url)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "你好，请用一句话介绍你自己"}],
                    max_tokens=100,
                    timeout=15,
                )
                reply = resp.choices[0].message.content
                self.after(0, lambda: self._on_test_result(True, reply))
            except Exception as e:
                self.after(0, lambda: self._on_test_result(False, str(e)))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_test_result(self, success, msg):
        """主线程回调：更新测试结果"""
        self._settings_test_result.delete("1.0", "end")
        if success:
            self._settings_test_result.insert("end", f"✅ 连接成功！\n\n模型回复：{msg}")
        else:
            self._settings_test_result.insert("end", f"❌ 连接失败：{msg}")

    def get_ai_config(self):
        """获取当前AI配置（供其他模块调用）"""
        return {
            "backend": db.load_config("ai_backend", "DeepSeek"),
            "api_key": db.load_config("ai_api_key", ""),
            "base_url": db.load_config("ai_base_url", "https://api.deepseek.com/v1"),
            "model": db.load_config("ai_active_model", "deepseek-chat"),
        }
