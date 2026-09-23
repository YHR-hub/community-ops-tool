"""数据库层：建表、迁移、CRUD、配置持久化、操作日志"""
import sqlite3, os, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ops_data.db")

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            game TEXT NOT NULL,
            dau INTEGER DEFAULT 0,
            new_posts INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            avg_session REAL DEFAULT 0,
            inter_rate REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER DEFAULT 0,
            name TEXT NOT NULL,
            game TEXT,
            type TEXT,
            start_date TEXT,
            end_date TEXT
        );
        CREATE TABLE IF NOT EXISTS versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL,
            version TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'planning',
            highlights TEXT
        );
        CREATE TABLE IF NOT EXISTS checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER,
            task TEXT NOT NULL,
            assignee TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            type TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            detail TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER,
            category TEXT,
            item_name TEXT,
            planned REAL DEFAULT 0,
            actual REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER,
            title TEXT,
            probability INTEGER DEFAULT 1,
            impact INTEGER DEFAULT 1,
            mitigation TEXT,
            contingency TEXT,
            owner TEXT,
            status TEXT DEFAULT 'open'
        );
        """)
        # 玩家表（P0 留存/流失/分群）
        c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT UNIQUE NOT NULL,
            game TEXT,
            register_date TEXT NOT NULL,
            last_login TEXT NOT NULL,
            total_sessions INTEGER DEFAULT 1,
            avg_session REAL DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
        """)
        # 迁移：events.version_id
        try:
            c.execute("ALTER TABLE events ADD COLUMN version_id INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()

def save_config(key, value):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO config(key,value) VALUES(?,?)", (key, str(value)))

def load_config(key, default=None):
    with get_conn() as c:
        row = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

def save_log(action, detail=""):
    with get_conn() as c:
        c.execute("INSERT INTO activity_log(action,detail) VALUES(?,?)", (action, detail))
        c.execute("DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 100)")
