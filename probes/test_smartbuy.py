# -*- coding: utf-8 -*-
"""跑新采集器 + 新规则，验证「聪明钱下场买了什么」。"""
from smartmoney import core, collectors, rules

con = core.db()
for name, fn in [
    ("multi_asset", collectors.multi_asset),
    ("smart_money_buy", collectors.smart_money_buy),
    ("stats70", collectors.stats70),
]:
    try:
        r = fn(con)
        con.commit()
        print(f"[OK] {name}: {r}")
    except Exception as e:
        con.rollback()
        print(f"[FAIL] {name}: {type(e).__name__} {str(e)[:160]}")

print("\n=== 聪明钱买入 按阵营 ===")
for r in con.execute(
        "SELECT entity, ts, amount_usd, value, detail FROM facts "
        "WHERE metric='holder_buy' ORDER BY amount_usd DESC LIMIT 15"):
    import json
    d = json.loads(r["detail"] or "{}")
    print(f"  {r['ts']} {d.get('camp','?'):8s} {d.get('stock','?'):10s} "
          f"{r['entity'][:22]:22s} {d.get('state'):4s} "
          f"{(r['amount_usd'] or 0):>7.2f}亿$")

print("\n=== 规则输出 ===")
for rule, ts, sentence, payload in rules.run_all(con):
    print(f"[{rule}] {ts}\n   {sentence}\n")
con.close()
