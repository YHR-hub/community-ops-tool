"""
运营早报智能体 —— 感知 → 决策 → 行动 → 产出
==============================================

这是什么：
  每天进总览页点一下，智能体自动巡检数据库，10 秒产出一份
  「带结论、带归因、带建议动作」的运营早报。

为什么叫智能体而不是报表：
  报表是把固定查询渲染出来；智能体对「查什么」做决策 ——
  它根据上一轮的发现路由下一步动作（发现留存下滑 → 才去交叉查询互动率；
  发现 DAU 异动 → 才去展开游戏维度拆分），并把每一步决策记入 trace。
  决策轨迹全程可解释，这是与「一次性跑完的定时脚本」的本质区别。

设计取舍（面试可讲）：
  · 数据查询是确定性操作，交给 LLM 自由决策是拿稳定性换噱头。
    所以把「智能」放在路由与归因规则上（规则引擎，可测试），
    把「表达」留给 LLM 润色（可选，失败自动回退规则模板）—— 各干各擅长的事。
  · 阈值与口径完全复用 db 层的 ANOMALY_RULES / valid_retention，
    智能体不另立口径，避免「报表一个数、早报另一个数」。
"""

from datetime import datetime

from db import (
    anomaly_report, retention_stats, metrics_between, latest_version,
    date_str, days_ago, load_config, query, execute,
)

# 与总览页 THRESHOLDS 保持一致：智能体不另立口径
RET_DROP_PP = -1.5       # 次留 7 天均值环比跌幅（pp）→ 预警
BUDGET_USAGE_WARN = 90   # 预算使用率（%）→ 预警
FRESH_WARN_DAYS = 1      # 数据落后天数 → 提醒

ANOMALY_ACTIONS = {
    "DAU": "核对渠道投放与版本节奏，确认下跌来自哪一段用户",
    "新增用户": "拆分新增结构（自然/买量/活动），定位量级变化来源",
    "互动率": "排查近期内容话题热度与发帖质量，必要时补位话题活动",
}


# ═══════════════════════════════════════════════════════
#  感知层：数据采集（每个函数只做一件事，方便单独测试）
# ═══════════════════════════════════════════════════════

def _freshness():
    """数据新鲜度：最后一条指标距今几天。无数据返回 None。"""
    row = query("SELECT MAX(date) AS last FROM daily_metrics", one=True)
    last = row["last"] if row else None
    if not last:
        return None
    late = (datetime.strptime(date_str(), "%Y-%m-%d")
            - datetime.strptime(str(last), "%Y-%m-%d")).days
    return {"last": str(last), "late": max(0, late)}


def _cross_interaction():
    """
    互动率交叉检查：近 7 天均值 vs 前 7 天均值，返回 pp 差。
    数据不足返回 None。供留存下滑时的归因路由使用。
    """
    rows = metrics_between(date_str(days_ago(14)), date_str())
    if len(rows) < 4:
        return None
    half = len(rows) // 2
    prev, cur = rows[:half], rows[half:]

    def avg(rs):
        vals = [r["interaction_rate"] for r in rs if r["interaction_rate"] is not None]
        return sum(vals) / len(vals) if vals else None

    a, b = avg(prev), avg(cur)
    if a is None or b is None:
        return None
    return round(b - a, 2)


def _overdue_count(version_id):
    row = query(
        "SELECT COUNT(*) AS n FROM checklists "
        "WHERE version_id=? AND status!='done' AND deadline < ?",
        (version_id, date_str()), one=True)
    return row["n"] or 0 if row else 0


def _budget_usage(version_id):
    """预算总使用率（%），无预算返回 None。"""
    row = query(
        "SELECT COALESCE(SUM(planned),0) AS p, COALESCE(SUM(actual),0) AS a "
        "FROM budgets WHERE version_id=?", (version_id,), one=True)
    if not row or not row["p"]:
        return None
    return round(row["a"] / row["p"] * 100, 1)


# ═══════════════════════════════════════════════════════
#  产出层：归因文案（纯函数，可单测）
# ═══════════════════════════════════════════════════════

