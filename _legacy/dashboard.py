import csv
from datetime import datetime, timedelta
from tkinter import ttk, messagebox, filedialog
try:
    from tkinter import Canvas
except ImportError:
    Canvas = None

import customtkinter as ctk

from db import get_conn, load_config, save_config, add_log, date_str, GAMES
from theme import MHY_RED, MHY_DARK, MHY_CARD, MHY_BORDER, MHY_TEXT, MHY_SUB, GRID_COLOR


class DashboardMixin:
    def show_dashboard(self):
        self.clear_main(on_done=self._build_dashboard)

    def _build_dashboard(self):
        self.highlight_nav(0)
        self.current_view = "dashboard"

        # ── 页面标题横幅 ──
        banner = ctk.CTkFrame(self.main_frame, fg_color=MHY_CARD, corner_radius=0)
        banner.pack(fill="x", padx=0, pady=(0, 20))
        ctk.CTkLabel(banner, text="📊 数据工作台",
                     font=("Microsoft YaHei", 26, "bold"), text_color="white").pack(anchor="w", padx=30, pady=(25, 5))
        ctk.CTkLabel(banner, text="录入运营数据，自动生成分析看板",
                     font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(anchor="w", padx=30, pady=(0, 20))

        # ── 汇总卡片 ──
        summary_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        summary_row.pack(fill="x", padx=30, pady=(0, 20))
        try:
            with get_conn() as c:
                data_days = c.execute("SELECT COUNT(DISTINCT date) FROM daily_metrics").fetchone()[0]
                pending = c.execute("SELECT COUNT(*) FROM checklists WHERE status='pending'").fetchone()[0]
                rep_count = c.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
                ver_active = c.execute("SELECT COUNT(*) FROM versions WHERE status IN ('planning','preparing','live')").fetchone()[0]
        except:
            data_days = pending = rep_count = ver_active = 0

        mini_cards = [
            (str(data_days), "数据天数"),
            (str(pending), "待办任务"),
            (str(rep_count), "历史报告"),
            (str(ver_active), "活跃版本"),
        ]
        for val, label in mini_cards:
            c = ctk.CTkFrame(summary_row, fg_color=MHY_CARD, corner_radius=10,
                             border_width=1, border_color=MHY_BORDER)
            c.pack(side="left", padx=5, fill="x", expand=True)
            ctk.CTkLabel(c, text=val, font=("Microsoft YaHei", 22, "bold"),
                         text_color=MHY_RED).pack(pady=(12, 0))
            ctk.CTkLabel(c, text=label, font=("Microsoft YaHei", 11),
                         text_color=MHY_SUB).pack(pady=(0, 10))

        # Tab
        tab_view = ctk.CTkTabview(self.main_frame, fg_color=MHY_CARD, segmented_button_fg_color=MHY_DARK,
                                   segmented_button_selected_color=MHY_RED, segmented_button_unselected_color=MHY_BORDER)
        tab_view.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        tab1 = tab_view.add("📝 数据录入")
        tab2 = tab_view.add("📈 数据看板")

        self._build_input_tab(tab1)
        self._build_dashboard_tab(tab2)

    def _build_input_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="录入每日运营数据", font=("Microsoft YaHei", 16, "bold"),
                     text_color="white").pack(anchor="w", pady=(0, 15))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="日期", width=80).pack(side="left", padx=5)
        self.inp_date = ctk.CTkEntry(row, width=150, placeholder_text="YYYY-MM-DD")
        self.inp_date.pack(side="left", padx=5)
        self.inp_date.insert(0, date_str(datetime.now()))
        ctk.CTkLabel(row, text="游戏", width=80).pack(side="left", padx=5)
        self.inp_game = ctk.CTkOptionMenu(row, values=GAMES, width=150)
        self.inp_game.pack(side="left", padx=5)

        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", pady=10)
        fields = [
            ("DAU", "inp_dau", "50000"),
            ("新增帖子", "inp_posts", "200"),
            ("评论数", "inp_comments", "1000"),
            ("平均停留(min)", "inp_session", "20.0"),
            ("互动率(%)", "inp_rate", "5.0"),
        ]
        self.entries = {}
        for label, key, default in fields:
            f = ctk.CTkFrame(row2, fg_color="transparent")
            f.pack(side="left", padx=5, fill="x", expand=True)
            ctk.CTkLabel(f, text=label).pack()
            e = ctk.CTkEntry(f, justify="center")
            e.insert(0, default)
            e.pack(fill="x", pady=3)
            self.entries[key] = e

        ctk.CTkButton(frame, text="💾 保存数据", fg_color="#ff4d6a", hover_color="#e0415c",
                      command=self._save_metric).pack(pady=15)

        ctk.CTkLabel(frame, text="添加运营活动", font=("Microsoft YaHei", 16, "bold"),
                     text_color="white").pack(anchor="w", pady=(20, 10))

        row3 = ctk.CTkFrame(frame, fg_color="transparent")
        row3.pack(fill="x")
        ctk.CTkLabel(row3, text="活动名称", width=80).pack(side="left", padx=5)
        self.ev_name = ctk.CTkEntry(row3, width=200)
        self.ev_name.pack(side="left", padx=5)
        ctk.CTkLabel(row3, text="游戏", width=40).pack(side="left", padx=5)
        self.ev_game = ctk.CTkOptionMenu(row3, values=GAMES, width=120)
        self.ev_game.pack(side="left", padx=5)

        row4 = ctk.CTkFrame(frame, fg_color="transparent")
        row4.pack(fill="x", pady=10)
        ctk.CTkLabel(row4, text="类型", width=60).pack(side="left", padx=5)
        self.ev_type = ctk.CTkOptionMenu(row4, values=["版本活动","角色卡池","福利活动","线下活动","联动","其他"], width=120)
        self.ev_type.pack(side="left", padx=5)
        ctk.CTkLabel(row4, text="开始日期", width=80).pack(side="left", padx=5)
        self.ev_start = ctk.CTkEntry(row4, width=130, placeholder_text="YYYY-MM-DD")
        self.ev_start.pack(side="left", padx=5)
        self.ev_start.insert(0, date_str(datetime.now()))
        ctk.CTkLabel(row4, text="结束日期", width=80).pack(side="left", padx=5)
        self.ev_end = ctk.CTkEntry(row4, width=130, placeholder_text="YYYY-MM-DD")
        self.ev_end.pack(side="left", padx=5)
        self.ev_end.insert(0, date_str(datetime.now() + timedelta(days=14)))
        ctk.CTkLabel(row4, text="关联版本", width=80).pack(side="left", padx=5)
        self.ev_version = ctk.CTkOptionMenu(row4, values=["无"], width=150)
        self.ev_version.pack(side="left", padx=5)
        # 加载版本列表
        try:
            with get_conn() as c2:
                vers = c2.execute("SELECT id,game,version FROM versions WHERE status!='closed' ORDER BY start_date DESC").fetchall()
            if vers:
                ver_labels = ["无"] + [f"{v[1]} {v[2]}" for v in vers]
                self.ev_version.configure(values=ver_labels)
                self._ev_ver_map = {"无": 0}
                self._ev_ver_map.update({f"{v[1]} {v[2]}": v[0] for v in vers})
        except:
            self._ev_ver_map = {"无": 0}

        ctk.CTkButton(frame, text="➕ 添加活动", fg_color="#8b5cf6", hover_color="#7c3aed",
                      command=self._save_event).pack(pady=15)

        # 近期活动列表
        ctk.CTkLabel(frame, text="近期活动", font=("Microsoft YaHei", 14, "bold"),
                     text_color="white").pack(anchor="w", pady=(10, 5))
        self.ev_table_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.ev_table_container.pack(fill="x", pady=5)
        self._refresh_event_table()

    def _save_metric(self):
        try:
            with get_conn() as c:
                c.execute("""INSERT INTO daily_metrics (date,game,dau,new_posts,comments,avg_session,interaction_rate)
                             VALUES (?,?,?,?,?,?,?)""",
                          (self.inp_date.get(), self.inp_game.get(),
                           int(self.entries["inp_dau"].get()), int(self.entries["inp_posts"].get()),
                           int(self.entries["inp_comments"].get()), float(self.entries["inp_session"].get()),
                           float(self.entries["inp_rate"].get())))
            self._toast("数据已保存")
            self._save_log("录入数据", f"{self.inp_game.get()} DAU={self.entries['inp_dau'].get()}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _save_event(self):
        try:
            vid = self._ev_ver_map.get(self.ev_version.get(), 0) if hasattr(self, '_ev_ver_map') else 0
            with get_conn() as c:
                c.execute("INSERT INTO events (name,game,type,start_date,end_date,version_id) VALUES (?,?,?,?,?,?)",
                          (self.ev_name.get(), self.ev_game.get(), self.ev_type.get(),
                           self.ev_start.get(), self.ev_end.get(), vid))
            self._toast(f"活动「{self.ev_name.get()}」已添加")
            self._save_log("添加活动", self.ev_name.get())
            self.ev_name.delete(0, "end")
            self._refresh_event_table()
        except Exception as e:
            messagebox.showerror("错误", f"添加失败: {e}")

    def _refresh_event_table(self):
        for w in self.ev_table_container.winfo_children():
            w.destroy()
        try:
            with get_conn() as c:
                rows = c.execute("SELECT name,game,type,start_date,end_date,version_id FROM events ORDER BY start_date DESC LIMIT 10").fetchall()
                # 建立 vid→名称 映射
                vids = set(r[5] for r in rows if r[5])
                vmap = {}
                if vids:
                    for vid in vids:
                        v = c.execute("SELECT game,version FROM versions WHERE id=?", (vid,)).fetchone()
                        vmap[vid] = f"{v[0]} {v[1]}" if v else "-"
            if rows:
                frame = ctk.CTkFrame(self.ev_table_container, fg_color="transparent")
                frame.pack(fill="x")
                cols = ["活动名称","游戏","类型","开始","结束","关联版本"]
                for i, col in enumerate(cols):
                    ctk.CTkLabel(frame, text=col, font=("Microsoft YaHei", 12, "bold"),
                                 width=110, text_color=MHY_TEXT).grid(row=0, column=i, padx=2)
                for ri, row in enumerate(rows):
                    vals = list(row[:5]) + [vmap.get(row[5], "-") if row[5] else "-"]
                    for ci, val in enumerate(vals):
                        ctk.CTkLabel(frame, text=str(val), width=110,
                                     font=("Microsoft YaHei", 11), text_color=MHY_SUB).grid(row=ri+1, column=ci, padx=2)
        except:
            pass

    def _build_dashboard_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x")
        self.dash_game = ctk.CTkOptionMenu(row, values=["全部"] + GAMES, width=150)
        self.dash_game.pack(side="left", padx=5)
        self.dash_range = ctk.CTkOptionMenu(row, values=["近7天","近30天","近90天"], width=120)
        self.dash_range.pack(side="left", padx=5)
        self.dash_range.set("近30天")
        ctk.CTkButton(row, text="🔄 刷新", fg_color="#ff4d6a", hover_color="#e0415c",
                      command=lambda: self._refresh_dash(frame)).pack(side="left", padx=10)

        self.dash_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.dash_container.pack(fill="both", expand=True, pady=10)
        self._refresh_dash(frame)

    def _refresh_dash(self, parent):
        for w in self.dash_container.winfo_children():
            w.destroy()

        days = {"近7天": 7, "近30天": 30, "近90天": 90}.get(self.dash_range.get(), 30)
        start = date_str(datetime.now() - timedelta(days=days))
        game = self.dash_game.get()

        sql = "SELECT * FROM daily_metrics WHERE date>=?"
        params = [start]
        if game != "全部":
            sql += " AND game=?"
            params.append(game)
        sql += " ORDER BY date"

        try:
            with get_conn() as c:
                rows = c.execute(sql, params).fetchall()
            if not rows:
                ctk.CTkLabel(self.dash_container, text="暂无数据，请先在数据录入页面添加",
                             font=("Microsoft YaHei", 14), text_color=MHY_SUB).pack(pady=40)
                return

            # 汇总卡片
            daus = [r[3] for r in rows]
            posts = [r[4] for r in rows]
            rates = [r[7] for r in rows]
            avg_dau = sum(daus) / len(daus)
            avg_posts = sum(posts) / len(posts)
            avg_rate = sum(rates) / len(rates)

            card_frame = ctk.CTkFrame(self.dash_container, fg_color="transparent")
            card_frame.pack(fill="x", pady=10)
            cards = [
                (f"{int(avg_dau):,}", "平均 DAU"),
                (f"{int(avg_posts):,}", "日均帖子"),
                (f"{avg_rate:.1f}%", "平均互动率"),
                (f"{len(rows)} 天", "数据天数"),
            ]
            for val, label in cards:
                c = ctk.CTkFrame(card_frame, fg_color=MHY_CARD, corner_radius=12,
                                 border_width=1, border_color=MHY_BORDER)
                c.pack(side="left", padx=5, fill="x", expand=True)
                ctk.CTkLabel(c, text=val, font=("Microsoft YaHei", 26, "bold"),
                             text_color="white").pack(pady=(15, 0))
                ctk.CTkLabel(c, text=label, font=("Microsoft YaHei", 12),
                             text_color=MHY_SUB).pack(pady=(0, 15))

            # 折线图（Canvas）
            chart_mode_row = ctk.CTkFrame(self.dash_container, fg_color="transparent")
            chart_mode_row.pack(fill="x", pady=(15, 5))
            ctk.CTkLabel(chart_mode_row, text="DAU 变化趋势",
                         font=("Microsoft YaHei", 14, "bold"), text_color="white").pack(side="left")
            is_dual = getattr(self, "dual_chart_mode", False)
            ctk.CTkButton(chart_mode_row, text="📊 双轴模式" if not is_dual else "📈 单轴模式",
                          fg_color=MHY_BORDER, hover_color="#3a3a4e", text_color=MHY_TEXT,
                          width=100, height=28,
                          command=self._show_dual_chart if not is_dual else self._show_single_chart).pack(side="right")

            recent = rows[-30:] if len(rows) > 30 else rows
            if len(recent) >= 2:
                canvas = Canvas(self.dash_container, height=200, bg="#0f0f1a", highlightthickness=1,
                                highlightbackground=MHY_BORDER, bd=0)
                canvas.pack(fill="x")
                w = 700
                h = 180
                canvas.config(width=w, height=h)

                vals = [r[3] for r in recent]
                max_v = max(vals)
                min_v = min(vals) if min(vals) != max_v else 0
                rng = max_v - min_v or 1
                step_x = (w - 60) / (len(recent) - 1)

                # 背景网格
                for i in range(5):
                    y = 30 + i * (h - 50) / 4
                    canvas.create_line(40, y, w - 20, y, fill=MHY_BORDER, dash=(2, 4))
                    canvas.create_text(30, y, text=f"{int(max_v - rng/4*i)}", fill=MHY_SUB,
                                       font=("Microsoft YaHei", 8), anchor="e")

                # 填色区域
                pts = []
                for i, v in enumerate(vals):
                    x = 50 + i * step_x
                    y = 30 + (max_v - v) / rng * (h - 50)
                    pts.extend([x, y])
                pts.extend([50 + (len(vals)-1)*step_x, h-5, 50, h-5])
                canvas.create_polygon(pts, fill="#ff4d6a", outline="", stipple="gray25")

                # 折线
                for i in range(len(vals) - 1):
                    x1 = 50 + i * step_x
                    y1 = 30 + (max_v - vals[i]) / rng * (h - 50)
                    x2 = 50 + (i + 1) * step_x
                    y2 = 30 + (max_v - vals[i+1]) / rng * (h - 50)
                    canvas.create_line(x1, y1, x2, y2, fill="#ff6b81", width=3)

                # 数据点
                for i, v in enumerate(vals):
                    x = 50 + i * step_x
                    y = 30 + (max_v - v) / rng * (h - 50)
                    canvas.create_oval(x-4, y-4, x+4, y+4, fill="#ff4d6a", outline="white", width=1)

                # 日期标签（智能间距防重叠）
                last_x = -100
                for i, r in enumerate(recent):
                    x = 50 + i * step_x
                    if x - last_x >= 45:
                        canvas.create_text(x, h-5, text=r[1][-5:], fill=MHY_SUB,
                                           font=("Microsoft YaHei", 8), anchor="n")
                        last_x = x

            # ── 双轴图表（测试模式）──
            if getattr(self, "dual_chart_mode", False):
                dual_data = self._load_dual_axis_data()
                if dual_data and len(dual_data) >= 2:
                    canvas2 = Canvas(self.dash_container, height=300, bg="#0f0f1a",
                                     highlightthickness=1, highlightbackground=MHY_BORDER, bd=0)
                    canvas2.pack(fill="x", pady=(10, 0))
                    canvas2.config(width=700, height=300)
                    self._draw_dual_axis_chart(canvas2, dual_data, 700, 300)
                else:
                    ctk.CTkLabel(self.dash_container, text="暂无角色使用率或社区热度数据，请先运行 fetch_data.py",
                                 font=("Microsoft YaHei", 12), text_color=MHY_SUB).pack(pady=10)

            # 导出按钮
            export_row = ctk.CTkFrame(self.dash_container, fg_color="transparent")
            export_row.pack(fill="x", pady=(10, 0))
            ctk.CTkButton(export_row, text="📥 导出数据 CSV", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                          text_color=MHY_TEXT, command=self._export_data_csv).pack(side="right", padx=5)

            # 明细数据
            ctk.CTkLabel(self.dash_container, text="原始数据",
                         font=("Microsoft YaHei", 14, "bold"), text_color="white").pack(anchor="w", pady=(15, 5))

            tree_frame = ctk.CTkFrame(self.dash_container, fg_color=MHY_CARD, corner_radius=8)
            tree_frame.pack(fill="x")
            cols = ["日期","游戏","DAU","新增帖子","评论数","停留(min)","互动率(%)"]
            tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
            for col in cols:
                tree.heading(col, text=col)
                tree.column(col, width=90)
            for r in rows[-30:]:
                tree.insert("", "end", values=[r[1], r[2], r[3], r[4], r[5], r[6], f"{r[7]}%"])
            tree.pack(fill="x")
            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            vsb.pack(side="right", fill="y")
            tree.configure(yscrollcommand=vsb.set)

        except Exception as e:
            ctk.CTkLabel(self.dash_container, text=f"加载失败: {e}",
                         font=("Microsoft YaHei", 12), text_color="#e74c3c").pack()

    def _export_data_csv(self):
        try:
            fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                              title="导出数据", initialfile=f"运营数据_{datetime.now().strftime('%Y%m%d')}.csv")
            if not fp:
                return
            with get_conn() as c:
                rows = c.execute("SELECT date,game,dau,new_posts,comments,avg_session,interaction_rate FROM daily_metrics ORDER BY date").fetchall()
            with open(fp, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["日期","游戏","DAU","新增帖子","评论数","平均停留(min)","互动率(%)"])
                for r in rows:
                    w.writerow(r)
            messagebox.showinfo("成功", f"已导出 {len(rows)} 条数据到:\n{fp}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _draw_dual_axis_chart(self, canvas, data, w, h):
        """双轴折线图：左轴角色使用率（红色），右轴社区帖子数（蓝色）"""
        if len(data) < 2:
            canvas.create_text(w//2, h//2, text="数据不足（需至少2个版本）",
                               fill=MHY_SUB, font=("Microsoft YaHei", 12))
            return

        versions = [d["version"] for d in data]
        usage_vals = [d["usage_rate"] for d in data]
        post_vals = [d["post_count"] for d in data]

        max_usage = max(usage_vals) or 1
        min_usage = min(usage_vals) if min(usage_vals) != max_usage else 0
        max_post = max(post_vals) or 1

        usage_range = max_usage - min_usage or 1
        post_range = max_post or 1

        step_x = (w - 100) / (len(data) - 1)
        chart_t = 40  # top margin
        chart_b = h - 50  # bottom margin

        # ── 背景网格 ──
        for i in range(5):
            gy = chart_t + i * (chart_b - chart_t) // 4
            canvas.create_line(60, gy, w - 20, gy, fill=GRID_COLOR, dash=(2, 4))

        # ── 左Y轴标签（使用率 %）──
        for i in range(5):
            val = int(max_usage - usage_range * i / 4)
            gy = chart_t + i * (chart_b - chart_t) // 4
            canvas.create_text(55, gy, text=f"{val}%", fill=MHY_RED,
                               font=("Microsoft YaHei", 8), anchor="e")

        # ── 右Y轴标签（帖子数）──
        for i in range(5):
            val = int(max_post * (1 - i / 4))
            gy = chart_t + i * (chart_b - chart_t) // 4
            canvas.create_text(w - 15, gy, text=str(val), fill="#5b9bd5",
                               font=("Microsoft YaHei", 8), anchor="w")

        # ── 角色使用率折线（红色）──
        pts_usage = []
        for i, v in enumerate(usage_vals):
            x = 70 + i * step_x
            y = chart_t + (max_usage - v) / usage_range * (chart_b - chart_t)
            pts_usage.extend([x, y])
            # 数值标注
            canvas.create_text(x, y - 12, text=f"{v:.1f}%", fill=MHY_RED,
                               font=("Microsoft YaHei", 8, "bold"))
            # 数据点
            canvas.create_oval(x-3, y-3, x+3, y+3, fill=MHY_RED, outline="white", width=1)

        for i in range(len(pts_usage)//2 - 1):
            x1, y1 = pts_usage[i*2], pts_usage[i*2+1]
            x2, y2 = pts_usage[(i+1)*2], pts_usage[(i+1)*2+1]
            canvas.create_line(x1, y1, x2, y2, fill=MHY_RED, width=2)

        # ── 帖子数折线（蓝色）──
        pts_post = []
        for i, v in enumerate(post_vals):
            x = 70 + i * step_x
            y = chart_t + (max_post - v) / post_range * (chart_b - chart_t)
            pts_post.extend([x, y])
            # 数值标注
            canvas.create_text(x, y + 12, text=str(int(v)), fill="#5b9bd5",
                               font=("Microsoft YaHei", 8, "bold"))
            # 数据点
            canvas.create_oval(x-3, y-3, x+3, y+3, fill="#5b9bd5", outline="white", width=1)

        for i in range(len(pts_post)//2 - 1):
            x1, y1 = pts_post[i*2], pts_post[i*2+1]
            x2, y2 = pts_post[(i+1)*2], pts_post[(i+1)*2+1]
            canvas.create_line(x1, y1, x2, y2, fill="#5b9bd5", width=2)

        # ── X轴版本标签 ──
        last_x = -100
        for i, ver in enumerate(versions):
            x = 70 + i * step_x
            if x - last_x >= 55:
                canvas.create_text(x, h - 15, text=ver, fill=MHY_SUB,
                                   font=("Microsoft YaHei", 9), anchor="n")
                last_x = x

        # ── 图例 ──
        canvas.create_oval(80, 12, 88, 20, fill=MHY_RED, outline="")
        canvas.create_text(95, 16, text="角色使用率(%)", fill=MHY_RED,
                           font=("Microsoft YaHei", 9), anchor="w")
        canvas.create_oval(180, 12, 188, 20, fill="#5b9bd5", outline="")
        canvas.create_text(195, 16, text="社区帖子数", fill="#5b9bd5",
                           font=("Microsoft YaHei", 9), anchor="w")

    def _load_dual_axis_data(self):
        """从 db 读取 char_usage + community_hot，按版本聚合"""
        try:
            with get_conn() as c:
                usage_rows = c.execute("""
                    SELECT version, AVG(usage_rate) as avg_rate
                    FROM char_usage GROUP BY version ORDER BY version
                """).fetchall()
                hot_rows = c.execute("""
                    SELECT version, SUM(post_count) as total_posts
                    FROM community_hot GROUP BY version ORDER BY version
                """).fetchall()
        except:
            return []

        # Merge by version
        usage_map = {r[0]: r[1] for r in usage_rows}
        hot_map = {r[0]: r[1] for r in hot_rows}
        all_versions = sorted(set(list(usage_map.keys()) + list(hot_map.keys())))

        data = []
        for ver in all_versions:
            data.append({
                "version": ver,
                "usage_rate": usage_map.get(ver, 0),
                "post_count": hot_map.get(ver, 0),
            })
        return data

    def _show_dual_chart(self):
        """切换为双轴图表模式"""
        self.clear_main(on_done=self._build_dashboard)
        self.dual_chart_mode = True

    def _show_single_chart(self):
        """切换为单轴图表模式"""
        self.clear_main(on_done=self._build_dashboard)
        self.dual_chart_mode = False
