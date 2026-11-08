# -*- coding: utf-8 -*-
"""Web 接口冒烟测试：逐端点验证返回结构与关键字段。"""
import json
import requests

BASE = "http://127.0.0.1:8848"

checks = []


def t(path, validate=None):
    try:
        r = requests.get(BASE + path, timeout=90)
        ok = r.status_code == 200
        body = None
        if "application/json" in r.headers.get("content-type", ""):
            body = r.json()
        detail = ""
        if ok and validate:
            try:
                validate(body)
                detail = "结构OK"
            except Exception as e:
                ok = False
                detail = f"校验失败 {e}"
        checks.append((path, ok, r.status_code, len(r.content), detail))
    except Exception as e:
        checks.append((path, False, "-", 0, f"{type(e).__name__}: {str(e)[:80]}"))


t("/", lambda b: None)
t("/api/summary", lambda b: (
    b["headlines"], b["narrative"], b["stats"]["facts"],
    [h for h in b["health"]]))
t("/api/gold", lambda b: (b["series"], b["current"]["oz"], b["ytd_wan_oz"]))
t("/api/holdings", lambda b: [f["positions"] for f in b["funds"]])
t("/api/trades", lambda b: (b["block"]["summary"], b["insider"]["rows"]))
t("/api/announcements", lambda b: b["rows"])

for path, ok, code, size, detail in checks:
    print(f"  {'PASS' if ok else 'FAIL'}  {path:24s} {code} {size:>7}B  {detail}")

# 打印关键数值，确认不是空壳
try:
    s = requests.get(BASE + "/api/summary", timeout=90).json()
    print("\n--- summary ---")
    print("as_of:", s["as_of"])
    print("facts:", s["stats"]["facts"], "signals:", s["stats"]["signals"])
    for n in s["narrative"]:
        print("  总述:", n)
    for h in s["headlines"]:
        print(f"  [{h['ts']}] {h['rule']}: {h['head'][:70]}")

    g = requests.get(BASE + "/api/gold", timeout=90).json()
    print("\n--- gold ---")
    print("series points:", len(g["series"]), "current:", g["current"])
    print("ytd:", g["ytd_wan_oz"])

    hd = requests.get(BASE + "/api/holdings", timeout=90).json()
    print("\n--- holdings ---")
    for f in hd["funds"]:
        print(f"  {f['entity']} {f['period']} total={f['total_usd_yi']:.1f}亿 "
              f"pos={len(f['positions'])} closed={len(f['closed'])}")
        for p in f["positions"][:3]:
            print(f"     {p['issuer']} {p['value_usd']/1e8:.1f}亿 [{p['change']}]")

    tr = requests.get(BASE + "/api/trades", timeout=90).json()
    print("\n--- trades ---")
    print("block:", tr["block"]["date"], tr["block"]["summary"])
    print("insider:", tr["insider"]["date"], "sell", tr["insider"]["sell"], "buy", tr["insider"]["buy"])
except Exception as e:
    print("数值抽查失败:", e)
