"""
主框架 —— 米游社运营助手 v4.2
==============================

信息架构改动（解决「功能板块模糊」）：
  旧版：侧边栏 4 项，底下却藏着 6 套业务能力；排期/预算/风险 在
        「版本管理」Tab 和独立页面两处重复出现。
  新版：5 项主导航，一个能力只有一个入口。
        · 排期 / 预算 / 风险 合并进「版本」详情
        · 「分析」独立承载 AI 顾问 / 健康度 / 版本对比
        · 全局搜索从侧边栏底部移到顶部命令栏（Ctrl+K）

架构改动：
  旧版 5 个 Mixin 全部继承 ctk.CTk，主流程出现 hasattr(self, 'ai_result')
  这类判断 —— 模块间没有状态边界，改一处怕碰坏三处。
  新版 Mixin 不继承 ctk.CTk（纯 Mixin），共享状态收敛到 AppState。
"""

import sys
import customtkinter as ctk

import theme
from theme import (
    BG_APP, BG_CONTENT, BG_CARD, BG_ELEVATED, BG_BORDER, BG_SIDEBAR,
    PRIMARY, PRIMARY_DIM, SUCCESS, WARNING,
    TEXT_PRIMARY, TEXT_BODY, TEXT_SECONDARY, TEXT_TERTIARY,
    font, SIZE_H3, SIZE_BODY, SIZE_SMALL, SIZE_TINY,
    SP_XS, SP_SM, SP_MD, SP_LG, SP_XL, RADIUS_MD,
)
import icons
import components as C
from db import (init_db, save_config, load_config, add_log, recent_logs,
                global_search, latest_version, task_progress, parse_date,
                ensure_unique_indexes)

from views import (OverviewMixin, DataMixin, VersionsMixin,
                   AnalysisMixin, ReportMixin, IndustryMixin, LibraryMixin)

APP_VERSION = "4.6"
APP_TITLE = "米游社运营助手"

ctk.set_appearance_mode("dark")

# 主导航：(key, 标题, 图标, 快捷键)
NAV_ITEMS = [
    ("overview", "总览", "grid", "1"),
    ("data", "数据", "chart", "2"),
    ("versions", "版本", "calendar", "3"),
    ("analysis", "分析", "bulb", "4"),
    ("report", "报告", "doc", "5"),
    ("industry", "行业", "search", "6"),
    ("library", "文库", "list", "7"),
]
NAV_LABEL = {key: label for key, label, *_ in NAV_ITEMS}


class AppState:
    """
    集中存放跨模块共享状态。
    旧版把 current_view / dual_chart_mode / _ai_saved_content 散在 self 上，
    再加 hasattr 探测，导致状态边界不清。

    注意：这个对象挂在 `self.app_state`，**不能**挂在 `self.state` ——
    Tk 的 Misc 自带 state() 方法（返回窗口状态），CustomTkinter 的
    DPI 缩放追踪器会调用 window.state()，被覆盖后会报
    "'AppState' object is not callable" 并让整个界面停在初始状态。
    """

    def __init__(self):
        self.current_view = "overview"
        self.last_error = None


class BaseMixin:
    """
    所有视图 Mixin 的基类。
    只声明「我需要宿主 App 提供什么」，不继承 ctk.CTk。
    """

    def page_scaffold(self, nav_key, title, subtitle, icon, refresh=None):
        """
        统一页面骨架：标题区 + 可滚动内容区。
        返回 (滚动容器, 页面容器)。左侧视图只要往里塞内容即可，
        标题样式、刷新按钮、边距全站一致。
        """
        self.set_nav(nav_key)
        self.app_state.current_view = nav_key

        page = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=1)
        page.pack(fill="both", expand=True,
                  padx=theme.PAGE_PAD_X, pady=(theme.PAGE_PAD_Y, 0))

        header = C.PageHeader(page, title, subtitle, icon=icon)
        header.pack(fill="x", pady=(0, SP_LG))

        C.GhostButton(header.actions, "刷新",
                      refresh or (lambda: self.remount(nav_key)),
                      icon="refresh", width=82, height=30).pack(side="right")

        body = ctk.CTkScrollableFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(0, theme.PAGE_PAD_Y))

        # 底部「吃空间」的空帧。
        # 问题：CTkScrollableFrame 的内容帧在内容不足一屏时仍会撑满视口，
        # 剩下的高度会被**最后一个 fill="x" 的子控件**吸收 —— 于是页面
        # 末尾那张卡片被纵向拉长（左侧色条拖到整卡高度、文字占上半部分），
        # 截图里分析页体检结论区、总览页风险区的巨大空白都源于此。
        # 解法：用 side="bottom" 先占住底部剩余空间。pack 的 side 决定吸附边，
        # 后加入的 side="top"（默认）控件会排在它上方，与加入顺序无关，
        # 所以这个空帧能稳定兜住所有多余高度。
        ctk.CTkFrame(body, fg_color="transparent", height=1).pack(
            side="bottom", fill="x")
        return body, page


