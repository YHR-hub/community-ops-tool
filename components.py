"""
通用组件 —— 让各页面写起来短、看起来统一
========================================

旧版的问题不是「没有组件」，而是每个页面各自手搓卡片、自己写颜色，
导致同样一个「指标卡」在 dashboard 和 versions 里长得不一样。

这里把重复度最高的几类组件固化下来：
  Card        —— 标准卡片（可带左侧色条强调）
  StatCard    —— 指标卡（大数字 + 标签 + 环比）
  Badge       -- 状态标签（药丸形，带底色边框）
  EmptyState  —— 空状态（图标 + 说明 + 引导按钮）
  PageTitle   —— 页面标题区
  IconButton  —— 图标按钮
  Divider     —— 分隔线
  Field       —— 带标签的输入行
"""

import customtkinter as ctk

from theme import (
    BG_CARD, BG_CONTENT, BG_ELEVATED, BG_BORDER, BG_APP,
    PRIMARY, PRIMARY_HOVER, PRIMARY_DIM, SUCCESS, WARNING, INFO, AI, AI_HOVER,
    DANGER,
    TEXT_PRIMARY, TEXT_BODY, TEXT_SECONDARY, TEXT_TERTIARY,
    font, num_font, SIZE_H1, SIZE_H2, SIZE_H3, SIZE_BODY, SIZE_SMALL, SIZE_TINY,
    SIZE_DISPLAY,
    SP_XS, SP_SM, SP_MD, SP_LG, SP_XL,
    RADIUS_MD, RADIUS_LG,
)
import icons


# ═══════════════════════════════════════════════════════════════
#  透明容器工厂 —— 绕开 CustomTkinter 的默认尺寸陷阱
# ═══════════════════════════════════════════════════════════════
#
# CTkFrame() 在不传 width/height 时的行为很坑：
#   - 空帧不会收缩到 0，而是保留一个 200x200 的默认尺寸，
#     实测渲染出来是 250px 高；
#   - pack(fill="x") 只约束宽度，高度照样留 250px。
#
# 后果：任何「先建容器、视条件再决定放不放内容」的地方，
# 只要条件不成立（比如某版本没导入任务清单 → foot 帧为空），
# 就会凭空多出 250px 空白，把整张卡片撑高，
# 连带同一行的其他卡片一起被拉长。截图里版本卡下半部分的巨大空白、
# 分析页体检结论区那条长得离谱的色条，全都是这一个原因。
#
# 所以：凡是不打算立刻放内容的透明容器，一律用下面两个工厂函数，
# 显式把初始高度压到 1px；一旦塞进真实子控件，pack/grid 的
# 尺寸传播会立刻把它撑到正确高度。
# ═══════════════════════════════════════════════════════════════

def vbox(parent, **kw):
    """
    透明竖向容器（对应 pack 的默认 side="top" 语义）。
    初始高度 1px，放入内容后自动撑开。
    """
    kw.setdefault("fg_color", "transparent")
    kw.setdefault("height", 1)
    return ctk.CTkFrame(parent, **kw)


def hbox(parent, **kw):
    """透明横向容器。父容器里需要 fill="x" + expand 才能横向铺满。"""
    kw.setdefault("fg_color", "transparent")
    kw.setdefault("height", 1)
    return ctk.CTkFrame(parent, **kw)


class Row(ctk.CTkFrame):
    """
    一行内容：左色条（可选）+ 文本区。
    把总览风险列表、分析结论列表这类重复结构收敛成一处，
    避免每个页面各写一遍 pack 参数（也就各错一遍）。
    """

    def __init__(self, parent, accent=None, bar_height=34):
        super().__init__(parent, fg_color="transparent", height=1)
        self.bar = None
        if accent:
            self.bar = ctk.CTkFrame(self, fg_color=accent, width=3,
                                    height=bar_height, corner_radius=2)
            self.bar.pack(side="left", fill="y", padx=(0, SP_SM))
            self.bar.pack_propagate(False)
        self.text = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self.text.pack(side="left", fill="x", expand=True)


