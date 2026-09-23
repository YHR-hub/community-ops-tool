"""
数据层 —— 米游社运营助手 v3.1
==============================

相比旧版 db.py 的改动：
  1. 加索引。旧版 11 张表零索引，却在 README 里把「无索引稳定运行」当卖点 ——
     这在面试场合是减分项。正确做法是按查询路径建索引。
  2. 启用 WAL + busy_timeout。旧版每次 connect 都是默认 journal 模式，
     并发读写容易 database is locked。
  3. 裸 except 全部收窄，关键路径的失败必须可见（记日志 + 可抛）。
  4. 提供 query / execute 便捷函数，避免每处手写 with get_conn()。
  5. 业务查询收敛到数据层，视图里不再散落 SQL。
"""

import sqlite3
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

def _db_path():
    """
    数据库落点。

    PyInstaller onefile 运行时 __file__ 指向临时解包目录（%TEMP%/_MEIxxxx），
    每次启动重建、退出清空 —— 数据库若跟着 __file__ 走，用户录的数据
    重启就没了。frozen 模式下必须落到 exe 旁边（持久、可写）。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data" / "ops_data.db"
    return Path(__file__).parent / "data" / "ops_data.db"


DB_PATH = _db_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

GAMES = ["原神", "崩坏：星穹铁道", "绝区零", "崩坏3"]

# 状态枚举统一在此定义，避免各处硬编码中英文对照
VERSION_STATUS_KEYS = ["planning", "preparing", "live", "review", "closed"]
TASK_STATUS_KEYS = ["pending", "doing", "done"]
RISK_LEVEL_KEYS = ["high", "medium", "low"]

# 兼容旧代码
STATUS_OPTS = ["规划中", "准备中", "已上线", "复盘", "已关闭"]


# ═══════════════════════════════════════════════════════════
#  连接管理
# ═══════════════════════════════════════════════════════════
def get_conn():
    """
    创建连接并应用统一 PRAGMA。
    WAL 让读不阻塞写；busy_timeout 让偶发锁等待自动重试而非直接抛错。
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # v4.3：打开外键约束（SQLite 默认关闭）。删版本时子表级联清理，
    # 不留孤儿数据。旧库的表没有 FK 定义，此 PRAGMA 对其无副作用。
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# v4.3：读失败要「看得见」。
# 旧实现出错时返回 [] / None，和「查到 0 行」长得一模一样 ——
# 查询报错时界面显示的是「暂无数据」空态，排障方向直接被带偏。
# （db.py 顶部注释批判过「写入失败假成功」，读路径上的同类问题一直没堵。）
# 返回类型保持不变（避免动到 81 项测试的既有断言），
# 改为把最后一次读错误存快照，供日志与自检读取。
_LAST_READ_ERROR = None


def last_error():
    """返回最近一次读失败的快照 dict（sql/err/at），无失败返回 None。"""
    return _LAST_READ_ERROR


def query(sql, params=(), one=False):
    """只读查询封装。失败时返回空结果，但错误会落日志 + 存快照。"""
    global _LAST_READ_ERROR
    try:
        with get_conn() as c:
            cur = c.execute(sql, params)
            rows = cur.fetchone() if one else cur.fetchall()
        _LAST_READ_ERROR = None      # 这次读成功了，清掉上一次的失败痕迹
        return rows
    except sqlite3.Error as e:
        _log_db_error("query", sql, e)
        import datetime
        _LAST_READ_ERROR = {
            "sql": sql[:200],
            "err": str(e),
            "at": datetime.datetime.now().strftime("%m-%d %H:%M:%S"),
        }
        from logger_setup import get_logger
        get_logger().error("读失败(伪装成空结果风险) sql=%s err=%s", sql[:120], e)
        return None if one else []


def execute(sql, params=()):
    """
    写入封装，返回 lastrowid。
    写入失败会抛出异常 —— 旧版大量 `except: pass` 让用户以为保存成功了，
    这是最坑的一类 bug。
    """
    with get_conn() as c:
        cur = c.execute(sql, params)
        return cur.lastrowid


