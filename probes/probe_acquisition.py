# -*- coding: utf-8 -*-
"""验证：能否从公告里抽出「谁 花多少钱 买了什么」。"""
import requests, re, json

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
})

def search(kw, n=30):
    d = {"pageNum": "1", "pageSize": str(n), "column": "szse", "tabName": "fulltext",
         "plate": "", "stock": "", "searchkey": kw, "secDate": "", "tDate": "",
         "type": "", "isHLtitle": "true"}
    r = S.post("http://www.cninfo.com.cn/new/fulltextSearch/full", data=d, timeout=30)
    j = r.json()
    out = []
    for a in (j.get("announcements") or []):
        t = re.sub(r"<[^>]+>", "", a.get("announcementTitle", ""))
        tm = a.get("announcementTime")
        import datetime
        ts = datetime.datetime.fromtimestamp(tm / 1000).strftime("%Y-%m-%d") if tm else ""
        out.append({"ts": ts, "code": a.get("secCode"), "name": a.get("secName"),
                    "title": t, "url": "http://static.cninfo.com.cn/" + (a.get("adjunctUrl") or "")})
    return j.get("totalRecordNum"), out

# 金额抽取
AMT = re.compile(r"([\d,\.]+)\s*(亿元|万元|亿|万)")

def extract_amount(title):
    m = AMT.search(title)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    u = m.group(2)
    if u.startswith("亿"):
        return v * 1e8
    return v * 1e4

for kw in ["收购", "受让", "竞得", "中标", "增资", "以集中竞价"]:
    try:
        total, rows = search(kw, 20)
    except Exception as e:
        print(f"[{kw}] FAIL {type(e).__name__}")
        continue
    print(f"\n{'='*70}\n【{kw}】 total={total} 取{len(rows)}条")
    for r in rows[:8]:
        amt = extract_amount(r["title"])
        amt_s = f"{amt/1e8:.2f}亿" if amt else "—"
        print(f"  {r['ts']} {r['code']} {r['name']:8s} 金额={amt_s:>8s} | {r['title'][:58]}")
