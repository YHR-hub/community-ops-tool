"""AI内容工厂 MarketingMixin：社媒文案/活动海报/投放素材"""
import threading, json, datetime
import customtkinter as ctk
from db import get_conn, save_config, load_config
from theme import (
    BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM,
    ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER,
)


# ─────────────────── Prompt 模板 ───────────────────
PLATFORM_GUIDE = {
    "微博": "微博风格：简洁有力，善用#话题标签#，带emoji，140字内，适合快节奏传播",
    "B站": "B站风格：二次元语感，用梗适度，支持长文，鼓励弹幕互动用语",
    "小红书": "小红书风格：种草体，分段+emoji标题，带标题党气息，口语化亲切",
}

STYLE_DESC = {
    "官方": "正式、专业、权威，代表米哈游官方口径",
    "二次元": "中二、热血、充满二次元梗和角色扮演语感",
    "悬念": "制造悬念、吊胃口、引导好奇，适合预热期",
    "热血": "激燃、振奋、充满战斗感和成就感",
}

MODEL_MAP = {
    "DeepSeek":   "deepseek-chat",
    "GPT-4o-mini": "gpt-4o-mini",
}

COPY_TYPES = {
    "社媒文案":  "social",
    "活动海报":  "poster",
    "投放素材":  "ad",
}


def _call_openai_sync(model_name: str, system_prompt: str, user_prompt: str) -> str:
    """同步调用 OpenAI 兼容 API（DeepSeek / GPT-4o-mini）。"""
    from openai import OpenAI
    key = load_config("openai_api_key", "")
    base_url = load_config("openai_base_url", "https://api.openai.com/v1")
    if not key:
        return "[错误] 请先在设置中配置 API Key"
    client = OpenAI(api_key=key, base_url=base_url)
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=2000,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[API 调用失败] {e}"


