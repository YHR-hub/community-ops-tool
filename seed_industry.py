# -*- coding: utf-8 -*-
"""
行业情报数据种子（v4.5）
=======================

从「行业知识库」目录摘录的结构化数据，幂等灌入 industry_events /
competitor_revenue / insight_cases 三张表。

设计说明：
  · 这三张表**不在** seed_demo._wipe 的清理列表里 —— 「重置数据」
    只重置自有运营数据，行业情报作为长期资产保留；
  · 日期是快照时点（2026-09 归档），后续更新增量追加即可。
"""
import db


def _event(date, category, title, detail="", impact="", source=""):
    db.execute(
        "INSERT OR REPLACE INTO industry_events "
        "(date, category, title, detail, impact, source) VALUES (?,?,?,?,?,?)",
        (date, category, title, detail, impact, source))


def _revenue(month, product, revenue, note=""):
    db.execute(
        "INSERT OR REPLACE INTO competitor_revenue "
        "(month, product, revenue, note) VALUES (?,?,?,?)",
        (month, product, revenue, note))


def _case(name, market, framework="", takeaway="", source=""):
    if db.query("SELECT id FROM insight_cases WHERE name=?", (name,), one=True):
        return
    db.execute(
        "INSERT INTO insight_cases (name, market, framework, takeaway, source) "
        "VALUES (?,?,?,?,?)", (name, market, framework, takeaway, source))


def seed():
    db.init_db()

    # ── 行业事件（来源：行业知识库 02/03，日期为事件日）──
    _event("2026-09-20", "版本",
           "星铁 4.6「月升之前，与兽共舞」前瞻直播",
           "300 兑换码；新角色真珠（冰属性·欢愉·辅助坦克）；9/28 上线至 11/11；"
           "公布 4.8 联动《绝区零》",
           "前瞻预热用「认知性话题」（星神进池意味着什么）而非数值话题",
           "官方前瞻 / 17173")
    _event("2026-09-20", "公司",
           "星布谷地「连接测试」开启（限量/删档/计费）",
           "终测开放充值、数据清空；公测定档 2026 冬；无战斗无抽卡",
           "删档计费=上线前最诚实的验证：玩家用真金白银投票",
           "品乐科技")
    _event("2026-09-04", "公司",
           "因缘精灵 + 星布谷地启动器预约开启",
           "米哈游启动器统一预约入口；因缘精灵三轮测试后待公测",
           "启动器正在平台化——米哈游在做生态而不只是产品",
           "IT之家")
    _event("2026-09-08", "舆情",
           "英语社区「退坑潮」讨论（power creep / 终局设计 / 剧情表现）",
           "Reddit+YouTube 集中讨论；8 月移动端流水 $28.72M vs 7 月 $42.08M",
           "愤怒的玩家还在乎；冷漠的玩家才是更大的威胁",
           "kursiv / gamingsport")
    _event("2026-09-04", "舆情",
           "KGUA 就 NIKKE 异常数据处罚发表声明",
           "韩国游戏利用者协会（律师主导）要求处罚标准透明化",
           "韩国维权从「卡车自组织」进化到「律师协会+政策游说」",
           "NGA / KGUA 官网")
    _event("2026-09-09", "行业",
           "Steam 大规模成就泄露事件",
           "《女神异闻录 6》《王国之心 4》等数十款未公开作品数据泄露",
           "信息安全成为行业焦点议题",
           "腾讯游戏新闻日报")
    _event("2026-10-01", "政策",
           "主播扣税新规生效（入账即扣税）",
           "劳务报酬改为入账次日自动扣税；年入 30 万内大概率汇算退税",
           "内容创作者生态的税务环境变化，MCN/内容运营需跟进",
           "平台公告")

    # ── 竞品流水（2026-08，第三方估算口径）──
    AUG = "2026-08"
    for prod, rev, note in [
        ("原神", 10.92, "7.0 至冬国开放（全平台）"),
        ("绝区零", 7.90, "周年后新版本（三产品唯一增长）"),
        ("鸣潮", 7.29, "清宵卡池 + 心月狐预告"),
        ("崩坏：星穹铁道", 6.19, "版本衔接期稳前五"),
        ("火影忍者", 4.16, "暑期+周年"),
        ("FGO", 4.08, "日服 11 周年（环比 +121%）"),
        ("异环", 3.49, "公测 4 个月站稳"),
        ("明日方舟", 2.99, ""),
        ("明日方舟：终末地", 1.56, "对比开服期有落差"),
        ("诡秘之主", 1.08, "8/21 公测，10 天破亿"),
    ]:
        _revenue(AUG, prod, rev, note)

    # ── 舆情案例卡（面试可引用）──
    _case("退坑潮与「冷漠」框架", "美",
          "power creep × 终局设计 × 剧情表现三重叠加；愤怒会表达，冷漠直接消失",
          "看社区健康度，要看「沉默流失」而不是「吵闹声量」",
          "kursiv.media / GamingSport 2026-09")
    _case("韩国玩家「协会化」", "韩",
          "KGUA：律师主导 + 立法游说（冒险岛案推动立法 → NIKKE 声明进行中）",
          "出海韩国：玩家维权的制度化 = 合规成本上升，是结构性变化",
          "NGA / KGUA 2026-09")
    _case("删档计费测试", "中",
          "星布谷地剔除战斗与抽卡，用计费测试验证「情感投入型」付费锚点",
          "上线前最诚实的验证方式，比任何问卷都准",
          "品乐科技 2026-09")
    _case("跨市场玩家联动", "全球",
          "第七史诗：中国玩家众筹租卡车开到韩国开发商门口，韩国玩家换头像致谢",
          "「四市场共振」不是推演——跨市场联合行动已经真实发生过",
          "公开报道")
    _case("纪念日杠杆", "日",
          "FGO 日服 11 周年单日收入破 315 万美元，8 月环比 +121%",
          "纪念日运营是二游最有效、最可复用的长线收入杠杆",
          "白鲸出海 2026-09")

    s = db.db_stats()
    print("行业情报种子完成：")
    print(f"  事件 {s.get('industry_events', 0)} 条 / "
          f"流水 {s.get('competitor_revenue', 0)} 条 / "
          f"案例 {s.get('insight_cases', 0)} 条")


def reset():
    """清空行业情报（一般不需要；seed_demo.reset 不会碰这三张表）。"""
    for t in ("industry_events", "competitor_revenue", "insight_cases"):
        db.execute(f"DELETE FROM {t}")


if __name__ == "__main__":
    seed()
