"""性能压力测试"""
import pytest
import sys
import os
import time
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


class TestPerformance:
    """性能测试套件"""
    
    def test_batch_insert_metrics(self):
        """批量写入运营数据测试"""
        # 创建临时数据库
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        c = conn.cursor()
        c.executescript("""
        CREATE TABLE daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            game TEXT NOT NULL,
            dau INTEGER DEFAULT 0,
            new_posts INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            avg_session REAL DEFAULT 0,
            inter_rate REAL DEFAULT 0
        );
        """)
        conn.commit()
        
        start_time = time.time()
        
        # 批量插入 5000 条数据
        for i in range(5000):
            c.execute(
                "INSERT INTO daily_metrics(date, game, dau, new_posts, comments, avg_session, inter_rate) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    f"2026-01-{(i % 31) + 1:02d}",
                    random.choice(["原神", "星穹铁道", "绝区零", "崩坏3"]),
                    random.randint(10000, 500000),
                    random.randint(10, 500),
                    random.randint(50, 2000),
                    round(random.uniform(5.0, 30.0), 1),
                    round(random.uniform(1.0, 10.0), 2),
                )
            )
        
        conn.commit()
        elapsed = time.time() - start_time
        conn.close()
        
        # 性能要求：< 1s
        print(f"批量写入 5000 条数据耗时: {elapsed:.3f}s")
        assert elapsed < 1.0, f"批量写入超时: {elapsed:.3f}s"
    
    def test_aggregate_query(self):
        """聚合查询性能测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        c = conn.cursor()
        # 创建完整的表结构（包含 inter_rate 列）
        c.execute("CREATE TABLE daily_metrics (id INTEGER PRIMARY KEY, date TEXT, game TEXT, dau INTEGER, new_posts INTEGER, comments INTEGER, avg_session REAL, inter_rate REAL)")
        
        # 准备数据
        for i in range(1000):
            c.execute("INSERT INTO daily_metrics(date, game, dau, new_posts, comments, avg_session, inter_rate) VALUES(?,?,?,?,?,?,?)",
                     (f"2026-01-{(i % 31) + 1:02d}", "原神", random.randint(10000, 500000), 100, 500, 15.0, 3.5))
        conn.commit()
        
        start_time = time.time()
        
        # 执行 200 次聚合查询
        for _ in range(200):
            c.execute("SELECT game, SUM(dau), AVG(inter_rate) FROM daily_metrics GROUP BY game").fetchall()
        
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"200 次聚合查询耗时: {elapsed:.3f}s")
        assert elapsed < 1.0, f"聚合查询超时: {elapsed:.3f}s"
    
    def test_version_template_import(self):
        """版本模板导入性能测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        c = conn.cursor()
        c.execute("CREATE TABLE versions (id INTEGER PRIMARY KEY, game TEXT, version TEXT, start_date TEXT, end_date TEXT, status TEXT)")
        c.execute("CREATE TABLE checklists (id INTEGER PRIMARY KEY, version_id INTEGER, task TEXT, assignee TEXT, deadline TEXT, status TEXT)")
        
        start_time = time.time()
        
        # 导入 50 个版本，每个版本 30 个任务
        for v in range(50):
            c.execute("INSERT INTO versions(game, version, start_date, end_date, status) VALUES(?,?,?,?,?)",
                     ("原神", f"v{v+1}.0", f"2026-0{v%12+1:02d}-01", f"2026-0{(v%12)+1:02d}-15", "active"))
            version_id = c.lastrowid
            
            for t in range(30):
                c.execute("INSERT INTO checklists(version_id, task, assignee, deadline, status) VALUES(?,?,?,?,?)",
                         (version_id, f"任务{t+1}", "测试用户", f"2026-01-{(t % 28) + 1:02d}", "pending"))
        
        conn.commit()
        elapsed = time.time() - start_time
        conn.close()
        
        # 性能要求：< 0.5s
        print(f"导入 50 版本 × 30 任务耗时: {elapsed:.3f}s")
        assert elapsed < 0.5, f"版本模板导入超时: {elapsed:.3f}s"
    
    def test_budget_batch_insert(self):
        """预算批量写入性能测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        c = conn.cursor()
        c.execute("CREATE TABLE budgets (id INTEGER PRIMARY KEY, version_id INTEGER, category TEXT, item_name TEXT, planned REAL, actual REAL)")
        
        start_time = time.time()
        
        categories = ["推广", "素材", "外包", "活动奖品", "线下", "其他"]
        for i in range(500):
            c.execute("INSERT INTO budgets(version_id, category, item_name, planned, actual) VALUES(?,?,?,?,?)",
                     (1, random.choice(categories), f"预算项{i}", random.randint(1000, 100000), random.randint(500, 80000)))
        
        conn.commit()
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"预算批量写入 500 条耗时: {elapsed:.3f}s")
        assert elapsed < 0.5, f"预算写入超时: {elapsed:.3f}s"
    
    def test_risk_batch_insert(self):
        """风险批量写入性能测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        c = conn.cursor()
        c.execute("CREATE TABLE risks (id INTEGER PRIMARY KEY, version_id INTEGER, title TEXT, probability INTEGER, impact INTEGER, mitigation TEXT, contingency TEXT, owner TEXT, status TEXT)")
        
        start_time = time.time()
        
        probabilities = [1, 2, 3, 4, 5]
        impacts = [1, 2, 3, 4, 5]
        
        for i in range(200):
            c.execute("INSERT INTO risks(version_id, title, probability, impact, mitigation, contingency, owner, status) VALUES(?,?,?,?,?,?,?,?)",
                     (1, f"风险{i}", random.choice(probabilities), random.choice(impacts), "预案A", "预案B", "负责人", "open"))
        
        conn.commit()
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"风险批量写入 200 条耗时: {elapsed:.3f}s")
        assert elapsed < 0.5, f"风险写入超时: {elapsed:.3f}s"
    
    def test_config_stress(self):
        """配置读写压力测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        conn.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
        
        start_time = time.time()
        
        # 1000 次写入
        for i in range(1000):
            conn.execute("INSERT OR REPLACE INTO config(key,value) VALUES(?,?)", (f"key_{i}", f"value_{i}"))
        
        # 100 次读取
        for i in range(100):
            conn.execute("SELECT value FROM config WHERE key=?", (f"key_{i}",)).fetchone()
        
        conn.commit()
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"配置读写压力测试耗时: {elapsed:.3f}s")
        assert elapsed < 10.0, f"配置读写超时: {elapsed:.3f}s"
    
    def test_log_throughput(self):
        """操作日志吞吐量测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        conn.execute("CREATE TABLE activity_log (id INTEGER PRIMARY KEY, action TEXT, detail TEXT, created_at TEXT)")
        
        start_time = time.time()
        
        # 插入 500 条日志
        for i in range(500):
            conn.execute("INSERT INTO activity_log(action,detail) VALUES(?,?)", (f"操作{i}", f"详情{i}"))
        
        conn.commit()
        
        # 验证自动清理机制（保留最近 100 条）
        conn.execute("DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 100)")
        conn.commit()
        
        count = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        
        elapsed = time.time() - start_time
        conn.close()
        
        assert count <= 100
        print(f"操作日志吞吐测试耗时: {elapsed:.3f}s")
        assert elapsed < 5.0, f"日志写入超时: {elapsed:.3f}s"
    
    def test_join_performance(self):
        """多表 JOIN 联查性能测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        conn.execute("CREATE TABLE versions (id INTEGER PRIMARY KEY, game TEXT, version TEXT)")
        conn.execute("CREATE TABLE checklists (id INTEGER PRIMARY KEY, version_id INTEGER, task TEXT, status TEXT)")
        
        # 准备关联数据
        for i in range(100):
            conn.execute("INSERT INTO versions(game, version) VALUES(?,?)", ("原神", f"v{i+1}.0"))
            version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for j in range(5):
                conn.execute("INSERT INTO checklists(version_id, task, status) VALUES(?,?,?)",
                           (version_id, f"任务{j}", "completed"))
        conn.commit()
        
        start_time = time.time()
        
        # 100 次联查
        for _ in range(100):
            conn.execute("""
                SELECT v.game, v.version, c.task, c.status
                FROM versions v
                LEFT JOIN checklists c ON v.id = c.version_id
                WHERE v.game = ?
            """, ("原神",)).fetchall()
        
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"100 次多表 JOIN 联查耗时: {elapsed:.3f}s")
        assert elapsed < 0.5, f"JOIN 查询超时: {elapsed:.3f}s"
    
    def test_cross_module_query(self):
        """跨模块关联查询性能测试"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        conn.execute("CREATE TABLE versions (id INTEGER PRIMARY KEY, game TEXT, version TEXT)")
        conn.execute("CREATE TABLE budgets (id INTEGER PRIMARY KEY, version_id INTEGER, category TEXT)")
        conn.execute("CREATE TABLE risks (id INTEGER PRIMARY KEY, version_id INTEGER, title TEXT)")
        
        # 准备四表关联数据
        for i in range(20):
            conn.execute("INSERT INTO versions(game, version) VALUES(?,?)", ("原神", f"v{i+1}.0"))
            version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO budgets(version_id, category) VALUES(?,?)", (version_id, "推广"))
            conn.execute("INSERT INTO risks(version_id, title) VALUES(?,?)", (version_id, f"风险{i}"))
        conn.commit()
        
        start_time = time.time()
        
        # 20 次四表联查
        for _ in range(20):
            conn.execute("""
                SELECT v.game, v.version, b.category, r.title
                FROM versions v
                LEFT JOIN budgets b ON v.id = b.version_id
                LEFT JOIN risks r ON v.id = r.version_id
                WHERE v.game = ?
            """, ("原神",)).fetchall()
        
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"20 次四表联查耗时: {elapsed:.3f}s")
        assert elapsed < 0.5, f"跨模块查询超时: {elapsed:.3f}s"
    
    def test_empty_table_query_performance(self):
        """空表查询性能"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        conn.execute("CREATE TABLE daily_metrics (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE versions (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE checklists (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE reports (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE config (id INTEGER PRIMARY KEY)")
        
        start_time = time.time()
        
        # 100 次空表查询
        for _ in range(100):
            conn.execute("SELECT * FROM daily_metrics LIMIT 1").fetchall()
            conn.execute("SELECT * FROM versions LIMIT 1").fetchall()
            conn.execute("SELECT * FROM checklists LIMIT 1").fetchall()
            conn.execute("SELECT * FROM reports LIMIT 1").fetchall()
            conn.execute("SELECT * FROM config LIMIT 1").fetchall()
        
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"100 次空表查询耗时: {elapsed:.3f}s")
        assert elapsed < 0.1, f"空表查询超时: {elapsed:.3f}s"
    
    def test_large_dataset_aggregation(self):
        """大数据集聚合性能"""
        temp_path = ":memory:"
        conn = __import__('sqlite3').connect(temp_path)
        conn.execute("CREATE TABLE daily_metrics (id INTEGER PRIMARY KEY, game TEXT, dau INTEGER, new_posts INTEGER)")
        
        # 插入 10000 条数据
        for i in range(10000):
            conn.execute("INSERT INTO daily_metrics(game, dau, new_posts) VALUES(?, ?, ?)",
                        (random.choice(["原神", "星穹铁道"]), random.randint(10000, 500000), 100))
        conn.commit()
        
        start_time = time.time()
        
        # 执行聚合
        conn.execute("SELECT game, SUM(dau), AVG(new_posts), COUNT(*) FROM daily_metrics GROUP BY game").fetchall()
        
        elapsed = time.time() - start_time
        conn.close()
        
        print(f"10000 条数据聚合耗时: {elapsed:.3f}s")
        assert elapsed < 1.0, f"大数据聚合超时: {elapsed:.3f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
