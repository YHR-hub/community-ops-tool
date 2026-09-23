from tkinter import ttk

# ── 标准色彩常量 ──
BG_COLOR = "#0f0f1a"
ACCENT_COLOR = "#ff4d6a"
TEXT_COLOR = "#ffffff"
GRID_COLOR = "#303040"
FONT_FAMILY = "Microsoft YaHei"

# ── 兼容旧版别名 ──
MHY_RED = ACCENT_COLOR
MHY_DARK = BG_COLOR
MHY_CARD = "#1a1a2e"
MHY_BORDER = "#2a2a3e"
MHY_TEXT = "#e8e8e8"
MHY_SUB = "#8888aa"


def setup_ttk_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview",
                    background=MHY_CARD, foreground=MHY_TEXT,
                    fieldbackground=MHY_CARD, bordercolor=MHY_BORDER,
                    borderwidth=1, font=(FONT_FAMILY, 10))
    style.configure("Treeview.Heading",
                    background=BG_COLOR, foreground=TEXT_COLOR,
                    font=(FONT_FAMILY, 10, "bold"),
                    relief="flat", padding=6)
    style.map("Treeview.Heading", background=[("active", MHY_BORDER)])
    style.map("Treeview", background=[("selected", ACCENT_COLOR)], foreground=[("selected", TEXT_COLOR)])
    style.configure("Vertical.TScrollbar",
                    background=MHY_BORDER, troughcolor=BG_COLOR,
                    arrowcolor=MHY_TEXT, bordercolor=BG_COLOR)


def set_app_icon(app):
    """设置主窗口图标（优先米哈游icon，回退默认）"""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ico_path = os.path.join(base, "icon.ico")
    png_path = os.path.join(base, "icon.png")
    if os.path.exists(ico_path):
        try:
            app.iconbitmap(ico_path)
        except:
            pass
