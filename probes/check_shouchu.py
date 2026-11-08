# -*- coding: utf-8 -*-
import sqlite3, json
c = sqlite3.connect("smartmoney.db")
c.row_factory = sqlite3.Row
for r in c.execute("SELECT ts,entity,action,detail FROM facts WHERE metric='announcement' "
                   "ORDER BY ts DESC LIMIT 200"):
    d = json.loads(r["detail"] or "{}")
    if d.get("keyword") == "收储":
        print(r["ts"], r["entity"], "|", d.get("title")[:70])
