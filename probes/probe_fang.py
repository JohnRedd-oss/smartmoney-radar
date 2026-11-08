# -*- coding: utf-8 -*-
"""房天下房价页结构解析。"""
import requests, re

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
s = requests.Session()
s.headers.update({"User-Agent": UA, "Referer": "https://www.fang.com/"})

r = s.get("https://fangjia.fang.com/", timeout=25)
r.encoding = "utf-8"
print("status", r.status_code, "len", len(r.content))

b = re.sub(r"<script.*?</script>", " ", r.text, flags=re.S)
b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
b = re.sub(r"<[^>]+>", " ", b)
t = re.sub(r"\s+", " ", b)

# 找出所有 元/平 的上下文
print("\n=== 元/平 上下文 ===")
for m in re.finditer(r"([\u4e00-\u9fa5]{2,8})\s*(\d{4,6})\s*元/平", t):
    print(f"  {m.group(1)} -> {m.group(2)}")

print("\n=== 前 30 个价格数字上下文 ===")
for m in list(re.finditer(r"(\d{4,6})\s*元", t))[:15]:
    st = max(0, m.start() - 60)
    print(f"  ...{t[st:m.end()+10]}")

print("\n=== 正文前 800 字 ===")
print(t[:800])
