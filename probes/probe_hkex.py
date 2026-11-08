# -*- coding: utf-8 -*-
"""HKEX 权益披露 + 政府采购 二次探测（带完整浏览器指纹）。"""
import requests, re, json

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
})

def show(n, fn):
    try:
        print(f"[OK] {n}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {n}: {type(e).__name__} {str(e)[:140]}")

# HKEX DI：先访问搜索页拿 session
def hkex_sess():
    r1 = S.get("https://di.hkex.com.hk/di/summary/SummaryOfInterests.aspx?lang=ZH", timeout=25)
    print("   page1", r1.status_code, len(r1.text))
    print("   cookies", list(S.cookies.keys()))
    r2 = S.get("https://di.hkex.com.hk/di/summary/SummaryOfInterests.aspx?lang=ZH", timeout=25)
    return r2.status_code, len(r2.text), ("權益" in r2.text or "权益" in r2.text)

# 政府采购 存量商品房
def ccgp_house():
    u = ("http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&bidSort=0"
         "&kw=%E5%AD%98%E9%87%8F%E5%95%86%E5%93%81%E6%88%BF&timeType=6"
         "&start_time=2026%3A01%3A01&end_time=2026%3A11%3A08&dbselect=bidx")
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    titles = re.findall(r'<a href="([^"]+)"[^>]*target="_blank"[^>]*>(.*?)</a>', r.text, re.S)
    clean = [(h, re.sub(r"<[^>]+>", "", t).strip()[:60]) for h, t in titles]
    return r.status_code, len(clean), clean[:5]

show("HKEX_会话", hkex_sess)
show("政采_存量商品房", ccgp_house)
