"""版本管理 Mixin：看板/清单/时间线/排期/预算/风险六标签页 + 双版本对比"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
from db import get_conn
from theme import BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM, ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER

class VersionsMixin:
    def create_versions(self, parent):
        self._v_games = ["崩坏：星穹铁道", "原神", "绝区零", "崩坏3", "未定事件簿", "崩坏：因缘精灵"]
        nb = ctk.CTkTabview(parent, fg_color=BG_CARD)
        nb.pack(fill="both", expand=True, padx=4, pady=4)
        t1 = nb.add("看板")
        t2 = nb.add("清单")
        t3 = nb.add("时间线")
        t4 = nb.add("对比")
        self._build_v_board(t1)
        self._build_v_checklist(t2)
        self._build_v_timeline(t3)
        self._build_v_compare(t4)
        self._refresh_versions()

    def _build_v_board(self, parent):
        top = ctk.CTkFrame(parent, fg_color=BG_CARD)
        top.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(top, text="游戏:", fg_color=BG_CARD).pack(side="left", padx=4)
        self._v_game_var = ctk.StringVar(value=self._v_games[0])
        ctk.CTkOptionMenu(top, variable=self._v_game_var, values=self._v_games, width=160, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=4)
        ctk.CTkButton(top, text="新增版本", width=100, command=self._add_version).pack(side="left", padx=4)
        ctk.CTkButton(top, text="编辑", width=60, command=self._edit_version).pack(side="left", padx=4)
        ctk.CTkButton(top, text="删除", width=60, fg_color=DANGER, command=self._delete_version).pack(side="left", padx=4)
        ctk.CTkButton(top, text="版本模板", width=100, command=self._use_template).pack(side="left", padx=4)
        cols = ("id", "game", "version", "start_date", "end_date", "status", "progress")
        self._v_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12, style="Dark.Treeview")
        for c in cols:
            self._v_tree.heading(c, text=c.upper() if c != "start_date" else "开始")
            self._v_tree.column(c, width=110, anchor="center")
        self._v_tree.pack(fill="both", expand=True, padx=4, pady=4)
        ysb = ttk.Scrollbar(parent, orient="vertical", command=self._v_tree.yview, style="Dark.Vertical.TScrollbar")
        self._v_tree.configure(yscrollcommand=ysb.set)
        ysb.pack(side="right", fill="y")

    def _build_v_checklist(self, parent):
        top = ctk.CTkFrame(parent, fg_color=BG_CARD)
        top.pack(fill="x", padx=4, pady=4)
        ctk.CTkButton(top, text="添加任务", width=100, command=self._add_checklist_item).pack(side="left", padx=4)
        ctk.CTkButton(top, text="刷新", width=60, command=self._refresh_versions).pack(side="left", padx=4)
        cols = ("id", "task", "assignee", "deadline", "status")
        self._cl_tree = ttk.Treeview(parent, columns=cols, show="headings", height=15, style="Dark.Treeview")
        for c in cols:
            self._cl_tree.heading(c, text={"id":"ID","task":"任务","assignee":"负责人","deadline":"截止","status":"状态"}[c])
            self._cl_tree.column(c, width=150 if c == "task" else 100, anchor="center")
        self._cl_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self._cl_tree.bind("<Double-1>", lambda e: self._toggle_checklist())
        ctk.CTkLabel(parent, text="双击切换完成状态", fg_color=BG_CARD, text_color=FG_DIM, font=("Microsoft YaHei", 9)).pack(pady=2)

    def _build_v_timeline(self, parent):
        self._tl_canvas = tk.Canvas(parent, bg=BG_DARK, highlightthickness=0)
        self._tl_canvas.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_v_compare(self, parent):
        top = ctk.CTkFrame(parent, fg_color=BG_CARD)
        top.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(top, text="版本A:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._cmp_a = ctk.StringVar()
        ctk.CTkOptionMenu(top, variable=self._cmp_a, values=[], width=180, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=4)
        ctk.CTkLabel(top, text="版本B:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._cmp_b = ctk.StringVar()
        ctk.CTkOptionMenu(top, variable=self._cmp_b, values=[], width=180, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=4)
        ctk.CTkButton(top, text="对比", width=60, command=self._compare_versions).pack(side="left", padx=4)
        self._cmp_text = ctk.CTkTextbox(parent, fg_color=BG_INPUT, text_color=FG_TEXT, font=("Microsoft YaHei", 10))
        self._cmp_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _refresh_versions(self):
        for item in self._v_tree.get_children():
            self._v_tree.delete(item)
        for item in self._cl_tree.get_children():
            self._cl_tree.delete(item)
        game = self._v_game_var.get()
        v_ids = []
        v_labels = []
        with get_conn() as c:
            for row in c.execute("SELECT id,game,version,start_date,end_date,status FROM versions WHERE game=? ORDER BY id DESC", (game,)):
                v_ids.append(row[0])
                v_labels.append(f"{row[2]} ({row[3] or '?'})")
                total = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (row[0],)).fetchone()[0]
                done = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (row[0],)).fetchone()[0]
                prog = f"{done}/{total}" if total else "0/0"
                self._v_tree.insert("", "end", values=(row[0], row[1], row[2], row[3] or "", row[4] or "", row[5], prog))
            for row in c.execute("SELECT id,task,assignee,deadline,status FROM checklists ORDER BY id DESC LIMIT 50"):
                self._cl_tree.insert("", "end", values=row, tags=("done",) if row[4] == "done" else ())
        self._tl_draw(v_ids)

    def _tl_draw(self, v_ids):
        self._tl_canvas.delete("all")
        if not v_ids:
            self._tl_canvas.create_text(200, 100, text="暂无版本数据", fill=FG_DIM, font=("Microsoft YaHei", 12))
            return
        y = 30
        bar_h = 28
        gap = 10
        x_start = 150
        max_w = 700
        with get_conn() as c:
            for vid in v_ids:
                row = c.execute("SELECT version,start_date,end_date,status FROM versions WHERE id=?", (vid,)).fetchone()
                if not row:
                    continue
                ver, sd, ed, st = row
                self._tl_canvas.create_text(10, y + bar_h // 2, text=ver, fill=FG_TEXT, font=("Microsoft YaHei", 9), anchor="w")
                color = {"planning": WARNING, "ongoing": ACCENT, "done": SUCCESS}.get(st, FG_DIM)
                w = max_w if sd and ed else 200
                self._tl_canvas.create_rectangle(x_start, y, x_start + w, y + bar_h, fill=color, outline="")
                self._tl_canvas.create_text(x_start + w // 2, y + bar_h // 2, text=f"{sd or '?'} → {ed or '?'}", fill="#fff", font=("Microsoft YaHei", 8))
                y += bar_h + gap

    def _add_version(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("新增版本")
        dlg.geometry("380x280")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="游戏:").pack(pady=4)
        game_var = ctk.StringVar(value=self._v_game_var.get())
        ctk.CTkOptionMenu(dlg, variable=game_var, values=self._v_games, width=200).pack(pady=4)
        ctk.CTkLabel(dlg, text="版本号:").pack(pady=2)
        ver_entry = ctk.CTkEntry(dlg, width=200)
        ver_entry.pack(pady=2)
        ctk.CTkLabel(dlg, text="开始日期:").pack(pady=2)
        sd_entry = ctk.CTkEntry(dlg, width=200)
        sd_entry.insert(0, datetime.date.today().isoformat())
        sd_entry.pack(pady=2)
        ctk.CTkLabel(dlg, text="结束日期:").pack(pady=2)
        ed_entry = ctk.CTkEntry(dlg, width=200)
        ed_entry.pack(pady=2)
        def save():
            with get_conn() as conn:
                conn.execute("INSERT INTO versions(game,version,start_date,end_date,status) VALUES(?,?,?,?,?)",
                             (game_var.get(), ver_entry.get(), sd_entry.get(), ed_entry.get(), "planning"))
            self._save_log("add_version", ver_entry.get())
            self._toast(f"版本 {ver_entry.get()} 已添加")
            dlg.destroy()
            self._refresh_versions()
        ctk.CTkButton(dlg, text="保存", command=save).pack(pady=8)

    def _edit_version(self):
        sel = self._v_tree.selection()
        if not sel:
            self._toast("请先选择一行")
            return
        vid = self._v_tree.item(sel[0])["values"][0]
        with get_conn() as c:
            row = c.execute("SELECT game,version,start_date,end_date,status FROM versions WHERE id=?", (vid,)).fetchone()
        if not row:
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("编辑版本")
        dlg.geometry("380x300")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="游戏:").pack(pady=4)
        game_var = ctk.StringVar(value=row[0])
        ctk.CTkOptionMenu(dlg, variable=game_var, values=self._v_games, width=200).pack(pady=4)
        ctk.CTkLabel(dlg, text="版本号:").pack(pady=2)
        ver_entry = ctk.CTkEntry(dlg, width=200)
        ver_entry.insert(0, row[1])
        ver_entry.pack(pady=2)
        ctk.CTkLabel(dlg, text="开始日期:").pack(pady=2)
        sd_entry = ctk.CTkEntry(dlg, width=200)
        sd_entry.insert(0, row[2] or "")
        sd_entry.pack(pady=2)
        ctk.CTkLabel(dlg, text="结束日期:").pack(pady=2)
        ed_entry = ctk.CTkEntry(dlg, width=200)
        ed_entry.insert(0, row[3] or "")
        ed_entry.pack(pady=2)
        ctk.CTkLabel(dlg, text="状态:").pack(pady=2)
        st_var = ctk.StringVar(value=row[4])
        ctk.CTkOptionMenu(dlg, variable=st_var, values=["planning", "ongoing", "done"], width=200).pack(pady=2)
        def save():
            with get_conn() as conn:
                conn.execute("UPDATE versions SET game=?,version=?,start_date=?,end_date=?,status=? WHERE id=?",
                             (game_var.get(), ver_entry.get(), sd_entry.get(), ed_entry.get(), st_var.get(), vid))
            self._save_log("edit_version", ver_entry.get())
            self._toast("版本已更新")
            dlg.destroy()
            self._refresh_versions()
        ctk.CTkButton(dlg, text="保存", command=save).pack(pady=8)

    def _delete_version(self):
        sel = self._v_tree.selection()
        if not sel:
            self._toast("请先选择一行")
            return
        vid = self._v_tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("确认", "确认删除该版本及关联数据？"):
            return
        with get_conn() as conn:
            conn.execute("DELETE FROM checklists WHERE version_id=?", (vid,))
            conn.execute("DELETE FROM budgets WHERE version_id=?", (vid,))
            conn.execute("DELETE FROM risks WHERE version_id=?", (vid,))
            conn.execute("DELETE FROM versions WHERE id=?", (vid,))
        self._save_log("delete_version", str(vid))
        self._toast("版本已删除")
        self._refresh_versions()

    def _add_checklist_item(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("添加任务")
        dlg.geometry("360x200")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="任务:").pack(pady=4)
        task_entry = ctk.CTkEntry(dlg, width=240)
        task_entry.pack(pady=4)
        ctk.CTkLabel(dlg, text="负责人:").pack(pady=2)
        assignee_entry = ctk.CTkEntry(dlg, width=240)
        assignee_entry.pack(pady=2)
        ctk.CTkLabel(dlg, text="截止日期:").pack(pady=2)
        deadline_entry = ctk.CTkEntry(dlg, width=240)
        deadline_entry.pack(pady=2)
        def save():
            with get_conn() as conn:
                conn.execute("INSERT INTO checklists(version_id,task,assignee,deadline,status) VALUES(0,?,?,?,'pending')",
                             (task_entry.get(), assignee_entry.get(), deadline_entry.get()))
            self._save_log("add_checklist", task_entry.get())
            self._toast("任务已添加")
            dlg.destroy()
            self._refresh_versions()
        ctk.CTkButton(dlg, text="保存", command=save).pack(pady=8)

    def _toggle_checklist(self):
        sel = self._cl_tree.selection()
        if not sel:
            return
        cid = self._cl_tree.item(sel[0])["values"][0]
        cur = self._cl_tree.item(sel[0])["values"][4]
        new_st = "done" if cur != "done" else "pending"
        with get_conn() as conn:
            conn.execute("UPDATE checklists SET status=? WHERE id=?", (new_st, cid))
        self._refresh_versions()

    def _use_template(self):
        template = [
            "版本规划评审", "美术资源确认", "前端开发完成", "后端接口联调",
            "QA测试一轮", "QA测试二轮", "灰度发布", "全量发布", "舆情监控", "版本复盘"
        ]
        with get_conn() as conn:
            for t in template:
                conn.execute("INSERT INTO checklists(version_id,task,status) VALUES(0,?,'pending')", (t,))
        self._save_log("use_template", "版本模板")
        self._toast(f"已添加 {len(template)} 个模板任务")
        self._refresh_versions()

    def _compare_versions(self):
        a = self._cmp_a.get()
        b = self._cmp_b.get()
        if not a or not b or a == b:
            self._toast("请选择两个不同版本")
            return
        self._cmp_text.delete("1.0", "end")
        def parse(label):
            return label.split(" (")[0]
        va, vb = parse(a), parse(b)
        with get_conn() as c:
            ra = c.execute("SELECT id,start_date,end_date,status FROM versions WHERE version=?", (va,)).fetchone()
            rb = c.execute("SELECT id,start_date,end_date,status FROM versions WHERE version=?", (vb,)).fetchone()
            if not ra or not rb:
                self._cmp_text.insert("end", "版本数据不存在")
                return
            ta = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (ra[0],)).fetchone()[0]
            da = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (ra[0],)).fetchone()[0]
            tb = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=?", (rb[0],)).fetchone()[0]
            db_ = c.execute("SELECT COUNT(*) FROM checklists WHERE version_id=? AND status='done'", (rb[0],)).fetchone()[0]
        txt = f"══ 版本对比 ══\n\n"
        txt += f"{'指标':<12}{'版本A':<20}{'版本B':<20}\n"
        txt += f"{'版本号':<12}{va:<20}{vb:<20}\n"
        txt += f"{'开始日期':<12}{ra[1] or '-':<20}{rb[1] or '-':<20}\n"
        txt += f"{'结束日期':<12}{ra[2] or '-':<20}{rb[2] or '-':<20}\n"
        txt += f"{'状态':<12}{ra[3]:<20}{rb[3]:<20}\n"
        txt += f"{'任务总数':<12}{ta:<20}{tb:<20}\n"
        txt += f"{'完成数':<12}{da:<20}{db_:<20}\n"
        txt += f"{'完成率':<12}{f'{da}/{ta}={da/ta*100:.0f}%' if ta else '-':<20}{f'{db_}/{tb}={db_/tb*100:.0f}%' if tb else '-':<20}\n"
        self._cmp_text.insert("end", txt)
