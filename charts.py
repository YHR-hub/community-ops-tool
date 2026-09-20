"""
图表组件 —— 自适应宽度的 Canvas 绘图
====================================

旧版图表的问题：
  `w = 700`、`bar_width = 680` 全部硬编码。窗口拖大后图表纹丝不动，
  换台分辨率不同的电脑演示，布局直接崩。

这里的做法：
  图表画在 Canvas 上，绑定 <Configure> 事件，容器宽度一变就按实际像素重绘。
  所有坐标基于传入的宽高计算，不含任何魔法数字。
"""

import tkinter as tk

from theme import (
    BG_APP, BG_CARD, BG_BORDER, PRIMARY, INFO, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_TERTIARY, font, SIZE_TINY, SIZE_SMALL,
)
from components import blend


def moving_average(values, window=3):
    """
    滑动平均，仅用于「画出来好看」的展示层平滑。

    为什么需要它：
      日频运营数据（DAU / 互动率）天然带噪声，30 个点直接连折线，
      曲线会锯齿到看不出趋势 —— 截图里两条线交错成一片，观感像花屏。
      业内看板通常画「原始点 + 平滑线」两层，这里简化为只画平滑线，
      但窗口固定 3 点，不会抹掉周末效应这种真实波动。

    注意：只对展示做平滑，所有计算（环比、阈值判断）仍用原始值。
    绝不能拿平滑后的数去做结论，否则会把真实下跌抹平。
    """
    if window < 2 or len(values) < window:
        return list(values)
    half = window // 2
    out = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        chunk = [v for v in values[lo:hi] if v is not None]
        out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


class _BaseChart(tk.Canvas):
    """图表基类：负责尺寸自适应与重绘节流。"""

    def __init__(self, parent, height=200, **kw):
        super().__init__(parent, height=height, bg=BG_CARD,
                         highlightthickness=0, bd=0, **kw)
        self._height = height
        self._data = None
        self._last_w = 0
        self._redraw_job = None
        self.bind("<Configure>", self._on_resize)

    def set_data(self, data):
        self._data = data
        self._schedule()

    def _on_resize(self, event):
        # 宽度变化超过 2px 才重绘，避免拖动窗口时疯狂刷新
        if abs(event.width - self._last_w) > 2:
            self._last_w = event.width
            self._schedule()

    def _schedule(self):
        """节流：把多次重绘请求合并到一次。"""
        if self._redraw_job:
            try:
                self.after_cancel(self._redraw_job)
            except Exception:
                pass
        self._redraw_job = self.after(16, self._redraw)

    def _redraw(self):
        self._redraw_job = None
        w = self.winfo_width()
        h = self._height
        if w <= 1:
            return
        self.delete("all")
        if self._data:
            self.draw(w, h)


