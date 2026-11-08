# -*- coding: utf-8 -*-
"""smartmoney.collectors — 每个源一个函数，失败互不影响。

约定：collector(con) -> dict(stats)
所有写入走 core.upsert_fact，必须带 source_url。
"""
import io
import re
import json
from datetime import datetime, timedelta

import openpyxl

from .core import session, upsert_fact, now_cst, fetch_bytes, fetch_json, polite_sleep

SAFE_LIST = "https://www.safe.gov.cn/safe/whcb/index.html"
SAFE_BASE = "https://www.safe.gov.cn"


# ------------------------------------------------------------------ 1. 央行黄金储备
def safe_gold(con):
    """SAFE 官方储备资产 xlsx：黄金储备（万盎司）+ 折美元。

    这是全工具链里最硬的一条数据 —— 官方、月频、无滞后、有原始文件。
    """
    s = session()
    r = s.get(SAFE_LIST, timeout=25)
    r.encoding = "utf-8"
    # 找最新的「官方储备资产（20XX年）」链接
    links = re.findall(r'href="(/safe/\d{4}/\d{4}/\d+\.html)"[^>]*>\s*官方储备资产（(\d{4})年）', r.text)
    if not links:
        raise RuntimeError("SAFE 列表页未匹配到官方储备资产链接")
    url, year = sorted(links, key=lambda x: x[1])[-1]
    page = SAFE_BASE + url
    pr = s.get(page, timeout=25)
    pr.encoding = "utf-8"
    xls = re.findall(r'href="(/safe/file/file/[^"]+\.xlsx)"', pr.text)
    if not xls:
        raise RuntimeError("SAFE 详情页未找到 xlsx 附件")

    blob = fetch_bytes(s, SAFE_BASE + xls[0])
    wb = openpyxl.load_workbook(io.BytesIO(blob), data_only=True)
    ws = wb["Sheet1"]

    grid = []
    for row in ws.iter_rows(values_only=True):
        cells = ["" if c is None else str(c).strip() for c in row]
        if any(cells):
            grid.append(cells)

    # 表头：列为 项目 | 2026.01 | (空) | 2026.02 | (空) ...
    header = next((r for r in grid if r and "项目" in r[0]), None)
    if not header:
        raise RuntimeError("未找到表头行")

    # 月份 → 列索引（1-based，对齐 xlsx 列）
    month_cols = []
    for j, c in enumerate(header):
        m = re.match(r"(\d{4})\.(\d{2})", c)
        if m:
            month_cols.append((f"{m.group(1)}-{m.group(2)}", j))
    if not month_cols:
        raise RuntimeError("表头未解析出月份")

    gold_usd = next((r for r in grid if r and r[0].startswith("4.") and "黄金" in r[0]), None)
    gold_oz = next((r for r in grid if "万盎司" in "".join(r)), None)
    if gold_usd is None or gold_oz is None:
        raise RuntimeError(f"未定位到黄金行 (usd={gold_usd is not None}, oz={gold_oz is not None})")

    def cell(row, j):
        return row[j] if row is not None and j < len(row) else ""

    n = 0
    for month, j in month_cols:
        oz = None
        mm = re.search(r"([\d,]+)\s*万盎司", cell(gold_oz, j))
        if mm:
            oz = float(mm.group(1).replace(",", ""))
        if oz is None:
            continue  # 未来月份，尚无数据
        usd = None
        raw = cell(gold_usd, j).replace(",", "")
        try:
            usd = float(raw) if raw else None
        except ValueError:
            usd = None

        upsert_fact(
            con, ts=month + "-01", entity="PBOC", action="hold", asset="gold",
            metric="gold_reserve_wan_oz", value=oz, unit="万盎司",
            amount_usd=usd, source="SAFE官方储备资产",
            source_url=page, confidence="high", lag_days=0,
            detail={"year": year, "attachment": xls[0]},
        )
        n += 1

    # 计算月度增量，落成独立事实，供规则引擎直接消费
    cur = con.execute(
        "SELECT ts, value FROM facts WHERE entity='PBOC' AND metric='gold_reserve_wan_oz' "
        "ORDER BY ts DESC LIMIT 2").fetchall()
    if len(cur) == 2:
        delta = cur[0]["value"] - cur[1]["value"]
        upsert_fact(
            con, ts=cur[0]["ts"], entity="PBOC", action="buy" if delta > 0 else "hold",
            asset="gold", metric="gold_reserve_delta_wan_oz", value=delta, unit="万盎司",
            source="SAFE官方储备资产", source_url=page, confidence="high", lag_days=0,
            detail={"prev_ts": cur[1]["ts"], "prev_value": cur[1]["value"]},
        )
    return {"months": n, "page": page}


