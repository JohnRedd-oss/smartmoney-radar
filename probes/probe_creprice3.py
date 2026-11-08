# -*- coding: utf-8 -*-
"""creprice 多城市房价解析验证。"""
import requests, re, time

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.creprice.cn/",
})

def text_of(html):
    b = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    return re.sub(r"\s+", " ", b)

# 单城市解析
def parse_city(code):
    u = f"https://www.creprice.cn/city/{code}.html"
    r = S.get(u, timeout=25)
    r.encoding = "utf-8"
    t = text_of(r.text)
    m = re.search(r"月度房价\s*(\d{4})年(\d{1,2})月\s*挂牌\s*([\d\.]+)\s*万元/㎡\s*环比[：:]\s*([\-\d\.]+)%", t)
    if not m:
        # 宽松模式
        m2 = re.search(r"(\d{4})年(\d{1,2})月\s*挂牌\s*([\d\.]+)\s*万元", t)
        return {"code": code, "raw": t[:0], "parsed": None,
                "loose": m2.groups() if m2 else None}
    return {"code": code, "period": f"{m.group(1)}-{int(m.group(2)):02d}",
            "price_wan": float(m.group(3)), "mom": float(m.group(4))}

for code in ["bj", "sh", "sz", "gz", "hz", "cd", "wh", "xa"]:
    try:
        res = parse_city(code)
        print(f"  {code}: {res}")
    except Exception as e:
        print(f"  {code}: FAIL {type(e).__name__} {str(e)[:60]}")
    time.sleep(0.6)

# 多城市排行页
print("\n=== 城市房价排行页 ===")
for u in ["https://www.creprice.cn/rank/citySel.html",
          "https://www.creprice.cn/rank/existCityAttraction.html"]:
    try:
        r = S.get(u, timeout=25)
        r.encoding = "utf-8"
        t = text_of(r.text)
        m = re.findall(r"([\u4e00-\u9fa5]{2,6})\s*([\d\.]{4,6})\s*元/㎡", t)
        print(f"  {u} -> {r.status_code} len={len(r.text)} 命中={len(m)} {m[:6]}")
    except Exception as e:
        print(f"  {u} -> FAIL {str(e)[:60]}")
