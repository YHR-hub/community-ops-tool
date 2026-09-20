"""
截图脚本 —— 把每个页面渲染出来存成 PNG，用于肉眼验收
====================================================

为什么要写这个：
  「界面太素」是视觉问题，测试断言通过不等于好看。
  必须真的把画面截下来看一遍，才能判断设计系统有没有生效。

用法：python capture.py
输出：shots/*.png
"""

import os
import sys
import time

import customtkinter as ctk

ctk.set_appearance_mode("dark")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")


def _is_black(img):
    """采样中心区域判断是否全黑（拿到黑帧说明抓屏抢在重绘之前）。"""
    w, h = img.size
    if w < 4 or h < 4:
        return True
    box = (w // 4, h // 4, 3 * w // 4, 3 * h // 4)
    px = img.crop(box).resize((1, 1)).getpixel((0, 0))
    return sum(px[:3]) < 12


def _looks_ours(img):
    """
    判断截到的画面是不是本应用。
    本应用是深色主题，整体平均亮度很低；如果平均色偏亮（> 180），
    说明抓到的是别的窗口（会议共享、浏览器、资源管理器…）。
    """
    w, h = img.size
    box = (w // 8, h // 8, 7 * w // 8, 7 * h // 8)
    px = img.crop(box).resize((1, 1)).getpixel((0, 0))
    return sum(px[:3]) / 3 < 120


def shoot(app, name):
    """
    截取窗口区域并保存。对黑帧自动重试。

    踩过的坑（都实测过）：
      · attributes("-topmost", True) 会让窗口在抓屏时变成"未绘制"状态，
        结果拿到整片黑 —— 所以这里全程不用 topmost。
      · focus_force() 会触发重绘，紧接着抓屏同样拿到黑帧。
      · 只 lift() 不主动重绘也不稳，必须 <Expose> 触发一次重绘再等一会儿。
    稳定做法：lift() → <Expose> → 睡眠 → update() → 抓屏 → 校验非黑。
    """
    from PIL import ImageGrab

    img = None
    ok = False
    for attempt in range(8):
        try:
            app.lift()
        except Exception:
            pass
        try:
            app.event_generate("<Expose>")
        except Exception:
            pass
        app.update_idletasks()
        app.update()
        # 首个尝试给足时间让系统合成器把像素落盘
        time.sleep(0.5 + attempt * 0.25)
        app.update_idletasks()
        app.update()

        x = app.winfo_rootx()
        y = app.winfo_rooty()
        w = app.winfo_width()
        h = app.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        if not _is_black(img) and _looks_ours(img):
            ok = True
            break

    if not ok:
        # 抓到的不是本应用：多半是其他窗口盖在上面（会议共享、全屏应用…）。
        # 不要静默存一张别人的截图 —— 明确报出来，让使用者关掉遮挡后重跑。
        print(f"  [跳过] {name}.png —— 画面被其他窗口遮挡，未采信")
        return None

    path = os.path.join(OUT, f"{name}.png")
    img.save(path)
    print(f"  saved {name}.png  ({img.size[0]}x{img.size[1]})")
    return path


def main():
    os.makedirs(OUT, exist_ok=True)

    import db
    db.init_db()
    db.ensure_unique_indexes()

    import seed_demo
    seed_demo.seed(force=True)

    import main as app_main
    app = app_main.App()
    app.geometry("1440x900+60+40")
    # 不要设 -topmost：那会让窗口在抓屏时呈现未绘制状态，整批图全黑。
    app.update()
    time.sleep(1.5)
    app.update()

    print("\n截图中…")

    # 五个主页面
    for key, name in (("overview", "01_总览"),
                      ("data", "02_数据"),
                      ("versions", "03_版本看板"),
                      ("analysis", "05_分析健康度"),
                      ("report", "07_报告智能")):
        app.show_view(key)
        shoot(app, name)

    # 版本时间线
    app.show_view("versions")
    app._version_tab = "timeline"
    app.remount("versions")
    shoot(app, "04_版本时间线")

    # 版本详情（含任务清单）
    v = db.latest_version()
    app.show_view("versions")
    app._version_tab = "board"
    app.remount("versions")
    app._open_version_detail(v["id"])
    app.update()
    time.sleep(0.5)
    apps = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
    if apps:
        shoot(apps[-1], "04b_版本详情")
        # 切到角色使用率子 Tab
        for child in apps[-1].winfo_children():
            pass
        try:
            hosts = [c for c in apps[-1].winfo_children()
                     if isinstance(c, ctk.CTkFrame)]
        except Exception:
            hosts = []
        apps[-1].destroy()
    app.update()

    # 分析页其余 Tab
    for tab, name in (("ai", "06_分析AI"), ("compare", "06b_版本对比"),
                      ("retention", "06c_留存分析")):
        app._analysis_tab = tab
        app.remount("analysis")
        shoot(app, name)
    app._analysis_tab = "health"

    # 报告页其余 Tab
    for tab, name in (("period", "08_报告周期"), ("history", "09_历史归档")):
        app._report_tab = tab
        app.remount("report")
        shoot(app, name)
    app._report_tab = "smart"

    # 命令面板
    app.show_view("overview")
    app._open_command_panel()
    app.update()
    time.sleep(0.5)
    panels = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
    if panels:
        shoot(panels[-1], "10_搜索面板")
        panels[-1].destroy()
    app.update()

    # 今日早报（v4.2 智能体抽屉）
    app.show_view("overview")
    app.update()
    import agent as ops_agent
    b = ops_agent.generate(use_ai=False)
    app._show_briefing(b)
    app.update()
    time.sleep(0.5)
    briefs = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
    if briefs:
        shoot(briefs[-1], "11_早报智能体")
        briefs[-1].destroy()
    app.update()

    app.destroy()
    print(f"\n全部截图完成 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
