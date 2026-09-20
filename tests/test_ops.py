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


def test_compose_attribution():
    """归因文案分派：留存下滑 × 互动率走低/平稳 给出不同归因。"""
    sys.path.insert(0, ROOT)
    import agent
    base = {"has_data": True, "game": "崩坏：星穹铁道", "version": "4.5",
            "day": 10, "ret_cur": 41.0, "alerts": [], "actions": [], "ups": []}
    a = agent.compose({**base, "ret_drop": -3.0, "rate_delta": -0.8})
    b = agent.compose({**base, "ret_drop": -3.0, "rate_delta": 0.1})
    assert a and b and a != b, "不同交叉结果应给出不同归因文案"
