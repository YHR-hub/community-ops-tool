# -*- coding: utf-8 -*-
"""
版本号防漂移守卫（v4.8 新增）
================================
背景：v4.8 发版时 main.py 的 APP_VERSION 漏改（仍写 "4.7"），
      于是代码是 v4.8、标题栏/底栏/启动日志却都显示 v4.7 ——
      CI 一路绿灯，直到人肉点开 exe 才看见"版本对不上"。
      这和"测试数漂移"是同一类毛病：关键数字靠手写、没人比对。

做法：当前版本只留一个真源 —— main.py 的 APP_VERSION，
      其余位置一律与它比对：

        真源   main.py            APP_VERSION = "4.8"
        文档   README.md          一级标题 …… v4.8
        发布   发布 tag / 期望版本  python tools/check_version.py v4.8

用法：
  python tools/check_version.py          # 静态互检（CI lint job 用）
  python tools/check_version.py v4.8     # 额外比对 tag（release job 用）
"""
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return io.open(ROOT / rel, encoding="utf-8").read()


def source_version():
    """真源：main.py 里的 APP_VERSION。"""
    m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', _read("main.py"), re.M)
    return m.group(1).strip() if m else None


def readme_version():
    """README 一级标题里的 vX.Y（取第一行非空内容）。"""
    for line in _read("README.md").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^#\s+.*?\bv(\d+(?:\.\d+)*)\s*$", line)
        return m.group(1) if m else None
    return None


def main():
    want = sys.argv[1].strip().lstrip("vV") if len(sys.argv) > 1 else None
    src = source_version()
    doc = readme_version()

    print("版本号互检：")
    print(f"  main.py APP_VERSION : {src}")
    print(f"  README 一级标题     : {doc}")
    if want:
        print(f"  期望版本（发布 tag）: {want}")

    problems = []
    if not src:
        problems.append("main.py 里找不到 APP_VERSION")
    if not doc:
        problems.append("README.md 一级标题里找不到 vX.Y")
    if src and doc and src != doc:
        problems.append(f"main.py 写 {src}，README 标题写 {doc}")
    if want and src and src.lstrip("vV") != want:
        problems.append(f"main.py 写 {src}，与本次发布 {want} 不一致")
    if want and doc and doc != want:
        problems.append(f"README 标题写 {doc}，与本次发布 {want} 不一致")

    if problems:
        print("\nFAIL: 版本号漂移——")
        for p in problems:
            print("  ·", p)
        print("\n请让 main.py 的 APP_VERSION、README 标题、发布 tag 三者一致，再提交/发版。")
        return 1

    print(f"\nOK: 版本号一致（{src}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
