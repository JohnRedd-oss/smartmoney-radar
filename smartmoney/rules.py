# -*- coding: utf-8 -*-
"""smartmoney.rules — 事实 → 一句话。

设计原则：
1. 每条句子必须可溯源，句末挂 [源|置信|滞后]。
2. 没有数字支撑的结论不产出句子，只产出「观察」。
3. 句子分两类：CHANGE（今日变化）和 STATE（当前状态）。
   CHANGE 才是日报主角，STATE 是背景板。
"""
import json
from datetime import datetime, timedelta

from .core import save_signal


def _fmt_yi(v_usd):
    """美元 → 亿"""
    if v_usd is None:
        return "—"
    return f"{v_usd:.1f}亿"


def _fmt_num(v, nd=0):
    if v is None:
        return "—"
    if nd == 0:
        return f"{v:,.0f}"
    return f"{v:,.{nd}f}"


def _money(cny_yi):
    """元 → 人类可读：小于 1 亿用万元。"""
    if cny_yi is None:
        return "—"
    if abs(cny_yi) < 1:
        return f"{cny_yi*10000:,.0f} 万元"
    return f"{cny_yi:.2f} 亿元"


# ------------------------------------------------------------------ 规则：央行黄金
def rule_pboc_gold(con, window_days=45):
    """央行增持黄金 → 一句话 + 成本估算。"""
    rows = con.execute(
        "SELECT ts, value, detail FROM facts WHERE entity='PBOC' "
        "AND metric='gold_reserve_wan_oz' ORDER BY ts DESC LIMIT 14").fetchall()
    if len(rows) < 2:
        return []

    out = []
    latest, prev = rows[0], rows[1]
    delta = (latest["value"] or 0) - (prev["value"] or 0)
    period = latest["ts"][:7]

    # 累计增持（年初至今）
    year = period[:4]
    ytd_rows = [r for r in rows if r["ts"].startswith(year)]
    ytd = (ytd_rows[0]["value"] - ytd_rows[-1]["value"]) if len(ytd_rows) > 1 else 0

    # 连续增持月数
    streak = 0
    for i in range(len(rows) - 1):
        d = (rows[i]["value"] or 0) - (rows[i + 1]["value"] or 0)
        if d > 0:
            streak += 1
        else:
            break

    # 成本估算：增量 × 同月金价（不用最新月，用数据所属月）
    def price_at(metric, ts):
        r = con.execute(
            "SELECT value FROM facts WHERE metric=? AND ts<=? ORDER BY ts DESC LIMIT 1",
            (metric, ts)).fetchone()
        return r["value"] if r else None

    usd_oz_val = price_at("price_usd_oz", latest["ts"])
    cny_g_val = price_at("price_cny_g", latest["ts"])

    cost_usd = None
    if usd_oz_val and delta:
        cost_usd = delta * 10000 * usd_oz_val / 1e8

    WAN_OZ_TO_TON = 0.3110348  # 1 万金衡盎司 = 0.3110348 吨

    sentence = (
        f"央行{period}黄金储备 {_fmt_num(latest['value'])} 万盎司，"
        f"环比 {delta:+,.0f} 万盎司（{delta*WAN_OZ_TO_TON:+.1f} 吨）"
    )
    if streak > 1:
        sentence += f"，连续第 {streak} 个月增持"
    sentence += (f"；年内累计 {ytd:+,.0f} 万盎司"
                 f"（{ytd*WAN_OZ_TO_TON:+.1f} 吨）")
    if cost_usd:
        sentence += (f"；按当月 {_fmt_num(usd_oz_val)} 美元/盎司估算，"
                     f"本月购金耗资约 {cost_usd:.0f} 亿美元")
    if cny_g_val:
        sentence += f"（沪金 {_fmt_num(cny_g_val, 1)} 元/克）"
    sentence += f"。 [源:SAFE官方储备资产|置信:高|滞后:0天]"

    out.append(("pboc_gold", latest["ts"], sentence, {
        "delta_wan_oz": delta, "ytd_wan_oz": ytd, "streak": streak,
        "cost_usd_yi": cost_usd}))

    # 异常检测：单月增量显著高于近 6 月均值
    recent = [(rows[i]["value"] or 0) - (rows[i + 1]["value"] or 0)
              for i in range(min(6, len(rows) - 1))]
    if recent:
        avg = sum(recent[1:]) / max(1, len(recent[1:])) if len(recent) > 1 else 0
        if avg and delta > avg * 2 and delta > 0:
            out.append(("pboc_gold_spike", latest["ts"],
                        f"央行购金提速：本月 {delta:+,.0f} 万盎司，为近 6 月均值的 {delta/avg:.1f} 倍。 "
                        f"[源:SAFE|置信:高|滞后:0天]",
                        {"delta": delta, "avg": avg}))
    return out


