# -*- coding: utf-8 -*-
"""
文库页（v4.6）——Obsidian 式的 markdown 知识库浏览器。

为什么要这一页：行业知识库、内容系列、研究文档全是 markdown，
散在文件夹里时「知道有但找不到」。这一页把整个 vault 挂进工具：

  · 左侧文件树 —— 扫描 vault 下的 .md（排除备份/工具目录）
  · 右侧阅读   —— 基础排版渲染（标题/引用/代码/加粗）
  · [[双向链接]] —— 点击跳转；当前文件底部的「反向链接」列出谁引用了它
  · 全文搜索   —— 关键词 → 文件:行:片段，点击直达
  · vault 可切换 —— 想把整个「面试资料」挂进来也行

设计取舍（和 Obsidian 的差异，有意为之）：
  · 只读，不编辑 —— 编辑交给专业的（Obsidian/VSCode），工具负责「快速查」
  · 无图谱视图 —— 文件量级（<100）下图形谱收益低，索引信息用反链面板替代
"""
import os
import re
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

import components as C
from theme import (
    PRIMARY, WARNING, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BG_APP, BG_CARD, BG_ELEVATED, SP_XS, SP_SM, SP_MD, SIZE_TINY, SIZE_SMALL, SIZE_BODY, font,
)
from db import load_config, save_config

DEFAULT_VAULT = r"D:\面试资料\运营"

# 扫描时跳过的目录（备份/工具/缓存/构建产物）
EXCLUDE_DIRS = {
    "_tools", "_backup_20260921", "__pycache__", "node_modules", ".git",
    "运营助手", "运营助手_demo", "dist", "build", ".obsidian", ".idea",
}

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


