# -*- coding: utf-8 -*-
"""新采集器实测：分城市房价 / 70城指数 / 多资产。"""
import sqlite3
from smartmoney import core, collectors

con = core.db()
for name, fn in [
    ("house_price_city", collectors.house_price_city),
    ("stats70", collectors.stats70),
    ("multi_asset", collectors.multi_asset),
]:
    try:
        r = fn(con)
        con.commit()
        print(f"[OK] {name}: {r}")
    except Exception as e:
        con.rollback()
        print(f"[FAIL] {name}: {type(e).__name__} {str(e)[:160]}")

print("\n=== 房价抽样 ===")
for r in con.execute("SELECT entity, ts, value FROM facts "
                     "WHERE metric='house_price_wan_per_sqm' "
                     "ORDER BY value DESC LIMIT 12"):
    print(f"  {r['entity']:14s} {r['ts'][:7]} {r['value']:.2f} 万元/㎡")

print("\n=== 70城指数抽样 ===")
for r in con.execute("SELECT entity, ts, metric, value FROM facts "
                     "WHERE metric LIKE 'hp_%' ORDER BY entity LIMIT 8"):
    print(f"  {r['entity']} {r['ts']} {r['metric']} {r['value']}")

print("\n=== 多资产 ===")
for r in con.execute("SELECT entity, value, unit, detail FROM facts "
                     "WHERE metric LIKE 'quote:%' ORDER BY entity"):
    d = r["detail"] or "{}"
    import json
    j = json.loads(d) if isinstance(d, str) else {}
    print(f"  {r['entity'].replace('ASSET:',''):16s} {r['value']:>12.2f} {r['unit']:8s} "
          f"{j.get('chg_pct',0):+.2f}%  [{j.get('group')}]")
con.close()
