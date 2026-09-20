"""
冒烟测试 —— 真正把应用跑起来，逐个页面渲染一遍
================================================

为什么必须做这个：
  语法正确不等于能渲染。CustomTkinter 的报错大多发生在构造阶段
  （未知参数、颜色非法、place 传宽高），只有真正把组件建出来才会暴露。
  这个脚本不进入 mainloop，而是构造 App → 逐页调用 _build_* → 强制
  update() 让布局跑完 → 检查是否有异常，最后销毁。

用法：python smoke_test.py
"""

import sys
import traceback

import customtkinter as ctk

ctk.set_appearance_mode("dark")

FAILS = []
PASSES = []


def check(name, fn):
    try:
        fn()
        PASSES.append(name)
        print(f"  [PASS] {name}")
    except Exception as e:
        FAILS.append((name, e))
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=6)


def main():
    import db
    db.init_db()
    # 老库可能带着重复行（旧版没有唯一约束），先清重再建唯一索引，
    # 否则 INSERT ... ON CONFLICT 会一直失败。
    removed, failed = db.ensure_unique_indexes()
    if removed:
        print(f"  (清重：{removed})")
    if failed:
        print(f"  (唯一索引失败：{failed})")

    # 确保有演示数据可渲染（否则空状态看不到真实布局）
    try:
        import seed_demo
        seed_demo.seed(force=False)
    except Exception as e:
        print(f"  (seed 跳过: {e})")

    import main as app_main
    from views import (OverviewMixin, DataMixin, VersionsMixin,
                       AnalysisMixin, ReportMixin)

    print("\n=== 1. 构造 App ===")
    app = None
    try:
        app = app_main.App()
        app.update()
        PASSES.append("App 构造 + 首屏")
        print("  [PASS] App 构造 + 首屏")
    except Exception as e:
        FAILS.append(("App 构造", e))
        print(f"  [FAIL] App 构造: {type(e).__name__}: {e}")
        traceback.print_exc(limit=8)
        return

    print("\n=== 2. 五个主页面渲染 ===")
    for key in ("overview", "data", "versions", "analysis", "report"):
        def go(k=key):
            app.show_view(k)
            app.update()
            app.update_idletasks()
        check(f"页面 {key}", go)

    print("\n=== 3. 版本页两个 Tab ===")
    app.show_view("versions")
    app.update()
    for tab in ("board", "timeline"):
        def go(t=tab):
            app._version_tab = t
            app.remount("versions")
            app.update()
        check(f"版本页 / {tab}", go)

    print("\n=== 4. 分析页四个 Tab ===")
    app.show_view("analysis")
    app.update()
    for tab in ("health", "ai", "compare", "retention"):
        def go(t=tab):
            app._analysis_tab = t
            app.remount("analysis")
            app.update()
        check(f"分析页 / {tab}", go)

    print("\n=== 5. 报告页三个 Tab ===")
    app.show_view("report")
    app.update()
    for tab in ("smart", "period", "history"):
        def go(t=tab):
            app._report_tab = t
            app.remount("report")
            app.update()
        check(f"报告页 / {tab}", go)

    print("\n=== 6. 弹窗类 ===")
    # 版本详情（内部含四个子 Tab，旧版正是在这里因 Canvas 未 import 而崩）
    def version_detail():
        v = db.latest_version()
        app._open_version_detail(v["id"])
        app.update()
        # 逐个切子 Tab
        for dlg in app.winfo_children():
            if isinstance(dlg, ctk.CTkToplevel):
                for child in dlg.winfo_children():
                    pass
        app.after(50, lambda: None)
    check("版本详情弹窗", version_detail)

    def new_version_dlg():
        app._open_new_version()
        app.update()
    check("新建版本弹窗", new_version_dlg)

    def add_risk_dlg():
        v = db.latest_version()
        app._add_risk(v["id"])
        app.update()
    check("添加风险弹窗", add_risk_dlg)

    def command_panel():
        app._open_command_panel()
        app.update()
    check("命令面板", command_panel)

    print("\n=== 7. 关闭所有子窗口 ===")
    for w in app.winfo_children():
        if isinstance(w, ctk.CTkToplevel):
            try:
                w.destroy()
            except Exception:
                pass
    app.update()

    print("\n=== 8. 关键交互逻辑（不依赖界面）===")
    check("健康度评分", lambda: app._health_scores(db.latest_version()))
    check("报告上下文", lambda: app._report_context("崩坏：星穹铁道"))
    check("核心发现推导",
          lambda: app._derive_findings(app._report_context("崩坏：星穹铁道")))
    check("下一步计划推导",
          lambda: app._derive_plans(app._report_context("崩坏：星穹铁道")))
    check("健康度 prompt",
          lambda: app._build_health_prompt(db.latest_version()))
    check("本地深化报告",
          lambda: app._local_deepen("占位草稿"))

    def fmt_metric():
        assert app._fmt_metric(0) == "—"
        assert "万" in app._fmt_metric(52000)
    check("指标格式化", fmt_metric)

    # ── v4.1 留存数据层 ──
    def retention_valid_filter():
        # 0 = 未统计（迁移补列的老数据），必须被序列过滤，
        # 否则曲线在开头砸到 0 再跳回 45，看起来像数据 bug
        rows = db.retention_series("2000-01-01", "2099-12-31", "崩坏：星穹铁道")
        assert rows, "演示数据应含留存行"
        assert all(
            (r["retention_1"] or 0) > 0 or (r["retention_7"] or 0) > 0
            for r in rows), "序列里混入了 retention 全 0 的行"
    check("留存序列过滤未统计行", retention_valid_filter)

    def retention_stats_mean():
        s = db.retention_stats("2000-01-01", "2099-12-31", "崩坏：星穹铁道")
        assert s["r1"] is not None, "演示数据应能算出次留均值"
        assert 30 <= s["r1"] <= 50, f"演示次留均值异常: {s['r1']}"
        assert s["r7"] and s["r30"], "7留/30留均值缺失"
        # 二游衰减规律：次留 < 7留的 2.4 倍（粘性系数 ≥0.42），30留 < 7留
        assert s["r7"] < s["r1"] < 2.4 * s["r7"]
        assert s["r30"] < s["r7"]
    check("留存均值与衰减规律", retention_stats_mean)

    def retention_valid_bounds():
        assert not db.valid_retention(0)      # 0 = 未统计
        assert not db.valid_retention(None)
        assert not db.valid_retention(128)    # >100 不可能
        assert db.valid_retention(45.2)
    check("留存有效值边界", retention_valid_bounds)

    def anomaly_structure():
        # 用确定性数据测异动检测，不依赖演示数据的随机性：
        # 8 天窗口，前 7 天 DAU=50000 / 互动率 4.0，最后一天 DAU 腰斩、互动率 -1pp。
        db.execute("DELETE FROM daily_metrics WHERE game=?", ("测试游戏",))
        from datetime import date as _date, timedelta as _td
        anchor = _date.today()
        for k in range(8, 0, -1):
            d = str(anchor - _td(days=k))
            last_day = (k == 1)
            db.execute(
                "INSERT INTO daily_metrics (date,game,dau,new_users,new_posts,"
                "comments,avg_session,interaction_rate) VALUES (?,?,?,?,?,?,?,?)",
                (d, "测试游戏", 30000 if last_day else 50000, 1000, 800,
                 4000, 20.0, 3.0 if last_day else 4.0))
        try:
            items = db.anomaly_report(game="测试游戏")
            dau = next((a for a in items if a["metric"] == "DAU"), None)
            assert dau and dau["down"], f"DAU -40% 应被抓到: {items}"
            rate = next((a for a in items if a["metric"] == "互动率"), None)
            assert rate and rate["down"] and "pp" in rate["change"], \
                f"互动率 -1.0pp 应被抓到: {items}"
            # 单游戏过滤：note 不应有拆分
            assert "拆分" not in (dau["note"] or "")
        finally:
            db.execute("DELETE FROM daily_metrics WHERE game=?", ("测试游戏",))
    check("异动检测与拆分逻辑", anomaly_structure)

    def anomaly_multi_game_split():
        # 两游戏同锚点：A 平稳、B 腰斩 → 拆分应只点名 B
        from datetime import date as _date, timedelta as _td
        anchor = _date.today()
        for gm, last_dau in (("测试A", 50000), ("测试B", 25000)):
            db.execute("DELETE FROM daily_metrics WHERE game=?", (gm,))
            for k in range(8, 0, -1):
                d = str(anchor - _td(days=k))
                last_day = (k == 1)
                db.execute(
                    "INSERT INTO daily_metrics (date,game,dau) VALUES (?,?,?)",
                    (d, gm, last_dau if last_day else 50000))
        try:
            items = db.anomaly_report()
            dau = next(a for a in items if a["metric"] == "DAU")
            assert "测试B" in dau["note"], f"拆分应点名测试B: {dau['note']}"
            assert "测试A" not in dau["note"], f"平稳的A不应被点名: {dau['note']}"
        finally:
            for gm in ("测试A", "测试B"):
                db.execute("DELETE FROM daily_metrics WHERE game=?", (gm,))
    check("异动按游戏拆分定位", anomaly_multi_game_split)

    def anomaly_empty_db():
        # 空库 / 单日库不报错、不产异动（基准不足）
        assert db.anomaly_report(game="不存在游戏") == []
    check("异动检测空库安全", anomaly_empty_db)

    # ── v4.2 早报智能体 ──
    def agent_briefing_runs():
        # 演示库上全链路生成：结构完整、轨迹可解释、不依赖 AI Key
        import agent as ops_agent
        b = ops_agent.generate(use_ai=False)
        assert b["ok"] and b["headline"] and b["narrative"]
        assert isinstance(b["alerts"], list) and isinstance(b["actions"], list)
        assert b["trace"], "决策轨迹不应为空"
    check("早报智能体全链路", agent_briefing_runs)

    def agent_anomaly_alert():
        # 确定性造数：最后一天 DAU 腰斩 → 早报必须捕获并给出建议动作
        import agent as ops_agent
        from datetime import date as _date, timedelta as _td
        db.execute("DELETE FROM daily_metrics WHERE game=?", ("测试游戏",))
        anchor = _date.today()
        for k in range(8, 0, -1):
            d = str(anchor - _td(days=k))
            last_day = (k == 1)
            db.execute(
                "INSERT INTO daily_metrics (date,game,dau,new_users,new_posts,"
                "comments,avg_session,interaction_rate) VALUES (?,?,?,?,?,?,?,?)",
                (d, "测试游戏", 30000 if last_day else 50000, 1000, 800,
                 4000, 20.0, 3.0 if last_day else 4.0))
        try:
            b = ops_agent.generate(use_ai=False)
            assert any("DAU" in a["text"] for a in b["alerts"]), \
                f"早报应捕获 DAU 异动: {b['alerts']}"
            assert b["actions"], "异动应伴随建议动作"
        finally:
            db.execute("DELETE FROM daily_metrics WHERE game=?", ("测试游戏",))
    check("早报捕获异动并给出动作", agent_anomaly_alert)

    def agent_compose_attribution():
        # 纯函数归因分派：留存下滑 × 互动率走低 → 内容；留存下滑 × 互动率平稳 → 渠道
        import agent as ops_agent
        base = {"has_data": True, "game": "崩坏：星穹铁道", "version": "3.8",
                "day": 12, "ret_cur": 43.2, "ret_drop": -1.8,
                "alerts": [{"level": "danger", "text": "次日留存环比 -1.8pp"}],
                "actions": ["核对渠道投放"], "ups": []}
        n1 = ops_agent.compose({**base, "rate_delta": -0.6})
        assert "内容吸引力" in n1, n1
        n2 = ops_agent.compose({**base, "rate_delta": 0.2})
        assert "渠道质量" in n2, n2
        n3 = ops_agent.compose({"has_data": False})
        assert "暂无运营数据" in n3
    check("早报归因文案分派", agent_compose_attribution)

    print("\n=== 9. AI 离线兜底（不配 Key）===")
    def offline_ai():
        app._analysis_tab = "ai"
        app.remount("analysis")
        app.update()
        app._generate_ai(scene="版本健康度分析")
        app.update()
        for _ in range(20):
            app.update()
            import time
            time.sleep(0.05)
    check("AI 离线兜底", offline_ai)

    print("\n=== 10. 布局不变量（防止透明帧 250px 幽灵高度回归）===")
    # 背景：CustomTkinter 的 CTkFrame 在不传 height 时保留 200x200 默认尺寸，
    # 渲染出来是 250px 高。空的透明帧不会收缩，会把整张卡片撑高一倍 ——
    # 表现为「卡片里一大片空白」「左侧色条拖成一条长竖线」。
    # 这里用断言把这个坑钉住：任何页面里出现异常高的空帧都视为失败。
    app.show_view("overview")
    app.update()
    app.update_idletasks()

    def no_phantom_frames():
        """
        找「没有子控件、却很高」的透明帧。
        CTkFrame 的默认尺寸是 250px，一旦某个空帧没给 height 就会留下
        这个高度的空白，把卡片撑高。
        注意：Row.text 这类「有意为空、由父级撑高」的包装帧要排除，
        它的高度是被父级拉伸的结果，不是幽灵高度。
        """
        import components as C
        exempt = (C.Row,)

        def walk(w, path="root"):
            for c in w.winfo_children():
                name = c.__class__.__name__
                try:
                    h = c.winfo_height()
                    has_kids = bool(c.winfo_children())
                except Exception:
                    continue
                # 空帧（没有子控件）却接近 250px 默认高度 → 幽灵高度
                if (name in ("CTkFrame", "Card") and not has_kids
                        and 200 < h <= 300
                        and not isinstance(c.master, exempt)):
                    raise AssertionError(
                        f"发现空的透明帧却有 {h}px 高（疑似 250px 默认尺寸）："
                        f"{path}/{name}")
                walk(c, f"{path}/{name}")
        walk(app)
    check("无幽灵空帧（全局）", no_phantom_frames)

    def card_heights_sane():
        """
        卡片高度应当贴合内容。

        阈值取「宽度的 0.9 倍」而不是固定像素：
        窗口默认尺寸下图卡只有 ~511px 宽，风险标题（wraplength=250）
        会折行，卡片自然长到 ~382px —— 这是正常的内容驱动高度。
        真正要防的是「空帧幽灵高度」：那种情况下卡片高度与内容无关，
        会顶到 600px 以上，远超宽度。
        """
        def measure(w, out):
            if w.__class__.__name__ == "Card":
                out.append((w.winfo_height(), w.winfo_width()))
            for c in w.winfo_children():
                measure(c, out)
        out = []
        measure(app, out)
        assert out, "一个 Card 都没渲染出来"
        # 阈值 1.0（h 超过 wd 才算异常）：
        # v3.1 用 0.9，v4.1 风险预警卡加入实时异动条目后内容高度自然长到
        # ~467px（宽 511px），卡在 0.9 边界误报。幽灵高度的真实症状是
        # 空帧顶到 600px 级、明显超过宽度 —— 1.0 更贴合这个语义。
        bad = [(h, wd) for h, wd in out if h > wd and wd > 300]
        assert not bad, f"有卡片高度远超其宽度（疑似空帧幽灵高度）：{bad}"
    check("卡片高度贴合内容", card_heights_sane)

    def row_heights_sane():
        """列表行的行高应当由内容决定，不能出现 250px 这种症状值。"""
        import components as C
        rows = []
        def walk(w):
            if isinstance(w, C.Row):
                rows.append(w.winfo_height())
            for c in w.winfo_children():
                walk(c)
        walk(app)
        bad = [h for h in rows if h > 120]
        assert not bad, f"有列表行异常高：{bad}"
    check("列表行高贴合内容", row_heights_sane)

    print("\n=== 11. 销毁 ===")
    try:
        app.destroy()
        print("  [PASS] 正常退出")
        PASSES.append("正常退出")
    except Exception as e:
        print(f"  [FAIL] 退出: {e}")
        FAILS.append(("退出", e))

    print("\n" + "=" * 56)
    print(f"通过 {len(PASSES)} 项，失败 {len(FAILS)} 项")
    if FAILS:
        print("\n失败明细：")
        for name, e in FAILS:
            print(f"  · {name}: {type(e).__name__}: {e}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