# ------------------------------------------------------------------ 规则：高管/股东减持
def rule_insider(con, date=None, top=5):
    date = date or con.execute(
        "SELECT MAX(ts) d FROM facts WHERE metric='insider_trade'").fetchone()["d"]
    if not date:
        return []
    rows = con.execute(
        "SELECT * FROM facts WHERE metric='insider_trade' AND ts=? "
        "ORDER BY ABS(value) DESC LIMIT 200", (date,)).fetchall()
    if not rows:
        return []

    sells = [r for r in rows if r["action"] == "sell"]
    buys = [r for r in rows if r["action"] == "buy"]

    def amt_yi(r):
        """优先用源给的成交额（元），缺失时用 股数×均价 估算。"""
        d = {}
        try:
            d = json.loads(r["detail"] or "{}")
        except Exception:
            pass
        cny = d.get("change_amount_cny")
        if cny:
            return abs(float(cny)) / 1e8
        return abs((r["value"] or 0) * (r["price"] or 0)) / 1e8

    sell_amt = sum(amt_yi(r) for r in sells)
    buy_amt = sum(amt_yi(r) for r in buys)

    out = []
    if sells or buys:
        s = (f"{date} A股高管增减持：减持 {len(sells)} 笔约 {_money(sell_amt)}，"
             f"增持 {len(buys)} 笔约 {_money(buy_amt)}，"
             f"净{'流出' if sell_amt>buy_amt else '流入'} "
             f"{_money(abs(sell_amt-buy_amt))}。")
        top_sell = max(sells, key=amt_yi, default=None)
        if top_sell:
            d = json.loads(top_sell["detail"] or "{}")
            s += (f" 最大单笔：{top_sell['entity']}（{d.get('stock')}·{d.get('position')}）"
                  f"减持 {abs(top_sell['value'] or 0)/1e4:.0f} 万股，"
                  f"均价 {top_sell['price']} 元，套现 {_money(amt_yi(top_sell))}。")
        s += " [源:东方财富高管持股|置信:高|滞后:1天]"
        out.append(("insider_daily", date, s, {
            "sell_cnt": len(sells), "buy_cnt": len(buys),
            "sell_amt_yi": sell_amt, "buy_amt_yi": buy_amt}))
    return out


# ------------------------------------------------------------------ 规则：大宗交易机构席位
def rule_block_trade(con, date=None):
    date = date or con.execute(
        "SELECT MAX(ts) d FROM facts WHERE metric='block_trade'").fetchone()["d"]
    if not date:
        return []
    rows = con.execute(
        "SELECT * FROM facts WHERE metric='block_trade' AND ts=? ORDER BY amount_usd DESC",
        (date,)).fetchall()
    if not rows:
        return []

    def cny_yi(r):
        try:
            d = json.loads(r["detail"] or "{}")
            return float(d.get("amount_cny") or 0) / 1e8
        except Exception:
            return 0.0

    total = sum(cny_yi(r) for r in rows)
    inst = [r for r in rows if "机构" in (r["entity"] or "")]
    inst_amt = sum(cny_yi(r) for r in inst)
    discount = [r for r in rows
                if (json.loads(r["detail"] or "{}").get("premium_ratio") or 0) < 0]

    s = (f"{date} 大宗交易 {len(rows)} 笔，成交 {_money(total)}；"
         f"机构专用席位买入 {len(inst)} 笔 {_money(inst_amt)}"
         f"（占比 {inst_amt/total*100 if total else 0:.0f}%），"
         f"折价成交 {len(discount)} 笔。")
    if inst:
        top = max(inst, key=cny_yi)
        d = json.loads(top["detail"] or "{}")
        s += (f" 机构最大买入：{d.get('stock')}（{d.get('code')}）"
              f"{_money(cny_yi(top))}，均价 {top['price']} 元，"
              f"卖方 {d.get('seller')}。")
    s += " [源:东方财富大宗交易|置信:高|滞后:1天]"
    return [("block_trade", date, s, {"total_cny_yi": total, "inst_cny_yi": inst_amt})]