class AccentBar(ctk.CTkFrame):
    """
    左侧强调色条。

    CustomTkinter 的 place() 不允许传 width/height（必须在构造函数里给），
    所以色条高度不能靠 relheight 自适应。这里改成「用 grid 分列」：
    卡片内部拆成 [色条 | 内容] 两列，色条 sticky ns 自动撑满高度。
    """

    def __init__(self, parent, color, width=3):
        super().__init__(parent, fg_color=color, width=width,
                         corner_radius=0, height=10)


class Card(ctk.CTkFrame):
    """
    标准卡片。

    accent —— 传入颜色时在左侧画一条 3px 色条，用于把「需要注意」的卡片
              从一堆同色卡片里拎出来。这是新版解决「界面太素」的关键手法之一。
    """

    def __init__(self, parent, accent=None, **kw):
        kw.setdefault("fg_color", BG_CARD)
        kw.setdefault("corner_radius", RADIUS_MD)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", accent or BG_BORDER)
        super().__init__(parent, **kw)

        if accent:
            # 两张列：色条固定宽，内容占满；色条用 sticky="ns" 自动等高
            self.grid_columnconfigure(1, weight=1)
            AccentBar(self, accent).grid(row=0, column=0, sticky="ns", padx=(1, 0), pady=1)
            self.body = ctk.CTkFrame(self, fg_color="transparent")
            self.body.grid(row=0, column=1, sticky="nsew")
        else:
            self.body = self


