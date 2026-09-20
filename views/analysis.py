"""
分析页 —— AI 顾问 / 版本健康度 / 版本对比
==========================================

为什么把这三块放在一起：
  它们都是「对着已有数据做判断」，输入是同一批指标，输出的都是结论。
  旧版把 AI 顾问单独放一页，健康度和版本对比又散在别处，
  用户要分析一个问题得在三个页面之间跳 —— 这就是「功能板块模糊」。

修掉的旧 bug：
  · `timeout=10` 太短，长回答必被截断 → 改为可配置，默认 45s
  · 7 个场景的 prompt 与 fallback 各自维护、容易不同步 → 收进一张表
  · AI 结果只存在内存里，切页就丢（依赖主流程的 _ai_saved_content）→ 落库
  · 健康度分析的 SQL 用 `except:` 裸捕获，失败后显示"未知"却看不出原因 → 收窄异常
"""

import threading
from datetime import datetime, timedelta

import customtkinter as ctk

import theme
from theme import (
    BG_APP, BG_CARD, BG_ELEVATED, BG_BORDER, BG_CONTENT,
    PRIMARY, PRIMARY_DIM, PRIMARY_HOVER, DANGER, SUCCESS, WARNING, INFO, AI, AI_HOVER,
    NEUTRAL,
    TEXT_PRIMARY, TEXT_BODY, TEXT_SECONDARY, TEXT_TERTIARY,
    font, num_font, SIZE_H1, SIZE_H2, SIZE_H3, SIZE_BODY, SIZE_SMALL, SIZE_TINY,
    SP_XS, SP_SM, SP_MD, SP_LG, SP_XL, RADIUS_MD, RADIUS_LG,
)
import icons
import components as C
import charts
import db
from db import (
    GAMES, query, execute, get_conn, load_config, save_config,
    get_versions, get_version_by_id, metrics_between, task_progress,
    open_risks, budget_summary, top_characters, community_summary,
    previous_version, version_series,
    date_str, days_ago, parse_date, latest_version, safe_float,
    retention_series, retention_stats, valid_retention,
)

# ═══════════════════════════════════════════════════════════
#  场景表：一处定义 prompt 与兜底内容，避免两边不同步
# ═══════════════════════════════════════════════════════════
SCENES = {
    "活动方案建议": {
        "icon": "rocket",
        "prompt": ("你是一位资深的游戏运营专家。请为{game}设计一个为期 14 天的社区运营活动方案，"
                   "目标是提升社区活跃度和用户参与度。请包含：活动主题、玩法机制、"
                   "奖励设计、推广节奏（分日排期）、以及可量化的成功指标。"),
        "fallback": ("【离线建议】活动策划方向\n"
                     "1. 限时签到福利：7 天连续签到送抽卡资源，第 7 天给一次十连\n"
                     "2. 社区二创激励：UGC 征集 + 投票 + 阶梯奖励，重点扶持中腰部创作者\n"
                     "3. 版本主题 H5：剧情问答 + 分享裂变，降低参与门槛\n\n"
                     "排期建议：预热 3 天 → 爆发 5 天 → 长尾 6 天\n"
                     "成功指标：参与率 ≥ 25%、UGC 投稿量环比 +30%、社区互动率回升至 4% 以上"),
    },
    "内容选题策划": {
        "icon": "bulb",
        "prompt": ("你是一位游戏社区内容运营专家。请为{game}的官方社区策划本周 5 个内容选题，"
                   "覆盖攻略、同人、讨论、资讯等方向。每个选题请给出：标题、形式、"
                   "目标人群、预期效果。"),
        "fallback": ("【离线建议】本周选题方向\n"
                     "1. 新角色攻略与配队推荐（攻略 · 强度党）\n"
                     "2. 版本剧情深度解读（图文 · 剧情党）\n"
                     "3. 社区热门同人作品精选（合集 · 泛用户）\n"
                     "4. 游戏冷知识 / 技巧合集（短片 · 新手）\n"
                     "5. 玩家投稿话题征集（互动 · 全量用户）"),
    },
    "文案优化": {
        "icon": "edit",
        "prompt": ("请优化以下运营文案，使其更具吸引力和转化率。"
                   "保留核心信息，输出 2 个版本（简洁版 / 情绪版），并说明改动理由。\n\n"
                   "原文案：\n{input}"),
        "fallback": ("【离线建议】文案优化方向\n"
                     "1. 前 12 个字必须出现核心卖点（角色名 / 奖励 / 时限）\n"
                     "2. 用具体数字替代形容词：\"丰厚奖励\" → \"十连抽 ×2\"\n"
                     "3. 情绪落点放在结尾，制造行动理由\n"
                     "4. 避免复杂修辞，移动端一行不超过 18 字"),
        "needs_input": True,
    },
    "数据分析解读": {
        "icon": "chart",
        "prompt": ("作为游戏运营数据分析师，请解读以下数据并给出行动建议。"
                   "请按「现象 → 归因 → 建议」三段式输出，不要罗列数字。\n\n数据：\n{input}"),
        "fallback": ("【离线建议】数据解读框架\n"
                     "1. 先看整体：DAU 与互动率的环比方向是否一致\n"
                     "2. 再看结构：分平台 / 分角色拆解，找到拖累项\n"
                     "3. 最后归因：区分「版本内容问题」与「投放节奏问题」\n"
                     "4. 给建议时标注优先级与预期效果"),
        "needs_input": True,
    },
    "舆情应对策略": {
        "icon": "shield",
        "prompt": ("你是一位游戏社区危机公关专家。{game}社区出现负面反馈，"
                   "请给出应对策略，包含：风险分级判断、对外口径、"
                   "客服话术要点、需要同步的内部动作、以及不建议做的事。"),
        "fallback": ("【离线建议】舆情应对原则\n"
                     "1. 第一时间确认事实，不猜测、不回避\n"
                     "2. 区分诉求合理性与影响范围，分级响应\n"
                     "3. 统一对外口径，同步客服话术\n"
                     "4. 合理诉求快速响应与补偿，不合理诉求清晰解释立场\n"
                     "5. 避免：删帖压热度、官方与玩家对线、无期限拖延"),
    },
    "版本复盘框架": {
        "icon": "compare",
        "prompt": ("请列出{game}一次完整版本更新的复盘框架，"
                   "包含指标定义、对比维度、结论模板。"
                   "要能直接套用，不要泛泛而谈。"),
        "fallback": ("【离线建议】版本复盘框架\n"
                     "一、数据维度：DAU 趋势、付费率、新增 / 回流、留存曲线\n"
                     "二、内容维度：主线完成率、活动参与率、角色抽取率\n"
                     "三、社区维度：正负向话题量、UGC 产出量、KOL 传播量\n"
                     "四、竞品维度：同期竞品版本表现对比\n"
                     "结论模板：做对了什么 / 做错了什么 / 下版本改什么（各不超过 3 条）"),
    },
    "版本健康度分析": {
        "icon": "eye",
        "prompt": None,   # 动态构建，见 _build_health_prompt
        "fallback": ("【离线建议】基于当前数据\n"
                     "1. 对比上版本使用率变化幅度 TOP5 角色，锁定异动项\n"
                     "2. 排查骤降角色是否存在数值或机制问题\n"
                     "3. 关注社区高回复帖中的核心诉求\n"
                     "4. 检查互动率是否低于健康线（3%）"),
    },
}