def compose(ctx):
    """
    把结构化发现拼成早报正文（规则模板，不依赖网络与 LLM）。
    ctx 关键字段：game / version / day / has_data / ret_cur / ret_drop /
    rate_delta / alerts / actions / ups
    """
    if not ctx.get("has_data"):
        return ("暂无运营数据：先在「数据」页录入每日指标，"
                "或载入演示数据。早报会在有数据后自动包含异动、"
                "留存与任务维度。")
    head = ""
    if ctx.get("game") and ctx.get("version"):
        head = f"{ctx['game']} {ctx['version']} 上线第 {ctx.get('day', '?')} 天："
    if ctx.get("alerts"):
        first = ctx["alerts"][0]["text"] if isinstance(ctx["alerts"][0], dict) \
            else str(ctx["alerts"][0])
        body = f"需要出手：{first}。"
    else:
        body = "各项指标平稳，无需干预。"
    if ctx.get("ret_drop") is not None and ctx["ret_drop"] <= RET_DROP_PP:
        if ctx.get("rate_delta") is not None and ctx["rate_delta"] < -0.3:
            body += (f"次日留存环比 {ctx['ret_drop']:+.1f}pp，"
                     f"互动率同步走低 {ctx['rate_delta']:+.1f}pp —— "
                     "两个下滑同期出现，指向内容吸引力整体回落。")
        elif ctx.get("rate_delta") is not None:
            body += (f"次日留存环比 {ctx['ret_drop']:+.1f}pp，"
                     "但互动率平稳 —— 下滑更可能来自新增渠道质量波动，"
                     "建议先拆新增结构。")
    if ctx.get("ups"):
        ups = ctx["ups"] if isinstance(ctx["ups"], list) else [ctx["ups"]]
        body += f"机会信号：{ups[0]}，暴涨是机会不是风险，可顺势加推。"
    if ctx.get("actions"):
        act = ctx["actions"] if isinstance(ctx["actions"], list) else [ctx["actions"]]
        body += f"今日建议：{act[0]}。"
    return (head + body).strip()


# 建议动作 → 结构化条目，供「一键转待办」使用。
# 为什么单独做一层映射而不是让 UI 直接写库：
#   「这条建议算任务还是风险、归到哪个类目、几天内做完」是运营规则，
#   规则就应该在数据层，UI 只负责触发 —— 换一个界面也照样成立。
ACTION_PLAN_RULES = [
    # (关键词, 类目, 落库目标, 建议天数)
    ("预算", "预算", "risk", 3),
    ("超支", "预算", "risk", 3),
    ("逾期", "任务推进", "task", 1),
    ("清逾期", "任务推进", "task", 1),
    ("互动率", "内容运营", "task", 2),
    ("话题", "内容运营", "task", 2),
    ("留存", "数据核查", "task", 2),
    ("渠道", "数据核查", "task", 2),
    ("投放", "数据核查", "task", 2),
    ("DAU", "数据核查", "task", 2),
]


def action_plan(actions, game=None):
    """
    把建议动作文本映射成结构化条目（不写库，纯函数，方便测试）。

    返回 list[dict]：text / category / target(task|risk) / days / owner。
    """
    out = []
    for text in actions or []:
        category, target, days = None, "task", 2
        for kw, cat, tgt, dd in ACTION_PLAN_RULES:
            if kw in text:
                category, target, days = cat, tgt, dd
                break
        out.append({
            "text": text,
            "category": category or "运营跟进",
            "target": target,
            "days": days,
            "owner": "",
            "game": game,
        })
    return out