# ------------------------------------------------------------------ 规则：13F 持仓变化
def rule_13f(con, entity=None):
    """13F QoQ diff：新增建仓、清仓、加仓、减仓。"""
    ents = [entity] if entity else [r["entity"] for r in con.execute(
        "SELECT DISTINCT entity FROM facts WHERE source='SEC 13F'").fetchall()]
    out = []
    for e in ents:
        periods = [r["ts"] for r in con.execute(
            "SELECT DISTINCT ts FROM facts WHERE entity=? AND source='SEC 13F' "
            "ORDER BY ts DESC LIMIT 2", (e,)).fetchall()]
        if len(periods) < 2:
            continue
        cur, prev = periods[0], periods[1]
        c = {r["metric"]: r for r in con.execute(
            "SELECT * FROM facts WHERE entity=? AND ts=? AND source='SEC 13F'",
            (e, cur)).fetchall()}
        p = {r["metric"]: r for r in con.execute(
            "SELECT * FROM facts WHERE entity=? AND ts=? AND source='SEC 13F'",
            (e, prev)).fetchall()}
        if not c:
            continue

        new_pos = [c[k] for k in c if k not in p]
        closed = [p[k] for k in p if k not in c]
        added, cut = [], []
        for k in c:
            if k in p:
                dv = (c[k]["value"] or 0) - (p[k]["value"] or 0)
                if dv > 0:
                    added.append((c[k], dv))
                elif dv < 0:
                    cut.append((c[k], dv))

        total_now = sum(r["amount_usd"] or 0 for r in c.values()) / 1e8
        total_prev = sum(r["amount_usd"] or 0 for r in p.values()) / 1e8

        s = (f"{e} 13F {prev}→{cur}：持仓 {len(p)}→{len(c)} 只，"
             f"市值 {total_prev:,.0f}→{total_now:,.0f} 亿美元")
        if new_pos:
            biggest_new = max(new_pos, key=lambda r: r["amount_usd"] or 0)
            try:
                dn = json.loads(biggest_new["detail"] or "{}").get("issuer") or biggest_new["metric"]
            except Exception:
                dn = biggest_new["metric"]
            s += (f"；新建仓 {len(new_pos)} 只（最大 {dn} "
                  f"{(biggest_new['amount_usd'] or 0)/1e8:.1f} 亿美元）")
        if closed:
            s += f"；清仓 {len(closed)} 只"
        if added:
            top = max(added, key=lambda x: x[1])
            s += f"；加仓 {len(added)} 只"
        if cut:
            s += f"；减仓 {len(cut)} 只"
        s += " [源:SEC 13F|置信:高|滞后:45天]"
        out.append(("13f_diff", cur, s, {
            "new": [r["metric"] for r in new_pos],
            "closed": [r["metric"] for r in closed],
            "total_now_usd_yi": total_now, "total_prev_usd_yi": total_prev}))
    return out


# ------------------------------------------------------------------ 规则：公告关键词
WATCH_PAT = ("控股股东", "实际控制人", "实控人", "董事长", "董事", "监事", "高管",
             "总经理", "大股东", "5%以上股东", "持股5%")
# 否定式：标题里有这些词说明「没减持」「不减持」「终止减持」，不能算卖出信号
NEG_PAT = ("未减持", "不减持", "未实施", "终止减持", "提前终止", "承诺不", "放弃减持",
           "不存在减持", "无减持", "未发生")


def rule_announcements(con, date=None, limit=8):
    date = date or con.execute(
        "SELECT MAX(ts) d FROM facts WHERE metric='announcement'").fetchone()["d"]
    if not date:
        return []
    rows = con.execute(
        "SELECT * FROM facts WHERE metric='announcement' AND ts=? "
        "AND action IN ('sell','buy') LIMIT 500", (date,)).fetchall()
    if not rows:
        return []

    def title(r):
        return json.loads(r["detail"] or "{}").get("title", "")

    def is_neg(r):
        t = title(r)
        return any(p in t for p in NEG_PAT)

    real = [r for r in rows if not is_neg(r)]
    negated = len(rows) - len(real)
    key_rows = [r for r in real if any(p in title(r) for p in WATCH_PAT)]
    sells = [r for r in key_rows if r["action"] == "sell"]
    buys = [r for r in key_rows if r["action"] == "buy"]

    msg = (f"{date} 公告扫描：命中 {len(rows)} 条，剔除否定式（未减持/终止减持等）{negated} 条，"
           f"涉及控股股东/实控人/董监高 {len(key_rows)} 条"
           f"（减持 {len(sells)}、增持/回购 {len(buys)}）。")
    if sells:
        names = "；".join(f"{json.loads(r['detail'] or '{}').get('code')} "
                         f"{title(r)[:30]}" for r in sells[:3])
        msg += f" 减持：{names}。"
    msg += " [源:巨潮资讯|置信:高|滞后:0天]"
    return [("announcements", date, msg,
             {"hit": len(rows), "negated": negated, "key": len(key_rows),
              "sell": len(sells), "buy": len(buys)})]


