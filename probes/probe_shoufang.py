# -*- coding: utf-8 -*-
"""收房（存量商品房收储）数据源全面探测。

三条线必须分清：
  A. 土地收储 —— 政府从企业手里收地（landchina / 巨潮）
  B. 存量商品房收储 —— 地方国企收购已建成商品房转保障房（公共资源交易 / 专项债）
  C. 资金端 —— 央行 PSL / 保障性住房再贷款余额（央行 / 财政部）
"""
import requests, re, json, sys

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

def t(name, fn):
    try:
        r = fn()
        print(f"[OK]   {name}: {r}")
        return True
    except Exception as e:
        print(f"[FAIL] {name}: {type(e).__name__} {str(e)[:130]}")
        return False


# ---------- 1. 全国公共资源交易平台（最可能出 B 类数据） ----------
def ggzy():
    u = "http://deal.ggzy.gov.cn/ds/deal/dealList_find.jsp"
    d = {"TIMEBEGIN_SHOW": "2026-01-01", "TIMEEND_SHOW": "2026-11-08",
         "TIMEBEGIN": "2026-01-01", "TIMEEND": "2026-11-08",
         "SOURCE_TYPE": "1", "DEAL_TIME": "02", "DEAL_CLASSIFY": "01",
         "DEAL_STAGE": "0101", "DEAL_PROVINCE": "0", "DEAL_CITY": "0",
         "DEAL_PLATFORM": "0", "BID_PLATFORM": "0", "DEAL_TRADE": "0",
         "isShowAll": "1", "PAGENUMBER": "1", "FINDTXT": "存量商品房"}
    r = S.post(u, data=d, timeout=25)
    r.encoding = "utf-8"
    return r.status_code, len(r.text), "存量商品房" in r.text


# ---------- 2. 中国招标投标公共服务平台 ----------
def cebpub():
    u = "https://ctbpsp.com/cutominfo/getList"
    r = S.post(u, json={"keyword": "存量商品房", "pageNo": 1, "pageSize": 20}, timeout=25)
    return r.status_code, len(r.text), r.text[:120]


# ---------- 3. 中国债券信息网 地方债信息披露 ----------
def chinabond_dfz():
    u = "https://www.chinabond.com.cn/dfz/"
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    return r.status_code, len(r.text), ("专项债" in r.text or "地方债" in r.text)


# ---------- 4. 财政部 地方政府债务信息公开平台 ----------
def mof_debt():
    u = "https://yss.mof.gov.cn/zhuantilanmu/dfzfzwxxgk/"
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    links = re.findall(r'href="([^"]+)"[^>]*>\s*([^<]{4,40})', r.text)
    rel = [(h, x.strip()) for h, x in links if "债" in x or "专项" in x]
    return r.status_code, len(r.text), rel[:5]


# ---------- 5. 央行 PSL / 货币政策执行报告 ----------
def pbc_psl():
    u = "http://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/index.html"
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)


# ---------- 6. 央行 调查统计司 主要数据 ----------
def pbc_stats():
    u = "http://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)


# ---------- 7. 住建部 ----------
def mohurd():
    u = "https://www.mohurd.gov.cn/xinwen/gzdt/index.html"
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    return r.status_code, len(r.text)


# ---------- 8. 地方交易中心抽样：广东 / 浙江 / 江苏 / 河南 ----------
def local_centers():
    out = {}
    for name, u in [
        ("广东", "https://ygp.gdzwfw.gov.cn/"),
        ("浙江", "https://zjpubservice.zjzwfw.gov.cn/"),
        ("江苏", "http://jsggzy.jszwfw.gov.cn/"),
        ("河南", "http://www.hnsggzy.com/"),
        ("四川", "https://ggzyjy.sc.gov.cn/"),
    ]:
        try:
            r = S.get(u, timeout=15)
            r.encoding = "utf-8"
            out[name] = (r.status_code, len(r.text))
        except Exception as e:
            out[name] = f"FAIL {type(e).__name__}"
    return out


# ---------- 9. landchina 深挖：找真正的接口 ----------
def landchina_deep():
    r = S.get("https://www.landchina.com/", timeout=25)
    r.encoding = "utf-8"
    html = r.text
    # 找 js 里的接口路径
    apis = re.findall(r'["\'](/[a-zA-Z0-9_/\-]{6,60})["\']', html)
    apis = [a for a in apis if any(k in a.lower() for k in
            ("rest", "api", "list", "query", "search", "deal", "supply"))]
    return r.status_code, len(html), sorted(set(apis))[:20]


print("=" * 70)
t("全国公共资源交易平台", ggzy)
t("招标投标公共服务平台", cebpub)
t("中国债券信息网-地方债", chinabond_dfz)
t("财政部债务平台", mof_debt)
t("央行PSL页", pbc_psl)
t("央行统计司", pbc_stats)
t("住建部", mohurd)
t("地方交易中心抽样", local_centers)
t("landchina深挖", landchina_deep)
