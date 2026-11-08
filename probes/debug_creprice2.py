# -*- coding: utf-8 -*-
"""看 creprice 拦截页内容，并对比不同请求头。"""
import requests, re

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

variants = {
    "A_仅UA+Referer": {"User-Agent": UA, "Referer": "https://www.creprice.cn/"},
    "B_UA+Referer+Lang": {"User-Agent": UA, "Referer": "https://www.creprice.cn/",
                          "Accept-Language": "zh-CN,zh;q=0.9"},
    "C_完整浏览器头": {
        "User-Agent": UA, "Referer": "https://www.creprice.cn/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin", "Sec-Fetch-User": "?1",
    },
}

for name, h in variants.items():
    s = requests.Session()
    s.headers.update(h)
    try:
        r = s.get("https://www.creprice.cn/city/bj.html", timeout=25)
        r.encoding = "utf-8"
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:220]
        print(f"[{name}] {r.status_code} len={len(r.content)}")
        print(f"    {body}")
    except Exception as e:
        print(f"[{name}] FAIL {type(e).__name__}")
    print()