# ------------------------------------------------------------------ 规则：政府收储
def rule_shouchu(con, days=30):
    """政府/城投收储：土地收储、房产收储。

    注意：这是「政府从企业手里收资产」，不是「政府从居民手里收商品房」。
    两者在公告里都写「收储」，必须区分 —— 这是数据源最容易出错的地方。
    """
    rows = con.execute(
        "SELECT * FROM facts WHERE metric='announcement' ORDER BY ts DESC LIMIT 800").fetchall()
    hits = []
    for r in rows:
        d = json.loads(r["detail"] or "{}")
        t = d.get("title", "")
        if "收储" not in t:
            continue
        hits.append((r["ts"], r["entity"], t))
    if not hits:
        return []

    cutoff = hits[0][0]
    recent = [h for h in hits if h[0] >= cutoff[:4] + "-" + str(
        max(1, int(cutoff[5:7]) - 1)).zfill(2) + "-01"]
    by_ent = {}
    for ts, ent, t in recent:
        by_ent.setdefault(ent, []).append(ts)

    land = [h for h in recent if "土地" in h[2]]
    house = [h for h in recent if "商品房" in h[2] or "存量房" in h[2]]

    s = (f"近 30 天收储类公告 {len(recent)} 条，涉及 {len(by_ent)} 家上市公司；"
         f"其中土地收储 {len(land)} 条、商品房/存量房收储 {len(house)} 条。")
    top = sorted(by_ent.items(), key=lambda kv: -len(kv[1]))[:3]
    if top:
        s += " 高频主体：" + "、".join(f"{k}({len(v)}次)" for k, v in top) + "。"
    if house:
        s += " ⚠ 出现商品房收储信号，需人工核验是否为国家收储入市。"
    s += " [源:巨潮资讯|置信:中|滞后:0天]"
    return [("shouchu", recent[0][0], s, {
        "total": len(recent), "land": len(land), "house": len(house),
        "entities": {k: len(v) for k, v in by_ent.items()}})]


# ------------------------------------------------------------------ 规则：聪明钱下场买了什么
CAMP_ORDER = ["北向资金", "汇金证金", "社保养老金", "国资平台",
              "险资", "外资", "公募", "其他机构"]


def rule_smart_buy(con, days=60, top=6):
    """谁在买、买了什么、多少钱。

    取最近 days 天内披露的报告期，而不是只取 MAX(ts) —— 季报披露是分散的，
    只取最新一天会漏掉绝大部分动作。
    """
    from datetime import datetime, timedelta
    latest = con.execute(
        "SELECT MAX(ts) d FROM facts WHERE metric='holder_buy'").fetchone()["d"]
    if not latest:
        return []
    try:
        cutoff = (datetime.strptime(latest, "%Y-%m-%d")
                  - timedelta(days=days)).strftime("%Y-%m-%d")
    except ValueError:
        cutoff = latest

    rows = con.execute(
        "SELECT * FROM facts WHERE metric='holder_buy' AND ts>=? "
        "ORDER BY amount_usd DESC LIMIT 1200", (cutoff,)).fetchall()
    if not rows:
        return []

    by_camp = {}
    for r in rows:
        try:
            d = json.loads(r["detail"] or "{}")
        except Exception:
            d = {}
        by_camp.setdefault(d.get("camp", "其他机构"), []).append((r, d))

    out = []
    total_usd = sum((r["amount_usd"] or 0) for r in rows)
    # 人民币口径更直观（A股市值本来就用元）
    total_cny = 0.0
    for r in rows:
        try:
            total_cny += float(json.loads(r["detail"] or "{}").get("market_cap_cny") or 0)
        except Exception:
            pass

    camps = [c for c in CAMP_ORDER if c in by_camp]
    s = (f"{cutoff}~{latest} 期间，十大流通股东新进/加仓 {len(rows)} 笔，"
         f"合计市值 {total_cny/1e8:,.0f} 亿元。")
    if camps:
        s += " 阵营：" + "、".join(
            f"{c} {len(by_camp[c])}笔" for c in camps[:5]) + "。"
    # 点名全局最大单笔
    r0 = max(rows, key=lambda r: r["amount_usd"] or 0)
    try:
        d0 = json.loads(r0["detail"] or "{}")
    except Exception:
        d0 = {}
    s += (f" 最大单笔：{d0.get('stock')}（{d0.get('state')}·{d0.get('camp')}）"
          f"{r0['entity'][:22]} 持仓 {(r0['amount_usd'] or 0):,.1f} 亿美元。")
    s += " [源:东方财富十大流通股东|置信:高|滞后:30天]"
    out.append(("smart_buy", latest, s, {
        "total_usd_yi": total_usd, "total_cny_yi": total_cny / 1e8,
        "count": len(rows), "camps": {c: len(by_camp[c]) for c in by_camp},
        "window_days": days}))

    # 每个阵营一句，按合计金额排
    ranked = sorted(camps, key=lambda c: -sum(
        (r["amount_usd"] or 0) for r, _ in by_camp[c]))
    for camp in ranked[:5]:
        items = sorted(by_camp[camp], key=lambda x: -(x[0]["amount_usd"] or 0))
        usd = sum((r["amount_usd"] or 0) for r, _ in items)
        if usd < 0.05:      # 太小不单独出句
            continue
        heads = "；".join(
            f"{d.get('stock')} {d.get('state')} {(r['amount_usd'] or 0):,.1f}亿$"
            for r, d in items[:3])
        out.append((f"smartbuy:{camp}", latest,
                    f"{camp} {len(items)} 笔，合计 {usd:,.1f} 亿美元。{heads}。"
                    f" [源:东财十大流通股东|置信:高|滞后:30天]",
                    {"count": len(items), "usd_yi": usd}))
    return out