class StatCard(ctk.CTkFrame):
    """
    指标卡：小标签 + 大数字 + 环比说明。

    delta     —— 环比文案，如 "较上期 +4.2%"
    delta_dir —— "up" / "down" / None，决定说明文字的颜色
    accent    —— 有值时整张卡变成强调卡（红边 + 左色条 + 数字用强调色）
    """

    def __init__(self, parent, label, value, delta=None, delta_dir=None,
                 accent=None, suffix=None, **kw):
        kw.setdefault("fg_color", BG_CARD)
        kw.setdefault("corner_radius", RADIUS_MD)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", accent or BG_BORDER)
        super().__init__(parent, **kw)

        # 关键：body 必须显式给初始高度 1px。
        # 不带 accent 时 body 就是 Card 自身的内容承载帧；若用 CTkFrame()
        # 默认尺寸，一旦调用方还没来得及塞内容（或本轮不塞内容），
        # 卡片会凭空高出 250px。
        inner = ctk.CTkFrame(self, fg_color="transparent", height=1)
        if accent:
            self.grid_columnconfigure(1, weight=1)
            AccentBar(self, accent, 3).grid(row=0, column=0, sticky="ns",
                                            padx=(1, 0), pady=1)
            inner.grid(row=0, column=1, sticky="nsew")
        else:
            inner.pack(fill="both", expand=True)

        ctk.CTkLabel(inner, text=label, font=font(SIZE_TINY),
                     text_color=TEXT_SECONDARY, anchor="w").pack(
            fill="x", padx=SP_MD, pady=(SP_MD, 0))

        val_row = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        val_row.pack(fill="x", padx=SP_MD, pady=(3, 0))
        ctk.CTkLabel(val_row, text=str(value), font=num_font(SIZE_DISPLAY),
                     text_color=accent or TEXT_PRIMARY, anchor="w").pack(side="left")
        if suffix:
            ctk.CTkLabel(val_row, text=suffix, font=font(SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w").pack(
                side="left", padx=(4, 0), pady=(6, 0))

        if delta:
            # 运营指标语义：涨=好=绿，跌=坏=红（注意与股票的涨红跌绿区分，
            # 这里是 DAU/帖子这类运营数据，不是行情）。
            dcolor = {"up": SUCCESS, "down": DANGER}.get(delta_dir, TEXT_SECONDARY)
            tail = ctk.CTkFrame(inner, fg_color="transparent", height=1)
            tail.pack(fill="x", padx=SP_MD, pady=(2, SP_MD))
            if delta_dir in ("up", "down"):
                icons.draw_icon(tail, delta_dir, 10, dcolor).pack(side="left", pady=1)
            ctk.CTkLabel(tail, text=delta, font=font(SIZE_TINY),
                         text_color=dcolor, anchor="w").pack(side="left", padx=(3, 0))
        else:
            ctk.CTkFrame(inner, fg_color="transparent", height=SP_MD).pack()


class Badge(ctk.CTkFrame):
    """
    药丸形状态标签：淡底 + 同色描边 + 同色文字。

    注意：Tk 不支持 #RRGGBBAA 八位色值（会报 invalid color name），
    所以淡底色必须用 RGB 混合算出来，不能靠 alpha 后缀。
    """

    def __init__(self, parent, text, color, **kw):
        kw.setdefault("fg_color", blend(color, BG_CARD, 0.16))
        kw.setdefault("corner_radius", 10)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", color)
        super().__init__(parent, **kw)
        ctk.CTkLabel(self, text=text, font=font(SIZE_TINY),
                     text_color=color).pack(padx=SP_SM, pady=1)


def blend(fg, bg, ratio):
    """
    把 fg 以 ratio 的比例混到 bg 上，返回 #RRGGBB。
    Tk 只认 6 位色值，这个函数用来手工实现「半透明底色」的效果。
    """
    def parse(c):
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    try:
        fr, fg_, fb = parse(fg)
        br, bg_, bb = parse(bg)
    except Exception:
        return BG_ELEVATED

    r = round(fr * ratio + br * (1 - ratio))
    g = round(fg_ * ratio + bg_ * (1 - ratio))
    b = round(fb * ratio + bb * (1 - ratio))
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


class SectionTitle(ctk.CTkFrame):
    """区块标题：图标 + 文字 + 右侧可选操作区。"""

    def __init__(self, parent, text, icon=None, icon_color=None, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(parent, **kw)
        if icon:
            icons.draw_icon(self, icon, 14,
                            icon_color or TEXT_SECONDARY).pack(side="left", pady=1)
        ctk.CTkLabel(self, text=text, font=font(SIZE_H3, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(6, 0))


class PageHeader(ctk.CTkFrame):
    """页面标题区：大标题 + 副标题 + 右侧操作槽。"""

    def __init__(self, parent, title, subtitle="", icon=None, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(parent, **kw)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", anchor="w")

        trow = ctk.CTkFrame(left, fg_color="transparent")
        trow.pack(anchor="w")
        if icon:
            icons.draw_icon(trow, icon, 17, PRIMARY).pack(side="left", pady=2)
        ctk.CTkLabel(trow, text=title, font=font(SIZE_H1, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(7, 0))

        if subtitle:
            ctk.CTkLabel(left, text=subtitle, font=font(SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w").pack(
                anchor="w", pady=(3, 0))

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.pack(side="right", anchor="e")


class EmptyState(ctk.CTkFrame):
    """
    空状态：图标 + 一句说明 + 可选引导按钮。

    旧版空状态只有一行灰字（"暂无数据"），用户不知道下一步做什么。
    """

    def __init__(self, parent, message, icon="folder", hint="",
                 action_text=None, action=None, height=140, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(parent, **kw)

        box = ctk.CTkFrame(self, fg_color="transparent", height=height)
        box.pack(fill="both", expand=True)
        box.pack_propagate(False)

        icons.draw_icon(box, icon, 30, BG_BORDER).pack(pady=(14, 6))
        ctk.CTkLabel(box, text=message, font=font(SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack()
        if hint:
            ctk.CTkLabel(box, text=hint, font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY).pack(pady=(2, 0))
        if action_text and action:
            PrimaryButton(box, action_text, action, icon="plus",
                          height=30).pack(pady=(10, 0))


class PrimaryButton(ctk.CTkButton):
    """主按钮：实心强调色。"""

    def __init__(self, parent, text, command, icon=None, height=32,
                 accent=PRIMARY, hover=PRIMARY_HOVER, **kw):
        kw.setdefault("font", font(SIZE_BODY, bold=True))
        super().__init__(parent, text=("  " + text) if icon else text,
                         command=command, height=height, corner_radius=RADIUS_MD,
                         fg_color=accent, hover_color=hover,
                         text_color="#FFFFFF", **kw)
        if icon:
            try:
                icons.draw_icon(self, icon, 13, "#FFFFFF").place(relx=0, x=12, rely=0.5, anchor="w")
            except Exception:
                pass


class GhostButton(ctk.CTkButton):
    """次级按钮：描边、透明底。"""

    def __init__(self, parent, text, command, icon=None, height=32, **kw):
        kw.setdefault("font", font(SIZE_BODY))
        super().__init__(parent, text=("  " + text) if icon else text,
                         command=command, height=height, corner_radius=RADIUS_MD,
                         fg_color="transparent", hover_color=BG_ELEVATED,
                         text_color=TEXT_BODY, border_width=1,
                         border_color=BG_BORDER, **kw)
        if icon:
            try:
                icons.draw_icon(self, icon, 13, TEXT_SECONDARY).place(
                    relx=0, x=11, rely=0.5, anchor="w")
            except Exception:
                pass


class IconButton(ctk.CTkButton):
    """
    纯图标按钮（用于删除、编辑等紧凑操作）。
    Tk 的 Button 没法只放图形，所以用「透明按钮 + 内嵌 Canvas」实现。
    """

    def __init__(self, parent, icon, command, size=26, color=TEXT_SECONDARY,
                 hover=BG_ELEVATED, **kw):
        super().__init__(parent, text="", command=command, width=size, height=size,
                         corner_radius=6, fg_color="transparent", hover_color=hover, **kw)
        icons.draw_icon(self, icon, 13, color).place(relx=0.5, rely=0.5, anchor="center")


class Divider(ctk.CTkFrame):
    def __init__(self, parent, vertical=False, **kw):
        if vertical:
            kw.setdefault("width", 1)
        else:
            kw.setdefault("height", 1)
        kw.setdefault("fg_color", BG_BORDER)
        kw.setdefault("corner_radius", 0)
        super().__init__(parent, **kw)


class Field(ctk.CTkFrame):
    """带标签的输入行，统一输入框外观。"""

    def __init__(self, parent, label, placeholder="", width=140,
                 label_width=76, kind="entry", values=None, default=None, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(parent, **kw)

        ctk.CTkLabel(self, text=label, font=font(SIZE_SMALL),
                     text_color=TEXT_SECONDARY, width=label_width,
                     anchor="w").pack(side="left", padx=(0, 4))

        if kind == "menu":
            self.widget = ctk.CTkOptionMenu(
                self, values=values or [], width=width,
                fg_color=BG_ELEVATED, button_color=BG_BORDER,
                button_hover_color=BG_BORDER, text_color=TEXT_BODY,
                dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_BODY,
                dropdown_hover_color=BG_ELEVATED, font=font(SIZE_BODY),
                dropdown_font=font(SIZE_BODY))
            if default is not None:
                self.widget.set(default)
        else:
            self.widget = ctk.CTkEntry(
                self, width=width, placeholder_text=placeholder,
                fg_color=BG_ELEVATED, border_color=BG_BORDER,
                border_width=1, text_color=TEXT_BODY,
                placeholder_text_color=TEXT_TERTIARY,
                font=font(SIZE_BODY), height=30)
            if default is not None:
                self.widget.insert(0, default)

        self.widget.pack(side="left")

    def get(self):
        return self.widget.get()

    def set(self, v):
        try:
            self.widget.set(v)
        except Exception:
            self.widget.delete(0, "end")
            self.widget.insert(0, v)

    def clear(self):
        try:
            self.widget.set("")
        except Exception:
            self.widget.delete(0, "end")


class FormCard(ctk.CTkFrame):
    """
    表单卡片：统一标题 + 行 + 提交按钮的排版。

    提供一个 rows 上下文，让调用方按行塞控件，避免每处都手写 pack 参数。
    """

    def __init__(self, parent, title, icon=None, **kw):
        kw.setdefault("fg_color", BG_CARD)
        kw.setdefault("corner_radius", RADIUS_MD)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", BG_BORDER)
        super().__init__(parent, **kw)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=SP_LG, pady=(SP_MD, SP_SM))
        SectionTitle(head, title, icon=icon).pack(side="left")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="x", padx=SP_LG, pady=(0, SP_MD))

    def row(self, pady=(0, SP_SM)):
        r = ctk.CTkFrame(self.body, fg_color="transparent")
        r.pack(fill="x", pady=pady)
        return r
