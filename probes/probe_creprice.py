# -*- coding: utf-8 -*-
"""房价行情网 creprice.cn 接口探测（要绝对价 元/㎡）。"""
import requests, json, re

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.creprice.cn/",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

r = S.get("https://www.creprice.cn/", timeout=25)
r.encoding = "utf-8"
print("首页", r.status_code, len(r.text))

# 找接口
apis = re.findall(r'["\'](/[a-zA-Z0-9_/\-\.]{4,60})["\']', r.text)
apis = [a for a in apis if any(k in a.lower() for k in ("api", "json", "rank", "city", "price", "data"))]
print("候选接口:", sorted(set(apis))[:20])

# 尝试常见城市页
for u in ["https://www.creprice.cn/rank/city/",
          "https://www.creprice.cn/rank/",
          "https://www.creprice.cn/city/bj.html"]:
    try:
        rr = S.get(u, timeout=20)
        rr.encoding = "utf-8"
        # 找数字+元/㎡ 模式
        nums = re.findall(r'(\d{4,6})\s*(?:元/㎡|元/平)', rr.text)
        print(f"  {u} -> {rr.status_code} len={len(rr.text)} 价格模式命中={len(nums)} {nums[:5]}")
    except Exception as e:
        print(f"  {u} -> FAIL {type(e).__name__} {str(e)[:60]}")

# 东财 房地产板块行情（替代资产视角）
print("\n=== 东财 房地产板块 ===")
u = ("https://push2.eastmoney.com/api/qt/clist/get?"
     "pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f12,f14,f3")
j = S.get(u, timeout=20).json()
d = (j.get("data") or {}).get("diff") or []
for x in d[:8]:
    print(f"  {x.get('f14')} {x.get('f3')}%")

# 中证/申万 房地产指数
print("\n=== 房地产指数 secid ===")
for name, secid in [("地产指数", "1.000006"), ("申万房地产", "0.399200"),
                    ("房地产ETF", "1.512200"), ("保利发展", "1.600048"),
                    ("万科A", "0.000002")]:
    u = (f"https://push2.eastmoney.com/api/qt/stock/get?"
         f"secid={secid}&fields=f43,f58,f170")
    try:
        jj = S.get(u, timeout=12).json()
        dd = jj.get("data") or {}
        print(f"  {name:10s} {secid:12s} -> {dd.get('f58')} {dd.get('f43')}")
    except Exception as e:
        print(f"  {name:10s} -> FAIL")
