"""排期/预算/风险三合一 Mixin"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import datetime
from db import get_conn
from theme import BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM, ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER

class PlansMixin:
    def create_plans(self, parent):
        nb = ctk.CTkTabview(parent, fg_color=BG_CARD)
        nb.pack(fill="both", expand=True, padx=4, pady=4)
        t1 = nb.add("排期")
        t2 = nb.add("预算")
        t3 = nb.add("风险")
        self._build_schedule(t1)
        self._build_budget(t2)
        self._build_risk(t3)
        self._refresh_plans()

    def _build_schedule(self, parent):
        top = ctk.CTkFrame(parent, fg_color=BG_CARD)
        top.pack(fill="x", padx=4, pady=4)
        ctk.CTkButton(top, text="添加节点", width=100, command=self._add_schedule_node).pack(side="left", padx=4)
        ctk.CTkButton(top, text="刷新", width=60, command=self._refresh_plans).pack(side="left", padx=4)
        cols = ("id", "task", "deadline", "status")
        self._sched_tree = ttk.Treeview(parent, columns=cols, show="headings", height=15, style="Dark.Treeview")
        labels = {"id":"ID","task":"节点","deadline":"截止日期","status":"状态"}
        for c in cols:
            self._sched_tree.heading(c, text=labels[c])
            self._sched_tree.column(c, width=200 if c == "task" else 120, anchor="center")
        self._sched_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self._sched_tree.bind("<Double-1>", lambda e: self._toggle_schedule())

    def _build_budget(self, parent):
        top = ctk.CTkFrame(parent, fg_color=BG_CARD)
        top.pack(fill="x", padx=4, pady=4)
        cats = ["推广", "素材", "外包", "活动奖品", "线下"]
        ctk.CTkLabel(top, text="分类:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._bud_cat = ctk.StringVar(value=cats[0])
        ctk.CTkOptionMenu(top, variable=self._bud_cat, values=cats, width=100, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkLabel(top, text="项目:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._bud_name = ctk.StringVar()
        ctk.CTkEntry(top, textvariable=self._bud_name, width=120, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkLabel(top, text="计划:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._bud_plan = ctk.StringVar()
        ctk.CTkEntry(top, textvariable=self._bud_plan, width=80, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkLabel(top, text="实际:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._bud_actual = ctk.StringVar()
        ctk.CTkEntry(top, textvariable=self._bud_actual, width=80, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkButton(top, text="添加", width=60, command=self._add_budget).pack(side="left", padx=4)
        cols = ("id", "category", "item", "planned", "actual", "diff", "rate")
        self._bud_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12, style="Dark.Treeview")
        labels = {"id":"ID","category":"分类","item":"项目","planned":"计划","actual":"实际","diff":"差额","rate":"使用率"}
        for c in cols:
            self._bud_tree.heading(c, text=labels[c])
            self._bud_tree.column(c, width=100, anchor="center")
        self._bud_tree.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_risk(self, parent):
        top = ctk.CTkFrame(parent, fg_color=BG_CARD)
        top.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(top, text="风险标题:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._risk_title = ctk.StringVar()
        ctk.CTkEntry(top, textvariable=self._risk_title, width=120, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkLabel(top, text="概率(1-5):", fg_color=BG_CARD).pack(side="left", padx=2)
        self._risk_prob = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(top, variable=self._risk_prob, values=["1","2","3","4","5"], width=50, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkLabel(top, text="影响(1-5):", fg_color=BG_CARD).pack(side="left", padx=2)
        self._risk_imp = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(top, variable=self._risk_imp, values=["1","2","3","4","5"], width=50, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkLabel(top, text="负责人:", fg_color=BG_CARD).pack(side="left", padx=2)
        self._risk_owner = ctk.StringVar()
        ctk.CTkEntry(top, textvariable=self._risk_owner, width=80, fg_color=BG_INPUT, text_color=FG_TEXT).pack(side="left", padx=2)
        ctk.CTkButton(top, text="添加", width=60, command=self._add_risk).pack(side="left", padx=4)
        cols = ("id", "title", "prob", "imp", "score", "level", "owner", "status")
        self._risk_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12, style="Dark.Treeview")
        labels = {"id":"ID","title":"风险","prob":"概率","imp":"影响","score":"分值","level":"等级","owner":"负责人","status":"状态"}
        for c in cols:
            self._risk_tree.heading(c, text=labels[c])
            self._risk_tree.column(c, width=90, anchor="center")
        self._risk_tree.pack(fill="both", expand=True, padx=4, pady=4)
        ctk.CTkLabel(parent, text="风险分值 = 概率 × 影响  |  ≥15 高危(红)  ≥8 中危(橙)  <8 低危(绿)",
                     fg_color=BG_CARD, text_color=FG_DIM, font=("Microsoft YaHei", 9)).pack(pady=2)

    def _refresh_plans(self):
        for item in self._sched_tree.get_children():
            self._sched_tree.delete(item)
        for item in self._bud_tree.get_children():
            self._bud_tree.delete(item)
        for item in self._risk_tree.get_children():
            self._risk_tree.delete(item)
        with get_conn() as c:
            for row in c.execute("SELECT id,task,deadline,status FROM checklists WHERE deadline != '' AND deadline IS NOT NULL ORDER BY deadline"):
                self._sched_tree.insert("", "end", values=row, tags=("done",) if row[3] == "done" else ())
            total_plan = total_actual = 0
            for row in c.execute("SELECT id,category,item_name,planned,actual FROM budgets ORDER BY id"):
                diff = (row[4] or 0) - (row[3] or 0)
                rate = f"{(row[4] or 0)/(row[3] or 1)*100:.0f}%" if row[3] else "-"
                tag = "over" if diff > 0 else "ok"
                self._bud_tree.insert("", "end", values=(row[0], row[1], row[2], row[3] or 0, row[4] or 0, f"{diff:+.0f}", rate), tags=(tag,))
                total_plan += row[3] or 0
                total_actual += row[4] or 0
            if total_plan:
                self._bud_tree.insert("", "end", values=("", "合计", "", total_plan, total_actual, f"{total_actual-total_plan:+.0f}", f"{total_actual/total_plan*100:.0f}%"), tags=("total",))
            for row in c.execute("SELECT id,title,probability,impact,owner,status FROM risks ORDER BY probability*impact DESC"):
                score = row[2] * row[3]
                level = "高" if score >= 15 else ("中" if score >= 8 else "低")
                self._risk_tree.insert("", "end", values=(row[0], row[1], row[2], row[3], score, level, row[4] or "", row[5]), tags=(level,))
        self._sched_tree.tag_configure("done", foreground=SUCCESS)
        self._bud_tree.tag_configure("over", foreground=DANGER)
        self._bud_tree.tag_configure("ok", foreground=SUCCESS)
        self._bud_tree.tag_configure("total", foreground=ACCENT)
        self._risk_tree.tag_configure("高", foreground=DANGER)
        self._risk_tree.tag_configure("中", foreground=WARNING)
        self._risk_tree.tag_configure("低", foreground=SUCCESS)

    def _add_schedule_node(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("添加排期节点")
        dlg.geometry("340x200")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="节点名称:").pack(pady=4)
        name_e = ctk.CTkEntry(dlg, width=220)
        name_e.pack(pady=4)
        ctk.CTkLabel(dlg, text="截止日期:").pack(pady=2)
        dl_e = ctk.CTkEntry(dlg, width=220)
        dl_e.insert(0, datetime.date.today().isoformat())
        dl_e.pack(pady=2)
        def save():
            with get_conn() as conn:
                conn.execute("INSERT INTO checklists(version_id,task,deadline,status) VALUES(0,?,?,'pending')",
                             (name_e.get(), dl_e.get()))
            self._save_log("add_schedule", name_e.get())
            self._toast("节点已添加")
            dlg.destroy()
            self._refresh_plans()
        ctk.CTkButton(dlg, text="保存", command=save).pack(pady=8)

    def _toggle_schedule(self):
        sel = self._sched_tree.selection()
        if not sel:
            return
        cid = self._sched_tree.item(sel[0])["values"][0]
        cur = self._sched_tree.item(sel[0])["values"][3]
        new_st = "done" if cur != "done" else "pending"
        with get_conn() as conn:
            conn.execute("UPDATE checklists SET status=? WHERE id=?", (new_st, cid))
        self._refresh_plans()

    def _add_budget(self):
        name = self._bud_name.get().strip()
        if not name:
            self._toast("请输入项目名称")
            return
        try:
            plan = float(self._bud_plan.get() or 0)
            actual = float(self._bud_actual.get() or 0)
        except ValueError:
            self._toast("计划/实际必须是数字")
            return
        with get_conn() as conn:
            conn.execute("INSERT INTO budgets(version_id,category,item_name,planned,actual) VALUES(0,?,?,?,?)",
                         (self._bud_cat.get(), name, plan, actual))
        self._save_log("add_budget", name)
        self._toast("预算项已添加")
        self._bud_name.set("")
        self._bud_plan.set("")
        self._bud_actual.set("")
        self._refresh_plans()

    def _add_risk(self):
        title = self._risk_title.get().strip()
        if not title:
            self._toast("请输入风险标题")
            return
        prob = int(self._risk_prob.get())
        imp = int(self._risk_imp.get())
        with get_conn() as conn:
            conn.execute("INSERT INTO risks(version_id,title,probability,impact,owner,status) VALUES(0,?,?,?,?,?,'open')",
                         (title, prob, imp, self._risk_owner.get()))
        self._save_log("add_risk", title)
        score = prob * imp
        level = "高危" if score >= 15 else ("中危" if score >= 8 else "低危")
        self._toast(f"风险已添加（{level}，分值{score}）")
        self._risk_title.set("")
        self._refresh_plans()
