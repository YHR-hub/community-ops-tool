# -*- coding: utf-8 -*-
"""
行业情报页（v4.5）——与「行业知识库」目录联动的活数据层。

设计动机：行业观察原来躺在 markdown 里（行业知识库/ 目录），
看的时候是资料、用的时候找不到。这一页把它变成可查询的数据：

  · 行业事件时间线 —— 版本/舆情/公司/竞品/政策，按日期倒序
  · 竞品流水对比   —— 月度横向条形图（第三方估算口径，脚注标明）
  · 舆情案例卡     —— 市场 / 框架 / 启示 三段式

数据维护两条通道：
  · seed_industry.py 从知识库摘录结构化肥入（批量）
  · 以后可在本页手动补录（单条，与雷达周报配合）
"""
import customtkinter as ctk

import components as C
import charts
from theme import (
    BG_ELEVATED, PRIMARY, INFO, WARNING, DANGER, SUCCESS, AI,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    SP_XS, SP_SM, SP_MD, SP_LG, SIZE_TINY, SIZE_SMALL,
    RADIUS_SM, font,
)
from db import query

# 分类 → 颜色（时间线徽标用）
CAT_COLOR = {
    "版本": PRIMARY, "舆情": DANGER, "公司": AI,
    "竞品": INFO, "政策": WARNING, "行业": TEXT_SECONDARY,
}
# 市场 → 颜色（案例卡用）
MKT_COLOR = {
    "美": INFO, "韩": DANGER, "日": SUCCESS, "中": PRIMARY, "全球": WARNING,
}


