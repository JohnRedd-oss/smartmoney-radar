# -*- coding: utf-8 -*-
"""smartmoney.web — 浏览器界面。

启动：
    python -m smartmoney.web              # 默认 http://127.0.0.1:8848
    python -m smartmoney.web --port 9000
    python -m smartmoney.web --host 0.0.0.0

接口：
    GET  /api/summary        一句话摘要 + 覆盖率
    GET  /api/gold           央行黄金储备时序（含环比、成本估算）
    GET  /api/holdings       13F 持仓明细与对比
    GET  /api/trades         大宗交易 + 高管增减持
    GET  /api/announcements  公告扫描
    POST /api/collect        触发一次采集（同步）
"""
import argparse
import json
import os
import sys
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from .core import db, now_cst
from . import rules
from .cli import collect, STEPS

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="聪明钱雷达", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------- 工具
def _con():
    return db()


def _rows(con, sql, args=()):
    con.row_factory = None
    return con.execute(sql, args).fetchall()


def _latest_ts(con, metric):
    r = _rows(con, "SELECT MAX(ts) FROM facts WHERE metric=?", (metric,))
    return r[0][0] if r and r[0][0] else None


# ---------------------------------------------------------------- 接口
@app.get("/api/summary")
def api_summary():
    con = _con()
    try:
        signals = rules.run_all(con)
        con.commit()

        heads = []
        errs = []
        for rule, ts, sentence, payload in signals:
            if rule == "_error":
                errs.append({"rule": ts, "error": sentence})
                continue
            heads.append({"rule": rule, "ts": ts, "sentence": sentence,
                          "head": sentence.split("；")[0].split("。")[0],
                          "payload": payload})

        # 自动生成一段总述：把最重要的几个数字拼起来
        narrative = []
        gold = next((h for h in heads if h["rule"] == "pboc_gold"), None)
        if gold and gold["payload"]:
            p = gold["payload"]
            narrative.append(
                f"央行连续 {p.get('streak', 0)} 个月增持黄金，"
                f"年内累计 {p.get('ytd_wan_oz', 0):+,.0f} 万盎司，"
                f"本月估算耗资 {p.get('cost_usd_yi', 0):.0f} 亿美元。")
        f13 = next((h for h in heads if h["rule"] == "13f_diff"), None)
        if f13 and f13["payload"]:
            p = f13["payload"]
            narrative.append(
                f"国家资本海外持仓市值由 {p.get('total_prev_usd_yi', 0):,.0f} "
                f"亿美元升至 {p.get('total_now_usd_yi', 0):,.0f} 亿美元，"
                f"新建仓 {len(p.get('new', []))} 只、清仓 {len(p.get('closed', []))} 只。")
        blk = next((h for h in heads if h["rule"] == "block_trade"), None)
        if blk and blk["payload"]:
            p = blk["payload"]
            ratio = (p.get("inst_cny_yi", 0) / p["total_cny_yi"] * 100) if p.get("total_cny_yi") else 0
            narrative.append(
                f"最近交易日大宗交易 {p.get('total_cny_yi', 0):.2f} 亿元，"
                f"机构专用席位占 {ratio:.0f}%。")

        stats = _rows(con, """
            SELECT (SELECT COUNT(*) FROM facts) f,
                   (SELECT COUNT(*) FROM signals) s,
                   (SELECT COUNT(*) FROM runs) r,
                   (SELECT COUNT(DISTINCT entity) FROM facts) e
        """)[0]

        last_run = _rows(con, "SELECT started, ended, ok, stats FROM runs ORDER BY id DESC LIMIT 1")
        LABELS = {
            "safe_gold": ("央行黄金储备", "外汇局官方储备资产 xlsx"),
            "gold_price": ("金价序列", "东方财富月线"),
            "cninfo": ("公告扫描", "巨潮全文检索"),
            "insider": ("高管增减持", "东方财富高管持股"),
            "block": ("大宗交易", "东方财富逐笔"),
            "13f": ("13F 持仓", "SEC EDGAR"),
            "land": ("土地成交", "中国土地市场网"),
        }

        def human(name, v):
            """把采集器返回值压成一句人话，不把原始 JSON 丢给界面。"""
            if isinstance(v, str) and v.startswith("FAIL"):
                return v[:120]
            if v is None:
                return "未运行"
            try:
                if name == "safe_gold" and isinstance(v, dict):
                    return f"解析 {v.get('months','?')} 个月度数据"
                if name == "gold_price" and isinstance(v, dict):
                    return "、".join(f"{k} {n} 根" for k, n in v.items())
                if name == "cninfo" and isinstance(v, dict):
                    return "关键词 " + "、".join(f"{k}{n}条" for k, n in v.items())
                if name in ("insider", "block") and isinstance(v, dict):
                    return f"{v.get('rows','?')} 条记录"
                if name == "13f" and isinstance(v, dict):
                    return f"{len(v)} 个报告期持仓"
                if name == "land" and isinstance(v, dict):
                    return f"{v.get('rows','?')} 宗成交"
            except Exception:
                pass
            return str(v)[:100]

        health = []
        if last_run:
            try:
                st = json.loads(last_run[0][3] or "{}")
            except Exception:
                st = {}
            for name, _fn in STEPS:
                label, src = LABELS.get(name, (name, ""))
                v = st.get(name)
                ok = (None if v is None else
                      not (isinstance(v, str) and v.startswith("FAIL")))
                health.append({"source": name, "label": label, "src": src,
                               "ok": ok, "detail": human(name, v)})
        else:
            health = [{"source": n, "label": LABELS.get(n, (n, ""))[0],
                       "src": LABELS.get(n, ("", ""))[1],
                       "ok": None, "detail": "未运行"} for n, _ in STEPS]

        return {
            "as_of": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
            "narrative": narrative,
            "headlines": heads,
            "errors": errs,
            "stats": {"facts": stats[0], "signals": stats[1],
                      "runs": stats[2], "entities": stats[3]},
            "health": health,
            "last_run": ({"started": last_run[0][0], "ended": last_run[0][1],
                          "ok": bool(last_run[0][2])} if last_run else None),
        }
    finally:
        con.close()