def _log_db_error(op, sql, err):
    """把数据库错误打到 stderr，便于排查。"""
    print(f"[db:{op}] {err}\n  SQL: {' '.join(str(sql).split())[:160]}", file=sys.stderr)
    traceback.print_exc(limit=2)


# ═══════════════════════════════════════════════════════════
#  建表与迁移
# ═══════════════════════════════════════════════════════════
SCHEMA = """
CREATE TABLE IF NOT EXISTS versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game        TEXT NOT NULL,
    version     TEXT NOT NULL,
    start_date  TEXT NOT NULL,
    end_date    TEXT,
    status      TEXT DEFAULT 'planning',
    highlights  TEXT DEFAULT '',
    notes       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT NOT NULL,
    game             TEXT NOT NULL,
    dau              INTEGER DEFAULT 0,
    new_posts        INTEGER DEFAULT 0,
    comments         INTEGER DEFAULT 0,
    avg_session      REAL DEFAULT 0,
    interaction_rate REAL DEFAULT 0,
    -- v4.1 留存：汇总口径（从 BI 导出的当日留存率，非用户级追踪）。
    -- 单位 %，范围 [0,100]；0 表示「当天没算/没填」，绘制与统计时要过滤。
    new_users        INTEGER DEFAULT 0,
    retention_1      REAL DEFAULT 0,
    retention_7      REAL DEFAULT 0,
    retention_30     REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    game       TEXT NOT NULL,
    type       TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    notes      TEXT DEFAULT '',
    version_id INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS checklists (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER REFERENCES versions(id) ON DELETE CASCADE,
    task       TEXT NOT NULL,
    category   TEXT DEFAULT '常规',
    assignee   TEXT DEFAULT '',
    deadline   TEXT,
    status     TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    type       TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT NOT NULL,
    detail     TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS budgets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    category   TEXT NOT NULL,
    item_name  TEXT NOT NULL,
    planned    REAL DEFAULT 0,
    actual     REAL DEFAULT 0,
    notes      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS risks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id  INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    probability TEXT DEFAULT 'medium',
    impact      TEXT DEFAULT 'medium',
    mitigation  TEXT DEFAULT '',
    contingency TEXT DEFAULT '',
    owner       TEXT DEFAULT '',
    status      TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS char_usage (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    version        TEXT NOT NULL,
    character_name TEXT NOT NULL,
    usage_rate     REAL,
    abyss_floor    INTEGER,
    update_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(version, character_name)
);

CREATE TABLE IF NOT EXISTS community_hot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version         TEXT NOT NULL,
    platform        TEXT NOT NULL,
    post_count      INTEGER,
    avg_reply_count REAL,
    update_time     TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(version, platform)
);

-- ═══ v4.5 行业情报（与「行业知识库」目录联动）═══
-- 把行业观察从 markdown 变成可查询的活数据：
-- 行业事件时间线 / 竞品流水对比 / 舆情案例卡 三张表。
CREATE TABLE IF NOT EXISTS industry_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '行业',   -- 版本/舆情/公司/竞品/政策
    title    TEXT NOT NULL,
    detail   TEXT DEFAULT '',
    impact   TEXT DEFAULT '',                -- 运营视角观察（一句话）
    source   TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS competitor_revenue (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    month   TEXT NOT NULL,                   -- 2026-08
    product TEXT NOT NULL,
    revenue REAL NOT NULL,                   -- 亿元（第三方估算口径）
    note    TEXT DEFAULT '',
    UNIQUE(month, product)
);

CREATE TABLE IF NOT EXISTS insight_cases (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    market    TEXT NOT NULL DEFAULT '全球',   -- 美/韩/日/中/全球
    framework TEXT DEFAULT '',               -- 分析框架/核心结论
    takeaway  TEXT DEFAULT '',               -- 可迁移的启示
    source    TEXT DEFAULT ''
);
"""

