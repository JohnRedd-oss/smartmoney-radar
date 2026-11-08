# -*- coding: utf-8 -*-
"""HKEXnews 披露易 标题检索 + 环评公示 探测。"""
import requests, re, json

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})

def show(n, fn):
    try:
        print(f"[OK] {n}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {n}: {type(e).__name__} {str(e)[:150]}")

# 1) HKEXnews 标题搜索 API
def hkexnews():
    u = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
    p = {"sortDir": "0", "sortByOptions": "DateTime", "category": "0",
         "market": "SEHK", "stockId": "-1", "documentType": "-1",
         "fromDate": "20260101", "toDate": "20261108", "title": "权益",
         "searchType": "1", "t1code": "-1", "t2Gcode": "-1", "t2code": "-1",
         "rowRange": "20", "lang": "zh"}
    r = S.get(u, params=p, timeout=25)
    j = r.json()
    res = j.get("result")
    if isinstance(res, str):
        res = json.loads(res)
    return r.status_code, j.get("recordInfo"), (res or [])[:2]

# 2) 环评公示（生态环境部 全国环评平台）
def eia():
    for u in ["https://www.mee.gov.cn/ywdt/",
              "http://114.251.10.205:8080/eia/",
              "https://www.mee.gov.cn/"]:
        try:
            r = S.get(u, timeout=15)
            print(f"    {u} -> {r.status_code} {len(r.text)}")
        except Exception as e:
            print(f"    {u} -> FAIL {str(e)[:60]}")

# 3) 土地成交（东财/中国土地市场网）
def land():
    u = "https://www.landchina.com/default.aspx"
    r = S.get(u, timeout=20)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)

# 4) 中国货币网 / 央行 PSL
def psl():
    u = "http://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/index.html"
    r = S.get(u, timeout=20)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)

show("HKEXnews标题", hkexnews)
show("环评", eia)
show("土地市场网", land)
show("央行PSL", psl)