@app.get("/api/gold")
def api_gold():
    con = _con()
    try:
        rows = _rows(con, """
            SELECT ts, value, amount_usd FROM facts
            WHERE entity='PBOC' AND metric='gold_reserve_wan_oz'
            ORDER BY ts ASC
        """)
        series = []
        for i, (ts, oz, usd) in enumerate(rows):
            delta = None if i == 0 else oz - rows[i - 1][1]
            series.append({"month": ts[:7], "oz": oz, "usd": usd, "delta": delta})

        prices = _rows(con, """
            SELECT ts, metric, value FROM facts
            WHERE entity='MARKET' AND metric IN ('price_usd_oz','price_cny_g')
            ORDER BY ts ASC
        """)
        p_usd, p_cny = {}, {}
        for ts, m, v in prices:
            (p_usd if m == "price_usd_oz" else p_cny)[ts[:7]] = v

        # 用同月金价反推购金成本
        for s in series:
            price = p_usd.get(s["month"])
            s["price_usd"] = price
            s["price_cny"] = p_cny.get(s["month"])
            s["cost_usd"] = (s["delta"] * 10000 * price / 1e8) if (s["delta"] and price) else None

        cur = series[-1] if series else None
        ytd = None
        if len(series) >= 2:
            year = series[-1]["month"][:4]
            same = [s for s in series if s["month"].startswith(year)]
            if len(same) > 1:
                ytd = same[-1]["oz"] - same[0]["oz"]

        return {"series": series, "current": cur, "ytd_wan_oz": ytd,
                "ton_per_wan_oz": 0.3110348}
    finally:
        con.close()


@app.get("/api/holdings")
def api_holdings():
    con = _con()
    try:
        rows = _rows(con, """
            SELECT entity, ts, metric, value, amount_usd, detail
            FROM facts WHERE source='SEC 13F' ORDER BY entity, ts DESC
        """)
        by = {}
        for ent, ts, metric, val, amt, detail in rows:
            d = {}
            try:
                d = json.loads(detail or "{}")
            except Exception:
                pass
            by.setdefault(ent, {}).setdefault(ts, []).append({
                "cusip": metric.split(":")[-1],
                "issuer": d.get("issuer", metric),
                "shares": val,
                "value_usd": amt,
                "filed": d.get("filed"),
            })

        out = []
        for ent, periods in by.items():
            plist = sorted(periods.keys(), reverse=True)
            latest = plist[0] if plist else None
            prev = plist[1] if len(plist) > 1 else None
            cur_pos = periods.get(latest, [])
            prev_map = {p["cusip"]: p for p in periods.get(prev, [])} if prev else {}

            positions = []
            for p in sorted(cur_pos, key=lambda x: -(x["value_usd"] or 0)):
                old = prev_map.get(p["cusip"])
                positions.append({
                    **p,
                    "prev_value_usd": old["value_usd"] if old else None,
                    "change": ("new" if not old else
                               "cut" if (p["value_usd"] or 0) < (old["value_usd"] or 0) else
                               "add"),
                })
            closed = [p for c, p in prev_map.items()
                      if c not in {x["cusip"] for x in cur_pos}]
            total_now = sum(p["value_usd"] or 0 for p in cur_pos) / 1e8
            total_prev = sum(p["value_usd"] or 0 for p in prev_map.values()) / 1e8 if prev_map else None

            out.append({"entity": ent, "period": latest, "prev_period": prev,
                        "total_usd_yi": total_now, "prev_total_usd_yi": total_prev,
                        "positions": positions, "closed": closed})
        return {"funds": out}
    finally:
        con.close()


