# -*- coding: utf-8 -*-
"""房天下城市房价 URL 格式 + 解析器验证。"""
import requests, re, time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
s = requests.Session()
s.headers.update({"User-Agent": UA, "Referer": "https://www.fang.com/"})

def plain(h):
    b = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    return re.sub(r"\s+", " ", b)

CN_MONTH = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,
            "七":7,"八":8,"九":9,"十":10,"十一":11,"十二":12}

PAT = re.compile(
    r"([\u4e00-\u9fa5]{1,3})月二手房参考均价\s*([\d\.]{4,7})\s*元/平"
    r"\s*比上月(上涨|下跌|持平)\s*([\d\.]+)?%?")

def parse(html):
    t = plain(html)
    m = PAT.search(t)
    if not m:
        return None
    mon = CN_MONTH.get(m.group(1))
    price = float(m.group(2))
    chg = float(m.group(4)) if m.group(4) else 0.0
    if m.group(3) == "下跌":
        chg = -chg
    # 标题里拿城市名和年份
    y = re.search(r"(\d{4})-\d{2}\s*房天下", t)
    city = re.search(r"^([\u4e00-\u9fa5]{2,6})房价_", t.strip())
    return {"month": mon, "price": price, "chg": chg,
            "year": y.group(1) if y else None,
            "city_guess": city.group(1) if city else None}

# 测试不同 URL 形态
tests = [
    "https://fangjia.fang.com/",
    "https://fangjia.fang.com/beijing/",
    "https://bj.fangjia.fang.com/",
    "https://fangjia.fang.com/sh/",
    "https://sh.fangjia.fang.com/",
    "https://fangjia.fang.com/city/beijing/",
]
for u in tests:
    try:
        r = s.get(u, timeout=20)
        r.encoding = "utf-8"
        p = parse(r.text)
        title = re.search(r"<title>([^<]{0,40})", r.text)
        print(f"  {u:44s} {r.status_code} len={len(r.content):>6} "
              f"title={title.group(1) if title else '?'}")
        print(f"       解析: {p}")
    except Exception as e:
        print(f"  {u:44s} FAIL {type(e).__name__}")
    time.sleep(1.2)
