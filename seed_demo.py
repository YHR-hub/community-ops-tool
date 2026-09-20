"""
演示数据 —— 让工具一打开就有内容可看、可讲
==========================================

为什么需要这个：
  重构前的数据库是空的（daily_metrics 0 条、versions 0 条），
  所以打开工具第一屏什么都没有 —— 这是「感觉功能不行」的主因。

  面试演示时更是如此：面试官坐下看 30 秒，如果第一屏是空表格，
  再好的代码也讲不出来。

用法：
  python seed_demo.py           # 数据为空时填充
  python seed_demo.py --force   # 清空后重新填充
"""

import random
import sys
from datetime import datetime, timedelta

import db

random.seed(20260919)  # 固定种子，保证每次生成的演示数据一致

GAME = "崩坏：星穹铁道"

# 角色池（用于生成使用率数据）—— 对齐 4.5「挥掷千星的筹码」卡池
# （知更鸟·晴歌 / 砂金·戏浪双SP，复刻风堇 / 不死途，4.4 SP 姬子·启行）
CHARACTERS = [
    "知更鸟·晴歌", "砂金·戏浪", "姬子·启行", "风堇", "不死途", "遨蝶",
    "长夜月", "昔涟", "遐蝶", "飞霄", "知更鸟", "花火", "符玄", "流萤",
]

# 上游版本（用于制造"使用率下降"的趋势，让风险检测有东西可抓）
PREV_VERSION = "4.4"
CUR_VERSION = "4.5"

PLATFORMS = ["米游社", "B站", "微博", "抖音", "贴吧"]

# 标准任务模板（按阶段分组，替代旧版的扁平任务列表）
TASK_TEMPLATE = [
    ("内容制作", ["版本PV发布", "角色演示视频", "技能展示帖", "预约H5上线", "倒计时海报"]),
    ("社媒预热", ["微博预热话题", "B站UP主投放", "米游社置顶预告", "小红书种草"]),
    ("活动配置", ["活动规则确认", "奖励数值配置", "公告文案审核", "FAQ准备"]),
    ("上线保障", ["数据埋点检查", "客服话术同步", "舆情监控就位"]),
    ("版本复盘", ["核心指标对比", "社区反馈汇总", "复盘会议"]),
]

BUDGET_ITEMS = [
    ("推广", "B站KOL投放", 320000, 301000),
    ("推广", "微博话题加热", 150000, 148000),
    ("素材", "PV与角色演示制作", 260000, 245000),
    ("素材", "视觉物料设计", 80000, 72000),
    ("外包", "H5互动页开发", 120000, 118000),
    ("活动奖品", "社区二创激励", 60000, 41000),
    ("线下", "线下主题展位", 200000, 96000),
]

EVENTS = [
    ("4.6版本前瞻预约活动", "版本活动", -3, 12),
    ("新角色同人征集大赛", "福利活动", -6, 20),
    ("米游社创作者激励计划", "福利活动", -14, 30),
    ("品牌联动特别直播", "联动", 4, 4),
    ("巡星之礼签到活动", "福利活动", -8, 8),
]


def _wipe():
    """清空业务表（保留 config）。"""
    for t in ("versions", "daily_metrics", "events", "checklists",
              "budgets", "risks", "char_usage", "community_hot",
              "activity_log", "reports"):
        db.execute(f"DELETE FROM {t}")


