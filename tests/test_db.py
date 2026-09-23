"""数据库层单元测试"""
import pytest
import sqlite3
import os
import sys
import tempfile
import shutil

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_ops.db")
    
    # 修改 DB_PATH 指向临时数据库
    original_db_path = db.DB_PATH
    db.DB_PATH = db_path
    
    # 初始化数据库
    db.init_db()
    
    yield db_path
    
    # 恢复原始路径
    db.DB_PATH = original_db_path
    
    # 清理
    import time
    for _ in range(5):
        try:
            shutil.rmtree(temp_dir)
            break
        except PermissionError:
            time.sleep(0.2)


class TestDatabaseInit:
    """测试数据库初始化"""
    
    def test_create_tables(self, temp_db):
        """测试建表"""
        conn = sqlite3.connect(temp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()
        
        expected_tables = [
            'daily_metrics', 'events', 'versions', 'checklists',
            'reports', 'config', 'activity_log', 'budgets', 'risks', 'players'
        ]
        for table in expected_tables:
            assert table in table_names, f"缺少表: {table}"


class TestDailyMetrics:
    """测试日常指标 CRUD"""
    
    def test_insert_and_query(self, temp_db):
        """测试插入和查询"""
        conn = sqlite3.connect(temp_db)
        
        # 插入数据
        conn.execute(
            "INSERT INTO daily_metrics(date, game, dau, new_posts, comments, avg_session, inter_rate) "
            "VALUES(?,?,?,?,?,?,?)",
            ("2026-01-01", "原神", 100000, 50, 200, 15.5, 3.2)
        )
        conn.commit()
        
        # 查询数据 - 使用列名而不是位置索引
        row = conn.execute(
            "SELECT * FROM daily_metrics WHERE date=?", ("2026-01-01",)
        ).fetchone()
        assert row is not None
        assert row[2] == "原神"      # game 是第3列(id=0, date=1, game=2)
        assert row[3] == 100000     # dau 是第4列
        conn.close()
    
    def test_empty_table_query(self, temp_db):
        """测试空表查询不崩溃"""
        conn = sqlite3.connect(temp_db)
        rows = conn.execute("SELECT * FROM daily_metrics LIMIT 1").fetchall()
        assert rows == []
        conn.close()
    
    def test_aggregate_empty(self, temp_db):
        """测试空表聚合返回 None"""
        conn = sqlite3.connect(temp_db)
        result = conn.execute(
            "SELECT AVG(dau) FROM daily_metrics"
        ).fetchone()
        assert result[0] is None
        conn.close()


class TestVersions:
    """测试版本管理 CRUD"""
    
    def test_insert_version(self, temp_db):
        """测试插入版本"""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO versions(game, version, start_date, end_date, status, highlights) "
            "VALUES(?,?,?,?,?,?)",
            ("原神", "4.0", "2026-01-01", "2026-02-01", "active", "新角色上线")
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM versions WHERE game=?", ("原神",)
        ).fetchone()
        assert row is not None
        assert row[2] == "4.0"       # version 是第3列(id=0, game=1, version=2)
        conn.close()
    
    def test_delete_version(self, temp_db):
        """测试删除版本"""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO versions(game, version, start_date, end_date, status) "
            "VALUES(?,?,?,?,?)",
            ("原神", "4.0", "2026-01-01", "2026-02-01", "active")
        )
        version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        conn.execute("DELETE FROM versions WHERE id=?", (version_id,))
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM versions WHERE id=?", (version_id,)
        ).fetchone()
        assert row is None
        conn.close()


class TestChecklists:
    """测试清单任务 CRUD"""
    
    def test_insert_task(self, temp_db):
        """测试插入任务"""
        conn = sqlite3.connect(temp_db)
        
        # 先插入版本
        conn.execute(
            "INSERT INTO versions(game, version, start_date, end_date, status) "
            "VALUES(?,?,?,?,?)",
            ("原神", "4.0", "2026-01-01", "2026-02-01", "active")
        )
        version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 插入任务
        conn.execute(
            "INSERT INTO checklists(version_id, task, assignee, deadline, status) "
            "VALUES(?,?,?,?,?)",
            (version_id, "发布PV", "张三", "2026-01-15", "pending")
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM checklists WHERE version_id=?", (version_id,)
        ).fetchone()
        assert row is not None
        assert row[2] == "发布PV"    # task 是第3列(id=0, version_id=1, task=2)
        conn.close()


class TestReports:
    """测试报告管理 CRUD"""
    
    def test_insert_report(self, temp_db):
        """测试插入报告"""
        conn = sqlite3.connect(temp_db)
        content = "# 运营周报\n\n测试内容"
        conn.execute(
            "INSERT INTO reports(title, content, type) VALUES(?,?,?)",
            ("运营周报-2026", content, "weekly")
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM reports WHERE type=?", ("weekly",)
        ).fetchone()
        assert row is not None
        assert "运营周报" in row[1]  # title 是第2列
        conn.close()


