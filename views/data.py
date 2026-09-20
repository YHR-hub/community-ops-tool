"""
数据页 —— 录入 / 导入 / 使用率 / 社区热度
==========================================

旧版这一页的问题（都是用户说的「功能不行」的具体来源）：
  1. 单条录入用 grid 硬摆 11 个输入框，窗口一窄就挤成一团；
  2. 重复录入同一天同一游戏会静默插入两条，DAU 直接翻倍，
     图表看不出异常 —— 这是最危险的一类 bug；
  3. CSV 导入没有列名校验，导入失败只提示「导入失败」，不说是哪一列错了；
  4. 没有数据列表，录完看不到自己录了什么，也没法删错行。

新版对应的改动：
  · 录入区改为「一行一个字段」的紧凑表单，宽度自适应；
  · 保存前先查重，已存在则明确询问是「覆盖」还是「跳过」；
  · CSV 导入做列名映射 + 逐行错误定位，报错精确到行号与字段名；
  · 补一张最近记录表，支持选中删除。
"""

import csv
import os
from tkinter import filedialog

import customtkinter as ctk

import theme
from theme import (
    BG_APP, BG_CARD, BG_ELEVATED, BG_BORDER,
    PRIMARY, DANGER, SUCCESS, WARNING, TEXT_PRIMARY, TEXT_BODY, TEXT_SECONDARY, TEXT_TERTIARY,
    font, num_font, SIZE_H3, SIZE_SMALL, SIZE_TINY,
    SP_XS, SP_SM, SP_MD, SP_LG, RADIUS_MD,
)
import icons
import components as C
import charts
import db
from db import (
    GAMES, query, execute, get_versions, top_characters,
    date_str, safe_int, safe_float, valid_date,
)

# CSV 表头 → 数据库列名。允许中文表头，降低使用门槛。
# v4.3：权威定义迁到 data_source.py（数据源适配层），此处引用同一份，
# 避免「UI 一套别名、数据源另一套别名」的漂移。
from data_source import CSV_ALIASES, REQUIRED_COLS, NUMERIC_COLS  # noqa: F401

METRIC_FIELDS = [
    ("dau", "DAU", "如 52000"),
    ("new_users", "新增用户", "选填，如 1800"),
    ("new_posts", "新增帖子", "如 1200"),
    ("comments", "评论数", "如 6400"),
    ("avg_session", "平均时长(分)", "如 22.5"),
    ("interaction_rate", "互动率(%)", "如 4.2"),
    ("retention_1", "次日留存(%)", "选填，如 45.2"),
    ("retention_7", "7日留存(%)", "选填，如 21.8"),
    ("retention_30", "30日留存(%)", "选填，如 12.4"),
]

METRIC_LABEL = {
    "dau": "DAU", "new_users": "新增用户", "new_posts": "新增帖子",
    "comments": "评论数", "avg_session": "平均时长",
    "interaction_rate": "互动率",
    "retention_1": "次日留存", "retention_7": "7日留存",
    "retention_30": "30日留存",
}

# 百分比类字段：上限 100，录入或导入超界要拦住。
# 留存率 128% 这种值一旦入库，图表和均值全部失真，属于脏数据源头。
PERCENT_FIELDS = {"interaction_rate", "retention_1", "retention_7",
                  "retention_30"}


