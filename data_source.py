# -*- coding: utf-8 -*-
"""
数据源适配层 —— 把「数据从哪来」和「数据怎么用」分开
==================================================

为什么需要这一层：
  原来 CSV 解析、列名映射、逐行校验全写在 views/data.py 里，
  结果就是「只有 CSV 导入这一条路能用」——
  真实运营场景里，数据更多来自 BI 接口、数仓查询、飞书表格。
  把解析+校验抽成数据源，接入新来源就是加一个类，不动 UI、不动数据层。

三种来源，同一套口径：
  CsvSource   文件导入（Excel 导出的 GBK 也支持）
  ApiSource   HTTP JSON 接口（真实 BI / 数仓出口）
  ManualSource 表单录入（保持原有逐字段校验路径）

口径约定（与 db 层一致，不另立一套）：
  · 列名支持中文别名（"次留" ≡ retention_1），降低使用门槛；
  · 数值列非法值逐行报出行号与字段名，不静默丢弃；
  · 留存率上限 100%，0 值视为「未统计」原样保留（db 层再决定怎么过滤）。
"""
import csv
import json
import os
import re
import urllib.request
import urllib.error

# ── 列名别名（权威定义，views 层从这里引用，避免两处漂移）──
CSV_ALIASES = {
    "日期": "date", "date": "date",
    "游戏": "game", "game": "game",
    "dau": "dau", "活跃": "dau", "日活": "dau", "日活跃": "dau",
    "新增用户": "new_users", "new_users": "new_users", "新增": "new_users",
    "帖子": "new_posts", "new_posts": "new_posts", "新增帖子": "new_posts",
    "评论": "comments", "comments": "comments", "评论数": "comments",
    "时长": "avg_session", "avg_session": "avg_session", "平均时长": "avg_session",
    "互动率": "interaction_rate", "interaction_rate": "interaction_rate",
    "次日留存": "retention_1", "次留": "retention_1", "retention_1": "retention_1",
    "7日留存": "retention_7", "7留": "retention_7", "retention_7": "retention_7",
    "30日留存": "retention_30", "30留": "retention_30", "retention_30": "retention_30",
}

REQUIRED_COLS = ["date", "game"]
NUMERIC_COLS = ["dau", "new_users", "new_posts", "comments",
                "avg_session", "interaction_rate"]
RETENTION_COLS = ["retention_1", "retention_7", "retention_30"]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RowError(Exception):
    """单行数据错误，携带行号与字段名，供 UI 精确定位。"""


def parse_number(val, field, line_no):
    """数值解析：空值按 0，非法值报错（不静默吞掉）。"""
    if val is None or str(val).strip() == "":
        return 0
    s = str(val).strip().replace(",", "").replace("%", "")
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        raise RowError(f"第 {line_no} 行「{field}」不是数字：{val}")


def normalize_rows(raw_rows, default_game=None):
    """
    把任意来源的原始行归一化成 db 层可写入的记录。

    返回 (records, errors)：errors 是 (行号, 原因) 列表 ——
    部分行失败不拖垮整批，这点和「导入失败只提示一句话」的旧行为有本质区别。
    """
    records, errors = [], []
    for i, raw in enumerate(raw_rows, start=2):   # 第 1 行是表头
        try:
            rec = {}
            for raw_key, val in raw.items():
                if raw_key is None:
                    continue
                col = CSV_ALIASES.get(str(raw_key).strip().lower())
                if col:
                    rec[col] = val

            for need in REQUIRED_COLS:
                if not str(rec.get(need, "")).strip():
                    if need == "game" and default_game:
                        rec["game"] = default_game
                    else:
                        raise RowError(f"缺少必需列：{need}")

            date_v = str(rec.get("date", "")).strip()
            if not _DATE_RE.match(date_v):
                raise RowError(f"日期格式应为 YYYY-MM-DD：{date_v}")

            out = {"date": date_v, "game": str(rec.get("game", "")).strip()}
            for col in NUMERIC_COLS:
                out[col] = parse_number(rec.get(col), col, i)
            for col in RETENTION_COLS:
                if col in rec and str(rec[col]).strip() != "":
                    v = parse_number(rec[col], col, i)
                    if v < 0 or v > 100:
                        raise RowError(f"第 {i} 行「{col}」超出 0-100：{v}")
                    out[col] = v
            records.append(out)
        except RowError as e:
            errors.append((i, str(e)))
    return records, errors


class DataSource:
    """数据源基类：只约定「取数 + 归一化」，具体来源由子类实现。"""

    name = "base"

    def fetch(self):
        raise NotImplementedError

    def load(self, default_game=None):
        """取数 + 归一化，返回 (records, errors)。"""
        raw = self.fetch()
        return normalize_rows(raw, default_game=default_game)


class CsvSource(DataSource):
    """CSV 文件：依次尝试 utf-8-sig / utf-8 / gbk（国内 Excel 导出多为 GBK）。"""

    name = "csv"

    def __init__(self, path):
        self.path = path

    def fetch(self):
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                with open(self.path, newline="", encoding=enc) as f:
                    return list(csv.DictReader(f))
            except UnicodeDecodeError:
                continue
        raise RowError(f"无法识别文件编码：{os.path.basename(self.path)}")


class ApiSource(DataSource):
    """
    HTTP JSON 接口：GET 一个返回数组的 URL，字段走同一套别名映射。

    真实 BI 出口通常还要鉴权（header 带 token），所以 headers 对外开放；
    超时默认 15 秒 —— 和 AI 调用同理，桌面工具不能让用户在原地干等。
    """

    name = "api"

    def __init__(self, url, headers=None, timeout=15):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout

    def fetch(self):
        req = urllib.request.Request(self.url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RowError(f"接口请求失败：{e}")
        except json.JSONDecodeError as e:
            raise RowError(f"接口返回的不是合法 JSON：{e}")
        # 兼容两种常见返回：直接数组 / {"data": [...]}
        if isinstance(payload, dict):
            payload = payload.get("data", payload.get("rows", []))
        if not isinstance(payload, list):
            raise RowError("接口返回结构应为数组或 {data: [...]} 的字典")
        return payload


class ManualSource(DataSource):
    """表单录入：数据已在 UI 层校验过，这里只做统一的字段收口。"""

    name = "manual"

    def __init__(self, record):
        self.record = record

    def fetch(self):
        return [self.record]
