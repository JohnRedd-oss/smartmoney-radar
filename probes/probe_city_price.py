# -*- coding: utf-8 -*-
"""70城最新月排序 + 城市绝对房价(元/㎡)源探测。"""
import requests, json

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"})

print("=== 70城 按日期倒序取最新月 ===")
u = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
     "reportName=RPT_ECONOMY_HOUSE_PRICE&columns=ALL&pageNumber=1&pageSize=200"
     "&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB")
j = S.get(u, timeout=30).json()
d = (j.get("result") or {}).get("data") or []
print("rows:", len(d), "pages:", (j.get("result") or {}).get("pages"))
if d:
    latest = d[0]["REPORT_DATE"]
    print("最新报告期:", latest)
    same = [r for r in d if r["REPORT_DATE"] == latest]
    print("同月城市数:", len(same))
    for r in same[:6]:
        print(f"  {r['CITY']:8s} 新房同比{r['FIRST_COMHOUSE_SAME']} 环比{r['FIRST_COMHOUSE_SEQUENTIAL']} "
              f"二手同比{r['SECOND_HOUSE_SAME']} 环比{r['SECOND_HOUSE_SEQUENTIAL']}")

print("\n=== 城市绝对房价源探测 ===")
cands = [
    ("房价行情网", "https://www.creprice.cn/"),
    ("安居客", "https://www.anjuke.com/fangjia/"),
    ("贝壳找房", "https://www.ke.com/"),
    ("房天下指数", "https://industry.fang.com/index/"),
    ("中指院", "https://www.fang.com/"),
]
for name, u in cands:
    try:
        r = S.get(u, timeout=15)
        r.encoding = "utf-8"
        print(f"  {name:10s} {r.status_code} len={len(r.text)}")
    except Exception as e:
        print(f"  {name:10s} FAIL {type(e).__name__} {str(e)[:50]}")

print("\n=== 东财 房地产行业数据(投资/销售/库存) ===")
for rn in ["RPT_ECONOMY_REALESTATE_INVEST", "RPT_ECONOMY_HOUSE_SALE_AREA",
           "RPT_ECONOMY_REALESTATE_INDEX", "RPT_ECONOMY_ESTATE"]:
    u = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
         f"reportName={rn}&columns=ALL&pageNumber=1&pageSize=3&source=WEB&client=WEB")
    try:
        jj = S.get(u, timeout=15).json()
        dd = (jj.get("result") or {}).get("data")
        print(f"  {rn}: {jj.get('success')} rows={len(dd) if dd else 0} {jj.get('message') or ''}")
    except Exception as e:
        print(f"  {rn}: FAIL {type(e).__name__}")
