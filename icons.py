"""
矢量图标 —— 用 tkinter Canvas 直接绘制
=====================================

为什么不用 emoji：
  emoji 在不同 Windows 版本 / 字体下的渲染差异很大，同一份代码在
  你的电脑和面试官的电脑上可能长得完全不同，演示风险高，且显廉价。

为什么不用图标字体：
  需要额外分发 .ttf 文件，打包体积增加，且字体缺失时静默失效。

Canvas 手绘的好处：
  零依赖、打包无副作用、可跟随主题色变色、风格完全统一。
"""

from theme import (TEXT_SECONDARY, TEXT_PRIMARY, BG_CARD, BG_ELEVATED,
                   PRIMARY, SUCCESS, WARNING, INFO, AI, NEUTRAL)

# 每个图标由一组绘制指令描述：(kind, coords, options)
# 这样图标定义是纯数据，可复用、可测。
_S = 14  # 默认视口尺寸


def _norm(insts, size, color, width):
    """把基于 14px 视口的指令缩放到目标尺寸。"""
    k = size / _S
    out = []
    for kind, coords, opts in insts:
        c = [v * k for v in coords]
        o = dict(opts)
        if "w" in o:
            o["w"] = max(1.0, o["w"] * k)
        if o.pop("stroke", False):
            # 闭合多边形轮廓 —— Tk 的 create_line 没有 outline，
            # 必须用 create_polygon 才能描边。
            o["outline"] = color
            o["fill"] = ""
            o["width"] = o.pop("w", width)
        elif o.pop("line", False):
            o["fill"] = color
            o["width"] = o.pop("w", width)
            o["capstyle"] = "round"
            o["joinstyle"] = "round"
        else:
            o["fill"] = o.pop("fill_color", color)
            o["outline"] = ""
        out.append((kind, c, o))
    return out


