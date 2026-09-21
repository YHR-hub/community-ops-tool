"""
总览页 —— 新版默认首页
======================

为什么加这一页：
  旧版打开后直接进「数据工作台」的录入表单，而数据库通常是空的，
  于是第一屏是一片空白 —— 这就是用户觉得「功能不行」的主因之一。
  总览页解决两个问题：
    1. 打开就有信息可看（指标、趋势、风险、进度）
    2. 遇到异常数据时，用强调卡把问题拎出来，一眼看到
"""

from datetime import datetime

import customtkinter as ctk

import theme
from theme import (
    BG_CARD, BG_APP, BG_ELEVATED, BG_BORDER,
    PRIMARY, PRIMARY_HOVER, DANGER, SUCCESS, WARNING, INFO, AI, NEUTRAL,
    TEXT_PRIMARY, TEXT_BODY, TEXT_SECONDARY, TEXT_TERTIARY,
    font, SIZE_H3, SIZE_BODY, SIZE_SMALL, SIZE_TINY,
    SP_XS, SP_SM, SP_MD, SP_LG, RADIUS_MD,
)
import icons
import components as C
import charts
from db import (
    metrics_between, latest_version, task_progress, open_risks, date_str, days_ago, parse_date, retention_stats,
    anomaly_report, query,
)

# 指标异常判定阈值（抽成常量，不再散落在各处）
THRESHOLDS = {
    "interaction_rate_warn": 3.0,    # 互动率低于此值 → 强调
    "dau_drop_warn": -5.0,           # DAU 环比跌幅超此值 → 强调
    "retention1_drop_pp": -1.5,      # 次留 7 天均值环比跌幅（pp）→ 实时预警
}


