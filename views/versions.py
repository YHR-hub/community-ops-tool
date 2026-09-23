from datetime import datetime, timedelta
from tkinter import messagebox, StringVar
import logging

import customtkinter as ctk

from db import get_conn, load_config, save_config, add_log, date_str, GAMES
from theme import MHY_RED, MHY_DARK, MHY_CARD, MHY_BORDER, MHY_TEXT, MHY_SUB

logger = logging.getLogger(__name__)


class VersionsMixin:
    def show_versions(self):
        self.clear_main(on_done=self._build_versions)

    def _build_versions(self):
        self.highlight_nav(2)
        self.current_view = "versions"

        banner = ctk.CTkFrame(self.main_frame, fg_color=MHY_CARD, corner_radius=0)
        banner.pack(fill="x", padx=0, pady=(0, 20))
        ctk.CTkLabel(banner, text="📅 版本管理",
                     font=("Microsoft YaHei", 26, "bold"), text_color="white").pack(anchor="w", padx=30, pady=(25, 5))
        ctk.CTkLabel(banner, text="版本排期、任务追踪、Checklist",
                     font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(anchor="w", padx=30, pady=(0, 20))

        tab_view = ctk.CTkTabview(self.main_frame, fg_color=MHY_CARD, segmented_button_fg_color=MHY_DARK,
                                   segmented_button_selected_color=MHY_RED, segmented_button_unselected_color=MHY_BORDER)
        tab_view.pack(fill="both", expand=True, padx=30, pady=20)
        tab1 = tab_view.add("📌 版本看板")
        tab2 = tab_view.add("📋 检查清单")
        tab3 = tab_view.add("📅 时间线")
        tab4 = tab_view.add("🗓 排期")
        tab5 = tab_view.add("💰 预算")
        tab6 = tab_view.add("⚠ 风险")

        self._build_version_board(tab1)
        self._build_checklist_tab(tab2)
        self._build_timeline_tab(tab3)
        self._build_schedule_tab(tab4)
        self._build_budget_tab(tab5)
        self._build_risk_tab(tab6)

    def _build_version_board(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="筛选游戏", width=80, text_color=MHY_TEXT).pack(side="left", padx=5)
        self.ver_game = ctk.CTkOptionMenu(row, values=["全部"] + GAMES, width=150,
                                           command=lambda _: self._refresh_versions())
        self.ver_game.pack(side="left", padx=5)

        # 新建版本表单
        ctk.CTkButton(row, text="➕ 新建版本", fg_color="#8b5cf6", hover_color="#7c3aed",
                      command=self._show_new_version_form).pack(side="right", padx=5)

        self.ver_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.ver_container.pack(fill="both", expand=True, pady=10)
        self._refresh_versions()

    def _show_new_version_form(self, edit_data=None):
        is_edit = edit_data is not None
        dialog = ctk.CTkToplevel(self)
        dialog.title("编辑版本" if is_edit else "新建版本")
        dialog.geometry("550x520")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=MHY_CARD)

        ctk.CTkLabel(dialog, text="编辑版本" if is_edit else "新建版本",
                     font=("Microsoft YaHei", 16, "bold"), text_color="white").pack(pady=(15, 10))

        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row, text="游戏", width=60, text_color=MHY_TEXT).pack(side="left")
        game_var = ctk.StringVar(value=edit_data[1] if is_edit else GAMES[0])
        ctk.CTkOptionMenu(row, variable=game_var, values=GAMES, width=150).pack(side="left")

        row2 = ctk.CTkFrame(dialog, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row2, text="版本号", width=60, text_color=MHY_TEXT).pack(side="left")
        ver_entry = ctk.CTkEntry(row2, width=150, placeholder_text="如 4.8")
        if is_edit:
            ver_entry.insert(0, edit_data[2])
        ver_entry.pack(side="left")

        row3 = ctk.CTkFrame(dialog, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row3, text="开始日期", width=60, text_color=MHY_TEXT).pack(side="left")
        start_entry = ctk.CTkEntry(row3, width=150, placeholder_text="YYYY-MM-DD")
        start_entry.insert(0, edit_data[3] if is_edit else date_str(datetime.now()))
        start_entry.pack(side="left")

        row4 = ctk.CTkFrame(dialog, fg_color="transparent")
        row4.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row4, text="结束日期", width=60, text_color=MHY_TEXT).pack(side="left")
        end_entry = ctk.CTkEntry(row4, width=150, placeholder_text="YYYY-MM-DD")
        end_entry.insert(0, edit_data[4] if (is_edit and edit_data[4]) else date_str(datetime.now() + timedelta(days=42)))
        end_entry.pack(side="left")

        row_st = ctk.CTkFrame(dialog, fg_color="transparent")
        row_st.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row_st, text="状态", width=60, text_color=MHY_TEXT).pack(side="left")
        st_vals = {"planning":"规划中","preparing":"准备中","live":"已上线","review":"复盘","closed":"已关闭"}
        st_rev = {v:k for k,v in st_vals.items()}
        def_val = st_vals.get(edit_data[5], "规划中") if is_edit else "规划中"
        status_var = ctk.StringVar(value=def_val)
        st_menu = ctk.CTkOptionMenu(row_st, variable=status_var,
                                     values=list(st_vals.values()), width=150)
        st_menu.pack(side="left")

        ctk.CTkLabel(dialog, text="版本亮点", font=("Microsoft YaHei", 12), text_color=MHY_TEXT).pack(anchor="w", padx=20)
        hl_text = ctk.CTkTextbox(dialog, height=60, fg_color=MHY_DARK, text_color=MHY_TEXT)
        if is_edit and edit_data[6]:
            hl_text.insert("1.0", edit_data[6])
        hl_text.pack(fill="x", padx=20, pady=5)

        # 模板选择
        if not is_edit:
            ctk.CTkLabel(dialog, text="任务模板（可选）", font=("Microsoft YaHei", 12), text_color=MHY_TEXT).pack(anchor="w", padx=20)
            tmpl_row = ctk.CTkFrame(dialog, fg_color="transparent")
            tmpl_row.pack(fill="x", padx=20, pady=5)
            tmpl_var = ctk.StringVar(value="无")
            templates = {
                "无": [],
                "标准手游版本": ["版本PV发布","角色卡池上线","版本活动配置","社媒预热","数据埋点检查","版本复盘"],
                "角色卡池上线": ["角色PV制作","前瞻直播","技能展示帖","预约H5","倒计时海报","数据分析"],
                "大型活动": ["活动规则确认","奖励数值配置","宣传素材准备","公告文案审核","FAQ准备","复盘收集"],
            }
            ctk.CTkOptionMenu(tmpl_row, variable=tmpl_var, values=list(templates.keys()), width=200).pack(side="left")
            ctk.CTkLabel(tmpl_row, text="新建版本后自动导入任务", font=("Microsoft YaHei", 11),
                         text_color=MHY_SUB).pack(side="left", padx=10)
        else:
            tmpl_var = None
            templates = {}

        def save():
            try:
                hl = hl_text.get("1.0", "end-1c").strip()
                game_v = game_var.get()
                ver_v = ver_entry.get()
                st_v = start_entry.get()
                end_v = end_entry.get()
                status_cn = status_var.get()
                status = st_rev.get(status_cn, "planning")  # convert Chinese label back to English key
                if not game_v or not ver_v or not st_v:
                    messagebox.showwarning("提示", "游戏、版本号、开始日期为必填项")
                    return
                with get_conn() as c:
                    if is_edit:
                        c.execute("""UPDATE versions SET game=?,version=?,start_date=?,end_date=?,
                                     status=?,highlights=? WHERE id=?""",
                                  (game_v, ver_v, st_v, end_v, status, hl, edit_data[0]))
                    else:
                        cur = c.execute("""INSERT INTO versions (game,version,start_date,end_date,status,highlights)
                                     VALUES (?,?,?,?,?,?)""",
                                  (game_v, ver_v, st_v, end_v, status, hl))
                        vid = cur.lastrowid
                        # 导入模板任务
                        for task in templates.get(tmpl_var.get(), []):
                            c.execute("INSERT INTO checklists (version_id,task) VALUES (?,?)", (vid, task))
                dialog.destroy()
                self._refresh_versions()
                messagebox.showinfo("成功", "版本已更新" if is_edit else "版本已创建"
                                    + (f"，已导入 {len(templates.get(tmpl_var.get(), []))} 个预设任务" if not is_edit and tmpl_var.get() != "无" else ""))
            except Exception as e:
                messagebox.showerror("错误", str(e))

        ctk.CTkButton(dialog, text="✅ 确认保存", fg_color="#ff4d6a", hover_color="#e0415c",
                      command=save).pack(pady=20)

    def _refresh_versions(self):
        for w in self.ver_container.winfo_children():
            w.destroy()

        try:
            game = self.ver_game.get()
            sql = "SELECT * FROM versions"
            params = []
            if game != "全部":
                sql += " WHERE game=?"
                params.append(game)
            sql += " ORDER BY start_date DESC"

            with get_conn() as c:
                rows = c.execute(sql, params).fetchall()
            if not rows:
                ctk.CTkLabel(self.ver_container, text="暂无版本数据，点击「新建版本」开始",
                             font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(pady=30)
                return

            for r in rows:
                vid, game, ver, start, end, status, highlights, notes = r
                card = ctk.CTkFrame(self.ver_container, fg_color=MHY_CARD, corner_radius=12,
                                     border_width=1, border_color=MHY_BORDER)
                card.pack(fill="x", pady=6)

                # 标题行
                title_row = ctk.CTkFrame(card, fg_color="transparent")
                title_row.pack(fill="x", padx=15, pady=(10, 5))

                status_map = {"planning": ("规划中", "#f59e0b"), "preparing": ("准备中", "#06b6d4"),
                              "live": ("已上线", "#2ecc71"), "review": ("复盘", "#8b5cf6"), "closed": ("已关闭", "#999")}
                slabel, scol = status_map.get(status, (status, "#999"))

                ctk.CTkLabel(title_row, text=f"{game} {ver}", font=("Microsoft YaHei", 15, "bold"),
                             text_color="white").pack(side="left")
                badge = ctk.CTkFrame(title_row, fg_color=scol, corner_radius=12)
                badge.pack(side="left", padx=10)
                ctk.CTkLabel(badge, text=slabel, font=("Microsoft YaHei", 11),
                             text_color="white").pack(padx=10, pady=2)
                ctk.CTkLabel(title_row, text=f"{start} → {end or 'TBD'}",
                             font=("Microsoft YaHei", 12), text_color=MHY_SUB).pack(side="right")

                # 编辑/删除 按钮
                btn_row = ctk.CTkFrame(title_row, fg_color="transparent")
                btn_row.pack(side="right", padx=10)
                ctk.CTkButton(btn_row, text="✏ 编辑", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                              text_color=MHY_TEXT, width=60, height=24, font=("Microsoft YaHei", 10),
                              command=lambda rid=r: self._edit_version(rid)).pack(side="left", padx=2)
                ctk.CTkButton(btn_row, text="🗑 删除", fg_color="#e74c3c", hover_color="#c0392b",
                              text_color="white", width=60, height=24, font=("Microsoft YaHei", 10),
                              command=lambda rid=r: self._delete_version(rid)).pack(side="left", padx=2)

                # 进度条
                with get_conn() as c2:
                    total = c2.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (vid,)).fetchone()[0]
                    done = c2.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (vid,)).fetchone()[0]
                if total > 0:
                    pct = int(done / total * 100)
                    pg_row = ctk.CTkFrame(card, fg_color="transparent")
                    pg_row.pack(fill="x", padx=15, pady=(0, 5))
                    ctk.CTkLabel(pg_row, text=f"任务进度 {done}/{total}", font=("Microsoft YaHei", 11),
                                 text_color=MHY_SUB).pack(side="left")
                    ctk.CTkLabel(pg_row, text=f"{pct}%", font=("Microsoft YaHei", 11, "bold"),
                                 text_color="#2ecc71" if pct == 100 else MHY_SUB).pack(side="right")
                    bar_frame = ctk.CTkFrame(card, fg_color=MHY_DARK, height=6, corner_radius=3)
                    bar_frame.pack(fill="x", padx=15, pady=(0, 10))
                    bar_fill = ctk.CTkFrame(bar_frame, fg_color="#2ecc71" if pct == 100 else MHY_RED,
                                            height=6, corner_radius=3, width=int(pct / 100 * 700))
                    bar_fill.pack(side="left")

                # 健康度评分
                health_score = self._calc_version_health(vid)
                if health_score is not None:
                    score_color = "#2ecc71" if health_score >= 0.8 else ("#f59e0b" if health_score >= 0.6 else "#e74c3c")
                    score_pct = int(health_score * 100)
                    health_row = ctk.CTkFrame(card, fg_color="transparent")
                    health_row.pack(fill="x", padx=15, pady=(0, 5))
                    ctk.CTkLabel(health_row, text="健康度",
                                  font=("Microsoft YaHei", 11), text_color=MHY_SUB).pack(side="left")
                    ctk.CTkLabel(health_row, text=f"{score_pct}%",
                                  font=("Microsoft YaHei", 11, "bold"),
                                  text_color=score_color).pack(side="left", padx=5)
                    # 简易进度条
                    hbar_bg = ctk.CTkFrame(health_row, fg_color=MHY_DARK, height=6, width=100, corner_radius=3)
                    hbar_bg.pack(side="left", padx=5)
                    hbar_fill = ctk.CTkFrame(hbar_bg, fg_color=score_color, height=6, corner_radius=3,
                                             width=int(health_score * 100))
                    hbar_fill.pack(side="left")

                if highlights:
                    ctk.CTkLabel(card, text=f"亮点: {highlights[:60]}",
                                 font=("Microsoft YaHei", 11), text_color=MHY_SUB).pack(
                        anchor="w", padx=15, pady=(0, 10))

        except Exception as e:
            ctk.CTkLabel(self.ver_container, text=f"加载失败: {e}",
                         font=("Microsoft YaHei", 12), text_color="#e74c3c").pack()

    def _edit_version(self, row_data):
        self._show_new_version_form(edit_data=row_data)

    def _delete_version(self, row_data):
        vid, game, ver = row_data[0], row_data[1], row_data[2]
        if not messagebox.askyesno("确认删除", f"确定要删除 {game} {ver} 及其所有任务吗？\n此操作不可撤销。"):
            return
        try:
            with get_conn() as c:
                c.execute("DELETE FROM checklists WHERE version_id=?", (vid,))
                c.execute("DELETE FROM versions WHERE id=?", (vid,))
            self._refresh_versions()
            messagebox.showinfo("成功", f"{game} {ver} 已删除")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _calc_version_health(self, vid):
        """计算版本健康度: 0-1 之间的浮点数"""
        try:
            with get_conn() as c:
                # DAU 完成率
                dau_rows = c.execute(
                    "SELECT AVG(dau) FROM daily_metrics WHERE game=(SELECT game FROM versions WHERE id=?)",
                    (vid,)).fetchone()
                avg_dau = dau_rows[0] if dau_rows and dau_rows[0] else 0
                dau_ratio = min(1.0, avg_dau / 200000) if avg_dau > 0 else 0.5

                # 预算偏差率
                budget_rows = c.execute(
                    "SELECT SUM(planned), SUM(actual) FROM budgets WHERE version_id=?", (vid,)).fetchone()
                planned = budget_rows[0] or 0
                actual = budget_rows[1] or 0
                budget_deviation = abs(planned - actual) / max(planned, 1)
                budget_score = max(0, 1 - budget_deviation)

                # 风险数
                risk_cnt = c.execute("SELECT COUNT(*) FROM risks WHERE version_id=?", (vid,)).fetchone()[0]
                risk_score = max(0, 1 - risk_cnt / 20)

                # 社区热度
                hot_rows = c.execute(
                    "SELECT SUM(post_count) FROM community_hot WHERE version=(SELECT version FROM versions WHERE id=?)",
                    (vid,)).fetchone()
                hot_total = hot_rows[0] if hot_rows and hot_rows[0] else 0
                hot_normalized = min(1.0, hot_total / 50000) if hot_total > 0 else 0.3

                # 任务完成率
                total_tasks = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (vid,)).fetchone()[0]
                done_tasks = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (vid,)).fetchone()[0]
                task_ratio = done_tasks / total_tasks if total_tasks > 0 else 0.5

                # 加权计算
                score = 0.3 * dau_ratio + 0.3 * budget_score + 0.2 * risk_score + 0.1 * hot_normalized + 0.1 * task_ratio
                return round(max(0.0, min(1.0, score)), 3)
        except Exception as e:
            logger.debug(f"健康度计算异常 vid={vid}: {e}")
            return None

    def _build_checklist_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 选择版本
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="选择版本", width=80, text_color=MHY_TEXT).pack(side="left", padx=5)

        try:
            with get_conn() as c:
                vers = c.execute("SELECT id,game,version FROM versions ORDER BY start_date DESC").fetchall()
        except:
            vers = []

        if not vers:
            ctk.CTkLabel(frame, text="暂无版本，请先在版本看板中创建",
                         font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(pady=30)
            return

        ver_labels = [f"{v[1]} {v[2]}" for v in vers]
        self.cl_version = ctk.CTkOptionMenu(row, values=ver_labels, width=250)
        self.cl_version.pack(side="left", padx=5)
        self._cl_vers = {f"{v[1]} {v[2]}": v[0] for v in vers}

        # 新增任务
        task_row = ctk.CTkFrame(frame, fg_color="transparent")
        task_row.pack(fill="x", pady=15)
        self.cl_task = ctk.CTkEntry(task_row, width=300, placeholder_text="输入新任务...")
        self.cl_task.pack(side="left", padx=5)
        self.cl_assignee = ctk.CTkEntry(task_row, width=120, placeholder_text="负责人")
        self.cl_assignee.pack(side="left", padx=5)
        self.cl_deadline = ctk.CTkEntry(task_row, width=130, placeholder_text="截止日期")
        self.cl_deadline.pack(side="left", padx=5)
        ctk.CTkButton(task_row, text="➕ 添加", fg_color="#8b5cf6", hover_color="#7c3aed",
                      command=self._add_task).pack(side="left", padx=5)

        self.cl_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.cl_container.pack(fill="both", expand=True, pady=10)
        self._refresh_tasks()

    def _add_task(self):
        key = self.cl_version.get()
        vid = self._cl_vers.get(key)
        if not vid or not self.cl_task.get():
            return
        try:
            with get_conn() as c:
                c.execute("INSERT INTO checklists (version_id,task,assignee,deadline) VALUES (?,?,?,?)",
                          (vid, self.cl_task.get(), self.cl_assignee.get(), self.cl_deadline.get()))
            self.cl_task.delete(0, "end")
            self._refresh_tasks()
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _refresh_tasks(self):
        for w in self.cl_container.winfo_children():
            w.destroy()

        key = self.cl_version.get()
        vid = self._cl_vers.get(key)
        if not vid:
            return

        try:
            with get_conn() as c:
                items = c.execute("SELECT id,task,assignee,deadline,status FROM checklists WHERE version_id=? ORDER BY id",
                                  (vid,)).fetchall()
            if not items:
                ctk.CTkLabel(self.cl_container, text="暂无任务，添加一个吧",
                             font=("Microsoft YaHei", 12), text_color=MHY_SUB).pack(pady=20)
                return

            for item in items:
                iid, task, assignee, deadline, status = item
                done = status == "done"
                f = ctk.CTkFrame(self.cl_container, fg_color=MHY_CARD, corner_radius=8,
                                 border_width=1, border_color=MHY_BORDER)
                f.pack(fill="x", pady=3)

                var = ctk.BooleanVar(value=done)
                cb = ctk.CTkCheckBox(f, text="", variable=var,
                                      command=lambda iid=iid, v=var: self._toggle_task(iid, v))
                cb.pack(side="left", padx=10, pady=8)

                task_text = f"{'✅ ' if done else ''}{task}"
                ctk.CTkLabel(f, text=task_text,
                             font=("Microsoft YaHei", 13),
                             text_color=MHY_SUB if done else MHY_TEXT).pack(side="left", padx=5)
                if assignee:
                    ctk.CTkLabel(f, text=f"👤 {assignee}", font=("Microsoft YaHei", 11),
                                 text_color=MHY_SUB).pack(side="right", padx=10)
                if deadline:
                    ctk.CTkLabel(f, text=f"📅 {deadline}", font=("Microsoft YaHei", 11),
                                 text_color=MHY_SUB).pack(side="right", padx=5)
                ctk.CTkButton(f, text="🗑", fg_color="transparent", hover_color="#c0392b",
                              text_color="#e74c3c", width=30, height=24, font=("Microsoft YaHei", 10),
                              command=lambda iid=iid: self._delete_task(iid)).pack(side="right", padx=5)

        except Exception as e:
            ctk.CTkLabel(self.cl_container, text=f"加载失败: {e}",
                         font=("Microsoft YaHei", 12), text_color="#e74c3c").pack()

    def _toggle_task(self, iid, var):
        status = "done" if var.get() else "pending"
        try:
            with get_conn() as c:
                c.execute("UPDATE checklists SET status=? WHERE id=?", (status, iid))
            self._refresh_tasks()
        except:
            pass

    def _delete_task(self, iid):
        if not messagebox.askyesno("确认", "确定要删除这个任务吗？"):
            return
        try:
            with get_conn() as c:
                c.execute("DELETE FROM checklists WHERE id=?", (iid,))
            self._refresh_tasks()
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _build_timeline_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        try:
            with get_conn() as c:
                rows = c.execute("SELECT id,game,version,start_date,end_date,status FROM versions ORDER BY start_date").fetchall()
        except:
            rows = []

        if not rows:
            ctk.CTkLabel(frame, text="暂无版本数据", font=("Microsoft YaHei", 13),
                         text_color=MHY_SUB).pack(pady=30)
            return

        dates = []
        for r in rows:
            try:
                dates.append(datetime.strptime(r[3], "%Y-%m-%d"))
            except:
                dates.append(datetime.now())
            if r[4]:
                try:
                    dates.append(datetime.strptime(r[4], "%Y-%m-%d"))
                except:
                    pass
        if not dates:
            return
        min_d = min(dates)
        max_d = max(dates)
        total_days = max(1, (max_d - min_d).days)
        bar_width = 680

        colors = {"planning":"#f59e0b","preparing":"#06b6d4","live":"#2ecc71","review":"#8b5cf6","closed":"#999"}

        ctk.CTkLabel(frame, text=f"版本时间线  [{min_d.strftime('%m/%d')}  —  {max_d.strftime('%m/%d')}]",
                     font=("Microsoft YaHei", 14, "bold"), text_color="white").pack(anchor="w", pady=(0, 15))

        for r in rows:
            vid, game, ver, start_s, end_s, status = r
            try:
                sd = datetime.strptime(start_s, "%Y-%m-%d")
            except:
                sd = datetime.now()
            try:
                ed = datetime.strptime(end_s, "%Y-%m-%d") if end_s else sd + timedelta(days=42)
            except:
                ed = sd + timedelta(days=42)

            # 进度计算
            with get_conn() as c2:
                total = c2.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (vid,)).fetchone()[0]
                done = c2.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (vid,)).fetchone()[0]
            pct = f"  {done}/{total} ({int(done/total*100) if total else 0}%)" if total else ""

            row_frame = ctk.CTkFrame(frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=6)

            # 左侧版本标签
            label_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=160)
            label_frame.pack(side="left")
            ctk.CTkLabel(label_frame, text=f"{game} {ver}", font=("Microsoft YaHei", 12, "bold"),
                         text_color="white").pack(anchor="w")
            ctk.CTkLabel(label_frame, text=f"{start_s} → {end_s or 'TBD'}{pct}",
                         font=("Microsoft YaHei", 10), text_color=MHY_SUB).pack(anchor="w")

            # 自动风险标记：检测该版本是否有auto-marked风险
            try:
                with get_conn() as c2:
                    risk_count = c2.execute(
                        "SELECT COUNT(*) FROM risks WHERE version_id=? AND title LIKE '%使用率%'", (vid,)
                    ).fetchone()[0]
            except:
                risk_count = 0

            if risk_count > 0:
                # Canvas画小红圈+白色感叹号
                warn = Canvas(label_frame, width=24, height=24, bg="#0f0f1a", highlightthickness=0)
                warn.pack(anchor="w", pady=(2, 0))
                warn.create_oval(2, 2, 22, 22, fill="#ff4d6a", outline="")
                warn.create_text(12, 12, text="!", fill="white", font=("Microsoft YaHei", 11, "bold"))

            # 右侧甘特图条
            bar_frame = ctk.CTkFrame(row_frame, fg_color=MHY_DARK, corner_radius=8, height=28)
            bar_frame.pack(side="left", fill="x", expand=True, padx=(10, 0))

            left_offset = int((sd - min_d).days / total_days * bar_width)
            bar_len = max(30, int((ed - sd).days / total_days * bar_width))
            bar_color = colors.get(status, "#999")

            inner = ctk.CTkFrame(bar_frame, fg_color=bar_color, corner_radius=6, height=22, width=bar_len)
            inner.place(x=left_offset, y=3)
            ctk.CTkLabel(inner, text=f"{game} {ver}", font=("Microsoft YaHei", 9),
                         text_color="white").place(relx=0.5, rely=0.5, anchor="center")

    def _show_version_compare(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("版本对比分析")
        dialog.geometry("750x550")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=MHY_CARD)

        ctk.CTkLabel(dialog, text="版本对比分析", font=("Microsoft YaHei", 16, "bold"),
                     text_color="white").pack(pady=(15, 5))

        try:
            with get_conn() as c:
                vers = c.execute("SELECT id,game,version,start_date,end_date,highlights FROM versions ORDER BY start_date DESC").fetchall()
        except:
            vers = []

        if len(vers) < 2:
            ctk.CTkLabel(dialog, text="需要至少两个版本才能对比（请先创建版本）",
                         font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(pady=30)
            return

        ver_labels = [f"{v[1]} {v[2]} ({v[3]})" for v in vers]
        sel_row = ctk.CTkFrame(dialog, fg_color="transparent")
        sel_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(sel_row, text="版本A", width=50, text_color=MHY_TEXT).pack(side="left")
        a_var = ctk.StringVar(value=ver_labels[0])
        ctk.CTkOptionMenu(sel_row, variable=a_var, values=ver_labels, width=200).pack(side="left", padx=10)
        ctk.CTkLabel(sel_row, text="版本B", width=50, text_color=MHY_TEXT).pack(side="left", padx=(20, 0))
        b_var = ctk.StringVar(value=ver_labels[-1] if len(ver_labels) > 1 else ver_labels[0])
        ctk.CTkOptionMenu(sel_row, variable=b_var, values=ver_labels, width=200).pack(side="left", padx=10)

        result_text = ctk.CTkTextbox(dialog, height=300, fg_color=MHY_DARK,
                                      border_width=1, border_color=MHY_BORDER, text_color=MHY_TEXT,
                                      font=("Microsoft YaHei", 12))
        result_text.pack(fill="both", expand=True, padx=20, pady=15)

        def do_compare():
            idx_a = ver_labels.index(a_var.get())
            idx_b = ver_labels.index(b_var.get())
            if idx_a == idx_b:
                result_text.delete("1.0", "end")
                result_text.insert("1.0", "请选择两个不同的版本进行对比")
                return
            va, vb = vers[idx_a], vers[idx_b]
            with get_conn() as c:
                # 任务
                ta = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (va[0],)).fetchone()[0]
                da = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (va[0],)).fetchone()[0]
                tb = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (vb[0],)).fetchone()[0]
                db = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (vb[0],)).fetchone()[0]
                # 活动
                ev_a = c.execute("SELECT COUNT(*) FROM events WHERE version_id=?", (va[0],)).fetchone()[0]
                ev_b = c.execute("SELECT COUNT(*) FROM events WHERE version_id=?", (vb[0],)).fetchone()[0]
                # 预算
                pa = c.execute("SELECT COALESCE(SUM(planned),0), COALESCE(SUM(actual),0) FROM budgets WHERE version_id=?", (va[0],)).fetchone()
                pb = c.execute("SELECT COALESCE(SUM(planned),0), COALESCE(SUM(actual),0) FROM budgets WHERE version_id=?", (vb[0],)).fetchone()
                # 风险
                ra = c.execute("SELECT COUNT(*) FROM risks WHERE version_id=?", (va[0],)).fetchone()[0]
                rb = c.execute("SELECT COUNT(*) FROM risks WHERE version_id=?", (vb[0],)).fetchone()[0]
                # DAU
                dau_a = c.execute("SELECT AVG(dau) FROM daily_metrics WHERE date>=? AND date<=?",
                                   (va[3], va[4] or va[3])).fetchone()[0] or 0
                dau_b = c.execute("SELECT AVG(dau) FROM daily_metrics WHERE date>=? AND date<=?",
                                   (vb[3], vb[4] or vb[3])).fetchone()[0] or 0
                # 健康分
                hs_a = self._calc_version_health(va[0])
                hs_b = self._calc_version_health(vb[0])

            def arrow(a, b):
                if a > b: return "▲"
                if a < b: return "▼"
                return "—"
            def color(a, b):
                if a > b: return "#2ecc71"
                if a < b: return "#e74c3c"
                return "#888"

            lines = []
            lines.append(f"版本对比: {va[1]} {va[2]}  vs  {vb[1]} {vb[2]}")
            lines.append("=" * 55)
            lines.append("")

            # 任务
            pct_a = int(da/ta*100) if ta else 0
            pct_b = int(db/tb*100) if tb else 0
            lines.append("【任务进度】")
            lines.append(f"  版本A: {da}/{ta} ({pct_a}%)   版本B: {db}/{tb} ({pct_b}%)")
            lines.append(f"  {arrow(pct_a, pct_b)} {pct_a}% vs {pct_b}%")
            lines.append("")

            # 活动
            lines.append("【关联活动】")
            lines.append(f"  版本A: {ev_a} 个   版本B: {ev_b} 个")
            lines.append("")

            # 预算
            planned_a, actual_a = pa
            planned_b, actual_b = pb
            pct_a_b = int(actual_a/planned_a*100) if planned_a else 0
            pct_b_b = int(actual_b/planned_b*100) if planned_b else 0
            lines.append("【预算执行】")
            lines.append(f"  版本A: {actual_a:,.0f} / {planned_a:,.0f} ({pct_a_b}%)")
            lines.append(f"  版本B: {actual_b:,.0f} / {planned_b:,.0f} ({pct_b_b}%)")
            if planned_a and planned_b:
                lines.append(f"  预算总额: {arrow(planned_a, planned_b)} ¥{planned_a:,.0f} vs ¥{planned_b:,.0f}")
            lines.append("")

            # 风险
            lines.append("【风险项】")
            lines.append(f"  版本A: {ra} 个   版本B: {rb} 个  {arrow(rb, ra)}")
            lines.append("")

            # DAU
            lines.append("【平均 DAU】")
            lines.append(f"  版本A: {int(dau_a):,}   版本B: {int(dau_b):,}  {arrow(int(dau_a), int(dau_b))}")
            lines.append("")

            # 健康分
            lines.append("【健康度评分】")
            sa = int(hs_a*100) if hs_a else 0
            sb = int(hs_b*100) if hs_b else 0
            verdict_a = "健康" if sa >= 80 else ("一般" if sa >= 60 else "需关注")
            verdict_b = "健康" if sb >= 80 else ("一般" if sb >= 60 else "需关注")
            lines.append(f"  版本A: {sa}% ({verdict_a})   版本B: {sb}% ({verdict_b})")

            result_text.delete("1.0", "end")
            result_text.insert("1.0", "\n".join(lines))
            result_text.delete("1.0", "end")
            result_text.insert("1.0", "\n".join(lines))

        ctk.CTkButton(dialog, text="📊 开始对比", fg_color=MHY_RED, hover_color="#e0415c",
                      command=do_compare).pack(pady=(0, 15))
