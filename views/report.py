import csv
import threading
from datetime import datetime, timedelta
from tkinter import messagebox, filedialog

import customtkinter as ctk

from db import get_conn, load_config, save_config, add_log, date_str, GAMES
from theme import MHY_RED, MHY_DARK, MHY_CARD, MHY_BORDER, MHY_TEXT, MHY_SUB


class ReportMixin:
    def show_report(self):
        self.clear_main(on_done=self._build_report)

    def _build_report(self):
        self.highlight_nav(3)
        self.current_view = "report"

        banner = ctk.CTkFrame(self.main_frame, fg_color=MHY_CARD, corner_radius=0)
        banner.pack(fill="x", padx=0, pady=(0, 20))
        ctk.CTkLabel(banner, text="📝 运营报告",
                     font=("Microsoft YaHei", 26, "bold"), text_color="white").pack(anchor="w", padx=30, pady=(25, 5))
        ctk.CTkLabel(banner, text="一键生成运营周报/月报",
                     font=("Microsoft YaHei", 13), text_color=MHY_SUB).pack(anchor="w", padx=30, pady=(0, 20))

        # API 配置快捷栏
        api_cfg_row = ctk.CTkFrame(self.main_frame, fg_color=MHY_CARD, corner_radius=8,
                                    border_width=1, border_color=MHY_BORDER)
        api_cfg_row.pack(fill="x", padx=30, pady=(0, 15))
        key_saved = load_config("ai_api_key")
        url_saved = load_config("ai_base_url") or "https://api.deepseek.com"
        model_saved = load_config("ai_model") or "deepseek-chat"
        if key_saved:
            ctk.CTkLabel(api_cfg_row, text=f"API 已配置 ✓ | {model_saved} | {url_saved[:40]}...",
                         font=("Microsoft YaHei", 11), text_color="#2ecc71").pack(side="left", padx=15, pady=8)
        else:
            ctk.CTkLabel(api_cfg_row, text="API 未配置，AI 生成功能将不可用",
                         font=("Microsoft YaHei", 11), text_color="#f59e0b").pack(side="left", padx=15, pady=8)
        ctk.CTkButton(api_cfg_row, text="⚙ 设置", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                      text_color=MHY_TEXT, width=70, height=26, font=("Microsoft YaHei", 10),
                      command=self._show_report_api_config).pack(side="right", padx=10, pady=5)

        tab_view = ctk.CTkTabview(self.main_frame, fg_color=MHY_CARD, segmented_button_fg_color=MHY_DARK,
                                   segmented_button_selected_color=MHY_RED, segmented_button_unselected_color=MHY_BORDER)
        tab_view.pack(fill="both", expand=True, padx=30, pady=20)
        tab1 = tab_view.add("📄 生成报告")
        tab2 = tab_view.add("📚 历史报告")

        self._build_report_gen(tab1)
        self._build_report_history(tab2)

    def _build_report_gen(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x")
        self.rp_type = ctk.CTkOptionMenu(row, values=["周报", "月报", "自定义"], width=120)
        self.rp_type.pack(side="left", padx=5)
        self.rp_game = ctk.CTkOptionMenu(row, values=["全部"] + GAMES, width=150)
        self.rp_game.pack(side="left", padx=5)
        self.rp_days = ctk.CTkEntry(row, width=80, placeholder_text="天数")
        self.rp_days.insert(0, "7")
        self.rp_days.pack(side="left", padx=5)

        ctk.CTkButton(row, text="📊 生成报告", fg_color="#ff4d6a", hover_color="#e0415c",
                      command=self._gen_report).pack(side="left", padx=10)
        self.rp_ai_btn = ctk.CTkButton(row, text="🤖 AI 生成", fg_color="#8b5cf6", hover_color="#7c3aed",
                                        command=self._gen_ai_report)
        self.rp_ai_btn.pack(side="left", padx=5)
        self.rp_smart_btn = ctk.CTkButton(row, text="📋 一键生成智能报告", fg_color=MHY_CARD,
                                           hover_color="#2a2a3e", text_color=MHY_TEXT,
                                           border_width=1, border_color=MHY_BORDER,
                                           command=self._gen_smart_report, width=160, height=32)
        self.rp_smart_btn.pack(side="left", padx=5)

        self.rp_output = ctk.CTkTextbox(frame, height=400, fg_color=MHY_DARK,
                                         border_width=1, border_color=MHY_BORDER,
                                         font=("Microsoft YaHei", 12), text_color=MHY_TEXT)
        self.rp_output.pack(fill="both", expand=True, pady=15)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x")
        ctk.CTkButton(btn_row, text="📋 复制到剪贴板",
                      command=self._copy_report).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="💾 保存报告", fg_color="#8b5cf6", hover_color="#7c3aed",
                      command=self._save_report).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="📥 导出 CSV", fg_color=MHY_BORDER, hover_color="#3a3a4e",
                      text_color=MHY_TEXT, command=self._export_report_csv).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="📄 导出为PDF", fg_color="#e74c3c", hover_color="#c0392b",
                      command=self._export_pdf).pack(side="left", padx=5)

    def _get_report_data_context(self):
        """从 db 读取角色使用率、社区热度、风险项数据"""
        ctx = {}
        try:
            with get_conn() as c:
                ver_row = c.execute("SELECT version FROM versions ORDER BY start_date DESC LIMIT 1").fetchone()
                version = ver_row[0] if ver_row else "N/A"
                ctx["version"] = version

                usage_rows = c.execute(
                    "SELECT character_name, usage_rate FROM char_usage WHERE version=? ORDER BY usage_rate DESC LIMIT 5",
                    (version,)
                ).fetchall()
                if usage_rows:
                    ctx["top_char"] = usage_rows[0][0]
                    ctx["top_rate"] = f"{usage_rows[0][1]:.1f}"
                    ctx["top5_list"] = "\n".join([f"- {r[0]}：{r[1]:.1f}%" for r in usage_rows])
                else:
                    ctx["top_char"] = "暂无"
                    ctx["top_rate"] = "0"
                    ctx["top5_list"] = "- 暂无数据"

                hot_row = c.execute(
                    "SELECT COALESCE(SUM(post_count),0), COALESCE(AVG(avg_reply_count),0) FROM community_hot WHERE version=?",
                    (version,)
                ).fetchone()
                ctx["post_count"] = str(int(hot_row[0])) if hot_row else "0"
                ctx["avg_reply"] = f"{hot_row[1]:.1f}" if hot_row and hot_row[1] else "0"

                risk_rows = c.execute(
                    "SELECT r.title FROM risks r JOIN versions v ON r.version_id=v.id WHERE v.version=?",
                    (version,)
                ).fetchall()
                ctx["risk_count"] = str(len(risk_rows))
                ctx["risk_list"] = "\n".join([f"- {r[0]}" for r in risk_rows]) if risk_rows else "- 暂无风险项"
        except:
            ctx = {"version": "N/A", "top_char": "暂无", "top_rate": "0", "top5_list": "- 暂无数据",
                   "post_count": "0", "avg_reply": "0", "risk_count": "0", "risk_list": "- 暂无风险项"}
        return ctx

    def _gen_smart_report(self):
        """一键生成智能报告：自动填充数据 + 预设四段落结构"""
        ctx = self._get_report_data_context()
        game = self.rp_game.get()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = []
        lines.append(f"# {game if game != '全部' else '全游戏'}运营智能报告")
        lines.append(f"**生成时间**: {now}")
        lines.append(f"**当前版本**: {ctx['version']}")
        lines.append("")

        # 数据摘要（自动填充）
        lines.append("## 1. 数据摘要")
        lines.append(f"- 角色使用率最高为 **{ctx['top_char']}**，达到 **{ctx['top_rate']}%**")
        lines.append(f"- 社区帖子总数 **{ctx['post_count']}**，平均回复 **{ctx['avg_reply']}**")
        lines.append(f"- 当前风险项数量 **{ctx['risk_count']}**")
        lines.append("")
        lines.append("### 角色使用率 TOP5")
        lines.append(ctx["top5_list"])
        lines.append("")

        # 核心发现（AI生成或兜底）
        lines.append("## 2. 核心发现")
        api_key = load_config("ai_api_key")
        if api_key:
            lines.append("*AI 正在基于数据生成核心发现... 请点击「🤖 AI 生成」按钮获取智能分析*")
        else:
            lines.append(f"- 当前版本 **{ctx['version']}** 角色使用率最高为 {ctx['top_char']}，社区热度处于{'活跃' if int(ctx['post_count']) > 1000 else '一般'}水平")
            lines.append("- 建议关注使用率波动较大的角色，结合社区反馈优化运营策略")
        lines.append("")

        # 风险与应对（自动填充）
        lines.append("## 3. 风险与应对")
        lines.append(ctx["risk_list"])
        lines.append("")

        # 下一步计划（预留）
        lines.append("## 4. 下一步计划")
        lines.append("- [ ] 版本内容复盘会议")
        lines.append("- [ ] 角色使用率趋势跟踪")
        lines.append("- [ ] 社区活跃度提升活动策划")
        lines.append("- [ ] 风险项应对方案落地")
        lines.append("")
        lines.append("---")
        lines.append("*报告由 米游社运营助手 智能生成*")

        report = "\n".join(lines)
        self.rp_output.delete("1.0", "end")
        self.rp_output.insert("1.0", report)
        try:
            days = int(self.rp_days.get())
            end = datetime.now()
            start = end - timedelta(days=days)
            game = self.rp_game.get()

            sql = "SELECT * FROM daily_metrics WHERE date>=? AND date<=?"
            params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
            if game != "全部":
                sql += " AND game=?"
                params.append(game)
            sql += " ORDER BY date"

            with get_conn() as c:
                rows = c.execute(sql, params).fetchall()

            if not rows:
                self.rp_output.delete("1.0", "end")
                self.rp_output.insert("1.0", "⚠️ 该时间范围内无数据，请先在数据工作台录入")
                return

            avg_dau = sum(r[3] for r in rows) / len(rows)
            total_posts = sum(r[4] for r in rows)
            total_comments = sum(r[5] for r in rows)
            avg_rate = sum(r[7] for r in rows) / len(rows)

            lines = []
            lines.append(f"# {'全部游戏' if game == '全部' else game}运营{'周报' if days <= 7 else '月报'}")
            lines.append(f"**报告周期**: {start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')}")
            lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            lines.append("")
            lines.append("## 1. 核心指标")
            lines.append(f"| 指标 | 数值 |")
            lines.append(f"|------|------|")
            lines.append(f"| 平均 DAU | {int(avg_dau):,} |")
            lines.append(f"| 新增帖子（合计） | {total_posts:,} |")
            lines.append(f"| 评论数（合计） | {total_comments:,} |")
            lines.append(f"| 平均互动率 | {avg_rate:.1f}% |")
            lines.append(f"| 数据天数 | {len(rows)} 天 |")
            lines.append("")
            lines.append("## 2. 每日明细")
            for r in rows:
                lines.append(f"- {r[1]} | {r[2]} | DAU: {r[3]:,} | 帖子: {r[4]} | 互动率: {r[7]}%")
            lines.append("")
            lines.append("## 3. 运营建议")
            if avg_rate < 3:
                lines.append("- ⚠️ 互动率偏低，建议加强社区话题引导")
            elif avg_rate < 6:
                lines.append("- ✅ 互动率正常，可尝试策划主题活动提升活跃度")
            else:
                lines.append("- 🎉 互动率表现良好，继续保持")
            lines.append("- 📊 建议建立数据复盘机制，每次版本后对比核心指标")
            lines.append("")
            lines.append("---")
            lines.append("*报告由 米游社运营助手 自动生成*")

            report = "\n".join(lines)
            self.rp_output.delete("1.0", "end")
            self.rp_output.insert("1.0", report)

        except Exception as e:
            self.rp_output.delete("1.0", "end")
            self.rp_output.insert("1.0", f"生成失败: {e}")

    def _gen_ai_report(self):
        api_key = load_config("ai_api_key")
        if not api_key:
            messagebox.showwarning("提示", "请先在「AI 运营顾问」中配置 API Key")
            return
        base_url = load_config("ai_base_url") or "https://api.deepseek.com"
        model = load_config("ai_model") or "deepseek-chat"

        try:
            days = int(self.rp_days.get())
            end = datetime.now()
            start = end - timedelta(days=days)
            game = self.rp_game.get()

            sql = "SELECT * FROM daily_metrics WHERE date>=? AND date<=?"
            params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
            if game != "全部":
                sql += " AND game=?"
                params.append(game)
            sql += " ORDER BY date"

            with get_conn() as c:
                rows = c.execute(sql, params).fetchall()
            if not rows:
                self.rp_output.delete("1.0", "end")
                self.rp_output.insert("1.0", "⚠️ 该时间范围内无数据，请先在数据工作台录入")
                return

            # 构造数据摘要
            avg_dau = sum(r[3] for r in rows) / len(rows)
            total_posts = sum(r[4] for r in rows)
            total_comments = sum(r[5] for r in rows)
            avg_rate = sum(r[7] for r in rows) / len(rows)

            data_summary = f"报告类型：{self.rp_type.get()}\n"
            data_summary += f"游戏：{game}\n"
            data_summary += f"周期：{start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')}\n"
            data_summary += f"平均 DAU: {int(avg_dau):,}\n"
            data_summary += f"新增帖子合计: {total_posts:,}\n"
            data_summary += f"评论数合计: {total_comments:,}\n"
            data_summary += f"平均互动率: {avg_rate:.1f}%\n"
            data_summary += f"数据天数: {len(rows)} 天\n\n每日明细:\n"
            for r in rows:
                data_summary += f"- {r[1]} | {r[2]} | DAU:{r[3]:,} | 帖子:{r[4]} | 评论:{r[5]} | 互动率:{r[7]}%\n"

            prompt = f"""你是一位资深游戏运营分析师，请根据以下运营数据，生成一份专业、结构化的运营报告。

要求：
1. 报告标题使用 markdown 一级标题
2. 包含核心指标解读（不要只罗列数字，要有分析）
3. 包含趋势洞察和异常分析
4. 包含可落地的运营建议（3-5条，具体可执行）
5. 语言专业但不生硬，面向运营团队
6. 用 markdown 格式输出（表格、列表、加粗等）

{data_summary}"""

            self.rp_output.delete("1.0", "end")
            self.rp_output.insert("1.0", "AI 正在分析数据生成报告...\n")
            self.rp_ai_btn.configure(state="disabled", text="⏳ 生成中...")

            def worker():
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key, base_url=base_url)
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                    )
                    result = resp.choices[0].message.content
                except Exception as e:
                    result = f"AI 生成失败: {e}"
                self.after(0, lambda: self._on_rp_ai_done(result))

            threading.Thread(target=worker, daemon=True).start()

        except Exception as e:
            self.rp_output.delete("1.0", "end")
            self.rp_output.insert("1.0", f"生成失败: {e}")

    def _on_rp_ai_done(self, result):
        self.rp_output.delete("1.0", "end")
        self.rp_output.insert("1.0", result)
        self.rp_ai_btn.configure(state="normal", text="🤖 AI 生成")

    def _show_report_api_config(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("API 配置")
        dialog.geometry("500x280")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=MHY_CARD)

        ctk.CTkLabel(dialog, text="AI API 配置", font=("Microsoft YaHei", 15, "bold"),
                     text_color="white").pack(pady=(15, 10))

        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row, text="API Key", width=70, text_color=MHY_TEXT).pack(side="left")
        key_entry = ctk.CTkEntry(row, width=300, placeholder_text="sk-...", show="*")
        key_entry.pack(side="left", padx=5)
        saved_key = load_config("ai_api_key")
        if saved_key:
            key_entry.insert(0, saved_key)

        row2 = ctk.CTkFrame(dialog, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row2, text="Base URL", width=70, text_color=MHY_TEXT).pack(side="left")
        url_entry = ctk.CTkEntry(row2, width=300, placeholder_text="https://api.deepseek.com")
        url_entry.pack(side="left", padx=5)
        saved_url = load_config("ai_base_url")
        if saved_url:
            url_entry.insert(0, saved_url)

        row3 = ctk.CTkFrame(dialog, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row3, text="模型", width=70, text_color=MHY_TEXT).pack(side="left")
        model_menu = ctk.CTkOptionMenu(row3, values=["deepseek-chat", "deepseek-v4-pro", "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], width=200)
        model_menu.pack(side="left", padx=5)
        saved_model = load_config("ai_model")
        if saved_model:
            model_menu.set(saved_model)

        def save():
            save_config("ai_api_key", key_entry.get())
            save_config("ai_base_url", url_entry.get())
            save_config("ai_model", model_menu.get())
            dialog.destroy()
            messagebox.showinfo("提示", "API 配置已保存，AI 报告生成可用")

        ctk.CTkButton(dialog, text="💾 保存配置", fg_color=MHY_RED, hover_color="#e0415c",
                      command=save, width=120).pack(pady=15)

    def _copy_report(self):
        content = self.rp_output.get("1.0", "end-1c")
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self._toast("已复制到剪贴板")

    def _export_report_csv(self):
        content = self.rp_output.get("1.0", "end-1c")
        if not content or content.startswith("⚠️"):
            messagebox.showwarning("提示", "没有可导出的报告内容")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                          title="导出报告", initialfile=f"报告_{datetime.now().strftime('%Y%m%d')}.csv")
        if not fp:
            return
        try:
            with open(fp, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                for line in content.split("\n"):
                    w.writerow([line])
            messagebox.showinfo("成功", f"报告已导出到:\n{fp}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _save_report(self):
        content = self.rp_output.get("1.0", "end-1c")
        if not content:
            return
        try:
            with get_conn() as c:
                c.execute("INSERT INTO reports (title,content,type) VALUES (?,?,?)",
                          (f"运营报告_{datetime.now().strftime('%Y%m%d')}", content, self.rp_type.get()))
            self._toast("报告已保存")
            self._save_log("保存报告")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _export_pdf(self):
        content = self.rp_output.get("1.0", "end-1c")
        if not content or content.startswith("⚠️"):
            messagebox.showwarning("提示", "没有可导出的报告内容")
            return

        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            title="导出PDF报告", initialfile=f"运营周报_{datetime.now().strftime('%Y%m%d')}.pdf")
        if not fp:
            return

        self._toast("正在生成PDF报告...")
        threading.Thread(target=self._do_export_pdf, args=(fp, content), daemon=True).start()

    def _do_export_pdf(self, fp, content):
        import os, tempfile
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor, white, black
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Image, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # 中文字体注册
        zh_fonts = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
        zh_font_path = None
        for f in zh_fonts:
            if os.path.exists(f):
                zh_font_path = f
                break
        if zh_font_path:
            try:
                pdfmetrics.registerFont(TTFont("ZHFont", zh_font_path))
                cn_font_name = "ZHFont"
            except:
                cn_font_name = "Helvetica"
        else:
            cn_font_name = "Helvetica"

        mp_font = FontProperties(fname=zh_font_path, size=10) if zh_font_path else None

        width, height = A4
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        tmp_files = []

        # ── 获取数据库数据 ──
        try:
            days = int(self.rp_days.get()) if hasattr(self, 'rp_days') else 7
        except:
            days = 7
        game = self.rp_game.get() if hasattr(self, 'rp_game') else "全部"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        dau_dates = []
        dau_vals = []
        hot_vals = []
        risk_data = []
        budget_planned = 0
        budget_actual = 0
        risk_count = 0
        total_posts = 0

        try:
            with get_conn() as c:
                # DAU 数据
                sql = "SELECT date, dau FROM daily_metrics WHERE date>=? AND date<=? ORDER BY date"
                params = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
                rows = c.execute(sql, params).fetchall()
                for r in rows:
                    dau_dates.append(r[0])
                    dau_vals.append(r[1])

                # 帖子数
                rows2 = c.execute(
                    "SELECT COALESCE(SUM(new_posts),0) FROM daily_metrics WHERE date>=? AND date<=?",
                    params).fetchone()
                total_posts = int(rows2[0]) if rows2 else 0

                # 社区热度
                hot_rows = c.execute(
                    "SELECT SUM(post_count) FROM community_hot").fetchone()
                hot_total = int(hot_rows[0]) if hot_rows and hot_rows[0] else 0
                if dau_dates:
                    n_days = len(dau_dates)
                    step = max(1, hot_total // n_days) if n_days > 0 else 0
                    hot_vals = [step * i for i in range(n_days)]

                # 风险数据
                risk_rows = c.execute(
                    "SELECT title, probability, impact, status FROM risks").fetchall()
                prob_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
                imp_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
                for r in risk_rows:
                    p = prob_map.get(r[1].lower() if r[1] else "medium", 2)
                    i = imp_map.get(r[2].lower() if r[2] else "medium", 2)
                    risk_data.append((r[0][:12], p, i, r[3]))
                risk_count = len(risk_rows)

                # 预算
                budget_rows = c.execute(
                    "SELECT COALESCE(SUM(planned),0), COALESCE(SUM(actual),0) FROM budgets").fetchone()
                budget_planned = budget_rows[0] if budget_rows else 0
                budget_actual = budget_rows[1] if budget_rows else 0

                # 创建临时目录（如果不存在）
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "temp")
                os.makedirs(temp_dir, exist_ok=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror("错误", f"数据读取失败: {e}"))
            return

        # ── 图表1: DAU 折线图 ──
        chart1_path = os.path.join(temp_dir, "temp_dau.png")
        if dau_vals:
            fig, ax = plt.subplots(figsize=(7, 3.5))
            ax.plot(range(len(dau_vals)), dau_vals, color="#ff4d6a", linewidth=2, marker="o", markersize=4, label="DAU")
            ax.set_title("DAU 趋势", fontsize=14, fontproperties=mp_font, color="#333")
            ax.set_xticks(range(len(dau_dates)))
            ax.set_xticklabels(dau_dates, rotation=45, fontsize=7)
            ax.set_facecolor("#1a1a2e")
            fig.patch.set_facecolor("#1a1a2e")
            ax.spines["bottom"].set_color("#444")
            ax.spines["left"].set_color("#444")
            ax.tick_params(colors="#ccc")
            ax.yaxis.label.set_color("#ccc")
            ax.xaxis.label.set_color("#ccc")
            ax.title.set_color("white")
            ax.grid(True, alpha=0.3, color="#555")
            fig.tight_layout()
            fig.savefig(chart1_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            tmp_files.append(chart1_path)

        # ── 图表2: 风险矩阵热力图 ──
        chart2_path = os.path.join(temp_dir, "temp_risk.png")
        if risk_data:
            fig, ax = plt.subplots(figsize=(5, 4))
            colors_map = {"open": "#e74c3c", "monitoring": "#f39c12", "resolved": "#2ecc71"}
            for title, p, i, status in risk_data:
                c = colors_map.get(status, "#888")
                ax.scatter(p, i, s=(p + i) * 60, c=c, alpha=0.7, edgecolors="white", linewidth=0.5)
                ax.annotate(title, (p, i), fontsize=6, ha="center", va="bottom", color="white", fontproperties=mp_font)
            ax.set_xlim(0.5, 4.5)
            ax.set_ylim(0.5, 4.5)
            ax.set_xticks([1, 2, 3, 4])
            ax.set_yticks([1, 2, 3, 4])
            ax.set_xticklabels(["低", "中", "高", "严重"], fontproperties=mp_font, fontsize=9, color="#ccc")
            ax.set_yticklabels(["低", "中", "高", "严重"], fontproperties=mp_font, fontsize=9, color="#ccc")
            ax.set_xlabel("概率", fontsize=11, fontproperties=mp_font, color="#ccc")
            ax.set_ylabel("影响", fontsize=11, fontproperties=mp_font, color="#ccc")
            ax.set_title("风险矩阵", fontsize=14, fontproperties=mp_font, color="white")
            ax.set_facecolor("#1a1a2e")
            fig.patch.set_facecolor("#1a1a2e")
            ax.grid(True, alpha=0.3, color="#555")
            for spine in ax.spines.values():
                spine.set_color("#444")
            fig.tight_layout()
            fig.savefig(chart2_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            tmp_files.append(chart2_path)

        # ── 图表3: 版本健康度雷达图 ──
        chart3_path = os.path.join(temp_dir, "temp_radar.png")
        import numpy as np
        # 五维: DAU完成率, 预算偏差率, 风险数(逆), 社区热度, 内容产出
        avg_dau = sum(dau_vals) / len(dau_vals) if dau_vals else 0
        dau_ratio = min(1.0, avg_dau / 200000) if avg_dau > 0 else 0.5
        budget_deviation = abs(budget_planned - budget_actual) / max(budget_planned, 1)
        budget_score = max(0, 1 - budget_deviation)
        risk_score = max(0, 1 - risk_count / 20)
        hot_total = sum(hot_vals)
        hot_normalized = min(1.0, hot_total / 50000) if hot_total > 0 else 0.3
        content_score = min(1.0, total_posts / 5000) if total_posts > 0 else 0.3
        scores = [dau_ratio, budget_score, risk_score, hot_normalized, content_score]
        # 确保都在合理范围
        scores = [max(0.01, min(1.0, s)) for s in scores]

        categories = ["DAU完成率", "预算偏差率", "风险数(逆)", "社区热度", "内容产出"]
        N = len(categories)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]
        scores += scores[:1]

        fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
        ax.fill(angles, scores, alpha=0.3, color="#ff4d6a")
        ax.plot(angles, scores, color="#ff4d6a", linewidth=2)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontproperties=mp_font, fontsize=10, color="white")
        ax.set_ylim(0, 1.1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=7, color="#888")
        ax.set_title("版本健康度雷达图", fontsize=14, fontproperties=mp_font, color="white", pad=20)
        ax.set_facecolor("#1a1a2e")
        fig.patch.set_facecolor("#1a1a2e")
        ax.grid(True, alpha=0.3, color="#555")
        for spine in ax.spines.values():
            spine.set_color("#444")
        fig.tight_layout()
        fig.savefig(chart3_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        tmp_files.append(chart3_path)

        # ── 生成 PDF ──
        try:
            doc = SimpleDocTemplate(fp, pagesize=A4,
                                    leftMargin=20*mm, rightMargin=20*mm,
                                    topMargin=15*mm, bottomMargin=15*mm)
            elements = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle("CNTitle", fontSize=28, textColor=HexColor("#ff4d6a"),
                                         fontName=cn_font_name, spaceAfter=10, alignment=1)
            subtitle_style = ParagraphStyle("CNSub", fontSize=13, textColor=HexColor("#8888aa"),
                                            fontName=cn_font_name, alignment=1, spaceAfter=30)
            h2_style = ParagraphStyle("CNH2", fontSize=18, textColor=HexColor("#ff4d6a"),
                                       fontName=cn_font_name, spaceAfter=10, spaceBefore=15)
            body_style = ParagraphStyle("CNBody", fontSize=10, textColor=HexColor("#cccccc"),
                                         fontName=cn_font_name, leading=16, spaceAfter=5)

            # 封面
            elements.append(Spacer(1, 80))
            elements.append(Paragraph("米游社运营周报", title_style))
            elements.append(Paragraph(f"自动生成于 {now_str}", subtitle_style))
            line_style = ParagraphStyle("Line", fontSize=11, textColor=HexColor("#aaaaaa"),
                                         fontName=cn_font_name, alignment=1, spaceAfter=5)
            elements.append(Paragraph(f"报告周期: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}", line_style))
            elements.append(Paragraph(f"游戏: {game} | 数据天数: {len(dau_vals) if dau_vals else 0}", line_style))
            elements.append(Paragraph(f"平均 DAU: {int(avg_dau):,} | 风险项: {risk_count}", line_style))
            elements.append(Spacer(1, 20))
            elements.append(Paragraph("━" * 50, ParagraphStyle("Sep", fontSize=10, textColor=HexColor("#ff4d6a"), alignment=1)))
            elements.append(Spacer(1, 20))

            # DAU 折线图
            if os.path.exists(chart1_path):
                elements.append(Paragraph("1. DAU 趋势图", h2_style))
                img = Image(chart1_path, width=460, height=230)
                elements.append(img)
                elements.append(Spacer(1, 15))

            # 风险矩阵
            if os.path.exists(chart2_path):
                elements.append(Paragraph("2. 风险矩阵", h2_style))
                img = Image(chart2_path, width=360, height=288)
                elements.append(img)
                elements.append(Spacer(1, 15))

            # 雷达图
            if os.path.exists(chart3_path):
                elements.append(Paragraph("3. 版本健康度雷达图", h2_style))
                img = Image(chart3_path, width=360, height=360)
                elements.append(img)
                elements.append(Spacer(1, 15))

            # 文字报告
            elements.append(Paragraph("4. 文字报告", h2_style))
            for line in content.split("\n")[:50]:
                safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if safe_line.strip():
                    elements.append(Paragraph(safe_line, body_style))
            elements.append(Spacer(1, 30))
            elements.append(Paragraph(f"报告由 米游社运营助手 自动生成 | {now_str}",
                                      ParagraphStyle("Footer", fontSize=9, textColor=HexColor("#666"),
                                                     fontName=cn_font_name, alignment=1)))

            doc.build(elements)
            self.after(0, lambda: messagebox.showinfo("成功", f"PDF报告已导出到:\n{fp}"))
            self.after(0, lambda: self._toast("PDF导出成功"))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror("错误", f"PDF生成失败: {e}"))

        # 清理临时文件
        for tf in tmp_files:
            try:
                if os.path.exists(tf):
                    os.remove(tf)
            except:
                pass

    def _build_report_history(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        try:
            with get_conn() as c:
                rows = c.execute("SELECT title,type,created_at FROM reports ORDER BY created_at DESC LIMIT 30").fetchall()
            if not rows:
                ctk.CTkLabel(frame, text="暂无历史报告", font=("Microsoft YaHei", 13),
                             text_color=MHY_SUB).pack(pady=30)
                return
            for r in rows:
                card = ctk.CTkFrame(frame, fg_color=MHY_CARD, corner_radius=8,
                                     border_width=1, border_color=MHY_BORDER)
                card.pack(fill="x", pady=4)
                ctk.CTkLabel(card, text=f"[{r[1]}] {r[0]}",
                             font=("Microsoft YaHei", 13), text_color=MHY_TEXT).pack(side="left", padx=15, pady=8)
                ctk.CTkLabel(card, text=r[2], font=("Microsoft YaHei", 11),
                             text_color=MHY_SUB).pack(side="right", padx=15)
        except Exception as e:
            ctk.CTkLabel(frame, text=f"加载失败: {e}", text_color="#e74c3c").pack()
