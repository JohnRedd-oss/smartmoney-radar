# -*- coding: utf-8 -*-
"""新接口冒烟：smartbuy / assets / region。"""
import requests, json

BASE = "http://127.0.0.1:8848"

for path in ["/", "/api/summary", "/api/smartbuy", "/api/assets", "/api/region",
             "/api/gold", "/api/holdings", "/api/trades", "/api/announcements"]:
    try:
        r = requests.get(BASE + path, timeout=120)
        print(f"  {'PASS' if r.status_code==200 else 'FAIL'}  {path:24s} "
              f"{r.status_code} {len(r.content):>7}B")
    except Exception as e:
        print(f"  FAIL  {path:24s} {type(e).__name__} {str(e)[:60]}")

print("\n=== smartbuy ===")
sb = requests.get(BASE + "/api/smartbuy", timeout=120).json()
print("as_of", sb.get("as_of"), "window", sb.get("window_from"))
print("summary", sb.get("summary"))
for c in sb.get("camps", [])[:6]:
    print(f"  {c['camp']:8s} {c['count']:>4}笔  ${c['usd']:>8.1f}亿  ¥{c['cny']/1e8:>8.0f}亿")
    for t in c["top"][:2]:
        print(f"      · {t['stock']:10s} {t['state']} {t['usd']:.2f}亿$")

print("\n=== assets ===")
a = requests.get(BASE + "/api/assets", timeout=120).json()
print("date", a.get("date"))
for g in a.get("groups", []):
    print(f"  [{g['group']}] " + " | ".join(
        f"{i['name']} {i['value']:.2f}({i['chg']:+.2f}%)" for i in g["items"]))

print("\n=== region ===")
rg = requests.get(BASE + "/api/region", timeout=120).json()
print("month", rg.get("month"), "cities", len(rg.get("cities", [])))
cs = rg.get("cities", [])
if cs:
    print("  最弱:", cs[0]["city"], cs[0].get("snd_yoy"))
    print("  最强:", cs[-1]["city"], cs[-1].get("snd_yoy"))