def commit_actions(actions, game=None, version_id=None):
    """
    把建议动作写回业务表：任务进 checklists、风险进 risks —— 早报闭环。

    幂等：同版本同名条目已存在则跳过（重复点「转待办」不会堆积）。
    返回 dict：tasks / risks / skipped。
    """
    from datetime import timedelta

    if not actions:
        return {"tasks": 0, "risks": 0, "skipped": 0}

    if version_id is None:
        v = latest_version(game)
        version_id = v["id"] if v else None
    if version_id is None:
        return {"tasks": 0, "risks": 0, "skipped": len(list(actions))}

    plan = action_plan(actions, game)
    today = datetime.strptime(date_str(), "%Y-%m-%d").date()
    n_task = n_risk = n_skip = 0

    for item in plan:
        text = item["text"]
        if item["target"] == "risk":
            exists = query(
                "SELECT id FROM risks WHERE version_id=? AND title=?",
                (version_id, text), one=True)
            if exists:
                n_skip += 1
                continue
            execute(
                "INSERT INTO risks (version_id,title,probability,impact,"
                "mitigation,contingency,owner,status) "
                "VALUES (?,?,'medium','medium',?,'',?,'open')",
                (version_id, text, text, item["owner"] or "运营"))
            n_risk += 1
        else:
            exists = query(
                "SELECT id FROM checklists WHERE version_id=? AND task=?",
                (version_id, text), one=True)
            if exists:
                n_skip += 1
                continue
            deadline = str(today + timedelta(days=item["days"]))
            execute(
                "INSERT INTO checklists "
                "(version_id,task,category,assignee,deadline,status) "
                "VALUES (?,?,?,?,?,'pending')",
                (version_id, text, item["category"],
                 item["owner"] or "", deadline))
            n_task += 1

    return {"tasks": n_task, "risks": n_risk, "skipped": n_skip}