class AnalysisMixin:
    """由 App 混入，提供分析页。"""

    def show_analysis(self):
        self.clear_main()
        if getattr(self, "_analysis_tab", None) not in (
                "health", "ai", "compare", "retention"):
            self._analysis_tab = "health"
        self._build_analysis()

    # ═══════════════════════════════════════════════════════
    def _build_analysis(self):
        # Tab 状态兜底
        if getattr(self, "_analysis_tab", None) not in (
                "health", "ai", "compare", "retention"):
            self._analysis_tab = "health"

        body, _page = self.page_scaffold(
            "analysis", "分析",
            "基于已有数据做判断：健康度体检、AI 顾问、版本对比、留存分析",
            icon="bulb", refresh=self._build_analysis)

        tabbar = ctk.CTkFrame(body, fg_color="transparent", height=1)
        tabbar.pack(fill="x", pady=(0, SP_MD))

        TABS = [("health", "版本健康度", "eye"),
                ("ai", "AI 顾问", "bolt"),
                ("compare", "版本对比", "compare"),
                ("retention", "留存分析", "trend")]

        for key, text, icon in TABS:
            active = (key == self._analysis_tab)
            btn = ctk.CTkButton(
                tabbar, text=("  " + text),
                command=lambda k=key: self._switch_analysis(k),
                fg_color=PRIMARY_DIM if active else "transparent",
                hover_color=BG_ELEVATED,
                text_color=TEXT_PRIMARY if active else TEXT_SECONDARY,
                font=font(SIZE_BODY), corner_radius=RADIUS_MD,
                height=32, width=112, border_width=1,
                border_color=PRIMARY if active else BG_BORDER)
            btn.pack(side="left", padx=(0, SP_SM))

        if self._analysis_tab == "health":
            self._build_health(body)
        elif self._analysis_tab == "ai":
            self._build_ai(body)
        elif self._analysis_tab == "retention":
            self._build_retention(body)
        else:
            self._build_compare(body)

    def _switch_analysis(self, key):
        self._analysis_tab = key
        self.remount("analysis")

    # ═══════════════════════════════════════════════════════
    #  Tab 1 · 版本健康度
    # ═══════════════════════════════════════════════════════
    def _build_health(self, parent):
        versions = get_versions(limit=12)
        if not versions:
            card = C.Card(parent)
            card.pack(fill="x")
            C.EmptyState(card.body, "还没有版本可以体检", "calendar",
                         "先创建版本并录入数据",
                         "去创建版本",
                         lambda: self.show_view("versions")).pack(fill="x")
            return

        # 版本选择器
        sel = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        sel.pack(fill="x", pady=(0, SP_MD))
        opts = [f"{v['game']} {v['version']}" for v in versions]
        self._health_versions = versions
        self._health_sel = C.Field(sel, "体检对象", kind="menu", values=opts,
                                   width=190, label_width=64, default=opts[0])
        self._health_sel.pack(side="left")
        self._health_sel.widget.configure(
            command=lambda _v: self._refresh_health())

        C.PrimaryButton(sel, "生成体检报告", self._analyze_current_version,
                        icon="bolt", width=136, height=30).pack(side="right")

        self._health_host = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        self._health_host.pack(fill="x")

        self._refresh_health()

    def _current_health_version(self):
        """解析当前选中的版本行。用索引取，不用 label 反查 —— 旧版正是在这里埋了坑。"""
        label = self._health_sel.get()
        for v in self._health_versions:
            if f"{v['game']} {v['version']}" == label:
                return v
        return self._health_versions[0] if self._health_versions else None

    def _refresh_health(self):
        host = self._health_host
        for w in host.winfo_children():
            w.destroy()

        v = self._current_health_version()
        if not v:
            return

        scores = self._health_scores(v)

        # ── 总分卡 + 四维评分 ──
        top = ctk.CTkFrame(host, fg_color="transparent", height=1)
        top.pack(fill="x", pady=(0, SP_MD))
        top.grid_columnconfigure(0, weight=0)
        for i in range(1, 5):
            top.grid_columnconfigure(i, weight=1, uniform="hs")

        total, grade, grade_color = self._overall_score(scores)
        big = C.Card(top, accent=grade_color if grade in ("偏弱", "预警") else None)
        big.grid(row=0, column=0, sticky="nsew", padx=(0, SP_SM))
        binner = ctk.CTkFrame(big.body, fg_color="transparent", height=1)
        binner.pack(fill="both", expand=True, padx=SP_LG, pady=SP_MD)
        ctk.CTkLabel(binner, text="综合健康度", font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(binner, text=str(total), font=num_font(34),
                     text_color=grade_color, anchor="w").pack(anchor="w")
        C.Badge(binner, grade, grade_color).pack(anchor="w", pady=(SP_XS, 0))

        for i, (name, score, color, desc) in enumerate(scores, start=1):
            cell = ctk.CTkFrame(top, fg_color=BG_CARD, corner_radius=RADIUS_MD,
                                border_width=1,
                                border_color=color if score < 60 else BG_BORDER)
            cell.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 1 else SP_SM, 0))
            inner = ctk.CTkFrame(cell, fg_color="transparent", height=1)
            inner.pack(fill="both", expand=True, padx=SP_MD, pady=SP_MD)

            ctk.CTkLabel(inner, text=name, font=font(SIZE_TINY),
                         text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w")
            ctk.CTkLabel(inner, text=f"{score}", font=num_font(22),
                         text_color=color, anchor="w").pack(anchor="w")
            bar = charts.ProgressBar(inner, height=4, color=color)
            bar.pack(fill="x", pady=(3, SP_XS))
            bar.after(40, lambda b=bar, s=score: b.set(s) if b.winfo_exists() else None)
            ctk.CTkLabel(inner, text=desc, font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY, anchor="w",
                         wraplength=140, justify="left").pack(anchor="w")

        # ── 结论区 ──
        self._build_health_findings(host, v, scores)

    def _health_scores(self, v):
        """
        四维体检。每个维度给 0~100 分 + 一句人话说明。
        评分逻辑刻意做成可解释的规则，而不是黑盒 —— 面试时能讲清每一分怎么来的。
        """
        # 1. 用户规模：DAU 环比
        rows = metrics_between(date_str(days_ago(30)), date_str(), v["game"])
        if len(rows) >= 4:
            mid = len(rows) // 2
            prev = [r["dau"] for r in rows[:mid] if r["dau"]]
            cur = [r["dau"] for r in rows[mid:] if r["dau"]]
            p = sum(prev) / len(prev) if prev else 0
            c = sum(cur) / len(cur) if cur else 0
            dau_pct = (c - p) / p * 100 if p else 0
            scale = max(0, min(100, 60 + dau_pct * 2))
            scale_desc = f"DAU 环比 {dau_pct:+.1f}%"
        else:
            scale, scale_desc = 50, "数据不足 30 天"

        # 2. 社区活力：互动率
        rates = [r["interaction_rate"] for r in rows if r["interaction_rate"]]
        if rates:
            avg_rate = sum(rates) / len(rates)
            # 4% 为健康线，2% 为警戒线
            activity = max(0, min(100, (avg_rate - 2) / 2 * 100))
            activity_desc = f"平均互动率 {avg_rate:.1f}%（健康线 4%）"
        else:
            avg_rate, activity, activity_desc = 0, 30, "无互动率数据"

        # 3. 执行效率：任务完成度
        total_t, done_t = task_progress(v["id"])
        if total_t:
            exec_score = int(done_t / total_t * 100)
            exec_desc = f"任务 {done_t}/{total_t} 完成"
        else:
            exec_score, exec_desc = 40, "未导入任务清单"

        # 4. 风险控制：高概率风险越少分越高
        risks = open_risks(v["id"])
        high = len([r for r in risks if r["probability"] == "high"])
        med = len([r for r in risks if r["probability"] == "medium"])
        risk_score = max(0, 100 - high * 25 - med * 10)
        risk_desc = (f"{len(risks)} 项风险" +
                     (f"，{high} 项高概率" if high else "，无高概率项")
                     if risks else "暂无风险记录")

        def color_of(s):
            return SUCCESS if s >= 75 else (WARNING if s >= 55 else DANGER)

        return [
            ("用户规模", int(scale), color_of(scale), scale_desc),
            ("社区活力", int(activity), color_of(activity), activity_desc),
            ("执行效率", int(exec_score), color_of(exec_score), exec_desc),
            ("风险控制", int(risk_score), color_of(risk_score), risk_desc),
        ]

    @staticmethod
    def _overall_score(scores):
        total = int(sum(s for _, s, _, _ in scores) / len(scores))
        if total >= 80:
            return total, "健康", SUCCESS
        if total >= 65:
            return total, "正常", INFO
        if total >= 50:
            return total, "偏弱", WARNING
        return total, "预警", DANGER

    def _build_health_findings(self, host, v, scores):
        """把评分翻译成「要做什么」，而不是只给分数。"""
        card = C.Card(host)
        # fill="x" 而非 "both"/expand：结论条数不固定（2~6 条），
        # 一旦父容器给额外高度，卡片被拉长后左侧色条会拖到整卡高度，
        # 而文字只占上半部分 —— 截图里那条长得离谱的竖线就是这个。
        card.pack(fill="x")

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "体检结论与建议", icon="bulb",
                       icon_color=AI).pack(side="left")

        findings = []

        for name, score, _color, desc in scores:
            if score < 55:
                findings.append((DANGER, "warn", f"{name}偏弱：{desc}",
                                 self._advice_for(name)))
            elif score < 75:
                findings.append((WARNING, "clock", f"{name}需关注：{desc}",
                                 self._advice_for(name)))

        # 角色使用率异动单独查一遍，这是运营最关心的信号
        prev_row = previous_version(v)
        if prev_row:
            prev_ver = prev_row["version"]
            drops = query(
                "SELECT c.character_name, c.usage_rate AS cur, "
                "p.usage_rate AS prev FROM char_usage c "
                "JOIN char_usage p ON c.character_name=p.character_name "
                "WHERE c.version=? AND p.version=? "
                "ORDER BY (p.usage_rate - c.usage_rate) DESC LIMIT 3",
                (v["version"], prev_ver))
            big = [d for d in drops
                   if (d["prev"] or 0) - (d["cur"] or 0) >= 3.0]
            if big:
                names = "、".join(
                    f"{d['character_name']}({(d['prev'] or 0) - (d['cur'] or 0):.1f}pp)"
                    for d in big)
                findings.append((DANGER, "down",
                                 f"角色使用率异动：{names}",
                                 "优先排查是否存在数值、机制或配队环境变化，"
                                 "必要时安排数值评估与替代角色推广。"))

        p_post, p_reply = community_summary(v["version"])
        if p_post:
            findings.append((INFO, "bolt",
                             f"社区热度：累计发帖 {int(p_post):,}，"
                             f"平均回复 {p_reply:.1f}",
                             "回复数低于 8 说明话题讨论深度不足，"
                             "建议加强引导性提问与 UGC 征集。"))

        if not findings:
            C.EmptyState(card.body, "各项指标都在健康区间", "check",
                         "保持当前节奏即可，记得持续录入数据",
                         height=110).pack(fill="x")
            return

        for color, icon, title, advice in findings:
            row = C.Row(card.body)
            row.pack(fill="x", padx=SP_LG, pady=(0, SP_SM))
            if row.bar is not None:
                row.bar.configure(fg_color=color)

            trow = ctk.CTkFrame(row.text, fg_color="transparent", height=1)
            trow.pack(fill="x")
            icons.draw_icon(trow, icon, 12, color).pack(side="left", pady=2)
            ctk.CTkLabel(trow, text=title, font=font(SIZE_SMALL, bold=True),
                         text_color=TEXT_PRIMARY, anchor="w").pack(
                side="left", padx=(5, 0))
            ctk.CTkLabel(row.text, text=advice, font=font(SIZE_TINY),
                         text_color=TEXT_SECONDARY, anchor="w",
                         wraplength=620, justify="left").pack(anchor="w",
                                                              pady=(2, 0))

        ctk.CTkFrame(card.body, fg_color="transparent", height=SP_SM).pack()

    @staticmethod
    def _advice_for(dim):
        return {
            "用户规模": "检查买量与回流活动的投放节奏；如果 DAU 在版本中期下滑，"
                        "通常是内容消耗速度超过更新速度，需要补充中段活动。",
            "社区活力": "互动率是内容吸引力的直接反映。优先做话题引导型活动，"
                        "并检查近期内容的标题是否过于同质化。",
            "执行效率": "任务积压会直接推迟上线动作。先清「版本复盘」以外的逾期项，"
                        "复盘类任务可放到版本结束后统一处理。",
            "风险控制": "高概率风险需要指定负责人和截止时间，"
                        "否则复盘时只能写「已关注」这类无效结论。",
        }.get(dim, "建议安排专项复盘。")

    def _analyze_current_version(self):
        """健康度体检 + 可选调用 AI 深化分析。"""
        v = self._current_health_version()
        if not v:
            self.toast("请先选择要体检的版本", WARNING)
            return
        self._analysis_tab = "ai"
        self.remount("analysis")
        self.after(120, lambda: self._generate_ai(scene="版本健康度分析",
                                                  version=v))

    # ═══════════════════════════════════════════════════════
    #  Tab 2 · AI 顾问
    # ═══════════════════════════════════════════════════════
    def _build_ai(self, parent):
        # ── 配置卡 ──
        cfg = C.Card(parent)
        cfg.pack(fill="x", pady=(0, SP_MD))

        head = ctk.CTkFrame(cfg.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "模型配置", icon="settings").pack(side="left")

        saved_key = load_config("ai_api_key")
        self._ai_status = ctk.CTkLabel(
            head, text="已保存配置" if saved_key else "未配置",
            font=font(SIZE_TINY),
            text_color=SUCCESS if saved_key else TEXT_TERTIARY)
        self._ai_status.pack(side="right")

        row = ctk.CTkFrame(cfg.body, fg_color="transparent", height=1)
        row.pack(fill="x", padx=SP_LG, pady=(0, SP_SM))

        self.ai_key = C.Field(row, "API Key", placeholder="sk-...", width=250,
                              label_width=64)
        self.ai_key.pack(side="left", padx=(0, SP_MD))
        self.ai_key.widget.configure(show="*")
        if saved_key:
            self.ai_key.set(saved_key)

        key_toggle = C.IconButton(row, "eye", self._toggle_key_visibility,
                                  size=26)
        key_toggle.pack(side="left", padx=(0, SP_MD))

        self.ai_model = C.Field(
            row, "模型", kind="menu",
            values=["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro",
                    "gpt-4o-mini", "gpt-4o"],
            width=154, label_width=40,
            default=load_config("ai_model", "deepseek-chat"))
        self.ai_model.pack(side="left")

        row2 = ctk.CTkFrame(cfg.body, fg_color="transparent", height=1)
        row2.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))

        self.ai_base = C.Field(
            row2, "Base URL", width=250, label_width=64,
            default=load_config("ai_base_url", "https://api.deepseek.com"))
        self.ai_base.pack(side="left", padx=(0, SP_MD))

        C.GhostButton(row2, "保存配置", lambda: self._save_ai_config(True),
                      icon="save", width=100, height=30).pack(side="left")

        ctk.CTkLabel(row2, text="未配置时使用内置离线建议，页面功能不中断",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="left", padx=(SP_MD, 0))

        # ── 场景卡 ──
        scene_card = C.Card(parent)
        scene_card.pack(fill="x", pady=(0, SP_MD))

        srow = ctk.CTkFrame(scene_card.body, fg_color="transparent", height=1)
        srow.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(srow, "选择场景", icon="list").pack(side="left")

        self._scene_var = ctk.StringVar(value="版本健康度分析")
        menu = ctk.CTkOptionMenu(
            srow, variable=self._scene_var, values=list(SCENES.keys()),
            width=154, fg_color=BG_ELEVATED, button_color=BG_BORDER,
            button_hover_color=BG_BORDER, text_color=TEXT_BODY,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_BODY,
            dropdown_hover_color=BG_ELEVATED, font=font(SIZE_BODY),
            dropdown_font=font(SIZE_BODY), command=lambda _v: self._on_scene_change())
        menu.pack(side="left", padx=(SP_MD, 0))

        self._ai_game = C.Field(srow, "游戏", kind="menu", values=GAMES,
                                width=140, label_width=40, default=GAMES[1])
        self._ai_game.pack(side="left", padx=(SP_MD, 0))

        C.PrimaryButton(srow, "生成", lambda: self._generate_ai(),
                        icon="bolt", width=90, height=30).pack(side="right")

        # 场景说明 + 可选输入
        self._scene_hint = ctk.CTkLabel(
            scene_card.body, text="", font=font(SIZE_TINY),
            text_color=TEXT_TERTIARY, anchor="w",
            wraplength=680, justify="left")
        self._scene_hint.pack(anchor="w", fill="x", padx=SP_LG)

        self._ai_input_host = ctk.CTkFrame(scene_card.body, fg_color="transparent", height=1)
        self._ai_input_host.pack(fill="x", padx=SP_LG, pady=(SP_SM, SP_MD))

        self._ai_input = None
        self._on_scene_change()

        # ── 结果卡 ──
        out = C.Card(parent, accent=AI)
        out.pack(fill="both", expand=True)

        ohead = ctk.CTkFrame(out.body, fg_color="transparent", height=1)
        ohead.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(ohead, "分析结果", icon="doc",
                       icon_color=AI).pack(side="left")

        self._ai_buttons = []
        for text, icon, cmd, color in (
                ("保存为报告", "save", self._save_ai_result, AI),
                ("复制", "copy", self._copy_ai_result, None),
                ("清空", "trash", self._clear_ai_result, None)):
            btn = (C.PrimaryButton if color else C.GhostButton)(
                ohead, text, cmd, icon=icon, width=104, height=28,
                **({"accent": color, "hover": AI_HOVER} if color else {}))
            btn.pack(side="right", padx=(SP_XS, 0))
            self._ai_buttons.append(btn)

        self.ai_result = ctk.CTkTextbox(
            out.body, fg_color=BG_APP, text_color=TEXT_BODY,
            font=font(SIZE_BODY), wrap="word", border_width=1,
            border_color=BG_BORDER, corner_radius=RADIUS_MD)
        self.ai_result.pack(fill="both", expand=True, padx=SP_LG,
                            pady=(0, SP_MD))

        # 恢复上次内容（旧版切页就丢，因为只存在内存里）
        last = load_config("ai_last_result", "")
        if last:
            self.ai_result.insert("1.0", last)

    def _toggle_key_visibility(self):
        self._key_visible = not getattr(self, "_key_visible", False)
        try:
            self.ai_key.widget.configure(show="" if self._key_visible else "*")
        except Exception:
            pass

    def _on_scene_change(self):
        scene = self._scene_var.get()
        cfg = SCENES.get(scene, {})
        self._scene_hint.configure(
            text=f"提示：{cfg.get('prompt', '').splitlines()[0][:88]}"
            if cfg.get("prompt") else "将读取当前版本的真实数据，生成结构化体检结论")

        # 仅「文案优化」「数据分析解读」需要粘贴原文
        for w in self._ai_input_host.winfo_children():
            w.destroy()

        if cfg.get("needs_input"):
            ctk.CTkLabel(self._ai_input_host,
                         text="请粘贴需要处理的内容：",
                         font=font(SIZE_TINY), text_color=TEXT_SECONDARY,
                         anchor="w").pack(anchor="w", pady=(0, SP_XS))
            self._ai_input = ctk.CTkTextbox(
                self._ai_input_host, height=76, fg_color=BG_APP,
                text_color=TEXT_BODY, font=font(SIZE_BODY), wrap="word",
                border_width=1, border_color=BG_BORDER,
                corner_radius=RADIUS_MD)
            self._ai_input.pack(fill="x")
        else:
            self._ai_input = None

    def _save_ai_config(self, notify=False):
        save_config("ai_api_key", self.ai_key.get().strip())
        save_config("ai_base_url", self.ai_base.get().strip())
        save_config("ai_model", self.ai_model.get())
        if notify:
            self._ai_status.configure(text="已保存配置", text_color=SUCCESS)
            self.toast("配置已保存")

    def _current_scene_input(self):
        if self._ai_input is None:
            return ""
        try:
            return self._ai_input.get("1.0", "end").strip()
        except Exception:
            return ""

    def _generate_ai(self, scene=None, version=None):
        scene = scene or self._scene_var.get()
        token = self.ai_key.get().strip()
        base = self.ai_base.get().strip() or "https://api.deepseek.com"
        model = self.ai_model.get()
        game = self._ai_game.get()

        cfg = SCENES.get(scene, {})
        text_input = self._current_scene_input()

        if cfg.get("needs_input") and not text_input:
            self.toast("该场景需要先粘贴内容", WARNING)
            return

        # 组装 prompt
        if scene == "版本健康度分析":
            v = version or latest_version()
            prompt = self._build_health_prompt(v)
        else:
            prompt = (cfg.get("prompt") or "").format(game=game,
                                                      input=text_input)

        self._save_ai_config()

        try:
            self.ai_result.delete("1.0", "end")
            self.ai_result.insert("1.0", "正在生成，请稍候...\n")
        except Exception:
            pass

        for b in self._ai_buttons:
            try:
                b.configure(state="disabled")
            except Exception:
                pass
        self._ai_status.configure(text="生成中…", text_color=WARNING)

        def worker():
            result = None
            error = None
            if token:
                try:
                    from openai import OpenAI
                    # 旧版 timeout=10 太短，长回答会被截断；这里放宽到 45s
                    client = OpenAI(api_key=token, base_url=base, timeout=45)
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7)
                    result = resp.choices[0].message.content
                except Exception as e:
                    error = str(e)[:120]

            if not result:
                result = cfg.get("fallback", "暂无建议。")
                if error:
                    result += f"\n\n———\n（API 调用失败，以上为离线建议。原因：{error}）"
                elif not token:
                    result += "\n\n———\n（未配置 API Key，以上为离线建议。填入 Key 后可获得针对你数据的分析。）"

            self.after(0, lambda: self._on_ai_done(result, error))

        threading.Thread(target=worker, daemon=True).start()
    def _on_ai_done(self, result, error=None):
        try:
            self.ai_result.delete("1.0", "end")
            self.ai_result.insert("1.0", result)
        except Exception:
            return
        for b in self._ai_buttons:
            try:
                b.configure(state="normal")
            except Exception:
                pass

        if error:
            self._ai_status.configure(text="已降级为离线建议", text_color=WARNING)
        else:
            self._ai_status.configure(text="已生成", text_color=SUCCESS)
            # 落库，切页不丢
            save_config("ai_last_result", result[:20000])
        self.log("生成分析", self._scene_var.get())

    def _copy_ai_result(self):
        try:
            content = self.ai_result.get("1.0", "end").strip()
        except Exception:
            content = ""
        if not content:
            self.toast("还没有可复制的内容", WARNING)
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.toast("已复制到剪贴板")
        except Exception as e:
            self.toast(f"复制失败：{e}", DANGER)

    def _clear_ai_result(self):
        try:
            self.ai_result.delete("1.0", "end")
        except Exception:
            pass
        save_config("ai_last_result", "")
        self._ai_status.configure(text="已清空", text_color=TEXT_TERTIARY)

    def _save_ai_result(self):
        """把 AI 结果存成报告 —— 这样「分析」和「报告」两条线就接上了。"""
        try:
            content = self.ai_result.get("1.0", "end").strip()
        except Exception:
            content = ""
        if not content:
            self.toast("还没有可保存的内容", WARNING)
            return

        scene = self._scene_var.get()
        title = f"{self._ai_game.get()} · {scene}"
        try:
            execute("INSERT INTO reports (title, content, type) VALUES (?,?,?)",
                    (title, content, "AI分析"))
        except Exception as e:
            self.toast(f"保存失败：{e}", DANGER)
            return

        self.log("保存分析报告", title)
        self.toast("已保存，可在「报告」页查看")

    # ── 构建健康度 prompt（读真实数据） ──
    def _build_health_prompt(self, v):
        """
        从数据库拼出结构化 prompt。
        旧版这段用 `except:` 裸捕获，任一查询失败就整体退化成「未知」，
        用户看到的是"暂无数据"却不知道是查询炸了还是真没数据。
        这里逐段兜底并保留具体缺失项。
        """
        if not v:
            return "当前还没有创建版本，无法进行健康度分析。"

        ver = v["version"]
        game = v["game"]

        top = top_characters(ver, 5)
        top5 = "、".join(f"{r['character_name']}({r['usage_rate']:.1f}%)"
                         for r in top) if top else "暂未采集"

        posts, replies = community_summary(ver)
        heat = "活跃" if posts > 3000 else ("一般" if posts > 1000 else "偏低")

        risks = [r["title"] for r in open_risks(v["id"])]
        risk_txt = "；".join(risks) if risks else "暂无风险项"

        total_t, done_t = task_progress(v["id"])
        exec_txt = f"{done_t}/{total_t} 完成" if total_t else "未导入清单"

        rows = metrics_between(date_str(days_ago(30)), date_str(), game)
        if len(rows) >= 4:
            mid = len(rows) // 2
            def avg(rs, k):
                vals = [r[k] for r in rs if r[k] is not None]
                return sum(vals) / len(vals) if vals else 0
            dau_d = avg(rows[mid:], "dau") - avg(rows[:mid], "dau")
            rate_d = (avg(rows[mid:], "interaction_rate")
                      - avg(rows[:mid], "interaction_rate"))
            metric_txt = (f"近 30 天 DAU 环比 {dau_d:+.0f}，"
                          f"互动率环比 {rate_d:+.2f}pp")
        else:
            metric_txt = "近 30 天数据不足"

        return f"""你是一名游戏运营数据分析师，请对以下版本做健康度诊断。

游戏：{game}　版本：{ver}
版本周期：{v['start_date']} → {v['end_date'] or '进行中'}
指标趋势：{metric_txt}
角色使用率 TOP5：{top5}
社区热度：{heat}（累计发帖 {int(posts)}，平均回复 {replies:.1f}）
执行进度：{exec_txt}
已知风险：{risk_txt}

请输出：
1. 一句话总体判断（这个版本现在健康吗）
2. 最需要关注的 2 个问题，并说明判断依据（要引用上面给出的具体数据）
3. 每个问题给 2 条可执行的运营动作，注明优先级
4. 明确列出「不确定的部分」，不要编造未提供的数据

控制在 400 字以内，用条目式，不要客套话。"""

    # ═══════════════════════════════════════════════════════
    #  Tab 3 · 版本对比
    # ═══════════════════════════════════════════════════════
    def _build_compare(self, parent):
        versions = get_versions(limit=12)
        if len(versions) < 2:
            card = C.Card(parent)
            card.pack(fill="x")
            C.EmptyState(card.body, "至少需要 2 个版本才能对比", "compare",
                         "先创建更多版本并录入数据").pack(fill="x")
            return

        opts = [f"{v['game']} {v['version']}" for v in versions]
        self._cmp_versions = versions

        bar = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        bar.pack(fill="x", pady=(0, SP_MD))

        self._cmp_a = C.Field(bar, "对比基准", kind="menu", values=opts,
                              width=180, label_width=64, default=opts[1])
        self._cmp_a.pack(side="left")
        icons.draw_icon(bar, "arrow-right", 14, TEXT_TERTIARY).pack(
            side="left", padx=SP_MD, pady=6)
        self._cmp_b = C.Field(bar, "对比对象", kind="menu", values=opts,
                              width=180, label_width=64, default=opts[0])
        self._cmp_b.pack(side="left")

        for f in (self._cmp_a, self._cmp_b):
            f.widget.configure(command=lambda _v: self._refresh_compare())

        self._cmp_host = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        self._cmp_host.pack(fill="x")

        self._refresh_compare()

    def _resolve_cmp(self, field):
        """按字符串定位版本行。这里用完整匹配而非 index()，避免重复项错位。"""
        label = field.get()
        for v in self._cmp_versions:
            if f"{v['game']} {v['version']}" == label:
                return v
        return None

    def _refresh_compare(self):
        host = self._cmp_host
        for w in host.winfo_children():
            w.destroy()

        va = self._resolve_cmp(self._cmp_a)
        vb = self._resolve_cmp(self._cmp_b)
        if not va or not vb:
            return
        if va["id"] == vb["id"]:
            C.EmptyState(host, "两栏选了同一个版本", "compare",
                         "换一个版本才能看出差异").pack(fill="x")
            return

        # ── 指标对比 ──
        metrics = [
            ("DAU", lambda v: self._avg_metric(v, "dau")),
            ("日均帖子", lambda v: self._avg_metric(v, "new_posts")),
            ("评论数", lambda v: self._avg_metric(v, "comments")),
            ("平均时长(分)", lambda v: self._avg_metric(v, "avg_session")),
            ("互动率(%)", lambda v: self._avg_metric(v, "interaction_rate")),
        ]

        card = C.Card(host)
        card.pack(fill="x", pady=(0, SP_MD))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "核心指标对比", icon="chart").pack(side="left")
        ctk.CTkLabel(head, text="数值为版本周期内的日均值",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="right")

        cols = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        cols.pack(fill="x")
        ctk.CTkLabel(cols, text="指标", font=font(SIZE_TINY, bold=True),
                     text_color=TEXT_SECONDARY, width=120, anchor="w").pack(
            side="left")
        ctk.CTkLabel(cols, text=f"{va['version']}",
                     font=font(SIZE_TINY, bold=True),
                     text_color=TEXT_SECONDARY, width=100,
                     anchor="e").pack(side="left")
        ctk.CTkLabel(cols, text=f"{vb['version']}",
                     font=font(SIZE_TINY, bold=True),
                     text_color=TEXT_SECONDARY, width=100,
                     anchor="e").pack(side="left")
        ctk.CTkLabel(cols, text="变化", font=font(SIZE_TINY, bold=True),
                     text_color=TEXT_SECONDARY, width=110, anchor="e").pack(
            side="left")
        C.Divider(cols).pack(side="left", fill="y", padx=SP_SM)

        C.Divider(card.body).pack(fill="x", padx=SP_LG, pady=(3, 0))

        for name, getter in metrics:
            a = getter(va)
            b = getter(vb)
            line = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
            line.pack(fill="x", padx=SP_LG, pady=2)

            ctk.CTkLabel(line, text=name, font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, width=120,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=self._fmt_metric(a), font=font(SIZE_SMALL),
                         text_color=TEXT_PRIMARY, width=100,
                         anchor="e").pack(side="left")
            ctk.CTkLabel(line, text=self._fmt_metric(b), font=font(SIZE_SMALL),
                         text_color=TEXT_PRIMARY, width=100,
                         anchor="e").pack(side="left")

            if a and b:
                pct = (b - a) / a * 100
                # 涨红跌绿（国内看盘习惯）
                color = DANGER if pct > 0 else (SUCCESS if pct < 0 else TEXT_TERTIARY)
                cell = ctk.CTkFrame(line, fg_color="transparent", width=110,
                                    height=1)
                cell.pack(side="left")
                arrow = "up" if pct > 0 else ("down" if pct < 0 else None)
                if arrow:
                    icons.draw_icon(cell, arrow, 10, color).pack(
                        side="left", pady=3)
                ctk.CTkLabel(cell, text=f"{pct:+.1f}%", font=font(SIZE_TINY),
                             text_color=color).pack(side="left", padx=(3, 0))
            else:
                ctk.CTkLabel(line, text="—", font=font(SIZE_TINY),
                             text_color=TEXT_TERTIARY, width=110).pack(
                    side="left")

            C.Divider(card.body, height=1).pack(fill="x", padx=SP_LG)

        ctk.CTkFrame(card.body, fg_color="transparent", height=SP_SM).pack()

        # ── 执行与风险对比 ──
        grid = ctk.CTkFrame(host, fg_color="transparent", height=1)
        grid.pack(fill="x", pady=(0, SP_MD))
        grid.grid_columnconfigure(0, weight=1, uniform="cmp")
        grid.grid_columnconfigure(1, weight=1, uniform="cmp")

        self._compare_side(grid, 0, va, "版本 A")
        self._compare_side(grid, 1, vb, "版本 B")

        # ── 角色使用率变化 ──
        self._compare_characters(host, va, vb)

    def _avg_metric(self, v, key):
        """取版本周期内的日均值。窗口取版本起止与近 90 天的交集。"""
        start = parse_date(v["start_date"])
        end = parse_date(v["end_date"], start + timedelta(days=42))
        today = datetime.now()
        if end > today:
            end = today
        if start > today:
            return 0
        rows = metrics_between(date_str(start), date_str(end), v["game"])
        vals = [r[key] for r in rows if r[key] is not None]
        return sum(vals) / len(vals) if vals else 0

    @staticmethod
    def _fmt_metric(v):
        if not v:
            return "—"
        if v >= 10000:
            return f"{v/10000:.1f}万"
        if v >= 100:
            return f"{v:,.0f}"
        return f"{v:.1f}"

    def _compare_side(self, grid, col, v, tag):
        card = C.Card(grid)
        card.grid(row=0, column=col, sticky="nsew",
                  padx=(0 if col == 0 else SP_SM, 0))

        label, color = theme.VERSION_STATUS.get(v["status"], (v["status"], NEUTRAL))

        inner = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        inner.pack(fill="x", padx=SP_LG, pady=SP_MD)

        top = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        top.pack(fill="x")
        ctk.CTkLabel(top, text=f"{v['game']} {v['version']}",
                     font=font(SIZE_H3, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left")
        C.Badge(top, label, color).pack(side="right")

        total_t, done_t = task_progress(v["id"])
        pct = int(done_t / total_t * 100) if total_t else 0
        risks = open_risks(v["id"])
        high = len([r for r in risks if r["probability"] == "high"])
        planned, actual = budget_summary(v["id"])

        rows = [
            ("任务完成", f"{done_t}/{total_t} · {pct}%" if total_t else "未导入清单",
             SUCCESS if pct == 100 and total_t else TEXT_BODY),
            ("风险项", f"{len(risks)} 项" + (f"（{high} 高概率）" if high else ""),
             DANGER if high else (WARNING if risks else TEXT_BODY)),
            ("预算使用", f"{actual/10000:.0f}/{planned/10000:.0f} 万"
             if planned else "—",
             DANGER if planned and actual > planned else TEXT_BODY),
        ]
        for name, val, colr in rows:
            r = ctk.CTkFrame(inner, fg_color="transparent", height=1)
            r.pack(fill="x", pady=(SP_SM, 0))
            ctk.CTkLabel(r, text=name, font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY, width=68,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, font=font(SIZE_SMALL),
                         text_color=colr, anchor="w").pack(side="left")

        bar = charts.ProgressBar(inner, height=4,
                                 color=SUCCESS if (total_t and pct == 100) else PRIMARY)
        bar.pack(fill="x", pady=(SP_SM, 0))
        bar.after(40, lambda b=bar, p=pct: b.set(p) if b.winfo_exists() else None)

    def _compare_characters(self, host, va, vb):
        card = C.Card(host)
        card.pack(fill="x")

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "角色使用率变化", icon="star").pack(side="left")
        ctk.CTkLabel(head, text=f"{va['version']} → {vb['version']}",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="right")

        rows = query(
            "SELECT a.character_name, a.usage_rate AS a, b.usage_rate AS b "
            "FROM char_usage a JOIN char_usage b "
            "ON a.character_name = b.character_name "
            "WHERE a.version=? AND b.version=? "
            "ORDER BY (b.usage_rate - a.usage_rate) DESC",
            (va["version"], vb["version"]))

        if not rows:
            C.EmptyState(card.body, "这两个版本没有共同的角色数据", "star",
                         "需要两个版本都录入使用率才能对比").pack(fill="x")
            return

        box = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        box.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))

        for r in rows[:10]:
            a = r["a"] or 0
            b = r["b"] or 0
            d = b - a

            line = ctk.CTkFrame(box, fg_color="transparent", height=1)
            line.pack(fill="x", pady=1)

            ctk.CTkLabel(line, text=r["character_name"], font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, width=110,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=f"{a:.1f}%", font=font(SIZE_SMALL),
                         text_color=TEXT_SECONDARY, width=56,
                         anchor="e").pack(side="left")
            icons.draw_icon(line, "arrow-right", 11, TEXT_TERTIARY).pack(
                side="left", padx=SP_XS, pady=4)
            ctk.CTkLabel(line, text=f"{b:.1f}%", font=font(SIZE_SMALL),
                         text_color=TEXT_PRIMARY, width=56,
                         anchor="e").pack(side="left")

            color = DANGER if d > 0 else (SUCCESS if d < 0 else TEXT_TERTIARY)
            arrow = "up" if d > 0 else ("down" if d < 0 else None)
            if arrow:
                icons.draw_icon(line, arrow, 10, color).pack(side="left",
                                                             padx=(SP_SM, 0),
                                                             pady=4)
            ctk.CTkLabel(line, text=f"{d:+.1f}pp", font=font(SIZE_TINY),
                         text_color=color).pack(side="left", padx=(3, 0))

            if abs(d) >= 5.0:
                C.Badge(line, "显著变化", DANGER if d < 0 else SUCCESS).pack(
                    side="right")

    # ═══════════════════════════════════════════════════════
    #  Tab 4 · 留存分析
    # ═══════════════════════════════════════════════════════

    # 二游经验健康线：次日留存约 45%，7 日留约为次留的 47%，30 日约 26%。
    # 健康线不是真理，是「低于它就该查原因」的触发器 —— 用途写在卡片的 accent 上。
    RET_HEALTH = 45.0

    def _build_retention(self, parent):
        bar = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        bar.pack(fill="x", pady=(0, SP_MD))

        self._ret_game = C.Field(bar, "游戏", kind="menu",
                                 values=["全部"] + GAMES,
                                 width=176, label_width=32, default="全部")
        self._ret_game.pack(side="left")
        self._ret_game.widget.configure(
            command=lambda _v: self._refresh_retention())

        ctk.CTkLabel(bar,
                     text="口径：BI 汇总留存率 · 未录入的天自动跳过",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="right", pady=6)

        self._ret_host = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        self._ret_host.pack(fill="x")

        self._refresh_retention()

    def _refresh_retention(self):
        host = self._ret_host
        for w in host.winfo_children():
            w.destroy()

        game = self._ret_game.get()
        end = date_str()
        rows = retention_series(date_str(days_ago(60)), end, game)
        if not rows:
            C.EmptyState(host, "还没有留存数据", "trend",
                         "在「数据」页录入次留 / 7留 / 30留，或载入演示数据",
                         "载入演示数据", self._load_demo).pack(fill="x")
            return

        cur = [r for r in rows if r["date"] >= date_str(days_ago(30))]
        prev = [r for r in rows if r["date"] < date_str(days_ago(30))]
        stats = retention_stats(date_str(days_ago(30)), end, game)

        # ── 三张留存卡 ──
        wrap = ctk.CTkFrame(host, fg_color="transparent", height=1)
        wrap.pack(fill="x", pady=(0, SP_LG))
        for i in range(3):
            wrap.grid_columnconfigure(i, weight=1, uniform="ret")

        prev_stats = retention_stats(date_str(days_ago(60)),
                                     date_str(days_ago(30)), game)

        cards_spec = [
            ("r1", "次日留存", self.RET_HEALTH),
            ("r7", "7日留存", self.RET_HEALTH * 0.47),
            ("r30", "30日留存", self.RET_HEALTH * 0.26),
        ]
        for i, (key, label, line) in enumerate(cards_spec):
            v = stats[key]
            p = prev_stats[key]
            if v is None:
                C.StatCard(wrap, label, "—", None, None).grid(
                    row=0, column=i, sticky="nsew",
                    padx=(0 if i == 0 else SP_SM, 0))
                continue
            # 留存的环比用「百分点差 pp」而不是百分比变化 ——
            # 留存率本身已是比例，再做一次百分比变化会把 45→40 放大成 -11%；
            # 行业口径统一用 pp，跌 5 个点就说跌 5.0pp，不制造情绪数字。
            if p:
                d = v - p
                d_txt = f"较上期 {d:+.1f}pp"
                d_dir = "up" if d >= 0 else "down"
            else:
                d_txt, d_dir = None, None
            accent = DANGER if v < line else None
            C.StatCard(wrap, label, f"{v:.1f}%", d_txt, d_dir,
                       accent=accent).grid(
                row=0, column=i, sticky="nsew",
                padx=(0 if i == 0 else SP_SM, 0))

        # ── 留存曲线 ──
        chart_card = C.Card(host)
        chart_card.pack(fill="x", pady=(0, SP_LG))
        head = ctk.CTkFrame(chart_card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "留存曲线 · 近 30 天", icon="trend").pack(side="left")
        ctk.CTkLabel(head, text=self._retention_hint(stats),
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="right")

        chart = charts.LineChart(chart_card.body, height=210)
        chart.pack(fill="x", padx=SP_SM, pady=(0, SP_MD))
        chart.set_data({
            "labels": [r["date"][-5:] for r in cur],
            "series": [
                {"name": "次日留存",
                 "values": self._ret_vals(cur, "retention_1"),
                 "color": PRIMARY, "axis": "left", "fill": True,
                 "width": 2, "smooth": 5},
                {"name": "7日留存",
                 "values": self._ret_vals(cur, "retention_7"),
                 "color": INFO, "axis": "left", "width": 1.4, "smooth": 5},
                {"name": "30日留存",
                 "values": self._ret_vals(cur, "retention_30"),
                 "color": AI, "axis": "left", "width": 1.4, "smooth": 5},
            ],
        })

        # ── 人话解读 ──
        insight = self._retention_insight(cur, prev_stats, stats, game)
        if insight:
            card = C.Card(host, accent=AI)
            card.pack(fill="x")
            inner = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
            inner.pack(fill="x", padx=SP_LG, pady=SP_MD)
            icons.draw_icon(inner, "bulb", 15, AI).pack(side="left", pady=2)
            ctk.CTkLabel(inner, text=insight, font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, anchor="w", justify="left",
                         wraplength=780).pack(side="left", padx=(8, 0),
                                              fill="x", expand=True)

    @staticmethod
    def _ret_vals(rows, col):
        """留存列 → 绘图序列；未统计的天给 None，折线自动断开而不是砸到 0。"""
        return [r[col] if valid_retention(r[col]) else None for r in rows]

    @staticmethod
    def _retention_hint(stats):
        """曲线右上角的一句话：7留/次留粘性系数。"""
        if stats["r1"] and stats["r7"]:
            return f"7留/次留 粘性系数 {stats['r7'] / stats['r1']:.2f}"
        return ""

    def _retention_insight(self, cur, prev_stats, stats, game):
        """
        留存的人话解读。
        结构：健康线结论 → 趋势结论 → 交叉归因（联动互动率方向）。
        交叉归因是这一段的价值所在：单看留存只能知道「跌了」，
        对着互动率的方向看，才能区分「新增质量差」还是「内容吸引力回落」。
        """
        r1, r7 = stats["r1"], stats["r7"]
        if r1 is None:
            return ""
        parts = []
        if r1 < self.RET_HEALTH:
            gap = self.RET_HEALTH - r1
            parts.append(f"次日留存 {r1:.1f}%，低于二游 45% 健康线 {gap:.1f}pp")
        else:
            parts.append(f"次日留存 {r1:.1f}%，高于 45% 健康线，新增质量健康")

        p1 = prev_stats["r1"]
        if p1:
            d1 = r1 - p1
            if d1 <= -2:
                parts.append(f"较上期下滑 {abs(d1):.1f}pp")
            elif d1 >= 2:
                parts.append(f"较上期回升 {d1:.1f}pp")

        if r7 is not None and r1:
            ratio = r7 / r1
            if ratio < 0.42:
                parts.append("7留/次留比值偏低，首周内容消耗偏快，"
                             "建议检查活动间隔与长线目标引导")

        # 交叉归因：留存方向 × 互动率方向
        p7 = prev_stats["r7"]
        ret_down = (p1 and r1 - p1 <= -2) or (p7 and r7 and r7 - p7 <= -2)
        if ret_down and cur:
            rows = metrics_between(date_str(days_ago(60)), date_str(), game)
            if len(rows) >= 8:
                mid = len(rows) // 2
                pa = sum(r["interaction_rate"] or 0 for r in rows[:mid]) / mid
                pb = sum(r["interaction_rate"] or 0 for r in rows[mid:]) / (len(rows) - mid)
                if pb < pa - 0.15:
                    parts.append("留存下滑与互动率回落同期出现，"
                                 "指向内容吸引力整体回落：优先复盘版本内容供给与活动节奏")
                else:
                    parts.append("留存下滑但互动率平稳，更可能是新增渠道质量波动："
                                 "建议分渠道核查新增来源")
        return "；".join(parts) + "。"

    # ── Ctrl+S ──
    def _save_analysis(self):
        if self._analysis_tab == "ai":
            self._save_ai_result()
        else:
            self.toast("分析页的结论由数据实时计算，无需保存", WARNING)
