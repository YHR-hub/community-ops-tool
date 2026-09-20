"""
版本页 —— 看板 / 时间线 / 版本详情
====================================

信息架构上的核心决定：
  旧版把「任务清单」「排期」「预算」「风险」分散在「版本管理」的 Tab
  和几个独立页面里，同一件事有两个入口 —— 这就是「功能板块模糊」。
  新版统一收进「版本详情抽屉」：选中一个版本，看到它的全部上下文。

顺带修掉的旧 bug：
  · 旧 versions.py 用了 Canvas 却没 import → 版本带「使用率」风险项时崩
  · bar_width = 680 硬编码 → 换分辨率就崩
  · ver_labels.index() 反查版本名 → 重名或缺失时 IndexError
  · 版本对比时格式化参数错位 → 显示成 %s 或数字串位
"""

import tkinter as tk
from datetime import datetime, timedelta

import customtkinter as ctk

import theme
from theme import (
    BG_APP, BG_CARD, BG_ELEVATED, BG_BORDER, BG_CONTENT,
    PRIMARY, PRIMARY_DIM, PRIMARY_HOVER, DANGER, SUCCESS, WARNING, INFO, AI, NEUTRAL,
    TEXT_PRIMARY, TEXT_BODY, TEXT_SECONDARY, TEXT_TERTIARY,
    font, num_font, SIZE_H1, SIZE_H2, SIZE_H3, SIZE_BODY, SIZE_SMALL, SIZE_TINY,
    SP_XS, SP_SM, SP_MD, SP_LG, SP_XL, RADIUS_MD, RADIUS_LG,
)
import icons
import components as C
import charts
import db
from db import (
    GAMES, query, execute, get_versions, get_version_by_id,
    previous_version, version_series,
    task_progress, task_progress_map, open_risks, budget_summary,
    safe_int, safe_float, valid_date,
    date_str, days_ago, parse_date, top_characters,
)

# 版本状态的中文展示顺序
STATUS_ORDER = ["planning", "preparing", "live", "review", "closed"]

# 新建版本时可选的标准任务模板（按阶段分组）
DEFAULT_TEMPLATE = [
    ("内容制作", ["版本PV发布", "角色演示视频", "技能展示帖", "预约H5上线"]),
    ("社媒预热", ["微博预热话题", "B站UP主投放", "米游社置顶预告"]),
    ("活动配置", ["活动规则确认", "奖励数值配置", "公告文案审核"]),
    ("上线保障", ["数据埋点检查", "客服话术同步", "舆情监控就位"]),
    ("版本复盘", ["核心指标对比", "社区反馈汇总", "复盘会议"]),
]

RISK_PROB = ["high", "medium", "low"]
RISK_IMP = ["high", "medium", "low"]
RISK_PROB_LABEL = {"high": "高概率", "medium": "中概率", "low": "低概率"}
RISK_IMP_LABEL = {"high": "高影响", "medium": "中影响", "low": "低影响"}


