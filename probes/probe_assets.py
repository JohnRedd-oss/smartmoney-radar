# -*- coding: utf-8 -*-
"""区域房价 / 收储成本 / 多资产行情 数据源探测。"""
import requests, json, re

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
    except Exception as e:
        print(f"[FAIL] {name}: {type(e).__name__} {str(e)[:130]}")


# ---------- 1. 国家统计局 70城房价（分城市，最权威的区域维度） ----------
def stats_70():
    u = "https://data.stats.gov.cn/easyquery.htm"
    # 先建 session
    S.get("https://data.stats.gov.cn/", timeout=20)
    p = {"m": "QueryData", "dbcode": "fsyd", "rowcode": "reg",
         "colcode": "sj", "wds": "[]", "dfwds": '[{"wdcode":"zb","valuecode":"A010801"}]'}
    r = S.get(u, params=p, timeout=25, verify=False)
    j = r.json()
    return r.status_code, str(j)[:200]


# ---------- 2. 东财 70城房价 / 房地产数据 ----------
def em_house():
    out = {}
    for rn in ["RPT_ECONOMY_HOUSE_PRICE", "RPT_ECONOMY_CPI",
               "RPT_ECONOMY_GDP", "RPT_ECONOMY_PMI"]:
        u = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
             f"reportName={rn}&columns=ALL&pageNumber=1&pageSize=5&source=WEB&client=WEB")
        try:
            j = S.get(u, timeout=20).json()
            d = (j.get("result") or {}).get("data")
            out[rn] = f"{j.get('success')} rows={len(d) if d else 0}"
        except Exception as e:
            out[rn] = f"FAIL {type(e).__name__}"
    return out


# ---------- 3. 东财 多资产行情（黄金/原油/铜/债/汇率/指数/加密） ----------
def em_multi_asset():
    targets = {
        "沪金9999": "118.au9999", "COMEX黄金": "101.GC00Y",
        "沪银": "113.agm", "原油WTI": "101.CL00Y", "布伦特": "101.B00Y",
        "沪铜": "113.cum", "螺纹钢": "113.rbm",
        "上证指数": "1.000001", "沪深300": "1.000300", "创业板指": "0.399006",
        "恒生指数": "100.HSI", "纳斯达克": "100.NDX", "标普500": "100.SPX",
        "美元指数": "100.UDI", "美元人民币": "133.USDCNH",
        "10年国债": "1.019547", "比特币": "120.BTC",
    }
    out = {}
    for name, secid in targets.items():
        u = (f"https://push2.eastmoney.com/api/qt/stock/get?"
             f"secid={secid}&fields=f43,f58,f60,f170")
        try:
            j = S.get(u, timeout=12).json()
            d = j.get("data") or {}
            out[name] = (d.get("f58"), d.get("f43"), d.get("f170"))
        except Exception as e:
            out[name] = f"FAIL {type(e).__name__}"
    return out


# ---------- 4. 东财 房地产板块 / 保障房概念 ----------
def em_reits():
    u = ("https://push2.eastmoney.com/api/qt/clist/get?"
         "pn=1&pz=10&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f12,f14,f3")
    r = S.get(u, timeout=20)
    j = r.json()
    d = (j.get("data") or {}).get("diff")
    return len(d) if d else 0


# ---------- 5. 克而瑞/中指 公开数据（抽样） ----------
def cri_index():
    for u in ["https://www.cricchina.com/", "https://www.fang.com/",
              "https://industry.fang.com/"]:
        try:
            r = S.get(u, timeout=15)
            print(f"      {u} -> {r.status_code} {len(r.text)}")
        except Exception as e:
            print(f"      {u} -> FAIL {str(e)[:50]}")


# ---------- 6. 地方公共资源交易中心：搜"存量商品房" ----------
def local_search():
    out = {}
    for name, u in [
        ("广东", "https://ygp.gdzwfw.gov.cn/ggzy-portal/search?keyword=%E5%AD%98%E9%87%8F%E5%95%86%E5%93%81%E6%88%BF"),
        ("四川", "https://ggzyjy.sc.gov.cn/jyxx/transactionInfo.html"),
    ]:
        try:
            r = S.get(u, timeout=15)
            r.encoding = "utf-8"
            out[name] = (r.status_code, len(r.text), "存量商品房" in r.text)
        except Exception as e:
            out[name] = f"FAIL {type(e).__name__}"
    return out


print("=" * 72)
t("统计局70城", stats_70)
t("东财宏观报表", em_house)
t("东财多资产", em_multi_asset)
t("东财板块", em_reits)
t("克而瑞抽样", cri_index)
t("地方交易中心搜索", local_search)
