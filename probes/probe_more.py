# -*- coding: utf-8 -*-
"""港股权益披露 + 政府采购 + 巨潮分类，三源探测。"""
import requests, json

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})

def p(n, fn):
    try:
        print(f"[OK] {n}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {n}: {type(e).__name__} {str(e)[:140]}")

# 1) HKEX DI 权益披露搜索（POST JSON）
def hkex():
    u = "https://di.hkex.com.hk/di/DPIPWebService.asmx/GetDPIPSearch"
    body = {"lang": "ZH", "market": "MAIN", "from": "20260101", "to": "20261108",
            "role": "0", "shType": "0", "shName": "", "shNameClause": "0"}
    r = S.post(u, json=body, timeout=20)
    return r.status_code, len(r.text), r.text[:200]

# 2) HKEX DI 首页拿 cookie 后再试
def hkex2():
    r0 = S.get("https://di.hkex.com.hk/di/NSSrchCorpList.aspx?sa2=cl&lang=ZH", timeout=20)
    return r0.status_code, len(r0.text)

# 3) 政府采购网 收储/收购
def ccgp():
    u = ("http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&bidSort=0"
         "&buyerName=&projectId=&pinMu=0&bidType=0&dbselect=bidx&kw=%E6%94%B6%E8%B4%AD"
         "&start_time=2026%3A01%3A01&end_time=2026%3A11%3A08&timeType=6&displayZone=&zoneId=&pppStatus=0&agentName=")
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    import re
    n = len(re.findall(r"<li>", r.text))
    return r.status_code, len(r.text), "收储" in r.text, n

# 4) 巨潮 分类检索（减持类）
def cninfo_cat():
    u = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    d = {"pageNum": "1", "pageSize": "30", "column": "szse", "tabName": "fulltext",
         "plate": "", "stock": "", "searchkey": "", "secDate": "", "tDate": "",
         "type": "category_jjzc_szsh", "isHLtitle": "true"}
    h = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
         "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice"}
    r = S.post(u, data=d, timeout=25, headers=h)
    j = r.json()
    return j.get("totalAnnouncement"), (j.get("announcements") or [])[:2]

p("HKEX_JSON", hkex)
p("HKEX_HTML", hkex2)
p("CCGP_收储", ccgp)
p("CNINFO_分类", cninfo_cat)
