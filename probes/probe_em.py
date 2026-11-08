# -*- coding: utf-8 -*-
"""HKEXnews 按股票查 + 东财增减持/高管持股 报表探测。"""
import requests, json

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh",
})
S.get("https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh", timeout=25)

# 按股票代码查（0410 = SOHO中国）
p = {"sortDir": "0", "sortByOptions": "DateTime", "category": "0",
     "market": "SEHK", "stockId": "410", "documentType": "-1",
     "fromDate": "20240101", "toDate": "20261108", "title": "",
     "searchType": "0", "t1code": "-2", "t2Gcode": "-2", "t2code": "-2",
     "rowRange": "20", "lang": "zh"}
r = S.get("https://www1.hkexnews.hk/search/titleSearchServlet.do", params=p, timeout=30)
j = r.json()
res = j.get("result")
if isinstance(res, str):
    res = json.loads(res)
print("HKEX stockId=410 rows:", len(res or []), "recordCnt", j.get("recordCnt"))
for x in (res or [])[:3]:
    print("  ", x.get("DATE_TIME"), x.get("STOCK_NAME"), str(x.get("TITLE"))[:50])

print("\n--- 东财报表 ---")
reports = {
    "股东增减持": "RPT_LICO_FN_CPD",
    "高管持股变动": "RPT_EXECUTIVE_HOLD_DETAILS",
    "机构调研": "RPT_ORG_SURVEYNEW",
    "十大流通股东": "RPT_F10_EH_FREEHOLDERS",
}
for name, rn in reports.items():
    u = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName={rn}"
         f"&columns=ALL&pageNumber=1&pageSize=3&source=WEB&client=WEB")
    try:
        rr = S.get(u, timeout=20)
        jj = rr.json()
        d = (jj.get("result") or {}).get("data")
        print(f"[{name}] success={jj.get('success')} rows={len(d) if d else 0} msg={jj.get('message')}")
        if d:
            print("    keys:", list(d[0].keys())[:14])
    except Exception as e:
        print(f"[{name}] FAIL {type(e).__name__} {str(e)[:80]}")