@app.get("/api/trades")
def api_trades():
    con = _con()
    try:
        block_date = _latest_ts(con, "block_trade")
        block = []
        if block_date:
            rows = _rows(con, """
                SELECT entity, ts, value, price, detail FROM facts
                WHERE metric='block_trade' AND ts=? ORDER BY ts
            """, (block_date,))
            for buyer, ts, vol, price, detail in rows:
                d = {}
                try:
                    d = json.loads(detail or "{}")
                except Exception:
                    pass
                amt = float(d.get("amount_cny") or 0)
                block.append({"buyer": buyer, "stock": d.get("stock"),
                              "code": d.get("code"), "vol": vol, "price": price,
                              "amount_cny": amt,
                              "premium": d.get("premium_ratio"),
                              "seller": d.get("seller")})
            block.sort(key=lambda x: -x["amount_cny"])

        ins_date = _latest_ts(con, "insider_trade")
        ins = []
        if ins_date:
            rows = _rows(con, """
                SELECT entity, ts, value, price, detail FROM facts
                WHERE metric='insider_trade' AND ts=? 
            """, (ins_date,))
            for person, ts, shares, price, detail in rows:
                d = {}
                try:
                    d = json.loads(detail or "{}")
                except Exception:
                    pass
                ins.append({"person": person, "stock": d.get("stock"),
                            "code": d.get("code"), "position": d.get("position"),
                            "shares": shares, "price": price,
                            "amount_cny": d.get("change_amount_cny"),
                            "action": "sell" if (shares or 0) < 0 else "buy"})
            ins.sort(key=lambda x: -abs(x["amount_cny"] or 0))

        def agg_block(rows):
            tot = sum(r["amount_cny"] or 0 for r in rows)
            inst = [r for r in rows if "机构" in (r["buyer"] or "")]
            return {"count": len(rows), "total_cny": tot,
                    "inst_count": len(inst),
                    "inst_cny": sum(r["amount_cny"] or 0 for r in inst)}

        return {"block": {"date": block_date, "rows": block[:60],
                          "summary": agg_block(block)},
                "insider": {"date": ins_date, "rows": ins[:60],
                            "sell": len([r for r in ins if r["action"] == "sell"]),
                            "buy": len([r for r in ins if r["action"] == "buy"])}}
    finally:
        con.close()


@app.get("/api/announcements")
def api_announcements():
    con = _con()
    try:
        rows = _rows(con, """
            SELECT ts, entity, action, detail, source_url FROM facts
            WHERE metric='announcement' ORDER BY ts DESC LIMIT 200
        """)
        out = []
        for ts, ent, action, detail, url in rows:
            d = {}
            try:
                d = json.loads(detail or "{}")
            except Exception:
                pass
            t = d.get("title", "")
            out.append({"ts": ts, "entity": ent, "code": d.get("code"),
                        "title": t, "keyword": d.get("keyword"),
                        "action": action, "url": url,
                        "negated": any(p in t for p in rules.NEG_PAT),
                        "watch": any(p in t for p in rules.WATCH_PAT)})
        return {"rows": out}
    finally:
        con.close()


