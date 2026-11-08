# -*- coding: utf-8 -*-
"""SEC 13F 全文检索 + 央行 PSL + 东财股东增减持 探测。"""
import requests, json

UA = {"User-Agent": "Zhudong Research research@example.com",
      "Accept-Encoding": "gzip, deflate"}

print("=== SEC EDGAR full-text search ===")
try:
    r = requests.get("https://efts.sec.gov/LATEST/search-index",
                     params={"q": '"Wutongshu"', "forms": "13F-HR"},
                     headers=UA, timeout=25)
    print("status", r.status_code, "len", len(r.text))
    print(r.text[:300])
except Exception as e:
    print("FAIL", e)

print("\n=== SEC EDGAR normal full text ===")
try:
    r = requests.get("https://efts.sec.gov/LATEST/search-index",
                     params={"q": "Wutongshu"}, headers=UA, timeout=25)
    print("status", r.status_code, "len", len(r.text), r.text[:200])
except Exception as e:
    print("FAIL", e)

print("\n=== SEC company facts (梧桐树 CIK 猜测) ===")
for cik in ["0001767640"]:
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=UA, timeout=25)
        j = r.json()
        print(cik, j.get("name"), j.get("cik"), len(j.get("filings", {}).get("recent", {}).get("form", [])))
    except Exception as e:
        print(cik, "FAIL", str(e)[:80])