def seed(force=False):
    db.init_db()

    existing = db.db_stats()
    if existing.get("versions", 0) > 0 and not force:
        return 0

    if force:
        _wipe()

    count = 0
    now = datetime.now()
    today = now.date()

    # ═══════════════════════════════════════════════
    #  1. 版本：一个已关闭的上游 + 一个进行中的当前版本
    # ═══════════════════════════════════════════════
    prev_start = today - timedelta(days=54)
    cur_start = today - timedelta(days=12)
    # 4.3（closed）：真实版本「沉于生者的忘川」——千冶·刃SP回归、二相乐园篇章
    v43_start = prev_start - timedelta(days=44)

    # 4.0 ~ 4.2（closed）：真实历史版本，让时间线有完整的 4.x 演进
    # 4.0 爻光/火花双欢愉开幕 -> 4.1 不死途（官方公告「献给破晓的失控」）
    # -> 4.2 银狼LV.999/绯英 -> 4.3 千冶·刃 -> 4.4 姬子·启行+Fate联动+主线终章 -> 4.5 双SP
    HISTORICAL_VERSIONS = [
        ("4.0", "爻光/火花双欢愉登场，4.x世代开幕"),
        ("4.1", "不死途登场，二相乐园篇章推进"),
        ("4.2", "银狼LV.999/绯英登场，欢愉体系扩充"),
    ]
    hist_start = v43_start - timedelta(days=40 * len(HISTORICAL_VERSIONS))
    for ver, hl in HISTORICAL_VERSIONS:
        db.execute(
            "INSERT INTO versions (game,version,start_date,end_date,status,highlights,notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (GAME, ver, str(hist_start), str(hist_start + timedelta(days=40)),
             "closed", hl, ""))
        hist_start += timedelta(days=40)
        count += 1
    db.execute(
        "INSERT INTO versions (game,version,start_date,end_date,status,highlights,notes) "
        "VALUES (?,?,?,?,?,?,?)",
        (GAME, "4.3", str(v43_start), str(v43_start + timedelta(days=44)),
         "closed", "千冶·刃SP回归，二相乐园篇章开启，复刻昔涟/白厄",
         ""))
    count += 1

    prev_id = db.execute(
        "INSERT INTO versions (game,version,start_date,end_date,status,highlights,notes) "
        "VALUES (?,?,?,?,?,?,?)",
        (GAME, PREV_VERSION, str(prev_start), str(prev_start + timedelta(days=42)),
         "closed", "姬子·启行SP上线，Fate/stay night联动开放，主线终章完结",
         "版本整体表现平稳，社区口碑正向"))
    count += 1

    cur_id = db.execute(
        "INSERT INTO versions (game,version,start_date,end_date,status,highlights,notes) "
        "VALUES (?,?,?,?,?,?,?)",
        (GAME, CUR_VERSION, str(cur_start), str(cur_start + timedelta(days=42)),
         "live", "知更鸟·晴歌/砂金·戏浪双SP登场，千星城开放",
         "关注互动率下滑问题"))
    count += 1

    # 另一个游戏的版本，证明多游戏支持
    other_start = today - timedelta(days=25)
    db.execute(
        "INSERT INTO versions (game,version,start_date,end_date,status,highlights,notes) "
        "VALUES (?,?,?,?,?,?,?)",
        ("原神", "7.0", str(other_start), str(other_start + timedelta(days=42)),
         "live", "主线推进至至冬篇，周年庆节点前蓄势", ""))
    count += 1

    # ═══════════════════════════════════════════════
    #  2. 每日指标：60 天，含人工植入的"互动率下滑"
    # ═══════════════════════════════════════════════
    base_dau = 52000
    for i in range(60, 0, -1):
        d = today - timedelta(days=i)
        # 版本切换日有一个小高峰
        bump = 6000 if abs((d - cur_start).days) <= 2 else 0
        # 周末活跃更高
        weekend = 4200 if d.weekday() >= 5 else 0
        trend = (60 - i) * 110          # 缓慢自然增长
        noise = random.randint(-1800, 1800)
        dau = base_dau + bump + weekend + trend + noise

        posts = int(dau * random.uniform(0.018, 0.026))
        comments = int(posts * random.uniform(4.2, 5.8))
        session = round(random.uniform(18.5, 26.5), 1)

        # 互动率：前 30 天正常，后 30 天逐步下滑 —— 制造可被解读的趋势
        if i > 30:
            rate = round(random.uniform(4.2, 5.4), 1)
        else:
            decay = (30 - i) * 0.06
            rate = round(random.uniform(3.4, 4.0) - decay, 1)

        # 留存（汇总口径，%）：
        #   次留健康线二游约 45%，7 留约为次留的 47%，30 留约为次留的 26%。
        #   后 30 天与互动率下滑同期走低 —— 让留存分析 Tab 和风险预警
        #   都有真实的趋势可抓，而不是一条死板的直线。
        new_users = int(dau * random.uniform(0.032, 0.042))
        if i > 30:
            r1 = random.uniform(45.0, 47.5)
        else:
            r1 = random.uniform(44.0, 45.5) - (30 - i) * 0.22
        r1 = max(30.0, r1)
        r7 = max(12.0, r1 * random.uniform(0.44, 0.50))
        r30 = max(7.0, r1 * random.uniform(0.24, 0.28))

        db.execute(
            "INSERT INTO daily_metrics "
            "(date,game,dau,new_users,new_posts,comments,avg_session,"
            "interaction_rate,retention_1,retention_7,retention_30) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (str(d), GAME, dau, new_users, posts, comments, session,
             max(1.4, rate), round(r1, 1), round(r7, 1), round(r30, 1)))
        count += 1

    # 原神也补一批，让游戏筛选有意义
    for i in range(45, 0, -1):
        d = today - timedelta(days=i)
        dau = 38000 + random.randint(-2000, 2600) + (45 - i) * 60
        new_users = int(dau * random.uniform(0.028, 0.036))
        r1 = random.uniform(42.5, 45.5)
        r7 = r1 * random.uniform(0.44, 0.50)
        r30 = r1 * random.uniform(0.24, 0.28)
        db.execute(
            "INSERT INTO daily_metrics "
            "(date,game,dau,new_users,new_posts,comments,avg_session,"
            "interaction_rate,retention_1,retention_7,retention_30) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (str(d), "原神", dau, new_users,
             int(dau * random.uniform(0.015, 0.022)),
             int(dau * 0.09),
             round(random.uniform(17, 24), 1),
             round(random.uniform(3.6, 5.0), 1),
             round(r1, 1), round(r7, 1), round(r30, 1)))
        count += 1

    # ═══════════════════════════════════════════════
    #  3. 任务清单
    # ═══════════════════════════════════════════════
    def add_tasks(vid, done_ratio):
        for cat, tasks in TASK_TEMPLATE:
            for t in tasks:
                # 前面阶段完成度高，后面阶段低，模拟真实推进节奏
                done = random.random() < done_ratio
                status = "done" if done else (
                    "doing" if random.random() < 0.35 else "pending")
                deadline = today + timedelta(days=random.randint(-4, 24))
                db.execute(
                    "INSERT INTO checklists (version_id,task,category,assignee,deadline,status) "
                    "VALUES (?,?,?,?,?,?)",
                    (vid, t, cat,
                     random.choice(["运营A", "运营B", "市场C", "设计D", ""]),
                     str(deadline), status))

    add_tasks(cur_id, 0.42)
    add_tasks(prev_id, 1.0)
    count += sum(len(t) for _, t in TASK_TEMPLATE) * 2

    # ═══════════════════════════════════════════════
    #  4. 活动
    # ═══════════════════════════════════════════════
    for name, etype, off_start, off_end in EVENTS:
        db.execute(
            "INSERT INTO events (name,game,type,start_date,end_date,notes,version_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (name, GAME, etype,
             str(today + timedelta(days=off_start)),
             str(today + timedelta(days=off_end)),
             "", cur_id))
        count += 1

    # ═══════════════════════════════════════════════
    #  5. 预算
    # ═══════════════════════════════════════════════
    for cat, item, planned, actual in BUDGET_ITEMS:
        db.execute(
            "INSERT INTO budgets (version_id,category,item_name,planned,actual,notes) "
            "VALUES (?,?,?,?,?,?)",
            (cur_id, cat, item, planned, actual, ""))
        count += 1

    # ═══════════════════════════════════════════════
    #  6. 风险
    # ═══════════════════════════════════════════════
    risks = [
        ("姬子·启行使用率连续下滑，存在角色强度争议", "high", "high",
         "分析角色定位，评估是否需要数值调整",
         "准备角色加强方案或同定位替代角色推广", "运营"),
        ("B站投放预算使用率已达 94%，可能超支", "medium", "medium",
         "暂停非核心渠道投放，重新评估ROI",
         "追加预算审批或压缩线下活动支出", "市场"),
        ("社区互动率低于健康线，内容话题热度不足", "high", "medium",
         "策划话题引导活动，加强UGC征集",
         "启动紧急内容补位，联系KOL造势", "运营"),
        ("线下主题展位招商进度延后", "low", "medium",
         "提前锁定场地供应商",
         "缩减展位规模或改为线上虚拟展", "市场"),
    ]
    for title, prob, imp, mit, con, owner in risks:
        db.execute(
            "INSERT INTO risks (version_id,title,probability,impact,"
            "mitigation,contingency,owner,status) VALUES (?,?,?,?,?,?,?,'open')",
            (cur_id, title, prob, imp, mit, con, owner))
        count += 1

    # ═══════════════════════════════════════════════
    #  7. 角色使用率（制造可被自动检测的下降趋势）
    # ═══════════════════════════════════════════════
    cur_usage = []
    prev_usage = []
    for idx, ch in enumerate(CHARACTERS):
        base = 62 - idx * 3.4 + random.uniform(-2, 2)
        prev_usage.append({
            "version": PREV_VERSION, "character_name": ch,
            "usage_rate": round(max(2.0, base), 1), "abyss_floor": 12})

        # 姬子·启行、风堇 明显下滑（4.4 顶流被 4.5 双SP分流），触发自动风险标记。
        # drop 下限 7.0：叠加随机噪声（+1.6 上限）后净差仍 ≥5.4pp，
        # 保证必然越过「下滑超 5pp」的抓取线 ——
        # v4.1 曾因随机序列变化让 drop 掉到 5.5 + 1.6，测试抓取数从 2 变 1。
        drop = 0
        if ch in ("姬子·启行", "风堇"):
            drop = random.uniform(7.0, 9.5)
        elif ch in ("流萤", "花火"):
            drop = random.uniform(1.0, 3.0)

        cur_usage.append({
            "version": CUR_VERSION, "character_name": ch,
            "usage_rate": round(max(2.0, base - drop + random.uniform(-1.2, 1.6)), 1),
            "abyss_floor": 12})

    db.upsert_char_usage(prev_usage)
    db.upsert_char_usage(cur_usage)
    count += len(prev_usage) + len(cur_usage)

    # ═══════════════════════════════════════════════
    #  8. 社区热度
    # ═══════════════════════════════════════════════
    for ver, scale in ((PREV_VERSION, 1.0), (CUR_VERSION, 0.92)):
        for p in PLATFORMS:
            posts = int(random.uniform(1800, 4200) * scale)
            db.upsert_community_hot([{
                "version": ver, "platform": p,
                "post_count": posts,
                "avg_reply_count": round(random.uniform(6.5, 15.0), 1)}])
            count += 1

    db.add_log("载入演示数据", f"{GAME} {CUR_VERSION}")
    return count


def reset():
    """清空全部业务数据（供用户恢复干净状态）。"""
    db.init_db()
    _wipe()
    return True


if __name__ == "__main__":
    force = "--force" in sys.argv
    db.init_db()
    if "--reset" in sys.argv:
        reset()
        print("已清空全部业务数据")
    else:
        n = seed(force=force)
        if n:
            print(f"已生成演示数据，共 {n} 条记录")
        else:
            print("数据库已有数据，跳过（用 --force 强制重新生成）")
    print("当前表行数：", db.db_stats())
