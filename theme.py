"""
设计系统 —— 米游社运营助手 v4.0「星空琉璃」
============================================

v4.0 换装说明：
  v3.1 是「中性暗色 + 米哈游红」，整体偏工具感；
  v4.0 借鉴星穹铁道登录界面的蓝紫冷调，往「游戏感」靠：
    - 主色换成星轨紫 #7B6BFF，与崩铁版本色（#8F7BFF）同族；
    - 明度阶梯整体偏蓝，卡片在深底上有一层「琉璃」般的冷光对比；
    - 语义色全部重新调校，保证在蓝紫底上依旧一眼可辨。

  最重要的结构变化：v3.1 的 PRIMARY 同时兼任「主色」和「危险红」，
  换主色前必须把这两层语义拆开 —— 否则换色后风险标记、涨跌、
  错误提示会全部变成紫色。所以 v4.0 新增 DANGER：
    PRIMARY = 品牌紫（按钮 / 导航 / 进度 / DAU 折线）
    DANGER  = 警戒红（高风险 / 逾期 / 超支 / 涨红 / 错误 toast）

颜色策略不变：用「五级明度阶梯」制造层次。
Tk 不支持 #RRGGBBAA 八位色值（会抛 invalid color name），
所有「淡底色」都必须用 RGB 混合算出来，见 blend()。
"""

# ═══════════════════════════════════════════════════════════
#  1. 明度阶梯（核心：层次的来源）
#     整体偏蓝紫，越靠前的元素越亮，层级自然浮现。
# ═══════════════════════════════════════════════════════════
BG_TOPBAR = "#07070F"     # 顶栏（最深）
BG_APP = "#0A0A16"        # 应用最底层
BG_SIDEBAR = "#0C0C19"    # 侧边栏比内容区更深 → 导航退后、内容靠前
BG_CONTENT = "#111123"    # 内容区
BG_CARD = "#191932"       # 卡片面
BG_ELEVATED = "#232348"   # 悬浮态 / 输入框 / 次级按钮
BG_BORDER = "#32325E"     # 边框 / 分隔线

# ═══════════════════════════════════════════════════════════
#  2. 语义色板
# ═══════════════════════════════════════════════════════════
PRIMARY = "#7B6BFF"        # 星轨紫 —— 主色 / 品牌强调 / 主按钮 / 主进度
PRIMARY_HOVER = "#6A59F0"

DANGER = "#FF4655"         # 警戒红 —— 高风险 / 逾期 / 超支 / 涨红 / 错误
DANGER_HOVER = "#E63A48"
SUCCESS = "#34D399"        # 正常 / 达标 / 已完成 / 跌绿
WARNING = "#FFB340"        # 警告 / 关注 / 进行中
INFO = "#5FD4FF"           # 对照轴 / 次要数据 / 副指标折线
AI = "#B48CFF"             # AI 功能统一用浅紫（与主色同族但更亮）
AI_HOVER = "#A37AFF"
NEUTRAL = "#6A6A94"        # 中性 / 已关闭

# 卡片面（blend 的默认底色，所有淡底都往卡片色上混）
_BG_CARD_FOR_BLEND = BG_CARD


def blend(fg, bg=_BG_CARD_FOR_BLEND, ratio=0.16):
    """把 fg 按 ratio 混到 bg 上，得到 #RRGGBB 的淡色。用于标签底、悬浮态。"""
    def parse(c):
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    try:
        fr, fgn, fb = parse(fg)
        br, bgn, bb = parse(bg)
    except Exception:
        return _BG_CARD_FOR_BLEND
    r = round(fr * ratio + br * (1 - ratio))
    g = round(fgn * ratio + bgn * (1 - ratio))
    b = round(fb * ratio + bb * (1 - ratio))
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


# 预计算的淡底色（替代 #RRGGBBAA 写法）
PRIMARY_DIM = blend(PRIMARY)
DANGER_DIM = blend(DANGER)
SUCCESS_DIM = blend(SUCCESS)
WARNING_DIM = blend(WARNING)
INFO_DIM = blend(INFO)
AI_DIM = blend(AI)
PRIMARY_SOFT = blend(PRIMARY, blend(PRIMARY, ratio=0.30), 0.45)

# ═══════════════════════════════════════════════════════════
#  3. 文字层级（冷调灰蓝，与底色同族）
# ═══════════════════════════════════════════════════════════
TEXT_PRIMARY = "#F2F2FC"    # 标题、关键数值
TEXT_BODY = "#C8C8E0"       # 正文
TEXT_SECONDARY = "#8C8CB8"  # 辅助说明、表头
TEXT_TERTIARY = "#6A6A96"   # 提示、占位符
TEXT_DISABLED = "#4A4A74"

# ═══════════════════════════════════════════════════════════
#  4. 字体
# ═══════════════════════════════════════════════════════════
FONT = "Microsoft YaHei"
FONT_NUM = "Segoe UI"  # 数字用 Segoe UI，比雅黑数字更规整

