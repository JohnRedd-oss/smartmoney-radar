# -*- coding: utf-8 -*-
"""SAFE 官方储备资产页解析：定位黄金储备数值。"""
import requests, re

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
U = "https://www.safe.gov.cn/safe/2026/0205/27113.html"

r = requests.get(U, timeout=20, headers=H)
r.encoding = "utf-8"
t = r.text
print("status", r.status_code, "len", len(t))

print("--- attachments ---")
for m in re.finditer(r'(?:href|src)="([^"]+\.(?:xlsx|xls|pdf|doc|htm|html))"', t):
    print(" ", m.group(1))

print("--- tables ---")
tabs = re.findall(r"<table.*?</table>", t, re.S)
print("count", len(tabs))
for tb in tabs[:3]:
    s = re.sub(r"<[^>]+>", " | ", tb)
    s = re.sub(r"(\s*\|\s*)+", " | ", s)
    s = re.sub(r"\s+", " ", s)
    print(s[:1500])
    print("====")