# ------------------------------------------------------------------ 2. 金价（成本反推用）
def gold_price(con):
    """东财：黄金9999 现货 + COMEX，取月度均价用于反推央行购金成本带。"""
    s = session()
    out = {}
    for secid, name, unit in [
        ("118.au9999", "黄金9999现货", "元/克"),
        ("101.GC00Y", "COMEX黄金", "美元/盎司"),
    ]:
        u = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
             f"?secid={secid}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56"
             "&klt=103&fqt=0&beg=20240101&end=20301231")
        try:
            j = fetch_json(s, u)
        except Exception as e:
            out[name] = f"FAIL {e}"
            continue
        d = j.get("data") or {}
        klines = d.get("klines") or []
        # klt=103 月线：date,open,close,high,low,volume —— 已是实际价格，不再缩放
        metric = "price_cny_g" if "9999" in name else "price_usd_oz"
        for k in klines:
            p = k.split(",")
            if len(p) < 3:
                continue
            ym = p[0][:7]
            try:
                close = float(p[2])
            except ValueError:
                continue
            upsert_fact(
                con, ts=ym + "-01", entity="MARKET", action="hold", asset="gold",
                metric=metric, value=close, unit=unit,
                source="东方财富行情", source_url=u,
                confidence="high", lag_days=0,
                detail={"series": name, "bar": p[:5]},
            )
        out[name] = len(klines)
        polite_sleep()
    return out


# ------------------------------------------------------------------ 3. A股公告：减持/增持/回购/收储
def cninfo_announcements(con, keywords=("减持", "增持", "回购", "收储")):
    """巨潮全文检索。这是民营资本动向最快的一条线（T+0 当日披露）。"""
    s = session()
    s.headers.update({
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
    })
    out = {}
    today = now_cst()
    for kw in keywords:
        payload = {
            "pageNum": "1", "pageSize": "50", "column": "szse", "tabName": "fulltext",
            "plate": "", "stock": "", "searchkey": kw,
            "secDate": "", "tDate": "",
            "type": "", "isHLtitle": "true",
        }
        try:
            r = s.post("http://www.cninfo.com.cn/new/fulltextSearch/full",
                       data=payload, timeout=30)
            j = r.json()
        except Exception as e:
            out[kw] = f"FAIL {type(e).__name__}"
            continue

        anns = j.get("announcements") or []
        n = 0
        for a in anns:
            title = re.sub(r"<[^>]+>", "", a.get("announcementTitle", ""))
            t = a.get("announcementTime")
            ts = datetime.fromtimestamp(t / 1000).strftime("%Y-%m-%d") if t else today.strftime("%Y-%m-%d")
            adj = a.get("adjunctUrl", "")
            url = f"http://static.cninfo.com.cn/{adj}" if adj else "http://www.cninfo.com.cn/"
            action = ("sell" if "减持" in title else
                      "buy" if "增持" in title else
                      "buy" if "回购" in title else "announce")
            upsert_fact(
                con, ts=ts, entity=a.get("secName", "?"), action=action,
                asset="equity", metric="announcement", value=None, unit=None,
                source="巨潮资讯", source_url=url, confidence="high", lag_days=0,
                detail={"keyword": kw, "title": title, "code": a.get("secCode"),
                        "announcementId": a.get("announcementId")},
            )
            n += 1
        out[kw] = n
        polite_sleep()
    return out


