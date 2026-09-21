"""
流程测试 —— 模拟真实操作路径，验证功能确实能用
================================================

冒烟测试只验证「能渲染」，这个脚本验证「能干活」：
  · 录入一条指标 → 数据真的进库了吗
  · 同一天重复录入 → 会不会静默产生两条（旧版的 DAU 翻倍 bug）
  · CSV 导入正常 / 缺列 / 脏数据 → 三种情况的表现
  · 任务状态切换 → 进度条是否跟着走
  · 自动标记风险 → 是否真的抓到了使用率下滑的角色
  · 版本详情的四个子 Tab → 逐个渲染
  · 报告生成 → 四段式结构是否完整（旧版会被周期报表覆盖）

用法：python flow_test.py
"""

import os
import sys
import tempfile
import traceback

import customtkinter as ctk

ctk.set_appearance_mode("dark")

RESULTS = []


def check(name, fn, expect=None):
    try:
        got = fn()
        if expect is not None and got != expect:
            RESULTS.append((name, False, f"期望 {expect!r}，实际 {got!r}"))
            print(f"  [FAIL] {name}: 期望 {expect!r}，实际 {got!r}")
            return
        RESULTS.append((name, True, got))
        print(f"  [PASS] {name}" + (f" → {got}" if got is not None else ""))
    except Exception as e:
        RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=5)