class App(OverviewMixin, DataMixin, VersionsMixin, AnalysisMixin, ReportMixin,
          IndustryMixin, LibraryMixin, BaseMixin, ctk.CTk):
    def __init__(self):
        super().__init__()

        init_db()
        # 老库补唯一索引：旧版没有唯一约束，重复录入会堆积重复行，
        # 而 CSV 导入依赖 ON CONFLICT 更新，缺约束会直接报错。
        try:
            ensure_unique_indexes()
        except Exception:
            pass

        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.configure(fg_color=BG_APP)

        theme.setup_ttk_style()
        theme.set_app_icon(self)

        self.app_state = AppState()
        self._ai_saved_content = ""
        self._nav_buttons = {}
        self._cmd_open = False
        # 页面级 Tab 状态：在构造时初始化，避免某个入口没走 show_* 就访问
        self._version_tab = "board"
        self._selected_version_id = None
        self._analysis_tab = "health"
        self._report_tab = "smart"

        self._build_sidebar()
        self._build_main()

        saved_geo = load_config("win_geometry")
        if saved_geo:
            try:
                self.geometry(saved_geo)
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_shortcuts()

        last = load_config("last_view", "overview")
        if last not in NAV_LABEL:
            last = "overview"
        self.show_view(last)
        self._refresh_log_widget()

    # ═══════════════════════════════════════════════════════
    #  侧边栏
    # ═══════════════════════════════════════════════════════
    def _build_sidebar(self):
        bar = ctk.CTkFrame(self, width=176, corner_radius=0, fg_color=BG_SIDEBAR)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)
        self.sidebar = bar

        self._build_logo(bar)
        self._build_nav(bar)
        self._build_footer(bar)
        # 当前版本卡片贴在底部之上
        self._build_current_version_card(bar)

    def _build_logo(self, bar):
        logo = ctk.CTkFrame(bar, fg_color="transparent", height=1)
        logo.pack(fill="x", padx=SP_LG, pady=(SP_XL, SP_LG))

        mark = ctk.CTkFrame(logo, fg_color=PRIMARY, width=28, height=28,
                            corner_radius=7)
        mark.pack(side="left")
        mark.pack_propagate(False)
        icons.draw_icon(mark, "grid", 15, "#FFFFFF", bg=PRIMARY).place(
            relx=0.5, rely=0.5, anchor="center")

        ttl = ctk.CTkFrame(logo, fg_color="transparent", height=1)
        ttl.pack(side="left", padx=(9, 0))
        ctk.CTkLabel(ttl, text="米游社", font=font(SIZE_H3, bold=True),
                     text_color=TEXT_PRIMARY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(ttl, text="运营助手", font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w")

    def _build_nav(self, bar):
        nav = ctk.CTkFrame(bar, fg_color="transparent", height=1)
        nav.pack(fill="x", padx=SP_SM, pady=(SP_XS, 0))

        for key, label, icon, hotkey in NAV_ITEMS:
            row = ctk.CTkFrame(nav, fg_color="transparent", height=38)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            # corner_radius = 高度的一半 → 胶囊形选中态。
            # v3.1 是 7px 的小圆角矩形，游戏感不足；v4.0 对齐星轨选单的胶囊样式。
            btn = ctk.CTkButton(
                row, text="", command=lambda k=key: self.show_view(k),
                fg_color="transparent", hover_color=BG_ELEVATED,
                corner_radius=19, height=38)
            btn.pack(fill="both", expand=True)

            icons.draw_icon(btn, icon, 14, TEXT_SECONDARY).place(
                x=13, rely=0.5, anchor="w")
            lbl = ctk.CTkLabel(btn, text=label, font=font(SIZE_BODY),
                               text_color=TEXT_BODY)
            lbl.place(x=37, rely=0.5, anchor="w")

            # 左侧激活指示条
            strip = ctk.CTkFrame(row, fg_color="transparent", width=3, height=20,
                                 corner_radius=2)
            strip.place(x=0, rely=0.5, anchor="w")

            # 图标画布和文字标签也要能随选中态变色（见 set_nav），
            # 所以把引用一起存下来；Canvas 不能直接改色，只能重建。
            self._nav_buttons[key] = {"btn": btn, "strip": strip,
                                      "icon": icon, "icon_w": None,
                                      "label": lbl}

    def _build_footer(self, bar):
        foot = ctk.CTkFrame(bar, fg_color="transparent", height=1)
        foot.pack(side="bottom", fill="x", padx=SP_LG, pady=SP_LG)

        row = ctk.CTkFrame(foot, fg_color="transparent", height=1)
        row.pack(fill="x")
        dot = ctk.CTkFrame(row, fg_color=SUCCESS, width=6, height=6, corner_radius=3)
        dot.pack(side="left", pady=4)
        dot.pack_propagate(False)
        ctk.CTkLabel(row, text="数据本地存储", font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(5, 0))
        ctk.CTkLabel(foot, text=f"v{APP_VERSION} · SQLite", font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY, anchor="w").pack(anchor="w", pady=(2, 0))

    def _build_current_version_card(self, bar):
        """
        侧边栏常驻「当前版本 + 上线天数 + 任务进度」。
        旧版这里只有一行 "v2.0 · SQLite"，对运营毫无信息量。
        """
        self._cv_card = ctk.CTkFrame(bar, fg_color=BG_CARD, corner_radius=RADIUS_MD,
                                     border_width=1, border_color=BG_BORDER)
        self._cv_card.pack(side="bottom", fill="x", padx=SP_MD, pady=SP_MD)
        self._render_current_version()

    def _render_current_version(self):
        for w in self._cv_card.winfo_children():
            w.destroy()

        v = latest_version()
        if not v:
            ctk.CTkLabel(self._cv_card, text="尚未创建版本",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY
                         ).pack(pady=SP_MD)
            return

        from datetime import datetime
        inner = ctk.CTkFrame(self._cv_card, fg_color="transparent", height=1)
        inner.pack(fill="x", padx=SP_MD, pady=SP_MD)

        ctk.CTkLabel(inner, text="当前版本", font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text=f"{v['game']} {v['version']}",
                     font=font(SIZE_H3, bold=True), text_color=TEXT_PRIMARY,
                     anchor="w").pack(anchor="w", pady=(2, 4))

        label, color = theme.VERSION_STATUS.get(v["status"],
                                                (v["status"], theme.NEUTRAL))
        row = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        row.pack(anchor="w")
        d = ctk.CTkFrame(row, fg_color=color, width=5, height=5, corner_radius=3)
        d.pack(side="left", pady=4)
        d.pack_propagate(False)
        days = max(0, (datetime.now() - parse_date(v["start_date"])).days)
        ctk.CTkLabel(row, text=f"{label} · 第 {days} 天", font=font(SIZE_TINY),
                     text_color=color).pack(side="left", padx=(5, 0))

        total, done = task_progress(v["id"])
        if total:
            pct = int(done / total * 100)
            ctk.CTkLabel(inner, text=f"任务 {done}/{total} · {pct}%",
                         font=font(SIZE_TINY), text_color=TEXT_TERTIARY,
                         anchor="w").pack(anchor="w", pady=(5, 3))
            track = ctk.CTkFrame(inner, fg_color=BG_APP, height=4, corner_radius=2)
            track.pack(fill="x")
            fill = ctk.CTkFrame(track, fg_color=SUCCESS if pct == 100 else PRIMARY,
                                height=4, corner_radius=2, width=10)
            fill.place(x=0, y=0)
            # 按容器实际宽度设置填充
            def size_bar(_e=None, f=fill, p=pct, t=track):
                w = max(4, int(t.winfo_width() * p / 100))
                f.configure(width=w)
            track.bind("<Configure>", size_bar)

    # ═══════════════════════════════════════════════════════
    #  主内容区
    # ═══════════════════════════════════════════════════════
    def _build_main(self):
        wrap = ctk.CTkFrame(self, fg_color=BG_CONTENT, corner_radius=0)
        wrap.pack(side="right", fill="both", expand=True)
        self.main_frame = wrap
        self._build_command_bar(wrap)

    def _build_command_bar(self, parent):
        """
        顶部命令栏：搜索入口 + 最近操作摘要。
        把旧版藏在侧边栏底部的搜索提到最显眼的位置。
        """
        bar = ctk.CTkFrame(parent, fg_color=BG_APP, height=44, corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        search = ctk.CTkButton(
            bar, text="", command=self._open_command_panel,
            fg_color=BG_CARD, hover_color=BG_ELEVATED,
            corner_radius=7, height=30, border_width=1, border_color=BG_BORDER)
        search.pack(side="left", fill="x", expand=True,
                    padx=(SP_XL, SP_MD), pady=7)
        icons.draw_icon(search, "search", 12, TEXT_TERTIARY).place(
            x=11, rely=0.5, anchor="w")
        ctk.CTkLabel(search, text="搜索版本 / 活动 / 报告", font=font(SIZE_SMALL),
                     text_color=TEXT_TERTIARY).place(x=31, rely=0.5, anchor="w")
        ctk.CTkLabel(search, text="Ctrl K", font=font(SIZE_TINY),
                     text_color=TEXT_TERTIARY).place(relx=1, x=-11, rely=0.5, anchor="e")

        self.log_label = ctk.CTkLabel(bar, text="", font=font(SIZE_TINY),
                                      text_color=TEXT_TERTIARY, anchor="e")
        self.log_label.pack(side="right", padx=(0, SP_XL))

    def _bind_shortcuts(self):
        for key, _label, _icon, hotkey in NAV_ITEMS:
            self.bind_all(f"<Control-Key-{hotkey}>",
                          lambda e, k=key: self.show_view(k))
        self.bind_all("<Control-k>", lambda e: self._open_command_panel())
        self.bind_all("<Control-f>", lambda e: self._open_command_panel())
        self.bind_all("<Control-s>", lambda e: self._quick_save())

    # ═══════════════════════════════════════════════════════
    #  导航
    # ═══════════════════════════════════════════════════════
    def set_nav(self, key):
        for k, items in self._nav_buttons.items():
            active = (k == key)
            items["btn"].configure(fg_color=PRIMARY_DIM if active else "transparent")
            items["strip"].configure(
                fg_color=PRIMARY if active else BG_SIDEBAR)
            # 选中项的文字和图标提亮 —— 胶囊底色只有配上亮文字才是「选中」，
            # 否则看起来像一块浮在侧边栏上的紫色补丁。
            items["label"].configure(
                text_color=TEXT_PRIMARY if active else TEXT_BODY)
            old = items.get("icon_w")
            if old is not None:
                try:
                    old.destroy()
                except Exception:
                    pass
            w = icons.draw_icon(items["btn"], items["icon"], 14,
                                TEXT_PRIMARY if active else TEXT_SECONDARY)
            w.place(x=13, rely=0.5, anchor="w")
            items["icon_w"] = w
        self.app_state.current_view = key

    def show_view(self, key, force=True):
        """切换视图。视图由各 Mixin 提供的 _build_<key> 实现。"""
        builder = getattr(self, f"_build_{key}", None)
        if builder is None:
            self.toast(f"「{NAV_LABEL.get(key, key)}」尚未实现", WARNING)
            return
        if not force and self.app_state.current_view == key:
            return
        self.clear_main()
        builder()
        self.app_state.current_view = key
        self._render_current_version()

    def remount(self, key=None):
        """重建当前视图（刷新）。"""
        self.show_view(key or self.app_state.current_view)

    def clear_main(self):
        """
        清空主内容区。

        旧版这里同时做了：保存 AI 内容、放遮罩、after(30) 延迟重建 ——
        把「切页」和「状态变更」耦合在一起，导致 dual_chart_mode 这类
        标志位的赋值时机难以推理，出现「点两次才生效」。
        新版只负责清空，其它副作用由调用方显式处理。
        """
        for w in self.main_frame.winfo_children():
            w.destroy()
        self._build_command_bar(self.main_frame)

    # ═══════════════════════════════════════════════════════
    #  命令面板
    # ═══════════════════════════════════════════════════════
    def _open_command_panel(self):
        if self._cmd_open:
            return
        self._cmd_open = True

        panel = ctk.CTkToplevel(self)
        panel.title("搜索")
        panel.transient(self)
        panel.configure(fg_color=BG_CARD)
        panel.resizable(False, False)

        self.update_idletasks()
        x = max(0, self.winfo_rootx() + (self.winfo_width() - 560) // 2)
        y = max(0, self.winfo_rooty() + 110)
        panel.geometry(f"560x420+{x}+{y}")

        top = ctk.CTkFrame(panel, fg_color="transparent", height=1)
        top.pack(fill="x", padx=SP_LG, pady=(SP_LG, SP_SM))
        icons.draw_icon(top, "search", 14, TEXT_TERTIARY).pack(side="left", pady=3)
        entry = ctk.CTkEntry(top, placeholder_text="输入关键词后回车",
                             fg_color=BG_ELEVATED, border_color=BG_BORDER,
                             border_width=1, text_color=TEXT_BODY,
                             placeholder_text_color=TEXT_TERTIARY,
                             font=font(SIZE_BODY), height=34)
        entry.pack(side="left", fill="x", expand=True, padx=(SP_SM, 0))

        box = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=SP_MD, pady=(0, SP_MD))

        def render(items):
            for w in box.winfo_children():
                w.destroy()
            if not items:
                C.EmptyState(box, "没有找到相关结果", "search",
                             "试试版本号、活动名或报告标题").pack(fill="both", expand=True)
                return
            for it in items:
                card = ctk.CTkFrame(box, fg_color=BG_ELEVATED,
                                    corner_radius=RADIUS_MD, height=54)
                card.pack(fill="x", pady=3)
                card.pack_propagate(False)

                ctk.CTkLabel(card, text=it["kind"], font=font(SIZE_TINY),
                             text_color=PRIMARY, width=34).pack(side="left",
                                                                padx=(SP_MD, 0))
                mid = ctk.CTkFrame(card, fg_color="transparent", height=1)
                mid.pack(side="left", fill="both", expand=True, padx=SP_SM)
                ctk.CTkLabel(mid, text=it["title"], font=font(SIZE_BODY),
                             text_color=TEXT_PRIMARY, anchor="w").pack(anchor="w",
                                                                       pady=(8, 0))
                ctk.CTkLabel(mid, text=it["meta"], font=font(SIZE_TINY),
                             text_color=TEXT_TERTIARY, anchor="w").pack(anchor="w")
                icons.draw_icon(card, "arrow-right", 13, TEXT_TERTIARY).pack(
                    side="right", padx=SP_MD)

        def do_search(_e=None):
            q = entry.get().strip()
            render(global_search(q) if q else [])

        entry.bind("<Return>", do_search)
        entry.bind("<KeyRelease>",
                   lambda e: do_search() if len(entry.get()) >= 2 else None)

        C.EmptyState(box, "输入关键词开始搜索", "search",
                     "支持版本、活动、报告全文").pack(fill="both", expand=True)

        def on_close():
            self._cmd_open = False
            try:
                panel.destroy()
            except Exception:
                pass

        panel.protocol("WM_DELETE_WINDOW", on_close)
        self.bind_all("<Escape>", lambda e: on_close(), add="+")
        try:
            panel.grab_set()
        except Exception:
            pass
        panel.after(60, entry.focus_set)

    # ═══════════════════════════════════════════════════════
    #  通用工具
    # ═══════════════════════════════════════════════════════
    def toast(self, msg, color=SUCCESS, ms=2000):
        t = ctk.CTkFrame(self, fg_color=color, corner_radius=RADIUS_MD)
        t.place(relx=0.985, rely=0.04, anchor="ne")

        inner = ctk.CTkFrame(t, fg_color="transparent", height=1)
        inner.pack(padx=SP_MD, pady=SP_SM)
        icons.draw_icon(inner, "check" if color == SUCCESS else "warn",
                        14, "#FFFFFF", bg=color).pack(side="left")
        ctk.CTkLabel(inner, text=msg, font=font(SIZE_SMALL),
                     text_color="#FFFFFF").pack(side="left", padx=(6, 0))
        self.after(ms, lambda: t.destroy() if t.winfo_exists() else None)

    def log(self, action, detail=""):
        add_log(action, detail)
        self._refresh_log_widget()

    def _refresh_log_widget(self):
        rows = recent_logs(2)
        if not rows:
            self.log_label.configure(text="")
            return
        parts = []
        for r in rows:
            s = r["action"] + (f" · {r['detail']}" if r["detail"] else "")
            parts.append(s[:18])
        self.log_label.configure(text="最近：" + " / ".join(parts))

    def _quick_save(self):
        """
        Ctrl+S 的上下文保存。
        旧版在 dashboard 分支只弹了个 Toast（"使用 Ctrl+1~4 切换模块"），
        根本没保存，用户却以为保存成功了。
        新版：能保存就保存，不能保存就明确说明。
        """
        view = self.app_state.current_view
        handler = getattr(self, f"_save_{view}", None)
        if callable(handler):
            handler()
        else:
            self.toast(f"「{NAV_LABEL.get(view, view)}」页面没有待保存的编辑内容",
                       WARNING)

    def _on_close(self):
        try:
            save_config("last_view", self.app_state.current_view or "overview")
            save_config("win_geometry", self.geometry())
        except Exception:
            pass
        self.destroy()


def main():
    import logger_setup
    log = logger_setup.setup_logging()
    log.info("=== 启动 v%s (frozen=%s) ===", APP_VERSION,
             bool(getattr(sys, "frozen", False)))
    try:
        App().mainloop()
        log.info("=== 正常退出 ===")
    except Exception:
        # 崩溃必须有痕迹：用户只会说「它闪了一下」，日志是唯一的线索
        log.exception("=== 未捕获异常，应用退出 ===")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
