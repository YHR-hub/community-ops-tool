# -*- coding: utf-8 -*-
"""
内容页（v4.7）——内容运营工作台。

为什么有这一页：工具的真实使用痕迹（activity_log）显示，用户真正在做的是
「内容发布与数据追踪」，而此前只能拿操作日志凑合记录。这一页把它升级为一等数据：

  · 内容作品库    —— 每条内容（平台 × 形式 × 标题）+ 发布数据 + 复盘
  · 形式实验对比  —— 按"形式"聚合的浏览对比（文章 vs 回答——真实实验）
  · 系列进度      —— 8 篇的内容系列状态一览

定位意义：工具从「模拟运营一款游戏」转向「运营自己真实在做的事」——
这也是对 JD「搭建完整的监测和分析体系」最直接的回应。
"""

import customtkinter as ctk

import components as C
import charts
from theme import (
    PRIMARY, SUCCESS, WARNING, DANGER, NEUTRAL, INFO,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_BODY,
    BG_CARD, SP_XS, SP_SM, SP_MD, SP_LG, SP_XL, SIZE_H2,
    SIZE_TINY, font,
)
from db import query, execute, valid_date, date_str

PLATFORMS = ["知乎", "公众号", "米游社", "小红书", "其他"]
FORMS = ["文章", "回答", "想法", "短内容"]
STATUS_LIST = ["待发布", "已发布", "已归档"]
STATUS_COLOR = {"待发布": WARNING, "已发布": SUCCESS, "已归档": NEUTRAL}
FORM_COLOR = {"文章": INFO, "回答": PRIMARY, "想法": NEUTRAL, "短内容": SUCCESS}

# 内容系列（8 篇）—— 用于系列进度面板（与内容发布目录一致）
SERIES = [
    "四场不同的仗（总纲）",
    "争议为什么总在重复（三条结构线）",
    "日本：同人的隐形引擎",
    "美国：内容创作者才是运营接口",
    "韩国：48 小时能集结",
    "最坏场景：四市场共振",
    "数据复盘：4.x 版本节奏",
    "方法论：一个玩家怎么做完研究",
]


