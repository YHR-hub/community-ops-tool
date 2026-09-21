# -*- coding: utf-8 -*-
"""
pytest 适配层 —— 让既有测试脚本能在 pytest 下运行并统计覆盖率
==================================================

为什么用适配层而不是重写：
  smoke_test.py / flow_test.py 是自研的 check() 框架，能跑、跑得稳、
  输出格式是为「人看」设计的（分节 + PASS/FAIL 明细）。重写成 pytest 用例
  会把这些资产全部作废，风险远大于收益。

适配层的做法：
  把两个脚本当「一个整体用例」交给 pytest —— 脚本自己 exit code 非 0 即判失败，
  失败明细仍由脚本自身的中文输出给出（pytest -s 可见）。
  这样：CI 能拿到覆盖率与用例筛选，脚本的中文排错信息也一条不丢。

运行：
  pytest tests/ -s                 # 看详细输出
  pytest tests/ --cov=db --cov=agent --cov-report=term-missing
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module", autouse=True)
def _isolated_test_db():
    """
    v4.4：纯逻辑用例跑在独立测试库上，绝不碰用户真实数据。

    起因：用户把工具切到「真实模式」后，测试如果直接 import db，
    就会往真实库写演示数据——测试必须自带环境，不能依赖外部状态。
    """
    sys.path.insert(0, ROOT)
    import pathlib

    import db
    p = pathlib.Path(ROOT) / "data" / "test_logic.db"
    db.DB_PATH = p
    for suffix in ("", "-wal", "-shm"):
        f = pathlib.Path(str(p) + suffix)
        if f.exists():
            f.unlink()
    db.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db.init_db()
    import seed_demo
    seed_demo.seed(force=False)
    yield


def _run(script, *args):
    """在项目根下跑一个测试脚本，返回 (returncode, 输出)。"""
    proc = subprocess.run(
        [sys.executable, script, *args],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@pytest.mark.gui
def test_smoke_suite():
    """渲染冒烟 47 项：页面/弹窗/核心逻辑/布局不变量/早报智能体。"""
    code, out = _run("smoke_test.py")
    print(out)
    assert code == 0, "smoke_test 存在失败项，见上方明细"


@pytest.mark.gui
def test_flow_suite():
    """业务流程 34 项：录入/导入/切换/标记/报告/早报闭环（先重灌演示数据）。"""
    code, out = _run("flow_test.py", "--force")
    print(out)
    assert code == 0, "flow_test 存在失败项，见上方明细"


# ── 纯逻辑用例（不启动 GUI，CI 快速反馈靠它们）──

def test_anomaly_confirm_fields():
    """异动检测必须带齐确认字段，且分级自洽。"""
    sys.path.insert(0, ROOT)
    import db
    rows = db.anomaly_report()
    assert rows, "演示库应有异动可检"
    for r in rows:
        for k in ("wow_change", "confirmed", "streak", "special", "level"):
            assert k in r, f"缺少确认字段 {k}"
        assert r["level"] in ("danger", "warn", "watch")


def test_action_plan_mapping():
    """建议动作 → 待办映射规则（纯函数，不碰数据库）。"""
    sys.path.insert(0, ROOT)
    import agent
    plan = agent.action_plan([
        "排查近期内容话题热度与发帖质量",
        "预算使用率已达 94%，可能超支",
        "先清逾期任务，再排今日新工作",
    ])
    assert len(plan) == 3
    assert plan[0]["category"] == "内容运营" and plan[0]["target"] == "task"
    assert plan[1]["target"] == "risk"
    assert plan[2]["category"] == "任务推进"


def test_data_source_alias_mapping():
    """数据源适配：中文表头映射 + 数值解析，跨来源同一套口径。"""
    sys.path.insert(0, ROOT)
    import data_source as ds
    rows = [{
        "日期": "2026-09-20", "游戏": "崩坏：星穹铁道",
        "日活": "52,000", "次留": "45.2", "7留": "21.0",
    }]
    recs, errs = ds.normalize_rows(rows)
    assert not errs, errs
    assert recs[0]["game"] == "崩坏：星穹铁道"
    assert recs[0]["dau"] == 52000          # 千分位要吃掉
    assert recs[0]["retention_1"] == 45.2   # 「次留」≡ retention_1


def test_data_source_rejects_bad_rows():
    """坏行逐行报出行号与原因，且不拖垮其他行（部分成功）。"""
    sys.path.insert(0, ROOT)
    import data_source as ds
    rows = [
        {"date": "2026-09-20", "game": "星铁", "dau": "5000"},      # 正常
        {"date": "2026/09/20", "game": "星铁", "dau": "5000"},      # 日期格式错
        {"date": "2026-09-21", "game": "星铁", "dau": "abc"},       # 数值非法
        {"date": "2026-09-22", "game": "星铁", "次留": "120"},      # 留存越界
    ]
    recs, errs = ds.normalize_rows(rows)
    assert len(recs) == 1, "只有第一行合法"
    assert len(errs) == 3
    assert any("日期格式" in e[1] for e in errs)
    assert any("不是数字" in e[1] for e in errs)
    assert any("超出 0-100" in e[1] for e in errs)
    assert all(isinstance(e[0], int) for e in errs), "错误必须带行号"


def test_data_source_api_shape():
    """ApiSource 两种常见返回结构（数组 / {data:[...]}）都能取到行。"""
    sys.path.insert(0, ROOT)
    import data_source as ds
    # 不真发请求：验证接口行走同一套归一化（ApiSource 只负责取数）
    src = ds.ApiSource("http://example.invalid/api")
    assert src.name == "api" and src.timeout == 15
    recs, _ = ds.normalize_rows(
        [{"date": "2026-09-20", "game": "星铁", "dau": 100}])
    assert recs and recs[0]["dau"] == 100


def test_compose_attribution():
    """归因文案分派：留存下滑 × 互动率走低/平稳 给出不同归因。"""
    sys.path.insert(0, ROOT)
    import agent
    base = {"has_data": True, "game": "崩坏：星穹铁道", "version": "4.5",
            "day": 10, "ret_cur": 41.0, "alerts": [], "actions": [], "ups": []}
    a = agent.compose({**base, "ret_drop": -3.0, "rate_delta": -0.8})
    b = agent.compose({**base, "ret_drop": -3.0, "rate_delta": 0.1})
    assert a and b and a != b, "不同交叉结果应给出不同归因文案"