# ── 图标定义（14×14 视口坐标系）──
_ICONS = {
    # 网格 —— 总览
    "grid": [
        ("rect", [2, 2, 6, 6], {"fill_color": None}),
        ("rect", [8, 2, 12, 6], {"fill_color": None}),
        ("rect", [2, 8, 6, 12], {"fill_color": None}),
        ("rect", [8, 8, 12, 12], {"fill_color": None}),
    ],
    # 柱状图 —— 数据
    "chart": [
        ("line", [2.5, 11.5, 2.5, 7], {"line": True, "w": 1.8}),
        ("line", [6.3, 11.5, 6.3, 4], {"line": True, "w": 1.8}),
        ("line", [10.1, 11.5, 10.1, 6.5], {"line": True, "w": 1.8}),
    ],
    # 折线 —— 趋势
    "trend": [
        ("line", [2, 10, 5, 6.5, 8, 8.5, 12, 3], {"line": True, "w": 1.8}),
    ],
    # 日历 —— 版本
    "calendar": [
        ("rect", [1.8, 3, 12.2, 12], {"stroke": True, "w": 1.3}),
        ("line", [1.8, 6, 12.2, 6], {"line": True, "w": 1.2}),
        ("line", [4.5, 1.5, 4.5, 3.5], {"line": True, "w": 1.3}),
        ("line", [9.5, 1.5, 9.5, 3.5], {"line": True, "w": 1.3}),
    ],
    # 人形 —— 分析
    "user": [
        ("oval", [4.6, 2, 9.4, 6.4], {"stroke": True, "w": 1.3}),
        ("arc", [2.2, 8, 11.8, 14], {"stroke": True, "w": 1.3}),
    ],
    # 文档 —— 报告
    "doc": [
        ("poly", [3.5, 1.8, 8.2, 1.8, 10.5, 4.4, 10.5, 12.2, 3.5, 12.2],
         {"stroke": True, "w": 1.3}),
        ("line", [5.5, 6, 8.5, 6], {"line": True, "w": 1.2}),
        ("line", [5.5, 8.6, 8.5, 8.6], {"line": True, "w": 1.2}),
    ],
    # 搜索
    "search": [
        ("oval", [2.5, 2.5, 9, 9], {"stroke": True, "w": 1.4}),
        ("line", [8.6, 8.6, 11.8, 11.8], {"line": True, "w": 1.5}),
    ],
    # 加号
    "plus": [
        ("line", [7, 3, 7, 11], {"line": True, "w": 1.8}),
        ("line", [3, 7, 11, 7], {"line": True, "w": 1.8}),
    ],
    # 关闭
    "close": [
        ("line", [3.5, 3.5, 10.5, 10.5], {"line": True, "w": 1.6}),
        ("line", [10.5, 3.5, 3.5, 10.5], {"line": True, "w": 1.6}),
    ],
    # 刷新
    "refresh": [
        ("arc", [2, 2, 12, 12], {"stroke": True, "w": 1.4}),
        ("line", [11, 2.5, 11.4, 5.8], {"line": True, "w": 1.4}),
    ],
    # 编辑
    "edit": [
        ("poly", [3, 11, 4.2, 8.4, 9.6, 3, 11, 4.4, 5.6, 9.8], {"stroke": True, "w": 1.2}),
    ],
    # 删除（垃圾桶）
    "trash": [
        ("line", [3.2, 4, 10.8, 4], {"line": True, "w": 1.3}),
        ("line", [5.5, 2.4, 8.5, 2.4], {"line": True, "w": 1.3}),
        ("line", [4.3, 4.4, 4.9, 11.6], {"line": True, "w": 1.2}),
        ("line", [9.7, 4.4, 9.1, 11.6], {"line": True, "w": 1.2}),
    ],
    # 警告三角
    "warn": [
        ("poly", [7, 2, 12.6, 12, 1.4, 12], {"stroke": True, "w": 1.2}),
        ("line", [7, 6, 7, 9], {"line": True, "w": 1.4}),
        ("oval", [6.4, 10, 7.6, 11.2], {"fill_color": None}),
    ],
    # 勾
    "check": [
        ("line", [3, 7.4, 6, 10.4, 11, 4], {"line": True, "w": 1.9}),
    ],
    # 下载
    "download": [
        ("line", [7, 2.2, 7, 9.4], {"line": True, "w": 1.5}),
        ("line", [3.8, 6.4, 7, 9.6, 10.2, 6.4], {"line": True, "w": 1.5}),
        ("line", [2.4, 11.8, 11.6, 11.8], {"line": True, "w": 1.5}),
    ],
    # 复制
    "copy": [
        ("rect", [4.6, 1.8, 12.2, 9.4], {"stroke": True, "w": 1.2}),
        ("poly", [1.8, 4.6, 1.8, 12.2, 9.4, 12.2, 9.4, 9.4], {"stroke": True, "w": 1.2}),
    ],
    # 保存（软盘）
    "save": [
        ("poly", [2, 2, 10.4, 2, 12, 3.6, 12, 12, 2, 12], {"stroke": True, "w": 1.2}),
        ("rect", [4.4, 2.4, 9.6, 5.6], {"fill_color": NEUTRAL}),
        ("rect", [4.2, 8, 9.8, 12], {"fill_color": NEUTRAL}),
    ],
    # 火箭 —— AI 生成
    "rocket": [
        ("poly", [7, 1.6, 10.4, 5.2, 8.4, 10, 5.6, 10, 3.6, 5.2], {"stroke": True, "w": 1.2}),
        ("oval", [5.8, 4.4, 8.2, 6.8], {"stroke": True, "w": 1.1}),
        ("line", [5.4, 10.4, 4.2, 12.4], {"line": True, "w": 1.1}),
        ("line", [8.6, 10.4, 9.8, 12.4], {"line": True, "w": 1.1}),
    ],
    # 灯泡
    "bulb": [
        ("arc", [3.6, 1.6, 10.4, 8.4], {"stroke": True, "w": 1.3}),
        ("line", [5.4, 8.6, 5.4, 10.6], {"line": True, "w": 1.3}),
        ("line", [8.6, 8.6, 8.6, 10.6], {"line": True, "w": 1.3}),
        ("line", [5.6, 12, 8.4, 12], {"line": True, "w": 1.3}),
    ],
    # 左箭头
    "arrow-left": [
        ("line", [11.5, 7, 2.5, 7], {"line": True, "w": 1.6}),
        ("line", [6, 3.2, 2.3, 7, 6, 10.8], {"line": True, "w": 1.6}),
    ],
    # 右箭头
    "arrow-right": [
        ("line", [2.5, 7, 11.5, 7], {"line": True, "w": 1.6}),
        ("line", [8, 3.2, 11.7, 7, 8, 10.8], {"line": True, "w": 1.6}),
    ],
    # 向上趋势
    "up": [
        ("line", [7, 11.5, 7, 2.8], {"line": True, "w": 1.7}),
        ("line", [3.4, 6.4, 7, 2.6, 10.6, 6.4], {"line": True, "w": 1.7}),
    ],
    # 向下趋势
    "down": [
        ("line", [7, 2.5, 7, 11.2], {"line": True, "w": 1.7}),
        ("line", [3.4, 7.6, 7, 11.4, 10.6, 7.6], {"line": True, "w": 1.7}),
    ],
    # 盾牌
    "shield": [
        ("poly", [7, 1.6, 11.8, 3.6, 11.8, 7.4, 7, 12.4, 2.2, 7.4, 2.2, 3.6],
         {"stroke": True, "w": 1.2}),
    ],
    # 钱袋
    "money": [
        ("poly", [4.6, 3.2, 9.4, 3.2, 10.6, 5.4, 10.6, 10.6, 3.4, 10.6, 3.4, 5.4],
         {"stroke": True, "w": 1.2}),
        ("line", [5.4, 1.4, 8.6, 1.4], {"line": True, "w": 1.2}),
    ],
    # 列表清单
    "list": [
        ("line", [2.4, 3.6, 11.6, 3.6], {"line": True, "w": 1.4}),
        ("line", [2.4, 7, 11.6, 7], {"line": True, "w": 1.4}),
        ("line", [2.4, 10.4, 8, 10.4], {"line": True, "w": 1.4}),
    ],
    # 时钟
    "clock": [
        ("oval", [1.8, 1.8, 12.2, 12.2], {"stroke": True, "w": 1.3}),
        ("line", [7, 4, 7, 7.2, 9.4, 8.6], {"line": True, "w": 1.3}),
    ],
    # 设置齿轮
    "settings": [
        ("oval", [5.2, 5.2, 8.8, 8.8], {"stroke": True, "w": 1.2}),
        ("line", [7, 1.2, 7, 3.4], {"line": True, "w": 1.2}),
        ("line", [7, 10.6, 7, 12.8], {"line": True, "w": 1.2}),
        ("line", [1.9, 7, 4.1, 7], {"line": True, "w": 1.2}),
        ("line", [9.9, 7, 12.1, 7], {"line": True, "w": 1.2}),
    ],
    # 眼睛
    "eye": [
        ("arc", [1.4, 3, 12.6, 11], {"stroke": True, "w": 1.2}),
        ("oval", [5.4, 5.2, 8.6, 8.4], {"fill_color": None}),
    ],
    # 闪电
    "bolt": [
        ("poly", [7.6, 1.4, 3.4, 8, 6.6, 8, 6.2, 12.6, 10.4, 6.2, 7.2, 6.2],
         {"stroke": True, "w": 1.1}),
    ],
    # 星标
    "star": [
        ("poly", [7, 1.6, 8.6, 5.4, 12.6, 5.8, 9.6, 8.5, 10.5, 12.4, 7, 10.2, 3.5, 12.4,
                  4.4, 8.5, 1.4, 5.8, 5.4, 5.4], {"stroke": True, "w": 1.1}),
    ],
    # 文件夹
    "folder": [
        ("poly", [1.8, 4.2, 5.6, 4.2, 6.8, 6, 12.2, 6, 12.2, 11.8, 1.8, 11.8],
         {"stroke": True, "w": 1.2}),
    ],
    # 对比（双柱）
    "compare": [
        ("line", [3.6, 11.6, 3.6, 5.4], {"line": True, "w": 2.2}),
        ("line", [7, 11.6, 7, 2.8], {"line": True, "w": 2.2}),
        ("line", [10.4, 11.6, 10.4, 7.6], {"line": True, "w": 2.2}),
    ],
}


