import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "ops_data.db"
DB_PATH.parent.mkdir(exist_ok=True)

GAMES = ["原神", "崩坏：星穹铁道", "绝区零", "崩坏3"]
STATUS_OPTS = ["规划中", "准备中", "已上线", "复盘", "已关闭"]


def get_conn():
    return sqlite3.connect(str(DB_PATH))


def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL, game TEXT NOT NULL,
            dau INTEGER DEFAULT 0, new_posts INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0, avg_session REAL DEFAULT 0,
            interaction_rate REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, game TEXT NOT NULL,
            type TEXT NOT NULL, start_date TEXT NOT NULL,
            end_date TEXT NOT NULL, notes TEXT DEFAULT '',
            version_id INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL, version TEXT NOT NULL,
            start_date TEXT NOT NULL, end_date TEXT,
            status TEXT DEFAULT 'planning', highlights TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER, task TEXT NOT NULL,
            assignee TEXT DEFAULT '', deadline TEXT,
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT NOT NULL,
            type TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL, detail TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            item_name TEXT NOT NULL,
            planned REAL DEFAULT 0,
            actual REAL DEFAULT 0,
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            probability TEXT DEFAULT 'medium',
            impact TEXT DEFAULT 'medium',
            mitigation TEXT DEFAULT '',
            contingency TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            status TEXT DEFAULT 'open'
        );
        CREATE TABLE IF NOT EXISTS char_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            character_name TEXT NOT NULL,
            usage_rate REAL,
            abyss_floor INTEGER,
            update_time TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(version, character_name)
        );
        CREATE TABLE IF NOT EXISTS community_hot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            platform TEXT NOT NULL,
            post_count INTEGER,
            avg_reply_count REAL,
            update_time TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(version, platform)
        );
        """)
    # 迁移
    try:
        with get_conn() as c:
            c.execute("ALTER TABLE events ADD COLUMN version_id INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass


def save_config(key, value):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    logger.debug(f"save_config: {key}")


def load_config(key, default=""):
    with get_conn() as c:
        r = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return r[0] if r else default


def add_log(action, detail=""):
    try:
        with get_conn() as c:
            c.execute("INSERT INTO activity_log (action,detail) VALUES (?,?)", (action, detail))
            c.execute("DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 100)")
        logger.info(f"操作: {action} - {detail}")
    except:
        logger.exception("add_log 异常")


def date_str(d):
    return d.strftime("%Y-%m-%d")


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
            """, (row["version"], row["character_name"], row["usage_rate"], row["abyss_floor"]))


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
            """, (row["version"], row["platform"], row["post_count"], row["avg_reply_count"]))