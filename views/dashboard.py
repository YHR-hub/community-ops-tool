"""数据看板 Mixin：双标签页 = 数据工作台 + 玩家健康度看板
- 数据工作台：日指标录入、Treeview 表格、Canvas 折线图、CSV 导出、汇总卡片
- 玩家健康度：留存率柱状图、玩家分群饼图、流失预警列表、测试数据生成、分群导出
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime, csv, os, random

from theme import (
    BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM,
    ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER,
)
import db


# ── 常量 ──────────────────────────────────────────────
GAMES = ["原神", "崩坏：星穹铁道", "绝区零", "崩坏3", "未定事件簿", "米游社综合"]
METRIC_COLS = ("id", "date", "game", "dau", "new_posts", "comments", "avg_session", "inter_rate")
METRIC_HDRS = ("ID", "日期", "游戏", "DAU", "新帖", "评论", "会话时长", "互动率%")
METRIC_WIDS = (50, 100, 110, 80, 70, 70, 80, 80)

CHURN_COLS = ("player_id", "game", "register_date", "last_login", "days", "status")
CHURN_HDRS = ("玩家ID", "游戏", "注册日期", "最后登录", "未登录天数", "状态")
CHURN_WIDS = (90, 110, 110, 110, 90, 90)

# 玩家分群配色
SEG_DEFS = [
    ("high",    "高活跃", ACCENT),
    ("medium",  "中活跃", SUCCESS),
    ("low",     "低活跃", WARNING),
    ("churned", "已流失", DANGER),
]


class DashboardMixin:
    """数据看板页面：双标签页（数据工作台 + 玩家健康度）"""

    # ────────────────── 入口 ──────────────────
    def create_dashboard(self, parent):
        """构建数据看板：CTkTabview 双标签页结构"""
        self._dash_frame = ctk.CTkFrame(parent, fg_color=BG_DARK)
        self._dash_frame.pack(fill="both", expand=True)

        self._tabview = ctk.CTkTabview(
            self._dash_frame, fg_color=BG_DARK,
            segmented_button_fg_color=BG_CARD,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_LIGHT,
            segmented_button_unselected_color=BG_CARD,
            segmented_button_unselected_hover_color=BG_INPUT,
            text_color=FG_TEXT,
        )
        self._tabview.pack(fill="both", expand=True, padx=6, pady=6)
        self._tabview.configure(command=self._on_dash_tab_change)

        tab_work = self._tabview.add("数据工作台")
        tab_health = self._tabview.add("玩家健康度")

        self._build_workbench_tab(tab_work)
        self._create_health_tab(tab_health)

        return self._dash_frame

    def _on_dash_tab_change(self):
        """切换标签页时按需刷新健康度看板"""
        try:
            name = self._tabview.get()
        except Exception:
            return
        if name == "玩家健康度":
            self._refresh_health()

    # ══════════════════ 数据工作台标签页 ══════════════════
    def _build_workbench_tab(self, parent):
        """构建数据工作台页面（原有全部功能）"""
        # ── 顶部汇总卡片行 ──
        cards_row = ctk.CTkFrame(parent, fg_color=BG_DARK)
        cards_row.pack(fill="x", padx=16, pady=(16, 8))

        self._dash_cards = {}
        card_cfgs = [
            ("data_days",   "数据天数",   "0",  ACCENT),
            ("today_dau",   "今日 DAU",   "--", SUCCESS),
            ("avg_rate",    "平均互动率", "--",  WARNING),
            ("total_posts", "总帖子数",   "0",  ACCENT_LIGHT),
        ]
        for i, (key, label, val, color) in enumerate(card_cfgs):
            card = ctk.CTkFrame(cards_row, fg_color=BG_CARD, corner_radius=10)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            cards_row.columnconfigure(i, weight=1)

            dot = ctk.CTkFrame(card, fg_color=color, width=4, height=40, corner_radius=2)
            dot.pack(side="left", padx=(12, 8), pady=12)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=10)

            lbl = ctk.CTkLabel(info, text=label, font=("Microsoft YaHei", 11),
                               text_color=FG_DIM, anchor="w")
            lbl.pack(anchor="w")

            val_lbl = ctk.CTkLabel(info, text=val, font=("Microsoft YaHei", 22, "bold"),
                                   text_color=FG_TEXT, anchor="w")
            val_lbl.pack(anchor="w")

            self._dash_cards[key] = val_lbl

        # ── 中间区域：折线图 + 录入表单 ──
        mid = ctk.CTkFrame(parent, fg_color=BG_DARK)
        mid.pack(fill="both", expand=True, padx=16, pady=4)

        # 左：折线图
        chart_outer = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10)
        chart_outer.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ctk.CTkLabel(chart_outer, text="DAU 趋势", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(anchor="w", padx=12, pady=(10, 2))

        self._dash_canvas = tk.Canvas(chart_outer, bg=BG_CARD, highlightthickness=0, height=220)
        self._dash_canvas.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # 右：录入表单
        form = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10, width=280)
        form.pack(side="right", fill="y", padx=(0, 0))
        form.pack_propagate(False)

        ctk.CTkLabel(form, text="数据录入", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(anchor="w", padx=12, pady=(10, 6))

        # 日期
        ctk.CTkLabel(form, text="日期", font=("Microsoft YaHei", 11),
                     text_color=FG_DIM).pack(anchor="w", padx=12)
        self._dash_date = ctk.CTkEntry(form, fg_color=BG_INPUT, text_color=FG_TEXT,
                                        border_color=BORDER, placeholder_text="YYYY-MM-DD",
                                        font=("Microsoft YaHei", 11))
        self._dash_date.pack(fill="x", padx=12, pady=(0, 6))
        self._dash_date.insert(0, datetime.date.today().isoformat())

        # 游戏
        ctk.CTkLabel(form, text="游戏", font=("Microsoft YaHei", 11),
                     text_color=FG_DIM).pack(anchor="w", padx=12)
        self._dash_game = ctk.CTkComboBox(form, values=GAMES, fg_color=BG_INPUT,
                                           text_color=FG_TEXT, border_color=BORDER,
                                           button_color=ACCENT, button_hover_color=ACCENT_LIGHT,
                                           dropdown_fg_color=BG_CARD, dropdown_hover_color=BG_INPUT,
                                           font=("Microsoft YaHei", 11))
        self._dash_game.set(GAMES[0])
        self._dash_game.pack(fill="x", padx=12, pady=(0, 6))

        # DAU / 新帖 / 评论
        field_defs = [
            ("dau",        "DAU",     "0"),
            ("new_posts",  "新帖数",  "0"),
            ("comments",   "评论数",  "0"),
        ]
        self._dash_fields = {}
        for key, label, placeholder in field_defs:
            ctk.CTkLabel(form, text=label, font=("Microsoft YaHei", 11),
                         text_color=FG_DIM).pack(anchor="w", padx=12)
            entry = ctk.CTkEntry(form, fg_color=BG_INPUT, text_color=FG_TEXT,
                                 border_color=BORDER, placeholder_text=placeholder,
                                 font=("Microsoft YaHei", 11))
            entry.pack(fill="x", padx=12, pady=(0, 6))
            self._dash_fields[key] = entry

        # 会话时长
        ctk.CTkLabel(form, text="平均会话时长(分钟)", font=("Microsoft YaHei", 11),
                     text_color=FG_DIM).pack(anchor="w", padx=12)
        self._dash_fields["avg_session"] = ctk.CTkEntry(form, fg_color=BG_INPUT,
                                                         text_color=FG_TEXT, border_color=BORDER,
                                                         placeholder_text="0",
                                                         font=("Microsoft YaHei", 11))
        self._dash_fields["avg_session"].pack(fill="x", padx=12, pady=(0, 6))

        # 互动率
        ctk.CTkLabel(form, text="互动率(%)", font=("Microsoft YaHei", 11),
                     text_color=FG_DIM).pack(anchor="w", padx=12)
        self._dash_fields["inter_rate"] = ctk.CTkEntry(form, fg_color=BG_INPUT,
                                                        text_color=FG_TEXT, border_color=BORDER,
                                                        placeholder_text="0.0",
                                                        font=("Microsoft YaHei", 11))
        self._dash_fields["inter_rate"].pack(fill="x", padx=12, pady=(0, 6))

        # 按钮行
        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(6, 10))

        ctk.CTkButton(btn_row, text="保存", fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                      font=("Microsoft YaHei", 11, "bold"), width=80,
                      command=self._dash_save).pack(side="left", padx=(0, 4))
        ctk.CTkButton(btn_row, text="清空表单", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 11), width=80,
                      command=self._dash_clear_form).pack(side="left", padx=(0, 4))
        ctk.CTkButton(btn_row, text="刷新", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 11), width=80,
                      command=self._refresh_dashboard).pack(side="left")

        # ── 底部：Treeview + 导出 ──
        bottom = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10)
        bottom.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        bar = ctk.CTkFrame(bottom, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(bar, text="运营数据明细", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(side="left")

        ctk.CTkButton(bar, text="导出 CSV", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 11), width=100,
                      command=self._export_csv).pack(side="right")
        ctk.CTkButton(bar, text="导入示例数据", fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                      font=("Microsoft YaHei", 11), width=110,
                      command=self._import_sample_data).pack(side="right", padx=(0, 4))
        ctk.CTkButton(bar, text="清空全部", fg_color=DANGER, hover_color="#c0392b",
                      font=("Microsoft YaHei", 11), width=90,
                      command=self._dash_clear_all).pack(side="right", padx=(0, 6))

        # Treeview
        tree_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._dash_tree = ttk.Treeview(tree_frame, columns=METRIC_COLS, show="headings",
                                       style="Dark.Treeview", height=8)
        for col, hdr, wid in zip(METRIC_COLS, METRIC_HDRS, METRIC_WIDS):
            self._dash_tree.heading(col, text=hdr, anchor="center")
            self._dash_tree.column(col, width=wid, anchor="center", minwidth=40)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._dash_tree.yview)
        self._dash_tree.configure(yscrollcommand=vsb.set)
        self._dash_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # 初始加载
        self._refresh_dashboard()

    # ────────────────── 保存数据 ──────────────────
    def _dash_save(self):
        """录入一条日指标到 daily_metrics"""
        date = self._dash_date.get().strip()
        game = self._dash_game.get().strip()

        # 校验日期格式
        try:
            datetime.date.fromisoformat(date)
        except (ValueError, TypeError):
            messagebox.showwarning("格式错误", "日期格式应为 YYYY-MM-DD")
            return

        # 读取数值
        try:
            dau = int(self._dash_fields["dau"].get() or 0)
            new_posts = int(self._dash_fields["new_posts"].get() or 0)
            comments = int(self._dash_fields["comments"].get() or 0)
            avg_session = float(self._dash_fields["avg_session"].get() or 0)
            inter_rate = float(self._dash_fields["inter_rate"].get() or 0)
        except ValueError:
            messagebox.showwarning("格式错误", "数值字段请输入有效数字")
            return

        if not game:
            messagebox.showwarning("必填项", "请选择游戏")
            return

        try:
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO daily_metrics(date,game,dau,new_posts,comments,avg_session,inter_rate) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (date, game, dau, new_posts, comments, avg_session, inter_rate),
                )
                conn.commit()
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return

        self._save_log("数据录入", f"{date} {game} DAU={dau}")
        self._toast("数据已保存")
        self._refresh_dashboard()

    # ────────────────── 刷新 ──────────────────
    def _refresh_dashboard(self):
        """从数据库加载全部日指标，刷新表格 + 折线图 + 汇总卡片"""
        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT id,date,game,dau,new_posts,comments,avg_session,inter_rate "
                    "FROM daily_metrics ORDER BY date DESC, id DESC LIMIT 500"
                ).fetchall()

                # 汇总查询
                agg = conn.execute(
                    "SELECT COUNT(DISTINCT date), "
                    "  SUM(CASE WHEN date=date('now','localtime') THEN dau ELSE 0 END), "
                    "  AVG(inter_rate), "
                    "  SUM(new_posts) "
                    "FROM daily_metrics"
                ).fetchone()
        except Exception:
            rows, agg = [], (0, 0, 0, 0)

        # 填充 Treeview
        self._dash_tree.delete(*self._dash_tree.get_children())
        for r in rows:
            display = list(r)
            display[7] = f"{display[7]:.2f}" if display[7] else "0.00"
            display[6] = f"{display[6]:.1f}" if display[6] else "0.0"
            self._dash_tree.insert("", "end", values=display)

        # 更新卡片
        data_days = agg[0] if agg[0] else 0
        today_dau = agg[1] if agg[1] else 0
        avg_rate = agg[2] if agg[2] else 0.0
        total_posts = agg[3] if agg[3] else 0

        self._dash_cards["data_days"].configure(text=str(data_days))
        self._dash_cards["today_dau"].configure(text=f"{int(today_dau):,}")
        self._dash_cards["avg_rate"].configure(text=f"{avg_rate:.2f}%")
        self._dash_cards["total_posts"].configure(text=f"{int(total_posts):,}")

        # 折线图数据（按日期正序，取最近30天 DAU 合计）
        self._chart_data = []
        try:
            with db.get_conn() as conn:
                chart_rows = conn.execute(
                    "SELECT date, SUM(dau) FROM daily_metrics "
                    "GROUP BY date ORDER BY date DESC LIMIT 30"
                ).fetchall()
            self._chart_data = list(reversed(chart_rows))
        except Exception:
            pass

        self._draw_chart()

    # ────────────────── Canvas 折线图 ──────────────────
    def _draw_chart(self):
        """在 Canvas 上绘制 DAU 趋势折线图"""
        canvas = self._dash_canvas
        canvas.delete("all")

        data = self._chart_data if hasattr(self, "_chart_data") else []
        if not data:
            canvas.create_text(
                canvas.winfo_reqwidth() // 2, 110,
                text="暂无数据", fill=FG_DIM,
                font=("Microsoft YaHei", 14),
            )
            return

        # 获取Canvas尺寸
        W = canvas.winfo_width() or 600
        H = canvas.winfo_height() or 220

        PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 40
        cw = W - PAD_L - PAD_R
        ch = H - PAD_T - PAD_B

        values = [d[1] or 0 for d in data]
        labels = [d[0] for d in data]
        vmax = max(values) if values else 1
        if vmax == 0:
            vmax = 1

        # 网格线
        grid_steps = 4
        for i in range(grid_steps + 1):
            y = PAD_T + ch - (ch * i / grid_steps)
            canvas.create_line(PAD_L, y, W - PAD_R, y, fill=BORDER, dash=(2, 4))
            val = int(vmax * i / grid_steps)
            canvas.create_text(PAD_L - 8, y, text=f"{val:,}", anchor="e",
                               fill=FG_DIM, font=("Microsoft YaHei", 9))

        # 折线
        n = len(values)
        if n < 2:
            # 单点
            cx = PAD_L + cw // 2
            cy = PAD_T + ch - (values[0] / vmax * ch)
            canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=ACCENT, outline=ACCENT)
            canvas.create_text(cx, H - 12, text=labels[0], fill=FG_DIM,
                               font=("Microsoft YaHei", 8))
        else:
            points = []
            for i, (val, lbl) in enumerate(zip(values, labels)):
                x = PAD_L + (cw * i / (n - 1))
                y = PAD_T + ch - (val / vmax * ch)
                points.append((x, y))

                # X 轴标签（间隔显示）
                if n <= 10 or i % max(1, n // 8) == 0 or i == n - 1:
                    short = lbl[5:] if len(lbl) > 5 else lbl  # MM-DD
                    canvas.create_text(x, H - 12, text=short, fill=FG_DIM,
                                       font=("Microsoft YaHei", 8))

            # 面积填充
            area = []
            for x, y in points:
                area.extend([x, y])
            area.extend([points[-1][0], PAD_T + ch])
            area.extend([points[0][0], PAD_T + ch])
            if len(area) >= 6:
                canvas.create_polygon(*area, fill=ACCENT + "20", outline="")

            # 连线
            for i in range(len(points) - 1):
                canvas.create_line(points[i][0], points[i][1],
                                   points[i + 1][0], points[i + 1][1],
                                   fill=ACCENT, width=2)

            # 数据点
            for x, y in points:
                canvas.create_oval(x - 3, y - 3, x + 3, y + 3,
                                   fill=ACCENT, outline=ACCENT_LIGHT)

    # ────────────────── CSV 导出 ──────────────────
    def _export_csv(self):
        """将 daily_metrics 导出为 CSV 文件"""
        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT date,game,dau,new_posts,comments,avg_session,inter_rate "
                    "FROM daily_metrics ORDER BY date DESC"
                ).fetchall()
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return

        if not rows:
            self._toast("无数据可导出")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"运营数据_{datetime.date.today().isoformat()}.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["日期", "游戏", "DAU", "新帖", "评论", "会话时长", "互动率%"])
                for r in rows:
                    writer.writerow(r)
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return

        self._save_log("CSV导出", f"{len(rows)} 条数据导出到 {os.path.basename(path)}")
        self._toast(f"已导出 {len(rows)} 条数据")

    # ────────────────── 删除选中行 ──────────────────
    def _dash_delete_selected(self):
        """删除 Treeview 中选中的数据行"""
        sel = self._dash_tree.selection()
        if not sel:
            self._toast("请先选择要删除的行")
            return

        if not messagebox.askyesno("确认删除", f"确定删除选中的 {len(sel)} 条数据？"):
            return

        ids = [self._dash_tree.item(s, "values")[0] for s in sel]
        try:
            with db.get_conn() as conn:
                conn.executemany(
                    "DELETE FROM daily_metrics WHERE id=?",
                    [(i,) for i in ids],
                )
                conn.commit()
        except Exception as exc:
            messagebox.showerror("删除失败", str(exc))
            return

        self._save_log("数据删除", f"删除 {len(ids)} 条记录")
        self._toast(f"已删除 {len(ids)} 条记录")
        self._refresh_dashboard()

    # ────────────────── 清空表单 ──────────────────
    def _dash_clear_form(self):
        """清空录入表单"""
        self._dash_date.delete(0, "end")
        self._dash_date.insert(0, datetime.date.today().isoformat())
        for key in self._dash_fields:
            self._dash_fields[key].delete(0, "end")
        self._toast("表单已清空")

    # ────────────────── 导入示例数据 ──────────────────
    def _import_sample_data(self):
        """批量导入 14 天示例运营数据"""
        today = datetime.date.today()
        rows = []
        for i in range(14):
            d = today - datetime.timedelta(days=i)
            game = random.choice(GAMES)
            dau = random.randint(5000, 50000)
            new_posts = random.randint(20, 200)
            comments = random.randint(100, 1000)
            avg_session = round(random.uniform(5, 45), 1)
            inter_rate = round(random.uniform(1.5, 8.0), 2)
            rows.append((d.isoformat(), game, dau, new_posts, comments, avg_session, inter_rate))

        try:
            with db.get_conn() as conn:
                conn.executemany(
                    "INSERT INTO daily_metrics(date,game,dau,new_posts,comments,avg_session,inter_rate) "
                    "VALUES(?,?,?,?,?,?,?)",
                    rows,
                )
                conn.commit()
        except Exception as exc:
            messagebox.showerror("导入失败", str(exc))
            return

        self._save_log("示例数据导入", f"导入 {len(rows)} 条数据")
        self._toast(f"已导入 {len(rows)} 条示例数据")
        self._refresh_dashboard()

    # ────────────────── 清空全部数据 ──────────────────
    def _dash_clear_all(self):
        """清空 daily_metrics 表中全部数据"""
        if not messagebox.askyesno("确认清空", "确定要清空全部运营数据吗？此操作不可恢复！"):
            return

        try:
            with db.get_conn() as conn:
                conn.execute("DELETE FROM daily_metrics")
                conn.commit()
        except Exception as exc:
            messagebox.showerror("清空失败", str(exc))
            return

        self._save_log("数据清空", "已清空全部 daily_metrics 数据")
        self._toast("已清空全部运营数据")
        self._refresh_dashboard()

    # ══════════════════ 玩家健康度看板 ══════════════════
    def _create_health_tab(self, parent):
        """构建玩家健康度看板标签页"""
        # ── 顶部：四张汇总卡片 ──
        cards_row = ctk.CTkFrame(parent, fg_color=BG_DARK)
        cards_row.pack(fill="x", padx=16, pady=(16, 8))

        self._health_cards = {}
        health_card_cfgs = [
            ("total_players", "总玩家数", "0",  ACCENT),
            ("active_rate",   "活跃率",   "--", SUCCESS),
            ("churn_rate",    "流失率",   "--", WARNING),
            ("risk_count",    "风险预警", "0",  DANGER),
        ]
        for i, (key, label, val, color) in enumerate(health_card_cfgs):
            card = ctk.CTkFrame(cards_row, fg_color=BG_CARD, corner_radius=10)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            cards_row.columnconfigure(i, weight=1)

            dot = ctk.CTkFrame(card, fg_color=color, width=4, height=40, corner_radius=2)
            dot.pack(side="left", padx=(12, 8), pady=12)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=10)

            ctk.CTkLabel(info, text=label, font=("Microsoft YaHei", 11),
                         text_color=FG_DIM, anchor="w").pack(anchor="w")
            val_lbl = ctk.CTkLabel(info, text=val, font=("Microsoft YaHei", 22, "bold"),
                                   text_color=FG_TEXT, anchor="w")
            val_lbl.pack(anchor="w")
            self._health_cards[key] = val_lbl

        # ── 中间：左留存柱状图 + 右分群饼图 ──
        mid = ctk.CTkFrame(parent, fg_color=BG_DARK)
        mid.pack(fill="both", expand=True, padx=16, pady=4)

        # 左：留存率柱状图
        ret_outer = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10)
        ret_outer.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ctk.CTkLabel(ret_outer, text="留存率（次日 / 7日 / 30日）",
                     font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(anchor="w", padx=12, pady=(10, 2))
        self._ret_canvas = tk.Canvas(ret_outer, bg=BG_CARD, highlightthickness=0, height=240)
        self._ret_canvas.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._ret_after_id = None
        self._ret_canvas.bind("<Configure>", self._on_ret_resize)

        # 右：分群饼图 + 四张分群卡片
        seg_outer = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10)
        seg_outer.pack(side="right", fill="both", expand=True)
        ctk.CTkLabel(seg_outer, text="玩家分群分布",
                     font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(anchor="w", padx=12, pady=(10, 2))
        self._seg_canvas = tk.Canvas(seg_outer, bg=BG_CARD, highlightthickness=0, height=200)
        self._seg_canvas.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self._seg_after_id = None
        self._seg_canvas.bind("<Configure>", self._on_seg_resize)

        seg_cards_row = ctk.CTkFrame(seg_outer, fg_color="transparent")
        seg_cards_row.pack(fill="x", padx=12, pady=(0, 10))
        self._seg_cards = {}
        for i, (key, name, color) in enumerate(SEG_DEFS):
            sc = ctk.CTkFrame(seg_cards_row, fg_color=BG_INPUT, corner_radius=8)
            sc.grid(row=0, column=i, padx=4, sticky="nsew")
            seg_cards_row.columnconfigure(i, weight=1)

            bar = ctk.CTkFrame(sc, fg_color=color, width=3, height=34, corner_radius=2)
            bar.pack(side="left", padx=(8, 6), pady=8)
            ctk.CTkLabel(sc, text=name, font=("Microsoft YaHei", 9),
                         text_color=FG_DIM, anchor="w").pack(anchor="w", padx=(0, 8), pady=(6, 0))
            cnt_lbl = ctk.CTkLabel(sc, text="0 (0.0%)", font=("Microsoft YaHei", 12, "bold"),
                                    text_color=FG_TEXT, anchor="w")
            cnt_lbl.pack(anchor="w", padx=(0, 8), pady=(0, 6))
            self._seg_cards[key] = cnt_lbl

        # ── 底部：流失预警列表 + 操作按钮 ──
        bottom = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10)
        bottom.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        bar = ctk.CTkFrame(bottom, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(bar, text="流失预警列表", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(side="left")

        ctk.CTkButton(bar, text="导出分群 CSV", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 11), width=120,
                      command=self._export_segments).pack(side="right")
        ctk.CTkButton(bar, text="生成测试数据", fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                      font=("Microsoft YaHei", 11, "bold"), width=120,
                      command=self._gen_test_players).pack(side="right", padx=(0, 6))

        tree_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._churn_tree = ttk.Treeview(tree_frame, columns=CHURN_COLS, show="headings",
                                        style="Dark.Treeview", height=8)
        for col, hdr, wid in zip(CHURN_COLS, CHURN_HDRS, CHURN_WIDS):
            self._churn_tree.heading(col, text=hdr, anchor="center")
            self._churn_tree.column(col, width=wid, anchor="center", minwidth=40)

        # 行颜色标签
        self._churn_tree.tag_configure("churned", background="#5a1e1e", foreground="#ffffff")
        self._churn_tree.tag_configure("risk", background="#4a2a1a", foreground="#ffffff")
        self._churn_tree.tag_configure("normal", background=BG_CARD, foreground=FG_TEXT)

        csb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._churn_tree.yview)
        self._churn_tree.configure(yscrollcommand=csb.set)
        self._churn_tree.pack(side="left", fill="both", expand=True)
        csb.pack(side="right", fill="y")

        # 初始化缓存并加载一次
        self._ret_data = (0.0, 0.0, 0.0, 0)
        self._seg_data = {
            "high": 0, "medium": 0, "low": 0, "churned": 0,
            "total": 0, "active": 0, "risk_count": 0,
        }
        self._refresh_health()

    # ────────────────── 健康度看板统一刷新 ──────────────────
    def _refresh_health(self):
        """刷新玩家健康度看板：留存 + 分群 + 流失列表 + 卡片"""
        self._ret_data = self._calc_retention()
        self._seg_data = self._calc_segments()
        self._refresh_health_cards()
        self._draw_retention_chart()
        self._draw_segment_pie()
        self._refresh_churn_list()

    def _refresh_health_cards(self):
        """刷新顶部汇总卡片与四张分群卡片"""
        seg = self._seg_data
        total = seg.get("total", 0)
        active = seg.get("active", 0)
        churned = seg.get("churned", 0)
        risk = seg.get("risk_count", 0)

        self._health_cards["total_players"].configure(text=str(total))
        self._health_cards["active_rate"].configure(
            text=f"{active / total * 100:.1f}%" if total else "--")
        self._health_cards["churn_rate"].configure(
            text=f"{churned / total * 100:.1f}%" if total else "--")
        self._health_cards["risk_count"].configure(text=str(risk))

        for key, _name, _color in SEG_DEFS:
            cnt = seg.get(key, 0)
            pct = cnt / total * 100 if total else 0.0
            self._seg_cards[key].configure(text=f"{cnt}  ({pct:.1f}%)")

    # ────────────────── 1. 留存率 ──────────────────
    def _calc_retention(self):
        """计算次日/7日/30日留存率（合格队列口径）
        返回 (d1_rate, d7_rate, d30_rate, total) 百分比
        合格队列：注册满 N 天的玩家才计入分母
        留存：last_login >= register_date + N 视为该窗口留存
        """
        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT register_date, last_login FROM players"
                ).fetchall()
        except Exception:
            rows = []

        if not rows:
            return 0.0, 0.0, 0.0, 0

        today = datetime.date.today()
        q1 = r1 = q7 = r7 = q30 = r30 = 0
        for reg, last in rows:
            try:
                rd = datetime.date.fromisoformat(reg)
                ll = datetime.date.fromisoformat(last)
            except (ValueError, TypeError):
                continue
            reg_age = (today - rd).days
            login_span = (ll - rd).days
            if login_span < 0:
                continue  # 数据异常：最后登录早于注册
            if reg_age >= 1:
                q1 += 1
                if login_span >= 1:
                    r1 += 1
            if reg_age >= 6:
                q7 += 1
                if login_span >= 6:
                    r7 += 1
            if reg_age >= 29:
                q30 += 1
                if login_span >= 29:
                    r30 += 1

        d1 = r1 / q1 * 100 if q1 else 0.0
        d7 = r7 / q7 * 100 if q7 else 0.0
        d30 = r30 / q30 * 100 if q30 else 0.0
        return d1, d7, d30, len(rows)

    def _on_ret_resize(self, event=None):
        """防抖：留存率图表重绘"""
        if self._ret_after_id:
            self.after_cancel(self._ret_after_id)
        self._ret_after_id = self.after(100, self._draw_retention_chart)

    def _on_seg_resize(self, event=None):
        """防抖：分群饼图重绘"""
        if self._seg_after_id:
            self.after_cancel(self._seg_after_id)
        self._seg_after_id = self.after(100, self._draw_segment_pie)

    def _draw_retention_chart(self):
        """Canvas 自绘柱状图：次日 / 7日 / 30日 留存率"""
        canvas = self._ret_canvas
        canvas.delete("all")

        d1, d7, d30, total = self._ret_data if hasattr(self, "_ret_data") else (0, 0, 0, 0)

        W = canvas.winfo_width() or 420
        H = canvas.winfo_height() or 240

        if total == 0:
            canvas.create_text(W / 2, H / 2, text="暂无玩家数据",
                               fill=FG_DIM, font=("Microsoft YaHei", 13))
            return

        labels = ["次日留存", "7日留存", "30日留存"]
        values = [d1, d7, d30]
        colors = [ACCENT, SUCCESS, WARNING]

        PAD_L, PAD_R, PAD_T, PAD_B = 44, 20, 34, 46
        cw = W - PAD_L - PAD_R
        ch = H - PAD_T - PAD_B

        # 纵轴网格（0-100%）
        for i in range(5):
            y = PAD_T + ch - ch * i / 4
            canvas.create_line(PAD_L, y, W - PAD_R, y, fill=BORDER, dash=(2, 4))
            canvas.create_text(PAD_L - 6, y, text=f"{25 * i}%", anchor="e",
                               fill=FG_DIM, font=("Microsoft YaHei", 8))

        # 基线
        canvas.create_line(PAD_L, PAD_T + ch, W - PAD_R, PAD_T + ch, fill=BORDER)

        n = 3
        slot = cw / n
        bar_w = slot * 0.46
        for i, (lbl, val, color) in enumerate(zip(labels, values, colors)):
            cx = PAD_L + slot * i + slot / 2
            bh = (val / 100.0) * ch
            x0 = cx - bar_w / 2
            y0 = PAD_T + ch - bh
            x1 = cx + bar_w / 2
            y1 = PAD_T + ch
            if bh > 0:
                canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
            # 百分比数值
            canvas.create_text(cx, y0 - 12, text=f"{val:.1f}%",
                               fill=FG_TEXT, font=("Microsoft YaHei", 12, "bold"))
            # 类目标签
            canvas.create_text(cx, PAD_T + ch + 18, text=lbl,
                               fill=FG_DIM, font=("Microsoft YaHei", 10))

    # ────────────────── 2. 玩家分群 ──────────────────
    def _calc_segments(self):
        """玩家分群：高活跃 / 中活跃 / 低活跃 / 已流失
        高活跃：3天内有登录 且 total_sessions>=20
        中活跃：7天内有登录 且 total_sessions>=5
        低活跃：14天内有登录 或 total_sessions<5
        已流失：超过14天未登录
        同时统计 total / active(高+中) / risk_count(>=7天未登录)
        """
        seg = {
            "high": 0, "medium": 0, "low": 0, "churned": 0,
            "total": 0, "active": 0, "risk_count": 0,
        }
        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT last_login, total_sessions FROM players"
                ).fetchall()
        except Exception:
            rows = []

        today = datetime.date.today()
        for last, sess in rows:
            try:
                ll = datetime.date.fromisoformat(last)
            except (ValueError, TypeError):
                continue
            days = (today - ll).days
            sess = sess or 0
            seg["total"] += 1
            if days > 14:
                seg["churned"] += 1
            elif days <= 3 and sess >= 20:
                seg["high"] += 1
            elif days <= 7 and sess >= 5:
                seg["medium"] += 1
            else:
                seg["low"] += 1
            if days >= 7:
                seg["risk_count"] += 1

        seg["active"] = seg["high"] + seg["medium"]
        return seg

    def _draw_segment_pie(self):
        """Canvas 自绘环形图：玩家分群分布"""
        canvas = self._seg_canvas
        canvas.delete("all")

        seg = self._seg_data if hasattr(self, "_seg_data") else {}
        total = seg.get("total", 0)

        W = canvas.winfo_width() or 380
        H = canvas.winfo_height() or 200

        if total == 0:
            canvas.create_text(W / 2, H / 2, text="暂无分群数据",
                               fill=FG_DIM, font=("Microsoft YaHei", 13))
            return

        cx = W * 0.34
        cy = H / 2
        r = min(W * 0.30, H * 0.42)

        # 顺时针绘制各扇区
        start = 90.0
        for key, _name, color in SEG_DEFS:
            cnt = seg.get(key, 0)
            if cnt <= 0:
                continue
            span = 360.0 * cnt / total
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                              start=start, extent=-span,
                              style="pieslice", fill=color, outline="")
            start -= span

        # 中心圆（做成环形）
        hole = r * 0.56
        canvas.create_oval(cx - hole, cy - hole, cx + hole, cy + hole,
                           fill=BG_CARD, outline="")
        canvas.create_text(cx, cy - 8, text=f"{total}",
                           fill=FG_TEXT, font=("Microsoft YaHei", 18, "bold"))
        canvas.create_text(cx, cy + 12, text="总玩家",
                           fill=FG_DIM, font=("Microsoft YaHei", 9))

        # 图例
        lx = W * 0.62
        ly = cy - (len(SEG_DEFS) * 24) / 2
        for i, (key, name, color) in enumerate(SEG_DEFS):
            cnt = seg.get(key, 0)
            pct = cnt / total * 100 if total else 0.0
            y = ly + i * 24
            canvas.create_rectangle(lx, y, lx + 14, y + 14, fill=color, outline="")
            canvas.create_text(lx + 20, y + 7, text=f"{name}  {cnt} ({pct:.1f}%)",
                               fill=FG_TEXT, anchor="w",
                               font=("Microsoft YaHei", 10))

    # ────────────────── 3. 流失预警 ──────────────────
    def _refresh_churn_list(self):
        """刷新流失预警 Treeview：player_id/游戏/注册/最后登录/未登录天数/状态"""
        tree = self._churn_tree
        tree.delete(*tree.get_children())

        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT player_id, game, register_date, last_login "
                    "FROM players ORDER BY last_login ASC"
                ).fetchall()
        except Exception:
            rows = []

        today = datetime.date.today()
        for pid, game, reg, last in rows:
            try:
                ll = datetime.date.fromisoformat(last)
            except (ValueError, TypeError):
                continue
            days = (today - ll).days
            if days >= 14:
                status = "已流失"
                tag = "churned"
            elif days >= 7:
                status = "流失风险"
                tag = "risk"
            else:
                status = "正常"
                tag = "normal"
            tree.insert("", "end",
                        values=(pid, game, reg, last, days, status),
                        tags=(tag,))

    # ────────────────── 生成测试玩家 ──────────────────
    def _gen_test_players(self):
        """批量生成 50 个模拟玩家数据"""
        today = datetime.date.today()
        inserted = 0
        try:
            with db.get_conn() as conn:
                for _ in range(50):
                    pid = "P" + str(random.randint(1000, 9999))
                    game = random.choice(GAMES)

                    if random.random() < 0.2:
                        # 20% 概率超 14 天未登录（已流失），需注册满 20 天以上
                        reg_offset = random.randint(20, 60)
                        reg_date = today - datetime.timedelta(days=reg_offset)
                        inactive = random.randint(15, reg_offset)
                        last_login = today - datetime.timedelta(days=inactive)
                    else:
                        # 80% 概率近期登录（0-13 天未登录）
                        reg_offset = random.randint(1, 60)
                        reg_date = today - datetime.timedelta(days=reg_offset)
                        max_inactive = min(13, reg_offset)
                        inactive = random.randint(0, max_inactive)
                        last_login = today - datetime.timedelta(days=inactive)

                    total_sessions = random.randint(1, 50)
                    avg_session = round(random.uniform(5, 120), 1)

                    cur = conn.execute(
                        "INSERT OR IGNORE INTO players"
                        "(player_id, game, register_date, last_login, total_sessions, avg_session, status) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (pid, game, reg_date.isoformat(), last_login.isoformat(),
                         total_sessions, avg_session, "active"),
                    )
                    inserted += cur.rowcount
                conn.commit()
        except Exception as exc:
            messagebox.showerror("生成失败", str(exc))
            return

        self._save_log("生成测试玩家", f"插入 {inserted} 条")
        self._toast(f"已生成 {inserted} 个测试玩家")
        self._refresh_health()

    # ────────────────── 分群数据导出 ──────────────────
    def _export_segments(self):
        """将玩家分群数据导出为 CSV 文件"""
        seg = self._seg_data if hasattr(self, "_seg_data") else {}
        total = seg.get("total", 0)
        if total == 0:
            self._toast("无分群数据可导出")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"玩家分群_{datetime.date.today().isoformat()}.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["分群", "人数", "占比%"])
                for _key, name, _color in SEG_DEFS:
                    cnt = seg.get(_key, 0)
                    pct = cnt / total * 100 if total else 0.0
                    writer.writerow([name, cnt, f"{pct:.2f}"])
                writer.writerow(["合计", total, "100.00"])
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return

        self._save_log("分群导出", f"导出到 {os.path.basename(path)}")
        self._toast("已导出分群数据")
