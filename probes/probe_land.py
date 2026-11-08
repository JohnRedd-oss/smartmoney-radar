# -*- coding: utf-8 -*-
"""土地市场网接口实测。"""
import requests, json

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.landchina.com/",
    "Content-Type": "application/json;charset=UTF-8",
})

tests = [
    ("POST landDeal/list", "https://www.landchina.com/landsupply/rest/landDeal/list",
     {"pageNo": 1, "pageSize": 10}),
    ("POST landDeal/page", "https://www.landchina.com/landsupply/rest/landDeal/page",
     {"pageNo": 1, "pageSize": 10}),
    ("GET 首页", "https://www.landchina.com/default.aspx", None),
]
for name, u, body in tests:
    try:
        if body:
            r = S.post(u, json=body, timeout=20)
        else:
            r = S.get(u, timeout=20)
        print(f"[{name}] {r.status_code} len={len(r.content)} ct={r.headers.get('Content-Type')}")
        print("   ", r.text[:200].replace("\n", " "))
    except Exception as e:
        print(f"[{name}] FAIL {type(e).__name__} {str(e)[:100]}")
