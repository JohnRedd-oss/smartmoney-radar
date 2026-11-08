# -*- coding: utf-8 -*-
import sqlite3, json
c = sqlite3.connect("smartmoney.db")
c.row_factory = sqlite3.Row
print("--- insider ---")
for r in c.execute("SELECT ts,entity,value,price,detail FROM facts "
                   "WHERE metric='insider_trade' ORDER BY ts DESC LIMIT 8"):
    d = json.loads(r["detail"] or "{}")
    print(r["ts"], r["entity"], r["value"], r["price"],
          "| cny=", d.get("change_amount_cny"), "|", d.get("stock"), d.get("position"))
print("--- block ---")
for r in c.execute("SELECT ts,entity,value,price,amount_usd,detail FROM facts "
                   "WHERE metric='block_trade' ORDER BY ts DESC LIMIT 5"):
    d = json.loads(r["detail"] or "{}")
    print(r["ts"], r["entity"], r["value"], r["price"], r["amount_usd"],
          d.get("amount_cny"), d.get("stock"))
print("--- prices ---")
for r in c.execute("SELECT ts,metric,value FROM facts WHERE entity='MARKET' "
                   "ORDER BY ts DESC LIMIT 6"):
    print(r["ts"], r["metric"], r["value"])
