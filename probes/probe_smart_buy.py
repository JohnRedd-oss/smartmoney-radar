# -*- coding: utf-8 -*-
"""验证：能否产出「社保/汇金/国资/险资 新进加仓了什么」榜单。"""
import requests, json

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"})

BASE = "https://datacenter-web.eastmoney.com/api/data/v1/get"

def fetch(page=1, size=500):
    p = {"reportName": "RPT_F10_EH_FREEHOLDERS", "columns": "ALL",
         "pageNumber": page, "pageSize": size,
         "sortColumns": "HOLDER_MARKET_CAP", "sortTypes": -1,
         "source": "WEB", "client": "WEB"}
    u = BASE + "?" + "&".join(f"{k}={v}" for k, v in p.items())
    j = S.get(u, timeout=30).json()
    return (j.get("result") or {}).get("data") or []

# 阵营识别
CAMPS = [
    ("社保/养老金", ["社保基金", "全国社会保障", "基本养老保险", "养老金"]),
    ("汇金/证金", ["中央汇金", "中国证券金融", "证金公司"]),
    ("国资平台", ["国有资本", "国有资产", "国有投资", "国资", "投资控股集团",
                  "产业发展集团", "城投", "国新", "诚通"]),
    ("险资", ["人寿保险", "财产保险", "养老保险股份", "保险资产管理", "平安人寿",
             "泰康", "新华人寿", "太平洋保险"]),
    ("外资", ["QFII", "GIC", "摩根", "高盛", "瑞银", "淡马锡", "阿布达比", "挪威"]),
    ("公募", ["基金管理", "证券投资基金"]),
]

def classify(name):
    for camp, keys in CAMPS:
        if any(k in name for k in keys):
            return camp
    return "其他"

rows = []
for pg in (1, 2):
    rows += fetch(pg)
print("拉取记录:", len(rows))

# 动作筛选
moves = [r for r in rows if r.get("HOLDER_STATE") in ("新进", "加仓")]
print("新进/加仓记录:", len(moves))

# 按阵营归类
from collections import defaultdict
by_camp = defaultdict(list)
for r in moves:
    camp = classify(r.get("HOLDER_NAME") or "")
    by_camp[camp].append(r)

print("\n=== 各阵营新进/加仓 笔数 ===")
for c in sorted(by_camp, key=lambda x: -len(by_camp[x])):
    print(f"  {c:10s} {len(by_camp[c])} 笔")

print("\n=== 社保/汇金/国资 具体买了什么（按市值）===")
for camp in ["社保/养老金", "汇金/证金", "国资平台", "险资"]:
    lst = sorted(by_camp.get(camp, []), key=lambda r: -(r.get("HOLDER_MARKET_CAP") or 0))
    if not lst:
        continue
    print(f"\n-- {camp} （{len(lst)} 笔）--")
    for r in lst[:6]:
        cap = (r.get("HOLDER_MARKET_CAP") or 0) / 1e8
        chg = r.get("HOLD_NUM_CHANGE")
        print(f"  {r['END_DATE'][:10]} {r['SECURITY_NAME_ABBR']:8s} "
              f"{r['HOLDER_NAME'][:26]:26s} {r['HOLDER_STATE']:4s} "
              f"市值{cap:>8.2f}亿 变动{chg}")
