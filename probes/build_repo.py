# -*- coding: utf-8 -*-
"""组装干净的 GitHub 仓库目录：只含 smartmoney 项目本身，剔除缓存与无关文件。"""
import os
import shutil

SRC = r"E:\deepssk"
DST = r"E:\deepssk\smartmoney-radar"

# 目标目录
if os.path.exists(DST):
    shutil.rmtree(DST)
os.makedirs(DST)

def copy(src, dst_rel=None):
    rel = dst_rel or os.path.relpath(src, SRC)
    dst = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  + {rel}")

print("=== 复制包源码 ===")
pkg = os.path.join(SRC, "smartmoney")
for root, dirs, files in os.walk(pkg):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith((".pyc", ".pyo")):
            continue
        p = os.path.join(root, f)
        copy(p)

print("=== 复制测试与脚本 ===")
for name in ["test_smartmoney.py", "run.ps1", "run.bat"]:
    p = os.path.join(SRC, name)
    if os.path.exists(p):
        copy(p)

print("=== 复制探测脚本 ===")
probes = os.path.join(SRC, "probes")
if os.path.isdir(probes):
    for f in sorted(os.listdir(probes)):
        p = os.path.join(probes, f)
        if os.path.isfile(p) and f.endswith((".py", ".json")):
            copy(p)

print("=== 复制日报 ===")
reports = os.path.join(SRC, "reports")
if os.path.isdir(reports):
    for f in sorted(os.listdir(reports)):
        if f.endswith(".md"):
            copy(os.path.join(reports, f))

print("=== 复制截图（仅 smartmoney 相关）===")
shots = os.path.join(SRC, "shots")
KEEP = {"sm3.png", "sm4.png", "sm5.png", "smartmoney-full.png"}
if os.path.isdir(shots):
    for f in sorted(os.listdir(shots)):
        if f in KEEP:
            copy(os.path.join(shots, f), os.path.join("screenshots", f))

# 统计
total = sum(os.path.getsize(os.path.join(r, f))
            for r, _, fs in os.walk(DST) for f in fs)
n = sum(len(fs) for _, _, fs in os.walk(DST))
print(f"\n共 {n} 个文件，{total/1024:.0f} KB")
print("输出目录:", DST)