class LibraryMixin:
    """由 App 混入，提供文库页。"""

    def show_library(self):
        self.clear_main()
        self._build_library()

    # ═══════════════════════════════════════════════════════
    def _build_library(self):
        body, _page = self.page_scaffold(
            "library", "文库",
            "Obsidian 式知识库浏览器 · 双链跳转 · 反向链接 · 全文搜索",
            icon="doc", refresh=self._build_library)

        self._vault = load_config("vault_path", DEFAULT_VAULT)
        self._vault_files = self._scan_vault()
        self._backlinks = self._build_backlink_index()
        self._current_file = None
        self._search_mode = False

        # ── 工具条 ──
        bar = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10)
        bar.pack(fill="x", pady=(0, SP_SM))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=SP_MD, pady=SP_SM)

        ctk.CTkLabel(inner, text="📁", font=font(SIZE_SMALL)).pack(side="left")
        self._vault_label = ctk.CTkLabel(
            inner, text=self._short_vault(), font=font(SIZE_TINY),
            text_color=TEXT_SECONDARY)
        self._vault_label.pack(side="left", padx=(4, SP_MD))
        C.GhostButton(inner, "更换目录", self._pick_vault,
                      width=88, height=28).pack(side="left")

        C.PrimaryButton(inner, "搜索", self._do_search,
                        width=70, height=28).pack(side="right")
        self.lib_search = ctk.CTkEntry(inner, placeholder_text="全文搜索（回车）",
                                       width=220, height=28, font=font(SIZE_SMALL))
        self.lib_search.pack(side="right", padx=(0, SP_SM))
        self.lib_search.bind("<Return>", lambda e: self._do_search())

        # ── 主体：左树 + 右阅读 ──
        main = ctk.CTkFrame(body, fg_color="transparent")
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=0, minsize=300)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # 左：文件树 / 搜索结果（同一位置切换）
        self._tree_box = ctk.CTkScrollableFrame(main, fg_color=BG_CARD,
                                                width=300, corner_radius=10)
        self._tree_box.grid(row=0, column=0, sticky="nsew", padx=(0, SP_SM))
        self._result_box = ctk.CTkScrollableFrame(main, fg_color=BG_CARD,
                                                  width=300, corner_radius=10)
        # result_box 初始不 grid（搜索时替换 tree_box）

        self._build_tree()

        # 右：阅读区
        right = ctk.CTkFrame(main, fg_color=BG_CARD, corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew")
        reader = ctk.CTkFrame(right, fg_color="transparent")
        reader.pack(fill="both", expand=True, padx=SP_SM, pady=SP_SM)

        self.lib_text = tk.Text(
            reader, bg=BG_APP, fg=TEXT_PRIMARY, wrap="word",
            relief="flat", padx=18, pady=14, insertbackground=PRIMARY,
            font=font(SIZE_BODY), spacing1=2, spacing3=4,
            highlightthickness=0)
        vsb = ctk.CTkScrollbar(reader, command=self.lib_text.yview)
        self.lib_text.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.lib_text.pack(side="left", fill="both", expand=True)
        self._setup_text_tags()

        # 底部状态栏 + 反向链接
        self.lib_status = ctk.CTkLabel(
            body, text=f"vault 共 {len(self._vault_files)} 个文件",
            font=font(SIZE_TINY), text_color=TEXT_TERTIARY, anchor="w")
        self.lib_status.pack(fill="x", pady=(SP_XS, 0))

        # 打开第一个文件（或提示）
        if self._vault_files:
            self._open_file(self._vault_files[0][0])
        else:
            self.lib_text.insert("1.0", "（vault 里没有找到 .md 文件——换个目录试试）")

    # ── 扫描与索引 ────────────────────────────────────────
    def _scan_vault(self):
        files = []
        root = self._vault
        if not os.path.isdir(root):
            return files
        for base, dirs, fnames in os.walk(root):
            dirs[:] = [d for d in dirs
                       if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for fn in fnames:
                if fn.endswith(".md"):
                    p = os.path.join(base, fn)
                    files.append((os.path.relpath(p, root), p))
        return sorted(files, key=lambda x: x[0].lower())

    def _build_backlink_index(self):
        """全库扫一遍 [[链接]]，建反向索引 {目标名: [引用它的文件]}。"""
        idx = {}
        for rel, p in self._vault_files:
            try:
                with open(p, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            for m in WIKILINK_RE.findall(content):
                target = m.split("|")[0].split("#")[0].strip()
                if target:
                    idx.setdefault(target, []).append(rel)
        return idx

    # ── 左栏：文件树 ──────────────────────────────────────
    def _build_tree(self):
        for w in self._tree_box.winfo_children():
            w.destroy()
        last_dir = None
        for rel, _p in self._vault_files:
            d = os.path.dirname(rel)
            if d and d != last_dir:
                ctk.CTkLabel(self._tree_box, text="  " + d,
                             font=font(SIZE_TINY, bold=True),
                             text_color=TEXT_TERTIARY, anchor="w",
                             height=20).pack(fill="x", pady=(SP_XS, 0))
                last_dir = d
            name = os.path.basename(rel)
            depth = rel.count(os.sep)
            btn = ctk.CTkButton(
                self._tree_box, text="  " * min(depth, 3) + "📄 " + name,
                font=font(SIZE_SMALL), anchor="w", height=26,
                fg_color="transparent", hover_color=BG_ELEVATED,
                text_color=TEXT_SECONDARY, corner_radius=6,
                command=lambda r=rel: self._open_file(r))
            btn.pack(fill="x", pady=1)

    def _pick_vault(self):
        path = filedialog.askdirectory(title="选择知识库目录（vault）")
        if not path:
            return
        save_config("vault_path", path)
        self._build_library()

    def _short_vault(self):
        v = self._vault
        return v if len(v) <= 42 else "…" + v[-40:]

    # ── 阅读区 ────────────────────────────────────────────
    def _setup_text_tags(self):
        t = self.lib_text
        t.tag_configure("h1", font=font(19, bold=True), spacing1=12,
                        spacing3=6, foreground=TEXT_PRIMARY)
        t.tag_configure("h2", font=font(15, bold=True), spacing1=10,
                        spacing3=4, foreground=TEXT_PRIMARY)
        t.tag_configure("h3", font=font(13, bold=True), spacing1=8,
                        spacing3=2)
        t.tag_configure("bold", font=font(SIZE_BODY, bold=True))
        t.tag_configure("quote", foreground=TEXT_SECONDARY,
                        lmargin1=16, lmargin2=16,
                        font=("Microsoft YaHei", SIZE_BODY, "italic"))
        t.tag_configure("code", font=("Consolas", SIZE_SMALL),
                        background="#0D0D1C", foreground="#8CD0A0",
                        lmargin1=16, lmargin2=16)
        t.tag_configure("meta", foreground=TEXT_TERTIARY,
                        font=font(SIZE_TINY))
        t.tag_configure("link", foreground=PRIMARY, underline=True)
        t.tag_configure("hr", foreground="#33335A")

    def _open_file(self, rel):
        path = None
        for r, p in self._vault_files:
            if r == rel:
                path = p
                break
        if path is None:
            return
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self.toast(f"读取失败：{e}", WARNING)
            return
        self._current_file = rel
        self._render(content)
        stem = os.path.splitext(os.path.basename(rel))[0]
        inflow = self._backlinks.get(stem, [])
        extra = f" · 被 {len(inflow)} 处引用" if inflow else ""
        self.lib_status.configure(
            text=f"{rel} · {len(content)} 字符{extra} · "
                 f"vault 共 {len(self._vault_files)} 个文件")

    def _render(self, content):
        t = self.lib_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        self._link_targets = {}
        self._link_seq = 0

        in_code = False
        for line in content.splitlines():
            if line.strip().startswith("```"):
                in_code = not in_code
                t.insert("end", line + "\n", ("code",))
                continue
            if in_code:
                t.insert("end", line + "\n", ("code",))
                continue
            if line.startswith("# "):
                t.insert("end", line[2:] + "\n", ("h1",))
            elif line.startswith("## "):
                t.insert("end", line[3:] + "\n", ("h2",))
            elif line.startswith("### "):
                t.insert("end", line[4:] + "\n", ("h3",))
            elif line.startswith("> "):
                t.insert("end", line[2:] + "\n", ("quote",))
            elif line.strip() == "---":
                t.insert("end", "─" * 40 + "\n", ("hr",))
            else:
                self._insert_inline(line + "\n", ())

        # 反向链接面板（附录在文末）
        stem = os.path.splitext(os.path.basename(self._current_file or ""))[0]
        inflow = [x for x in self._backlinks.get(stem, [])
                  if x != self._current_file]
        if inflow:
            t.insert("end", "\n" + "─" * 40 + "\n", ("hr",))
            t.insert("end", f"反向链接（{len(inflow)}）：\n", ("meta",))
            for src in inflow:
                self._insert_inline("  ← " + src + "\n", ("meta",))

        t.configure(state="disabled")

    def _insert_inline(self, text, base_tags):
        """处理行内 **加粗** 与 [[双链]]（链接高亮 + 可点击）。"""
        t = self.lib_text
        pos = 0
        pattern = re.compile(r"(\*\*.+?\*\*|\[\[[^\]]+\]\])")
        for m in pattern.finditer(text):
            if m.start() > pos:
                t.insert("end", text[pos:m.start()], base_tags)
            frag = m.group(0)
            if frag.startswith("**"):
                t.insert("end", frag[2:-2], tuple(base_tags) + ("bold",))
            else:  # [[链接]]
                name = frag[2:-2]
                display = name.split("|")[-1]
                # 每个链接一个唯一 tag（用自增序号，不用 id()——
                # 短字符串的 id 可能被复用，导致点击跳到别的链接）
                self._link_seq += 1
                tag = f"wl_{self._link_seq}"
                t.insert("end", display, tuple(base_tags) + ("link", tag))
                self._link_targets[tag] = name.split("|")[0].split("#")[0].strip()
                t.tag_bind(tag, "<Button-1>",
                           lambda e, tg=tag: self._open_wikilink(tg))
            pos = m.end()
        if pos < len(text):
            t.insert("end", text[pos:], base_tags)

    def _open_wikilink(self, tag):
        target = self._link_targets.get(tag)
        if not target:
            return
        for rel, _p in self._vault_files:
            stem = os.path.splitext(os.path.basename(rel))[0]
            if stem == target or rel == target or \
                    rel.replace("\\", "/").endswith(target + ".md"):
                self._open_file(rel)
                return
        self.toast(f"未找到链接目标：{target}（可能尚未创建）", WARNING)

    # ── 搜索 ──────────────────────────────────────────────
    def _do_search(self):
        kw = self.lib_search.get().strip()
        if not kw:
            return
        lower = kw.lower()
        results = []
        for rel, p in self._vault_files:
            try:
                with open(p, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if lower in line.lower():
                    results.append((rel, i, line.strip()[:70]))
        self._show_results(kw, results[:50])

    def _show_results(self, kw, results):
        self._tree_box.grid_remove()
        self._result_box.grid(row=0, column=0, sticky="nsew", padx=(0, SP_SM))
        for w in self._result_box.winfo_children():
            w.destroy()

        head = ctk.CTkFrame(self._result_box, fg_color="transparent")
        head.pack(fill="x", pady=(0, SP_SM))
        ctk.CTkLabel(head, text=f"「{kw}」· {len(results)} 条",
                     font=font(SIZE_SMALL, bold=True),
                     text_color=TEXT_PRIMARY).pack(side="left")
        C.GhostButton(head, "返回文件树", self._exit_search,
                      width=92, height=26).pack(side="right")

        if not results:
            ctk.CTkLabel(self._result_box, text="没有命中",
                         font=font(SIZE_TINY),
                         text_color=TEXT_TERTIARY).pack(pady=SP_MD)
            return
        for rel, line_no, frag in results:
            card = ctk.CTkButton(
                self._result_box, text=f"{rel} · L{line_no}\n{frag}",
                font=font(SIZE_TINY), anchor="w", height=44,
                fg_color="transparent", hover_color=BG_ELEVATED,
                text_color=TEXT_SECONDARY, corner_radius=6,
                command=lambda r=rel: self._open_file(r))
            card.pack(fill="x", pady=1)
        self.lib_status.configure(text=f"搜索「{kw}」命中 {len(results)} 条")

    def _exit_search(self):
        self._result_box.grid_remove()
        self._tree_box.grid(row=0, column=0, sticky="nsew", padx=(0, SP_SM))
