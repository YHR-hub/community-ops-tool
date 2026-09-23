"""主题层：芙宁娜配色（皇家深蓝+金色点缀+白）+ ttk.Style 配置"""
import tkinter.ttk as ttk

# ── 芙宁娜配色 ──
# 背景层：深海蓝
BG_DARK      = "#0d1b2a"   # 最深背景
BG_CARD      = "#152238"   # 卡片/面板
BG_INPUT     = "#1b3a5c"   # 输入框/按钮
# 文字层
FG_TEXT       = "#e8f0fe"   # 主文字（浅蓝白）
FG_DIM        = "#7a9ec2"   # 次要文字
# 强调层：皇家蓝 + 金色
ACCENT        = "#2d6aa5"   # 皇家蓝（选中/主按钮）
ACCENT_LIGHT  = "#4a9bd9"   # 浅蓝（悬浮/高亮）
GOLD          = "#c9a94e"   # 芙宁娜金（装饰/徽标）
GOLD_LIGHT    = "#e0c97a"   # 浅金
# 状态色
SUCCESS       = "#3dba72"   # 绿（偏蓝调，不违和）
WARNING       = "#d4a843"   # 警告（金色系）
DANGER        = "#c75450"   # 危险（深红）
# 边框
BORDER        = "#2a4a6e"


def setup_ttk_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.Treeview",
                     background=BG_CARD, foreground=FG_TEXT,
                     fieldbackground=BG_CARD, rowheight=28,
                     borderwidth=0, font=("Microsoft YaHei", 10))
    style.configure("Dark.Treeview.Heading",
                     background=BG_INPUT, foreground=GOLD,
                     font=("Microsoft YaHei", 10, "bold"))
    style.map("Dark.Treeview", background=[("selected", ACCENT)])
    style.map("Dark.Treeview.Heading", background=[("active", ACCENT_LIGHT)])
    return style
