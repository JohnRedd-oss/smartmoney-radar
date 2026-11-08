# -*- coding: utf-8 -*-
"""分城市房价备选源：安居客 / 房天下。"""
import requests, re, time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def plain(h):
    b = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    return re.sub(r"\s+", " ", b)

# --- 安居客城市房价 ---
print("=== 安居客 ===")
s = requests.Session()
s.headers.update({"User-Agent": UA, "Referer": "https://www.anjuke.com/"})
for city in ["beijing", "shanghai", "shenzhen"]:
    for u in [f"https://www.anjuke.com/fangjia/{city}/",
              f"https://{city}.anjuke.com/fangjia/"]:
        try:
            r = s.get(u, timeout=20)
            r.encoding = "utf-8"
            t = plain(r.text)
            m = re.findall(r"(\d{4,6})\s*元/㎡", t)
            m2 = re.findall(r"均价[：:\s]*([\d,\.]+)\s*元", t)
            print(f"  {u} -> {r.status_code} len={len(r.content)} 元/㎡={len(m)} {m[:4]} 均价={m2[:3]}")
        except Exception as e:
            print(f"  {u} -> FAIL {type(e).__name__} {str(e)[:50]}")
        time.sleep(1)

# --- 房天下 ---
print("\n=== 房天下 ===")
s2 = requests.Session()
s2.headers.update({"User-Agent": UA, "Referer": "https://www.fang.com/"})
for u in ["https://industry.fang.com/index/",
          "https://newhouse.fang.com/house/s/",
          "https://fangjia.fang.com/"]:
    try:
        r = s2.get(u, timeout=20)
        r.encoding = "utf-8"
        t = plain(r.text)
        m = re.findall(r"(\d{4,6})\s*元/平", t)
        print(f"  {u} -> {r.status_code} len={len(r.content)} 命中={len(m)} {m[:4]}")
    except Exception as e:
        print(f"  {u} -> FAIL {type(e).__name__}")
    time.sleep(1)

# --- creprice 恢复检查 ---
print("\n=== creprice 恢复检查 ===")
s3 = requests.Session()
s3.headers.update({"User-Agent": UA, "Referer": "https://www.creprice.cn/"})
r = s3.get("https://www.creprice.cn/city/bj.html", timeout=20)
r.encoding = "utf-8"
print(f"  len={len(r.content)} 被限={'验证码' in r.text}")