SIZE_DISPLAY = 26
SIZE_H1 = 19
SIZE_H2 = 15
SIZE_H3 = 13
SIZE_BODY = 12
SIZE_SMALL = 11
SIZE_TINY = 10


def font(size=SIZE_BODY, bold=False):
    """统一字体元组工厂，避免各处硬编码字体名。"""
    return (FONT, size, "bold") if bold else (FONT, size)


def num_font(size=SIZE_DISPLAY, bold=True):
    """数字专用字体。"""
    return (FONT_NUM, size, "bold") if bold else (FONT_NUM, size)


# ═══════════════════════════════════════════════════════════
#  5. 间距与圆角
# ═══════════════════════════════════════════════════════════
SP_XS = 4
SP_SM = 8
SP_MD = 12
SP_LG = 16
SP_XL = 24
SP_2XL = 32

RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14

PAGE_PAD_X = 24
PAGE_PAD_Y = 16


# ═══════════════════════════════════════════════════════════
#  6. 状态映射
# ═══════════════════════════════════════════════════════════
VERSION_STATUS = {
    "planning":  ("规划中", WARNING),
    "preparing": ("准备中", INFO),
    "live":      ("已上线", SUCCESS),
    "review":    ("复盘中", AI),
    "closed":    ("已关闭", NEUTRAL),
}

RISK_LEVEL = {"high": ("高", DANGER), "medium": ("中", WARNING), "low": ("低", SUCCESS)}
RISK_IMPACT = {"high": "高影响", "medium": "中影响", "low": "低影响"}

# 各游戏品牌色（时间线 / 使用率图会按游戏取色）
GAME_ACCENT = {
    "原神": "#5FD4FF",
    "崩坏：星穹铁道": "#8F7BFF",
    "绝区零": "#FFC94A",
    "崩坏3": "#FF4655",
}


# ═══════════════════════════════════════════════════════════
#  7. 兼容层 —— 旧常量名保持可用，迁移期不炸
#     注意 MHY_RED 指向 DANGER 而不是 PRIMARY：
#     它的语义是「米哈游红」，v4.0 里红色只承担警戒。
# ═══════════════════════════════════════════════════════════
MHY_RED = DANGER
MHY_DARK = BG_APP
MHY_CARD = BG_CARD
MHY_BORDER = BG_BORDER
MHY_TEXT = TEXT_BODY
MHY_SUB = TEXT_SECONDARY
GRID_COLOR = BG_BORDER
BG_COLOR = BG_APP
ACCENT_COLOR = PRIMARY
TEXT_COLOR = TEXT_PRIMARY
FONT_FAMILY = FONT


# ═══════════════════════════════════════════════════════════
#  8. ttk 样式
# ═══════════════════════════════════════════════════════════
def setup_ttk_style():
    from tkinter import ttk

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure("Treeview",
                    background=BG_CARD, foreground=TEXT_BODY,
                    fieldbackground=BG_CARD, bordercolor=BG_BORDER,
                    borderwidth=0, rowheight=30, font=(FONT, SIZE_BODY))
    style.configure("Treeview.Heading",
                    background=BG_APP, foreground=TEXT_SECONDARY,
                    font=(FONT, SIZE_SMALL, "bold"),
                    relief="flat", padding=(8, 8), borderwidth=0)
    style.map("Treeview.Heading", background=[("active", BG_ELEVATED)])
    style.map("Treeview",
              background=[("selected", blend(PRIMARY, ratio=0.30))],
              foreground=[("selected", TEXT_PRIMARY)])
    # 去掉选中时的虚线焦点框
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure("Vertical.TScrollbar",
                    background=BG_BORDER, troughcolor=BG_CONTENT,
                    arrowcolor=TEXT_SECONDARY, bordercolor=BG_CONTENT,
                    borderwidth=0, width=10)
    style.map("Vertical.TScrollbar", background=[("active", PRIMARY)])
    style.configure("Horizontal.TScrollbar",
                    background=BG_BORDER, troughcolor=BG_CONTENT,
                    arrowcolor=TEXT_SECONDARY, bordercolor=BG_CONTENT,
                    borderwidth=0)


# ═══════════════════════════════════════════════════════════
#  9. 资源路径（修正打包后取不到图标的问题）
# ═══════════════════════════════════════════════════════════
def resource_path(relative):
    """
    PyInstaller onefile 运行时资源被解压到 sys._MEIPASS；
    开发态则相对本文件所在目录。
    旧版用 dirname 两级上跳，打包后必然取不到图标。
    """
    import os
    import sys

    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


def set_app_icon(app):
    """设置窗口图标，失败静默降级（不中断启动）。"""
    import os

    ico = resource_path("icon.ico")
    if os.path.exists(ico):
        try:
            app.iconbitmap(ico)
            return
        except Exception:
            pass

    png = resource_path("icon.png")
    if os.path.exists(png):
        try:
            from PIL import Image, ImageTk
            img = ImageTk.PhotoImage(Image.open(png))
            app.iconphoto(False, img)
            app._icon_ref = img  # 防止被 GC 回收
        except Exception:
            pass
