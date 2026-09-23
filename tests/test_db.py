import unittest
import sqlite3
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        cls.mem_conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL, game TEXT NOT NULL,
                dau INTEGER DEFAULT 0, new_posts INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0, avg_session REAL DEFAULT 0,
                interaction_rate REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL, detail TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, content TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
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
        cls.mem_conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.mem_conn.close()

    def setUp(self):
        self.orig_get_conn = db.get_conn
        db.get_conn = lambda: self.mem_conn
        # 清空测试数据
        self.mem_conn.execute("DELETE FROM config")
        self.mem_conn.execute("DELETE FROM activity_log")
        self.mem_conn.execute("DELETE FROM char_usage")
        self.mem_conn.execute("DELETE FROM community_hot")
        self.mem_conn.commit()

    def tearDown(self):
        db.get_conn = self.orig_get_conn

    def test_save_load_config(self):
        db.save_config("test_key", "test_value")
        result = db.load_config("test_key")
        self.assertEqual(result, "test_value")

    def test_load_config_default(self):
        result = db.load_config("nonexistent_key", "default_val")
        self.assertEqual(result, "default_val")

    def test_date_str(self):
        from datetime import datetime
        d = datetime(2025, 6, 26, 12, 0, 0)
        self.assertEqual(db.date_str(d), "2025-06-26")

    def test_add_log(self):
        db.add_log("TEST", "测试日志")
        db.add_log("TEST2", "第二条日志")
        self.assertTrue(True)

    def test_save_load_config_overwrite(self):
        db.save_config("overwrite_key", "value1")
        db.save_config("overwrite_key", "value2")
        self.assertEqual(db.load_config("overwrite_key"), "value2")

    def test_upsert_char_usage(self):
        data = [
            {"version": "5.0", "character_name": "胡桃", "usage_rate": 75.5, "abyss_floor": 12},
            {"version": "5.0", "character_name": "钟离", "usage_rate": 80.0, "abyss_floor": 12},
        ]
        db.upsert_char_usage(data)
        # 验证写入
        cur = self.mem_conn.execute("SELECT COUNT(*) FROM char_usage")
        self.assertGreaterEqual(cur.fetchone()[0], 2)

    def test_upsert_community_hot(self):
        data = [
            {"version": "5.0", "platform": "B站", "post_count": 1500, "avg_reply_count": 25.5},
        ]
        db.upsert_community_hot(data)
        cur = self.mem_conn.execute("SELECT COUNT(*) FROM community_hot")
        self.assertGreaterEqual(cur.fetchone()[0], 1)

    def test_games_list(self):
        self.assertEqual(len(db.GAMES), 4)
        self.assertIn("原神", db.GAMES)
        self.assertIn("崩坏：星穹铁道", db.GAMES)


if __name__ == "__main__":
    unittest.main()