def _ai_polish(narrative, findings_text):
    """
    LLM 润色：只改表达，不改事实。
    任何失败（无 Key / 无网 / 超时）返回 None，调用方回退规则模板 ——
    智能体的产出链路永远可用，不依赖外部服务。
    """
    token = load_config("ai_api_key")
    if not token:
        return None
    try:
        from openai import OpenAI
        base = load_config("ai_base_url", "https://api.deepseek.com") \
            or "https://api.deepseek.com"
        client = OpenAI(api_key=token, base_url=base, timeout=45)
        resp = client.chat.completions.create(
            model=load_config("ai_model", "deepseek-chat"),
            temperature=0.4,
            messages=[
                {"role": "system",
                 "content": "你是游戏社区运营助手。把用户给的结构化巡检结果改写成"
                            "一段 120 字以内、面向运营负责人的中文早报正文。"
                            "先结论后细节，保留关键数字，语气克制专业；"
                            "只改表达，严禁编造数据里没有的信息。"},
                {"role": "user",
                 "content": f"巡检结果：\n{findings_text}\n\n规则版草稿：\n{narrative}"},
            ])
        text = (resp.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════
#  主流程：感知 → 决策 → 行动 → 产出
# ═══════════════════════════════════════════════════════

def generate(use_ai=None):
    """
    生成今日早报。use_ai=None 时按「是否配置了 Key」自动决定。
    返回结构化 dict（UI 渲染用），trace 记录全部决策轨迹。
    """
    trace = []
    alerts = []      # {"level": "danger|warn|info", "text": str}
    actions = []
    ups = []

    # ── 感知 ──
    trace.append("感知：检查数据新鲜度（最后数据日 vs 今天）")
    fresh = _freshness()

    trace.append("感知：读取当前版本上下文（版本 / 任务 / 预算）")
    version = latest_version()
    overdue = _overdue_count(version["id"]) if version else 0
    budget_pct = _budget_usage(version["id"]) if version else None

    trace.append("感知：扫描指标异动（最近数据日 vs 前 7 日均值）")
    anomalies = anomaly_report()

    trace.append("感知：留存趋势（近 7 天均值 vs 前 7 天均值）")
    ret_cur = retention_stats(date_str(days_ago(7)), date_str())
    ret_prev = retention_stats(date_str(days_ago(14)), date_str(days_ago(7)))

    has_data = fresh is not None

    # ── 决策路由 + 行动 ──
    ret_drop = None
    if ret_cur["r1"] and ret_prev["r1"]:
        ret_drop = round(ret_cur["r1"] - ret_prev["r1"], 1)
        if ret_drop <= RET_DROP_PP:
            alerts.append({
                "level": "danger",
                "text": f"次日留存近 7 天均值 {ret_cur['r1']:.1f}%，"
                        f"环比 {ret_drop:+.1f}pp",
            })
            # 路由：留存下滑 → 才去交叉查询互动率（无事不查，省查询也保可解释）
            trace.append("决策：留存下滑 → 路由到互动率交叉归因")
            rate_delta = _cross_interaction()
            trace.append(f"行动：互动率交叉检查 → {'+' if (rate_delta or 0) >= 0 else ''}"
                         f"{rate_delta if rate_delta is not None else '数据不足'}pp")
        else:
            rate_delta = None
            trace.append("决策：留存环比在阈值内 → 不触发交叉归因")
    else:
        rate_delta = None
        trace.append("决策：留存数据不足（老数据未统计或天数不够）→ 跳过")

    for a in anomalies:
        if a["down"]:
            text = f"{a['metric']}异动：{a['change']}（vs 前 7 日均值）"
            if a["note"]:
                text += f"；{a['note']}"
            alerts.append({"level": "warn", "text": text})
            act = ANOMALY_ACTIONS.get(a["metric"])
            if act:
                actions.append(act)
        else:
            ups.append(f"{a['metric']}{a['change']}")

    if overdue:
        alerts.append({
            "level": "warn",
            "text": f"有 {overdue} 项任务已逾期（当前版本）",
        })
        actions.append("先清逾期任务，再排今日新工作")
    if budget_pct is not None and budget_pct >= BUDGET_USAGE_WARN:
        alerts.append({
            "level": "danger" if budget_pct >= 100 else "warn",
            "text": f"预算使用率 {budget_pct:.0f}%，注意超支风险",
        })
        actions.append("复核剩余预算与未完事项的匹配度")
    if fresh and fresh["late"] >= FRESH_WARN_DAYS:
        alerts.append({
            "level": "info",
            "text": f"数据已 {fresh['late']} 天未更新（最后数据日 {fresh['last']}），"
                    "异动与留存可能失真",
        })
        actions.append("先补录数据再看结论")

    if not has_data:
        actions = ["去「数据」页录入，或点击「载入演示数据」"]

    ctx = {
        "has_data": has_data,
        "game": version["game"] if version else "",
        "version": version["version"] if version else "",
        "day": (datetime.now() - datetime.strptime(str(version["start_date"]),
               "%Y-%m-%d")).days if version else 0,
        "ret_cur": ret_cur["r1"],
        "ret_drop": ret_drop,
        "rate_delta": rate_delta,
        "alerts": alerts,
        "actions": actions,
        "ups": ups,
    }

    narrative = compose(ctx)
    trace.append("产出：规则模板拼装正文")

    ai_polished = False
    if use_ai is None:
        use_ai = bool(load_config("ai_api_key"))
    if use_ai and has_data:
        findings = "\n".join(
            [f"- {a['level'].upper()}: {a['text']}" for a in alerts]
            + ([f"- 上涨: {u}" for u in ups])
            + [f"- 次留7日均值: {ret_cur['r1']:.1f}%" if ret_cur["r1"] else ""]
            + [f"- 预算使用率: {budget_pct:.0f}%" if budget_pct is not None else ""])
        polished = _ai_polish(narrative, findings)
        if polished:
            narrative, ai_polished = polished, True
            trace.append("产出：LLM 润色成功（事实层未改动，失败会自动回退）")

    # ── headline ──
    if not has_data:
        headline = "暂无运营数据 —— 先录入或载入演示数据"
    elif alerts:
        n_danger = sum(1 for a in alerts if a["level"] == "danger")
        headline = (f"{ctx['game']} {ctx['version']} · "
                    f"{'⚠ ' if n_danger else ''}{len(alerts)} 项需要出手")
    else:
        headline = f"{ctx['game']} {ctx['version']} · 指标平稳，无需干预"

    return {
        "ok": True,
        "generated_at": datetime.now().strftime("%m-%d %H:%M"),
        "headline": headline,
        "has_data": has_data,
        "game": ctx.get("game") or None,      # 供「转待办」定位版本
        "version": ctx.get("version") or None,
        "alerts": alerts,
        "actions": actions,
        "trace": trace,
        "narrative": narrative,
        "ai_polished": ai_polished,
        "ret_cur": ret_cur["r1"],
        "budget_pct": budget_pct,
        "overdue": overdue,
    }
