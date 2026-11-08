# -*- coding: utf-8 -*-
"""SAFE 官方储备资产：全行导出，定位黄金储备（万盎司）与折美元。"""
import requests, io, re, json
import openpyxl

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://www.safe.gov.cn"
PAGE = BASE + "/safe/2026/0205/27113.html"

r = requests.get(PAGE, timeout=20, headers=H)
r.encoding = "utf-8"
x = re.findall(r'href="(/safe/file/file/[^"]+\.xlsx)"', r.text)[0]
d = requests.get(BASE + x, timeout=30, headers=H)
wb = openpyxl.load_workbook(io.BytesIO(d.content), data_only=True)
ws = wb["Sheet1"]

rows = []
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True), 1):
    cells = [("" if c is None else str(c).strip()) for c in row]
    if any(cells):
        rows.append((i, cells))

for i, cells in rows:
    line = " | ".join(c for c in cells if c)
    print(f"r{i:02d}: {line[:260]}")

print("\n=== 黄金相关行原始值 ===")
for i, cells in rows:
    joined = "".join(cells)
    if "黄金" in joined or "盎司" in joined:
        print(f"r{i}: {cells[:25]}")