class OverviewMixin:
    """由 App 混入，提供总览页。"""

    def show_overview(self):
        self.clear_main()
        self._build_overview()

    # ═══════════════════════════════════════════════════════
    def _build_overview(self):
        body, _page = self.page_scaffold(
            "overview", "总览", "一眼看清当前版本的健康状况与待办压力",
            icon="grid", refresh=self._build_overview)

        v = latest_version()
        rows = self._overview_metrics(30)
        has_data = bool(rows)

        if v:
            days = max(0, (datetime.now() - parse_date(v["start_date"])).days)
            warm = f"{v['game']} {v['version']} · 上线第 {days} 天 · 数据截至今日"
        else:
            warm = "尚未创建版本 —— 先去「版本」页建一个，整条主线就跑起来了"

        if has_data or v:
            bar = ctk.CTkFrame(body, fg_color="transparent", height=1)
            bar.pack(fill="x", pady=(0, SP_MD))
            ctk.CTkLabel(bar, text=warm, font=font(SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left")
            # v4.2：早报智能体入口 —— 感知/决策/行动/产出见 agent.py
            ctk.CTkButton(bar, text="生成今日早报", width=132, height=30,
                          font=font(SIZE_SMALL, bold=True),
                          fg_color=AI, hover_color="#8F79E8",
                          command=self._open_briefing).pack(side="right")

        self._overview_stats(body, rows, v)
        self._overview_trend(body, rows)

        grid = ctk.CTkFrame(body, fg_color="transparent", height=1)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="ov")
        grid.grid_columnconfigure(1, weight=1, uniform="ov")

        self._overview_risks(grid, v)
        self._overview_progress(grid, v)

        if not has_data and not v:
            self._overview_getting_started(body)

    # ═══════════════════════════════════════════════════════
    #  数据准备
    # ═══════════════════════════════════════════════════════
    def _overview_metrics(self, days):
        return metrics_between(date_str(days_ago(days)), date_str())

    def _split_periods(self, rows, half=15):
        """把区间切成前后两段，用于算环比。"""
        if len(rows) < 4:
            return rows, []
        mid = len(rows) // 2
        return rows[:mid], rows[mid:]

    @staticmethod
    def _avg(rows, key):
        vals = [r[key] for r in rows if r[key] is not None]
        return sum(vals) / len(vals) if vals else 0

    @staticmethod
    def _delta(cur, prev):
        if not prev:
            return None, None
        pct = (cur - prev) / prev * 100
        return f"较上期 {pct:+.1f}%", ("up" if pct >= 0 else "down")

    # ═══════════════════════════════════════════════════════
    #  指标卡
    # ═══════════════════════════════════════════════════════
    def _overview_stats(self, parent, rows, v):
        wrap = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        wrap.pack(fill="x", pady=(0, SP_LG))
        for i in range(4):
            wrap.grid_columnconfigure(i, weight=1, uniform="stat")

        if rows:
            prev, cur = self._split_periods(rows)
            avg_dau = self._avg(rows, "dau")
            avg_posts = self._avg(rows, "new_posts")
            avg_rate = self._avg(rows, "interaction_rate")

            d_dau = self._delta(self._avg(cur, "dau"), self._avg(prev, "dau"))
            d_post = self._delta(self._avg(cur, "new_posts"), self._avg(prev, "new_posts"))
            d_rate = self._delta(self._avg(cur, "interaction_rate"), self._avg(prev, "interaction_rate"))

            # 互动率低于阈值 → 这张卡变强调卡
            rate_accent = DANGER if avg_rate < THRESHOLDS["interaction_rate_warn"] else None

            cards = [
                (f"{int(avg_dau):,}", "平均 DAU", d_dau, None),
                (f"{int(avg_posts):,}", "日均帖子", d_post, None),
                (f"{avg_rate:.1f}%", "平均互动率", d_rate, rate_accent),
                (self._todo_value(v), "待办任务", self._todo_delta(v), None),
            ]
        else:
            cards = [
                ("—", "平均 DAU", None, None),
                ("—", "日均帖子", None, None),
                ("—", "平均互动率", None, None),
                (self._todo_value(v), "待办任务", self._todo_delta(v), None),
            ]

        for i, (val, label, delta, accent) in enumerate(cards):
            # delta 有三种合法形态：(文字, 方向) 二元组 / 纯文字（如 "11/19 已完成"）/ None。
            # v3.1 这里直接二元组解包，纯文字形态会 ValueError ——
            # 潜伏到 v4.1 才被演示数据的随机序列变化踩出来，属于典型的「碰巧没炸」。
            if isinstance(delta, tuple):
                d_txt, d_dir = delta
            elif delta:
                d_txt, d_dir = delta, None
            else:
                d_txt, d_dir = None, None
            C.StatCard(wrap, label, val, d_txt, d_dir, accent=accent).grid(
                row=0, column=i, sticky="nsew", padx=(0 if i == 0 else SP_SM, 0))

    def _todo_value(self, v):
        if not v:
            return "0"
        total, done = task_progress(v["id"])
        return f"{total - done}"

    def _todo_delta(self, v):
        if not v:
            return None
        total, done = task_progress(v["id"])
        if not total:
            return "尚无任务"
        overdue = 0
        today = date_str()
        for r in __import__("db").query(
                "SELECT deadline FROM checklists WHERE version_id=? AND status!='done'",
                (v["id"],)):
            if r["deadline"] and r["deadline"] < today:
                overdue += 1
        if overdue:
            return None
        return f"{done}/{total} 已完成"

    # ═══════════════════════════════════════════════════════
    #  趋势图
    # ═══════════════════════════════════════════════════════
    def _overview_trend(self, parent, rows):
        card = C.Card(parent)
        card.pack(fill="x", pady=(0, SP_LG))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "DAU 与互动率趋势 · 近 30 天", icon="trend").pack(side="left")

        ctk.CTkLabel(head, text=self._trend_hint(rows), font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY).pack(side="right")

        # 双轴图在这里有个固有缺陷：DAU 与互动率量纲完全不同，
        # 两条线各自按自己的轴映射后会在视觉上互相穿插，
        # 30 天日频数据下更像一团彩色噪声，读不出任何结论。
        # 解法：DAU 用「填充面积」表达体量（左轴），互动率用「细折线」表达
        # 波动（右轴），并让互动率线明显更细、更亮，两者不再抢同一视觉层级。
        chart = charts.LineChart(card.body, height=200)
        chart.pack(fill="x", padx=SP_SM, pady=(0, SP_MD))

        if rows:
            labels = [r["date"][-5:] for r in rows]
            chart.set_data({
                "labels": labels,
                "series": [
                    {"name": "DAU", "values": [r["dau"] for r in rows],
                     "color": PRIMARY, "axis": "left", "fill": True,
                     "width": 2, "smooth": 5},
                    {"name": "互动率(%)", "values": [r["interaction_rate"] for r in rows],
                     "color": INFO, "axis": "right", "width": 1.4, "smooth": 3},
                ],
                # v4.4：把版本事件标到曲线上——「那天发生了什么」和
                # 「数据怎么动」对得上，趋势图才从展示变成分析工具。
                "markers": self._trend_markers(rows),
            })
        else:
            for w in card.body.winfo_children():
                if isinstance(w, charts.LineChart):
                    w.destroy()
            C.EmptyState(card.body, "还没有运营数据", "chart",
                         "去「数据」页录入，或点击下方载入演示数据",
                         "载入演示数据", self._load_demo).pack(fill="x")

    def _trend_markers(self, rows, limit=6):
        """
        v4.4：把近期版本事件映射成趋势图的标注（数据 × 事件对齐）。

        规则：
          · 只标数据覆盖范围内的事件（曲线上没有的日子标了没意义）；
          · 事件日不在数据点上时，就近吸附（±1 天）——日志录入的日期
            和指标日期常有半天一天的出入；
          · 最多 6 个 + 标签上下交错，避免挤成一团。
        """
        try:
            date_idx = {r["date"]: i for i, r in enumerate(rows)}
            evs = query(
                "SELECT name, start_date FROM events "
                "WHERE start_date>=? ORDER BY start_date LIMIT 12",
                (rows[0]["date"],))
        except Exception:
            return []
        out = []
        for e in evs or []:
            d = str(e["start_date"])
            idx = date_idx.get(d)
            if idx is None:      # 就近吸附 ±1 天
                from datetime import datetime, timedelta
                try:
                    base = datetime.strptime(d, "%Y-%m-%d").date()
                except ValueError:
                    continue
                for off in (1, -1):
                    idx = date_idx.get(str(base + timedelta(days=off)))
                    if idx is not None:
                        break
            if idx is None:
                continue
            out.append({"index": idx,
                        "label": str(e["name"])[:9],
                        "slot": len(out) % 2})
            if len(out) >= limit:
                break
        return out

    def _trend_hint(self, rows):
        """
        给趋势图加一句人话解读。
        运营看的是结论，不是曲线本身 —— 这句话比图更有价值。
        """
        if len(rows) < 4:
            return ""
        prev, cur = self._split_periods(rows)
        dau_d = self._avg(cur, "dau") - self._avg(prev, "dau")
        rate_d = self._avg(cur, "interaction_rate") - self._avg(prev, "interaction_rate")
        if dau_d > 0 and rate_d < 0:
            return "DAU 上升但互动率下滑，需排查内容吸引力"
        if dau_d < 0 and rate_d > 0:
            return "用户量回落但互动转好，留存质量在改善"
        if dau_d > 0 and rate_d > 0:
            return "双指标同步向好"
        return "双指标同步走弱，建议复盘近期活动"

    # ═══════════════════════════════════════════════════════
    def _auto_warnings(self):
        """
        数据驱动的实时预警（不落库，每次进页重算）。

        为什么放总览而不只放分析页：留存与 DAU 异动是运营第一信号，
        掉了必须主动浮到首屏，不能躺在分析 Tab 里等人去翻。

        两条来源：
          1. 留存：近 7 天均值 vs 前 7 天均值（均值对均值，单日噪声会假预警）；
          2. 异动归因：db.anomaly_report 的下跌项，meta 带游戏维度拆分线索。
        上涨不进风险卡 —— 暴涨是机会不是风险，风险卡只收「需要出手」的事。
        """
        end = date_str()
        warns = []

        cur = retention_stats(date_str(days_ago(7)), end)
        prev = retention_stats(date_str(days_ago(14)), date_str(days_ago(7)))
        if cur["r1"] and prev["r1"]:
            d = cur["r1"] - prev["r1"]
            if d <= THRESHOLDS["retention1_drop_pp"]:
                warns.append((
                    f"次日留存近 7 天均值 {cur['r1']:.1f}%，"
                    f"环比下滑 {abs(d):.1f}pp",
                    "实时检测 · 近 7 天 vs 前 7 天"))

        for a in anomaly_report():
            if not a["down"]:
                continue
            title = f"{a['metric']}异动：最近数据日 {a['change']}（vs 前 7 日均值）"
            warns.append((title, a["note"] or "实时检测 · 建议进「分析」页归因"))
        return warns

    #  风险预警
    # ═══════════════════════════════════════════════════════
    def _overview_risks(self, parent, v):
        card = C.Card(parent)
        # sticky="new"（north+east+west）而不是 "nsew"：
        # 风险卡内容少、进度卡内容多，用 nsew 会把风险卡纵向拉伸，
        # 左侧色条被撑到整卡高度、文字浮在中间，截图里那块巨大空白就是这么来的。
        card.grid(row=0, column=0, sticky="new", padx=(0, SP_SM))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "风险预警", icon="warn",
                       icon_color=DANGER).pack(side="left")

        risks = open_risks(v["id"]) if v else []
        high = [r for r in risks if r["probability"] == "high"]

        auto = self._auto_warnings()

        if risks or auto:
            color = DANGER if (high or auto) else WARNING
            C.Badge(head, f"{len(risks) + len(auto)} 项", color).pack(side="right")

        if not risks and not auto:
            C.EmptyState(card.body, "当前没有记录风险项", "shield",
                         "可在「版本」详情里添加或自动标记").pack(fill="x")
            return

        for title, meta in auto:
            row = C.Row(card.body, accent=DANGER)
            row.pack(fill="x", padx=SP_LG, pady=(0, SP_SM))
            ctk.CTkLabel(row.text, text=title, font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, anchor="w", wraplength=250,
                         justify="left").pack(anchor="w")
            ctk.CTkLabel(row.text, text=meta, font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY,
                         anchor="w").pack(anchor="w")

        for i, r in enumerate(risks[:4]):
            prob_label, prob_color = theme.RISK_LEVEL.get(
                r["probability"], ("中", WARNING))
            # 色条颜色在构造时就传给 C.Row —— 内部色条带显式 height，
            # 不会被 fill="y" 拉成默认的 250px（那样整行会被撑高）。
            row = C.Row(card.body, accent=prob_color)
            row.pack(fill="x", padx=SP_LG, pady=(0, SP_SM))

            ctk.CTkLabel(row.text, text=r["title"], font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, anchor="w", wraplength=250,
                         justify="left").pack(anchor="w")
            meta = f"{theme.RISK_IMPACT.get(r['impact'], '')}"
            if r["owner"]:
                meta += f" · {r['owner']}"
            ctk.CTkLabel(row.text, text=meta, font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY, anchor="w").pack(anchor="w")

    # ═══════════════════════════════════════════════════════
    #  版本进度
    # ═══════════════════════════════════════════════════════
    def _overview_progress(self, parent, v):
        card = C.Card(parent)
        card.grid(row=0, column=1, sticky="new", padx=(SP_SM, 0))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "版本进度", icon="calendar").pack(side="left")

        if not v:
            C.EmptyState(card.body, "还没有版本", "calendar",
                         "创建版本后这里会显示任务完成度",
                         "新建版本", lambda: self.show_view("versions")).pack(fill="x")
            return

        total, done = task_progress(v["id"])
        pct = int(done / total * 100) if total else 0

        ctk.CTkLabel(head, text=f"{done} / {total} 完成", font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY).pack(side="right")

        bar = charts.ProgressBar(card.body, height=6,
                                 color=SUCCESS if pct == 100 else PRIMARY)
        bar.pack(fill="x", padx=SP_LG, pady=(0, SP_SM))
        # 与 analysis 页保持一致：回调前确认组件还在（切页时可能已被销毁）
        bar.after(30, lambda: bar.set(pct) if bar.winfo_exists() else None)

        # 分类进度
        from db import query
        cat_rows = query(
            "SELECT category, COUNT(*) AS total, "
            "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done "
            "FROM checklists WHERE version_id=? GROUP BY category "
            "ORDER BY total DESC LIMIT 4", (v["id"],))

        if not cat_rows:
            ctk.CTkLabel(card.body, text="尚未导入任务清单",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
                pady=(0, SP_MD))
            return

        for r in cat_rows:
            t, d = r["total"] or 0, r["done"] or 0
            row = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
            row.pack(fill="x", padx=SP_LG, pady=(0, SP_XS))

            ctk.CTkLabel(row, text=r["category"] or "常规", font=font(SIZE_TINY),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left")
            state = "已完成" if d == t and t else ("进行中" if d else "未开始")
            color = SUCCESS if state == "已完成" else (
                WARNING if state == "进行中" else TEXT_TERTIARY)
            ctk.CTkLabel(row, text=f"{d}/{t}", font=font(SIZE_TINY),
                         text_color=color).pack(side="right")

        ctk.CTkFrame(card.body, fg_color="transparent", height=SP_SM).pack()

    # ═══════════════════════════════════════════════════════
    #  空库引导
    # ═══════════════════════════════════════════════════════
    def _overview_getting_started(self, parent):
        card = C.Card(parent, accent=AI)
        card.pack(fill="x", pady=(SP_LG, 0))

        inner = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        inner.pack(fill="x", padx=SP_LG, pady=SP_LG)

        top = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        top.pack(fill="x")
        icons.draw_icon(top, "bolt", 15, AI).pack(side="left", pady=2)
        C.SectionTitle(top, "还没有数据？三步跑起来", icon=None).pack(
            side="left", padx=(6, 0))

        steps = [
            ("1", "创建版本", "在「版本」页新建一个版本，导入标准任务模板", "versions"),
            ("2", "录入数据", "在「数据」页录入每日指标，或导入 CSV", "data"),
            ("3", "生成报告", "在「报告」页一键生成智能运营报告", "report"),
        ]
        for n, title, desc, target in steps:
            row = ctk.CTkFrame(inner, fg_color="transparent", height=1)
            row.pack(fill="x", pady=(SP_SM, 0))

            num = ctk.CTkFrame(row, fg_color=BG_ELEVATED, width=22, height=22,
                               corner_radius=11)
            num.pack(side="left")
            num.pack_propagate(False)
            ctk.CTkLabel(num, text=n, font=font(SIZE_TINY, bold=True),
                         text_color=AI).place(relx=0.5, rely=0.5, anchor="center")

            txt = ctk.CTkFrame(row, fg_color="transparent", height=1)
            txt.pack(side="left", padx=SP_SM, fill="x", expand=True)
            ctk.CTkLabel(txt, text=title, font=font(SIZE_SMALL, bold=True),
                         text_color=TEXT_PRIMARY, anchor="w").pack(anchor="w")
            ctk.CTkLabel(txt, text=desc, font=font(SIZE_TINY),
                         text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w")

            C.GhostButton(row, "前往", lambda t=target: self.show_view(t),
                          width=62, height=28).pack(side="right")

    # ═══════════════════════════════════════════════════════
    def _load_demo(self):
        """载入演示数据，见 seed_demo.py。"""
        try:
            import seed_demo
            n = seed_demo.seed(force=False)
            self.toast(f"已载入演示数据（{n} 条记录）")
            self.log("载入演示数据")
            self._render_current_version()
            self.show_view("overview")
        except Exception as e:
            self.toast(f"载入失败：{e}", DANGER)

    # ═══════════════════════════════════════════════════════
    #  今日早报（v4.2 智能体，逻辑在 agent.py）
    # ═══════════════════════════════════════════════════════
    def _open_briefing(self):
        """
        早报按钮 —— 必须走线程。

        v4.3 修的真 bug：这里原本直接在主线程调 generate()，
        而 generate 在配置了 API Key 时会同步请求 LLM（timeout 45s），
        等于把整个窗口冻住 45 秒 —— 点了按钮像死机一样。
        analysis 页的 AI 建议早就用了线程，这条路径漏了。
        现在：线程里生成 → after(0) 回主线程渲染 → 回调里检查窗口还在不在。
        """
        import threading

        import agent as ops_agent
        self.toast("早报生成中…")

        def worker():
            try:
                b = ops_agent.generate()
            except Exception as e:      # noqa: BLE001
                # 线程里只能兜住异常再回传主线程（不能在这里崩溃）
                err = str(e)
                self.after(0, lambda: self._on_briefing_failed(err))
                return
            self.after(0, lambda: self._on_briefing_ready(b))

        threading.Thread(target=worker, daemon=True).start()

    def _on_briefing_ready(self, b):
        """主线程回调：窗口可能已在等待期间被关掉，先确认还活着。"""
        if not self.winfo_exists():
            return
        self.log("生成今日早报")
        self._show_briefing(b)

    def _on_briefing_failed(self, err):
        if not self.winfo_exists():
            return
        self.toast(f"早报生成失败：{err}", DANGER)

    def _show_briefing(self, b):
        """早报抽屉：结论 → 正文 → 预警 → 建议动作（可转待办）→ 决策轨迹。"""
        import agent as ops_agent
        LEVEL_COLOR = {"danger": DANGER, "warn": WARNING, "info": INFO}

        dlg = ctk.CTkToplevel(self)
        dlg.title("今日运营早报")
        dlg.configure(fg_color=BG_APP)
        x = max(0, self.winfo_rootx() + (self.winfo_width() - 680) // 2)
        y = max(0, self.winfo_rooty() + 36)
        dlg.geometry(f"680x740+{x}+{y}")
        dlg.transient(self)

        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=SP_MD, pady=SP_MD)

        # 头部：标题 + 生成方式徽标 + 时间
        head = ctk.CTkFrame(scroll, fg_color="transparent", height=1)
        head.pack(fill="x", pady=(0, SP_SM))
        C.SectionTitle(head, "今日运营早报", icon="bolt",
                       icon_color=AI).pack(side="left")
        ctk.CTkLabel(head, text=b["generated_at"], font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY).pack(side="right", padx=(SP_SM, 0))
        C.Badge(head, "AI 润色" if b["ai_polished"] else "规则生成",
                AI if b["ai_polished"] else NEUTRAL).pack(side="right")

        # headline
        ctk.CTkLabel(scroll, text=b["headline"], font=font(SIZE_H3, bold=True),
                     text_color=DANGER if b["alerts"] else TEXT_PRIMARY,
                     anchor="w", wraplength=600, justify="left").pack(
            anchor="w", pady=(0, SP_SM))

        # 正文
        card = C.Card(scroll)
        card.pack(fill="x", pady=(0, SP_MD))
        ctk.CTkLabel(card.body, text=b["narrative"], font=font(SIZE_BODY),
                     text_color=TEXT_BODY, anchor="w", wraplength=560,
                     justify="left").pack(anchor="w", padx=SP_LG, pady=SP_MD)

        # 预警
        if b["alerts"]:
            ctk.CTkLabel(scroll, text="需要出手", font=font(SIZE_SMALL, bold=True),
                         text_color=TEXT_SECONDARY, anchor="w").pack(
                anchor="w", pady=(0, SP_XS))
            for a in b["alerts"]:
                row = C.Row(scroll, accent=LEVEL_COLOR.get(a["level"], NEUTRAL))
                row.pack(fill="x", pady=(0, SP_XS))
                ctk.CTkLabel(row.text, text=a["text"], font=font(SIZE_SMALL),
                             text_color=TEXT_BODY, anchor="w", wraplength=520,
                             justify="left").pack(anchor="w")

        # 建议动作（可一键转待办 —— 早报从「看到」闭环到「有人跟进」）
        if b["actions"]:
            act_head = ctk.CTkFrame(scroll, fg_color="transparent", height=1)
            act_head.pack(fill="x", pady=(SP_SM, SP_XS))
            ctk.CTkLabel(act_head, text="建议动作", font=font(SIZE_SMALL, bold=True),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left")

            def _commit(selected=None):
                # 闭环写库：任务进 checklists、风险进 risks（同名条目自动跳过）
                acts = selected if selected is not None else b["actions"]
                res = ops_agent.commit_actions(acts, game=b.get("game"))
                done = res["tasks"] + res["risks"]
                if done:
                    self.toast(
                        f"已转待办 {done} 项（任务 {res['tasks']} / 风险 {res['risks']}）")
                    dlg.destroy()
                    self._refresh()
                else:
                    self.toast("这些动作已在待办中，无需重复添加")

            ctk.CTkButton(act_head, text="全部转待办", width=96, height=26,
                          fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                          font=font(SIZE_TINY), corner_radius=13,
                          command=_commit).pack(side="right")
            for i, act in enumerate(b["actions"], 1):
                row = ctk.CTkFrame(scroll, fg_color="transparent", height=1)
                row.pack(fill="x", pady=(0, SP_XS))
                ctk.CTkLabel(row, text=f"{i}. {act}", font=font(SIZE_SMALL),
                             text_color=TEXT_BODY, anchor="w", wraplength=470,
                             justify="left").pack(side="left", anchor="w")
                ctk.CTkButton(row, text="转待办", width=58, height=24,
                              fg_color=BG_ELEVATED, hover_color=BG_BORDER,
                              text_color=TEXT_SECONDARY, font=font(SIZE_TINY),
                              corner_radius=12,
                              command=lambda a=act: _commit([a])).pack(
                    side="right")

        # 决策轨迹（可解释性：智能体每一步为什么这么查，全在这里）
        trace = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=RADIUS_MD)
        trace.pack(fill="x", pady=(SP_MD, 0))
        ctk.CTkLabel(trace, text="智能体决策轨迹", font=font(SIZE_TINY, bold=True),
                     text_color=TEXT_TERTIARY, anchor="w").pack(
            anchor="w", padx=SP_LG, pady=(SP_SM, 0))
        for step in b["trace"]:
            ctk.CTkLabel(trace, text=f"· {step}", font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY, anchor="w", wraplength=560,
                         justify="left").pack(anchor="w", padx=SP_LG,
                                              pady=(2, 0))
        ctk.CTkFrame(trace, fg_color="transparent", height=SP_SM).pack()
