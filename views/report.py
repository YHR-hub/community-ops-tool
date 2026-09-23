"""运营报告 Mixin：模板化生成 + AI 润色 + 历史管理 + CSV/剪贴板导出"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime, csv, os, threading

from theme import (
    BG_DARK, BG_CARD, BG_INPUT, FG_TEXT, FG_DIM,
    ACCENT, ACCENT_LIGHT, GOLD, GOLD_LIGHT, SUCCESS, WARNING, DANGER, BORDER,
)
import db


# ── 常量 ──────────────────────────────────────────────
REPORT_COLS = ("id", "title", "type", "created_at")
REPORT_HDRS = ("ID", "标题", "类型", "创建时间")
REPORT_WIDS = (50, 280, 100, 160)

REPORT_TYPES = {
    "周报": "weekly",
    "月报": "monthly",
}


class ReportMixin:
    """运营报告页面：模板生成 + AI 润色 + 历史管理 + 导出"""

    # ────────────────── 入口 ──────────────────
    def create_report(self, parent):
        """构建运营报告页面"""
        self._rpt_frame = ctk.CTkFrame(parent, fg_color=BG_DARK)
        self._rpt_frame.pack(fill="both", expand=True)

        # ── 顶部操作栏 ──
        top = ctk.CTkFrame(self._rpt_frame, fg_color=BG_CARD, corner_radius=10)
        top.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(top, text="运营报告", font=("Microsoft YaHei", 14, "bold"),
                     text_color=FG_TEXT).pack(side="left", padx=12, pady=10)

        # 报告类型
        ctk.CTkLabel(top, text="类型", font=("Microsoft YaHei", 11),
                     text_color=FG_DIM).pack(side="left", padx=(20, 4))
        self._rpt_type = ctk.CTkComboBox(top, values=list(REPORT_TYPES.keys()),
                                          fg_color=BG_INPUT, text_color=FG_TEXT,
                                          border_color=BORDER, button_color=ACCENT,
                                          button_hover_color=ACCENT_LIGHT,
                                          dropdown_fg_color=BG_CARD,
                                          dropdown_hover_color=BG_INPUT,
                                          font=("Microsoft YaHei", 11), width=100)
        self._rpt_type.set("周报")
        self._rpt_type.pack(side="left", padx=4, pady=10)

        # 生成按钮
        ctk.CTkButton(top, text="自动生成", fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                      font=("Microsoft YaHei", 11, "bold"), width=100,
                      command=self._generate_report).pack(side="left", padx=(12, 4), pady=10)

        # AI 润色按钮
        self._rpt_polish_btn = ctk.CTkButton(top, text="AI 润色", fg_color=SUCCESS,
                                              hover_color="#27ae60",
                                              font=("Microsoft YaHei", 11), width=90,
                                              command=self._ai_polish)
        self._rpt_polish_btn.pack(side="left", padx=4, pady=10)

        # ── 中间：报告预览区 ──
        mid = ctk.CTkFrame(self._rpt_frame, fg_color=BG_DARK)
        mid.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # 左：报告编辑区
        editor_frame = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10)
        editor_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        editor_top = ctk.CTkFrame(editor_frame, fg_color="transparent")
        editor_top.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(editor_top, text="报告内容", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(side="left")

        # 导出按钮组
        ctk.CTkButton(editor_top, text="复制到剪贴板", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 10), width=110,
                      command=self._rpt_copy_clipboard).pack(side="right", padx=(4, 0))
        ctk.CTkButton(editor_top, text="导出 Markdown", fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                      font=("Microsoft YaHei", 10), width=110,
                      command=self._export_markdown).pack(side="right", padx=(4, 0))
        ctk.CTkButton(editor_top, text="导出 CSV", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 10), width=90,
                      command=self._export_report).pack(side="right", padx=(4, 0))
        ctk.CTkButton(editor_top, text="保存报告", fg_color=SUCCESS, hover_color="#27ae60",
                      font=("Microsoft YaHei", 10, "bold"), width=90,
                      command=self._rpt_save).pack(side="right", padx=(4, 0))

        self._rpt_text = ctk.CTkTextbox(editor_frame, fg_color=BG_INPUT, text_color=FG_TEXT,
                                         border_color=BORDER, font=("Microsoft YaHei", 11),
                                         wrap="word")
        self._rpt_text.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # 右：历史报告列表
        history_frame = ctk.CTkFrame(mid, fg_color=BG_CARD, corner_radius=10, width=420)
        history_frame.pack(side="right", fill="y", padx=(0, 0))
        history_frame.pack_propagate(False)

        hist_top = ctk.CTkFrame(history_frame, fg_color="transparent")
        hist_top.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(hist_top, text="历史报告", font=("Microsoft YaHei", 13, "bold"),
                     text_color=FG_TEXT).pack(side="left")

        ctk.CTkButton(hist_top, text="删除", fg_color=DANGER, hover_color="#c0392b",
                      font=("Microsoft YaHei", 10), width=60,
                      command=self._rpt_delete).pack(side="right", padx=(4, 0))
        ctk.CTkButton(hist_top, text="查看", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 10), width=60,
                      command=self._rpt_view).pack(side="right", padx=(4, 0))
        ctk.CTkButton(hist_top, text="刷新", fg_color=BG_INPUT, hover_color=BORDER,
                      font=("Microsoft YaHei", 10), width=60,
                      command=self._rpt_refresh_list).pack(side="right", padx=(4, 0))

        # Treeview
        tree_container = ctk.CTkFrame(history_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._rpt_tree = ttk.Treeview(tree_container, columns=REPORT_COLS, show="headings",
                                       style="Dark.Treeview", height=12)
        for col, hdr, wid in zip(REPORT_COLS, REPORT_HDRS, REPORT_WIDS):
            self._rpt_tree.heading(col, text=hdr, anchor="center")
            self._rpt_tree.column(col, width=wid, anchor="center", minwidth=40)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self._rpt_tree.yview)
        self._rpt_tree.configure(yscrollcommand=vsb.set)
        self._rpt_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # ── 状态栏 ──
        status_bar = ctk.CTkFrame(self._rpt_frame, fg_color="transparent")
        status_bar.pack(fill="x", padx=16, pady=(0, 12))

        self._rpt_status = ctk.CTkLabel(status_bar, text="就绪",
                                         font=("Microsoft YaHei", 11), text_color=FG_DIM)
        self._rpt_status.pack(side="left")

        # 加载历史列表
        self._rpt_refresh_list()

        return self._rpt_frame

    # ────────────────── 自动生成报告 ──────────────────
    def _generate_report(self):
        """从 daily_metrics 聚合数据，生成模板化运营报告"""
        rpt_type_key = self._rpt_type.get()
        rpt_type = REPORT_TYPES.get(rpt_type_key, "weekly")

        # 计算时间范围
        today = datetime.date.today()
        if rpt_type == "weekly":
            start = today - datetime.timedelta(days=7)
            label = f"周报 ({start.isoformat()} ~ {today.isoformat()})"
        else:
            start = today.replace(day=1)
            label = f"月报 ({start.isoformat()} ~ {today.isoformat()})"

        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT date, game, SUM(dau), SUM(new_posts), SUM(comments), "
                    "  AVG(avg_session), AVG(inter_rate) "
                    "FROM daily_metrics WHERE date >= ? AND date <= ? "
                    "GROUP BY date, game ORDER BY date",
                    (start.isoformat(), today.isoformat()),
                ).fetchall()

                # 汇总
                agg = conn.execute(
                    "SELECT COUNT(DISTINCT date), SUM(dau), SUM(new_posts), "
                    "  SUM(comments), AVG(avg_session), AVG(inter_rate) "
                    "FROM daily_metrics WHERE date >= ? AND date <= ?",
                    (start.isoformat(), today.isoformat()),
                ).fetchone()
        except Exception as exc:
            messagebox.showerror("查询失败", str(exc))
            return

        if not rows:
            self._rpt_text.delete("1.0", "end")
            self._rpt_text.insert("1.0", f"## {label}\n\n> 所选时间范围内暂无运营数据，请先在数据工作台录入数据。")
            self._rpt_status.configure(text="无数据")
            return

        # 构建报告
        data_days = agg[0] or 0
        total_dau = agg[1] or 0
        total_posts = agg[2] or 0
        total_comments = agg[3] or 0
        avg_session = agg[4] or 0
        avg_rate = agg[5] or 0

        lines = [
            f"# 米游社运营{rpt_type_key} · {label}",
            "",
            "---",
            "",
            "## 一、核心指标概览",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 数据天数 | {data_days} 天 |",
            f"| 累计 DAU | {int(total_dau):,} |",
            f"| 总帖子数 | {int(total_posts):,} |",
            f"| 总评论数 | {int(total_comments):,} |",
            f"| 平均会话时长 | {avg_session:.1f} 分钟 |",
            f"| 平均互动率 | {avg_rate:.2f}% |",
            "",
            "## 二、每日数据明细",
            "",
            "| 日期 | 游戏 | DAU | 新帖 | 评论 | 会话时长 | 互动率% |",
            "|------|------|-----|------|------|----------|---------|",
        ]

        for row in rows:
            date, game, dau, posts, coms, session, rate = row
            lines.append(
                f"| {date} | {game} | {int(dau):,} | {int(posts):,} | {int(coms):,} "
                f"| {session:.1f} | {rate:.2f} |"
            )

        lines += [
            "",
            "## 三、趋势分析",
            "",
        ]

        # 按游戏统计
        game_stats = {}
        for row in rows:
            game = row[1]
            if game not in game_stats:
                game_stats[game] = {"dau": 0, "posts": 0, "comments": 0, "count": 0}
            game_stats[game]["dau"] += row[2] or 0
            game_stats[game]["posts"] += row[3] or 0
            game_stats[game]["comments"] += row[4] or 0
            game_stats[game]["count"] += 1

        for game, stats in game_stats.items():
            lines.append(f"**{game}**：累计 DAU {int(stats['dau']):,}，"
                         f"新帖 {int(stats['posts']):,}，"
                         f"评论 {int(stats['comments']):,}，"
                         f"数据 {stats['count']} 天")

        lines += [
            "",
            "## 四、待跟进事项",
            "",
            "> 此部分由运营团队手动填写，或使用「AI 润色」功能生成智能建议。",
            "",
            "- [ ] 待补充...",
            "",
            "---",
            f"*报告生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        ]

        self._rpt_text.delete("1.0", "end")
        self._rpt_text.insert("1.0", "\n".join(lines))
        self._rpt_status.configure(text=f"已生成 {rpt_type_key}，共 {data_days} 天数据")
        self._save_log("报告生成", f"{rpt_type_key} {start}~{today}")
        self._toast(f"{rpt_type_key}已生成")

    # ────────────────── AI 润色 ──────────────────
    def _ai_polish(self):
        """调用 AI 对当前报告内容进行润色"""
        content = self._rpt_text.get("1.0", "end").strip()
        if not content:
            self._toast("请先生成或输入报告内容")
            return

        api_key = db.load_config("ai_api_key", "")
        model = db.load_config("ai_model", "deepseek-chat")

        if not api_key:
            messagebox.showwarning("缺少配置", "请先在 AI 运营顾问页面配置 API Key")
            return

        self._rpt_polish_btn.configure(state="disabled", text="润色中...")
        self._rpt_status.configure(text="AI 润色中，请稍候...")

        def _worker():
            try:
                from openai import OpenAI

                base_url = None
                if "deepseek" in model.lower():
                    base_url = "https://api.deepseek.com"

                client_kwargs = {"api_key": api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url

                client = OpenAI(**client_kwargs)

                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content":
                         "你是一位专业的游戏运营报告撰写助手。请对用户提供的运营报告进行润色和优化，"
                         "保持原有的数据和结构，但提升文字的专业性、可读性和分析深度。"
                         "适当增加趋势分析、归因解读和可操作的建议。保留 Markdown 格式。"},
                        {"role": "user", "content": f"请润色以下运营报告：\n\n{content}"},
                    ],
                    temperature=0.7,
                    max_tokens=3000,
                )
                result = resp.choices[0].message.content
                error = None
            except Exception as exc:
                result = ""
                error = str(exc)

            self.after(0, lambda: self._ai_polish_done(result, error))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_polish_done(self, result, error):
        """AI 润色完成回调（主线程）"""
        self._rpt_polish_btn.configure(state="normal", text="AI 润色")

        if error:
            self._rpt_status.configure(text="润色失败")
            messagebox.showerror("AI 润色失败", error)
            return

        self._rpt_text.delete("1.0", "end")
        self._rpt_text.insert("1.0", result)
        self._rpt_status.configure(text="AI 润色完成")
        self._save_log("AI润色", "报告内容已润色")
        self._toast("AI 润色完成")

    # ────────────────── 保存报告 ──────────────────
    def _rpt_save(self):
        """将当前报告保存到 reports 表"""
        content = self._rpt_text.get("1.0", "end").strip()
        if not content:
            self._toast("报告内容为空")
            return

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        rpt_type_key = self._rpt_type.get()
        title = f"运营{rpt_type_key}-{now}"

        try:
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO reports(title, content, type) VALUES(?,?,?)",
                    (title, content, REPORT_TYPES.get(rpt_type_key, "weekly")),
                )
                conn.commit()
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return

        self._save_log("报告保存", title)
        self._toast("报告已保存")
        self._rpt_refresh_list()

    # ────────────────── 历史列表 ──────────────────
    def _rpt_refresh_list(self):
        """刷新历史报告列表"""
        try:
            with db.get_conn() as conn:
                rows = conn.execute(
                    "SELECT id, title, type, created_at FROM reports ORDER BY id DESC LIMIT 200"
                ).fetchall()
        except Exception:
            rows = []

        self._rpt_tree.delete(*self._rpt_tree.get_children())
        for r in rows:
            display = list(r)
            # 类型显示中文
            type_map = {"weekly": "周报", "monthly": "月报", "ai_report": "AI报告"}
            display[2] = type_map.get(display[2], display[2] or "未知")
            self._rpt_tree.insert("", "end", values=display)

    def _rpt_view(self):
        """查看选中的历史报告"""
        sel = self._rpt_tree.selection()
        if not sel:
            self._toast("请先选择一条报告")
            return

        rpt_id = self._rpt_tree.item(sel[0], "values")[0]
        try:
            with db.get_conn() as conn:
                row = conn.execute(
                    "SELECT content FROM reports WHERE id=?", (rpt_id,)
                ).fetchone()
        except Exception as exc:
            messagebox.showerror("查询失败", str(exc))
            return

        if row and row[0]:
            self._rpt_text.delete("1.0", "end")
            self._rpt_text.insert("1.0", row[0])
            title = self._rpt_tree.item(sel[0], "values")[1]
            self._rpt_status.configure(text=f"已加载：{title}")
        else:
            self._toast("该报告内容为空")

    def _rpt_delete(self):
        """删除选中的历史报告"""
        sel = self._rpt_tree.selection()
        if not sel:
            self._toast("请先选择要删除的报告")
            return

        if not messagebox.askyesno("确认删除", f"确定删除选中的 {len(sel)} 条报告？"):
            return

        ids = [self._rpt_tree.item(s, "values")[0] for s in sel]
        try:
            with db.get_conn() as conn:
                conn.executemany(
                    "DELETE FROM reports WHERE id=?",
                    [(i,) for i in ids],
                )
                conn.commit()
        except Exception as exc:
            messagebox.showerror("删除失败", str(exc))
            return

        self._save_log("报告删除", f"删除 {len(ids)} 条报告")
        self._toast(f"已删除 {len(ids)} 条报告")
        self._rpt_refresh_list()

    # ────────────────── 导出 ──────────────────
    def _export_report(self):
        """将当前报告导出为 CSV 文件"""
        content = self._rpt_text.get("1.0", "end").strip()
        if not content:
            self._toast("报告内容为空")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"运营报告_{datetime.date.today().isoformat()}.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["运营报告"])
                writer.writerow([f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"])
                writer.writerow([])
                for line in content.split("\n"):
                    writer.writerow([line])
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return

        self._save_log("报告导出", f"导出到 {os.path.basename(path)}")
        self._toast("报告已导出")

    def _export_markdown(self):
        """将当前报告导出为 Markdown 文件"""
        content = self._rpt_text.get("1.0", "end").strip()
        if not content:
            self._toast("报告内容为空")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown 文件", "*.md"), ("所有文件", "*.*")],
            initialfile=f"运营报告_{datetime.date.today().isoformat()}.md",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return

        self._save_log("Markdown导出", f"导出到 {os.path.basename(path)}")
        self._toast("报告已导出为 Markdown")

    def _rpt_copy_clipboard(self):
        """将报告内容复制到剪贴板"""
        content = self._rpt_text.get("1.0", "end").strip()
        if not content:
            self._toast("报告内容为空")
            return

        self._rpt_frame.clipboard_clear()
        self._rpt_frame.clipboard_append(content)
        self._toast("已复制到剪贴板")
        self._save_log("剪贴板复制", "报告内容已复制")
