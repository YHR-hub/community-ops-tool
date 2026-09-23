# 米游社运营助手 · 单元测试套件

## 测试架构

本项目使用 pytest 框架进行单元测试，测试覆盖三个维度：

| 测试层级 | 测试文件 | 覆盖范围 |
|----------|----------|----------|
| 数据库层 | test_db.py | 建表、CRUD、配置持久化、操作日志 |
| 视图层 | test_views.py | 视图方法可用性、UI 组件初始化 |
| 性能层 | test_performance.py | 批量写入、聚合查询、压力测试 |

## 运行测试

```bash
# 安装测试依赖
pip install pytest

# 运行全部测试
pytest tests/ -v

# 运行指定测试文件
pytest tests/test_db.py -v
pytest tests/test_views.py -v
pytest tests/test_performance.py -v

# 带覆盖率报告
pytest tests/ --cov=. --cov-report=html
```

## 测试配置

项目根目录的 `pytest.ini` 配置文件：

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

## 测试用例清单

### test_db.py（数据库层测试）

| 测试用例 | 描述 | 验证点 |
|----------|------|--------|
| test_create_tables | 数据库建表 | 9 张表存在 |
| test_daily_metrics_crud | 日常指标 CRUD | 增删改查正常 |
| test_versions_crud | 版本管理 CRUD | 增删改查正常 |
| test_checklists_crud | 清单任务 CRUD | 增删改查正常 |
| test_reports_crud | 报告管理 CRUD | 增删改查正常 |
| test_config_persistence | 配置持久化 | KV 读写正确 |
| test_activity_log | 操作日志 | 上限 100 自动清理 |
| test_budgets_crud | 预算管理 CRUD | 增删改查正常 |
| test_risks_crud | 风险管理 CRUD | 增删改查正常 |
| test_events_crud | 活动管理 CRUD | 增删改查正常 |
| test_multi_table_query | 多表联查 | JOIN 查询正确 |
| test_empty_table_query | 空表查询 | 不崩溃 |

### test_views.py（视图层测试）

| 测试用例 | 描述 | 验证点 |
|----------|------|--------|
| test_dashboard_init | 数据看板初始化 | 组件创建成功 |
| test_ai_prompt_template | AI Prompt 模板 | 模板格式正确 |
| test_versions_init | 版本管理初始化 | 4 标签页存在 |
| test_report_generation | 报告生成 | Markdown 格式正确 |
| test_plans_init | 排期预算初始化 | 三合一标签页存在 |
| test_marketing_init | 内容工厂初始化 | 三平台选择正确 |
| test_social_trend_init | 趋势雷达初始化 | 热点列表加载 |
| test_settings_init | AI 设置初始化 | API Key 保存 |

### test_performance.py（性能层测试）

| 测试用例 | 描述 | 数据量 | 预期耗时 |
|----------|------|--------|----------|
| test_batch_insert_metrics | 批量写入运营数据 | 5,000 条 | < 1s |
| test_aggregate_query | 聚合查询 | 200 次 | < 1s |
| test_version_template_import | 版本模板导入 | 50 版 × 30 任务 | < 0.1s |
| test_budget_batch_insert | 预算批量写入 | 500 条 | < 0.1s |
| test_risk_batch_insert | 风险批量写入 | 200 条 | < 0.1s |
| test_config_stress | 配置读写压力 | 1,000 写 + 100 读 | < 10s |
| test_log_throughput | 操作日志吞吐 | 500 条 | < 5s |
| test_join_performance | 多表 JOIN 性能 | 100 次 | < 0.1s |
| test_boundary_values | 边界值测试 | - | 正常 |
| test_special_characters | 特殊字符测试 | - | 正确存储 |

## 覆盖率目标

- 数据库层：≥ 90%
- 视图层：≥ 80%
- 总体：≥ 85%
