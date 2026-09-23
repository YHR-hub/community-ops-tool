"""AI 运营顾问 Mixin：Prompt 场景选择、OpenAI 兼容接口异步调用、结果持久化"""
import customtkinter as ctk
from tkinter import messagebox
import threading, datetime

from theme import (
    BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM,
    ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, BORDER,
)
import db


# ── 常量 ──────────────────────────────────────────────
MODELS = ["deepseek-chat", "gpt-4o-mini", "deepseek-v4-pro", "gpt-4o"]

SCENARIOS = [
    ("活动复盘", "活动复盘分析师",
     "你是一位资深游戏运营分析师，请根据用户提供的活动数据，从参与率、留存、转化、ROI 等维度进行复盘分析，并给出改进建议。输出格式：# 活动复盘分析\\n## 核心数据\\n## 亮点\\n## 问题\\n## 改进建议"),
    ("舆情分析", "舆情分析师",
     "你是一位游戏社区舆情分析专家，请根据用户提供的舆情数据（评论、帖子、反馈），分析用户情感倾向、主要诉求、潜在风险，并给出应对建议。输出格式：# 舆情分析报告\\n## 情感分布\\n## 热点话题\\n## 风险预警\\n## 应对建议"),
    ("竞品分析", "竞品分析师",
     "你是一位游戏行业竞品分析师，请根据用户提供的竞品信息，从产品定位、运营策略、社区活跃度等维度进行对比分析。输出格式：# 竞品分析报告\\n## 竞品概况\\n## 策略对比\\n## 优势劣势\\n## 可借鉴点"),
    ("用户画像", "用户画像分析师",
     "你是一位用户增长分析师，请根据用户提供的用户数据（行为、偏好、反馈），构建用户画像，识别核心用户群体特征。输出格式：# 用户画像分析\\n## 核心群体\\n## 行为特征\\n## 偏好洞察\\n## 运营建议"),
    ("内容策划", "内容策划师",
     "你是一位游戏内容策划专家，请根据用户提供的主题和目标受众，策划内容方案，包含选题、角度、大纲和预期效果。输出格式：# 内容策划方案\\n## 选题建议\\n## 内容大纲\\n## 发布渠道\\n## 预期效果"),
    ("数据解读", "数据解读专家",
     "你是一位运营数据解读专家，请根据用户提供的运营数据（DAU、帖子、评论等指标），分析趋势、发现异常、给出解读和行动建议。输出格式：# 数据解读报告\\n## 趋势分析\\n## 异常发现\\n## 原因推测\\n## 行动建议"),
]


