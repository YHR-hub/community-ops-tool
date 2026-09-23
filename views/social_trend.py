"""社媒趋势雷达 SocialTrendMixin：真实数据爬取 + 热点追踪 + AI分析"""
import threading, random, datetime
import customtkinter as ctk
from db import get_conn, save_config, load_config
from theme import (
    BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM,
    ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER,
)


# ─────────────────── 预设热点数据 ───────────────────
PRESET_TRENDS = [
    # 微博
    {"platform": "微博", "keyword": "原神新角色",       "heat": 95, "desc": "原神5.0新角色立绘曝光引发热议"},
    {"platform": "微博", "keyword": "崩铁周年庆",       "heat": 92, "desc": "崩坏：星穹铁道2周年活动全平台讨论"},
    {"platform": "微博", "keyword": "绝区零版本更新",    "heat": 88, "desc": "绝区零1.4版本新角色+新地图"},
    {"platform": "微博", "keyword": "米哈游新春会",     "heat": 85, "desc": "米哈游新春拜年祭预约破千万"},
    {"platform": "微博", "keyword": "原神音乐会",       "heat": 78, "desc": "原神线上音乐会直播预告"},
    {"platform": "微博", "keyword": "崩铁同人创作",     "heat": 72, "desc": "星穹铁道同人大赛作品刷屏"},
    {"platform": "微博", "keyword": "原神剧情讨论",     "heat": 68, "desc": "纳塔主线剧情解析引发玩家讨论"},
    {"platform": "微博", "keyword": "绝区零联动",       "heat": 65, "desc": "绝区零x知名IP联动爆料"},
    # B站
    {"platform": "B站",  "keyword": "原神二创",         "heat": 93, "desc": "原神二创视频播放量突破纪录"},
    {"platform": "B站",  "keyword": "崩铁攻略",         "heat": 90, "desc": "星穹铁道新版本角色攻略合集"},
    {"platform": "B站",  "keyword": "米哈游整活",       "heat": 86, "desc": "米哈游官方B站趣味内容"},
    {"platform": "B站",  "keyword": "绝区零角色演示",    "heat": 82, "desc": "绝区零角色战斗演示视频"},
    {"platform": "B站",  "keyword": "原神实况",         "heat": 76, "desc": "原神版本实况解说"},
    {"platform": "B站",  "keyword": "崩铁MMD",          "heat": 70, "desc": "星穹铁道角色MMD舞蹈"},
    {"platform": "B站",  "keyword": "绝区零二创",       "heat": 67, "desc": "绝区零同人动画/漫画"},
    {"platform": "B站",  "keyword": "米游社日常",       "heat": 60, "desc": "米游社社区日常趣味投稿"},
    # 小红书
    {"platform": "小红书", "keyword": "原神穿搭",        "heat": 91, "desc": "原神角色cos穿搭分享"},
    {"platform": "小红书", "keyword": "崩铁壁纸",        "heat": 87, "desc": "星穹铁道高清壁纸合集"},
    {"platform": "小红书", "keyword": "绝区零手办",      "heat": 83, "desc": "绝区零角色手办开箱"},
    {"platform": "小红书", "keyword": "米游社周边",      "heat": 79, "desc": "米哈游官方周边种草"},
    {"platform": "小红书", "keyword": "原神食谱",        "heat": 74, "desc": "原神料理复刻教程"},
    {"platform": "小红书", "keyword": "崩铁角色分析",    "heat": 71, "desc": "星穹铁道角色强度分析"},
    {"platform": "小红书", "keyword": "绝区零攻略",      "heat": 66, "desc": "绝区零新手入门指南"},
    {"platform": "小红书", "keyword": "原神拍照打卡",    "heat": 62, "desc": "原神取景地打卡分享"},
]

PLATFORMS = ["全部", "微博", "B站", "小红书"]