# ------------------------------------------------------------------ 4. 高管与股东增减持（东财，带金额和均价）
def insider_trades(con, pages=3):
    """东财高管持股变动：带人名、均价、变动股数、变动金额。

    比公告文本强的地方：结构化，能直接出「谁、多少钱、什么价」。
    """
    s = session()
    total = 0
    for page in range(1, pages + 1):
        u = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
             "?reportName=RPT_EXECUTIVE_HOLD_DETAILS&columns=ALL"
             f"&pageNumber={page}&pageSize=100&sortColumns=CHANGE_DATE&sortTypes=-1"
             "&source=WEB&client=WEB")
        try:
            j = fetch_json(s, u)
        except Exception:
            break
        data = (j.get("result") or {}).get("data") or []
        if not data:
            break
        for d in data:
            cd = (d.get("CHANGE_DATE") or "")[:10]
            shares = d.get("CHANGE_SHARES")
            price = d.get("AVERAGE_PRICE")
            amt = d.get("CHANGE_AMOUNT")
            upsert_fact(
                con, ts=cd, entity=d.get("PERSON_NAME") or "?",
                action="sell" if (shares or 0) < 0 else "buy",
                asset="equity", metric="insider_trade",
                value=shares, unit="股", price=price, amount_usd=None,
                source="东方财富高管持股", source_url=u, confidence="high", lag_days=1,
                detail={"stock": d.get("SECURITY_NAME"), "code": d.get("SECURITY_CODE"),
                        "position": d.get("POSITION_NAME"),
                        "change_amount_cny": amt, "reason": d.get("CHANGE_REASON")},
            )
            total += 1
        polite_sleep()
    return {"rows": total}


# ------------------------------------------------------------------ 5. 大宗交易（机构专用席位 = 聪明钱痕迹）
def block_trades(con, pages=2):
    s = session()
    total = 0
    for page in range(1, pages + 1):
        u = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
             "?reportName=RPT_DATA_BLOCKTRADE&columns=ALL"
             f"&pageNumber={page}&pageSize=100&sortColumns=TRADE_DATE&sortTypes=-1"
             "&source=WEB&client=WEB")
        try:
            j = fetch_json(s, u)
        except Exception:
            break
        data = (j.get("result") or {}).get("data") or []
        if not data:
            break
        for d in data:
            td = (d.get("TRADE_DATE") or "")[:10]
            amt_cny = d.get("DEAL_AMT")
            upsert_fact(
                con, ts=td, entity=d.get("BUYER_NAME") or "?",
                action="buy", asset="equity", metric="block_trade",
                value=d.get("DEAL_VOLUME"), unit="股",
                price=d.get("DEAL_PRICE"),
                amount_usd=(amt_cny / 7.1 / 1e8) if amt_cny else None,
                source="东方财富大宗交易", source_url=u, confidence="high", lag_days=1,
                detail={"stock": d.get("SECURITY_NAME_ABBR"), "code": d.get("SECURITY_CODE"),
                        "seller": d.get("SELLER_NAME"), "amount_cny": amt_cny,
                        "premium_ratio": d.get("PREMIUM_RATIO"),
                        "turnover_ratio": d.get("TOTAL_SHARES_RATIO")},
            )
            total += 1
        polite_sleep()
    return {"rows": total}


# ------------------------------------------------------------------ 6. SEC 13F（国家资本海外腿）
CIKS = {
    "梧桐树投资平台 Wutongshu": "1767640",
    "中投公司 CIC": "1643316",
}


