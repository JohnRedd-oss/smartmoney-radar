# -*- coding: utf-8 -*-
"""13F 持仓解析修正：走 filing index.json 找 information table。"""
import requests, json
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Zhudong Research research@example.com"}
BASE = "https://data.sec.gov"

CIK = "1767640"
ACC = "0001011438-26-000537"
accn = ACC.replace("-", "")

# 1) filing index
u = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{accn}/index.json"
r = requests.get(u, headers=UA, timeout=25)
print("index", r.status_code)
j = r.json()
items = j.get("directory", {}).get("item", [])
for it in items:
    print("  ", it["name"], it.get("size"))

# 2) 找 information table xml（非 primary_doc）
cands = [it["name"] for it in items if it["name"].lower().endswith(".xml")
         and "primary_doc" not in it["name"].lower()]
print("candidates:", cands)

for c in cands:
    fu = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{accn}/{c}"
    rr = requests.get(fu, headers=UA, timeout=30)
    print("fetch", fu, rr.status_code, len(rr.text))
    if rr.status_code != 200:
        continue
    root = ET.fromstring(rr.content)
    ns = {"n": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    infos = root.findall(".//n:infoTable", ns) if ns else root.findall(".//infoTable")
    print("infoTable count:", len(infos))
    rows = []
    for it in infos:
        def g(tag):
            e = it.find(f"n:{tag}", ns) if ns else it.find(tag)
            return e.text.strip() if e is not None and e.text else ""
        rows.append({
            "issuer": g("nameOfIssuer"),
            "cls": g("titleOfClass"),
            "cusip": g("cusip"),
            "value": g("value"),
            "shares": (it.find(".//n:shrsOrPrnAmt/n:sshPrnamt", ns) if ns
                       else it.find(".//shrsOrPrnAmt/sshPrnamt")),
        })
    print("parsed rows:", len(rows))
    for x in rows[:5]:
        print("   ", x["issuer"], x["cls"], x["cusip"], x["value"])
    break