class VersionsMixin:
    """由 App 混入，提供版本页。"""

    def show_versions(self):
        self.clear_main()
        if getattr(self, "_version_tab", None) not in ("board", "timeline"):
            self._version_tab = "board"
        if not hasattr(self, "_selected_version_id"):
            self._selected_version_id = None
        self._build_versions()

    # ═══════════════════════════════════════════════════════
    def _build_versions(self):
        # Tab 状态兜底：任何入口（show_view / remount / 快捷键）进来都保证有值
        if getattr(self, "_version_tab", None) not in ("board", "timeline"):
            self._version_tab = "board"

        body, _page = self.page_scaffold(
            "versions", "版本", "管理版本全生命周期：任务、排期、预算、风险",
            icon="calendar", refresh=self._build_versions)

        bar = ctk.CTkFrame(body, fg_color="transparent", height=1)
        bar.pack(fill="x", pady=(0, SP_MD))
        self._build_version_toolbar(bar)

        if self._version_tab == "board":
            self._build_version_board(body)
        else:
            self._build_version_timeline(body)

    def _build_version_toolbar(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        card = C.Card(parent)
        card.pack(fill="x")
        row = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        row.pack(fill="x", padx=SP_LG, pady=SP_MD)

        # 分段控件：看板 / 时间线
        seg = ctk.CTkFrame(row, fg_color=BG_APP, corner_radius=RADIUS_MD)
        seg.pack(side="left")
        for key, label in (("board", "看板"), ("timeline", "时间线")):
            active = (key == self._version_tab)
            ctk.CTkButton(
                seg, text=label, command=lambda k=key: self._switch_tab(k),
                fg_color=BG_ELEVATED if active else "transparent",
                hover_color=BG_ELEVATED,
                text_color=TEXT_PRIMARY if active else TEXT_SECONDARY,
                font=font(SIZE_SMALL), corner_radius=RADIUS_MD - 2,
                height=28, width=76).pack(side="left", padx=2, pady=2)

        self._vfilter = C.Field(row, "", kind="menu", values=["全部"] + GAMES,
                                width=112, label_width=0, default="全部")
        self._vfilter.pack(side="left", padx=(SP_MD, 0))
        self._vfilter.widget.configure(command=lambda _v: self.remount("versions"))

        C.PrimaryButton(row, "新建版本", self._open_new_version,
                        icon="plus", width=112, height=30).pack(side="right")

    def _switch_tab(self, key):
        self._version_tab = key
        self.remount("versions")

    # ═══════════════════════════════════════════════════════
    #  看板视图
    # ═══════════════════════════════════════════════════════
    def _build_version_board(self, parent):
        game = self._vfilter.get() if hasattr(self, "_vfilter") else "全部"
        versions = get_versions(game if game != "全部" else None)
        progress = task_progress_map()

        if not versions:
            card = C.Card(parent)
            card.pack(fill="x")
            C.EmptyState(card.body, "还没有任何版本", "calendar",
                         "版本是一切的主线：任务、预算、风险都挂在它下面",
                         "新建版本", self._open_new_version).pack(fill="x")
            return

        # 按状态分组呈现 —— 状态即阶段，运营一眼看出堵在哪
        grouped = {s: [] for s in STATUS_ORDER}
        for v in versions:
            grouped.setdefault(v["status"] or "planning", []).append(v)

        for status in STATUS_ORDER:
            items = grouped.get(status) or []
            if not items:
                continue
            self._build_status_group(parent, status, items, progress)

    def _build_status_group(self, parent, status, items, progress):
        label, color = theme.VERSION_STATUS.get(status, (status, NEUTRAL))

        head = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        head.pack(fill="x", pady=(SP_SM, SP_SM))
        dot = ctk.CTkFrame(head, fg_color=color, width=7, height=7,
                           corner_radius=4)
        dot.pack(side="left", pady=5)
        dot.pack_propagate(False)
        ctk.CTkLabel(head, text=label, font=font(SIZE_H3, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(7, 0))
        ctk.CTkLabel(head, text=f"{len(items)} 个版本",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="left", padx=(SP_SM, 0))

        grid = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        grid.pack(fill="x", pady=(0, SP_SM))
        cols = 2
        for i in range(cols):
            grid.grid_columnconfigure(i, weight=1, uniform="vcard")
        # 行不拉伸：卡片按内容高度排布，避免同一行里矮卡被撑出大片空白
        for r in range((len(items) + cols - 1) // cols):
            grid.grid_rowconfigure(r, weight=0)

        for i, v in enumerate(items):
            cell = ctk.CTkFrame(grid, fg_color="transparent", height=1)
            cell.grid(row=i // cols, column=i % cols, sticky="new",
                      padx=(0 if i % cols == 0 else SP_SM, 0),
                      pady=(0, SP_SM))
            self._build_version_card(cell, v, progress.get(v["id"], (0, 0)),
                                     color)

    def _build_version_card(self, parent, v, prog, status_color):
        """
        版本卡。
        选中态用强调色边框 + 左色条标出 —— 一眼看到当前在看哪个版本。
        """
        selected = (v["id"] == self._selected_version_id)
        accent = status_color if selected else None

        card = C.Card(parent, accent=accent)
        card.pack(fill="x")

        inner = C.vbox(card.body)
        inner.pack(fill="x", padx=SP_LG, pady=SP_MD)

        top = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        top.pack(fill="x")
        ctk.CTkLabel(top, text=v["version"], font=font(SIZE_H2, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(top, text=v["game"], font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY).pack(side="left", padx=(SP_SM, 0))

        label, color = theme.VERSION_STATUS.get(v["status"], (v["status"], NEUTRAL))
        C.Badge(top, label, color).pack(side="right")

        # 起止日期 + 进度天数
        start = parse_date(v["start_date"])
        end = parse_date(v["end_date"], start + timedelta(days=42))
        span = max(1, (end - start).days)
        elapsed = (datetime.now() - start).days
        if 0 <= elapsed <= span:
            days_txt = f"第 {elapsed} / {span} 天"
        elif elapsed > span:
            days_txt = f"已结束 {elapsed - span} 天"
        else:
            days_txt = f"还有 {abs(elapsed)} 天开始"

        ctk.CTkLabel(inner,
                     text=f"{v['start_date']} → {v['end_date'] or '—'} · {days_txt}",
                     font=font(SIZE_TINY), text_color=TEXT_SECONDARY,
                     anchor="w").pack(anchor="w", pady=(SP_XS, SP_SM))

        # 进度条
        total, done = prog
        pct = int(done / total * 100) if total else 0
        prow = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        prow.pack(fill="x")
        ctk.CTkLabel(prow, text="任务进度", font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY).pack(side="left")
        ctk.CTkLabel(prow,
                     text=f"{done}/{total} · {pct}%" if total else "未导入清单",
                     font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY).pack(side="right")

        bar = charts.ProgressBar(inner, height=5,
                                 color=SUCCESS if (total and pct == 100) else PRIMARY)
        bar.pack(fill="x", pady=(3, SP_SM))
        bar.after(40, lambda b=bar, p=pct: b.set(p) if b.winfo_exists() else None)

        # 风险 / 预算摘要。
        # 这个帧必须用 C.hbox（初始高度 1px）：当版本既没风险也没预算
        # （比如刚建、还没导入任务清单的版本）时它是空的，
        # 而空的 CTkFrame 会保留 250px 默认高度，直接把卡片撑高一倍。
        risks = open_risks(v["id"])
        planned, actual = budget_summary(v["id"])
        high = [r for r in risks if r["probability"] == "high"]

        foot = C.hbox(inner)
        foot.pack(fill="x")

        if risks:
            color_r = DANGER if high else WARNING
            icons.draw_icon(foot, "warn", 11, color_r).pack(side="left", pady=2)
            ctk.CTkLabel(foot,
                         text=f"{len(risks)} 项风险"
                              + (f"（{len(high)} 高概率）" if high else ""),
                         font=font(SIZE_TINY), text_color=color_r).pack(
                side="left", padx=(4, SP_MD))

        if planned:
            over = actual > planned
            ctk.CTkLabel(foot,
                         text=f"预算 {actual/10000:.0f}/{planned/10000:.0f} 万",
                         font=font(SIZE_TINY),
                         text_color=DANGER if over else TEXT_TERTIARY).pack(
                side="left")

        C.GhostButton(inner, "查看详情",
                      lambda vid=v["id"]: self._open_version_detail(vid),
                      width=88, height=28).pack(side="right", pady=(SP_SM, 0))

    # ═══════════════════════════════════════════════════════
    #  时间线视图
    # ═══════════════════════════════════════════════════════
    def _build_version_timeline(self, parent):
        game = self._vfilter.get() if hasattr(self, "_vfilter") else "全部"
        versions = get_versions(game if game != "全部" else None)

        card = C.Card(parent)
        card.pack(fill="x", pady=(0, SP_MD))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "版本排期", icon="calendar").pack(side="left")

        if not versions:
            C.EmptyState(card.body, "还没有版本可以排期", "calendar",
                         "新建版本后会自动出现在这里").pack(fill="x")
            return

        rows = []
        dmin = dmax = None
        for v in versions:
            start = parse_date(v["start_date"])
            end = parse_date(v["end_date"], start + timedelta(days=42))
            dmin = start if dmin is None else min(dmin, start)
            dmax = end if dmax is None else max(dmax, end)
            risks = open_risks(v["id"])
            rows.append({
                "label": f"{v['game'][:2]} {v['version']}",
                "start": start, "end": end,
                "color": theme.GAME_ACCENT.get(v["game"], PRIMARY),
                "badge": bool([r for r in risks if r["probability"] == "high"]),
            })

        # 留一点左右边距，条形不贴边
        dmin -= timedelta(days=3)
        dmax += timedelta(days=3)

        chart = charts.GanttChart(card.body, height=max(150, 32 * len(rows) + 56))
        chart.pack(fill="x", padx=SP_SM, pady=(0, SP_SM))
        chart.set_data({"rows": rows, "min": dmin, "max": dmax})

        legend = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        legend.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
        for g, color in theme.GAME_ACCENT.items():
            if not any(r["label"].startswith(g[:2]) for r in rows):
                continue
            item = ctk.CTkFrame(legend, fg_color="transparent", height=1)
            item.pack(side="left", padx=(0, SP_MD))
            d = ctk.CTkFrame(item, fg_color=color, width=8, height=8,
                             corner_radius=4)
            d.pack(side="left", pady=3)
            d.pack_propagate(False)
            ctk.CTkLabel(item, text=g, font=font(SIZE_TINY),
                         text_color=TEXT_SECONDARY).pack(side="left", padx=(5, 0))

        ctk.CTkLabel(legend, text="红点 = 存在高概率风险", font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY).pack(side="right")

        self._build_timeline_events(parent)

    def _build_timeline_events(self, parent):
        card = C.Card(parent)
        card.pack(fill="x")

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "活动排期", icon="bolt").pack(side="left")

        events = query("SELECT * FROM events ORDER BY start_date DESC LIMIT 12")
        if not events:
            C.EmptyState(card.body, "还没有活动", "bolt",
                         "在版本详情里添加，或导入活动数据").pack(fill="x")
            return

        today = date_str()
        for e in events:
            row = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
            row.pack(fill="x", padx=SP_LG, pady=(0, SP_SM))

            color = theme.GAME_ACCENT.get(e["game"], PRIMARY)
            # 色条必须显式给 height：pack_propagate(False) 会禁用尺寸传播，
            # 没有 height 时它保留 250px 默认值，再把整行撑到 250px。
            bar = ctk.CTkFrame(row, fg_color=color, width=3, height=34,
                               corner_radius=2)
            bar.pack(side="left", fill="y", padx=(0, SP_SM))
            bar.pack_propagate(False)

            mid = ctk.CTkFrame(row, fg_color="transparent", height=1)
            mid.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(mid, text=e["name"], font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, anchor="w").pack(anchor="w")
            ctk.CTkLabel(mid,
                         text=f"{e['game']} · {e['type']} · "
                              f"{e['start_date']} → {e['end_date']}",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                         anchor="w").pack(anchor="w")

            if e["start_date"] <= today <= e["end_date"]:
                C.Badge(row, "进行中", SUCCESS).pack(side="right")
            elif e["start_date"] > today:
                C.Badge(row, "未开始", INFO).pack(side="right")
            else:
                C.Badge(row, "已结束", NEUTRAL).pack(side="right")

    # ═══════════════════════════════════════════════════════
    #  新建版本
    # ═══════════════════════════════════════════════════════
    def _open_new_version(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("新建版本")
        dlg.transient(self)
        dlg.configure(fg_color=BG_CARD)
        dlg.resizable(False, False)
        self._center(dlg, 440, 408)

        head = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_XL, pady=(SP_XL, SP_MD))
        icons.draw_icon(head, "calendar", 17, PRIMARY).pack(side="left", pady=2)
        ctk.CTkLabel(head, text="新建版本", font=font(SIZE_H2, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(7, 0))

        form = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        form.pack(fill="x", padx=SP_XL)

        f_game = C.Field(form, "游戏", kind="menu", values=GAMES, width=210,
                         label_width=72, default=GAMES[1])
        f_game.pack(fill="x", pady=(0, SP_SM))
        f_ver = C.Field(form, "版本号", placeholder="如 4.5", width=210,
                        label_width=72)
        f_ver.pack(fill="x", pady=(0, SP_SM))
        f_start = C.Field(form, "开始日期", placeholder="YYYY-MM-DD",
                          width=210, label_width=72, default=date_str())
        f_start.pack(fill="x", pady=(0, SP_SM))
        f_end = C.Field(form, "结束日期", placeholder="留空默认 42 天后",
                        width=210, label_width=72,
                        default=date_str(datetime.now() + timedelta(days=42)))
        f_end.pack(fill="x", pady=(0, SP_SM))
        f_status = C.Field(form, "状态", kind="menu",
                           values=[theme.VERSION_STATUS[s][0] for s in STATUS_ORDER],
                           width=210, label_width=72, default="准备中")
        f_status.pack(fill="x", pady=(0, SP_SM))
        f_hl = C.Field(form, "版本亮点", placeholder="选填，如「新角色上线」",
                       width=210, label_width=72)
        f_hl.pack(fill="x", pady=(0, SP_SM))

        opt = ctk.CTkCheckBox(
            form, text="同时导入标准任务清单（5 阶段 17 项）",
            font=font(SIZE_SMALL), text_color=TEXT_BODY,
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
            border_color=BG_BORDER, checkmark_color="#FFFFFF")
        opt.pack(anchor="w", pady=(SP_SM, 0))
        opt.select()

        hint = ctk.CTkLabel(dlg, text="", font=font(SIZE_TINY), text_color=DANGER)

        def submit():
            game = f_game.get()
            ver = f_ver.get().strip()
            start = f_start.get().strip()
            end = f_end.get().strip()

            if not ver:
                hint.configure(text="请填写版本号")
                hint.pack(pady=(SP_SM, 0))
                return
            if not valid_date(start):
                hint.configure(text="开始日期格式不对，需要 YYYY-MM-DD")
                hint.pack(pady=(SP_SM, 0))
                return
            if end and not valid_date(end):
                hint.configure(text="结束日期格式不对，需要 YYYY-MM-DD")
                hint.pack(pady=(SP_SM, 0))
                return
            if end and end < start:
                hint.configure(text="结束日期不能早于开始日期")
                hint.pack(pady=(SP_SM, 0))
                return

            dup = query("SELECT id FROM versions WHERE game=? AND version=?",
                        (game, ver), one=True)
            if dup:
                hint.configure(text=f"{game} {ver} 已存在，请换一个版本号")
                hint.pack(pady=(SP_SM, 0))
                return

            status = next((k for k, vv in theme.VERSION_STATUS.items()
                           if vv[0] == f_status.get()), "planning")
            try:
                vid = execute(
                    "INSERT INTO versions "
                    "(game,version,start_date,end_date,status,highlights,notes) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (game, ver, start,
                     end or date_str(datetime.now() + timedelta(days=42)),
                     status, f_hl.get().strip(), ""))
            except Exception as e:
                hint.configure(text=f"保存失败：{e}")
                hint.pack(pady=(SP_SM, 0))
                return

            n = self._apply_template(vid) if opt.get() else 0

            self.log("新建版本", f"{game} {ver}")
            self.toast(f"已创建 {game} {ver}"
                       + (f"，导入 {n} 项任务" if n else ""))
            self._selected_version_id = vid
            dlg.destroy()
            self.remount("versions")

        btns = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        btns.pack(fill="x", padx=SP_XL, pady=SP_LG)
        C.PrimaryButton(btns, "创建", submit, icon="check",
                        width=110, height=32).pack(side="right")
        C.GhostButton(btns, "取消", dlg.destroy, width=88, height=32).pack(
            side="right", padx=(0, SP_SM))

        try:
            dlg.grab_set()
        except Exception:
            pass

    def _apply_template(self, vid, template=None):
        """按阶段模板批量插入任务。"""
        tpl = template or DEFAULT_TEMPLATE
        n = 0
        today = datetime.now()
        with db.get_conn() as c:
            for cat, tasks in tpl:
                for i, t in enumerate(tasks):
                    c.execute(
                        "INSERT INTO checklists "
                        "(version_id,task,category,assignee,deadline,status) "
                        "VALUES (?,?,?,?,?,?)",
                        (vid, t, cat, "", date_str(today + timedelta(days=i * 3)),
                         "pending"))
                    n += 1
        return n

    # ═══════════════════════════════════════════════════════
    #  版本详情抽屉
    # ═══════════════════════════════════════════════════════
    def _open_version_detail(self, vid):
        v = get_version_by_id(vid)
        if not v:
            self.toast("版本不存在，可能已被删除", DANGER)
            return

        self._selected_version_id = vid

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"{v['game']} {v['version']} · 详情")
        dlg.transient(self)
        dlg.configure(fg_color=BG_APP)
        w, h = 780, 660
        self._center(dlg, w, h)

        label, color = theme.VERSION_STATUS.get(v["status"], (v["status"], NEUTRAL))

        # ── 头部 ──
        head = ctk.CTkFrame(dlg, fg_color=BG_CARD, corner_radius=0)
        head.pack(fill="x")
        top = ctk.CTkFrame(head, fg_color="transparent", height=1)
        top.pack(fill="x", padx=SP_XL, pady=(SP_LG, SP_SM))

        left = ctk.CTkFrame(top, fg_color="transparent", height=1)
        left.pack(side="left")
        ctk.CTkLabel(left, text=f"{v['game']} {v['version']}",
                     font=font(SIZE_H1, bold=True),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(left, text=f"{v['start_date']} → {v['end_date'] or '—'}",
                     font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(top, fg_color="transparent", height=1)
        right.pack(side="right")
        C.Badge(right, label, color).pack(side="right")
        C.IconButton(right, "close", dlg.destroy, size=28).pack(
            side="right", padx=(0, SP_SM))

        if v["highlights"]:
            ctk.CTkLabel(head, text=v["highlights"], font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, anchor="w",
                         wraplength=w - 60, justify="left").pack(
                anchor="w", padx=SP_XL, pady=(0, SP_LG))

        # ── Tab 区 ──
        tabbar = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        tabbar.pack(fill="x", padx=SP_XL, pady=(SP_MD, 0))

        host = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        host.pack(fill="both", expand=True, padx=SP_XL, pady=SP_MD)

        TABS = [("tasks", "任务清单"), ("risks", "风险"),
                ("budget", "预算"), ("usage", "角色使用率")]

        btns = {}
        state = {"tab": "tasks"}

        def render():
            for w_ in host.winfo_children():
                w_.destroy()
            for k, b in btns.items():
                active = (k == state["tab"])
                b.configure(fg_color=PRIMARY_DIM if active else "transparent",
                            text_color=TEXT_PRIMARY if active else TEXT_SECONDARY)
            {
                "tasks": self._detail_tasks,
                "risks": self._detail_risks,
                "budget": self._detail_budget,
                "usage": self._detail_usage,
            }[state["tab"]](host, v)

        for key, text in TABS:
            b = ctk.CTkButton(
                tabbar, text=text,
                command=lambda k=key: (state.update(tab=k), render()),
                fg_color="transparent", hover_color=BG_ELEVATED,
                text_color=TEXT_SECONDARY, font=font(SIZE_SMALL),
                corner_radius=RADIUS_MD, height=30, width=96)
            b.pack(side="left", padx=(0, SP_XS))
            btns[key] = b

        render()

        try:
            dlg.grab_set()
        except Exception:
            pass

    def _center(self, win, w, h):
        """把弹窗居中到主窗口，避免出现在屏幕角落。"""
        self.update_idletasks()
        x = max(0, self.winfo_rootx() + (self.winfo_width() - w) // 2)
        y = max(0, self.winfo_rooty() + (self.winfo_height() - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    # ── 详情 · 任务清单 ──
    def _detail_tasks(self, host, v):
        total, done = task_progress(v["id"])
        pct = int(done / total * 100) if total else 0

        top = ctk.CTkFrame(host, fg_color="transparent", height=1)
        top.pack(fill="x", pady=(0, SP_SM))
        counter = ctk.CTkLabel(top, text=f"整体完成度 {done}/{total} · {pct}%",
                               font=font(SIZE_SMALL), text_color=TEXT_BODY)
        counter.pack(side="left")
        C.GhostButton(top, "追加模板任务",
                      lambda: self._add_template_tasks(v["id"]),
                      icon="plus", width=136, height=28).pack(side="right")

        bar = charts.ProgressBar(host, height=6,
                                 color=SUCCESS if (total and pct == 100) else PRIMARY)
        bar.pack(fill="x", pady=(0, SP_MD))
        bar.after(40, lambda b=bar, p=pct: b.set(p) if b.winfo_exists() else None)

        box = ctk.CTkScrollableFrame(host, fg_color="transparent")
        box.pack(fill="both", expand=True)

        cats = query("SELECT DISTINCT category FROM checklists WHERE version_id=?",
                     (v["id"],))
        if not cats:
            C.EmptyState(box, "还没有任务", "list",
                         "可以一键导入标准任务模板").pack(fill="both", expand=True)
            return

        def on_change():
            """就地更新顶部进度，不重建整个弹窗。"""
            t, d = task_progress(v["id"])
            p = int(d / t * 100) if t else 0
            counter.configure(text=f"整体完成度 {d}/{t} · {p}%")
            if bar.winfo_exists():
                bar.set(p, SUCCESS if (t and d == t) else PRIMARY)

        for cat_row in cats:
            cat = cat_row["category"] or "常规"
            items = query("SELECT * FROM checklists WHERE version_id=? "
                          "AND category=? ORDER BY id", (v["id"], cat))
            d = sum(1 for i in items if i["status"] == "done")

            head = ctk.CTkFrame(box, fg_color="transparent", height=1)
            head.pack(fill="x", pady=(SP_SM, SP_XS))
            ctk.CTkLabel(head, text=cat, font=font(SIZE_SMALL, bold=True),
                         text_color=TEXT_PRIMARY).pack(side="left")
            ctk.CTkLabel(head, text=f"{d}/{len(items)}", font=font(SIZE_TINY),
                         text_color=SUCCESS if d == len(items) else TEXT_TERTIARY
                         ).pack(side="right")

            for it in items:
                self._task_row(box, it, on_change)

    def _task_row(self, parent, it, on_change):
        """
        单条任务：右侧状态标签可点击，循环切换 待开始 → 进行中 → 已完成。
        旧版用 Treeview 双击改状态，交互隐蔽；这里做成显式的可点按钮。
        """
        row = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=6)
        row.pack(fill="x", pady=2)

        inner = ctk.CTkFrame(row, fg_color="transparent", height=1)
        inner.pack(fill="x", padx=SP_MD, pady=SP_SM)

        status = it["status"] or "pending"
        overdue = bool(it["deadline"] and it["deadline"] < date_str()
                       and status != "done")

        icons.draw_icon(inner,
                        "check" if status == "done" else "clock", 12,
                        {"done": SUCCESS, "doing": WARNING}.get(
                            status, TEXT_TERTIARY)).pack(side="left", pady=2)

        mid = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        mid.pack(side="left", fill="x", expand=True, padx=SP_SM)
        task_label = ctk.CTkLabel(
            mid, text=it["task"], font=font(SIZE_SMALL),
            text_color=TEXT_TERTIARY if status == "done" else TEXT_BODY,
            anchor="w")
        task_label.pack(anchor="w")

        sub = []
        if it["assignee"]:
            sub.append(it["assignee"])
        if it["deadline"]:
            sub.append(("逾期 " if overdue else "") + it["deadline"])
        if sub:
            sub_label = ctk.CTkLabel(
                mid, text=" · ".join(sub), font=font(SIZE_TINY),
                text_color=DANGER if overdue else TEXT_TERTIARY, anchor="w")
            sub_label.pack(anchor="w")

        STYLE = {
            "pending": ("待开始", TEXT_TERTIARY),
            "doing": ("进行中", WARNING),
            "done": ("已完成", SUCCESS),
        }
        label, color = STYLE[status]
        badge = ctk.CTkButton(
            inner, text=label, width=62, height=24,
            font=font(SIZE_TINY), corner_radius=10,
            fg_color=C.blend(color, BG_CARD, 0.16),
            hover_color=BG_ELEVATED, text_color=color,
            border_width=1, border_color=color)
        badge.pack(side="right")

        def toggle():
            cur = badge.cget("text")
            nxt_key = {"待开始": "doing", "进行中": "done", "已完成": "pending"}[cur]
            try:
                execute("UPDATE checklists SET status=? WHERE id=?",
                        (nxt_key, it["id"]))
            except Exception as e:
                self.toast(f"更新失败：{e}", DANGER)
                return
            new_label, new_color = STYLE[nxt_key]
            badge.configure(text=new_label, text_color=new_color,
                            fg_color=C.blend(new_color, BG_CARD, 0.16),
                            border_color=new_color)
            task_label.configure(text_color=TEXT_TERTIARY
                                 if nxt_key == "done" else TEXT_BODY)
            self.log("更新任务", f"{it['task']} → {new_label}")
            on_change()

        badge.configure(command=toggle)

    def _add_template_tasks(self, vid):
        existing = {r["task"] for r in
                    query("SELECT task FROM checklists WHERE version_id=?", (vid,))}
        n = 0
        today = datetime.now()
        with db.get_conn() as c:
            for cat, tasks in DEFAULT_TEMPLATE:
                for i, t in enumerate(tasks):
                    if t in existing:
                        continue
                    c.execute(
                        "INSERT INTO checklists "
                        "(version_id,task,category,assignee,deadline,status) "
                        "VALUES (?,?,?,?,?,?)",
                        (vid, t, cat, "", date_str(today + timedelta(days=i * 3)),
                         "pending"))
                    n += 1
        if n:
            self.log("追加任务模板", f"{n} 项")
            self.toast(f"已追加 {n} 项任务")
        else:
            self.toast("标准任务已全部存在，无需追加", WARNING)
        self.remount("versions")

    # ── 详情 · 风险 ──
    def _detail_risks(self, host, v):
        top = ctk.CTkFrame(host, fg_color="transparent", height=1)
        top.pack(fill="x", pady=(0, SP_SM))
        ctk.CTkLabel(top, text="按概率排序，高概率项优先处理",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(side="left")
        C.PrimaryButton(top, "自动标记风险", lambda: self._auto_mark_risks(v),
                        icon="bolt", width=124, height=28).pack(side="right")
        C.GhostButton(top, "添加风险", lambda: self._add_risk(v["id"]),
                      icon="plus", width=96, height=28).pack(side="right",
                                                            padx=(0, SP_SM))

        box = ctk.CTkScrollableFrame(host, fg_color="transparent")
        box.pack(fill="both", expand=True)

        risks = open_risks(v["id"])
        if not risks:
            C.EmptyState(box, "还没有记录风险项", "shield",
                         "点击「自动标记风险」可以根据数据自动发现",
                         height=140).pack(fill="both", expand=True)
            return

        for r in risks:
            card = ctk.CTkFrame(box, fg_color=BG_CARD, corner_radius=6)
            card.pack(fill="x", pady=3)
            inner = ctk.CTkFrame(card, fg_color="transparent", height=1)
            inner.pack(fill="x", padx=SP_MD, pady=SP_SM)

            _prob_txt, prob_color = theme.RISK_LEVEL.get(r["probability"],
                                                         ("中", WARNING))
            bar = ctk.CTkFrame(inner, fg_color=prob_color, width=3, height=34,
                               corner_radius=2)
            bar.pack(side="left", fill="y", padx=(0, SP_SM))
            bar.pack_propagate(False)

            mid = ctk.CTkFrame(inner, fg_color="transparent", height=1)
            mid.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(mid, text=r["title"], font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, anchor="w",
                         wraplength=450, justify="left").pack(anchor="w")

            detail = (f"{RISK_PROB_LABEL.get(r['probability'], '')} · "
                      f"{RISK_IMP_LABEL.get(r['impact'], '')}")
            if r["owner"]:
                detail += f" · 负责人 {r['owner']}"
            ctk.CTkLabel(mid, text=detail, font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY, anchor="w").pack(anchor="w")

            if r["mitigation"]:
                ctk.CTkLabel(mid, text=f"应对：{r['mitigation']}",
                             font=font(SIZE_TINY), text_color=TEXT_SECONDARY,
                             anchor="w", wraplength=450,
                             justify="left").pack(anchor="w", pady=(2, 0))

            C.IconButton(inner, "trash",
                         lambda rid=r["id"]: self._delete_risk(rid),
                         size=24).pack(side="right")

    def _delete_risk(self, rid):
        try:
            execute("DELETE FROM risks WHERE id=?", (rid,))
        except Exception as e:
            self.toast(f"删除失败：{e}", DANGER)
            return
        self.toast("已删除风险项")
        self.remount("versions")

    def _add_risk(self, vid):
        dlg = ctk.CTkToplevel(self)
        dlg.title("添加风险")
        dlg.transient(self)
        dlg.configure(fg_color=BG_CARD)
        dlg.resizable(False, False)
        self._center(dlg, 470, 432)

        head = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_XL, pady=(SP_XL, SP_MD))
        icons.draw_icon(head, "shield", 16, PRIMARY).pack(side="left", pady=2)
        ctk.CTkLabel(head, text="添加风险", font=font(SIZE_H2, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(7, 0))

        form = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        form.pack(fill="x", padx=SP_XL)

        f_title = C.Field(form, "风险描述", placeholder="一句话说清风险是什么",
                          width=270, label_width=72)
        f_title.pack(fill="x", pady=(0, SP_SM))
        f_prob = C.Field(form, "概率", kind="menu",
                         values=[RISK_PROB_LABEL[k] for k in RISK_PROB],
                         width=270, label_width=72, default="中概率")
        f_prob.pack(fill="x", pady=(0, SP_SM))
        f_imp = C.Field(form, "影响", kind="menu",
                        values=[RISK_IMP_LABEL[k] for k in RISK_IMP],
                        width=270, label_width=72, default="中影响")
        f_imp.pack(fill="x", pady=(0, SP_SM))
        f_owner = C.Field(form, "负责人", placeholder="选填", width=270,
                          label_width=72)
        f_owner.pack(fill="x", pady=(0, SP_SM))
        f_mit = C.Field(form, "应对措施", placeholder="打算怎么降低概率",
                        width=270, label_width=72)
        f_mit.pack(fill="x", pady=(0, SP_SM))

        hint = ctk.CTkLabel(dlg, text="", font=font(SIZE_TINY), text_color=DANGER)

        def submit():
            title = f_title.get().strip()
            if not title:
                hint.configure(text="请填写风险描述")
                hint.pack(pady=(SP_SM, 0))
                return
            prob = next(k for k, lbl in RISK_PROB_LABEL.items() if lbl == f_prob.get())
            imp = next(k for k, lbl in RISK_IMP_LABEL.items() if lbl == f_imp.get())
            try:
                execute(
                    "INSERT INTO risks (version_id,title,probability,impact,"
                    "mitigation,contingency,owner,status) "
                    "VALUES (?,?,?,?,?,?,'open')",
                    (vid, title, prob, imp, f_mit.get().strip(), "",
                     f_owner.get().strip()))
            except Exception as e:
                hint.configure(text=f"保存失败：{e}")
                hint.pack(pady=(SP_SM, 0))
                return
            self.log("添加风险", title)
            self.toast("已添加风险项")
            dlg.destroy()
            self.remount("versions")

        btns = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        btns.pack(fill="x", padx=SP_XL, pady=SP_LG)
        C.PrimaryButton(btns, "添加", submit, width=100, height=32).pack(side="right")
        C.GhostButton(btns, "取消", dlg.destroy, width=88, height=32).pack(
            side="right", padx=(0, SP_SM))

        try:
            dlg.grab_set()
        except Exception:
            pass

    def _auto_mark_risks(self, v):
        """
        根据角色使用率下滑自动标记风险。

        旧版这里写的是 entries[i][1]，取到的是使用率数值列，
        于是把「52.3」当成角色名 —— 功能静默失效。
        正确列是 entries[i][0]（角色名）。这里修正。
        """
        cur_ver = v["version"]
        # 取同一游戏的上一个版本。旧版在跨游戏列表里 index+1，
        # 结果「星铁 3.6 的上一个版本」被算成「原神 5.2」，
        # JOIN 出 0 行 → 自动标记静默失效。
        prev_row = previous_version(v)
        if not prev_row:
            self.toast(f"{v['game']} 没有上一个版本可比对，无法自动标记", WARNING)
            return
        prev_ver = prev_row["version"]

        entries = query(
            "SELECT c.character_name, c.usage_rate, p.usage_rate AS prev "
            "FROM char_usage c JOIN char_usage p "
            "ON c.character_name = p.character_name "
            "WHERE c.version=? AND p.version=?", (cur_ver, prev_ver))

        if not entries:
            self.toast(f"没有 {prev_ver} / {cur_ver} 的使用率数据可比对", WARNING)
            return

        existing = {r["title"] for r in open_risks(v["id"])}
        added = 0
        for e in entries:
            name = e["character_name"]     # ← 旧版错写成 entries[i][1]
            cur = e["usage_rate"] or 0
            prev = e["prev"] or 0
            drop = prev - cur
            if drop < 5.0:
                continue

            title = f"{name}使用率较 {prev_ver} 下滑 {drop:.1f} 个百分点"
            if title in existing:
                continue

            execute(
                "INSERT INTO risks (version_id,title,probability,impact,"
                "mitigation,contingency,owner,status) "
                "VALUES (?,?,?,?,?,?,?,'open')",
                (v["id"], title,
                 "high" if drop >= 7 else "medium", "medium",
                 f"分析{name}的配队定位，评估是否需要数值调整或推广替代角色",
                 "准备角色加强方案或同定位替代角色宣传", "运营"))

            # 顺带补一条排期任务，让风险有落地动作（而不是只挂个标签）
            execute(
                "INSERT INTO checklists "
                "(version_id,task,category,assignee,deadline,status) "
                "VALUES (?,?,?,?,?,?)",
                (v["id"], f"排查{name}使用率下滑原因", "版本复盘", "",
                 date_str(datetime.now() + timedelta(days=3)), "pending"))
            added += 1

        if added:
            self.log("自动标记风险", f"{added} 项")
            self.toast(f"已标记 {added} 项风险，并生成对应排查任务")
        else:
            self.toast("没有检测到需要标记的风险", WARNING)
        self.remount("versions")

    # ── 详情 · 预算 ──
    def _detail_budget(self, host, v):
        planned, actual = budget_summary(v["id"])
        rate = actual / planned * 100 if planned else 0

        grid = ctk.CTkFrame(host, fg_color="transparent", height=1)
        grid.pack(fill="x", pady=(0, SP_MD))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="bgt")

        cards = [
            ("计划预算", f"{planned/10000:.1f} 万", None, None),
            ("实际支出", f"{actual/10000:.1f} 万", None,
             DANGER if planned and actual > planned else None),
            ("使用率", f"{rate:.0f}%",
             "超支" if rate > 100 else ("接近上限" if rate > 90 else "正常"),
             DANGER if rate > 100 else (WARNING if rate > 90 else None)),
        ]
        for i, (label, val, delta, accent_val) in enumerate(cards):
            C.StatCard(grid, label, val, delta,
                       "down" if accent_val == DANGER else None,
                       accent=accent_val).grid(
                row=0, column=i, sticky="nsew",
                padx=(0 if i == 0 else SP_SM, 0))

        items = query("SELECT * FROM budgets WHERE version_id=? "
                      "ORDER BY planned DESC", (v["id"],))
        if not items:
            C.EmptyState(host, "还没有预算明细", "money",
                         "添加各项支出的计划与实际金额").pack(fill="both",
                                                              expand=True)
            return

        box = ctk.CTkScrollableFrame(host, fg_color="transparent")
        box.pack(fill="both", expand=True)

        for b in items:
            row = ctk.CTkFrame(box, fg_color=BG_CARD, corner_radius=6)
            row.pack(fill="x", pady=3)
            inner = ctk.CTkFrame(row, fg_color="transparent", height=1)
            inner.pack(fill="x", padx=SP_MD, pady=SP_SM)

            pl, ac = b["planned"] or 0, b["actual"] or 0
            over = ac > pl

            top = ctk.CTkFrame(inner, fg_color="transparent", height=1)
            top.pack(fill="x")
            ctk.CTkLabel(top, text=b["item_name"], font=font(SIZE_SMALL),
                         text_color=TEXT_BODY).pack(side="left")
            ctk.CTkLabel(top, text=b["category"], font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY).pack(side="left",
                                                        padx=(SP_SM, 0))
            ctk.CTkLabel(top, text=f"{ac/10000:.1f} / {pl/10000:.1f} 万",
                         font=font(SIZE_SMALL),
                         text_color=DANGER if over else TEXT_SECONDARY).pack(
                side="right")

            bar = charts.ProgressBar(inner, height=5,
                                     color=DANGER if over else SUCCESS)
            bar.pack(fill="x", pady=(SP_XS, 0))
            bar.after(40, lambda b_=bar, r=(ac / pl * 100 if pl else 0):
                      b_.set(r) if b_.winfo_exists() else None)

    # ── 详情 · 角色使用率 ──
    def _detail_usage(self, host, v):
        cur_ver = v["version"]
        # 同上：必须按 game 取相邻版本，不能跨游戏。
        prev_row = previous_version(v)
        prev_ver = prev_row["version"] if prev_row else None

        rows = top_characters(cur_ver, 12)
        if not rows:
            C.EmptyState(host, f"{cur_ver} 还没有使用率数据", "star",
                         "导入深渊角色使用率后这里会显示排名与变化").pack(
                fill="both", expand=True)
            return

        chart = charts.BarChart(host, height=min(280, 22 * len(rows) + 20),
                                horizontal=True)
        chart.pack(fill="x", pady=(0, SP_MD))
        chart.set_data({
            "items": [{"label": r["character_name"], "value": r["usage_rate"]}
                      for r in rows],
            "color": INFO,
        })

        if not prev_ver:
            ctk.CTkLabel(host, text="没有上一个版本，无法显示环比变化",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
                anchor="w")
            return

        prev_map = {r["character_name"]: r["usage_rate"] for r in
                    query("SELECT character_name, usage_rate FROM char_usage "
                          "WHERE version=?", (prev_ver,))}

        ctk.CTkLabel(host, text=f"较 {prev_ver} 的变化",
                     font=font(SIZE_SMALL, bold=True),
                     text_color=TEXT_PRIMARY, anchor="w").pack(
            anchor="w", pady=(SP_SM, SP_XS))

        box = ctk.CTkScrollableFrame(host, fg_color="transparent", height=170)
        box.pack(fill="x")

        for r in rows:
            name = r["character_name"]
            if name not in prev_map:
                continue
            d = (r["usage_rate"] or 0) - (prev_map[name] or 0)
            line = ctk.CTkFrame(box, fg_color="transparent", height=1)
            line.pack(fill="x", pady=1)

            ctk.CTkLabel(line, text=name, font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, width=110,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=f"{r['usage_rate']:.1f}%",
                         font=font(SIZE_SMALL), text_color=TEXT_PRIMARY,
                         width=60, anchor="w").pack(side="left")

            # 涨红跌绿 —— 沿用国内看盘习惯，运营扫一眼就知道方向
            color = DANGER if d > 0 else (SUCCESS if d < 0 else TEXT_TERTIARY)
            arrow = "up" if d > 0 else ("down" if d < 0 else None)
            if arrow:
                icons.draw_icon(line, arrow, 10, color).pack(side="left", pady=3)
            ctk.CTkLabel(line, text=f"{d:+.1f}pp", font=font(SIZE_TINY),
                         text_color=color).pack(side="left", padx=(3, 0))

            if d <= -5.0:
                C.Badge(line, "需关注", DANGER).pack(side="right")

    # ── Ctrl+S ──
    def _save_versions(self):
        self.toast("版本页的改动会即时写入，无需手动保存", WARNING)
