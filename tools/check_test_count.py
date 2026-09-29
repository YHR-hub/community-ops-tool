# -*- coding: utf-8 -*-
"""
测试数防漂移守卫（v4.8 新增）
================================
背景：测试从 74 → 93 的过程中，多处文档没同步更新，出现三处不一致
（README 徽章写 93 / CI 注释写 40 items / test_ops docstring 写 47 项）。
根因是"测试数靠手写"。本脚本让数字变成**可自动校验**的：

  模式 A（默认，秒级，无需 GUI）——静态互检：
    提取三处文档中的数字（README 徽章 / ci.yml 注释 / tests/test_ops.py docstring）
    互相比对，不一致即退出码 1（供 CI lint job 拦截）

  模式 B（--run，稍慢）——实跑校验：
    实际运行 smoke_test.py 与 flow_test.py，解析「通过 N 项」输出，
    与 README 徽章核对（用于周期性验证"文档 = 真实"）

用法：
  python tools/check_test_count.py          # 静态互检（CI lint job 用）
  python tools/check_test_count.py --run    # 实跑校验（本地/发布前用）
"""
import io
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return io.open(ROOT / rel, encoding="utf-8").read()


def collect_declared():
    """收集各处文档声明的数字。

    口径约定：
      README 徽章      = 总数（smoke + flow）
      ci.yml 注释      = 分侧数（Run smoke tests (N items) / Run flow tests (M items)）
      test_ops.py      = 冒烟单侧数（应与 ci.yml 的 smoke 数一致）
    """
    found = {}

    readme = _read("README.md")
    m = re.search(r"tests-(\d+)%20passing", readme)
    if m:
        found["README 徽章(总数)"] = int(m.group(1))

    ci = _read(".github/workflows/ci.yml")
    m = re.search(r"Run smoke tests \((\d+) items", ci)
    if m:
        found["ci.yml smoke"] = int(m.group(1))
    m = re.search(r"Run flow tests \((\d+) items", ci)
    if m:
        found["ci.yml flow"] = int(m.group(1))

    m = re.search(r"(\d+)\s*项", _read("tests/test_ops.py"))
    if m:
        found["test_ops.py(冒烟)"] = int(m.group(1))

    return found


def static_check():
    found = collect_declared()
    print("静态互检（各处声明的测试数）：")
    for k, v in found.items():
        print(f"  {k}: {v}")

    problems = []
    total = found.get("README 徽章(总数)")
    smoke = found.get("ci.yml smoke")
    flow = found.get("ci.yml flow")
    to_smoke = found.get("test_ops.py(冒烟)")

    if total and smoke and flow and smoke + flow != total:
        problems.append(f"ci.yml 分侧数 {smoke}+{flow}={smoke + flow} ≠ README 总数 {total}")
    if to_smoke and smoke and to_smoke != smoke:
        problems.append(f"test_ops.py 写 {to_smoke}，与 ci.yml smoke 数 {smoke} 不一致")

    if problems:
        print("\nFAIL: 测试数漂移——")
        for p in problems:
            print("  ·", p)
        print("\n请同步以上文件中的数字（总数=冒烟+流程），再提交。")
        return 1
    print("\nOK: 各处口径一致（总数 = 冒烟 + 流程）")
    return 0


def run_check():
    """实跑两个测试脚本，解析『通过 N 项』，与 README 对照。"""
    py = sys.executable
    results = {}
    for name, rel in (("smoke", "smoke_test.py"), ("flow", "flow_test.py")):
        print(f"运行 {rel} ...")
        p = subprocess.run([py, rel], cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="ignore")
        out = (p.stdout or "") + (p.stderr or "")
        # smoke: 「通过 59 项，失败 0 项」；flow: 「通过 59 / 60」
        m = re.search(r"通过\s*(\d+)\s*项", out) or re.search(r"通过\s*(\d+)\s*/", out)
        if not m:
            print(f"FAIL: 无法从 {rel} 输出解析通过数")
            print(out[-800:])
            return 1
        results[name] = int(m.group(1))
        print(f"  {name}: {results[name]}")

    actual = results["smoke"] + results["flow"]
    readme = _read("README.md")
    declared = int(re.search(r"tests-(\d+)%20passing", readme).group(1))
    print(f"\n实际: smoke {results['smoke']} + flow {results['flow']} = {actual}")
    print(f"README: {declared}")
    if actual != declared:
        print(f"\nFAIL: 漂移！请把 README 徽章（及文档）更新为 {actual}")
        return 1
    print("\nOK: 文档与实跑一致")
    return 0


if __name__ == "__main__":
    if "--run" in sys.argv:
        sys.exit(run_check())
    sys.exit(static_check())