# ─────────────────── Mixin ───────────────────
class MarketingMixin:
    """为宿主窗口注入 AI 内容工厂页面（create_marketing）。"""

    # ───── 对外入口 ─────
    def create_marketing(self, parent: ctk.CTkFrame):
        """构建 AI 内容工厂页面。"""
        parent.configure(fg_color=BG_DARK)

        # ---- 标题栏 ----
        hdr = ctk.CTkFrame(parent, fg_color=BG_DARK)
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="AI 内容工厂",
            font=("Microsoft YaHei", 20, "bold"), text_color=ACCENT_LIGHT,
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text="社媒文案 / 活动海报 / 投放素材  一键生成",
            font=("Microsoft YaHei", 12), text_color=FG_DIM,
        ).pack(side="left", padx=(12, 0))

        # ---- 主体：左右分栏 ----
        body = ctk.CTkFrame(parent, fg_color=BG_DARK)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10, width=340)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)
        right = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_input_panel(left)
        self._build_output_panel(right)

        # 加载历史
        self._load_history()

    # ───── 左侧输入 ─────
    def _build_input_panel(self, parent: ctk.CTkFrame):
        pad = {"padx": 16, "pady": 6}

        ctk.CTkLabel(
            parent, text="参数设置",
            font=("Microsoft YaHei", 14, "bold"), text_color=FG_TEXT,
        ).pack(anchor="w", **pad)

        # 文案类型
        ctk.CTkLabel(parent, text="文案类型", font=("Microsoft YaHei", 11), text_color=FG_DIM).pack(anchor="w", **pad)
        self._mk_type_var = ctk.StringVar(value="社媒文案")
        ctk.CTkSegmentedButton(
            parent, values=list(COPY_TYPES.keys()),
            variable=self._mk_type_var, font=("Microsoft YaHei", 11),
            selected_color=ACCENT, unselected_color=BG_INPUT,
            selected_hover_color=ACCENT_LIGHT, unselected_hover_color="#1a4a7a",
        ).pack(fill="x", **pad)

        # 主题输入
        ctk.CTkLabel(parent, text="活动 / 主题", font=("Microsoft YaHei", 11), text_color=FG_DIM).pack(anchor="w", **pad)
        self._mk_theme_entry = ctk.CTkTextbox(
            parent, height=80, fg_color=BG_INPUT, text_color=FG_TEXT,
            font=("Microsoft YaHei", 12), border_color=BORDER, border_width=1,
            corner_radius=6, wrap="word",
        )
        self._mk_theme_entry.pack(fill="x", **pad)
        self._mk_theme_entry.insert("1.0", "例：原神4.8版本「幻想真境剧诗」上线")

        # 平台选择
        ctk.CTkLabel(parent, text="目标平台", font=("Microsoft YaHei", 11), text_color=FG_DIM).pack(anchor="w", **pad)
        pf_frame = ctk.CTkFrame(parent, fg_color="transparent")
        pf_frame.pack(fill="x", **pad)
        self._mk_platform_vars = {}
        for i, pf in enumerate(["微博", "B站", "小红书"]):
            var = ctk.BooleanVar(value=(i == 0))
            cb = ctk.CTkCheckBox(
                pf_frame, text=pf, variable=var, font=("Microsoft YaHei", 11),
                fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                text_color=FG_TEXT, border_color=BORDER,
            )
            cb.pack(side="left", padx=(0, 12))
            self._mk_platform_vars[pf] = var

        # 风格选择
        ctk.CTkLabel(parent, text="内容风格", font=("Microsoft YaHei", 11), text_color=FG_DIM).pack(anchor="w", **pad)
        self._mk_style_var = ctk.StringVar(value="官方")
        ctk.CTkSegmentedButton(
            parent, values=list(STYLE_DESC.keys()),
            variable=self._mk_style_var, font=("Microsoft YaHei", 11),
            selected_color=ACCENT, unselected_color=BG_INPUT,
            selected_hover_color=ACCENT_LIGHT, unselected_hover_color="#1a4a7a",
        ).pack(fill="x", **pad)

        # 模型选择
        ctk.CTkLabel(parent, text="AI 模型", font=("Microsoft YaHei", 11), text_color=FG_DIM).pack(anchor="w", **pad)
        self._mk_model_var = ctk.StringVar(value="DeepSeek")
        seg = ctk.CTkSegmentedButton(
            parent, values=list(MODEL_MAP.keys()),
            variable=self._mk_model_var, font=("Microsoft YaHei", 11),
            selected_color=ACCENT, unselected_color=BG_INPUT,
            selected_hover_color=ACCENT_LIGHT, unselected_hover_color="#1a4a7a",
        )
        seg.pack(fill="x", **pad)

        # 生成按钮
        self._mk_gen_btn = ctk.CTkButton(
            parent, text="  一键生成  ", height=40,
            font=("Microsoft YaHei", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_LIGHT,
            command=self._generate_copy,
        )
        self._mk_gen_btn.pack(fill="x", padx=16, pady=(20, 8))

        # 进度条
        self._mk_progress = ctk.CTkProgressBar(
            parent, fg_color=BG_INPUT, progress_color=ACCENT, height=4,
        )
        self._mk_progress.pack(fill="x", padx=16, pady=(0, 4))
        self._mk_progress.set(0)

        # 状态标签
        self._mk_status_label = ctk.CTkLabel(
            parent, text="就绪", font=("Microsoft YaHei", 10), text_color=FG_DIM,
        )
        self._mk_status_label.pack(anchor="w", padx=16, pady=(0, 12))

    # ───── 右侧输出 ─────
    def _build_output_panel(self, parent: ctk.CTkFrame):
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            top_bar, text="生成结果",
            font=("Microsoft YaHei", 14, "bold"), text_color=FG_TEXT,
        ).pack(side="left")
        ctk.CTkButton(
            top_bar, text="复制全部", width=80, height=28,
            font=("Microsoft YaHei", 11), fg_color=BG_INPUT, hover_color=ACCENT,
            command=self._copy_to_clipboard,
        ).pack(side="right")
        ctk.CTkButton(
            top_bar, text="历史记录", width=80, height=28,
            font=("Microsoft YaHei", 11), fg_color=BG_INPUT, hover_color=ACCENT,
            command=self._show_history,
        ).pack(side="right", padx=(0, 8))

        self._mk_output_text = ctk.CTkTextbox(
            parent, fg_color=BG_DARK, text_color=FG_TEXT,
            font=("Microsoft YaHei", 12), border_color=BORDER, border_width=1,
            corner_radius=8, wrap="word", state="disabled",
        )
        self._mk_output_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    # ───── 生成文案 ─────
    def _generate_copy(self):
        theme = self._mk_theme_entry.get("1.0", "end").strip()
        if not theme or theme.startswith("例："):
            self._toast("请先输入活动/主题内容")
            return

        platforms = [p for p, v in self._mk_platform_vars.items() if v.get()]
        if not platforms:
            self._toast("请至少选择一个目标平台")
            return

        style = self._mk_style_var.get()
        model_label = self._mk_model_var.get()
        model_id = MODEL_MAP[model_label]
        copy_type = self._mk_type_var.get()
        copy_type_key = COPY_TYPES[copy_type]

        self._mk_gen_btn.configure(state="disabled", text="生成中...")
        self._mk_progress.set(0.3)
        self._mk_status_label.configure(text=f"正在调用 {model_label} ...")

        def _worker():
            result_parts = []
            for pf in platforms:
                prompt = self._build_prompt(copy_type_key, theme, pf, style)
                system = (
                    "你是米哈游/米游社资深运营文案专家，精通各平台内容风格。"
                    "请直接输出文案正文，不需要额外解释说明。"
                )
                text = _call_openai_sync(model_id, system, prompt)
                result_parts.append(f"【{pf}】\n{'─' * 40}\n{text}\n")
            final = "\n\n".join(result_parts)

            # 存入数据库
            try:
                conn = get_conn()
                conn.execute(
                    "INSERT INTO reports(title, content, type) VALUES(?,?,?)",
                    (f"{copy_type} - {theme[:30]}", final, "marketing"),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            # 回到主线程
            self.after(0, lambda: self._on_generate_done(final, model_label))

        threading.Thread(target=_worker, daemon=True).start()
        self._save_log("营销文案生成", f"类型={copy_type} 平台={platforms} 风格={style} 模型={model_label}")

    def _build_prompt(self, copy_type: str, theme: str, platform: str, style: str) -> str:
        """组装发给 LLM 的 user prompt。"""
        platform_guide = PLATFORM_GUIDE.get(platform, "")
        style_desc = STYLE_DESC.get(style, "")

        if copy_type == "social":
            return (
                f"请为以下游戏活动撰写【{platform}】社媒推广文案。\n\n"
                f"活动主题：{theme}\n"
                f"平台要求：{platform_guide}\n"
                f"风格要求：{style_desc}\n\n"
                "输出要求：\n"
                "1. 标题/开头hook（吸引点击）\n"
                "2. 正文（活动亮点、奖励信息、参与方式）\n"
                "3. 结尾CTA（引导互动/参与）\n"
                "4. 可选：话题标签/关键词\n"
            )
        elif copy_type == "poster":
            return (
                f"请为以下游戏活动设计海报文案方案。\n\n"
                f"活动主题：{theme}\n"
                f"目标平台：{platform}\n"
                f"风格：{style_desc}\n\n"
                "输出要求：\n"
                "1. 主视觉文案（大标题，6字以内，震撼有力）\n"
                "2. 副文案（1-2句补充说明，20字以内）\n"
                "3. CTA行动号召（引导用户点击/参与）\n"
                "4. 辅助文案（活动时间、奖励概览等）\n"
                "5. 设计建议（配色、元素、氛围）\n"
            )
        else:  # ad
            return (
                f"请为以下游戏活动撰写信息流广告文案，需要AB测试版本。\n\n"
                f"活动主题：{theme}\n"
                f"投放平台：{platform}\n"
                f"风格：{style_desc}\n\n"
                "输出要求：\n"
                "【版本A】标题 + 正文 + CTA\n"
                "【版本B】标题 + 正文 + CTA（不同角度/卖点）\n"
                "【版本C】标题 + 正文 + CTA（第三种风格）\n\n"
                "每个版本简短有力，适合信息流卡片展示。\n"
            )

    def _on_generate_done(self, result: str, model_label: str):
        self._mk_progress.set(1.0)
        self._mk_status_label.configure(text=f"生成完成 ({model_label})")
        self._mk_gen_btn.configure(state="normal", text="  一键生成  ")

        self._mk_output_text.configure(state="normal")
        self._mk_output_text.delete("1.0", "end")
        self._mk_output_text.insert("1.0", result)
        self._mk_output_text.configure(state="disabled")

        self._toast("文案生成完成")
        # 1.5 秒后进度条归零
        self.after(1500, lambda: self._mk_progress.set(0))

    # ───── 复制 ─────
    def _copy_to_clipboard(self):
        self._mk_output_text.configure(state="normal")
        content = self._mk_output_text.get("1.0", "end").strip()
        self._mk_output_text.configure(state="disabled")
        if not content:
            self._toast("没有可复制的内容")
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self._toast("已复制到剪贴板")

    # ───── 历史记录 ─────
    def _load_history(self):
        """从 reports 表加载 marketing 类型记录到内存。"""
        try:
            conn = get_conn()
            rows = conn.execute(
                "SELECT id, title, content, created_at FROM reports "
                "WHERE type='marketing' ORDER BY id DESC LIMIT 50"
            ).fetchall()
            conn.close()
            self._mk_history = rows
        except Exception:
            self._mk_history = []

    def _show_history(self):
        """弹出历史记录窗口。"""
        self._load_history()
        win = ctk.CTkToplevel(self)
        win.title("营销文案历史")
        win.geometry("700x500")
        win.configure(fg_color=BG_DARK)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(
            win, text="历史生成记录", font=("Microsoft YaHei", 16, "bold"),
            text_color=ACCENT_LIGHT,
        ).pack(padx=16, pady=(16, 8), anchor="w")

        scroll = ctk.CTkScrollableFrame(win, fg_color=BG_CARD, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        if not self._mk_history:
            ctk.CTkLabel(
                scroll, text="暂无历史记录", font=("Microsoft YaHei", 12), text_color=FG_DIM,
            ).pack(pady=40)
            return

        for rid, title, content, created_at in self._mk_history:
            row = ctk.CTkFrame(scroll, fg_color=BG_INPUT, corner_radius=6)
            row.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(
                row, text=title, font=("Microsoft YaHei", 12, "bold"), text_color=FG_TEXT,
                anchor="w",
            ).pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(
                row, text=created_at or "", font=("Microsoft YaHei", 10), text_color=FG_DIM,
            ).pack(side="right", padx=12, pady=8)

            def _load(c=content, t=title):
                self._mk_output_text.configure(state="normal")
                self._mk_output_text.delete("1.0", "end")
                self._mk_output_text.insert("1.0", c)
                self._mk_output_text.configure(state="disabled")
                self._toast(f"已加载: {t}")
                win.destroy()

            ctk.CTkButton(
                row, text="加载", width=50, height=26,
                font=("Microsoft YaHei", 10), fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                command=_load,
            ).pack(side="right", padx=(0, 8), pady=8)