class ContentMixin:
    """由 App 混入，提供内容页。"""

    def show_content(self):
        self.clear_main()
        self._build_content()

    # ═══════════════════════════════════════════════════════
    def _build_content(self):
        body, _page = self.page_scaffold(
            "content", "内容",
            "内容运营工作台 · 发布追踪 · 形式实验对比",
            icon="rocket", refresh=self._build_content)

        posts = query("SELECT * FROM content_posts "
                      "ORDER BY COALESCE(publish_date,'9999-12-31') DESC, id DESC")

        # ── KPI 行 ──
        published = [p for p in posts if p["status"] == "已发布"]
        total_views = sum((p["views"] or 0) for p in published)
        best = max(published, key=lambda p: p["views"] or 0, default=None)
        pending = [p for p in posts if p["status"] == "待发布"]

        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x")
        for k in range(4):
            grid.grid_columnconfigure(k, weight=1, uniform="kpi")
        rel = "无"
        if best and best["views"]:
            short = best["title"][:8] + "…" if len(best["title"]) > 9 else best["title"]
            rel = f"{short}（{best['views']}）"
        kpis = [
            ("已发布", str(len(published)), f"共 {len(posts)} 条记录"),
            ("累计浏览", str(total_views), "全平台合计"),
            ("最佳单篇", str(best["views"]) if best and best["views"] else "—", rel),
            ("库存待发", str(len(pending)), "成稿待发布"),
        ]
        for k, (lab, val, delta) in enumerate(kpis):
            C.StatCard(grid, lab, val, delta, None).grid(
                row=0, column=k, sticky="nsew",
                padx=(0 if k == 0 else SP_SM, 0))

        # ── 两列：系列进度 · 形式对比 ──
        two = ctk.CTkFrame(body, fg_color="transparent")
        two.pack(fill="x", pady=(SP_MD, 0))
        two.grid_columnconfigure(0, weight=1, uniform="col")
        two.grid_columnconfigure(1, weight=1, uniform="col")

        # 左：系列进度
        s_card = C.Card(two)
        s_card.grid(row=0, column=0, sticky="new", padx=(0, SP_SM))
        s_head = ctk.CTkFrame(s_card.body, fg_color="transparent", height=1)
        s_head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(s_head, "内容系列 · 8 篇进度",
                       icon="list").pack(side="left")

        by_series = {p["series_no"]: p for p in posts if p["series_no"]}
        s_wrap = ctk.CTkFrame(s_card.body, fg_color="transparent")
        s_wrap.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
        for i, name in enumerate(SERIES, 1):
            p = by_series.get(i)
            status = p["status"] if p else "待写"
            color = STATUS_COLOR.get(status, TEXT_TERTIARY)
            row = ctk.CTkFrame(s_wrap, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{i}.", width=20, font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=name, font=font(SIZE_TINY),
                         text_color=TEXT_SECONDARY, anchor="w").pack(
                side="left", fill="x", expand=True)
            if p and p["views"]:
                ctk.CTkLabel(row, text=str(p["views"]), font=font(SIZE_TINY),
                             text_color=TEXT_TERTIARY).pack(side="left",
                                                            padx=(0, SP_XS))
            C.Badge(row, status, color).pack(side="left")

        # 右：形式对比
        f_card = C.Card(two)
        f_card.grid(row=0, column=1, sticky="new", padx=(SP_SM, 0))
        f_head = ctk.CTkFrame(f_card.body, fg_color="transparent", height=1)
        f_head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(f_head, "形式实验对比 · 平均浏览",
                       icon="chart").pack(side="left")

        # 按形式聚合（只看已发布且有浏览数的）
        agg = {}
        for p in published:
            if p["views"]:
                agg.setdefault(p["form"], []).append(p["views"])
        items = [{"label": f"{f}（{len(v)}）", "value": sum(v) / len(v)}
                 for f, v in sorted(agg.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))]
        if len(items) >= 1:
            chart = charts.BarChart(f_card.body, height=max(110, 34 * len(items) + 20),
                                    horizontal=True)
            chart.pack(fill="x", padx=SP_SM, pady=(0, SP_XS))
            chart.set_data({"items": items, "color": PRIMARY})
            ctk.CTkLabel(f_card.body,
                         text="同一个系列、不同形式发在不同平台——这组对比就是真实的分发实验。",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                         anchor="w").pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
        else:
            C.EmptyState(f_card.body, "还没有「已发布」的数据", "chart",
                         "录入发布数据后，这里自动生成形式对比",
                         height=150).pack(fill="x")

        # ── 内容作品库 ──
        t_card = C.Card(body)
        t_card.pack(fill="x", pady=(SP_MD, 0))
        t_head = ctk.CTkFrame(t_card.body, fg_color="transparent", height=1)
        t_head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(t_head, "内容作品库", icon="doc").pack(side="left")
        C.PrimaryButton(t_head, "+ 添加内容", self._edit_post,
                        icon="plus", width=110, height=30).pack(side="right")

        if not posts:
            C.EmptyState(t_card.body, "还没有内容记录", "rocket",
                         "点右上「+ 添加内容」，把已发/库存的内容录进来",
                         height=140).pack(fill="x", pady=(0, SP_MD))
        else:
            # 表头
            head = ctk.CTkFrame(t_card.body, fg_color="transparent", height=1)
            head.pack(fill="x", padx=SP_LG)
            for txt, w in [("平台", 52), ("形式", 48), ("标题", 0), ("日期", 76),
                           ("浏览", 48), ("互动", 56), ("状态", 64), ("", 50)]:
                lab = ctk.CTkLabel(head, text=txt, font=font(SIZE_TINY),
                                   text_color=TEXT_TERTIARY, width=w,
                                   anchor="w" if not w else "center")
                lab.pack(side="left", padx=(0, SP_XS),
                         fill="x", expand=(w == 0))
            C.Divider(t_card.body).pack(fill="x", padx=SP_LG, pady=SP_XS)

            wrap = ctk.CTkFrame(t_card.body, fg_color="transparent")
            wrap.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
            for p in posts:
                row = ctk.CTkFrame(wrap, fg_color="transparent")
                row.pack(fill="x", pady=3)

                def cell(text, width, color=TEXT_BODY, bold=False, expand=False):
                    ctk.CTkLabel(row, text=text, width=width, anchor="w" if expand else "center",
                                 font=font(SIZE_TINY, bold=bold), text_color=color).pack(
                        side="left", padx=(0, SP_XS), fill="x", expand=expand)

                cell(p["platform"], 52, TEXT_SECONDARY)
                cell(p["form"], 48, FORM_COLOR.get(p["form"], TEXT_SECONDARY))
                title = p["title"]
                if len(title) > 34:
                    title = title[:33] + "…"
                cell(title, 0, TEXT_PRIMARY, expand=True)
                cell(p["publish_date"] or "—", 76, TEXT_TERTIARY)
                cell(str(p["views"]) if p["views"] else "—", 48,
                     TEXT_PRIMARY if p["views"] else TEXT_TERTIARY, bold=True)
                inter = (p["likes"] or 0) + (p["comments"] or 0)
                cell(str(inter) if inter else "—", 56,
                     TEXT_SECONDARY if inter else TEXT_TERTIARY)
                C.Badge(row, p["status"],
                        STATUS_COLOR.get(p["status"], TEXT_TERTIARY)).pack(side="left")
                C.GhostButton(row, "更新", lambda x=p: self._edit_post(x),
                              width=48, height=24).pack(side="left", padx=(SP_XS, 0))

            if any(p["review"] for p in posts):
                rv = [p for p in posts if p["review"]]
                ctk.CTkLabel(t_card.body,
                             text="最近复盘：" + rv[0]["review"][:60],
                             font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                             anchor="w").pack(fill="x", padx=SP_LG, pady=(0, SP_MD))

        ctk.CTkLabel(body,
                     text="维护：本页记录自己的内容运营数据——发布、数据、复盘，一个都不落",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                     anchor="w").pack(fill="x", pady=(SP_MD, 0))

    # ── 添加 / 更新弹窗 ────────────────────────────────────
    def _edit_post(self, post=None):
        editing = post is not None
        dlg = ctk.CTkToplevel(self)
        dlg.title("更新数据" if editing else "添加内容")
        dlg.transient(self)
        dlg.configure(fg_color=BG_CARD)
        dlg.resizable(False, False)
        self._center(dlg, 460, 520 if editing else 400)

        head = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_XL, pady=(SP_XL, SP_MD))
        ctk.CTkLabel(head, text="更新数据" if editing else "添加内容",
                     font=font(SIZE_H2, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left")

        form = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        form.pack(fill="x", padx=SP_XL)

        f_plat = C.Field(form, "平台", kind="menu", values=PLATFORMS,
                         width=210, label_width=66,
                         default=post["platform"] if editing else PLATFORMS[0])
        f_plat.pack(fill="x", pady=(0, SP_SM))
        f_form = C.Field(form, "形式", kind="menu", values=FORMS,
                         width=210, label_width=66,
                         default=post["form"] if editing else FORMS[0])
        f_form.pack(fill="x", pady=(0, SP_SM))
        f_title = C.Field(form, "标题", placeholder="内容标题",
                          width=210, label_width=66,
                          default=post["title"] if editing else None)
        f_title.pack(fill="x", pady=(0, SP_SM))
        f_series = C.Field(form, "系列篇号", placeholder="选填，1-8",
                           width=210, label_width=66,
                           default=str(post["series_no"]) if editing and post["series_no"] else None)
        f_series.pack(fill="x", pady=(0, SP_SM))
        f_status = C.Field(form, "状态", kind="menu", values=STATUS_LIST,
                           width=210, label_width=66,
                           default=post["status"] if editing else "待发布")
        f_status.pack(fill="x", pady=(0, SP_SM))
        f_date = C.Field(form, "发布日期", placeholder="YYYY-MM-DD",
                         width=210, label_width=66,
                         default=(post["publish_date"] or "") if editing else date_str())
        f_date.pack(fill="x", pady=(0, SP_SM))
        f_views = C.Field(form, "浏览", placeholder="0", width=210, label_width=66,
                          default=str(post["views"] or "") if editing else None)
        f_views.pack(fill="x", pady=(0, SP_SM))
        f_likes = C.Field(form, "赞同/点赞", placeholder="0", width=210, label_width=66,
                          default=str(post["likes"] or "") if editing else None)
        f_likes.pack(fill="x", pady=(0, SP_SM))
        f_cmt = C.Field(form, "评论", placeholder="0", width=210, label_width=66,
                        default=str(post["comments"] or "") if editing else None)
        f_cmt.pack(fill="x", pady=(0, SP_SM))
        f_review = C.Field(form, "复盘", placeholder="一句话复盘（选填）",
                           width=210, label_width=66,
                           default=post["review"] if editing else None)
        f_review.pack(fill="x", pady=(0, SP_SM))

        hint = ctk.CTkLabel(dlg, text="", font=font(SIZE_TINY), text_color=DANGER)

        def to_int(s, default=0):
            s = (s or "").strip()
            return int(s) if s.isdigit() else default

        def submit():
            title = f_title.get().strip()
            if not title:
                hint.configure(text="请填写标题")
                hint.pack(pady=(SP_SM, 0))
                return
            date = f_date.get().strip()
            if date and not valid_date(date):
                hint.configure(text="日期格式不对，需要 YYYY-MM-DD")
                hint.pack(pady=(SP_SM, 0))
                return
            series = f_series.get().strip()
            series_no = int(series) if series.isdigit() else None
            vals = (f_plat.get(), f_form.get(), title, series_no,
                    f_status.get(), date or None,
                    to_int(f_views.get()), to_int(f_likes.get()),
                    to_int(f_cmt.get()), f_review.get().strip())
            try:
                if editing:
                    execute(
                        "UPDATE content_posts SET platform=?, form=?, title=?, "
                        "series_no=?, status=?, publish_date=?, views=?, likes=?, "
                        "comments=?, review=?, update_time=datetime('now','localtime') "
                        "WHERE id=?", vals + (post["id"],))
                    self.log("更新内容数据", f"{title}（浏览 {vals[6]}）")
                    self.toast("已更新：" + title)
                else:
                    execute(
                        "INSERT OR REPLACE INTO content_posts "
                        "(platform, form, title, series_no, status, publish_date, "
                        "views, likes, comments, review) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        vals)
                    self.log("添加内容", f"{vals[0]}·{vals[1]} {title}")
                    self.toast("已添加：" + title)
            except Exception as e:
                hint.configure(text=f"保存失败：{e}")
                hint.pack(pady=(SP_SM, 0))
                return
            dlg.destroy()
            self.remount("content")

        btns = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        btns.pack(fill="x", padx=SP_XL, pady=(SP_MD, SP_XL))

        def do_delete():
            try:
                execute("DELETE FROM content_posts WHERE id=?", (post["id"],))
                self.log("删除内容", post["title"])
                self.toast("已删除：" + post["title"])
            except Exception as e:
                self.toast(f"删除失败：{e}", WARNING)
            dlg.destroy()
            self.remount("content")

        C.PrimaryButton(btns, "保存", submit, width=90, height=34).pack(side="right")
        if editing:
            C.GhostButton(btns, "删除", do_delete, width=70, height=34).pack(
                side="left")
        C.GhostButton(btns, "取消", dlg.destroy, width=70, height=34).pack(
            side="right", padx=(0, SP_SM))

        dlg.after(120, dlg.focus_force)