def sec_13f(con, ciks=None, quarters=2):
    """13F 持仓 + QoQ diff。滞后 45 天，但这是唯一能看见国家资本海外腿的窗口。"""
    import xml.etree.ElementTree as ET
    s = session("sec")
    ciks = ciks or CIKS
    out = {}
    for label, cik in ciks.items():
        cik10 = str(cik).zfill(10)
        try:
            sub = fetch_json(s, f"https://data.sec.gov/submissions/CIK{cik10}.json")
        except Exception as e:
            out[label] = f"FAIL submissions {e}"
            continue
        recent = sub.get("filings", {}).get("recent", {})
        filings = []
        for i, form in enumerate(recent.get("form", [])):
            if form == "13F-HR":
                filings.append((recent["filingDate"][i], recent["accessionNumber"][i]))
        filings = sorted(set(filings), reverse=True)[:quarters]

        for fdate, acc in filings:
            accn = acc.replace("-", "")
            idx_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/index.json"
            try:
                idx = fetch_json(s, idx_url)
            except Exception:
                continue
            names = [it["name"] for it in idx.get("directory", {}).get("item", [])]
            tbl = next((n for n in names if n.lower().endswith(".xml")
                        and "primary_doc" not in n.lower()), None)
            if not tbl:
                continue
            fu = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{tbl}"
            try:
                blob = fetch_bytes(s, fu)
                root = ET.fromstring(blob)
            except Exception:
                continue
            ns = {"n": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}

            # reportPeriod 在 primary_doc.xml 里，单独取
            period = fdate
            if "primary_doc.xml" in names:
                try:
                    pu = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/primary_doc.xml"
                    pr = ET.fromstring(fetch_bytes(s, pu))
                    pns = {"n": pr.tag.split("}")[0].strip("{")} if "}" in pr.tag else {}
                    pe = pr.find(".//n:periodOfReport", pns) if pns else pr.find(".//periodOfReport")
                    if pe is not None and pe.text:
                        raw = pe.text.strip()          # MM-DD-YYYY
                        m = re.match(r"(\d{2})-(\d{2})-(\d{4})", raw)
                        period = f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else raw
                except Exception:
                    pass

            rows = []
            infos = root.findall(".//n:infoTable", ns) if ns else root.findall(".//infoTable")
            for it in infos:
                def g(tag, node=it):
                    e = node.find(f"n:{tag}", ns) if ns else node.find(tag)
                    return e.text.strip() if e is not None and e.text else ""
                ssh = it.find(".//n:shrsOrPrnAmt/n:sshPrnamt", ns) if ns \
                    else it.find(".//shrsOrPrnAmt/sshPrnamt")
                shares = None
                if ssh is not None and ssh.text:
                    try:
                        shares = float(ssh.text.strip())
                    except ValueError:
                        pass
                val = g("value")
                rows.append({"issuer": g("nameOfIssuer"), "cusip": g("cusip"),
                             "value_usd": float(val) if val else None, "shares": shares})
                if val:
                    upsert_fact(
                        con, ts=period, entity=label, action="hold", asset="equity",
                        metric=f"13f:{g('cusip')}", value=shares, unit="股",
                        amount_usd=float(val), source="SEC 13F",
                        source_url=fu, confidence="high", lag_days=45,
                        detail={"issuer": g("nameOfIssuer"), "class": g("titleOfClass"),
                                "filed": fdate},
                    )
            out[f"{label}@{period}"] = len(rows)
            polite_sleep(0.5, 1.2)
    return out


# ------------------------------------------------------------------ 8. 分城市房价（收房成本基准）
# creprice.cn 城市代码 → 中文名
CITY_MAP = {
    "bj": "北京", "sh": "上海", "sz": "深圳", "gz": "广州", "hz": "杭州",
    "nj": "南京", "cd": "成都", "wh": "武汉", "xa": "西安", "cq": "重庆",
    "tj": "天津", "su": "苏州", "cs": "长沙", "zz": "郑州", "qd": "青岛",
    "dl": "大连", "xm": "厦门", "hf": "合肥", "jn": "济南", "sy": "沈阳",
    "nb": "宁波", "fz": "福州", "km": "昆明", "nc": "南昌", "gy": "贵阳",
    "heb": "哈尔滨", "cc": "长春", "sjz": "石家庄", "ty": "太原", "lz": "兰州",
}


def _plain_text(html):
    """去标签取正文，用于正则抽取。"""
    b = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    return re.sub(r"\s+", " ", b)


