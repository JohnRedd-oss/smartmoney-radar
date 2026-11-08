# -*- coding: utf-8 -*-
"""HKEXnews 修正 + 土地市场网 接口探测。"""
import requests, json

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh",
})

# HKEXnews：先建 session 再查
r0 = S.get("https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh", timeout=25)
print("warmup", r0.status_code, len(r0.text), list(S.cookies.keys()))

p = {"sortDir": "0", "sortByOptions": "DateTime", "category": "0",
     "market": "SEHK", "stockId": "-1", "documentType": "-1",
     "fromDate": "20260101", "toDate": "20261108", "title": "",
     "searchType": "0", "t1code": "-2", "t2Gcode": "-2", "t2code": "-2",
     "rowRange": "20", "lang": "zh"}
r = S.get("https://www1.hkexnews.hk/search/titleSearchServlet.do", params=p, timeout=30)
print("status", r.status_code, "len", len(r.text))
print("head:", r.text[:300])
try:
    j = r.json()
    print("recordInfo", j.get("recordInfo"))
    res = j.get("result")
    if isinstance(res, str):
        res = json.loads(res)
    print("rows", len(res or []))
    for x in (res or [])[:3]:
        print("  ", x.get("DATE_TIME"), x.get("STOCK_NAME"), x.get("TITLE")[:60], x.get("FILE_LINK"))
except Exception as e:
    print("json fail", e)
