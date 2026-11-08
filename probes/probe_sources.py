# -*- coding: utf-8 -*-
"""源可用性探测：确认每个 collector 的真实入口，不猜。"""
import requests, re, json, sys

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
out = {}


def t(name, fn):
    try:
        r = fn()
        out[name] = r
        print(f"[OK]   {name}: {r}")
    except Exception as e:
        out[name] = f"FAIL {type(e).__name__}: {str(e)[:120]}"
        print(f"[FAIL] {name}: {type(e).__name__} {str(e)[:120]}")


# 1) SAFE 官方储备资产（黄金储备页）
def safe_gold():
    u = "https://www.safe.gov.cn/safe/2024/0707/24619.html"
    r = requests.get(u, timeout=15, headers=H)
    r.encoding = "utf-8"
    return r.status_code, len(r.text), ("黄金储备" in r.text)


def safe_index():
    u = "https://www.safe.gov.cn/safe/whcb/index.html"
    r = requests.get(u, timeout=15, headers=H)
    r.encoding = "utf-8"
    hits = re.findall(r'href="([^"]+)"[^>]*>\s*([^<]{2,60})', r.text)
    return [h for h in hits if "储备" in h[1] or "黄金" in h[1]][:8]


# 2) 东财 黄金现货/期货
def em_gold():
    u = "https://push2.eastmoney.com/api/qt/stock/get?secid=118.au9999&fields=f43,f58,f60,f170"
    r = requests.get(u, timeout=12, headers=H)
    return r.json()


# 3) 巨潮全文检索：减持 / 增持 / 回购 / 收储
def cninfo(keyword):
    d = {
        "pageNum": "1", "pageSize": "30", "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": keyword, "secDate": "",
        "tDate": "", "type": "", "isHLtitle": "true",
    }
    hh = dict(H)
    hh["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    hh["Referer"] = "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice"
    r = requests.post("http://www.cninfo.com.cn/new/fulltextSearch/full",
                      data=d, timeout=20, headers=hh)
    j = r.json()
    return j.get("totalRecordNum"), [a["announcementTitle"][:40] for a in (j.get("announcements") or [])[:3]]


# 4) 全国公共资源交易平台 / 政府采购网
def ccgp():
    u = "http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&bidSort=0&pinMu=0&kw=%E6%94%B6%E5%82%A8"
    r = requests.get(u, timeout=15, headers=H)
    r.encoding = "utf-8"
    return r.status_code, len(r.text), ("收储" in r.text)


# 5) 央行 PSL / 货币政策
def pbc():
    u = "http://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
    r = requests.get(u, timeout=15, headers=H)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)


for name, fn in [
    ("SAFE黄金页", safe_gold),
    ("SAFE列表", safe_index),
    ("东财金价", em_gold),
    ("巨潮_减持", lambda: cninfo("减持")),
    ("巨潮_回购", lambda: cninfo("回购")),
    ("巨潮_收储", lambda: cninfo("收储")),
    ("政采_收储", ccgp),
    ("央行统计", pbc),
]:
    t(name, fn)

with open("probe_result.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