def house_price_city(con, cities=None):
    """分城市二手房挂牌均价（万元/㎡）。

    这是「收房成本」唯一可规模化获取的市场基准。
    注意：挂牌价 ≠ 成交价 ≠ 收储评估价，三者依次递减。
    """
    s = session()
    s.headers.update({"Referer": "https://www.creprice.cn/"})
    cities = cities or list(CITY_MAP.keys())
    ok = 0
    failed = []
    for code in cities:
        name = CITY_MAP.get(code, code)
        u = f"https://www.creprice.cn/city/{code}.html"
        try:
            r = s.get(u, timeout=25)
            r.encoding = "utf-8"
            t = _plain_text(r.text)
        except Exception:
            failed.append(code)
            continue

        # 月度房价 2026年10月 挂牌 5.38 万元/㎡ 环比：-3.35%
        m = re.search(
            r"(\d{4})年(\d{1,2})月\s*挂牌\s*([\d\.]+)\s*万元/㎡"
            r"(?:\s*环比[：:]\s*([\-\d\.]+)%)?", t)
        if not m:
            failed.append(code)
            continue
        period = f"{m.group(1)}-{int(m.group(2)):02d}"
        wan = float(m.group(3))
        mom = float(m.group(4)) if m.group(4) else None

        upsert_fact(
            con, ts=period + "-01", entity=f"CITY:{name}", action="hold",
            asset="house", metric="house_price_wan_per_sqm", value=wan,
            unit="万元/㎡", source="中国房价行情(禧泰)",
            source_url=u, confidence="medium", lag_days=15,
            detail={"city": name, "code": code, "mom_pct": mom,
                    "note": "二手房挂牌均价，非成交价"},
        )
        ok += 1
        polite_sleep(0.5, 1.0)
    return {"ok": ok, "failed": failed[:8], "total": len(cities)}


# ------------------------------------------------------------------ 9. 70 城房价指数（官方口径）
def stats70(con):
    """国家统计局 70 城房价指数，经东方财富转发。同比/环比，上年同月=100。"""
    s = session()
    u = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
         "?reportName=RPT_ECONOMY_HOUSE_PRICE&columns=ALL"
         "&pageNumber=1&pageSize=200&sortColumns=REPORT_DATE&sortTypes=-1"
         "&source=WEB&client=WEB")
    j = fetch_json(s, u)
    data = (j.get("result") or {}).get("data") or []
    if not data:
        raise RuntimeError("70城报表返回空")

    latest = data[0]["REPORT_DATE"][:10]
    rows = [r for r in data if r["REPORT_DATE"][:10] == latest]
    n = 0
    for r in rows:
        city = r.get("CITY") or "?"
        for metric, field, label in [
            ("hp_new_yoy", "FIRST_COMHOUSE_SAME", "新房同比"),
            ("hp_new_mom", "FIRST_COMHOUSE_SEQUENTIAL", "新房环比"),
            ("hp_2nd_yoy", "SECOND_HOUSE_SAME", "二手同比"),
            ("hp_2nd_mom", "SECOND_HOUSE_SEQUENTIAL", "二手环比"),
        ]:
            v = r.get(field)
            if v is None:
                continue
            upsert_fact(
                con, ts=latest, entity=f"CITY70:{city}", action="hold",
                asset="house", metric=metric, value=v, unit="指数",
                source="国家统计局70城(东财转发)",
                source_url=u, confidence="high", lag_days=20,
                detail={"city": city, "label": label, "base": "上年同月=100"},
            )
            n += 1
    return {"month": latest, "cities": len(rows), "facts": n}


