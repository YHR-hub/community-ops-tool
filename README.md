# 米游社运营助手 v3.0

面向米哈游 4 款游戏（原神、星穹铁道、绝区零、崩坏3）的**本地桌面端运营全流程管理工具**。

## 核心功能

| 模块 | 快捷键 | 能力 |
|------|:--:|------|
| 数据看板 | Ctrl+1 | 手动录入指标、DAU 折线图、双轴对比、**趋势预测（线性回归）** |
| AI 运营顾问 | Ctrl+2 | 7 种预设场景、DeepSeek API 对话、离线兜底、**词云分析** |
| 版本管理 | Ctrl+3 | 版本 CRUD、Checklist、甘特图、预算对比、**健康度评分**、风险矩阵 |
| 运营报告 | Ctrl+4 | 一键智能报告、AI 润色、**PDF 导出（封面+折线图+风险矩阵+雷达图）** |

其他亮点：自动风险检测、撤销/重做（Ctrl+Z/Y）、首次运行 5 步引导。

## 技术栈

| 层 | 技术 |
|---|---|
| 语言 | Python 3.11 |
| GUI | CustomTkinter（暗色主题，米哈游品牌色 `#ff4d6a`） |
| 存储 | SQLite（10 张表，纯本地离线） |
| AI | DeepSeek API（openai 兼容，10s 超时自动切离线兜底） |
| PDF/图表 | reportlab + matplotlib（雷达图、风险矩阵、折线图） |
| 词云 | jieba 分词 + wordcloud |
| 配置/日志 | YAML + logging（自动记录到 `logs/app.log`） |
| 分发 | PyInstaller 打包为独立 `.exe`（~100 MB，零依赖安装） |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 AI Key（可选，不影响离线功能）
#    编辑 config.yaml 中的 deepseek_api_key

# 3. 启动
python main.py
```

高级参数：

```bash
python main.py --config custom.yaml --log-level DEBUG
```

## 项目结构

```
米游社运营助手_独立版/
├── main.py                    # 入口（~290 行）
├── config.yaml                # YAML 配置中心
├── db.py                      # SQLite 数据层（~170 行）
├── fetch_data.py              # paimon.moe 角色数据抓取
├── theme.py                   # UI 主题常量
├── undo_manager.py            # 撤销/重做管理器
├── requirements.txt
├── run_tests.bat              # 一键运行测试
├── views/
│   ├── dashboard.py           # 数据看板（~570 行）
│   ├── ai.py                  # AI 顾问 + 词云（~360 行）
│   ├── versions.py            # 版本管理 + 健康分（~630 行）
│   ├── report.py              # 运营报告 + PDF 导出（~680 行）
│   ├── plans.py               # 排期/预算/风险（~455 行）
│   └── first_run.py           # 首次使用引导
├── tests/
│   ├── test_db.py             # 数据库单元测试（8 case）
│   └── test_fetch.py          # 数据抓取单元测试（4 case）
├── data/
│   └── ops_data.db            # SQLite 数据库
└── logs/
    └── app.log                # 运行日志
```

**15 个源文件，约 4200 行 Python。**

## 测试

```bash
python -m unittest discover tests -v
# Ran 12 tests in 0.13s → OK
```

压力测试：

```bash
python stress_test_ops.py
# 59 项全通过（数据库批量/并发/SQL注入/超长文本）
```

## 打包

```bash
pyinstaller --onefile --windowed --add-data "config.yaml;." --icon=icon.ico main.py
```

生成的 exe 约 100 MB，双击即运行，无需 Python 环境。

## 版本

v3.0 — 2026.06.26
