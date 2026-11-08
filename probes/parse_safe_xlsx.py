# -*- coding: utf-8 -*-
"""SAFE 官方储备资产 xlsx 解析，验证黄金储备数值可提取。"""
import requests, io, re
import openpyxl

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://www.safe.gov.cn"
PAGE = BASE + "/safe/2026/0205/27113.html"

r = requests.get(PAGE, timeout=20, headers=H)
r.encoding = "utf-8"
xlsx = re.findall(r'href="(/safe/file/file/[^"]+\.xlsx)"', r.text)
print("xlsx found:", xlsx)

for x in xlsx:
    u = BASE + x
    d = requests.get(u, timeout=30, headers=H)
    print("download", u, d.status_code, len(d.content))
    wb = openpyxl.load_workbook(io.BytesIO(d.content), data_only=True)
    for ws in wb.worksheets:
        print("sheet:", ws.title, ws.max_row, ws.max_column)
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 14), values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            line = " | ".join(cells).strip()
            if line.strip(" |"):
                print("  ", line[:200])
    print("=" * 60)