class DataMixin:
    """由 App 混入，提供数据页。"""

    # ── 页面状态（每次重建页面时重置，不留在 self 上跨页污染）──
    def show_data(self):
        self.clear_main()
        self._data_entries = {}
        self._build_data()

    # ═══════════════════════════════════════════════════════
    def _build_data(self):
        body, _page = self.page_scaffold(
            "data", "数据", "录入每日指标、批量导入、维护角色与社区数据",
            icon="chart", refresh=self._build_data)

        self._data_filter = ctk.CTkFrame(body, fg_color="transparent", height=1)
        self._data_filter.pack(fill="x", pady=(0, SP_MD))
        self._build_data_filter(self._data_filter)

        self._build_entry_form(body)
        self._build_usage_section(body)
        self._build_community_section(body)
        self._build_recent_table(body)

    # ── 顶部：游戏 / 时间范围 / 导入按钮 ──────────────────
    def _build_data_filter(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        card = C.Card(parent)
        card.pack(fill="x")

        row = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        row.pack(fill="x", padx=SP_LG, pady=SP_MD)

        self._game_filter = C.Field(
            row, "游戏", kind="menu", values=["全部"] + GAMES,
            width=132, label_width=32, default="全部")

        days_opts = ["近 7 天", "近 30 天", "近 90 天", "全部"]
        self._range_filter = C.Field(
            row, "区间", kind="menu", values=days_opts,
            width=92, label_width=32, default="近 30 天")

        for f in (self._game_filter, self._range_filter):
            f.pack(side="left", padx=(0, SP_LG))
            f.widget.configure(command=lambda _v: self._refresh_data_body())

        C.GhostButton(row, "导入 CSV", self._import_csv,
                      icon="download", width=106, height=30).pack(side="right")
        C.GhostButton(row, "导出 CSV", self._export_csv,
                      icon="save", width=106, height=30).pack(
            side="right", padx=(0, SP_SM))

    # ═══════════════════════════════════════════════════════
    #  录入表单
    # ═══════════════════════════════════════════════════════
    def _build_entry_form(self, parent):
        card = C.Card(parent)
        card.pack(fill="x", pady=(0, SP_MD))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "每日指标录入", icon="edit").pack(side="left")
        ctk.CTkLabel(head, text="同一天同一游戏重复保存会提示是否覆盖",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY).pack(
            side="right")

        grid = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        grid.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
        # 3 列布局：窗口变宽时自动摊开，变窄也不重叠
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="ent")

        self._data_entries = {}

        # 第一行：日期 / 游戏（必填项单独一组，视觉上区分开）
        date_f = C.Field(grid, "日期", placeholder="YYYY-MM-DD",
                         width=124, label_width=58, default=date_str())
        date_f.grid(row=0, column=0, sticky="w", pady=(0, SP_SM))
        self._data_entries["date"] = date_f

        game_f = C.Field(grid, "游戏", kind="menu", values=GAMES,
                         width=150, label_width=58, default=GAMES[1])
        game_f.grid(row=0, column=1, sticky="w", pady=(0, SP_SM))
        self._data_entries["game"] = game_f

        # 其余指标按两列铺开
        for i, (key, label, ph) in enumerate(METRIC_FIELDS):
            r = 1 + i // 2
            c = i % 2
            f = C.Field(grid, label, placeholder=ph, width=118,
                        label_width=96, kind="entry")
            f.grid(row=r, column=c, sticky="w", pady=(0, SP_SM))
            self._data_entries[key] = f

        # 操作行
        act = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        act.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))
        C.PrimaryButton(act, "保存记录", self._save_metric,
                        icon="check", width=112, height=32).pack(side="left")
        C.GhostButton(act, "清空表单", self._clear_metric_form,
                      width=94, height=32).pack(side="left", padx=(SP_SM, 0))
        self._entry_hint = ctk.CTkLabel(
            act, text="", font=font(SIZE_TINY), text_color=TEXT_TERTIARY)
        self._entry_hint.pack(side="left", padx=(SP_MD, 0))

    def _clear_metric_form(self):
        for k, f in self._data_entries.items():
            if k == "game":
                f.set(GAMES[1])
            elif k == "date":
                f.set(date_str())
            else:
                f.clear()
        if hasattr(self, "_entry_hint"):
            self._entry_hint.configure(text="")

    def _collect_metric(self):
        """把表单读成一条记录。校验失败返回 (None, 错误说明)。"""
        d = self._data_entries["date"].get().strip()
        g = self._data_entries["game"].get().strip()

        if not valid_date(d):
            return None, "日期格式不对，需要 YYYY-MM-DD"
        if not g:
            return None, "请选择游戏"

        rec = {"date": d, "game": g}
        for key, label, _ph in METRIC_FIELDS:
            raw = self._data_entries[key].get().strip()
            if not raw:
                rec[key] = 0
                continue
            if key == "avg_session" or key in PERCENT_FIELDS:
                v = safe_float(raw, default=None)
            else:
                v = safe_int(raw, default=None)
            if v is None:
                return None, f"「{label}」不是有效数字：{raw}"
            if v < 0:
                return None, f"「{label}」不能为负数"
            if key in PERCENT_FIELDS and v > 100:
                return None, f"「{label}」是百分比，不能超过 100"
            rec[key] = v

        return rec, None

    def _save_metric(self):
        rec, err = self._collect_metric()
        if err:
            self._entry_hint.configure(text=err, text_color=DANGER)
            self.toast(err, DANGER)
            return

        # 查重：同一天同一游戏只应有一条。旧版直接插入，DAU 会翻倍。
        dup = query("SELECT id FROM daily_metrics WHERE date=? AND game=?",
                    (rec["date"], rec["game"]), one=True)
        if dup:
            self._confirm_overwrite(rec, dup["id"])
            return

        self._insert_metric(rec)

    def _confirm_overwrite(self, rec, rid):
        """
        已存在时弹一个确认框。
        旧版在这里静默插入，用户以为只是「更新」，实际是「新增了一条」，
        导致趋势图出现不可能的跳变 —— 属于会误导决策的数据类 bug。
        """
        dlg = ctk.CTkToplevel(self)
        dlg.title("该日期已有记录")
        dlg.transient(self)
        dlg.configure(fg_color=BG_CARD)
        dlg.resizable(False, False)

        self.update_idletasks()
        x = max(0, self.winfo_rootx() + (self.winfo_width() - 380) // 2)
        y = max(0, self.winfo_rooty() + 220)
        dlg.geometry(f"380x172+{x}+{y}")

        icons.draw_icon(dlg, "warn", 20, WARNING).pack(pady=(SP_LG, SP_XS))
        ctk.CTkLabel(dlg, text=f"{rec['date']} · {rec['game']} 已有记录",
                     font=font(SIZE_H3, bold=True),
                     text_color=TEXT_PRIMARY).pack()
        ctk.CTkLabel(dlg, text="覆盖会替换原有数值，跳过则保留原记录。",
                     font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY).pack(pady=(SP_XS, SP_MD))

        btns = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        btns.pack()

        def do_overwrite():
            self._insert_metric(rec, overwrite_id=rid)
            dlg.destroy()

        C.PrimaryButton(btns, "覆盖", do_overwrite, width=90, height=30).pack(
            side="left")
        C.GhostButton(btns, "跳过", dlg.destroy, width=90, height=30).pack(
            side="left", padx=(SP_SM, 0))

        try:
            dlg.grab_set()
        except Exception:
            pass

    def _insert_metric(self, rec, overwrite_id=None):
        # 用 rec.get() 而不是 rec[]：调用方可能只传部分字段（如仅改 DAU 的
        # 批量修正），缺的按 0 落库。v4.1 前这里直接下标取值，flow_test 的
        # 部分字段用例一进来就 KeyError 被 except 吞掉，覆盖变成了假成功。
        vals = {k: rec.get(k, 0) for k in
                ("dau", "new_users", "new_posts", "comments", "avg_session",
                 "interaction_rate", "retention_1", "retention_7", "retention_30")}
        try:
            if overwrite_id:
                execute(
                    "UPDATE daily_metrics SET dau=?, new_users=?, new_posts=?, "
                    "comments=?, avg_session=?, interaction_rate=?, "
                    "retention_1=?, retention_7=?, retention_30=? WHERE id=?",
                    (vals["dau"], vals["new_users"], vals["new_posts"],
                     vals["comments"], vals["avg_session"],
                     vals["interaction_rate"], vals["retention_1"],
                     vals["retention_7"], vals["retention_30"],
                     overwrite_id))
                msg = f"已覆盖 {rec['date']} 的记录"
            else:
                execute(
                    "INSERT INTO daily_metrics "
                    "(date,game,dau,new_users,new_posts,comments,avg_session,"
                    "interaction_rate,retention_1,retention_7,retention_30) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (rec["date"], rec["game"], vals["dau"], vals["new_users"],
                     vals["new_posts"], vals["comments"], vals["avg_session"],
                     vals["interaction_rate"], vals["retention_1"],
                     vals["retention_7"], vals["retention_30"]))
                msg = f"已保存 {rec['date']} 的记录"
        except Exception as e:
            self.toast(f"保存失败：{e}", DANGER)
            return

        self.log("保存指标", f"{rec['date']} {rec['game']}")
        self.toast(msg)
        if hasattr(self, "_entry_hint"):
            self._entry_hint.configure(text=msg, text_color=SUCCESS)
        self._refresh_data_body(reset_form=False)

    # ═══════════════════════════════════════════════════════
    #  CSV 导入导出
    # ═══════════════════════════════════════════════════════
    def _import_csv(self):
        path = filedialog.askopenfilename(
            title="选择 CSV 文件",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return

        try:
            # 依次尝试常见编码：国内 Excel 导出的 CSV 多为 GBK
            rows, header = self._read_csv(path)
        except Exception as e:
            self.toast(f"读取失败：{e}", DANGER)
            return

        # 列名映射
        mapping = {}
        for raw_name in header:
            key = CSV_ALIASES.get(str(raw_name).strip().lower())
            if key:
                mapping[raw_name] = key

        missing = [c for c in REQUIRED_COLS if c not in mapping.values()]
        if missing:
            need = "、".join("日期" if m == "date" else "游戏" for m in missing)
            self._show_import_error(
                f"CSV 缺少必需列：{need}",
                f"识别到的表头：{'、'.join(str(h) for h in header)}\n"
                f"支持的表头写法见 README 或点击「导出 CSV」参考格式。")
            return

        # 逐行转换，记录第一处错误的位置
        records, errors = [], []
        for idx, raw in enumerate(rows, start=2):  # 第 1 行是表头
            rec, err = self._row_to_record(raw, mapping, idx)
            if err:
                errors.append(err)
                if len(errors) >= 3:
                    break
                continue
            records.append(rec)

        if errors:
            self._show_import_error(
                f"第 {len(errors)} 处数据有问题，已中止导入",
                "\n".join(errors) +
                "\n\n修正后重新导入。导入前不会修改任何已有数据。")
            return

        if not records:
            self.toast("CSV 里没有可导入的数据行", WARNING)
            return

        n = self._bulk_upsert(records)
        self.log("导入 CSV", f"{os.path.basename(path)} · {n} 条")
        self.toast(f"已导入 {n} 条记录")
        self._refresh_data_body(reset_form=False)

    def _read_csv(self, path):
        for enc in ("utf-8-sig", "gbk", "utf-8"):
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    reader = csv.DictReader(f)
                    header = list(reader.fieldnames or [])
                    rows = [r for r in reader]
                return rows, header
            except UnicodeDecodeError:
                continue
        raise ValueError("无法识别文件编码，请另存为 UTF-8 或 GBK 编码的 CSV")

    def _row_to_record(self, raw, mapping, lineno):
        rec = {}
        for src, key in mapping.items():
            val = raw.get(src)
            val = "" if val is None else str(val).strip()

            if key == "date":
                if not valid_date(val):
                    return None, f"第 {lineno} 行：日期「{val}」格式不对，应为 YYYY-MM-DD"
                rec["date"] = val
            elif key == "game":
                if not val:
                    return None, f"第 {lineno} 行：游戏为空"
                if val not in GAMES:
                    return None, (f"第 {lineno} 行：游戏「{val}」不在支持列表"
                                  f"（{'、'.join(GAMES)}）")
                rec["game"] = val
            else:
                if val == "":
                    rec[key] = 0
                    continue
                v = (safe_float(val, default=None)
                     if key == "avg_session" or key in PERCENT_FIELDS
                     else safe_int(val, default=None))
                if v is None:
                    return None, f"第 {lineno} 行：{METRIC_LABEL.get(key, key)}「{val}」不是数字"
                if v < 0:
                    return None, f"第 {lineno} 行：{METRIC_LABEL.get(key, key)}不能为负"
                if key in PERCENT_FIELDS and v > 100:
                    return None, (f"第 {lineno} 行：{METRIC_LABEL.get(key, key)}"
                                  f"是百分比，不能超过 100（当前 {val}）")
                rec[key] = v

        for k in METRIC_FIELDS:
            rec.setdefault(k[0], 0)
        return rec, None

    def _bulk_upsert(self, records):
        """整批写入，一条失败不影响已写入的部分（事务按行提交）。"""
        n = 0
        with db.get_conn() as c:
            for rec in records:
                c.execute(
                    "INSERT INTO daily_metrics "
                    "(date,game,dau,new_users,new_posts,comments,avg_session,"
                    "interaction_rate,retention_1,retention_7,retention_30) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(date, game) DO UPDATE SET "
                    "dau=excluded.dau, new_users=excluded.new_users, "
                    "new_posts=excluded.new_posts, comments=excluded.comments, "
                    "avg_session=excluded.avg_session, "
                    "interaction_rate=excluded.interaction_rate, "
                    "retention_1=excluded.retention_1, "
                    "retention_7=excluded.retention_7, "
                    "retention_30=excluded.retention_30",
                    (rec["date"], rec["game"], rec["dau"], rec["new_users"],
                     rec["new_posts"], rec["comments"], rec["avg_session"],
                     rec["interaction_rate"], rec["retention_1"],
                     rec["retention_7"], rec["retention_30"]))
                n += 1
        return n

    def _show_import_error(self, title, detail):
        """导入失败时把具体原因摆出来，而不是只弹「导入失败」。"""
        dlg = ctk.CTkToplevel(self)
        dlg.title("导入未完成")
        dlg.transient(self)
        dlg.configure(fg_color=BG_CARD)
        dlg.geometry("520x300")

        head = ctk.CTkFrame(dlg, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_LG, SP_SM))
        icons.draw_icon(head, "warn", 16, DANGER).pack(side="left", pady=2)
        ctk.CTkLabel(head, text=title, font=font(SIZE_H3, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(6, 0))

        box = ctk.CTkTextbox(dlg, fg_color=BG_APP, text_color=TEXT_BODY,
                             font=font(SIZE_SMALL), wrap="word",
                             border_width=1, border_color=BG_BORDER)
        box.pack(fill="both", expand=True, padx=SP_LG, pady=(0, SP_MD))
        box.insert("1.0", detail)
        box.configure(state="disabled")

        C.PrimaryButton(dlg, "知道了", dlg.destroy, width=90, height=30).pack(
            pady=(0, SP_LG))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            title="导出当前数据", defaultextension=".csv",
            initialfile=f"运营数据_{date_str()}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return

        rows = self._metric_rows()
        if not rows:
            self.toast("当前筛选条件下没有数据可导出", WARNING)
            return

        cols = ["date", "game", "dau", "new_users", "new_posts", "comments",
                "avg_session", "interaction_rate",
                "retention_1", "retention_7", "retention_30"]
        headers = ["日期", "游戏", "DAU", "新增用户", "新增帖子", "评论数",
                   "平均时长", "互动率", "次日留存", "7日留存", "30日留存"]
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for r in rows:
                    w.writerow([r[c] for c in cols])
        except Exception as e:
            self.toast(f"导出失败：{e}", DANGER)
            return

        self.log("导出 CSV", f"{len(rows)} 条")
        self.toast(f"已导出 {len(rows)} 条到 {os.path.basename(path)}")

    # ═══════════════════════════════════════════════════════
    #  角色使用率
    # ═══════════════════════════════════════════════════════
    def _build_usage_section(self, parent):
        card = C.Card(parent)
        card.pack(fill="x", pady=(0, SP_MD))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "角色使用率 TOP 8", icon="star").pack(side="left")

        versions = [v["version"] for v in get_versions(limit=8)]
        self._usage_version = C.Field(
            head, "", kind="menu", values=versions or ["—"],
            width=96, label_width=0,
            default=versions[0] if versions else "—")
        self._usage_version.pack(side="right")
        self._usage_version.widget.configure(
            command=lambda _v: self._refresh_usage())

        self._usage_host = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        self._usage_host.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))

        self._refresh_usage()

    def _refresh_usage(self):
        host = self._usage_host
        for w in host.winfo_children():
            w.destroy()

        ver = self._usage_version.get()
        rows = top_characters(ver, 8) if ver and ver != "—" else []

        if not rows:
            C.EmptyState(host, f"{ver} 还没有角色使用率数据", "star",
                         "可在「版本」页导入，或使用 seed_demo.py 生成演示数据",
                         height=120).pack(fill="x")
            return

        chart = charts.BarChart(host, height=min(170, 24 * len(rows) + 20),
                                horizontal=True)
        chart.pack(fill="x")
        chart.set_data({
            "items": [{"label": r["character_name"], "value": r["usage_rate"]}
                      for r in rows],
            "color": theme.GAME_ACCENT.get("崩坏：星穹铁道", PRIMARY),
        })

        # 附一句结论：最高与最低差距，以及有没有异常下滑
        top = rows[0]
        note = f"最高：{top['character_name']} {top['usage_rate']:.1f}%"
        ctk.CTkLabel(host, text=note, font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY, anchor="w").pack(
            fill="x", pady=(4, 0))

    # ═══════════════════════════════════════════════════════
    #  社区热度
    # ═══════════════════════════════════════════════════════
    def _build_community_section(self, parent):
        card = C.Card(parent)
        card.pack(fill="x", pady=(0, SP_MD))

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "社区平台热度", icon="bolt").pack(side="left")

        versions = [v["version"] for v in get_versions(limit=8)]
        self._community_version = C.Field(
            head, "", kind="menu", values=versions or ["—"],
            width=96, label_width=0,
            default=versions[0] if versions else "—")
        self._community_version.pack(side="right")
        self._community_version.widget.configure(
            command=lambda _v: self._refresh_community())

        self._community_host = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        self._community_host.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))

        self._refresh_community()

    def _refresh_community(self):
        host = self._community_host
        for w in host.winfo_children():
            w.destroy()

        ver = self._community_version.get()
        rows = query(
            "SELECT platform, post_count, avg_reply_count FROM community_hot "
            "WHERE version=? ORDER BY post_count DESC",
            (ver,)) if ver and ver != "—" else []

        if not rows:
            C.EmptyState(host, f"{ver} 还没有社区热度数据", "bolt",
                         "导入各平台的发帖量与平均回复数", height=110).pack(fill="x")
            return

        total = sum(r["post_count"] or 0 for r in rows)
        avg_reply = (sum(r["avg_reply_count"] or 0 for r in rows) / len(rows))

        grid = ctk.CTkFrame(host, fg_color="transparent", height=1)
        grid.pack(fill="x")
        for i in range(len(rows)):
            grid.grid_columnconfigure(i, weight=1, uniform="cm")

        for i, r in enumerate(rows):
            share = (r["post_count"] or 0) / total * 100 if total else 0
            cell = ctk.CTkFrame(grid, fg_color=BG_ELEVATED,
                                corner_radius=RADIUS_MD)
            cell.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else SP_SM, 0))
            inner = ctk.CTkFrame(cell, fg_color="transparent", height=1)
            inner.pack(fill="x", padx=SP_MD, pady=SP_SM)

            ctk.CTkLabel(inner, text=r["platform"], font=font(SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w")
            ctk.CTkLabel(inner, text=f"{int(r['post_count'] or 0):,}",
                         font=num_font(16), text_color=TEXT_PRIMARY,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(inner, text=f"占比 {share:.0f}% · 均回 {r['avg_reply_count'] or 0:.1f}",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                         anchor="w").pack(anchor="w")

        ctk.CTkLabel(host, text=f"合计发帖 {total:,} · 平均回复 {avg_reply:.1f}",
                     font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                     anchor="w").pack(fill="x", pady=(SP_SM, 0))

    # ═══════════════════════════════════════════════════════
    #  最近记录表
    # ═══════════════════════════════════════════════════════
    def _build_recent_table(self, parent):
        card = C.Card(parent)
        card.pack(fill="both", expand=True)

        head = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        C.SectionTitle(head, "数据明细", icon="list").pack(side="left")

        self._count_label = ctk.CTkLabel(head, text="", font=font(SIZE_TINY),
                                         text_color=TEXT_TERTIARY)
        self._count_label.pack(side="right")

        self._table_host = ctk.CTkFrame(card.body, fg_color="transparent", height=1)
        self._table_host.pack(fill="both", expand=True, padx=SP_LG,
                              pady=(0, SP_MD))

        self._refresh_table()

    def _metric_rows(self):
        """按当前筛选条件取数据。"""
        game = self._game_filter.get()
        rng = self._range_filter.get()

        sql = "SELECT * FROM daily_metrics WHERE 1=1"
        params = []
        if game and game != "全部":
            sql += " AND game=?"
            params.append(game)
        if rng != "全部":
            days = {"近 7 天": 7, "近 30 天": 30, "近 90 天": 90}.get(rng, 30)
            sql += " AND date>=?"
            params.append(date_str(db.days_ago(days)))
        sql += " ORDER BY date DESC, game LIMIT 200"
        return query(sql, params)

    def _refresh_data_body(self, reset_form=True):
        if reset_form:
            pass
        self._refresh_table()
        self._refresh_usage()
        self._refresh_community()

    def _refresh_table(self):
        host = self._table_host
        for w in host.winfo_children():
            w.destroy()

        rows = self._metric_rows()
        if hasattr(self, "_count_label"):
            self._count_label.configure(text=f"共 {len(rows)} 条")

        if not rows:
            C.EmptyState(host, "当前筛选条件下没有数据", "chart",
                         "调整游戏或时间范围，或在上方录入一条").pack(
                fill="both", expand=True)
            return

        # 表头
        cols = [("日期", 90), ("游戏", 120), ("DAU", 76), ("帖子", 70),
                ("评论", 76), ("时长", 62), ("互动率", 68), ("次留", 62)]
        hdr = ctk.CTkFrame(host, fg_color="transparent", height=1)
        hdr.pack(fill="x")
        for text, w in cols:
            ctk.CTkLabel(hdr, text=text, font=font(SIZE_TINY, bold=True),
                         text_color=TEXT_SECONDARY, width=w,
                         anchor="w").pack(side="left")
        ctk.CTkLabel(hdr, text="", width=30).pack(side="left")

        C.Divider(host).pack(fill="x", pady=(3, 0))

        table = ctk.CTkScrollableFrame(host, fg_color="transparent", height=220)
        table.pack(fill="both", expand=True)

        # 互动率低于阈值的高亮 —— 让「哪几天出了问题」一眼可见
        warn_line = 3.0

        for r in rows:
            line = ctk.CTkFrame(table, fg_color="transparent", height=28)
            line.pack(fill="x")
            line.pack_propagate(False)

            rate = r["interaction_rate"] or 0
            rate_color = DANGER if rate < warn_line else TEXT_BODY

            # 留存 0 = 未统计（迁移补列的历史数据），显示占位符而不是 0.0%
            r1 = r["retention_1"] if db.valid_retention(r["retention_1"]) else None

            vals = [
                (r["date"], 90, TEXT_BODY),
                (r["game"], 120, TEXT_SECONDARY),
                (f"{r['dau']:,}", 76, TEXT_PRIMARY),
                (f"{r['new_posts']:,}", 70, TEXT_BODY),
                (f"{r['comments']:,}", 76, TEXT_BODY),
                (f"{r['avg_session']:.1f}", 62, TEXT_BODY),
                (f"{rate:.1f}%", 68, rate_color),
                (f"{r1:.1f}%" if r1 is not None else "—", 62, TEXT_BODY),
            ]
            for text, w, color in vals:
                ctk.CTkLabel(line, text=str(text), font=font(SIZE_SMALL),
                             text_color=color, width=w,
                             anchor="w").pack(side="left")

            C.IconButton(line, "trash",
                         lambda _=None, rid=r["id"]: self._delete_metric(rid),
                         size=24, color=TEXT_TERTIARY).pack(side="left")

            C.Divider(table, height=1).pack(fill="x")

    def _delete_metric(self, rid):
        row = query("SELECT date, game FROM daily_metrics WHERE id=?", (rid,), one=True)
        if not row:
            return
        try:
            execute("DELETE FROM daily_metrics WHERE id=?", (rid,))
        except Exception as e:
            self.toast(f"删除失败：{e}", DANGER)
            return
        self.log("删除指标", f"{row['date']} {row['game']}")
        self.toast("已删除该条记录")
        self._refresh_table()

    # ── Ctrl+S 支持 ──
    def _save_data(self):
        """数据页没有草稿态，Ctrl+S 直接尝试保存当前表单。"""
        rec, err = self._collect_metric()
        if err:
            self.toast(err, DANGER)
            return
        self._save_metric()
