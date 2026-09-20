"""
报告页 —— 周期报表 / 智能报告 / 历史归档
==========================================

旧版这一页有个典型症状：`_gen_smart_report` 前半段辛苦拼出一份四段式报告
（数据摘要 / 核心发现 / 风险应对 / 下一步计划），写入文本框后，
**紧接着同一个函数的后半段又把文本框清空，换成一份周期报表**。
所以用户点「智能报告」，永远只看到周报 —— 前半段是纯死代码。

新版把两类报告彻底拆开：
  · 周期报表 —— 纯数据统计，选区间就能出，不依赖 AI，可导出 CSV
  · 智能报告 —— 四段式结构 + 结论性文字，可接 AI 深化
两个 Tab 各自独立，互不覆盖。

其它修掉的：
  · 历史报告只读、不能删 → 补上查看全文与删除
  · CSV 导出把 daily_metrics 的原始列序当成固定列，加字段就错位 → 改用列名
"""

import csv
import os
import threading
from datetime import datetime, timedelta
from tkinter import filedialog

import customtkinter as ctk

import theme
from theme import (
    BG_APP, BG_CARD, BG_ELEVATED, BG_BORDER,
    PRIMARY, PRIMARY_DIM, DANGER, SUCCESS, WARNING, INFO, AI, AI_HOVER,
    NEUTRAL,
    TEXT_PRIMARY, TEXT_BODY, TEXT_SECONDARY, TEXT_TERTIARY,
    font, SIZE_H3, SIZE_BODY, SIZE_SMALL, SIZE_TINY,
    SP_XS, SP_SM, SP_MD, SP_LG, SP_XL, RADIUS_MD,
)
import icons
import components as C
from db import (
    GAMES, query, execute, load_config, latest_version, metrics_between, task_progress,
    open_risks, top_characters, community_summary,
    previous_version, date_str, parse_date,
)

# 互动率健康线（报告里的判断依据集中在这里，不再散落魔法数字）
HEALTHY_RATE = 4.0
WARN_RATE = 3.0