@app.get("/api/smartbuy")
def api_smartbuy(days=60, limit=80):
    """聪明钱下场买了什么：按阵营分组的买入清单。"""
    con = _con()
    try:
        latest = _rows(con, "SELECT MAX(ts) FROM facts WHERE metric='holder_buy'")
        latest = latest[0][0] if latest and latest[0][0] else None
        if not latest:
            return {"as_of": None, "camps": [], "rows": [], "summary": {}}
        from datetime import datetime, timedelta
        try:
            cutoff = (datetime.strptime(latest, "%Y-%m-%d")
                      - timedelta(days=int(days))).strftime("%Y-%m-%d")
        except ValueError:
            cutoff = latest

        raw = _rows(con, """
            SELECT entity, ts, value, amount_usd, detail FROM facts
            WHERE metric='holder_buy' AND ts>=?
            ORDER BY amount_usd DESC LIMIT 1200
        """, (cutoff,))

        rows = []
        for holder, ts, shares, usd, detail in raw:
            d = {}
            try:
                d = json.loads(detail or "{}")
            except Exception:
                pass
            rows.append({
                "holder": holder, "ts": ts, "stock": d.get("stock"),
                "code": d.get("code"), "camp": d.get("camp", "其他机构"),
                "state": d.get("state"), "shares": shares,
                "usd": usd or 0,
                "cny": (d.get("market_cap_cny") or 0),
                "ratio": d.get("hold_ratio"),
            })

        # 阵营聚合
        agg = {}
        for r in rows:
            a = agg.setdefault(r["camp"], {"camp": r["camp"], "count": 0,
                                           "usd": 0.0, "cny": 0.0, "stocks": []})
            a["count"] += 1
            a["usd"] += r["usd"]
            a["cny"] += r["cny"]
            a["stocks"].append(r)

        camps = sorted(agg.values(), key=lambda x: -x["usd"])
        for c in camps:
            c["top"] = sorted(c["stocks"], key=lambda x: -x["usd"])[:6]
            c["stocks"] = None

        total_cny = sum(r["cny"] for r in rows)
        total_usd = sum(r["usd"] for r in rows)
        return {
            "as_of": latest, "window_from": cutoff, "days": int(days),
            "camps": camps, "rows": rows[:int(limit)],
            "summary": {"count": len(rows), "cny_yi": total_cny / 1e8,
                        "usd_yi": total_usd},
        }
    finally:
        con.close()


@app.get("/api/assets")
def api_assets():
    """多资产行情看板。"""
    con = _con()
    try:
        date = _rows(con, "SELECT MAX(ts) FROM facts WHERE metric LIKE 'quote:%'")
        date = date[0][0] if date and date[0][0] else None
        if not date:
            return {"date": None, "groups": []}
        raw = _rows(con, """
            SELECT entity, value, unit, detail FROM facts
            WHERE metric LIKE 'quote:%' AND ts=? ORDER BY entity
        """, (date,))
        groups = {}
        for ent, val, unit, detail in raw:
            d = {}
            try:
                d = json.loads(detail or "{}")
            except Exception:
                pass
            g = d.get("group", "其他")
            groups.setdefault(g, []).append({
                "name": ent.replace("ASSET:", ""), "value": val, "unit": unit,
                "chg": d.get("chg_pct", 0),
            })
        order = ["贵金属", "工业金属", "能源", "股指", "汇率", "债券"]
        out = [{"group": g, "items": groups[g]}
               for g in order if g in groups]
        return {"date": date, "groups": out}
    finally:
        con.close()


@app.get("/api/region")
def api_region():
    """70 城房价指数：官方口径的分区域价格趋势。"""
    con = _con()
    try:
        month = _rows(con, "SELECT MAX(ts) FROM facts WHERE metric LIKE 'hp_%'")
        month = month[0][0] if month and month[0][0] else None
        if not month:
            return {"month": None, "cities": []}
        raw = _rows(con, """
            SELECT entity, metric, value FROM facts
            WHERE metric LIKE 'hp_%' AND ts=?
        """, (month,))
        by = {}
        for ent, metric, val in raw:
            city = ent.split(":", 1)[-1]
            by.setdefault(city, {"city": city})[metric] = val
        cities = list(by.values())
        for c in cities:
            c["new_yoy"] = c.get("hp_new_yoy")
            c["new_mom"] = c.get("hp_new_mom")
            c["snd_yoy"] = c.get("hp_2nd_yoy")
            c["snd_mom"] = c.get("hp_2nd_mom")
        cities.sort(key=lambda x: (x.get("snd_yoy") or 0))
        return {"month": month, "cities": cities,
                "note": "国家统计局70城，上年同月=100，>100为同比上涨"}
    finally:
        con.close()


@app.post("/api/collect")
def api_collect():
    try:
        stats = collect(skip={"land"})
        return {"ok": True, "stats": stats}
    except Exception as e:
        return JSONResponse(status_code=500,
                            content={"ok": False, "error": f"{type(e).__name__}: {e}"})


# ---------------------------------------------------------------- 页面
@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(STATIC_DIR, "index.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/static/{name}")
def static(name: str):
    path = os.path.join(STATIC_DIR, name)
    if not os.path.exists(path):
        return JSONResponse(status_code=404, content={"error": "not found"})
    return FileResponse(path)


def main(argv=None):
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8848)
    a = ap.parse_args(argv)
    print(f"聪明钱雷达 → http://{a.host}:{a.port}")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
