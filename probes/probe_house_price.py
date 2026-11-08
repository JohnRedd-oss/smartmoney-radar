# -*- coding: utf-8 -*-
"""房价报表结构 + 缺失 secid 修正。"""
import requests, json

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"})

print("=== 70城房价报表结构 ===")
u = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
     "reportName=RPT_ECONOMY_HOUSE_PRICE&columns=ALL&pageNumber=1&pageSize=8"
     "&source=WEB&client=WEB")
j = S.get(u, timeout=25).json()
d = (j.get("result") or {}).get("data") or []
print("rows:", len(d))
if d:
    print("keys:", list(d[0].keys()))
    for r in d[:5]:
        print(json.dumps(r, ensure_ascii=False)[:400])

print("\n=== 房价报表可用列名探测（试其他 reportName）===")
for rn in ["RPT_ECONOMY_HOUSE_PRICE", "RPT_ECONOMY_HOUSE_INDEX",
           "RPT_ECONOMY_REALESTATE", "RPT_ECONOMY_ESTATE_INVEST",
           "RPT_ECONOMY_HOUSE_SALE"]:
    u = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
         f"reportName={rn}&columns=ALL&pageNumber=1&pageSize=3&source=WEB&client=WEB")
    try:
        jj = S.get(u, timeout=20).json()
        dd = (jj.get("result") or {}).get("data")
        print(f"  {rn}: success={jj.get('success')} rows={len(dd) if dd else 0} "
              f"msg={jj.get('message')}")
        if dd:
            print("     ", list(dd[0].keys())[:18])
    except Exception as e:
        print(f"  {rn}: FAIL {type(e).__name__}")

print("\n=== 原油/比特币 secid 修正 ===")
cands = {
    "原油WTI_a": "101.CL00Y", "原油WTI_b": "102.CL00Y", "原油WTI_c": "113.sc",
    "布伦特_a": "101.B00Y", "布伦特_b": "102.B00Y",
    "比特币_a": "120.BTC", "比特币_b": "102.BTC", "比特币_c": "101.BTC",
    "沪金主连": "113.aum", "沪银主连": "113.agm",
    "10年国债期货": "113.TM", "中证全债": "1.000012",
}
for name, secid in cands.items():
    u = (f"https://push2.eastmoney.com/api/qt/stock/get?"
         f"secid={secid}&fields=f43,f58,f170")
    try:
        jj = S.get(u, timeout=12).json()
        dd = jj.get("data") or {}
        print(f"  {name:16s} {secid:12s} -> {dd.get('f58')} {dd.get('f43')}")
    except Exception as e:
        print(f"  {name:16s} {secid:12s} -> FAIL {type(e).__name__}")
