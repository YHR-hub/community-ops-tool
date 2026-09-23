"""演示模式 —— 预填充丰富的模拟数据供面试展示"""
import random
from datetime import datetime, timedelta
from db import get_conn, GAMES, init_db

CHARS = ["胡桃","钟离","雷电将军","纳西妲","芙宁娜","枫原万叶","那维莱特","艾尔海森",
         "夜兰","妮露","刻晴","甘雨","宵宫","八重神子","珊瑚宫心海","流浪者","赛诺",
         "白术","闲云","仆人","申鹤","魈","达达利亚","神里绫华","万叶","妮露"]

PLATFORMS = ["微博","B站","贴吧","NGA","知乎","小红书","虎扑","抖音","米游社"]
EVENT_TYPES = ["签到活动","版本预热","社区创作","角色UP","网页活动","节日庆典","充值返利"]
STAFF = ["运营A","运营B","运营C","社区运营","数据分析师"]


def seed_demo(force=False):
    with get_conn() as c:
        cnt = c.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
        if cnt > 10 and not force:
            return

    base = datetime(2025, 1, 1)
    with get_conn() as c:
        # ── 版本数据 ──
        for i in range(10):
            v = f"{i//2+4}.{i%2}"
            s = base + timedelta(days=i * 42)
            e = s + timedelta(days=41)
            c.execute("""INSERT OR REPLACE INTO versions (game,version,start_date,end_date,status,highlights)
                         VALUES (?,?,?,?,?,?)""",
                      (GAMES[i % 4], v, s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"),
                       random.choice(["live","live","live","review","planning"]),
                       f"新角色上线、主线剧情第{i+1}章、周年庆活动"))

        vers = c.execute("SELECT id,game,version FROM versions").fetchall()

        # ── 每日指标 (30天) ──
        for g_idx, g in enumerate(GAMES):
            for d in range(30):
                dt = base + timedelta(days=d)
                base_dau = [80000, 120000, 60000, 40000][g_idx]
                dau_val = int(base_dau + random.randint(-20000, 30000) + d * 500)
                c.execute("""INSERT OR REPLACE INTO daily_metrics
                             (date,game,dau,new_posts,comments,avg_session,interaction_rate)
                             VALUES (?,?,?,?,?,?,?)""",
                          (dt.strftime("%Y-%m-%d"), g, dau_val,
                           random.randint(200, 3000), random.randint(500, 8000),
                           round(random.uniform(5, 25), 1), round(random.uniform(1, 8), 2)))

        # ── 活动 ──
        for i in range(15):
            g = GAMES[i % 4]
            v = vers[i % len(vers)]
            s = base + timedelta(days=random.randint(0, 400))
            e = s + timedelta(days=random.randint(7, 21))
            c.execute("""INSERT OR REPLACE INTO events (name,game,type,start_date,end_date,version_id,notes)
                         VALUES (?,?,?,?,?,?,?)""",
                      (f"{g}活动_{i+1}", g, random.choice(EVENT_TYPES),
                       s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"), v[0],
                       f"关联版本 {v[1]} {v[2]}"))

        # ── 任务清单 ──
        for i, v in enumerate(vers):
            for j in range(random.randint(3, 8)):
                c.execute("""INSERT OR REPLACE INTO checklists (version_id,task,assignee,deadline,status)
                             VALUES (?,?,?,?,?)""",
                          (v[0], f"任务_{j+1}: 版本{v[2]}准备项",
                           random.choice(STAFF),
                           (base + timedelta(days=random.randint(5, 300))).strftime("%Y-%m-%d"),
                           random.choice(["done","done","pending","in_progress"])))

        # ── 预算 ──
        cats = ["推广","素材","外包","活动奖品","线下","其他"]
        for v in vers[:6]:
            for j in range(random.randint(2, 5)):
                planned = round(random.uniform(10000, 200000), 2)
                actual = round(planned * random.uniform(0.7, 1.3), 2)
                c.execute("""INSERT OR REPLACE INTO budgets (version_id,category,item_name,planned,actual,notes)
                             VALUES (?,?,?,?,?,?)""",
                          (v[0], random.choice(cats), f"预算项_{j+1}", planned, actual, ""))

        # ── 风险 ──
        for v in vers:
            if random.random() > 0.3:
                titles = [
                    "角色使用率持续偏低",
                    "社区负面舆情风险",
                    "卡池流水不达预期",
                    "版本上线延期风险",
                    "竞品同期上线冲击",
                ]
                title = random.choice(titles)
                c.execute("""INSERT OR REPLACE INTO risks
                             (version_id,title,probability,impact,mitigation,contingency,owner,status)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (v[0], title,
                           random.choice(["low","medium","high","critical"]),
                           random.choice(["low","medium","high","critical"]),
                           f"预防措施: 加强监控与预案",
                           f"应急方案: 快速响应与补偿",
                           random.choice(STAFF),
                           random.choice(["open","monitoring","open"])))

        # ── 角色使用率 ──
        for ch in CHARS:
            usage = round(random.uniform(5, 85), 1)
            # 部分角色制造下降趋势（供自动风险检测用）
            if ch in ["刻晴","申鹤","夜兰"]:
                usage = round(random.uniform(0.1, 3.0), 1)
            for ver_label in ["4.8", "5.0", "5.1"]:
                c.execute("""INSERT OR REPLACE INTO char_usage (version,character_name,usage_rate,abyss_floor)
                             VALUES (?,?,?,?)""",
                          (ver_label, ch,
                           round(usage * random.uniform(0.85, 1.15), 1),
                           random.randint(10, 12)))

        # ── 社区热度 ──
        for p in PLATFORMS:
            for ver_label in ["4.8", "5.0", "5.1"]:
                c.execute("""INSERT OR REPLACE INTO community_hot (version,platform,post_count,avg_reply_count)
                             VALUES (?,?,?,?)""",
                          (ver_label, p, random.randint(200, 15000),
                           round(random.uniform(3, 60), 1)))

    print("[demo] 演示数据已生成")


if __name__ == "__main__":
    init_db()
    seed_demo(force=True)