class LineChart(_BaseChart):
    """
    折线图，支持双轴（左轴主指标，右轴副指标）。

    data = {
        "labels": ["08-21", ...],
        "series": [
            {"name": "DAU", "values": [...], "color": PRIMARY, "axis": "left",
             "fill": True, "width": 2, "smooth": 5},
            {"name": "互动率", "values": [...], "color": INFO, "axis": "right",
             "width": 1.4, "smooth": 3},
        ]
    }

    每个 series 支持的可选参数：
      fill    —— 是否填充到基线（只给主指标开，双轴都填会糊）
      width   —— 线宽，副指标建议 1.4 以便和主指标拉开层级
      smooth  —— 滑动平均窗口，0 表示不平滑（离散事件数据应设为 0）
    """

    def __init__(self, parent, height=210, show_legend=True, **kw):
        super().__init__(parent, height=height, **kw)
        self.show_legend = show_legend

    def draw(self, w, h):
        d = self._data
        labels = d.get("labels") or []
        series = d.get("series") or []
        if len(labels) < 2 or not series:
            self.create_text(w // 2, h // 2, text="数据不足，至少需要 2 个数据点",
                             fill=TEXT_TERTIARY, font=font(SIZE_TINY))
            return

        pad_l, pad_r = 52, 52
        pad_t = 34 if self.show_legend else 16
        pad_b = 26
        cw = max(10, w - pad_l - pad_r)
        ch = max(10, h - pad_t - pad_b)

        def axis_of(s):
            return s.get("axis", "left")

        # ── 各轴量程 ──
        def rng(axis):
            vals = []
            for s in series:
                if axis_of(s) == axis:
                    vals.extend(v for v in s["values"] if v is not None)
            if not vals:
                return 0, 1
            lo, hi = min(vals), max(vals)
            if lo == hi:
                lo, hi = lo * 0.9, hi * 1.1 if hi else 1
            # 上下留 8% 余量，曲线不会贴边
            span = hi - lo
            return lo - span * 0.08, hi + span * 0.08

        lmin, lmax = rng("left")
        rmin, rmax = rng("right")

        def ypos(v, axis):
            lo, hi = (lmin, lmax) if axis == "left" else (rmin, rmax)
            span = (hi - lo) or 1
            return pad_t + (1 - (v - lo) / span) * ch

        def xpos(i):
            return pad_l + i * cw / (len(labels) - 1)

        # ── 网格 ──
        # 只在中间三条画网格线，首尾两条省略：折线天生贴着上下边界，
        # 再画线会跟曲线重叠成「双线」，看着像数据错位。
        for k in range(1, 4):
            gy = pad_t + k * ch / 4
            self.create_line(pad_l, gy, pad_l + cw, gy,
                             fill=blend(BG_BORDER, BG_CARD, 0.55), dash=(2, 4))

        # ── 轴标签 ──
        left_used = any(axis_of(s) == "left" for s in series)
        right_used = any(axis_of(s) == "right" for s in series)

        for k in range(5):
            gy = pad_t + k * ch / 4
            if left_used:
                v = lmax - (lmax - lmin) * k / 4
                self.create_text(pad_l - 8, gy, text=_fmt_axis(v),
                                 fill=TEXT_TERTIARY, font=font(SIZE_TINY),
                                 anchor="e")
            if right_used:
                v = rmax - (rmax - rmin) * k / 4
                self.create_text(pad_l + cw + 8, gy, text=_fmt_axis(v),
                                 fill=blend(INFO, BG_CARD, 0.55),
                                 font=font(SIZE_TINY), anchor="w")

        # ── 折线 ──
        # 分两遍画：先铺所有填充面积，再画所有折线。
        # 否则后画的填充会把先画的线盖住，双轴场景下蓝色线被红色面积压掉一截。
        computed = []
        for s in series:
            axis = axis_of(s)
            win = s.get("smooth", 3)
            vals = moving_average(s["values"], win) if win else list(s["values"])
            pts = []
            for i, v in enumerate(vals):
                if v is None:
                    continue
                pts.extend([xpos(i), ypos(v, axis)])
            if len(pts) >= 4:
                computed.append((s, pts))

        for s, pts in computed:
            if not s.get("fill"):
                continue
            # 填充只用来表达「体量」，透明度压到 0.08，
            # 不让面积块抢走折线本身的视觉焦点。
            poly = list(pts) + [pts[-2], pad_t + ch, pts[0], pad_t + ch]
            self.create_polygon(poly, fill=blend(s["color"], BG_CARD, 0.08),
                                outline="")

        for s, pts in computed:
            self.create_line(*pts, fill=s["color"], width=s.get("width", 2),
                             capstyle="round", joinstyle="round", smooth=False)
            # 末端点：只给主指标画，副指标画反而让交叉处更乱
            if s.get("width", 2) >= 2:
                self.create_oval(pts[-2] - 3, pts[-1] - 3,
                                 pts[-2] + 3, pts[-1] + 3,
                                 fill=s["color"], outline=BG_CARD, width=1.5)

        # ── X 轴标签 ──
        # 用「等间隔抽稀 + 末尾强制补一个」的策略。
        # 旧版按 cw//44 估格数再取整，30 个点会抽出 09-04/09-05/09-07/09-08
        # 这种疏密不均的刻度，看着像 bug。
        label_w = 50
        max_labels = max(2, int(cw // label_w))
        if len(labels) <= max_labels:
            picks = list(range(len(labels)))
        else:
            step = len(labels) / max_labels
            picks = sorted({int(i * step) for i in range(max_labels)})
            picks[-1] = min(picks[-1], len(labels) - 1)
            if picks[-1] != len(labels) - 1:
                picks[-1] = len(labels) - 1
        for i in picks:
            self.create_text(xpos(i), pad_t + ch + 12, text=str(labels[i]),
                             fill=TEXT_TERTIARY, font=font(SIZE_TINY))

        # ── 图例 ──
        if self.show_legend:
            lx = pad_l
            for s in series:
                self.create_line(lx, 12, lx + 14, 12, fill=s["color"], width=2)
                self.create_text(lx + 19, 12, text=s["name"], fill=TEXT_SECONDARY,
                                 font=font(SIZE_TINY), anchor="w")
                lx += 22 + len(s["name"]) * 8


class BarChart(_BaseChart):
    """柱状图，用于角色使用率 TOP N 这类排名数据。"""

    def __init__(self, parent, height=200, horizontal=True, **kw):
        super().__init__(parent, height=height, **kw)
        self.horizontal = horizontal

    def draw(self, w, h):
        d = self._data
        items = d.get("items") or []
        if not items:
            self.create_text(w // 2, h // 2, text="暂无数据",
                             fill=TEXT_TERTIARY, font=font(SIZE_TINY))
            return

        if self.horizontal:
            self._draw_h(w, h, items)
        else:
            self._draw_v(w, h, items)

    def _draw_h(self, w, h, items):
        """横向条形：名字在左，条在右，数值在条尾。适合中文角色名。"""
        label_w = 92
        value_w = 56
        bar_area = max(20, w - label_w - value_w - 16)
        n = len(items)
        row_h = min(30, max(16, (h - 8) // n))
        top = (h - row_h * n) / 2

        vmax = max((it["value"] for it in items), default=1) or 1
        accent = self._data.get("color", PRIMARY)

        for i, it in enumerate(items):
            y = top + i * row_h + row_h / 2
            # 名字
            self.create_text(label_w - 8, y, text=str(it["label"])[:8],
                             fill=TEXT_SECONDARY, font=font(SIZE_TINY),
                             anchor="e")
            # 轨道
            self.create_rectangle(label_w, y - 5, label_w + bar_area, y + 5,
                                  fill=BG_APP, outline="")
            # 条
            bw = max(2, bar_area * it["value"] / vmax)
            self.create_rectangle(label_w, y - 5, label_w + bw, y + 5,
                                  fill=accent, outline="")
            # 数值
            self.create_text(label_w + bar_area + 8, y, text=_fmt_axis(it["value"]),
                             fill=TEXT_PRIMARY, font=font(SIZE_TINY), anchor="w")

    def _draw_v(self, w, h, items):
        """纵向柱：适合时间序列。"""
        pad_l, pad_r, pad_t, pad_b = 44, 12, 16, 28
        cw = max(10, w - pad_l - pad_r)
        ch = max(10, h - pad_t - pad_b)
        vmax = max((it["value"] for it in items), default=1) or 1
        n = len(items)
        slot = cw / n
        bw = max(4, slot * 0.55)
        accent = self._data.get("color", PRIMARY)

        for k in range(5):
            gy = pad_t + k * ch / 4
            self.create_line(pad_l, gy, pad_l + cw, gy, fill=BG_BORDER, dash=(2, 4))
            self.create_text(pad_l - 6, gy, text=_fmt_axis(vmax * (1 - k / 4)),
                             fill=TEXT_TERTIARY, font=font(SIZE_TINY), anchor="e")

        for i, it in enumerate(items):
            cx = pad_l + slot * i + slot / 2
            bh = ch * it["value"] / vmax
            self.create_rectangle(cx - bw / 2, pad_t + ch - bh,
                                  cx + bw / 2, pad_t + ch,
                                  fill=accent, outline="")
            self.create_text(cx, pad_t + ch + 12, text=str(it["label"])[:6],
                             fill=TEXT_TERTIARY, font=font(SIZE_TINY))


class GanttChart(_BaseChart):
    """
    时间线甘特图。

    data = {
        "rows": [{"label": "...", "start": date, "end": date, "color": "#..", "badge": "..."}],
        "min": date, "max": date,
    }
    """

    def __init__(self, parent, height=240, **kw):
        super().__init__(parent, height=height, **kw)

    def draw(self, w, h):
        d = self._data
        rows = d.get("rows") or []
        dmin, dmax = d.get("min"), d.get("max")
        if not rows or not dmin or not dmax:
            self.create_text(w // 2, h // 2, text="暂无版本数据",
                             fill=TEXT_TERTIARY, font=font(SIZE_TINY))
            return

        label_w = 148
        pad_r, pad_t, pad_b = 16, 30, 26
        cw = max(20, w - label_w - pad_r)
        ch = max(20, h - pad_t - pad_b)
        total_days = max(1, (dmax - dmin).days)

        # 月份刻度
        from datetime import timedelta
        t = dmin.replace(day=1)
        while t <= dmax:
            x = label_w + (t - dmin).days / total_days * cw
            if x >= label_w:
                self.create_line(x, pad_t - 6, x, pad_t + ch,
                                 fill=BG_BORDER, dash=(2, 4))
                self.create_text(x + 4, pad_t - 14, text=f"{t.month}月",
                                 fill=TEXT_TERTIARY, font=font(SIZE_TINY), anchor="w")
            # 下个月
            t = (t.replace(day=28) + timedelta(days=4)).replace(day=1)

        row_h = min(34, max(20, ch // max(1, len(rows))))
        for i, r in enumerate(rows):
            y = pad_t + i * row_h
            cy = y + row_h / 2
            self.create_text(label_w - 10, cy, text=str(r["label"])[:11],
                             fill=TEXT_PRIMARY, font=font(SIZE_SMALL, bold=True),
                             anchor="e")

            x0 = label_w + max(0, (r["start"] - dmin).days) / total_days * cw
            x1 = label_w + min(total_days, (r["end"] - dmin).days) / total_days * cw
            bw = max(12, x1 - x0)

            self.create_rectangle(x0, cy - 9, x0 + bw, cy + 9,
                                  fill=r.get("color", PRIMARY), outline="")
            if bw > 46:
                self.create_text(x0 + 7, cy, text=str(r["label"])[:10],
                                 fill="#FFFFFF", font=font(SIZE_TINY), anchor="w")

            # 风险标记
            if r.get("badge"):
                self.create_oval(x0 + bw + 4, cy - 6, x0 + bw + 16, cy + 6,
                                 fill=PRIMARY, outline="")
                self.create_text(x0 + bw + 10, cy, text="!",
                                 fill="#FFFFFF", font=(None, 9, "bold"))

        # 起止日期
        self.create_text(label_w, pad_t + ch + 12, text=dmin.strftime("%m/%d"),
                         fill=TEXT_TERTIARY, font=font(SIZE_TINY), anchor="w")
        self.create_text(label_w + cw, pad_t + ch + 12, text=dmax.strftime("%m/%d"),
                         fill=TEXT_TERTIARY, font=font(SIZE_TINY), anchor="e")


class ProgressBar(tk.Canvas):
    """细进度条，宽度自适应。"""

    def __init__(self, parent, height=6, color=PRIMARY, track=BG_APP, **kw):
        super().__init__(parent, height=height, bg=BG_CARD,
                         highlightthickness=0, bd=0, **kw)
        self._h = height
        self._color = color
        self._track = track
        self._pct = 0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, pct, color=None):
        self._pct = max(0, min(100, pct))
        if color:
            self._color = color
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        self.create_rectangle(0, 0, w, self._h, fill=self._track, outline="")
        fw = max(0, w * self._pct / 100)
        if fw >= 1:
            self.create_rectangle(0, 0, fw, self._h, fill=self._color, outline="")


def _fmt_axis(v):
    """坐标轴数字缩写，避免标签过长挤压绘图区。"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    a = abs(v)
    if a >= 100_000_000:
        return f"{v/100_000_000:.1f}亿"
    if a >= 10_000:
        return f"{v/10_000:.1f}万"
    if a >= 1000:
        return f"{v/1000:.1f}k"
    if a >= 10:
        return f"{v:.0f}"
    if a >= 1:
        return f"{v:.1f}"
    return f"{v:.2f}"