class AIMixin:
    """AI 运营顾问页面：场景 Prompt + 线程调用 + 配置持久化"""

    # ────────────────── 入口 ──────────────────
    def create_ai(self, parent):
        """构建 AI 运营顾问页面"""
        self._ai_frame = ctk.CTkFrame(parent, fg_color=BG_DARK)
        self._ai_frame.pack(fill="both", expand=True)

        # ── 顶部配置栏 ──
        cfg_bar = ctk.CTkFrame(self._ai_frame, fg_color=BG_CARD, corner_radius=10)
        cfg_bar.pack(fill="x", padx=16, pady=(16, 8))

        # API Key
        ctk.CTkLabel(cfg_bar, text="API Key", font=("Microsoft YaHei", 11),
                     text_color=FG_DIM).grid(row=0, column=0, padx=(12, 4), pady=8, sticky="w")
        self._ai_key_entry = ctk.CTkEntry(cfg_bar, fg_color=BG_INPUT, text_color=FG_TEXT,
                                           border_color=BORDER, show="*",
                                           placeholder_text="sk-...",
                                           font=("Microsoft YaHei", 11), width=320)
        self._ai_key_entry.grid(row=0, column=1, padx=4, pady=8, sticky="ew")

        # 模型选择
        ctk.CTkLabel(cfg_bar, text="模型", font=("Microsoft YaHei", 11),
                     text_color=FG_DIM).grid(row=0, column=2, padx=(16, 4), pady=8, sticky="w")
        self._ai_model_cb = ctk.CTkComboBox(cfg_bar, values=MODELS, fg_color=BG_INPUT,
                                              text_color=FG_TEXT, border_color=BORDER,
                                              button_color=ACCENT, button_hover_color=ACCENT_LIGHT,
                                              dropdown_fg_color=BG_CARD,
                                              dropdown_hover_color=BG_INPUT,
                                              font=("Microsoft YaHei", 11), width=180)
        self._ai_model_cb.set(MODELS[0])
        self._ai_model_cb.grid(row=0, column=3, padx=4, pady=8, sticky="w")

        # 保存配置
        ctk.CTkButton(cfg_bar, text="保存配置", fg_color=SUCCESS, hover_color="#27ae60",
                      font=("Microsoft YaHei", 11, "bold"), width=90,
                      command=self._ai_save_config).grid(row=0, column=4, padx=(8, 12), pady=8)

        cfg_bar.columnconfigure(1, weight=1)

        # ── 场景选择 ──
        scene_bar = ctk.CTkFrame(self._ai_frame, fg_color=BG_CARD, corner_radius=10)
        scene_bar.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(scene_bar, text="运营场景", font=("Microsoft YaHei", 12, "bold"),
                     text_color=FG_TEXT).pack(anchor="w", padx=12, pady=(8, 4))

        btns_frame = ctk.CTkFrame(scene_bar, fg_color="transparent")
        btns_frame.pack(fill="x", padx=12, pady=(0, 10))

        self._ai_scenario = ctk.StringVar(value=SCENARIOS[0][0])
        self._ai_scene_btns = {}
        for i, (name, role, prompt) in enumerate(SCENARIOS):
            btn = ctk.CTkButton(btns_frame, text=name, fg_color=BG_INPUT, hover_color=ACCENT,
                                font=("Microsoft YaHei", 10), width=90, height=30,
                                command=lambda n=name: self._ai_select_scenario(n))
            btn.grid(row=0, column=i, padx=4, pady=2)
            self._ai_scene_btns[name] = btn

        # 默认选中第一个
        self._ai_scene_btns[SCENARIOS[0][0]].configure(fg_color=ACCENT)

        # ── 中间区域：输入 + 输出 ──
        mid = ctk.CTkFrame(self._ai_frame, fg_color=BG_DARK)
        mid.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # 左：输入
        left = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        ctk.CTkLabel(left, text="输入内容", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(anchor="w", padx=12, pady=(10, 4))

        self._ai_input = ctk.CTkTextbox(left, fg_color=BG_INPUT, text_color=FG_TEXT,
                                         border_color=BORDER, font=("Microsoft YaHei", 11),
                                         wrap="word")
        self._ai_input.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self._ai_input.insert("1.0", "请粘贴运营数据或描述你的需求...")

        # 右：输出
        right = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10)
        right.pack(side="right", fill="both", expand=True, padx=(0, 0))

        ctk.CTkLabel(right, text="AI 输出", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(anchor="w", padx=12, pady=(10, 4))

        self._ai_output = ctk.CTkTextbox(right, fg_color=BG_INPUT, text_color=FG_TEXT,
                                          border_color=BORDER, font=("Microsoft YaHei", 11),
                                          wrap="word", state="disabled")
        self._ai_output.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # ── 底部按钮栏 ──
        bottom = ctk.CTkFrame(self._ai_frame, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 16))

        self._ai_gen_btn = ctk.CTkButton(bottom, text="发送请求", fg_color=ACCENT,
                                          hover_color=ACCENT_LIGHT,
                                          font=("Microsoft YaHei", 12, "bold"),
                                          width=140, command=self._call_ai)
        self._ai_gen_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(bottom, text="保存结果", fg_color=SUCCESS, hover_color="#27ae60",
                      font=("Microsoft YaHei", 12), width=110,
                      command=self._save_ai_result).pack(side="left", padx=(0, 8))

        ctk.CTkButton(bottom, text="清空", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 12), width=80,
                      command=self._ai_clear).pack(side="left")

        self._ai_status = ctk.CTkLabel(bottom, text="", font=("Microsoft YaHei", 11),
                                        text_color=FG_DIM)
        self._ai_status.pack(side="right")

        # 加载已保存配置
        self._ai_load_config()

        return self._ai_frame

    # ────────────────── 场景切换 ──────────────────
    def _ai_select_scenario(self, name):
        """切换场景高亮"""
        self._ai_scenario.set(name)
        for n, btn in self._ai_scene_btns.items():
            btn.configure(fg_color=ACCENT if n == name else BG_INPUT)

    def _ai_get_scenario_prompt(self):
        """获取当前选中场景的 system prompt"""
        name = self._ai_scenario.get()
        for sn, role, prompt in SCENARIOS:
            if sn == name:
                return role, prompt
        return SCENARIOS[0][1], SCENARIOS[0][2]

    # ────────────────── 配置加载/保存 ──────────────────
    def _ai_load_config(self):
        """从 config 表加载 API Key 和模型"""
        key = db.load_config("ai_api_key", "")
        model = db.load_config("ai_model", MODELS[0])
        if key:
            self._ai_key_entry.delete(0, "end")
            self._ai_key_entry.insert(0, key)
        if model in MODELS:
            self._ai_model_cb.set(model)

    def _ai_save_config(self):
        """保存 API Key 和模型到 config 表"""
        key = self._ai_key_entry.get().strip()
        model = self._ai_model_cb.get().strip()
        db.save_config("ai_api_key", key)
        db.save_config("ai_model", model)
        self._save_log("AI配置", f"模型={model}")
        self._toast("配置已保存")

    # ────────────────── 调用 AI ──────────────────
    def _call_ai(self):
        """后台线程调用 OpenAI 兼容接口"""
        api_key = self._ai_key_entry.get().strip()
        if not api_key:
            messagebox.showwarning("缺少 API Key", "请先输入 API Key")
            return

        user_input = self._ai_input.get("1.0", "end").strip()
        if not user_input or user_input == "请粘贴运营数据或描述你的需求...":
            messagebox.showwarning("缺少输入", "请输入你的问题或数据")
            return

        # 自动保存配置
        model = self._ai_model_cb.get().strip()
        db.save_config("ai_api_key", api_key)
        db.save_config("ai_model", model)

        # 禁用按钮
        self._ai_gen_btn.configure(state="disabled", text="生成中...")
        self._ai_status.configure(text="正在请求 AI 服务，请稍候...")

        # 清空输出
        self._ai_output.configure(state="normal")
        self._ai_output.delete("1.0", "end")
        self._ai_output.insert("1.0", "正在生成中，请稍候...")
        self._ai_output.configure(state="disabled")

        role, system_prompt = self._ai_get_scenario_prompt()

        def _worker():
            try:
                from openai import OpenAI

                # 判断是否为 DeepSeek 模型，设置对应 base_url
                base_url = None
                if "deepseek" in model.lower():
                    base_url = "https://api.deepseek.com"

                client_kwargs = {"api_key": api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url

                client = OpenAI(**client_kwargs)

                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                    temperature=0.7,
                    max_tokens=2000,
                )
                result = resp.choices[0].message.content
                error = None
            except Exception as exc:
                result = ""
                error = str(exc)

            # 回主线程更新 UI
            self.after(0, lambda: self._ai_on_done(result, error, role))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_on_done(self, result, error, role):
        """AI 调用完成回调（主线程）"""
        self._ai_gen_btn.configure(state="normal", text="发送请求")

        if error:
            self._ai_status.configure(text="请求失败")
            self._ai_output.configure(state="normal")
            self._ai_output.delete("1.0", "end")
            self._ai_output.insert("1.0", f"[错误] {error}")
            self._ai_output.configure(state="disabled")
            self._toast("AI 请求失败")
            return

        self._ai_status.configure(text=f"生成完成 · {role}")
        self._ai_output.configure(state="normal")
        self._ai_output.delete("1.0", "end")
        self._ai_output.insert("1.0", result)
        self._ai_output.configure(state="disabled")
        self._save_log("AI生成", f"场景={self._ai_scenario.get()} 模型={self._ai_model_cb.get()}")
        self._toast("AI 已生成")

    # ────────────────── 保存结果 ──────────────────
    def _save_ai_result(self):
        """将 AI 输出保存到 reports 表"""
        content = self._ai_output.get("1.0", "end").strip()
        if not content or content.startswith("正在生成中") or content.startswith("[错误]"):
            self._toast("没有可保存的内容")
            return

        scenario = self._ai_scenario.get()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"AI-{scenario}-{now}"

        try:
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO reports(title, content, type) VALUES(?,?,?)",
                    (title, content, "ai_report"),
                )
                conn.commit()
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return

        self._save_log("AI结果保存", f"{title}")
        self._toast("结果已保存到报告库")

    # ────────────────── 清空 ──────────────────
    def _ai_clear(self):
        """清空输入和输出"""
        self._ai_input.delete("1.0", "end")
        self._ai_output.configure(state="normal")
        self._ai_output.delete("1.0", "end")
        self._ai_output.configure(state="disabled")
        self._ai_status.configure(text="")