class IndustryMixin:
    """由 App 混入，提供行业情报页。"""

    def show_industry(self):
        self.clear_main()
        self._build_industry()

    # ═══════════════════════════════════════════════════════
    def _build_industry(self):
        body, _page = self.page_scaffold(
            "industry", "行业情报",
            "行业动态 · 竞品流水 · 舆情案例（与「行业知识库」联动）",
            icon="search", refresh=self._build_industry)

        evs = query("SELECT * FROM industry_events ORDER BY date DESC, id DESC")
        revs = query("SELECT * FROM competitor_revenue ORDER BY month DESC, revenue DESC")
        cases = query("SELECT * FROM insight_cases ORDER BY id")

        if not (evs or revs or cases):
            C.Card(body).pack(fill="x")
            return C.EmptyState(
                body, "还没有行业情报数据", "search",
                "运行 seed_industry.py 从知识库灌入，或稍后手动补录",
                height=160)

        # ── KPI 行 ──
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x")
        for k in range(4):
            grid.grid_columnconfigure(k, weight=1, uniform="kpi")

        latest_month = revs[0]["month"] if revs else "—"
        latest_ev = evs[0]["date"] if evs else "—"
        kpis = [
            ("行业事件", str(len(evs)), f"最近 {latest_ev}", None),
            ("竞品流水月", latest_month, f"{len(revs)} 条产品记录", None),
            ("舆情案例", str(len(cases)), "可面试引用", None),
            ("数据来源", "公开信息", "第三方估算口径", None),
        ]
        for k, (lab, val, delta, accent) in enumerate(kpis):
            C.StatCard(grid, lab, val, delta, None, accent=accent).grid(
                row=0, column=k, sticky="nsew",
                padx=(0 if k == 0 else SP_SM, 0))

        # ── 卡 1：行业事件时间线 ──
        ev_card = C.Card(body)
        ev_card.pack(fill="x", pady=(SP_MD, 0))
        ev_head = ctk.CTkFrame(ev_card.body, fg_color="transparent", height=1)
        ev_head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(ev_head, "行业事件时间线", icon="clock").pack(side="left")
        ctk.CTkLabel(ev_head, text=f"共 {len(evs)} 条 · 倒序",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(side="right")

        ev_wrap = ctk.CTkFrame(ev_card.body, fg_color="transparent")
        ev_wrap.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
        for e in evs[:12]:
            row = ctk.CTkFrame(ev_wrap, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=str(e["date"])[5:], width=46,
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                         anchor="w").pack(side="left")
            C.Badge(row, e["category"],
                    CAT_COLOR.get(e["category"], TEXT_SECONDARY)).pack(
                side="left", padx=(SP_XS, SP_SM))
            txt = ctk.CTkFrame(row, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(txt, text=e["title"], font=font(SIZE_SMALL),
                         text_color=TEXT_PRIMARY, anchor="w",
                         justify="left").pack(fill="x")
            if e["impact"]:
                ctk.CTkLabel(txt, text="→ " + e["impact"],
                             font=font(SIZE_TINY), text_color=TEXT_SECONDARY,
                             anchor="w", justify="left").pack(fill="x")

        # ── 卡 2：竞品流水对比 ──
        if revs:
            rev_card = C.Card(body)
            rev_card.pack(fill="x", pady=(SP_MD, 0))
            rev_head = ctk.CTkFrame(rev_card.body, fg_color="transparent", height=1)
            rev_head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
            C.SectionTitle(rev_head, f"竞品流水对比 · {latest_month}",
                           icon="money").pack(side="left")
            ctk.CTkLabel(rev_head, text="单位：亿元（全平台，第三方估算）",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(side="right")

            month_rows = [r for r in revs if r["month"] == latest_month]
            chart = charts.BarChart(rev_card.body, height=max(150, 34 * len(month_rows)),
                                    horizontal=True)
            chart.pack(fill="x", padx=SP_SM, pady=(0, SP_XS))
            chart.set_data({
                "items": [{"label": r["product"], "value": r["revenue"]}
                          for r in month_rows],
                "color": PRIMARY,
            })
            ctk.CTkLabel(rev_card.body,
                         text="口径说明：第三方机构依据商店榜单估算，与厂商披露口径有出入；对比看趋势。",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                         anchor="w").pack(fill="x", padx=SP_LG, pady=(0, SP_MD))

        # ── 卡 3：舆情案例卡 ──
        if cases:
            case_card = C.Card(body)
            case_card.pack(fill="x", pady=(SP_MD, 0))
            case_head = ctk.CTkFrame(case_card.body, fg_color="transparent", height=1)
            case_head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
            C.SectionTitle(case_head, "舆情案例卡（面试可引用）",
                           icon="bulb").pack(side="left")

            wrap = ctk.CTkFrame(case_card.body, fg_color="transparent")
            wrap.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
            for cs in cases:
                box = ctk.CTkFrame(wrap, fg_color=BG_ELEVATED,
                                   corner_radius=RADIUS_SM)
                box.pack(fill="x", pady=(0, SP_SM))
                head = ctk.CTkFrame(box, fg_color="transparent")
                head.pack(fill="x", padx=SP_SM, pady=(SP_XS, 0))
                ctk.CTkLabel(head, text=cs["name"], font=font(SIZE_SMALL),
                             text_color=TEXT_PRIMARY,
                             anchor="w").pack(side="left")
                C.Badge(head, cs["market"],
                        MKT_COLOR.get(cs["market"], TEXT_SECONDARY)).pack(
                    side="left", padx=(SP_SM, 0))
                if cs["framework"]:
                    ctk.CTkLabel(box, text="框架：" + cs["framework"],
                                 font=font(SIZE_TINY), text_color=TEXT_SECONDARY,
                                 anchor="w", justify="left",
                                 wraplength=760).pack(fill="x", padx=SP_SM)
                if cs["takeaway"]:
                    ctk.CTkLabel(box, text="启示：" + cs["takeaway"],
                                 font=font(SIZE_TINY), text_color=PRIMARY,
                                 anchor="w", justify="left",
                                 wraplength=760).pack(fill="x", padx=SP_SM,
                                                      pady=(0, SP_XS))

        # ── 底部轻提示 ──
        ctk.CTkLabel(body,
                     text="维护：seed_industry.py 批量灌入 · 可在「行业知识库」目录查看完整档案",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                     anchor="w").pack(fill="x", pady=(SP_MD, 0))
