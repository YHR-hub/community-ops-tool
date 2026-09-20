from tkinter import messagebox, StringVar
import customtkinter as ctk

from db import get_conn, load_config, save_config, GAMES, date_str
from theme import MHY_RED, MHY_DARK, MHY_CARD, MHY_BORDER, MHY_TEXT, MHY_SUB


class PlansMixin:
    # ═══════════════════════════════════════════
    #   排期管理 (Schedule)
    # ═══════════════════════════════════════════
    def _build_schedule_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="版本排期管理", font=("Microsoft YaHei", 15, "bold"),
                     text_color="white").pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(frame, text="按阶段规划版本上线前的时间节点",
                     font=("Microsoft YaHei", 11), text_color=MHY_SUB).pack(anchor="w", pady=(0, 15))

        # 选择版本
        with get_conn() as c:
            vers = c.execute("SELECT id,game,version,start_date,end_date FROM versions ORDER BY start_date DESC").fetchall()

        if not vers:
            ctk.CTkLabel(frame, text="暂无版本，请先创建版本",
                         font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(pady=30)
            return

        ver_labels = [f"{v[1]} {v[2]} ({v[3]})" for v in vers]
        sel_row = ctk.CTkFrame(frame, fg_color="transparent")
        sel_row.pack(fill="x")
        ctk.CTkLabel(sel_row, text="版本", width=60, text_color=MHY_TEXT).pack(side="left")
        sch_ver_var = StringVar(value=ver_labels[0])
        ctk.CTkOptionMenu(sel_row, variable=sch_ver_var, values=ver_labels, width=250).pack(side="left", padx=10)
        self._sch_ver_map = {f"{v[1]} {v[2]} ({v[3]})": v for v in vers}

        # 新增排期阶段
        add_row = ctk.CTkFrame(frame, fg_color=MHY_CARD, corner_radius=10,
                                border_width=1, border_color=MHY_BORDER)
        add_row.pack(fill="x", pady=15)

        ctk.CTkLabel(add_row, text="新增排期阶段", font=("Microsoft YaHei", 13, "bold"),
                     text_color="white").pack(anchor="w", padx=15, pady=(10, 5))

        row1 = ctk.CTkFrame(add_row, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row1, text="阶段名称", width=80, text_color=MHY_TEXT).pack(side="left")
        self.sch_name = ctk.CTkEntry(row1, width=200, placeholder_text="如：PV发布 / 预约开放 / 上线")
        self.sch_name.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="开始", width=50, text_color=MHY_TEXT).pack(side="left")
        self.sch_start = ctk.CTkEntry(row1, width=120, placeholder_text="YYYY-MM-DD")
        self.sch_start.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="结束", width=50, text_color=MHY_TEXT).pack(side="left")
        self.sch_end = ctk.CTkEntry(row1, width=120, placeholder_text="YYYY-MM-DD")
        self.sch_end.pack(side="left", padx=5)
        ctk.CTkButton(row1, text="➕ 添加", fg_color=MHY_RED, hover_color="#e0415c",
                      command=lambda: self._add_schedule(sch_ver_var.get()), width=80).pack(side="right")

        self.sch_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.sch_container.pack(fill="both", expand=True, pady=10)
        self._refresh_schedules(sch_ver_var.get())

    def _add_schedule(self, ver_label):
        v = self._sch_ver_map.get(ver_label)
        if not v or not self.sch_name.get():
            messagebox.showwarning("提示", "请填写阶段名称")
            return
        try:
            with get_conn() as c:
                c.execute("INSERT INTO checklists (version_id,task,assignee,deadline) VALUES (?,?,?,?)",
                          (v[0], f"[排期] {self.sch_name.get()}", "",
                           self.sch_end.get() or self.sch_start.get()))
            self.sch_name.delete(0, "end")
            self._refresh_schedules(ver_label)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _refresh_schedules(self, ver_label):
        for w in self.sch_container.winfo_children():
            w.destroy()
        v = self._sch_ver_map.get(ver_label)
        if not v:
            return
        with get_conn() as c:
            items = c.execute("SELECT id,task,deadline,status FROM checklists WHERE version_id=? AND task LIKE '[排期] %' ORDER BY id",
                              (v[0],)).fetchall()
        if not items:
            ctk.CTkLabel(self.sch_container, text="暂无排期阶段，请添加",
                         font=("Microsoft YaHei", 12), text_color=MHY_SUB).pack(pady=20)
            return
        for item in items:
            iid, task, deadline, status = item
            done = status == "done"
            card = ctk.CTkFrame(self.sch_container, fg_color=MHY_CARD, corner_radius=8,
                                border_width=1, border_color=MHY_BORDER)
            card.pack(fill="x", pady=3)

            var = ctk.BooleanVar(value=done)
            ctk.CTkCheckBox(card, text="", variable=var,
                            command=lambda iid=iid, v=var: self._toggle_task(iid, v)).pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(card, text=task.replace("[排期] ", ""),
                         font=("Microsoft YaHei", 13),
                         text_color=MHY_SUB if done else MHY_TEXT).pack(side="left", padx=5)
            if deadline:
                ctk.CTkLabel(card, text=f"📅 {deadline}", font=("Microsoft YaHei", 11),
                             text_color=MHY_SUB).pack(side="right", padx=10)
            ctk.CTkButton(card, text="🗑", fg_color="transparent", hover_color="#c0392b",
                          text_color="#e74c3c", width=30, height=24, font=("Microsoft YaHei", 10),
                          command=lambda iid=iid: self._delete_task(iid)).pack(side="right", padx=5)

    # ═══════════════════════════════════════════
    #   预算管理 (Budget)
    # ═══════════════════════════════════════════
    def _build_budget_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="预算管理", font=("Microsoft YaHei", 15, "bold"),
                     text_color="white").pack(anchor="w", pady=(0, 10))

        with get_conn() as c:
            vers = c.execute("SELECT id,game,version,start_date,end_date FROM versions ORDER BY start_date DESC").fetchall()
        if not vers:
            ctk.CTkLabel(frame, text="暂无版本", font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(pady=30)
            return

        ver_labels = [f"{v[1]} {v[2]} ({v[3]})" for v in vers]
        self._bud_ver_map = {f"{v[1]} {v[2]} ({v[3]})": v for v in vers}

        sel_row = ctk.CTkFrame(frame, fg_color="transparent")
        sel_row.pack(fill="x")
        self.bud_ver_var = StringVar(value=ver_labels[0])
        ctk.CTkLabel(sel_row, text="版本", width=60, text_color=MHY_TEXT).pack(side="left")
        ctk.CTkOptionMenu(sel_row, variable=self.bud_ver_var, values=ver_labels, width=250,
                          command=lambda _: self._refresh_budgets()).pack(side="left", padx=10)

        # 汇总
        self.budget_summary = ctk.CTkLabel(frame, text="", font=("Microsoft YaHei", 13, "bold"),
                                            text_color=MHY_RED)
        self.budget_summary.pack(anchor="w", pady=(10, 5))

        # 新增预算项
        add_row = ctk.CTkFrame(frame, fg_color=MHY_CARD, corner_radius=10,
                                border_width=1, border_color=MHY_BORDER)
        add_row.pack(fill="x", pady=10)

        ctk.CTkLabel(add_row, text="新增预算项", font=("Microsoft YaHei", 13, "bold"),
                     text_color="white").pack(anchor="w", padx=15, pady=(10, 5))

        row1 = ctk.CTkFrame(add_row, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row1, text="类别", width=60, text_color=MHY_TEXT).pack(side="left")
        self.bud_cat = ctk.CTkOptionMenu(row1, values=["推广","素材","外包","活动奖品","线下","其他"], width=120)
        self.bud_cat.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="项目名", width=60, text_color=MHY_TEXT).pack(side="left", padx=5)
        self.bud_name = ctk.CTkEntry(row1, width=180, placeholder_text="如：B站KOL投放")
        self.bud_name.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="预算(元)", width=70, text_color=MHY_TEXT).pack(side="left", padx=5)
        self.bud_planned = ctk.CTkEntry(row1, width=100, placeholder_text="50000")
        self.bud_planned.pack(side="left", padx=5)
        self.bud_actual = ctk.CTkEntry(row1, width=100, placeholder_text="实际支出")
        self.bud_actual.pack(side="left", padx=5)
        ctk.CTkButton(row1, text="➕", fg_color=MHY_RED, hover_color="#e0415c",
                      command=self._add_budget, width=40).pack(side="left", padx=5)

        self.bud_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.bud_container.pack(fill="both", expand=True, pady=10)
        self._refresh_budgets()

    def _add_budget(self):
        v = self._bud_ver_map.get(self.bud_ver_var.get())
        if not v or not self.bud_name.get():
            return
        try:
            with get_conn() as c:
                c.execute("INSERT INTO budgets (version_id,category,item_name,planned,actual) VALUES (?,?,?,?,?)",
                          (v[0], self.bud_cat.get(), self.bud_name.get(),
                           float(self.bud_planned.get() or 0), float(self.bud_actual.get() or 0)))
            self.bud_name.delete(0, "end")
            self.bud_planned.delete(0, "end")
            self.bud_actual.delete(0, "end")
            self._refresh_budgets()
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _refresh_budgets(self):
        for w in self.bud_container.winfo_children():
            w.destroy()
        v = self._bud_ver_map.get(self.bud_ver_var.get())
        if not v:
            return
        with get_conn() as c:
            items = c.execute("SELECT id,category,item_name,planned,actual FROM budgets WHERE version_id=? ORDER BY category,id",
                              (v[0],)).fetchall()
        if not items:
            ctk.CTkLabel(self.bud_container, text="暂无预算项，请添加",
                         font=("Microsoft YaHei", 12), text_color=MHY_SUB).pack(pady=20)
            self.budget_summary.configure(text="")
            return

        total_planned = sum(r[3] for r in items)
        total_actual = sum(r[4] for r in items)
        pct = int(total_actual/total_planned*100) if total_planned else 0
        self.budget_summary.configure(
            text=f"预算总计: {total_planned:,.0f} 元 | 实际: {total_actual:,.0f} 元 | 使用率: {pct}%")

        for item in items:
            iid, cat, name, planned, actual = item
            card = ctk.CTkFrame(self.bud_container, fg_color=MHY_CARD, corner_radius=8,
                                border_width=1, border_color=MHY_BORDER)
            card.pack(fill="x", pady=3)

            pct_item = int(actual/planned*100) if planned else 0
            color = "#2ecc71" if pct_item <= 100 else "#e74c3c"

            ctk.CTkLabel(card, text=f"[{cat}] {name}",
                         font=("Microsoft YaHei", 12), text_color=MHY_TEXT).pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(card, text=f"预算: {planned:,.0f} | 实际: {actual:,.0f}",
                         font=("Microsoft YaHei", 11), text_color=MHY_SUB).pack(side="left", padx=10)
            ctk.CTkLabel(card, text=f"{pct_item}%", font=("Microsoft YaHei", 12, "bold"),
                         text_color=color).pack(side="right", padx=15)
            ctk.CTkButton(card, text="🗑", fg_color="transparent", hover_color="#c0392b",
                          text_color="#e74c3c", width=30, height=24, font=("Microsoft YaHei", 10),
                          command=lambda iid=iid: self._delete_budget(iid)).pack(side="right", padx=5)

    def _delete_budget(self, iid):
        if not messagebox.askyesno("确认", "删除此预算项？"):
            return
        with get_conn() as c:
            c.execute("DELETE FROM budgets WHERE id=?", (iid,))
        self._refresh_budgets()

    # ═══════════════════════════════════════════
    #   风险预案 (Risk)
    # ═══════════════════════════════════════════
    def _build_risk_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="风险预案", font=("Microsoft YaHei", 15, "bold"),
                     text_color="white").pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(frame, text="识别版本风险并制定应对策略",
                     font=("Microsoft YaHei", 11), text_color=MHY_SUB).pack(anchor="w", pady=(0, 15))

        # 自动标记风险按钮
        auto_row = ctk.CTkFrame(frame, fg_color="transparent")
        auto_row.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(auto_row, text="🔍 自动标记风险", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                      text_color=MHY_TEXT, width=140, height=30,
                      command=self._auto_mark_risks).pack(side="left")

        with get_conn() as c:
            vers = c.execute("SELECT id,game,version,start_date,end_date FROM versions ORDER BY start_date DESC").fetchall()
        if not vers:
            ctk.CTkLabel(frame, text="暂无版本", font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(pady=30)
            return

        ver_labels = [f"{v[1]} {v[2]} ({v[3]})" for v in vers]
        self._risk_ver_map = {f"{v[1]} {v[2]} ({v[3]})": v for v in vers}

        sel_row = ctk.CTkFrame(frame, fg_color="transparent")
        sel_row.pack(fill="x")
        self.risk_ver_var = StringVar(value=ver_labels[0])
        ctk.CTkLabel(sel_row, text="版本", width=60, text_color=MHY_TEXT).pack(side="left")
        ctk.CTkOptionMenu(sel_row, variable=self.risk_ver_var, values=ver_labels, width=250,
                          command=lambda _: self._refresh_risks()).pack(side="left", padx=10)

        # 新增风险
        add_row = ctk.CTkFrame(frame, fg_color=MHY_CARD, corner_radius=10,
                                border_width=1, border_color=MHY_BORDER)
        add_row.pack(fill="x", pady=10)

        ctk.CTkLabel(add_row, text="新增风险项", font=("Microsoft YaHei", 13, "bold"),
                     text_color="white").pack(anchor="w", padx=15, pady=(10, 5))

        row1 = ctk.CTkFrame(add_row, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row1, text="风险", width=60, text_color=MHY_TEXT).pack(side="left")
        self.risk_title = ctk.CTkEntry(row1, width=220, placeholder_text="如：卡池流水不达预期")
        self.risk_title.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="概率", width=50, text_color=MHY_TEXT).pack(side="left")
        self.risk_prob = ctk.CTkOptionMenu(row1, values=["高","中","低"], width=60)
        self.risk_prob.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="影响", width=50, text_color=MHY_TEXT).pack(side="left")
        self.risk_impact = ctk.CTkOptionMenu(row1, values=["高","中","低"], width=60)
        self.risk_impact.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="负责人", width=60, text_color=MHY_TEXT).pack(side="left")
        self.risk_owner = ctk.CTkEntry(row1, width=100, placeholder_text="运营A")
        self.risk_owner.pack(side="left", padx=5)

        row2 = ctk.CTkFrame(add_row, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row2, text="预防措施", width=80, text_color=MHY_TEXT).pack(side="left")
        self.risk_mitigation = ctk.CTkEntry(row2, width=220, placeholder_text="如：提前准备备用素材")
        self.risk_mitigation.pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="应急预案", width=80, text_color=MHY_TEXT).pack(side="left", padx=5)
        self.risk_contingency = ctk.CTkEntry(row2, width=220, placeholder_text="如：追加福利活动补救")
        self.risk_contingency.pack(side="left", padx=5)

        ctk.CTkButton(row2, text="➕ 添加", fg_color=MHY_RED, hover_color="#e0415c",
                      command=self._add_risk, width=80).pack(side="right", padx=10)

        self.risk_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.risk_container.pack(fill="both", expand=True, pady=10)
        self._refresh_risks()

    def _add_risk(self):
        v = self._risk_ver_map.get(self.risk_ver_var.get())
        if not v or not self.risk_title.get():
            return
        prob_map = {"高": "high", "中": "medium", "低": "low"}
        try:
            with get_conn() as c:
                c.execute("""INSERT INTO risks (version_id,title,probability,impact,mitigation,contingency,owner)
                          VALUES (?,?,?,?,?,?,?)""",
                          (v[0], self.risk_title.get(),
                           prob_map.get(self.risk_prob.get(), "medium"),
                           prob_map.get(self.risk_impact.get(), "medium"),
                           self.risk_mitigation.get(), self.risk_contingency.get(),
                           self.risk_owner.get()))
            self.risk_title.delete(0, "end")
            self.risk_mitigation.delete(0, "end")
            self.risk_contingency.delete(0, "end")
            self.risk_owner.delete(0, "end")
            self._refresh_risks()
        except Exception:
            pass

    def _auto_mark_risks(self):
        """从 char_usage 表检测角色使用率下降，自动生成风险项"""
        try:
            with get_conn() as c:
                rows = c.execute("""
                    SELECT version, character_name, usage_rate
                    FROM char_usage ORDER BY character_name, version
                """).fetchall()
        except:
            messagebox.showwarning("提示", "暂无角色使用率数据，请先运行 fetch_data.py")
            return

        if len(rows) < 3:
            messagebox.showwarning("提示", "需要至少3条角色使用率数据才能检测趋势")
            return

        # 按角色分组
        char_data = {}
        for ver, name, rate in rows:
            if name not in char_data:
                char_data[name] = []
            char_data[name].append((ver, rate))

        auto_count = 0
        for char_name, entries in char_data.items():
            if len(entries) < 2:
                continue
            # 检测连续两期下降超过5个百分点
            for i in range(1, len(entries)):
                prev_rate = entries[i-1][1]
                curr_rate = entries[i][1]
                drop = prev_rate - curr_rate
                if drop > 5.0:
                    curr_ver = entries[i][1]
                    desc = f"{char_name}使用率持续下降（{prev_rate:.1f}%→{curr_rate:.1f}%，跌幅{drop:.1f}%）"
                    # Upsert
                    with get_conn() as c:
                        existing = c.execute(
                            "SELECT id FROM risks WHERE title LIKE ? AND version_id IN (SELECT id FROM versions WHERE version=?)",
                            (f"%{char_name}%使用率%", curr_ver)
                        ).fetchone()
                        if existing:
                            c.execute(
                                "UPDATE risks SET title=?, probability='high', impact='high' WHERE id=?",
                                (desc, existing[0])
                            )
                        else:
                            ver_row = c.execute(
                                "SELECT id FROM versions WHERE version=? LIMIT 1", (curr_ver,)
                            ).fetchone()
                            if ver_row:
                                c.execute(
                                    "INSERT INTO risks (version_id,title,probability,impact,mitigation,contingency,owner) VALUES (?,?,'high','high','分析角色定位，评估是否需要数值调整','准备角色加强方案或同定位替代角色推广','运营')",
                                    (ver_row[0], desc)
                                )
                                auto_count += 1

        self._refresh_risks()
        if auto_count > 0:
            messagebox.showinfo("完成", f"已自动标记 {auto_count} 条风险项")
        else:
            messagebox.showinfo("完成", "未检测到持续下降超过5%的角色")

    def _refresh_risks(self):
        for w in self.risk_container.winfo_children():
            w.destroy()
        v = self._risk_ver_map.get(self.risk_ver_var.get())
        if not v:
            return
        with get_conn() as c:
            items = c.execute("SELECT id,title,probability,impact,mitigation,contingency,owner,status FROM risks WHERE version_id=? ORDER BY id",
                              (v[0],)).fetchall()
        if not items:
            ctk.CTkLabel(self.risk_container, text="暂无风险项，请添加",
                         font=("Microsoft YaHei", 12), text_color=MHY_SUB).pack(pady=20)
            return

        prob_colors = {"high": "#e74c3c", "medium": "#f59e0b", "low": "#2ecc71"}
        prob_labels = {"high": "高", "medium": "中", "low": "低"}
        impact_labels = {"high": "高影响", "medium": "中影响", "low": "低影响"}

        for item in items:
            iid, title, prob, impact, mitigation, contingency, owner, status = item
            card = ctk.CTkFrame(self.risk_container, fg_color=MHY_CARD, corner_radius=8,
                                border_width=1, border_color=MHY_BORDER)
            card.pack(fill="x", pady=5)

            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(8, 3))
            ctk.CTkLabel(header, text=title, font=("Microsoft YaHei", 13, "bold"),
                         text_color="white").pack(side="left")

            p_color = prob_colors.get(prob, "#999")
            i_color = prob_colors.get(impact, "#999")
            pb = ctk.CTkFrame(header, fg_color=p_color, corner_radius=10)
            pb.pack(side="right", padx=3)
            ctk.CTkLabel(pb, text=f"概率{prob_labels.get(prob, prob)}",
                         font=("Microsoft YaHei", 10), text_color="white").pack(padx=8, pady=1)
            ib = ctk.CTkFrame(header, fg_color=i_color, corner_radius=10)
            ib.pack(side="right", padx=3)
            ctk.CTkLabel(ib, text=impact_labels.get(impact, impact),
                         font=("Microsoft YaHei", 10), text_color="white").pack(padx=8, pady=1)

            if mitigation:
                ctk.CTkLabel(card, text=f"预防: {mitigation}",
                             font=("Microsoft YaHei", 11), text_color=MHY_SUB,
                             anchor="w").pack(fill="x", padx=15)
            if contingency:
                ctk.CTkLabel(card, text=f"应急: {contingency}",
                             font=("Microsoft YaHei", 11), text_color=MHY_SUB,
                             anchor="w").pack(fill="x", padx=15, pady=(0, 2))
            if owner:
                ctk.CTkLabel(card, text=f"负责人: {owner}",
                             font=("Microsoft YaHei", 10), text_color=MHY_SUB,
                             anchor="w").pack(fill="x", padx=15, pady=(0, 3))

            ctk.CTkButton(card, text="🗑", fg_color="transparent", hover_color="#c0392b",
                          text_color="#e74c3c", width=30, height=24, font=("Microsoft YaHei", 10),
                          command=lambda iid=iid: self._delete_risk(iid)).pack(side="right", padx=5, pady=(0, 5))

    def _delete_risk(self, iid):
        if not messagebox.askyesno("确认", "删除此风险项？"):
            return
        with get_conn() as c:
            c.execute("DELETE FROM risks WHERE id=?", (iid,))
        self._refresh_risks()
