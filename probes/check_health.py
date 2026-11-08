# -*- coding: utf-8 -*-
import requests

BASE = "http://127.0.0.1:8848"
s = requests.get(BASE + "/api/summary", timeout=90).json()
print("as_of:", s["as_of"], "facts:", s["stats"]["facts"])
print("--- health ---")
for h in s["health"]:
    mark = "OK " if h["ok"] else ("BAD" if h["ok"] is False else "---")
    print(f"{mark} {h['label']:<10} {h['src']:<26} {h['detail']}")
print("--- narrative ---")
for n in s["narrative"]:
    print("  ", n)