# ------------------------------------------------------------------ 规则：多资产行情
GROUP_ORDER = ["贵金属", "工业金属", "能源", "股指", "汇率", "债券"]


def rule_assets(con):
    """多资产行情一句话：黄金、铜、原油、股指、汇率、债。"""
    date = con.execute(
        "SELECT MAX(ts) d FROM facts WHERE metric LIKE 'quote:%'").fetchone()["d"]
    if not date:
        return []
    rows = con.execute(
        "SELECT * FROM facts WHERE metric LIKE 'quote:%' AND ts=? ORDER BY entity",
        (date,)).fetchall()
    if not rows:
        return []

    items = []
    for r in rows:
        try:
            d = json.loads(r["detail"] or "{}")
        except Exception:
            d = {}
        items.append({"name": r["entity"].replace("ASSET:", ""), "value": r["value"],
                      "unit": r["unit"], "chg": d.get("chg_pct", 0),
                      "group": d.get("group", "其他")})

    grouped = {}
    for it in items:
        grouped.setdefault(it["group"], []).append(it)

    out = []
    # 黄金单独一句（核心资产）
    golds = grouped.get("贵金属", [])
    if golds:
        s = "贵金属：" + "；".join(
            f"{g['name']} {g['value']:,.2f} {g['unit']}（{g['chg']:+.2f}%）"
            for g in golds)
        s += " [源:东方财富行情|置信:高|滞后:0天]"
        out.append(("assets_metals", date, s, {"items": golds}))

    # 其余合并
    others = []
    for grp in ["工业金属", "能源", "股指", "汇率", "债券"]:
        for it in grouped.get(grp, []):
            others.append(it)
    if others:
        s = "其他资产：" + "；".join(
            f"{o['name']} {o['value']:,.2f}（{o['chg']:+.2f}%）" for o in others[:8])
        s += " [源:东方财富行情|置信:高|滞后:0天]"
        out.append(("assets_other", date, s, {"items": others}))
    return out


# ------------------------------------------------------------------ 汇总
ALL_RULES = [
    ("pboc_gold", rule_pboc_gold),
    ("smart_buy", rule_smart_buy),
    ("insider", rule_insider),
    ("block_trade", rule_block_trade),
    ("13f", rule_13f),
    ("announcements", rule_announcements),
    ("shouchu", rule_shouchu),
    ("assets", rule_assets),
]


def run_all(con):
    """跑全部规则，落库，返回句子列表。"""
    produced = []
    for name, fn in ALL_RULES:
        try:
            items = fn(con)
        except Exception as e:
            produced.append(("_error", name, f"规则 {name} 异常：{type(e).__name__}: {e}", None))
            continue
        for rule, ts, sentence, payload in items:
            save_signal(con, ts, rule, sentence, payload)
            produced.append((rule, ts, sentence, payload))
    con.commit()
    return produced