# 索引 —— 按实际查询路径设计，不是无脑加
INDEXES = [
    ("idx_metrics_date_game", "daily_metrics(date, game)"),
    ("idx_metrics_game", "daily_metrics(game)"),
    ("idx_versions_game", "versions(game)"),
    ("idx_versions_start", "versions(start_date)"),
    ("idx_events_start", "events(start_date)"),
    ("idx_events_version", "events(version_id)"),
    ("idx_checklists_version", "checklists(version_id)"),
    ("idx_checklists_status", "checklists(version_id, status)"),
    ("idx_budgets_version", "budgets(version_id)"),
    ("idx_risks_version", "risks(version_id)"),
    ("idx_char_usage_version", "char_usage(version)"),
    ("idx_community_version", "community_hot(version)"),
    ("idx_reports_created", "reports(created_at)"),
    ("idx_industry_date", "industry_events(date)"),
    ("idx_industry_cat", "industry_events(category)"),
    ("idx_comp_month", "competitor_revenue(month)"),
]

# 唯一约束 —— 必须单独建 UNIQUE INDEX，不能只写在 CREATE TABLE 里。
# 原因：CREATE TABLE IF NOT EXISTS 对已存在的表是空操作，
# 老库升级上来时表已经存在，写在建表语句里的 UNIQUE 永远不会生效，
# 于是 `INSERT ... ON CONFLICT(date, game)` 会直接报
# "ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint"。
# UNIQUE INDEX 用 IF NOT EXISTS 建，对老库新库都幂等。
UNIQUE_INDEXES = [
    ("ux_metrics_date_game", "daily_metrics(date, game)"),
    ("ux_versions_game_ver", "versions(game, version)"),
    ("ux_char_usage", "char_usage(version, character_name)"),
    ("ux_community", "community_hot(version, platform)"),
    ("ux_industry_event", "industry_events(date, title)"),
]

# 迁移：旧库缺的列，按 (表, 列, 定义) 声明
MIGRATIONS = [
    ("events", "version_id", "INTEGER DEFAULT 0"),
    ("checklists", "category", "TEXT DEFAULT '常规'"),
    ("versions", "notes", "TEXT DEFAULT ''"),
    # v4.1 留存字段 —— 老库补列后历史数据为 0，视为「未统计」，图表会自动跳过
    ("daily_metrics", "new_users", "INTEGER DEFAULT 0"),
    ("daily_metrics", "retention_1", "REAL DEFAULT 0"),
    ("daily_metrics", "retention_7", "REAL DEFAULT 0"),
    ("daily_metrics", "retention_30", "REAL DEFAULT 0"),
]


def init_db():
    """建表 + 建索引 + 迁移。幂等，可重复调用。"""
    with get_conn() as c:
        c.executescript(SCHEMA)
        for name, target in INDEXES:
            c.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")
        for name, target in UNIQUE_INDEXES:
            c.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {target}")

    # 迁移：先探测列是否存在再决定是否 ALTER。
    # 旧版用 try/except OperationalError 硬试，能用但会污染错误日志。
    for table, col, decl in MIGRATIONS:
        try:
            with get_conn() as c:
                existing = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
                if col not in existing:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        except sqlite3.Error as e:
            _log_db_error("migrate", f"{table}.{col}", e)


def dedupe_for_unique_indexes():
    """
    建立唯一索引前先清重。

    老库可能已经存在重复行（旧版没有唯一约束，重复录入会直接插入）。
    此时 CREATE UNIQUE INDEX 会失败，导致 upsert 后续全部报错。
    这里按「保留 id 最大的一条」清理，并在清理前打印被删条数。
    """
    rules = [
        ("daily_metrics", "date", "game"),
        ("versions", "game", "version"),
        ("char_usage", "version", "character_name"),
        ("community_hot", "version", "platform"),
    ]
    removed = {}
    for table, k1, k2 in rules:
        try:
            with get_conn() as c:
                before = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                c.execute(
                    f"DELETE FROM {table} WHERE id NOT IN "
                    f"(SELECT MAX(id) FROM {table} GROUP BY {k1}, {k2})")
                after = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if before != after:
                removed[table] = before - after
        except sqlite3.Error as e:
            _log_db_error("dedupe", table, e)
    return removed


