# -*- coding: utf-8 -*-
"""十大流通股东：能否筛出「国资/社保/险资 在加仓谁」。"""
import requests, json

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"})

BASE = "https://datacenter-web.eastmoney.com/api/data/v1/get"

def q(params):
    u = BASE + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return S.get(u, timeout=25).json()

print("=== 1. 无过滤，看最新报告期 ===")
j = q({"reportName": "RPT_F10_EH_FREEHOLDERS", "columns": "ALL",
       "pageNumber": 1, "pageSize": 5,
       "sortColumns": "END_DATE", "sortTypes": -1,
       "source": "WEB", "client": "WEB"})
d = (j.get("result") or {}).get("data") or []
print("rows:", len(d), "pages:", (j.get("result") or {}).get("pages"))
if d:
    print("最新报告期:", d[0]["END_DATE"])
    for r in d[:5]:
        print(f"  {r['SECURITY_NAME_ABBR']:8s} {r['HOLDER_NAME'][:24]:24s} "
              f"市值{r['HOLDER_MARKET_CAP']} 变动{r['HOLD_NUM_CHANGE']} "
              f"性质={r.get('HOLDER_STATE')}")

print("\n=== 2. HOLDER_STATE 取值分布 ===")
states = {}
for pg in range(1, 6):
    j = q({"reportName": "RPT_F10_EH_FREEHOLDERS", "columns": "ALL",
           "pageNumber": pg, "pageSize": 100,
           "sortColumns": "END_DATE", "sortTypes": -1,
           "source": "WEB", "client": "WEB"})
    for r in ((j.get("result") or {}).get("data") or []):
        st = r.get("HOLDER_STATE")
        states[st] = states.get(st, 0) + 1
print(states)

print("\n=== 3. 尝试 filter 语法 ===")
tests = [
    ("filter=HOLDER_STATE", {"filter": '(HOLDER_STATE="国有")'}),
    ("filter=IS_HOLDORG", {"filter": '(IS_HOLDORG=1)'}),
    ("filter=加仓", {"filter": '(HOLD_NUM_CHANGE>0)'}),
]
for name, extra in tests:
    p = {"reportName": "RPT_F10_EH_FREEHOLDERS", "columns": "ALL",
         "pageNumber": 1, "pageSize": 5,
         "sortColumns": "END_DATE", "sortTypes": -1,
         "source": "WEB", "client": "WEB"}
    p.update(extra)
    try:
        jj = q(p)
        dd = (jj.get("result") or {}).get("data")
        print(f"  {name}: success={jj.get('success')} rows={len(dd) if dd else 0} "
              f"msg={jj.get('message') or ''}")
        if dd:
            r = dd[0]
            print(f"     例: {r['SECURITY_NAME_ABBR']} {r['HOLDER_NAME'][:20]} "
                  f"市值={r['HOLDER_MARKET_CAP']} 变动={r['HOLD_NUM_CHANGE']}")
    except Exception as e:
        print(f"  {name}: FAIL {type(e).__name__} {str(e)[:60]}")