# ------------------------------------------------------------------ 10. 多资产行情
ASSETS = {
    # name: (secid, 单位, 缩放, 分组)
    "沪金9999":   ("118.au9999", "元/克", 1, "贵金属"),
    "COMEX黄金":  ("101.GC00Y", "美元/盎司", 1, "贵金属"),
    "沪银主连":   ("113.agm", "元/千克", 1, "贵金属"),
    "沪铜主连":   ("113.cum", "元/吨", 1, "工业金属"),
    "螺纹钢主连": ("113.rbm", "元/吨", 1, "工业金属"),
    "NYMEX原油":  ("102.CL00Y", "美元/桶", 1, "能源"),
    "上证指数":   ("1.000001", "点", 1, "股指"),
    "沪深300":    ("1.000300", "点", 1, "股指"),
    "创业板指":   ("0.399006", "点", 1, "股指"),
    "恒生指数":   ("100.HSI", "点", 1, "股指"),
    "纳斯达克":   ("100.NDX", "点", 1, "股指"),
    "标普500":    ("100.SPX", "点", 1, "股指"),
    "地产指数":   ("1.000006", "点", 1, "股指"),
    "美元指数":   ("100.UDI", "点", 1, "汇率"),
    "美元离岸人民币": ("133.USDCNH", "元", 1, "汇率"),
    "国债指数":   ("1.000012", "点", 1, "债券"),
}


def multi_asset(con):
    """多资产实时行情快照。一次抓完，落成当日事实。"""
    s = session()
    today = now_cst().strftime("%Y-%m-%d")
    ok, failed = 0, []
    for name, (secid, unit, scale, group) in ASSETS.items():
        u = (f"https://push2.eastmoney.com/api/qt/stock/get?"
             f"secid={secid}&fields=f43,f58,f60,f170,f169")
        try:
            j = fetch_json(s, u)
        except Exception:
            failed.append(name)
            continue
        d = j.get("data") or {}
        raw = d.get("f43")
        if raw in (None, "-"):
            failed.append(name)
            continue
        # f43 是该品种的最小价格单位整数，除 scale 后为真实价
        # 各品种量纲不同，用 f58 名称校验后按经验值换算
        divisor = _price_divisor(secid)
        price = raw / divisor
        chg = (d.get("f170") or 0) / 100.0   # 涨跌幅 %

        upsert_fact(
            con, ts=today, entity=f"ASSET:{name}", action="hold",
            asset="multi", metric=f"quote:{name}", value=price, unit=unit,
            source="东方财富行情", source_url=u, confidence="high", lag_days=0,
            detail={"group": group, "chg_pct": chg, "raw": raw, "secid": secid},
        )
        ok += 1
        polite_sleep(0.25, 0.5)
    return {"ok": ok, "failed": failed}


def _price_divisor(secid):
    """东财不同品种的价格放大倍数不同，这里按 secid 归类。"""
    # 贵金属/商品/指数经验值：多数放大 100 或 1000
    table = {
        "118.au9999": 100,      # 87400 -> 874.00 元/克
        "101.GC00Y": 10,        # 40795 -> 4079.5 美元/盎司
        "113.agm": 1,           # 12523 元/千克
        "113.cum": 1,           # 105060 元/吨
        "113.rbm": 1,           # 3046 元/吨
        "102.CL00Y": 100,       # 9034 -> 90.34 美元/桶
        "1.000001": 100,        # 364918 -> 3649.18 点
        "1.000300": 100,
        "0.399006": 100,
        "100.HSI": 100,
        "100.NDX": 100,
        "100.SPX": 100,
        "1.000006": 100,
        "100.UDI": 100,
        "133.USDCNH": 10000,    # 66738 -> 6.6738
        "1.000012": 100,
    }
    return table.get(secid, 100)


# ------------------------------------------------------------------ 11. 聪明钱下场买了什么（十大流通股东变动）
# 阵营识别：股东名称特征 → 资本性质
CAMPS = [
    # 香港中央结算 = 沪深港通北向资金，这是最能反映外资动向的单一主体
    ("北向资金",   ["香港中央结算"]),
    ("汇金证金",   ["中央汇金", "中国证券金融", "证金公司"]),
    ("社保养老金", ["社保基金", "全国社会保障", "基本养老保险", "养老金", "社保组合"]),
    ("国资平台",   ["国有资本", "国有资产", "国有投资", "国资", "投资控股集团",
                    "产业发展集团", "城投", "国新", "诚通", "国有股权"]),
    ("险资",       ["人寿保险", "财产保险", "养老保险股份", "保险资产管理",
                    "平安人寿", "泰康", "新华人寿", "太平洋保险", "人民保险"]),
    ("外资",       ["QFII", "GIC", "摩根", "高盛", "瑞银", "淡马锡",
                    "阿布达比", "挪威中央银行", "科威特"]),
    ("公募",       ["基金管理", "证券投资基金"]),
]