def ensure_unique_indexes():
    """
    先清重、再建唯一索引。返回 (清理统计, 失败项)。
    单独抽出来是因为 init_db 在启动时会被调用，
    而清重是有破坏性的动作，需要显式调用才执行。
    """
    removed = dedupe_for_unique_indexes()
    failed = []
    for name, target in UNIQUE_INDEXES:
        try:
            with get_conn() as c:
                c.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {target}")
        except sqlite3.Error as e:
            _log_db_error("unique_index", name, e)
            failed.append(name)
    return removed, failed


def db_stats():
    """返回各表行数，供自检 / 设置页使用。"""
    out = {}
    for t in ("versions", "daily_metrics", "events", "checklists", "reports",
              "budgets", "risks", "char_usage", "community_hot", "activity_log",
              "industry_events", "competitor_revenue", "insight_cases"):
        try:
            row = query(f"SELECT COUNT(*) AS n FROM {t}", one=True)
            out[t] = row["n"] if row else 0
        except Exception:
            out[t] = -1
    return out


def index_report():
    """列出当前库里的索引，用于自检（验证索引确实建上了）。"""
    rows = query("SELECT name, tbl_name FROM sqlite_master "
                 "WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY tbl_name")
    return [(r["tbl_name"], r["name"]) for r in rows]


# ═══════════════════════════════════════════════════════════
#  配置读写
# ═══════════════════════════════════════════════════════════
def save_config(key, value):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))


def load_config(key, default=""):
    row = query("SELECT value FROM config WHERE key=?", (key,), one=True)
    return row["value"] if row else default


# ═══════════════════════════════════════════════════════════
#  操作日志
# ═══════════════════════════════════════════════════════════
LOG_KEEP = 200


def add_log(action, detail=""):
    """
    写操作日志并裁剪到最近 LOG_KEEP 条。
    这里只吞「日志本身失败」，不影响主流程，但会打印到 stderr。
    旧版吞掉所有异常，导致日志功能坏了也无人察觉。
    """
    try:
        with get_conn() as c:
            c.execute("INSERT INTO activity_log (action, detail) VALUES (?, ?)", (action, detail))
            c.execute(
                "DELETE FROM activity_log WHERE id NOT IN "
                "(SELECT id FROM activity_log ORDER BY id DESC LIMIT ?)", (LOG_KEEP,))
    except sqlite3.Error as e:
        print(f"[db:add_log] {e}", file=sys.stderr)


def recent_logs(limit=3):
    return query("SELECT action, detail, created_at FROM activity_log "
                 "ORDER BY id DESC LIMIT ?", (limit,))


# ═══════════════════════════════════════════════════════════
#  输入安全转换（旧版大量裸 int() 导致用户输错就崩）
# ═══════════════════════════════════════════════════════════
def safe_int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return default


def safe_float(v, default=0.0):
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return default


