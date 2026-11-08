# -*- coding: utf-8 -*-
"""看 creprice 城市页里到底有没有可解析的均价数字。"""
import requests, re

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.creprice.cn/",
})

r = S.get("https://www.creprice.cn/city/bj.html", timeout=25)
r.encoding = "utf-8"
t = r.text
print("len", len(t))

# 找所有数字上下文
for pat, label in [
    (r'(\d{4,6})\s*元', "元"),
    (r'"price"\s*:\s*"?([\d\.]+)', "price字段"),
    (r'均价[：:\s]*([\d,\.]+)', "均价"),
    (r'(\d{2,3}\.\d{1,2})\s*万', "万元"),
]:
    m = re.findall(pat, t)
    print(f"{label}: {len(m)} → {m[:8]}")

print("\n--- 页面正文片段（去标签）---")
body = re.sub(r"<script.*?</script>", " ", t, flags=re.S)
body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
body = re.sub(r"<[^>]+>", " ", body)
body = re.sub(r"\s+", " ", body)
print(body[:1200])