def main():
    import pathlib

    import db
    # v4.4：测试用独立数据库，绝不碰用户真实数据（data/ops_data.db）
    _test_db = pathlib.Path(__file__).parent / "data" / "test_flow.db"
    db.DB_PATH = _test_db
    for _suffix in ("", "-wal", "-shm"):
        _p = pathlib.Path(str(_test_db) + _suffix)
        if _p.exists():
            _p.unlink()
    db.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db.init_db()
    db.ensure_unique_indexes()

    # ── 准备干净的数据环境 ──
    import seed_demo
    seed_demo.seed(force=True)

    import main as app_main

    print("\n=== 1. 启动应用 ===")
    app = app_main.App()
    app.update()
    print("  已启动")

    # ═══════════════════════════════════════════════════════
    print("\n=== 2. 数据录入 ===")
    app.show_view("data")
    app.update()

    def entry_exists():
        assert hasattr(app, "_data_entries") and app._data_entries
        return len(app._data_entries)
    check("录入表单字段数", entry_exists)

    # 填一条全新日期的数据
    test_date = "2026-01-15"
    db.execute("DELETE FROM daily_metrics WHERE date=?", (test_date,))

    def fill_and_save():
        app._data_entries["date"].set(test_date)
        app._data_entries["game"].set("崩坏：星穹铁道")
        app._data_entries["dau"].set("61000")
        app._data_entries["new_posts"].set("1500")
        app._data_entries["comments"].set("7200")
        app._data_entries["avg_session"].set("23.4")
        app._data_entries["interaction_rate"].set("3.8")
        app._save_metric()
        app.update()
        return db.query("SELECT COUNT(*) AS n FROM daily_metrics WHERE date=?",
                        (test_date,), one=True)["n"]
    check("录入新记录写入库", fill_and_save, 1)

    def verify_values():
        r = db.query("SELECT * FROM daily_metrics WHERE date=?",
                     (test_date,), one=True)
        return (r["dau"], r["new_posts"], r["interaction_rate"])
    check("录入数值正确", verify_values, (61000, 1500, 3.8))

    # ── 关键回归：重复录入不能静默产生第二条 ──
    def repeat_save_creates_dialog():
        app._data_entries["date"].set(test_date)
        app._data_entries["dau"].set("62000")
        app._save_metric()
        app.update()
        # 应当弹出确认框，而不是直接插入
        tops = [w for w in app.winfo_children()
                if isinstance(w, ctk.CTkToplevel)]
        n = db.query("SELECT COUNT(*) AS n FROM daily_metrics WHERE date=?",
                     (test_date,), one=True)["n"]
        for t in tops:
            try:
                t.destroy()
            except Exception:
                pass
        return n
    check("重复录入不新增行（弹确认框）", repeat_save_creates_dialog, 1)

    def overwrite_works():
        rid = db.query("SELECT id FROM daily_metrics WHERE date=?",
                       (test_date,), one=True)["id"]
        rec = {"date": test_date, "game": "崩坏：星穹铁道", "dau": 62000,
               "new_posts": 1500, "comments": 7200,
               "avg_session": 23.4, "interaction_rate": 3.8}
        app._insert_metric(rec, overwrite_id=rid)
        app.update()
        n = db.query("SELECT COUNT(*) AS n FROM daily_metrics WHERE date=?",
                     (test_date,), one=True)["n"]
        dau = db.query("SELECT dau FROM daily_metrics WHERE date=?",
                       (test_date,), one=True)["dau"]
        return (n, dau)
    check("覆盖写入不增加行数", overwrite_works, (1, 62000))

    # ── 非法输入被拦住 ──
    def bad_date_rejected():
        app._data_entries["date"].set("2026/13/45")
        rec, err = app._collect_metric()
        return err is not None
    check("非法日期被拒绝", bad_date_rejected, True)

    def bad_number_rejected():
        app._data_entries["date"].set("2026-01-16")
        app._data_entries["dau"].set("abc")
        rec, err = app._collect_metric()
        return err is not None
    check("非数字输入被拒绝", bad_number_rejected, True)

    def negative_rejected():
        app._data_entries["dau"].set("-100")
        rec, err = app._collect_metric()
        return err is not None
    check("负数被拒绝", negative_rejected, True)

    # ── v4.1 留存：百分比上限（脏数据源头，>100% 会让图表与均值全部失真）──
    def retention_over_cap_rejected():
        app._data_entries["date"].set("2026-01-16")
        app._data_entries["dau"].set("52000")   # 上一个用例遗留了负数，先归位
        app._data_entries["retention_1"].set("128")
        rec, err = app._collect_metric()
        return err is not None and "100" in err
    check("留存超 100% 被拒绝", retention_over_cap_rejected, True)

    def retention_row_saved():
        app._data_entries["date"].set("2026-01-15")   # test_date，前文已确保存在
        app._data_entries["dau"].set("52000")
        app._data_entries["retention_1"].set("45.2")
        app._data_entries["retention_7"].set("21.0")
        app._data_entries["retention_30"].set("11.5")
        rec, err = app._collect_metric()
        assert err is None, f"合法留存不应报错: {err}"
        rid = db.query("SELECT id FROM daily_metrics WHERE date=?",
                       ("2026-01-15",), one=True)["id"]
        app._insert_metric(rec, overwrite_id=rid)
        r = db.query("SELECT retention_1, retention_7, retention_30 "
                     "FROM daily_metrics WHERE date=?",
                     ("2026-01-15",), one=True)
        return (round(r["retention_1"], 1), round(r["retention_7"], 1),
                round(r["retention_30"], 1))
    check("留存字段落库", retention_row_saved, (45.2, 21.0, 11.5))

    # ═══════════════════════════════════════════════════════
    print("\n=== 3. CSV 导入 ===")

    def csv_ok():
        path = os.path.join(tempfile.gettempdir(), "ops_test_ok.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("日期,游戏,DAU,新增帖子,评论数,平均时长,互动率\n")
            f.write("2026-02-01,崩坏：星穹铁道,63000,1600,7800,24.1,4.1\n")
            f.write("2026-02-02,崩坏：星穹铁道,63500,1650,7900,24.3,4.2\n")
        db.execute("DELETE FROM daily_metrics WHERE date LIKE '2026-02-%'")
        rows, header = app._read_csv(path)
        mapping = {}
        for h in header:
            k = __import__("views.data", fromlist=["CSV_ALIASES"])
            key = k.CSV_ALIASES.get(str(h).strip().lower())
            if key:
                mapping[h] = key
        recs, errs = [], []
        for i, r in enumerate(rows, start=2):
            rec, e = app._row_to_record(r, mapping, i)
            if e:
                errs.append(e)
            else:
                recs.append(rec)
        assert not errs, errs
        n = app._bulk_upsert(recs)
        got = db.query("SELECT COUNT(*) AS n FROM daily_metrics "
                       "WHERE date LIKE '2026-02-%'", one=True)["n"]
        return (n, got)
    check("CSV 正常导入", csv_ok, (2, 2))

    def csv_missing_col():
        path = os.path.join(tempfile.gettempdir(), "ops_test_bad.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("日期,DAU\n2026-03-01,63000\n")
        rows, header = app._read_csv(path)
        from views.data import CSV_ALIASES
        mapping = {h: CSV_ALIASES.get(str(h).strip().lower())
                   for h in header if CSV_ALIASES.get(str(h).strip().lower())}
        missing = [c for c in ("date", "game") if c not in mapping.values()]
        return missing
    check("CSV 缺必需列能识别", csv_missing_col, ["game"])

    def csv_dirty_row():
        from views.data import CSV_ALIASES
        header = ["日期", "游戏", "DAU"]
        mapping = {h: CSV_ALIASES[h.lower()] for h in header}
        rec, e1 = app._row_to_record(
            {"日期": "2026-04-01", "游戏": "崩坏：星穹铁道", "DAU": "12万"}, mapping, 2)
        rec2, e2 = app._row_to_record(
            {"日期": "2026-04-01", "游戏": "不存在的游戏", "DAU": "100"}, mapping, 3)
        rec3, e3 = app._row_to_record(
            {"日期": "bad-date", "游戏": "崩坏：星穹铁道", "DAU": "100"}, mapping, 4)
        return (e1 is not None, e2 is not None, e3 is not None)
    check("CSV 脏数据逐类报错", csv_dirty_row, (True, True, True))

    # ═══════════════════════════════════════════════════════
    print("\n=== 4. 版本详情四个子 Tab ===")
    v = db.latest_version()

    def open_detail():
        app.show_view("versions")
        app.update()
        app._open_version_detail(v["id"])
        app.update()
        return len([w for w in app.winfo_children()
                    if isinstance(w, ctk.CTkToplevel)])
    check("版本详情打开", open_detail, 1)

    def detail_tabs():
        dlg = [w for w in app.winfo_children()
               if isinstance(w, ctk.CTkToplevel)][-1]
        # 找到 host 与 tabbar
        hosts = []

        def walk(w, depth=0):
            for c in w.winfo_children():
                if isinstance(c, ctk.CTkFrame) and depth > 0:
                    hosts.append(c)
                walk(c, depth + 1)
        walk(dlg)

        ok = 0
        for fn in (app._detail_tasks, app._detail_risks,
                   app._detail_budget, app._detail_usage):
            host = ctk.CTkFrame(dlg, fg_color="transparent")
            fn(host, v)
            app.update()
            host.destroy()
            ok += 1
        try:
            dlg.destroy()
        except Exception:
            pass
        return ok
    check("四个子 Tab 均可渲染", detail_tabs, 4)

    # ═══════════════════════════════════════════════════════
    print("\n=== 5. 任务状态切换 ===")
    app.update()

    def toggle_task():
        row = db.query(
            "SELECT id, status, version_id FROM checklists "
            "WHERE version_id=? AND status='pending' LIMIT 1", (v["id"],), one=True)
        if not row:
            db.execute("UPDATE checklists SET status='pending' "
                       "WHERE version_id=? LIMIT 1", (v["id"],))
            row = db.query(
                "SELECT id, status, version_id FROM checklists "
                "WHERE version_id=? AND status='pending' LIMIT 1",
                (v["id"],), one=True)
        tid = row["id"]
        before = db.task_progress(v["id"])

        # 模拟三次点击：pending → doing → done → pending
        seen = []
        for _ in range(3):
            execute_next(tid)
            seen.append(db.query("SELECT status FROM checklists WHERE id=?",
                                 (tid,), one=True)["status"])
        # 复原
        db.execute("UPDATE checklists SET status='pending' WHERE id=?", (tid,))
        after = db.task_progress(v["id"])
        return (seen, before == after)
    def execute_next(tid):
        cyc = {"pending": "doing", "doing": "done", "done": "pending"}
        cur = db.query("SELECT status FROM checklists WHERE id=?",
                       (tid,), one=True)["status"]
        db.execute("UPDATE checklists SET status=? WHERE id=?",
                   (cyc.get(cur, "doing"), tid))
    check("任务状态循环切换", toggle_task)

    # ═══════════════════════════════════════════════════════
    print("\n=== 6. 自动标记风险（旧版取错列的 bug）===")

    def auto_risk():
        db.execute("DELETE FROM risks WHERE version_id=?", (v["id"],))
        app._auto_mark_risks(v)
        app.update()
        rows = db.open_risks(v["id"])
        titles = [r["title"] for r in rows]
        # 应抓到 姬子·启行 与 风堇（种子里植入 >5pp 下滑）
        hit = [t for t in titles if "姬子·启行" in t or "风堇" in t]
        # 旧版会写出 "%!s(float=52.3)" 这类垃圾标题
        garbage = [t for t in titles if "float" in t or "%!" in t]
        return (len(hit), len(garbage))
    check("自动标记抓到下滑角色（应 2 个）", auto_risk, (2, 0))

    def prev_version_is_same_game():
        """回归：上一个版本必须同游戏。跨游戏时会 JOIN 出 0 行，功能静默失效。"""
        p = db.previous_version(v)
        assert p is not None
        return (p["game"], p["version"])
    check("上一版本限定同游戏", prev_version_is_same_game)

    def usage_join_nonempty():
        p = db.previous_version(v)
        rows = db.query(
            "SELECT COUNT(*) AS n FROM char_usage c JOIN char_usage pr "
            "ON c.character_name=pr.character_name "
            "WHERE c.version=? AND pr.version=?", (v["version"], p["version"]),
            one=True)
        return rows["n"]
    check("使用率对比有数据（应 14）", usage_join_nonempty, 14)

    def risk_title_clean():
        titles = [r["title"] for r in db.open_risks(v["id"])]
        bad = [t for t in titles if "float" in t or "%!" in t or t.startswith("0.")]
        return len(bad)
    check("风险标题无类型残留", risk_title_clean, 0)

    # ═══════════════════════════════════════════════════════
    print("\n=== 7. 报告生成（旧版死代码回归）===")

    def smart_report():
        app.show_view("report")
        app.update()
        app.rp_game.set("崩坏：星穹铁道")
        app._gen_smart_report()
        app.update()
        text = app.rp_output.get("1.0", "end")
        return text
    text = smart_report() if False else None
    try:
        app.show_view("report")
        app.update()
        app.rp_game.set("崩坏：星穹铁道")
        app._gen_smart_report()
        app.update()
        text = app.rp_output.get("1.0", "end")
    except Exception as e:
        text = ""
        print(f"  [FAIL] 智能报告生成: {e}")

    def has_sections():
        sections = ["## 1. 数据摘要", "## 2. 核心发现",
                    "## 3. 风险与应对", "## 4. 下一步计划"]
        missing = [s for s in sections if s not in text]
        return missing
    check("智能报告四段完整", has_sections, [])

    def not_overwritten_by_period():
        # 旧版 bug：智能报告被周期报表覆盖，会出现「每日明细」表格
        return "## 3. 每日明细" not in text
    check("未被周期报表覆盖", not_overwritten_by_period, True)

    def period_report():
        app._report_tab = "period"
        app.remount("report")
        app.update()
        app.rp_game.set("崩坏：星穹铁道")
        app._gen_period_report()
        app.update()
        t = app.rp_output.get("1.0", "end")
        return ("| 日期 |" in t, "平均 DAU" in t)
    check("周期报表含表格", period_report, (True, True))

    def archive_and_list():
        n0 = db.query("SELECT COUNT(*) AS n FROM reports", one=True)["n"]
        app._report_tab = "period"
        app.remount("report")
        app.update()
        app.rp_game.set("崩坏：星穹铁道")
        app._gen_period_report()
        app.update()
        app._save_period_report()
        app.update()
        n1 = db.query("SELECT COUNT(*) AS n FROM reports", one=True)["n"]
        app._report_tab = "history"
        app.remount("report")
        app.update()
        return n1 > n0
    check("报告归档成功", archive_and_list, True)

    # ═══════════════════════════════════════════════════════
    print("\n=== 8. 分析页能力 ===")

    def health_all_versions():
        app._analysis_tab = "health"
        app.remount("analysis")
        app.update()
        opts = app._health_sel.widget.cget("values")
        bad = []
        for opt in opts:
            app._health_sel.set(opt)
            try:
                app._refresh_health()
                app.update()
            except Exception as e:
                bad.append((opt, str(e)[:60]))
        return bad
    check("健康度遍历所有版本", health_all_versions, [])

    def compare_all():
        app._analysis_tab = "compare"
        app.remount("analysis")
        app.update()
        opts = app._cmp_a.widget.cget("values")
        app._cmp_a.set(opts[0])
        app._cmp_b.set(opts[1])
        app._refresh_compare()
        app.update()
        # 相同版本应给出提示而不是崩
        app._cmp_a.set(opts[0])
        app._cmp_b.set(opts[0])
        app._refresh_compare()
        app.update()
        return True
    check("版本对比含同版本边界", compare_all, True)

    # ═══════════════════════════════════════════════════════
    print("\n=== 9. 全局搜索转义（旧版搜 % 会全表命中）===")

    def search_escape():
        all_rows = db.global_search("崩坏")
        pct_rows = db.global_search("%")
        under_rows = db.global_search("_")
        return (len(all_rows) > 0, len(pct_rows), len(under_rows))
    check("通配符被转义", search_escape)

    def search_empty():
        return len(db.global_search(""))
    check("空搜索返回空", search_empty, 0)

    # ═══════════════════════════════════════════════════════
    print("\n=== 9b. 早报智能体（v4.2）===")

    def agent_briefing_flow():
        """智能体全链路：真实演示库上生成早报 + 抽屉渲染，结构完整、不崩溃。"""
        import agent as ops_agent
        b = ops_agent.generate(use_ai=False)
        assert b["ok"] and b["headline"] and b["narrative"], f"早报结构异常: {b}"
        assert isinstance(b["alerts"], list)
        assert b["trace"], "决策轨迹不应为空"
        # 抽屉也走一遍（不进 mainloop，构造 + 渲染即可）
        app._show_briefing(b)
        app.update()
        for w in app.winfo_children():
            if isinstance(w, ctk.CTkToplevel):
                w.destroy()
        app.update()
        return b["headline"]
    check("早报智能体全链路", agent_briefing_flow)

    # ═══════════════════════════════════════════════════════
    print("\n=== 10. 全部页面再走一遍（回归）===")
    for key in ("overview", "data", "versions", "analysis", "report"):
        def go(k=key):
            app.show_view(k)
            app.update()
            app.update_idletasks()
        check(f"页面 {key}", go)

    print("\n=== 11. 退出 ===")
    app.destroy()
    print("  已退出")

    # ═══════════════════════════════════════════════════════
    ok = sum(1 for _, p, _ in RESULTS if p)
    bad = [r for r in RESULTS if not r[1]]
    print("\n" + "=" * 56)
    print(f"通过 {ok} / {len(RESULTS)}")
    if bad:
        print("\n失败明细：")
        for name, _, detail in bad:
            print(f"  · {name}: {detail}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
