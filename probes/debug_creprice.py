# -*- coding: utf-8 -*-
"""调试 house_price_city 解析失败原因。"""
import re
from smartmoney.core import session

s = session()
s.headers.update({"Referer": "https://www.creprice.cn/"})

for code in ["bj", "sh"]:
    u = f"https://www.creprice.cn/city/{code}.html"
    r = s.get(u, timeout=25)
    r.encoding = "utf-8"
    print(f"--- {code} ---")
    print("status", r.status_code, "len", len(r.content), "textlen", len(r.text))

    b = re.sub(r"<script.*?</script>", " ", r.text, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    t = re.sub(r"\s+", " ", b)

    i = t.find("挂牌")
    print("挂牌位置:", i)
    if i > 0:
        print("上下文:", t[max(0, i - 120):i + 120])

    m1 = re.search(r"(\d{4})年(\d{1,2})月\s*挂牌\s*([\d\.]+)\s*万元/㎡"
                   r"(?:\s*环比[：:]\s*([\-\d\.]+)%)?", t)
    m2 = re.search(r"月度房价\s*(\d{4})年(\d{1,2})月", t)
    print("严格匹配:", m1.groups() if m1 else None)
    print("月度房价:", m2.groups() if m2 else None)