def _call_openai_trend_sync(system_prompt: str, user_prompt: str) -> str:
    """同步调用 OpenAI 兼容 API 分析趋势。"""
    from openai import OpenAI
    key = load_config("openai_api_key", "")
    base_url = load_config("openai_base_url", "https://api.openai.com/v1")
    if not key:
        return "[错误] 请先在设置中配置 API Key"
    model = load_config("ai_model", "deepseek-chat")
    client = OpenAI(api_key=key, base_url=base_url)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[API 调用失败] {e}"


def _heat_color(score: int) -> str:
    """根据热度分数返回颜色。"""
    if score >= 90:
        return DANGER
    elif score >= 80:
        return ACCENT
    elif score >= 70:
        return WARNING
    else:
        return SUCCESS


# ─────────────────── Mixin ───────────────────
class SocialTrendMixin:
    """为宿主窗口注入社媒趋势雷达页面（create_social_trend）。"""

    # ───── 对外入口 ─────
    def create_social_trend(self, parent: ctk.CTkFrame):
        """构建社媒趋势雷达页面。"""
        parent.configure(fg_color=BG_DARK)

        # ---- 标题栏 ----
        hdr = ctk.CTkFrame(parent, fg_color=BG_DARK)
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="社媒趋势雷达",
            font=("Microsoft YaHei", 20, "bold"), text_color=ACCENT_LIGHT,
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text="实时热点追踪 + AI 内容方向推荐",
            font=("Microsoft YaHei", 12), text_color=FG_DIM,
        ).pack(side="left", padx=(12, 0))

        # ---- 筛选栏 ----
        self._build_filter_bar(parent)

        # ---- 刷新按钮 ----
        ctk.CTkButton(
            hdr, text="🔄 刷新实时数据", width=140, height=30,
            fg_color=ACCENT, hover_color=ACCENT_LIGHT,
            font=("Microsoft YaHei", 10, "bold"),
            command=self._fetch_real_trends
        ).pack(side="right", padx=8)

        self._st_status_lbl = ctk.CTkLabel(
            hdr, text="", font=("Microsoft YaHei", 9), text_color=FG_DIM
        )
        self._st_status_lbl.pack(side="right", padx=4)

        # ---- 主体区域 ----
        body = ctk.CTkFrame(parent, fg_color=BG_DARK)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=3)
        body.grid_rowconfigure(1, weight=2)

        # 上方：热点卡片网格
        self._trend_grid_frame = ctk.CTkScrollableFrame(
            body, fg_color=BG_CARD, corner_radius=10,
        )
        self._trend_grid_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        # 下方：AI分析建议区
        self._build_analysis_panel(body)

        # 初始化数据
        self._st_current_filter = "全部"
        self._st_trends = list(PRESET_TRENDS)
        self._refresh_trends()

    # ───── 筛选栏 ─────
    def _build_filter_bar(self, parent: ctk.CTkFrame):
        bar = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8, height=48)
        bar.pack(fill="x", padx=16, pady=(8, 8))

        ctk.CTkLabel(
            bar, text="平台筛选", font=("Microsoft YaHei", 12, "bold"), text_color=FG_TEXT,
        ).pack(side="left", padx=(16, 12))

        self._st_filter_var = ctk.StringVar(value="全部")
        for pf in PLATFORMS:
            ctk.CTkRadioButton(
                bar, text=pf, variable=self._st_filter_var, value=pf,
                font=("Microsoft YaHei", 11), text_color=FG_TEXT,
                fg_color=ACCENT, hover_color=ACCENT_LIGHT, border_color=BORDER,
                command=self._on_filter_change,
            ).pack(side="left", padx=6)

        ctk.CTkButton(
            bar, text="刷新热点", width=90, height=30,
            font=("Microsoft YaHei", 11), fg_color=ACCENT, hover_color=ACCENT_LIGHT,
            command=self._refresh_trends,
        ).pack(side="right", padx=16)

    def _on_filter_change(self):
        self._st_current_filter = self._st_filter_var.get()
        self._refresh_trends()

    # ───── 爬取真实数据 ─────
    def _fetch_real_trends(self):
        """后台爬取B站二游数据（主数据源）"""
        self._st_status_lbl.configure(text="🔄 正在爬取B站二游数据...", text_color=WARNING)

        def do_fetch():
            real_data = []
            # B站（主数据源）
            try:
                from data.scrapers.bilibili import fetch_all as bili_fetch
                bili = bili_fetch()
                real_data.extend(bili)
            except Exception:
                pass
            # 回到主线程
            self.after(0, lambda: self._on_fetch_done(real_data))

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_fetch_done(self, real_data):
        """爬取完成回调"""
        if real_data:
            # 合并真实数据 + 预设数据（去重）
            seen = set()
            merged = []
            for item in real_data:
                key = item["keyword"]
                if key not in seen:
                    seen.add(key)
                    merged.append(item)
            # 补充预设数据（小红书）
            for item in PRESET_TRENDS:
                if item["platform"] == "小红书" and item["keyword"] not in seen:
                    seen.add(item["keyword"])
                    merged.append(item)
            self._st_trends = merged
            bili_count = len(real_data)
            self._st_status_lbl.configure(
                text=f"✅ B站二游: {bili_count}条 | 小红书: 预设数据",
                text_color=SUCCESS)
        else:
            self._st_status_lbl.configure(text="⚠️ 爬取失败，使用预设数据", text_color=WARNING)
        self._refresh_trends()

    # ───── 刷新热点 ─────
    def _refresh_trends(self):
        """刷新热点数据（模拟数据+随机波动）。"""
        for widget in self._trend_grid_frame.winfo_children():
            widget.destroy()

        filt = self._st_current_filter
        trends = []
        for t in self._st_trends:
            if filt != "全部" and t["platform"] != filt:
                continue
            # 加入随机波动模拟实时变化
            t_display = dict(t)
            t_display["heat"] = max(1, min(100, t["heat"] + random.randint(-3, 3)))
            trends.append(t_display)

        # 按热度排序
        trends.sort(key=lambda x: x["heat"], reverse=True)

        if not trends:
            ctk.CTkLabel(
                self._trend_grid_frame, text="暂无热点数据",
                font=("Microsoft YaHei", 14), text_color=FG_DIM,
            ).pack(pady=60)
            return

        # 关键词标签云（2行区域）
        cloud_frame = ctk.CTkFrame(self._trend_grid_frame, fg_color="transparent")
        cloud_frame.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            cloud_frame, text="热门关键词",
            font=("Microsoft YaHei", 13, "bold"), text_color=FG_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        tag_cloud = ctk.CTkFrame(cloud_frame, fg_color="transparent")
        tag_cloud.pack(fill="x")
        for t in trends[:16]:
            color = _heat_color(t["heat"])
            font_size = max(11, min(16, 11 + (t["heat"] - 60) // 8))
            lbl = ctk.CTkLabel(
                tag_cloud, text=f" {t['keyword']} ",
                font=("Microsoft YaHei", font_size, "bold"),
                text_color="#ffffff", fg_color=color,
                corner_radius=4,
            )
            lbl.pack(side="left", padx=3, pady=3)

        # 热点卡片网格
        grid_wrap = ctk.CTkFrame(self._trend_grid_frame, fg_color="transparent")
        grid_wrap.pack(fill="x", padx=12, pady=(8, 12))
        cols = 3
        for i, t in enumerate(trends):
            row, col = divmod(i, cols)
            self._create_trend_card(grid_wrap, t, row, col)

        # 配置网格权重
        for c in range(cols):
            grid_wrap.grid_columnconfigure(c, weight=1)

        self._toast(f"已刷新 {len(trends)} 条热点")

    def _create_trend_card(self, parent, trend: dict, row: int, col: int):
        """创建单个热点卡片。"""
        color = _heat_color(trend["heat"])
        card = ctk.CTkFrame(parent, fg_color=BG_INPUT, corner_radius=8, border_width=1, border_color=color)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        # 顶部：平台 + 热度
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            top, text=trend["platform"],
            font=("Microsoft YaHei", 10), text_color=FG_DIM,
            fg_color=BORDER, corner_radius=3,
        ).pack(side="left")
        ctk.CTkLabel(
            top, text=f"热度 {trend['heat']}",
            font=("Microsoft YaHei", 10, "bold"), text_color=color,
        ).pack(side="right")

        # 关键词
        ctk.CTkLabel(
            card, text=trend["keyword"],
            font=("Microsoft YaHei", 14, "bold"), text_color=FG_TEXT,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(4, 2))

        # 描述
        ctk.CTkLabel(
            card, text=trend.get("desc", ""),
            font=("Microsoft YaHei", 10), text_color=FG_DIM,
            anchor="w", wraplength=200,
        ).pack(fill="x", padx=10, pady=(0, 10))

        # 热度条
        bar = ctk.CTkProgressBar(card, height=3, fg_color=BG_DARK, progress_color=color)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        bar.set(trend["heat"] / 100.0)

    # ───── AI 分析面板 ─────
    def _build_analysis_panel(self, parent: ctk.CTkFrame):
        panel = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10)
        panel.grid(row=1, column=0, sticky="nsew")

        bar = ctk.CTkFrame(panel, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            bar, text="AI 趋势分析与内容推荐",
            font=("Microsoft YaHei", 13, "bold"), text_color=ACCENT_LIGHT,
        ).pack(side="left")
        self._st_analyze_btn = ctk.CTkButton(
            bar, text="AI 分析", width=80, height=28,
            font=("Microsoft YaHei", 11), fg_color=ACCENT, hover_color=ACCENT_LIGHT,
            command=self._analyze_trend,
        )
        self._st_analyze_btn.pack(side="right")

        self._st_analyze_text = ctk.CTkTextbox(
            panel, fg_color=BG_DARK, text_color=FG_TEXT,
            font=("Microsoft YaHei", 12), border_color=BORDER, border_width=1,
            corner_radius=6, wrap="word", state="disabled",
        )
        self._st_analyze_text.pack(fill="both", expand=True, padx=16, pady=(4, 16))

    # ───── AI 趋势分析 ─────
    def _analyze_trend(self):
        """调用 AI 分析当前热点并推荐内容方向。"""
        filt = self._st_current_filter
        trends_for_prompt = []
        for t in self._st_trends:
            if filt != "全部" and t["platform"] != filt:
                continue
            trends_for_prompt.append(t)
        trends_for_prompt.sort(key=lambda x: x["heat"], reverse=True)
        top_trends = trends_for_prompt[:10]

        if not top_trends:
            self._toast("没有可分析的热点数据")
            return

        self._st_analyze_btn.configure(state="disabled", text="分析中...")

        trend_text = "\n".join(
            f"- [{t['platform']}] {t['keyword']}（热度{t['heat']}）: {t['desc']}"
            for t in top_trends
        )

        system = (
            "你是米哈游/米游社资深运营策略专家。"
            "请根据当前社媒热点数据，给出内容运营建议。"
            "回答要有条理，分点说明，给出可执行的内容方向。"
        )
        user = (
            f"以下是当前{'某平台' if filt != '全部' else '各平台'}的游戏相关热点：\n\n"
            f"{trend_text}\n\n"
            "请从以下角度分析：\n"
            "1. 当前热点总结（2-3句话概括）\n"
            "2. 内容方向推荐（3-5个可执行的内容主题）\n"
            "3. 各平台差异化策略（针对不同平台给出不同建议）\n"
            "4. 风险提示（需要注意的内容风险）\n"
        )

        def _worker():
            result = _call_openai_trend_sync(system, user)
            self.after(0, lambda: self._on_analyze_done(result))

        threading.Thread(target=_worker, daemon=True).start()
        self._save_log("社媒趋势分析", f"平台={filt} 热点数={len(top_trends)}")

    def _on_analyze_done(self, result: str):
        self._st_analyze_btn.configure(state="normal", text="AI 分析")
        self._st_analyze_text.configure(state="normal")
        self._st_analyze_text.delete("1.0", "end")
        self._st_analyze_text.insert("1.0", result)
        self._st_analyze_text.configure(state="disabled")
        self._toast("AI 趋势分析完成")