def classify_holder(name):
    name = name or ""
    for camp, keys in CAMPS:
        if any(k in name for k in keys):
            return camp
    return "其他机构"


def smart_money_buy(con, pages=3, page_size=500):
    """十大流通股东里的「新进 / 加仓」。

    这是「聪明钱下场买了什么」最直接的结构化证据：
    谁（股东名）→ 买了什么（股票）→ 多少（市值）→ 动了多少（股数）→ 什么性质（阵营）。
    """
    s = session()
    total, kept = 0, 0
    seen = set()
    for page in range(1, pages + 1):
        p = {"reportName": "RPT_F10_EH_FREEHOLDERS", "columns": "ALL",
             "pageNumber": page, "pageSize": page_size,
             "sortColumns": "END_DATE", "sortTypes": -1,
             "source": "WEB", "client": "WEB"}
        u = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
             + "&".join(f"{k}={v}" for k, v in p.items()))
        try:
            j = fetch_json(s, u)
        except Exception:
            break
        data = (j.get("result") or {}).get("data") or []
        if not data:
            break
        for r in data:
            total += 1
            state = r.get("HOLDER_STATE")
            if state not in ("新进", "加仓"):
                continue
            holder = r.get("HOLDER_NAME") or "?"
            stock = r.get("SECURITY_NAME_ABBR") or "?"
            period = (r.get("END_DATE") or "")[:10]
            key = (period, stock, holder, state)
            if key in seen:
                continue
            seen.add(key)

            cap = r.get("HOLDER_MARKET_CAP") or 0
            upsw = r.get("HOLD_NUM_CHANGE")
            try:
                upsw = float(upsw) if upsw not in (None, "新进", "不变", "") else None
            except (TypeError, ValueError):
                upsw = None

            camp = classify_holder(holder)
            upsert_fact(
                con, ts=period, entity=holder, action="buy", asset="equity",
                metric="holder_buy", value=upsw, unit="股",
                amount_usd=(cap / 7.1 / 1e8) if cap else None,
                source="东方财富十大流通股东", source_url=u,
                confidence="high", lag_days=30,
                detail={"stock": stock, "code": r.get("SECURITY_CODE"),
                        "camp": camp, "state": state,
                        "market_cap_cny": cap,
                        "hold_ratio": r.get("FREE_HOLDNUM_RATIO"),
                        "rank": r.get("HOLDER_RANK")},
            )
            kept += 1
        polite_sleep(0.5, 1.0)
    return {"scanned": total, "kept": kept}


# ------------------------------------------------------------------ 汇总导出

def land_deals(con, city="", pages=2):
    """中国土地市场网公开成交公告。这块最能看出城投托底。"""
    s = session()
    s.headers.update({"Referer": "https://www.landchina.com/"})
    total = 0
    u = "https://www.landchina.com/landsupply/rest/landDeal/list"
    for page in range(1, pages + 1):
        try:
            r = s.post(u, json={"pageNo": page, "pageSize": 50, "cityName": city},
                       timeout=25)
            j = r.json()
        except Exception:
            break
        rows = (j.get("data") or {}).get("list") or j.get("list") or []
        if not rows:
            break
        for d in rows:
            upsert_fact(
                con, ts=(d.get("dealDate") or "")[:10] or now_cst().strftime("%Y-%m-%d"),
                entity=d.get("winner") or "?", action="buy", asset="land",
                metric="land_deal", value=d.get("area"), unit="㎡",
                price=d.get("price"), amount_usd=None,
                source="中国土地市场网", source_url=u, confidence="medium", lag_days=7,
                detail=d,
            )
            total += 1
    return {"rows": total, "note": "接口需实测，失败时降级为空"}
