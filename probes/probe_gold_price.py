# -*- coding: utf-8 -*-
"""金价历史序列探测：用于反推央行购金成本带。"""
import requests, json

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

cands = {
    "EM_au9999_kline": "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=118.au9999&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56&klt=103&fqt=0&beg=20250101&end=20261231",
    "EM_沪金主连_kline": "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=113.aum&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56&klt=103&fqt=0&beg=20250101&end=20261231",
    "EM_伦敦金": "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=101.GC00Y&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56&klt=103&fqt=0&beg=20250101&end=20261231",
}

for name, u in cands.items():
    try:
        r = requests.get(u, timeout=20, headers=H)
        j = r.json()
        d = j.get("data") or {}
        kl = d.get("klines") or []
        print(f"[{name}] status={r.status_code} name={d.get('name')} code={d.get('code')} bars={len(kl)}")
        if kl:
            print("   first:", kl[0])
            print("   last :", kl[-1])
    except Exception as e:
        print(f"[{name}] FAIL {type(e).__name__} {str(e)[:100]}")