class TestConfig:
    """测试配置持久化"""
    
    def test_config_write_read(self, temp_db):
        """测试配置读写"""
        # 保存配置
        db.save_config("ai_api_key", "sk-test-key")
        db.save_config("ai_model", "deepseek-chat")
        
        # 读取配置
        api_key = db.load_config("ai_api_key", "")
        model = db.load_config("ai_model", "gpt-4")
        
        assert api_key == "sk-test-key"
        assert model == "deepseek-chat"
    
    def test_config_default_value(self, temp_db):
        """测试配置默认值"""
        # 读取不存在的配置，应返回默认值
        value = db.load_config("non_existent_key", "default")
        assert value == "default"


class TestActivityLog:
    """测试操作日志"""
    
    def test_log_insert(self, temp_db):
        """测试日志插入"""
        db.save_log("测试操作", "测试详情")
        
        conn = sqlite3.connect(temp_db)
        row = conn.execute(
            "SELECT * FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[1] == "测试操作"  # action 是第2列
        conn.close()
    
    def test_log_limit_cleanup(self, temp_db):
        """测试日志上限自动清理"""
        # 插入超过上限的日志
        for i in range(105):
            db.save_log(f"操作{i}", f"详情{i}")
        
        conn = sqlite3.connect(temp_db)
        count = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        assert count <= 100
        conn.close()


class TestBudgets:
    """测试预算管理 CRUD"""
    
    def test_insert_budget(self, temp_db):
        """测试插入预算项"""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO budgets(version_id, category, item_name, planned, actual) "
            "VALUES(?,?,?,?,?)",
            (1, "推广", "广告投放", 50000, 45000)
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM budgets WHERE category=?", ("推广",)
        ).fetchone()
        assert row is not None
        assert row[3] == "广告投放"   # item_name 是第4列(id=0, version_id=1, category=2, item_name=3)
        conn.close()


class TestRisks:
    """测试风险管理 CRUD"""
    
    def test_insert_risk(self, temp_db):
        """测试插入风险项"""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO risks(version_id, title, probability, impact, mitigation, contingency, owner, status) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (1, "服务器宕机", 3, 4, "备用服务器", "紧急修复", "运维组", "open")
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM risks WHERE title=?", ("服务器宕机",)
        ).fetchone()
        assert row is not None
        conn.close()


class TestEvents:
    """测试活动管理 CRUD"""
    
    def test_insert_event(self, temp_db):
        """测试插入活动"""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO events(version_id, name, game, type, start_date, end_date) "
            "VALUES(?,?,?,?,?,?)",
            (1, "新春活动", "原神", "限时活动", "2026-01-20", "2026-02-20")
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM events WHERE name=?", ("新春活动",)
        ).fetchone()
        assert row is not None
        conn.close()


class TestMultiTableQuery:
    """测试多表联查"""
    
    def test_version_with_checklists(self, temp_db):
        """测试版本与任务联查"""
        conn = sqlite3.connect(temp_db)
        
        # 插入版本
        conn.execute(
            "INSERT INTO versions(game, version, start_date, end_date, status) "
            "VALUES(?,?,?,?,?)",
            ("原神", "4.0", "2026-01-01", "2026-02-01", "active")
        )
        version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 插入任务
        conn.execute(
            "INSERT INTO checklists(version_id, task, status) VALUES(?, ?, ?)",
            (version_id, "任务1", "completed")
        )
        conn.commit()
        
        # 联查
        rows = conn.execute("""
            SELECT v.game, v.version, c.task, c.status
            FROM versions v
            LEFT JOIN checklists c ON v.id = c.version_id
            WHERE v.game = ?
        """, ("原神",)).fetchall()
        
        assert len(rows) >= 1
        assert rows[0][0] == "原神"
        conn.close()


class TestBoundaryValues:
    """测试边界值"""
    
    def test_zero_dau(self, temp_db):
        """测试 DAU 为 0"""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO daily_metrics(date, game, dau, new_posts, comments) VALUES(?,?,?,?,?)",
            ("2026-01-01", "原神", 0, 0, 0)
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT dau FROM daily_metrics WHERE dau=0"
        ).fetchone()
        assert row[0] == 0
        conn.close()
    
    def test_max_dau(self, temp_db):
        """测试最大 DAU"""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO daily_metrics(date, game, dau, new_posts, comments) VALUES(?,?,?,?,?)",
            ("2026-01-01", "原神", 99999999, 1000000, 500000)
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT dau FROM daily_metrics WHERE dau=99999999"
        ).fetchone()
        assert row[0] == 99999999
        conn.close()
    
    def test_special_characters(self, temp_db):
        """测试特殊字符存储"""
        conn = sqlite3.connect(temp_db)
        content = "# 标题🎉\n\n> 引用\n\n| 表格 |\n|------|\n| 数据 |"
        conn.execute(
            "INSERT INTO reports(title, content, type) VALUES(?,?,?)",
            ("特殊字符测试", content, "weekly")
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT content FROM reports WHERE title=?", ("特殊字符测试",)
        ).fetchone()
        assert "🎉" in row[0]
        assert "表格" in row[0]
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
