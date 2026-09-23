# 米游社运营助手 · miHoYo Ops Tool

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-ff4d6a)](https://customtkinter.tomschimansky.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

游戏社区运营全流程管理桌面工具。覆盖数据看板、AI 顾问、版本管理、报告生成、排期预算、内容工厂、趋势雷达七大模块，适用于日常运营工作的完整工作流。

## 目录

- [项目截图](#项目截图)
- [功能模块](#功能模块)
- [快速开始](#快速开始)
- [技术架构](#技术架构)
- [数据库设计](#数据库设计)
- [项目结构](#项目结构)
- [核心设计决策](#核心设计决策)
- [性能测试](#性能测试)
- [适用场景](#适用场景)
- [开发日志](#开发日志)

## 项目截图

> 由于 GitHub 限制，以下为界面文字描述。实际运行效果请克隆后运行 `main.py` 或双击 `米游社运营助手.exe`。

```
┌─────────────────────────────────────────────────────┐
│ 🎮  米哈游运营助手                  📊 数据工作台   │
│ miHoYo Ops Tool                        │            │
│──────────────────────────────│         │            │
│ 📊 数据工作台  ────────────│         │  数据天数    │
│ 🤖 AI运营顾问              │         │  待办任务    │  ← 四张汇总卡片
│ 📅 版本管理                │         │  历史报告    │
│ 📝 运营报告                │         │  活跃版本    │
│ 🗓 排期预算                │         │            │
│ 🎯 内容工厂                │         │ ┌─────────┐ │  ← Canvas 自绘
│ 🔭 趋势雷达                │         │ │折线图    │ │
│                            │         │ │DAU趋势   │ │
│ 🔍 搜索版本/活动/报告...   │         │ └─────────┘ │
│ 📊 版本对比                │         │            │
│                            │         │ 📝数据录入  │
│ 最近操作                   │         │
│ ● 数据本地存储             │         │
│ v2.0 · SQLite              │         │
└─────────────────────────────────────────────────────┘
```

## 功能模块

| 模块 | 快捷键 | 功能描述 | 关键特性 |
|------|--------|----------|----------|
| 📊 数据工作台 | Ctrl+1 | 日常运营数据录入与管理 | Canvas 自绘折线图、双标签页（数据工作台/玩家健康度）、多维度筛选、CSV 导出、暗色 Treeview 表格 |
| 🤖 AI 顾问 | Ctrl+2 | 基于大模型的智能运营建议 | DeepSeek GPT-4o-mini 双兼容、Prompt 模板库、后台线程异步调用、结果持久化、离线兜底话术 |
| 📅 版本管理 | Ctrl+3 | 游戏版本全生命周期管理 | 4 个标签页（看板、清单、时间线、对比）、进度条、甘特图、版本模板、双版本对比 |
| 📝 运营报告 | Ctrl+4 | 运营周报/月报生成 | 模板化自动生成 + AI 智能润色、历史报告管理、CSV/剪贴板导出、Markdown 格式输出 |
| 🗓 排期预算 | Ctrl+5 | 版本上线时间节点与成本管控 | 三合一设计（排期/预算/风险）、按阶段划分节点、计划 vs 实际对比、超支红色预警、概率×影响矩阵 |
| 🎯 内容工厂 | Ctrl+6 | 社媒文案智能生成 | 支持微博/B站/小红书三平台、三种文案类型（社媒文案/活动海报/投放素材）、四种风格（官方/二次元/悬念/热血）、历史记录管理 |
| 🔭 趋势雷达 | Ctrl+7 | 社媒热点实时追踪 | 24 种预设热点分类、B站 API 真实数据爬取、热度评分可视化、关键词标签云、AI 趋势分析 |
| ⚙️ AI 设置 | Ctrl+8 | 后端配置管理 | API Key 配置、模型选择、代理设置、连接测试 |

## 快速开始

### 方式一：直接运行 EXE（推荐）

1. 下载 `米游社运营助手.exe`（约 85 MB）
2. 双击运行，无需安装任何环境
3. 数据自动存储在可执行文件同目录下的 `data/ops_data.db`

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/yourname/miHoYo-ops-tool.git
cd miHoYo-ops-tool

# 安装依赖
pip install customtkinter openai pillow

# 运行
python main.py
```

### 方式三：自行打包

```bash
pyinstaller --onefile --noconsole --name "米游社运营助手" \
  --add-data "data;data" --icon "icon.ico" \
  --hidden-import "openai" --hidden-import "customtkinter" \
  --hidden-import "PIL" --hidden-import "db" --hidden-import "theme" \
  --hidden-import "views.dashboard" --hidden-import "views.ai" \
  --hidden-import "views.versions" --hidden-import "views.report" \
  --hidden-import "views.plans" --hidden-import "views.marketing" \
  --hidden-import "views.social_trend" --hidden-import "views.settings" \
  --collect-all "customtkinter" main.py
```

### AI 功能配置

1. 打开应用，点击左侧 `⚙️ AI设置`
2. 填入 API Key（支持 DeepSeek / OpenAI 兼容接口）
3. 选择模型（`deepseek-chat` / `deepseek-v4-pro` / `gpt-4o-mini`）
4. 点击 `💾 保存配置`（后续自动加载，也可点击生成时自动保存）

## 技术架构

```
┌────────────────────────────────────────────┐
│                  main.py                    │
│         App(CTk + 8 个 Mixin)              │
│  侧边栏 | 导航 | Toast | 快捷键 | 搜索       │
├────────────────────────────────────────────┤
│ DashboardMixin │ AIMixin │ VersionsMixin │
│ ────────────   │  ─────  │  ──────────    │
│ 数据录入       │ Prompt  │  4 标签页      │
│ Canvas 折线图   │ 线程调用 │  甘特图         │
│ CSV 导出       │ 配置保存 │  版本对比      │
├────────────────────────────────────────────┤
│ ReportMixin  │ PlansMixin │ MarketingMixin│
│ ───────────  │  ───────  │  ──────────   │
│ 模板生成      │ 排期节点   │  社媒文案     │
│ AI 润色       │ 预算管控   │  三平台支持   │
│ 历史管理      │ 风险矩阵   │  风格选择     │
├────────────────────────────────────────────┤
│ SocialTrendMixin │ SettingsMixin │
│ ──────────────   │  ──────────── │
│ B站 API 爬取      │ API Key 配置 │
│ 热点追踪         │ 模型选择     │
│ 热度评分         │ 连接测试     │
├────────────────────────────────────────────┤
│      db.py           │     theme.py        │
│  ────────────────    │  ──────────────     │
│  9 张表 CRUD         │  色板常量           │
│  配置持久化          │  ttk 暗色 Style     │
│  操作日志(上限100)    │                     │
├────────────────────────────────────────────┤
│              SQLite (ops_data.db)           │
│   数据本地存储 · 零配置 · 离线可用            │
└────────────────────────────────────────────┘
```

**技术栈完整清单：**

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11 | 标准 CPython |
| GUI 框架 | CustomTkinter 5.2+ | 基于 Tkinter 的现代主题封装 |
| 原生表格 | ttk.Treeview (clam 主题) | 自定义暗色 Style 配置 |
| 数据可视化 | tkinter Canvas | 自绘折线图（零额外依赖） |
| 数据库 | SQLite 3 | 通过 `sqlite3` 标准库操作 |
| AI 集成 | openai SDK | 兼容 DeepSeek / OpenAI 接口 |
| 异步处理 | threading.Thread | 后台线程执行 API 调用，`after()` 切回主线程 |
| 数据爬取 | requests + BeautifulSoup | B站 API / 微博 API |
| 打包分发 | PyInstaller 6.x | `--onefile` 单文件模式 |
| 图表字体 | Microsoft YaHei | Windows 系统自带，无需打包 |

**设计模式：**

- **Mixin（多继承）**：8 个功能模块作为独立 Mixin 类，App 主类通过多继承组合
- **依赖注入**：所有 Mixin 通过 `self` 访问共享的导航、Toast、数据库方法
- **连接即用即关**：每次 DB 操作使用 `with get_conn() as c:` 上下文管理器

## 数据库设计

### ER 图（文字版）

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  checklists   │     │   budgets     │     │    risks      │
│──────────────│     │──────────────│     │──────────────│
│ id (PK)      │     │ id (PK)      │     │ id (PK)      │
│ version_id ──┼──┐  │ version_id ──┼──┐  │ version_id ──┼──┐
│ task         │  │  │ category     │  │  │ title        │  │
│ assignee     │  │  │ item_name    │  │  │ probability  │  │
│ deadline     │  │  │ planned      │  │  │ impact       │  │
│ status       │  │  │ actual       │  │  │ mitigation   │  │
└──────────────┘  │  └──────────────┘  │  │ contingency  │  │
                  │                    │  │ owner        │  │
  ┌───────────────┘                    │  │ status       │  │
  │  ┌────────────────────────────────┘  └──────────────┘  │
  │  │  ┌──────────────────────────────────────────────────┘
  ▼  ▼  ▼
┌──────────────┐     ┌──────────────┐
│  versions       │     │    events     │
│──────────────│     │──────────────│
│ id (PK)      │◄────│ version_id   │  ← 活动关联版本
│ game         │     │ name         │
│ version      │     │ game         │
│ start_date   │     │ type         │
│ end_date     │     │ start_date   │
│ status       │     │ end_date     │
│ highlights   │     └──────────────┘
└──────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│daily_metrics │  │   reports    │  │    config    │
│──────────────│  │──────────────│  │──────────────│
│ date         │  │ title        │  │ key (PK)     │
│ game         │  │ content      │  │ value        │
│ dau          │  │ type         │  └──────────────┘
│ new_posts    │  │ created_at   │  ┌──────────────┐
│ comments     │  └──────────────┘  │ activity_log  │
│ avg_session  │                    │──────────────│
│ inter_rate   │                    │ action       │
└──────────────┘                    │ detail       │
                                    │ created_at   │
                                    └──────────────┘
```

### 表结构常量

| 表名 | 行数上限 | 索引策略 | 备注 |
|------|----------|----------|------|
| daily_metrics | 无上限 | 无（按需建立） | 日均千条，无需索引 |
| events | 无上限 | 无 | 活动信息 |
| versions | < 200 | 无 | 按游戏生命周期约 20-50 个 |
| checklists | 随版本增长 | 无 | 每版本约 20-30 个任务 |
| reports | 无上限 | 无 | 含 AI 生成结果 |
| config | < 50 | PRIMARY KEY | KV 键值对，常驻内存 |
| activity_log | <= 100 | 自动清理 | 保留最近 100 条 |
| budgets | 随版本增长 | 无 | 每版本约 10-30 个预算项 |
| risks | 随版本增长 | 无 | 每版本约 5-15 个风险项 |

### 迁移策略

使用 `ALTER TABLE` 语句进行增量迁移，包裹在 `try/except sqlite3.OperationalError` 中确保幂等。当前有效迁移：

```sql
ALTER TABLE events ADD COLUMN version_id INTEGER DEFAULT 0
```

## 项目结构

```
miHoYo-ops-tool/
├── main.py                    # 入口文件，230 行
│   └── App(CTk, 8 个 Mixin)  # 侧边栏、导航、Toast、快捷键、搜索
├── db.py                      # 数据库层，116 行
│   └── 建表、迁移、CRUD、配置持久化、操作日志
├── theme.py                   # 主题层，34 行
│   └── 色板常量 + ttk.Style 暗色配置
├── views/
│   ├── __init__.py            # 包初始化
│   ├── dashboard.py           # 数据工作台（808 行，最重模块）
│   ├── ai.py                  # AI 顾问（249 行，Prompt 模板 + 线程调用）
│   ├── versions.py            # 版本管理（267 行，看板 + 清单 + 甘特图）
│   ├── report.py              # 运营报告（397 行，模板生成 + AI 润色）
│   ├── plans.py               # 排期预算风险（177 行，三合一模块）
│   ├── marketing.py           # 内容工厂（346 行，三平台文案生成）
│   ├── social_trend.py        # 趋势雷达（334 行，B站爬取 + 热点追踪）
│   └── settings.py            # AI 设置（345 行，配置管理）
├── data/                      # SQLite 数据库（运行时自动创建，不需要提交）
│   └── ops_data.db
├── tests/                     # 单元测试套件
│   ├── test_db.py             # 数据库层测试
│   ├── test_views.py          # 视图层测试
│   └── test_performance.py    # 性能压力测试
├── icon.ico                   # 应用图标
└── README.md                  # 本文件
```

**代码量统计：**

| 文件 | 行数 | 说明 |
|------|------|------|
| main.py | 230 | App 容器 + UI 框架 + 8 个 Mixin 组合 |
| db.py | 116 | 数据库层 |
| theme.py | 34 | 主题配置 |
| views/dashboard.py | 808 | 数据工作台（最重模块） |
| views/ai.py | 249 | AI 顾问 |
| views/versions.py | 267 | 版本管理 |
| views/report.py | 397 | 运营报告 |
| views/plans.py | 177 | 排期/预算/风险 |
| views/marketing.py | 346 | 内容工厂 |
| views/social_trend.py | 334 | 趋势雷达 |
| views/settings.py | 345 | AI 设置 |
| **合计** | **~3303** | 11 个源文件，8 个功能模块 |

## 核心设计决策

### 1. 为什么选择桌面应用而非 Web？

- **目标用户画像**：运营同学，非技术背景。桌面软件双击即用，无需配置环境或记住 URL
- **离线可用**：AI 功能需要网络，但数据管理功能完全离线
- **数据安全**：运营数据（DAU、预算金额、风险预案）存储在本地 SQLite，无需担心数据泄露
- **分发成本**：U 盘/网盘一个文件即可，比部署 Web 服务简单

### 2. 为什么使用 Mixin 而非拆分子窗口？

- **共享上下文**：所有模块共用侧边栏导航、Toast、快捷键、操作日志、数据库连接
- **跨模块通信**：方法通过 `self._toast()`、`self._save_log()` 等直接调用，无需事件总线
- **代码直观**：新增功能只需新建 Mixin 文件并加入 App 类的继承链

### 3. 为什么自绘 Canvas 图表而非引入 matplotlib？

- **体积控制**：matplotlib + numpy 会使 EXE 从 85MB 膨胀至 200MB+，效率损失不成正比
- **功能充分性**：运营场景需要趋势线 + 数据点标记，Canvas 原语（line/oval/polygon）足够覆盖
- **启动速度**：matplotlib 首帧渲染约 1-2s，Canvas 是即时绘制

### 4. AI 调用为什么采用 threading 而非 async/await？

- **同步 SDK**：`openai` SDK 的 `chat.completions.create()` 是同步阻塞调用
- **线程模型**：后台 `threading.Thread(daemon=True)` 执行，完成后通过 `self.after(0, callback)` 回到主线程更新 UI
- **用户体验**：生成期间按钮 disable 并显示"⏳ 生成中…"，阻止重复提交

### 5. Toast 通知为什么替代 messagebox？

- **场景区分**：成功操作（保存/复制）用 Toast 2s 消失；错误/警告/确认删除仍用 messagebox
- **工作流保护**：messagebox 会打断用户操作流，Toast 是非侵入式反馈
- **实现成本**：CTkFrame + `self.after(2000, destroy)` 仅 4 行代码

## 性能测试

测试覆盖正常值、边界值（0/MAX）、特殊字符（Emoji/换行/Markdown）、空表查询、除零计算、多表联查。

### 高压测试（R1）

| 测试场景 | 数据量 | 耗时 | 结论 |
|----------|--------|------|------|
| 批量写入运营数据 | 5,000 条 | 0.04s | 满足日均数据处理 |
| 聚合查询 | 200 次 GROUP BY | 0.73s | 看板流畅刷新 |
| 版本 + 任务批量创建 | 50 版 × 30 任务 = 1,500 条 | 0.01s | 模板导入极速 |
| 预算批量写入 | 500 条（6类） | 0.03s | 预算录入无压力 |
| 风险批量写入 | 200 条（3级概率×影响） | 0.03s | 风险矩阵即时生成 |
| 配置读写压力 | 1,000 写 + 100 读 | 6.50s | 低频操作，性能充足 |
| 操作日志吞吐 | 500 条（上限 100）| 3.39s | 自动清理机制正常 |
| 多表 JOIN 联查 | 100 次 3 表联查 | 0.05s | 复杂查询毫秒级 |
| 跨模块关联查询 | 20 次 四表联查 | 0.01s | 数据完整性能保障 |

### 边界测试（R2）

| 测试类别 | 测试项目 | 结果 |
|----------|----------|------|
| DAU 边界 | 0、99,999,999（MAX）| 正常 |
| 互动率边界 | 0.0%、100.0% | 正常 |
| 空表查询 | 5 张表 SELECT * LIMIT 1 | 不崩溃 |
| 空表聚合 | AVG(dau) 无数据时 | 返回 None，不异常 |
| 特殊字符 | 🎉 Emoji / Markdown 表格 / 换行符 | 正确存储 |
| 日期边界 | 跨年查询（2025-12-31 ~ 2026-01-01）| 正确筛选 |
| 除零保护 | 0 任务版本的进度计算 | 返回 0%，不报错 |

## 适用场景

### 游戏运营岗

- ✅ 作品集展示：远程仓库 + 现场演示 + U 盘备用
- ✅ 面试 Demo：4 分钟完整演示路线（Ctrl+1~7 切模块）
- ✅ 入职即用：版本管理、报告生成等模块直接用于日常

### 会计 / 财务岗

- ✅ 预算管理：分类录入 + 计划/实际对比 + 使用率核算
- ✅ 数据看板：指标汇总 + 趋势分析 + CSV 导出
- ✅ 数据严谨：边界测试全覆盖，零值/空表/除零均有保护

## 开发日志

| 日期 | 里程碑 |
|------|--------|
| 2026-06 | 项目启动，CustomTkinter 选型，初版单文件完成 |
| 2026-06 | AI 顾问模块：DeepSeek 接入 + Prompt 模板 + 异步线程 |
| 2026-06 | 版本管理重构：新增进度条、编辑/删除、甘特图时间线、版本模板 |
| 2026-07 | UI 升级：Toast、快捷键、过渡动画、侧边栏指示条、操作日志 |
| 2026-07 | 新增模块：排期管理、预算管理、风险预案（三合一设计） |
| 2026-07 | 新增模块：内容工厂（三平台文案生成）、趋势雷达（B站数据爬取） |
| 2026-07 | Mixin 架构重构：8 个功能模块拆分，代码解耦 |
| 2026-07 | 性能优化：Canvas 图表、SQLite WAL 模式、异步处理 |

## License

MIT License. 详见 [LICENSE](LICENSE) 文件。

---

**如果你觉得这个项目有用，请给一个 Star ⭐**

**如果我的项目帮到了你的面试，也欢迎分享你的经验 ❤️**