def valid_date(s):
    """严格校验 YYYY-MM-DD。"""
    if not s:
        return False
    try:
        datetime.strptime(str(s).strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def parse_date(s, fallback=None):
    """宽松日期解析，失败返回 fallback（默认今天）。"""
    if not s:
        return fallback or datetime.now()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
    return fallback or datetime.now()


def date_str(d=None):
    return (d or datetime.now()).strftime("%Y-%m-%d")


def days_ago(n):
    return datetime.now() - timedelta(days=n)


# ═══════════════════════════════════════════════════════════
#  业务查询（收敛到此，视图里不再散落 SQL）
# ═══════════════════════════════════════════════════════════
def get_versions(game=None, limit=None):
    sql = "SELECT * FROM versions"
    params = []
    if game and game != "全部":
        sql += " WHERE game=?"
        params.append(game)
    sql += " ORDER BY start_date DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return query(sql, params)


def get_version_by_id(vid):
    return query("SELECT * FROM versions WHERE id=?", (vid,), one=True)


def task_progress(vid):
    """一次查出总数与完成数。旧版在循环里反复开连接（N+1）。"""
    row = query(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done "
        "FROM checklists WHERE version_id=?", (vid,), one=True)
    if not row:
        return 0, 0
    return row["total"] or 0, row["done"] or 0


def task_progress_map():
    """一次性取回所有版本的进度，供列表页使用（消除 N+1 查询）。"""
    rows = query(
        "SELECT version_id, COUNT(*) AS total, "
        "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done "
        "FROM checklists GROUP BY version_id")
    return {r["version_id"]: (r["total"] or 0, r["done"] or 0) for r in rows}


def metrics_between(start, end, game=None):
    sql = "SELECT * FROM daily_metrics WHERE date>=? AND date<=?"
    params = [start, end]
    if game and game != "全部":
        sql += " AND game=?"
        params.append(game)
    sql += " ORDER BY date"
    return query(sql, params)


# 留存的「有效值」判定：迁移后老数据全是 0（= 未统计），
# 真实留存率也不可能恰好为 0，所以 0 一律当「没有这个数据点」处理。
# 否则曲线会在开头砸到 0 再跳回 45%，看起来像数据 bug。
def valid_retention(v):
    return v is not None and 0 < v <= 100


def retention_series(start, end, game=None):
    """
    留存日序列：[(date, new_users, r1, r7, r30), ...]，仅含有效留存值的行。

    口径说明（面试可讲）：
      这里存的是 BI 汇总口径的当日留存率（retention_1 = 当日新增用户次日回访比），
      不是用户级 Cohort 追踪 —— 运营工具通常拿不到用户级明细，
      但汇总口径足够支撑趋势判断与健康线对比。
    """
    sql = ("SELECT date, new_users, retention_1, retention_7, retention_30 "
           "FROM daily_metrics WHERE date>=? AND date<=?")
    params = [start, end]
    if game and game != "全部":
        sql += " AND game=?"
        params.append(game)
    sql += " ORDER BY date"
    rows = query(sql, params)
    return [dict(r) for r in rows
            if valid_retention(r["retention_1"])
            or valid_retention(r["retention_7"])
            or valid_retention(r["retention_30"])]


def retention_stats(start, end, game=None):
    """区间内留存均值（只统计有效值）。返回 dict：r1/r7/r30，无数据时为 None。"""
    rows = retention_series(start, end, game)
    out = {"r1": None, "r7": None, "r30": None}
    for key, col in (("r1", "retention_1"), ("r7", "retention_7"),
                     ("r30", "retention_30")):
        vals = [r[col] for r in rows if valid_retention(r[col])]
        out[key] = round(sum(vals) / len(vals), 1) if vals else None
    return out


# 异动判定阈值：|环比| 超过即视为异动。
# DAU/新增用百分比（量纲大），互动率用 pp（本身是比例）。
ANOMALY_RULES = [
    ("dau", "DAU", "pct", 10.0),
    ("new_users", "新增用户", "pct", 12.0),
    ("interaction_rate", "互动率", "pp", 0.5),
]

# 同环比确认比例：|同环比| / |环比| 达到该比例才算真异动。
# 低于它意味着「相对上周同日几乎没变」—— 是周期性低谷撞上 7 日均值基准。
ANOMALY_CONFIRM_RATIO = 0.5

# 连续确认：连续同向天数达到该值才算趋势（真异动是趋势，误报是孤立点）。
ANOMALY_STREAK_MIN = 2


def _mean_of(items, key):
    vals = [r[key] for r in items if r[key] is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _day_value(d, col, g):
    """某一天某指标的当日值（多游戏时取均值，与 anomaly_report 口径一致）。"""
    sql = "SELECT * FROM daily_metrics WHERE date=?"
    params = [str(d)]
    if g:
        sql += " AND game=?"
        params.append(g)
    rows = query(sql, params)
    vals = [r[col] for r in rows if r[col] is not None]
    return sum(vals) / len(vals) if vals else None


def _wow_check(d_last, col, mode, g, change):
    """
    同环比校验：最近数据日 vs 上周同一天（无数据顺延回退 1~2 天）。

    为什么需要：7 日均值只能对冲「周期性」，对冲不了节假日、版本活动
    这类非规则波动 —— 单日越线后隔天回落，多半是节律不是真异动。
    同环比把「周末对周末、活动日对活动日」的对照补上。

    判据是**幅度比例**而不是方向：
      · 若 |同环比| >= |环比| × CONFIRM_RATIO → 确认为真异动；
      · 若同环比幅度远小于环比 → 说明「相对上周同日几乎没变」，
        这次越线只是周期性低谷撞上了 7 日均值基准 → 疑似节律误报。
    举个反例说明为什么不能只看方向：单日 DAU 腰斩时，上周同日是正常值，
    方向当然与环比同向（都是跌），但那是真异动、不是节律 ——
    方向判断会把节律误报和真异动都判成「确认」，只有幅度比能分开。
    上周同日无数据时无法证伪，按「不降级」处理（漏报代价 > 误报代价）。
    """
    for back in (7, 8, 9):
        d = str(d_last - timedelta(days=back))
        wow = _day_value(d, col, g)
        cur = _day_value(str(d_last), col, g)
        if wow is None or cur is None or wow == 0:
            continue
        if mode == "pct":
            diff = (cur - wow) / wow * 100
            txt = f"{diff:+.1f}%"
        else:
            diff = cur - wow
            txt = f"{diff:+.2f}pp"
        confirmed = abs(diff) >= abs(change) * ANOMALY_CONFIRM_RATIO
        return txt, confirmed
    return "", True


def _streak_days(d_last, col, base_days, g, change):
    """
    连续确认：往回数连续多少天「当日 vs 该日前 base_days 日均值」与当日同向。

    真异动是趋势（连续多天同向），节律误报是孤立点（单日越线后回落）。
    streak>=2 说明不是单点噪声。最多回溯 5 天，够用且开销可控。
    """
    if not change:
        return 0
    sign = change > 0
    streak = 0
    for k in range(1, 6):
        d = d_last - timedelta(days=k)
        cur_d = _day_value(str(d), col, g)
        if cur_d is None:
            break
        base_rows = _rows_between(d - timedelta(days=base_days),
                                  d - timedelta(days=1), g)
        if not base_rows:
            break
        base_v = _mean_of(base_rows, col)
        if base_v == 0:
            break
        diff = (cur_d - base_v) / base_v * 100 if base_v else 0
        if (diff > 0) != sign:
            break
        streak += 1
    return streak


def _rows_between(start_d, end_d, g):
    sql = "SELECT * FROM daily_metrics WHERE date>=? AND date<=?"
    params = [str(start_d), str(end_d)]
    if g:
        sql += " AND game=?"
        params.append(g)
    return query(sql, params)


def _in_event_window(day, g=None):
    """
    活动日标记：最近数据日是否落在某个活动区间内。

    活动期内的波动是「预期内的波动」—— 版本活动、联动、前瞻预约都会
    抬升或扰动社区指标，此时越线不应直接等同真异动，标记为待人工复核。
    这里只做标记不改判定：把决定权留给运营，而不是用规则替他下结论。
    """
    sql = "SELECT * FROM events WHERE start_date<=? AND end_date>=?"
    params = [str(day), str(day)]
    if g:
        sql += " AND game=?"
        params.append(g)
    return bool(query(sql, params))


def anomaly_report(game=None, base_days=7):
    """
    异动检测：最近一个数据日 vs 之前 base_days 日均值。

    两个口径决定（面试可讲）：
      · 锚定「最近有数据的一天」而不是今天 —— 今天没录数时，
        按日历算环比会得到一堆 0，全是假异动；
      · 基准用 7 日均值而不是前一日 —— 单日环比的噪声太大，
        周三比周日跌 20% 多半是周内节律，不是异动。

    v4.3 补三个确认维度（不改变原有判定，只增加可解释性字段）：
      · 同环比校验 wow_change / confirmed：同向=真异动，反向=疑似节律；
      · 连续确认 streak：连续同向天数，>=2 说明是趋势而非单点噪声；
      · 活动日标记 special：活动期内波动，标记待人工复核。
    判定分三级 level：danger（已确认且 streak>=2）/ warn（已确认）
    / watch（未确认，仅观察）。

    返回 list[dict]：metric / cur / base / change（展示文字）/ down / note
    + wow_change / confirmed / streak / special / level。
    DAU 异动时 note 附按游戏拆分的贡献定位（多维拆解是归因的第一步）。
    """
    g = game if (game and game != "全部") else None
    row = query("SELECT MAX(date) AS d FROM daily_metrics", one=True)
    last = row["d"] if row else None
    if not last:
        return []

    d_last = datetime.strptime(last, "%Y-%m-%d").date()
    base_start = date_str(d_last - timedelta(days=base_days))

    sql = "SELECT * FROM daily_metrics WHERE date>=? AND date<=?"
    params = [base_start, last]
    if g:
        sql += " AND game=?"
        params.append(g)
    rows = query(sql, params)

    prev_rows = [r for r in rows if r["date"] < last]
    if not prev_rows:
        return []

    def mean_of(items, key):
        vals = [r[key] for r in items if r[key] is not None]
        return sum(vals) / len(vals) if vals else 0.0

    out = []
    for col, label, mode, threshold in ANOMALY_RULES:
        cur = mean_of([r for r in rows if r["date"] == last], col)
        base = mean_of(prev_rows, col)
        if base <= 0 and cur <= 0:
            continue
        if mode == "pct":
            change = (cur - base) / base * 100 if base else 0.0
            hit = abs(change) >= threshold and (base > 0 or cur > 0)
            change_txt = f"{change:+.1f}%"
        else:
            change = cur - base
            hit = abs(change) >= threshold
            change_txt = f"{change:+.2f}pp"
        if not hit:
            continue

        note = ""
        if col == "dau" and (not g) and len({r["game"] for r in rows}) > 1:
            # 多游戏场景：按游戏拆分环比，定位贡献最大的来源。
            # 这是异动归因的第一步 —— 先知道「谁贡献的」，再谈「为什么」。
            # 只统计「当日有数据」的游戏：今天没录数的游戏 cur=0，
            # 直接算会被误判成 -100% 拖累。
            games_today = {r["game"] for r in rows if r["date"] == last}
            parts = []
            for gm in games_today:
                gc = mean_of([r for r in rows
                              if r["date"] == last and r["game"] == gm], "dau")
                gb = mean_of([r for r in prev_rows
                              if r["game"] == gm], "dau")
                if gb <= 0:
                    continue
                gp = (gc - gb) / gb * 100
                if abs(gp) >= 5:
                    tag = "拖累" if gp < 0 else "带动"
                    parts.append(f"{gm}（{tag} {abs(gp):.0f}%）")
            if parts:
                note = "拆分：" + "、".join(parts[:2])

        # ── v4.3：同环比校验 + 连续确认 + 活动日标记 ──
        wow_change, confirmed = _wow_check(d_last, col, mode, g, change)
        streak = _streak_days(d_last, col, base_days, g, change)
        special = _in_event_window(last, g)

        if confirmed and streak >= 2:
            level = "danger"
        elif confirmed:
            level = "warn"
        else:
            level = "watch"

        if wow_change:
            tag = "同环比同向确认" if confirmed else "同环比反向，疑似节律波动"
            note += ("；" if note else "") + f"{tag}（周环比 {wow_change}）"
        if streak >= 2:
            note += f"；连续 {streak} 天同向"
        if special:
            note += "；活动期内，请人工复核节律"

        out.append({
            "metric": label,
            "cur": cur,
            "base": base,
            "change": change_txt,
            "down": change < 0,
            "note": note,
            "wow_change": wow_change,
            "confirmed": confirmed,
            "streak": streak,
            "special": special,
            "level": level,
        })
    return out


def latest_version(game=None):
    sql = "SELECT * FROM versions"
    params = []
    if game and game != "全部":
        sql += " WHERE game=?"
        params.append(game)
    sql += " ORDER BY start_date DESC LIMIT 1"
    return query(sql, params, one=True)


def previous_version(version_row):
    """
    取同一游戏时间轴上紧邻的上一个版本。

    为什么必须有这个函数：
      旧版直接在 `get_versions()` 的结果里用 index(当前版本) + 1 取上一个，
      但 get_versions() 是跨游戏按 start_date 全局排序的 ——
      库里有原神和星铁时，「星铁 3.6 的上一个版本」会被算成「原神 5.2」，
      于是角色使用率对比表 JOIN 出来 0 行，
      「自动标记风险」静默失效（先报"没有可比对数据"，实际是版本找错了）。
      正确做法是先按 game 过滤，再排序取相邻项。
    """
    if not version_row:
        return None
    game = version_row.get("game") if hasattr(version_row, "get") else version_row["game"]
    start = version_row.get("start_date") if hasattr(version_row, "get") else version_row["start_date"]

    row = query(
        "SELECT * FROM versions WHERE game=? AND start_date < ? "
        "ORDER BY start_date DESC LIMIT 1", (game, start), one=True)
    return row


def version_series(game):
    """同游戏版本列表，按时间倒序。用于对比、环比。"""
    return query("SELECT * FROM versions WHERE game=? ORDER BY start_date DESC",
                 (game,))


def top_characters(version, limit=5):
    return query(
        "SELECT character_name, usage_rate, abyss_floor FROM char_usage "
        "WHERE version=? ORDER BY usage_rate DESC LIMIT ?", (version, limit))


def community_summary(version):
    row = query(
        "SELECT COALESCE(SUM(post_count),0) AS posts, "
        "COALESCE(AVG(avg_reply_count),0) AS replies "
        "FROM community_hot WHERE version=?", (version,), one=True)
    return (row["posts"] if row else 0), (row["replies"] if row else 0)


def open_risks(version_id):
    return query(
        "SELECT * FROM risks WHERE version_id=? ORDER BY "
        "CASE probability WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id",
        (version_id,))


def budget_summary(version_id):
    row = query("SELECT COALESCE(SUM(planned),0) AS planned, "
                "COALESCE(SUM(actual),0) AS actual FROM budgets WHERE version_id=?",
                (version_id,), one=True)
    if not row:
        return 0.0, 0.0
    return row["planned"], row["actual"]


def upsert_char_usage(data):
    with get_conn() as c:
        for row in data:
            c.execute("""
                INSERT INTO char_usage (version, character_name, usage_rate, abyss_floor)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(version, character_name) DO UPDATE SET
                    usage_rate = excluded.usage_rate,
                    abyss_floor = excluded.abyss_floor,
                    update_time = datetime('now','localtime')
            """, (row["version"], row["character_name"],
                  row.get("usage_rate"), row.get("abyss_floor", 12)))


def upsert_community_hot(data):
    with get_conn() as c:
        for row in data:
            c.execute("""
                INSERT INTO community_hot (version, platform, post_count, avg_reply_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(version, platform) DO UPDATE SET
                    post_count = excluded.post_count,
                    avg_reply_count = excluded.avg_reply_count,
                    update_time = datetime('now','localtime')
            """, (row["version"], row["platform"],
                  row.get("post_count"), row.get("avg_reply_count")))


def global_search(q, limit=8):
    """
    全局搜索。
    旧版用 LIKE '%q%' 且未转义 % 和 _，用户搜一个 % 会全表命中。
    这里做转义，并保持前后缀通配（数据量小，够用）。
    """
    q = (q or "").strip()
    if not q:
        return []

    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{esc}%"
    results = []

    for r in query(
            "SELECT id, game, version, start_date, status FROM versions "
            "WHERE game LIKE ? ESCAPE '\\' OR version LIKE ? ESCAPE '\\' "
            "ORDER BY start_date DESC LIMIT ?", (like, like, limit)):
        results.append({
            "kind": "版本", "title": f"{r['game']} {r['version']}",
            "meta": f"{r['start_date']} · {r['status']}",
            "target": ("versions", r["id"]),
        })

    for r in query(
            "SELECT id, name, game, type, start_date FROM events "
            "WHERE name LIKE ? ESCAPE '\\' OR type LIKE ? ESCAPE '\\' "
            "ORDER BY start_date DESC LIMIT ?", (like, like, limit)):
        results.append({
            "kind": "活动", "title": r["name"],
            "meta": f"{r['game']} · {r['type']} · {r['start_date']}",
            "target": ("events", r["id"]),
        })

    for r in query(
            "SELECT id, title, type, created_at FROM reports "
            "WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\' "
            "ORDER BY created_at DESC LIMIT ?", (like, like, limit)):
        results.append({
            "kind": "报告", "title": r["title"],
            "meta": f"{r['type']} · {r['created_at']}",
            "target": ("reports", r["id"]),
        })

    return results
