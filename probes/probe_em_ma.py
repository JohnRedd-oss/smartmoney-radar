# -*- coding: utf-8 -*-
"""东财结构化报表：并购重组 / 股权转让 / 重大合同 / 十大股东。"""
import requests, json

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"})

CANDIDATES = [
    "RPT_MA_DEAL", "RPT_MAIN_DEAL", "RPT_MERGER_DEAL", "RPT_ACQUISITION",
    "RPT_SHARE_TRANSFER", "RPT_EQUITY_TRANSFER", "RPT_BIG_CONTRACT",
    "RPT_IMPORTANT_CONTRACT", "RPT_M_A", "RPT_REORGANIZATION",
    # 已知可用的
    "RPT_EXECUTIVE_HOLD_DETAILS", "RPT_DATA_BLOCKTRADE",
    "RPT_F10_EH_FREEHOLDERS", "RPT_ORG_SURVEYNEW",
    "RPT_LICO_FN_CPD", "RPT_MUTUAL_HOLDSTOCKNORTH_STA",
]

for rn in CANDIDATES:
    u = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
         f"reportName={rn}&columns=ALL&pageNumber=1&pageSize=3&source=WEB&client=WEB")
    try:
        j = S.get(u, timeout=15).json()
        d = (j.get("result") or {}).get("data")
        ok = j.get("success")
        msg = j.get("message") or ""
        if ok and d:
            print(f"[OK]   {rn}: rows={len(d)}")
            print(f"        keys: {list(d[0].keys())[:16]}")
        else:
            print(f"[--]   {rn}: {msg[:60]}")
    except Exception as e:
        print(f"[ERR]  {rn}: {type(e).__name__} {str(e)[:60]}")
