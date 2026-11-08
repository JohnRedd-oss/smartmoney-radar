# -*- coding: utf-8 -*-
"""13F 持仓还原：以梧桐树 Wutongshu 为例，验证全链路。"""
import requests, json, time

UA = {"User-Agent": "Zhudong Research research@example.com"}
BASE = "https://data.sec.gov"


def cik_lookup(name):
    u = "https://www.sec.gov/cgi-bin/browse-edgar"
    r = requests.get(u, params={"action": "getcompany", "company": name,
                                "type": "13F-HR", "dateb": "", "owner": "include",
                                "count": "10", "output": "atom"},
                     headers=UA, timeout=25)
    return r.status_code, len(r.text)


def fulltext(q, forms="13F-HR"):
    r = requests.get("https://efts.sec.gov/LATEST/search-index",
                     params={"q": q, "forms": forms}, headers=UA, timeout=25)
    j = r.json()
    hits = j.get("hits", {}).get("hits", [])
    return [(h["_source"].get("display_names"), h["_source"].get("file_date"), h["_id"]) for h in hits]


def submissions(cik):
    cik = str(cik).zfill(10)
    r = requests.get(f"{BASE}/submissions/CIK{cik}.json", headers=UA, timeout=25)
    j = r.json()
    recent = j.get("filings", {}).get("recent", {})
    out = []
    for i, form in enumerate(recent.get("form", [])):
        if form in ("13F-HR", "13F-HR/A"):
            out.append({
                "form": form,
                "date": recent["filingDate"][i],
                "acc": recent["accessionNumber"][i],
                "doc": recent["primaryDocument"][i],
            })
    return j.get("name"), out[:5]


def holdings(cik, acc, doc):
    """解析 13F information table XML"""
    cik = str(cik).zfill(10)
    accn = acc.replace("-", "")
    u = f"{BASE}/Archives/edgar/data/{int(cik)}/{accn}/{doc}"
    r = requests.get(u, headers=UA, timeout=25)
    return u, r.status_code, len(r.text), r.text[:300]


print("--- fulltext ---")
for x in fulltext('"Wutongshu"')[:5]:
    print(x)

print("\n--- 梧桐树 13F 列表 ---")
name, lst = submissions("1767640")
print(name)
for x in lst:
    print(x)

if lst:
    print("\n--- 最新一份持仓文件 ---")
    print(holdings("1767640", lst[0]["acc"], lst[0]["doc"]))