class ReportMixin:
    """由 App 混入，提供报告页。"""

    def show_report(self):
        self.clear_main()
        if getattr(self, "_report_tab", None) not in ("smart", "period", "history"):
            self._report_tab = "smart"
        self._build_report()

    # ═══════════════════════════════════════════════════════
    def _build_report(self):
        # Tab 状态兜底
        if getattr(self, "_report_tab", None) not in ("smart", "period", "history"):
            self._report_tab = "smart"

        body, _page = self.page_scaffold(
            "report", "报告",
            "把数据变成可以交付的文档：周期报表、智能报告、历史归档",
            icon="doc", refresh=self._build_report)

        tabbar = ctk.CTkFrame(body, fg_color="transparent", height=1)
        tabbar.pack(fill="x", pady=(0, SP_MD))

        TABS = [("smart", "智能报告", "bulb"),
                ("period", "周期报表", "calendar"),
                ("history", "历史归档", "folder")]

        for key, text, icon in TABS:
            active = (key == self._report_tab)
            ctk.CTkButton(
                tabbar, text=("  " + text),
                command=lambda k=key: self._switch_report(k),
                fg_color=PRIMARY_DIM if active else "transparent",
                hover_color=BG_ELEVATED,
                text_color=TEXT_PRIMARY if active else TEXT_SECONDARY,
                font=font(SIZE_BODY), corner_radius=RADIUS_MD,
                height=32, width=112, border_width=1,
                border_color=PRIMARY if active else BG_BORDER).pack(
                side="left", padx=(0, SP_SM))

        if self._report_tab == "smart":
            self._build_smart(body)
        elif self._report_tab == "period":
            self._build_period(body)
        else:
            self._build_history(body)

    def _switch_report(self, key):
        self._report_tab = key
        self.remount("report")

    # ═══════════════════════════════════════════════════════
    #  共享：输出区
    # ═══════════════════════════════════════════════════════
    def _build_output_card(self, parent, title, icon="doc", accent=None):
        card = C.Card(parent, accent=accent)
        card.pack(fill="both", expand=True)

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, title, icon=icon,
                       icon_color=accent or TEXT_SECONDARY).pack(side="left")

        self.rp_status = ctk.CTkLabel(head, text="", font=font(SIZE_TINY),
                                      text_color=TEXT_TERTIARY)
        self.rp_status.pack(side="right")

        box = ctk.CTkTextbox(card.body, fg_color=BG_APP, text_color=TEXT_BODY,
                             font=font(SIZE_BODY), wrap="word",
                             border_width=1, border_color=BG_BORDER,
                             corner_radius=RADIUS_MD)
        box.pack(fill="both", expand=True, padx=SP_LG, pady=(0, SP_MD))
        self.rp_output = box
        return card

    def _build_output_toolbar(self, parent, on_save, on_csv=None, on_ai=None):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        row.pack(fill="x", pady=(SP_MD, 0))

        C.PrimaryButton(row, "保存归档", on_save, icon="save",
                        width=112, height=32).pack(side="left")
        C.GhostButton(row, "复制全文", self._copy_report, icon="copy",
                      width=104, height=32).pack(side="left", padx=(SP_SM, 0))
        if on_csv:
            C.GhostButton(row, "导出 CSV", on_csv, icon="download",
                          width=104, height=32).pack(side="left", padx=(SP_SM, 0))
        if on_ai:
            C.PrimaryButton(row, "AI 深化", on_ai, icon="bolt",
                            width=104, height=32, accent=AI,
                            hover=AI_HOVER).pack(side="right")
        return row

    def _copy_report(self):
        try:
            content = self.rp_output.get("1.0", "end").strip()
        except Exception:
            content = ""
        if not content:
            self.toast("还没有可复制的内容", WARNING)
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.toast("已复制到剪贴板")
        except Exception as e:
            self.toast(f"复制失败：{e}", DANGER)

    def _archive(self, title, content, rtype):
        try:
            execute("INSERT INTO reports (title, content, type) VALUES (?,?,?)",
                    (title, content, rtype))
        except Exception as e:
            self.toast(f"保存失败：{e}", DANGER)
            return False
        self.log("保存报告", title)
        self.toast("已归档，可在「历史归档」查看")
        return True

    # ═══════════════════════════════════════════════════════
    #  Tab 1 · 智能报告（四段式）
    # ═══════════════════════════════════════════════════════
    def _build_smart(self, parent):
        bar = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        bar.pack(fill="x", pady=(0, SP_MD))

        self.rp_game = C.Field(bar, "游戏", kind="menu", values=["全部"] + GAMES,
                               width=150, label_width=40, default=GAMES[1])
        self.rp_game.pack(side="left")

        C.PrimaryButton(bar, "生成报告", self._gen_smart_report, icon="bolt",
                        width=116, height=30).pack(side="right")
        C.GhostButton(bar, "AI 深化", self._gen_ai_report, icon="bulb",
                      width=104, height=30).pack(side="right", padx=(0, SP_SM))

        ctk.CTkLabel(bar, text="四段式结构：数据摘要 → 核心发现 → 风险应对 → 下一步计划",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="left", padx=(SP_MD, 0))

        self._build_output_card(parent, "报告正文", icon="doc", accent=AI)
        self._build_output_toolbar(
            parent,
            on_save=self._save_smart_report,
        )

        self._gen_smart_report()

    def _gen_smart_report(self):
        """生成四段式智能报告。旧版这里前半段会被后半段覆盖成周报，现已拆开。"""
        game = self.rp_game.get()
        ctx = self._report_context(game)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            f"# {game if game != '全部' else '全游戏'}运营智能报告",
            "",
            f"- 生成时间：{now}",
            f"- 当前版本：{ctx['version']}",
            f"- 统计区间：{ctx['range']}",
            "",
            "## 1. 数据摘要",
            "",
        ]

        if ctx["has_metrics"]:
            lines += [
                f"- 平均 DAU **{ctx['avg_dau']:,.0f}**，"
                f"环比上期 **{ctx['dau_delta']:+.1f}%**",
                f"- 日均新增帖子 **{ctx['avg_posts']:,.0f}**，"
                f"累计评论 **{ctx['total_comments']:,.0f}**",
                f"- 平均互动率 **{ctx['avg_rate']:.2f}%**"
                + ("（低于健康线 4%）" if ctx["avg_rate"] < HEALTHY_RATE else "（处于健康区间）"),
                f"- 用户平均使用时长 **{ctx['avg_session']:.1f}** 分钟",
                "",
            ]
        else:
            lines += ["- 该区间暂无运营数据，以下结论基于版本与社区数据",
                      ""]

        lines += [
            "### 角色使用率 TOP5",
            "",
        ]
        if ctx["top_chars"]:
            for i, r in enumerate(ctx["top_chars"], 1):
                delta = ctx["char_deltas"].get(r["character_name"])
                tail = f"，较上版本 {delta:+.1f}pp" if delta is not None else ""
                lines.append(f"{i}. **{r['character_name']}** — "
                             f"{r['usage_rate']:.1f}%{tail}")
        else:
            lines.append("_尚无角色使用率数据_")

        lines += ["", "### 社区热度", ""]
        if ctx["posts"]:
            lines += [
                f"- 累计发帖 **{ctx['posts']:,}**，平均回复 **{ctx['replies']:.1f}**",
                f"- 各平台分布：{ctx['platform_txt']}",
            ]
        else:
            lines.append("_尚无社区热度数据_")

        # ── 2. 核心发现（规则驱动，不需要 AI 也能出结论）──
        lines += ["", "## 2. 核心发现", ""]
        findings = self._derive_findings(ctx)
        if findings:
            for i, f in enumerate(findings, 1):
                lines.append(f"{i}. **{f[0]}**：{f[1]}")
        else:
            lines.append("- 各项指标未触发异常规则，整体表现平稳")

        # ── 3. 风险与应对 ──
        lines += ["", "## 3. 风险与应对", ""]
        if ctx["risks"]:
            for r in ctx["risks"]:
                lvl = theme.RISK_LEVEL.get(r["probability"], ("中", WARNING))[0]
                lines.append(f"- **[{lvl}风险]** {r['title']}")
                if r["mitigation"]:
                    lines.append(f"  - 应对：{r['mitigation']}")
                if r["owner"]:
                    lines.append(f"  - 负责人：{r['owner']}")
        else:
            lines.append("- 当前没有登记风险项")

        # ── 4. 下一步计划（从真实逾期/未完成任务里生成，不是写死的清单）──
        lines += ["", "## 4. 下一步计划", ""]
        plans = self._derive_plans(ctx)
        for p in plans:
            lines.append(f"- [ ] {p}")

        lines += ["", "---",
                  "*报告由 米游社运营助手生成，结论基于本地数据库实时计算*"]

        report = "\n".join(lines)
        self._set_output(report)
        self.rp_status.configure(text=f"已生成 · {now}", text_color=SUCCESS)

    def _report_context(self, game):
        """把报告需要的所有数据一次取齐，避免生成过程里反复查库。"""
        g = None if game == "全部" else game
        v = latest_version(g)

        end = datetime.now()
        start = end - timedelta(days=30)
        rows = metrics_between(date_str(start), date_str(end), g)

        ctx = {
            "version": f"{v['game']} {v['version']}" if v else "未创建",
            "range": f"{date_str(start)} → {date_str(end)}",
            "has_metrics": bool(rows),
            "avg_dau": 0, "avg_posts": 0, "total_comments": 0,
            "avg_rate": 0.0, "avg_session": 0.0, "dau_delta": 0.0,
            "rate_delta": 0.0, "weekly": [], "version_row": v,
        }

        if rows:
            def avg(rs, k):
                vals = [r[k] for r in rs if r[k] is not None]
                return sum(vals) / len(vals) if vals else 0

            mid = max(1, len(rows) // 2)
            ctx["avg_dau"] = avg(rows, "dau")
            ctx["avg_posts"] = avg(rows, "new_posts")
            ctx["total_comments"] = sum(r["comments"] or 0 for r in rows)
            ctx["avg_rate"] = avg(rows, "interaction_rate")
            ctx["avg_session"] = avg(rows, "avg_session")

            prev_dau = avg(rows[:mid], "dau")
            if prev_dau:
                ctx["dau_delta"] = (avg(rows[mid:], "dau") - prev_dau) / prev_dau * 100
            ctx["rate_delta"] = (avg(rows[mid:], "interaction_rate")
                                 - avg(rows[:mid], "interaction_rate"))

            # 按周聚合，给报告一个可读的节奏感
            buckets = {}
            for r in rows:
                d = parse_date(r["date"])
                week_no = d.isocalendar()[1]
                buckets.setdefault(week_no, []).append(r)
            for wk in sorted(buckets):
                items = buckets[wk]
                ctx["weekly"].append((
                    f"{items[0]['date']} ~ {items[-1]['date']}",
                    avg(items, "dau"), avg(items, "interaction_rate")))

        # 版本相关
        ver_name = v["version"] if v else None
        ctx["top_chars"] = top_characters(ver_name, 5) if ver_name else []
        ctx["risks"] = open_risks(v["id"]) if v else []
        ctx["char_deltas"] = {}

        if ver_name:
            prev_row = previous_version(v)
            if prev_row:
                prev = prev_row["version"]
                for r in query(
                        "SELECT c.character_name, c.usage_rate AS cur, "
                        "p.usage_rate AS prev FROM char_usage c "
                        "JOIN char_usage p "
                        "ON c.character_name=p.character_name "
                        "WHERE c.version=? AND p.version=?",
                        (ver_name, prev)):
                    ctx["char_deltas"][r["character_name"]] = (
                        (r["cur"] or 0) - (r["prev"] or 0))

            posts, replies = community_summary(ver_name)
            ctx["posts"], ctx["replies"] = int(posts), replies
            platforms = query(
                "SELECT platform, post_count FROM community_hot "
                "WHERE version=? ORDER BY post_count DESC", (ver_name,))
            ctx["platform_txt"] = "、".join(
                f"{p['platform']} {int(p['post_count'] or 0):,}"
                for p in platforms) or "暂无数据"
        else:
            ctx["posts"], ctx["replies"], ctx["platform_txt"] = 0, 0, "暂无数据"

        # 任务与逾期（供「下一步计划」使用）
        ctx["overdue"] = []
        if v:
            ctx["overdue"] = query(
                "SELECT task, category, deadline FROM checklists "
                "WHERE version_id=? AND status!='done' AND deadline IS NOT NULL "
                "AND deadline < ? ORDER BY deadline", (v["id"], date_str()))

        return ctx

    def _derive_findings(self, ctx):
        """
        规则驱动的核心发现。
        关键点：AI 不可用时报告依然要有结论 —— 旧版这时候只输出
        「AI 正在生成…」这类占位文字，让人以为功能坏了。
        """
        out = []

        if ctx["has_metrics"]:
            if ctx["dau_delta"] > 3:
                out.append(("用户增长", f"DAU 环比上升 {ctx['dau_delta']:.1f}%，"
                                    f"达到 {ctx['avg_dau']:,.0f}，"
                                    f"版本内容的拉新效果明显"))
            elif ctx["dau_delta"] < -3:
                out.append(("用户流失", f"DAU 环比下降 {abs(ctx['dau_delta']):.1f}%，"
                                    f"降至 {ctx['avg_dau']:,.0f}，"
                                    f"需排查内容消耗速度与回流活动节奏"))

            if ctx["rate_delta"] < -0.3:
                out.append(("互动转弱",
                            f"互动率环比下滑 {abs(ctx['rate_delta']):.2f}pp，"
                            f"当前 {ctx['avg_rate']:.2f}%，"
                            f"说明内容吸引力下降，而非用户规模问题"))
            elif ctx["rate_delta"] > 0.3:
                out.append(("互动转好",
                            f"互动率环比提升 {ctx['rate_delta']:.2f}pp，"
                            f"社区讨论氛围改善"))

            if ctx["avg_dau"] and ctx["avg_rate"]:
                if ctx["dau_delta"] > 0 and ctx["rate_delta"] < 0:
                    out.append(("结构性矛盾",
                                "DAU 上升但互动率下滑 —— 新用户进来了但没有参与讨论，"
                                "建议做一次新人引导型内容"))

        big_drop = {k: v for k, v in ctx["char_deltas"].items() if v <= -5.0}
        if big_drop:
            names = "、".join(f"{k}({v:+.1f}pp)" for k, v in big_drop.items())
            out.append(("角色异动", f"{names} 使用率显著下滑，"
                                f"需评估数值或配队环境变化"))

        if ctx["posts"]:
            if ctx["replies"] < 8:
                out.append(("讨论深度不足",
                            f"平均回复仅 {ctx['replies']:.1f}，"
                            f"话题停留在点赞层面，建议增加引导性提问"))

        return out

    def _derive_plans(self, ctx):
        """下一步计划从真实数据推导，而不是写死四条。"""
        plans = []

        if ctx["overdue"]:
            plans.append(f"清理 {len(ctx['overdue'])} 项逾期任务，"
                         f"最紧急的是「{ctx['overdue'][0]['task']}」"
                         f"（截止 {ctx['overdue'][0]['deadline']}）")

        high = [r for r in ctx["risks"] if r["probability"] == "high"]
        if high:
            plans.append(f"处理 {len(high)} 项高概率风险，"
                         f"优先「{high[0]['title'][:24]}」")

        if ctx["has_metrics"] and ctx["avg_rate"] < HEALTHY_RATE:
            plans.append(f"策划一轮互动引导活动，目标把互动率从 "
                         f"{ctx['avg_rate']:.2f}% 拉回 {HEALTHY_RATE:.0f}% 以上")

        v = ctx["version_row"]
        if v:
            total_t, done_t = task_progress(v["id"])
            if total_t and done_t < total_t:
                plans.append(f"推进版本任务收尾（当前 {done_t}/{total_t}）")

        if not plans:
            plans.append("持续录入每日指标，保持复盘节奏")

        plans.append("版本结束后 3 日内完成复盘会议，与本期指标做对比")
        return plans

    def _set_output(self, text):
        try:
            self.rp_output.delete("1.0", "end")
            self.rp_output.insert("1.0", text)
        except Exception:
            pass

    def _save_smart_report(self):
        try:
            content = self.rp_output.get("1.0", "end").strip()
        except Exception:
            content = ""
        if not content or content.startswith("暂无"):
            self.toast("还没有可保存的报告", WARNING)
            return
        game = self.rp_game.get()
        title = (f"{game if game != '全部' else '全游戏'}智能报告 · "
                 f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        self._archive(title, content, "智能报告")

    # ═══════════════════════════════════════════════════════
    #  AI 深化
    # ═══════════════════════════════════════════════════════
    def _gen_ai_report(self):
        try:
            base_text = self.rp_output.get("1.0", "end").strip()
        except Exception:
            base_text = ""
        if not base_text:
            self.toast("请先生成报告草稿", WARNING)
            return

        token = load_config("ai_api_key")
        game = self.rp_game.get()

        def build():
            return f"""你是一名游戏运营负责人。下面是一份由工具自动生成的{game}运营报告草稿。
请在保留全部数据事实的前提下，改写成一份可以直接交给上级的报告。

要求：
1. 开头用 3 句话说清「本期最重要的结论」，不要先说背景
2. 保留数字，但把数字翻译成业务含义（例如"互动率 2.4%"要说清这意味着什么）
3. 风险部分必须给出明确的优先级排序和责任人建议
4. 删掉所有套话，不要出现"综上所述""赋能""抓手"这类词
5. 结尾给出 3 条下周期最关键的动作，每条不超过 25 字

草稿如下：

{base_text[:6000]}"""

        self.rp_status.configure(text="AI 生成中…", text_color=WARNING)
        self._set_output(base_text + "\n\n---\n\n_AI 正在深化，请稍候…_")

        def worker():
            if not token:
                result = self._local_deepen(base_text)
                result += ("\n\n---\n_（未配置 API Key，以上为本地规则生成的深化版本。"
                           "填入 Key 后可获得真正的语义改写。）_")
                self.after(0, lambda: self._on_ai_report(result, None))
                return

            base = load_config("ai_base_url", "https://api.deepseek.com")
            model = load_config("ai_model", "deepseek-chat")
            try:
                from openai import OpenAI
                client = OpenAI(api_key=token, base_url=base, timeout=45)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": build()}],
                    temperature=0.6)
                result = resp.choices[0].message.content
                self.after(0, lambda: self._on_ai_report(result, None))
            except Exception as e:
                err = str(e)[:110]
                result = self._local_deepen(base_text)
                result += f"\n\n---\n_（AI 调用失败，已降级为本地深化。原因：{err}）_"
                self.after(0, lambda: self._on_ai_report(result, err))

        threading.Thread(target=worker, daemon=True).start()

    def _local_deepen(self, base_text):
        """
        离线深化：把草稿里的数字拎出来，加一层解读。
        比直接返回「AI 不可用」有价值得多 —— 演示时不会因为没配 Key 就空白。
        """
        game = self.rp_game.get()
        ctx = self._report_context(game)

        lines = [f"# {game if game != '全部' else '全游戏'}运营报告（深化版）", ""]

        lines.append("## 本期最重要的三件事")
        lines.append("")
        n = 0
        findings = self._derive_findings(ctx)
        for title, desc in findings[:3]:
            n += 1
            lines.append(f"**{n}. {title}** —— {desc}")
        if n == 0:
            lines.append("本期各项指标未触发异常规则，重点应放在保持节奏上。")

        lines += ["", "## 数据事实", ""]
        if ctx["has_metrics"]:
            lines += [
                f"- 平均 DAU {ctx['avg_dau']:,.0f}，环比 {ctx['dau_delta']:+.1f}%",
                f"- 平均互动率 {ctx['avg_rate']:.2f}%，环比 {ctx['rate_delta']:+.2f}pp",
                f"- 日均帖子 {ctx['avg_posts']:,.0f}，累计评论 {ctx['total_comments']:,.0f}",
            ]
            if ctx["avg_rate"] < WARN_RATE:
                lines.append(f"- 互动率 {ctx['avg_rate']:.2f}% 已跌破警戒线 "
                             f"{WARN_RATE}%，属于需要立即介入的区间")
            elif ctx["avg_rate"] < HEALTHY_RATE:
                lines.append(f"- 互动率 {ctx['avg_rate']:.2f}% 低于健康线 "
                             f"{HEALTHY_RATE}%，但尚未跌破警戒线")
        else:
            lines.append("- 本期没有录入运营数据，无法给出量化结论")

        lines += ["", "## 下周期关键动作", ""]
        for i, p in enumerate(self._derive_plans(ctx)[:3], 1):
            lines.append(f"{i}. {p}")

        lines += ["", "---", "_本深化版由本地规则生成，未调用外部模型。_"]
        return "\n".join(lines)

    def _on_ai_report(self, result, error):
        self._set_output(result)
        if error:
            self.rp_status.configure(text="已降级为本地深化", text_color=WARNING)
        else:
            self.rp_status.configure(text="AI 已深化", text_color=SUCCESS)
        self.log("生成 AI 报告", self.rp_game.get())

    # ═══════════════════════════════════════════════════════
    #  Tab 2 · 周期报表
    # ═══════════════════════════════════════════════════════
    def _build_period(self, parent):
        bar = ctk.CTkFrame(parent, fg_color="transparent", height=1)
        bar.pack(fill="x", pady=(0, SP_MD))

        self.rp_game = C.Field(bar, "游戏", kind="menu", values=["全部"] + GAMES,
                               width=150, label_width=40, default=GAMES[1])
        self.rp_game.pack(side="left")

        self.rp_days = C.Field(bar, "区间", kind="menu",
                               values=["近 7 天", "近 14 天", "近 30 天", "近 90 天"],
                               width=110, label_width=40, default="近 7 天")
        self.rp_days.pack(side="left", padx=(SP_MD, 0))

        C.PrimaryButton(bar, "生成报表", self._gen_period_report, icon="chart",
                        width=116, height=30).pack(side="right")

        self._build_output_card(parent, "报表正文", icon="calendar")
        self._build_output_toolbar(
            parent,
            on_save=self._save_period_report,
            on_csv=self._export_period_csv,
        )

        self._gen_period_report()

    def _period_days(self):
        return {"近 7 天": 7, "近 14 天": 14,
                "近 30 天": 30, "近 90 天": 90}.get(self.rp_days.get(), 7)

    def _gen_period_report(self):
        game = self.rp_game.get()
        days = self._period_days()
        g = None if game == "全部" else game

        end = datetime.now()
        start = end - timedelta(days=days)
        rows = metrics_between(date_str(start), date_str(end), g)

        if not rows:
            self._set_output(
                f"# {game} 运营报表\n\n"
                f"**周期**：{date_str(start)} → {date_str(end)}\n\n"
                f"该时间范围内没有数据。请到「数据」页录入，"
                f"或点击数据页的「载入演示数据」快速填充。")
            self.rp_status.configure(text="无数据", text_color=WARNING)
            return

        label = "周报" if days <= 7 else ("双周报" if days <= 14 else
                                     ("月报" if days <= 30 else "季度报表"))

        def avg(k):
            vals = [r[k] for r in rows if r[k] is not None]
            return sum(vals) / len(vals) if vals else 0

        total_posts = sum(r["new_posts"] or 0 for r in rows)
        total_comments = sum(r["comments"] or 0 for r in rows)
        avg_rate = avg("interaction_rate")
        peak = max(rows, key=lambda r: r["dau"] or 0)
        trough = min(rows, key=lambda r: r["dau"] or 0)

        lines = [
            f"# {game if game != '全部' else '全游戏'}运营{label}",
            "",
            f"- **报告周期**：{date_str(start)} → {date_str(end)}（{len(rows)} 天）",
            f"- **生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 1. 核心指标",
            "",
            "| 指标 | 数值 | 说明 |",
            "|------|------|------|",
            f"| 平均 DAU | {avg('dau'):,.0f} | 区间日均 |",
            f"| DAU 峰值 | {peak['dau']:,} | {peak['date']} |",
            f"| DAU 谷值 | {trough['dau']:,} | {trough['date']} |",
            f"| 新增帖子（合计） | {total_posts:,} | 日均 {total_posts/len(rows):,.0f} |",
            f"| 评论数（合计） | {total_comments:,} | 日均 {total_comments/len(rows):,.0f} |",
            f"| 平均互动率 | {avg_rate:.2f}% | 健康线 {HEALTHY_RATE:.0f}% |",
            f"| 平均使用时长 | {avg('avg_session'):.1f} 分钟 | 区间均值 |",
            "",
        ]

        # 环比
        mid = max(1, len(rows) // 2)
        prev_rate = avg("interaction_rate") if len(rows) < 2 else (
            sum(r["interaction_rate"] or 0 for r in rows[:mid]) / mid)
        cur_rate = sum(r["interaction_rate"] or 0
                       for r in rows[mid:]) / max(1, len(rows) - mid)

        lines += ["## 2. 趋势判断", ""]
        if avg_rate < WARN_RATE:
            lines.append(f"- 互动率 {avg_rate:.2f}% 低于警戒线 {WARN_RATE:.0f}%，"
                         f"需立即排查内容吸引力问题")
        elif avg_rate < HEALTHY_RATE:
            lines.append(f"- 互动率 {avg_rate:.2f}% 低于健康线 {HEALTHY_RATE:.0f}%，"
                         f"建议加强话题引导")
        else:
            lines.append(f"- 互动率 {avg_rate:.2f}% 处于健康区间")

        if cur_rate < prev_rate:
            lines.append(f"- 后半段互动率（{cur_rate:.2f}%）低于前半段"
                         f"（{prev_rate:.2f}%），呈下滑趋势")
        else:
            lines.append(f"- 后半段互动率（{cur_rate:.2f}%）高于前半段"
                         f"（{prev_rate:.2f}%），走势向好")

        lines += ["", "## 3. 每日明细", "",
                  "| 日期 | 游戏 | DAU | 帖子 | 评论 | 时长 | 互动率 |",
                  "|------|------|-----|------|------|------|--------|"]
        for r in rows:
            lines.append(
                f"| {r['date']} | {r['game']} | {r['dau']:,} | {r['new_posts']:,} | "
                f"{r['comments']:,} | {r['avg_session']:.1f} | "
                f"{r['interaction_rate']:.2f}% |")

        lines += ["", "---",
                  f"*{len(rows)} 条记录，由 米游社运营助手 自动汇总*"]

        self._set_output("\n".join(lines))
        self.rp_status.configure(
            text=f"{len(rows)} 条记录 · {date_str(start)} 起", text_color=SUCCESS)

    def _save_period_report(self):
        try:
            content = self.rp_output.get("1.0", "end").strip()
        except Exception:
            content = ""
        if not content:
            self.toast("还没有可保存的报表", WARNING)
            return
        game = self.rp_game.get()
        days = self._period_days()
        title = (f"{game if game != '全部' else '全游戏'}近{days}天报表 · "
                 f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        self._archive(title, content, "周期报表")

    def _export_period_csv(self):
        game = self.rp_game.get()
        days = self._period_days()
        g = None if game == "全部" else game
        end = datetime.now()
        start = end - timedelta(days=days)
        rows = metrics_between(date_str(start), date_str(end), g)

        if not rows:
            self.toast("当前区间没有数据可导出", WARNING)
            return

        path = filedialog.asksaveasfilename(
            title="导出报表数据", defaultextension=".csv",
            initialfile=f"{game}_运营数据_{date_str(start)}_{date_str(end)}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return

        # 用列名取值，不再依赖 SELECT * 的列序（旧版加字段就会错位）
        cols = ["date", "game", "dau", "new_posts", "comments",
                "avg_session", "interaction_rate"]
        headers = ["日期", "游戏", "DAU", "新增帖子", "评论数",
                   "平均时长", "互动率"]
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for r in rows:
                    w.writerow([r[c] for c in cols])
        except Exception as e:
            self.toast(f"导出失败：{e}", DANGER)
            return

        self.log("导出报表", f"{len(rows)} 条")
        self.toast(f"已导出 {len(rows)} 条到 {os.path.basename(path)}")

    # ═══════════════════════════════════════════════════════
    #  Tab 3 · 历史归档
    # ═══════════════════════════════════════════════════════
    def _build_history(self, parent):
        reports = query("SELECT id, title, type, created_at, "
                        "LENGTH(content) AS size FROM reports "
                        "ORDER BY id DESC LIMIT 100")

        card = C.Card(parent)
        card.pack(fill="both", expand=True)

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "报告归档", icon="folder").pack(side="left")
        ctk.CTkLabel(head, text=f"共 {len(reports)} 份",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="right")

        if not reports:
            C.EmptyState(card.body, "还没有归档的报告", "folder",
                         "在「智能报告」或「周期报表」里生成后点「保存归档」",
                         height=180).pack(fill="both", expand=True)
            return

        box = ctk.CTkScrollableFrame(card.body, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=SP_LG, pady=(0, SP_MD))

        for r in reports:
            row = ctk.CTkFrame(box, fg_color=BG_CARD, corner_radius=6)
            row.pack(fill="x", pady=3)
            inner = ctk.CTkFrame(row, fg_color="transparent", height=1)
            inner.pack(fill="x", padx=SP_MD, pady=SP_SM)

            type_color = {"智能报告": AI, "AI分析": AI,
                          "周期报表": INFO}.get(r["type"], NEUTRAL)
            icons.draw_icon(inner, "doc", 13, type_color).pack(side="left", pady=2)

            mid = ctk.CTkFrame(inner, fg_color="transparent", height=1)
            mid.pack(side="left", fill="x", expand=True, padx=SP_SM)
            ctk.CTkLabel(mid, text=r["title"], font=font(SIZE_SMALL),
                         text_color=TEXT_BODY, anchor="w").pack(anchor="w")
            ctk.CTkLabel(mid,
                         text=f"{r['type']} · {r['created_at']} · "
                              f"{r['size'] or 0} 字符",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                         anchor="w").pack(anchor="w")

            C.GhostButton(inner, "查看",
                          lambda rid=r["id"]: self._view_report(rid),
                          width=64, height=26).pack(side="right")
            C.IconButton(inner, "trash",
                         lambda rid=r["id"], t=r["title"]:
                         self._delete_report(rid, t),
                         size=24).pack(side="right", padx=(0, SP_XS))

    def _view_report(self, rid):
        row = query("SELECT * FROM reports WHERE id=?", (rid,), one=True)
        if not row:
            self.toast("报告不存在", DANGER)
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(row["title"])
        dlg.transient(self)
        dlg.configure(fg_color=BG_APP)
        self._center(dlg, 760, 640)

        head = ctk.CTkFrame(dlg, fg_color=BG_CARD, corner_radius=0)
        head.pack(fill="x")
        hrow = ctk.CTkFrame(head, fg_color="transparent", height=1)
        hrow.pack(fill="x", padx=SP_XL, pady=SP_MD)

        left = ctk.CTkFrame(hrow, fg_color="transparent", height=1)
        left.pack(side="left")
        ctk.CTkLabel(left, text=row["title"], font=font(SIZE_H3, bold=True),
                     text_color=TEXT_PRIMARY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(left, text=f"{row['type']} · {row['created_at']}",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                     anchor="w").pack(anchor="w")

        C.IconButton(hrow, "close", dlg.destroy, size=28).pack(side="right")

        box = ctk.CTkTextbox(dlg, fg_color=BG_APP, text_color=TEXT_BODY,
                             font=font(SIZE_BODY), wrap="word",
                             border_width=0)
        box.pack(fill="both", expand=True, padx=SP_MD, pady=SP_MD)
        box.insert("1.0", row["content"] or "")
        box.configure(state="disabled")

        acts = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        acts.pack(fill="x", padx=SP_XL, pady=(0, SP_LG))

        def copy_it():
            try:
                self.clipboard_clear()
                self.clipboard_append(row["content"] or "")
                self.toast("已复制到剪贴板")
            except Exception as e:
                self.toast(f"复制失败：{e}", DANGER)

        C.GhostButton(acts, "复制", copy_it, icon="copy",
                      width=88, height=30).pack(side="left")
        C.GhostButton(acts, "删除", lambda: self._delete_report(
            rid, row["title"], dlg), icon="trash",
            width=88, height=30).pack(side="left", padx=(SP_SM, 0))

        try:
            dlg.grab_set()
        except Exception:
            pass

    def _delete_report(self, rid, title, dlg=None):
        try:
            execute("DELETE FROM reports WHERE id=?", (rid,))
        except Exception as e:
            self.toast(f"删除失败：{e}", DANGER)
            return
        if dlg:
            try:
                dlg.destroy()
            except Exception:
                pass
        self.log("删除报告", title[:24])
        self.toast("已删除该报告")
        self.remount("report")

    def _center(self, win, w, h):
        self.update_idletasks()
        x = max(0, self.winfo_rootx() + (self.winfo_width() - w) // 2)
        y = max(0, self.winfo_rooty() + (self.winfo_height() - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    # ── Ctrl+S ──
    def _save_report(self):
        if self._report_tab == "smart":
            self._save_smart_report()
        elif self._report_tab == "period":
            self._save_period_report()
        else:
            self.toast("历史归档页无需保存", WARNING)