def resolve_bg(parent, fallback=BG_CARD):
    """
    推断父容器的实际背景色。
    CTkFrame 的背景存在 fg_color 里，且可能是 (light, dark) 元组，
    Canvas 只接受单个颜色字符串，所以必须做一层转换。
    任何异常一律退回 fallback，绝不让取色失败影响渲染。
    """
    try:
        fg = parent.cget("fg_color")
    except Exception:
        return fallback
    if isinstance(fg, (tuple, list)):
        # (light, dark) → 本项目是暗色主题，取 dark
        fg = fg[-1] if fg else fallback
    if not isinstance(fg, str) or fg.lower() in ("", "none", "transparent"):
        return fallback
    return fg


def draw_icon(parent, name, size=16, color=TEXT_SECONDARY, bg=None, width=1.3):
    """
    在任意容器上绘制一个矢量图标。

    parent —— 父容器（CTkFrame / tk.Frame / Toplevel 均可）
    返回一个 Canvas 部件，请像普通组件一样 pack/grid/place。
    """
    import tkinter as tk

    insts = _ICONS.get(name)
    if insts is None:
        raise KeyError(f"未定义的图标: {name}")

    canvas = tk.Canvas(parent, width=size, height=size,
                       bg=bg if bg is not None else resolve_bg(parent),
                       highlightthickness=0, bd=0)

    for kind, coords, opts in _norm(insts, size, color, width):
        o = dict(opts)
        if kind == "line":
            canvas.create_line(*coords, **o)
        elif kind == "rect":
            if o.get("outline"):
                canvas.create_rectangle(*coords, **o)
            else:
                canvas.create_rectangle(*coords, fill=o.get("fill", color),
                                        outline=o.get("outline", ""))
        elif kind == "oval":
            if o.get("outline"):
                canvas.create_oval(*coords, **o)
            else:
                canvas.create_oval(*coords, fill=o.get("fill", color), outline="")
        elif kind == "arc":
            canvas.create_arc(*coords, start=30, extent=300, style="arc", **o)
        elif kind == "poly":
            # 闭合轮廓路径：用 polygon 描边，fill="" 表示只要线不要面
            canvas.create_polygon(*coords, **o)
    return canvas


def icon_names():
    """返回全部可用图标名，便于自检。"""
    return sorted(_ICONS.keys())
