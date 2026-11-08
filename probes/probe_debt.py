# -*- coding: utf-8 -*-
"""专项债 / PSL 数据源探测。"""
import requests, re

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"})

def show(n, fn):
    try:
        print(f"[OK] {n}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {n}: {type(e).__name__} {str(e)[:120]}")

# 1) 中国债券信息网 地方债
def chinabond():
    u = "https://www.chinabond.com.cn/"
    r = S.get(u, timeout=20)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)

# 2) 财政部 地方政府债务信息公开平台
def mof_debt():
    u = "https://yss.mof.gov.cn/zhuantilanmu/dfzfzwxxgk/"
    r = S.get(u, timeout=20)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)

# 3) 央行 调查统计司 数据页
def pbc_stats():
    u = "http://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
    r = S.get(u, timeout=20)
    r.encoding = "utf-8"
    hits = re.findall(r'href="([^"]+)"[^>]*>\s*([^<]{4,50})', r.text)
    rel = [(h, t.strip()) for h, t in hits if "储备" in t or "贷款" in t or "PSL" in t]
    return r.status_code, len(rel), rel[:6]

# 4) 东财 房地产/保障房 板块资金流（替代信号）
def em_reit():
    u = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
         "?reportName=RPT_FUND_FLOW&columns=ALL&pageNumber=1&pageSize=3&source=WEB&client=WEB")
    r = S.get(u, timeout=20)
    return r.status_code, len(r.text)

show("中国债券信息网", chinabond)
show("财政部债务平台", mof_debt)
show("央行统计司", pbc_stats)
show("东财资金流", em_reit)
