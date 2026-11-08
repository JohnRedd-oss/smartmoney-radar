# -*- coding: utf-8 -*-
"""政采/财政部/大宗交易 三源修正探测。"""
import requests, re

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

def show(n, fn):
    try:
        print(f"[OK] {n}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {n}: {type(e).__name__} {str(e)[:150]}")

# CCGP 正确参数：kw + timeType 必填，且要用 GET 带 Referer
def ccgp_fix(kw="存量商品房"):
    u = "http://search.ccgp.gov.cn/bxsearch"
    p = {"searchtype": "1", "page_index": "1", "bidSort": "0", "buyerName": "",
         "projectId": "", "pinMu": "0", "bidType": "0", "dbselect": "bidx",
         "kw": kw, "start_time": "2026:01:01", "end_time": "2026:11:08",
         "timeType": "6", "displayZone": "", "zoneId": "", "pppStatus": "0",
         "agentName": ""}
    h = {"Referer": "http://www.ccgp.gov.cn/"}
    r = S.get(u, params=p, timeout=25, headers=h)
    r.encoding = "utf-8"
    items = re.findall(r'<li[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S)
    clean = [(re.sub(r"<[^>]+>", "", t).strip()[:70], hh) for hh, t in items]
    return r.status_code, len(r.text), len(clean), clean[:4]

# 财政部 地方政府债券发行/存续期信息披露
def mof():
    u = "https://www.celma.org.cn/xxpl/dfz/index.jhtml"
    r = S.get(u, timeout=20)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)

# 沪深大宗交易（东财）
def block_trade():
    u = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
         "reportName=RPT_DATA_BLOCKTRADE&columns=ALL&pageNumber=1&pageSize=20"
         "&sortColumns=TRADE_DATE&sortTypes=-1&source=WEB&client=WEB")
    r = S.get(u, timeout=20)
    j = r.json()
    res = (j.get("result") or {}).get("data") or []
    return j.get("success"), len(res), res[0] if res else None

# 北向/沪深港通持股（东财）
def northbound():
    u = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
         "reportName=RPT_MUTUAL_HOLDSTOCKNORTH_STA&columns=ALL&pageNumber=1&pageSize=5"
         "&sortColumns=TRADE_DATE&sortTypes=-1&source=WEB&client=WEB")
    r = S.get(u, timeout=20)
    j = r.json()
    res = (j.get("result") or {}).get("data") or []
    return j.get("success"), len(res)

show("政采_修正", ccgp_fix)
show("财政部CELMA", mof)
show("大宗交易", block_trade)
show("北向持股", northbound)
