# -*- coding: utf-8 -*-
"""smartmoney.cli — 每日运行入口。

用法：
    python -m smartmoney.cli run          # 全量采集 + 出报
    python -m smartmoney.cli run --skip 13f,land
    python -m smartmoney.cli report       # 只出报，不采集
    python -m smartmoney.cli signals      # 只看历史信号
"""
import sys
import json
import traceback
from datetime import datetime

from .core import db, now_cst, DB_PATH
from . import collectors, rules

STEPS = [
    ("safe_gold", collectors.safe_gold),
    ("gold_price", collectors.gold_price),
    ("multi", collectors.multi_asset),          # 多资产行情：黄金/铜/原油/股指/汇率/债
    ("smartbuy", collectors.smart_money_buy),   # 聪明钱下场买了什么
    ("cninfo", collectors.cninfo_announcements),
    ("insider", collectors.insider_trades),
    ("block", collectors.block_trades),
    ("13f", collectors.sec_13f),
    ("stats70", collectors.stats70),            # 70城房价指数（官方口径，区域背景）
]


def collect(skip=()):
    con = db()
    started = now_cst().isoformat(timespec="seconds")
    stats = {}
    for name, fn in STEPS:
        if name in skip:
            continue
        try:
            stats[name] = fn(con)
            con.commit()
            print(f"  [OK]   {name}: {stats[name]}")
        except Exception as e:
            con.rollback()
            stats[name] = f"FAIL {type(e).__name__}: {str(e)[:160]}"
            print(f"  [FAIL] {name}: {type(e).__name__} {str(e)[:160]}")
    con.execute("INSERT INTO runs (started, ended, ok, stats) VALUES (?,?,?,?)",
                (started, now_cst().isoformat(timespec="seconds"),
                 1 if not any(isinstance(v, str) and v.startswith("FAIL") for v in stats.values()) else 0,
                 json.dumps(stats, ensure_ascii=False, default=str)))
    con.commit()
    con.close()
    return stats


def build_report():
    con = db()
    signals = rules.run_all(con)
    today = now_cst().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"# 聪明钱雷达 · 日报 {today}")
    lines.append("")
    lines.append(f"> 生成时间 {now_cst().strftime('%Y-%m-%d %H:%M:%S %Z')} · "
                 f"库 {DB_PATH}")
    lines.append("")

    changes = [s for s in signals if s[0] not in ("_error",)]
    errors = [s for s in signals if s[0] == "_error"]

    # 摘要层：每条 CHNAGE 压成一行，供扫读
    lines.append("## 零、一句话摘要")
    lines.append("")
    if not changes:
        lines.append("_今日无新变化。_")
    else:
        for rule, ts, sentence, payload in changes:
            head = sentence.split("；")[0].split("。")[0]
            lines.append(f"- **{rule}** · {head}")
    lines.append("")

    lines.append("## 一、今日变化（CHANGE）")
    lines.append("")
    if not changes:
        lines.append("_今日无新变化。_")
    for rule, ts, sentence, payload in changes:
        lines.append(f"- **[{ts}]** {sentence}")
    lines.append("")

    lines.append("## 二、当前状态（STATE）")
    lines.append("")
    con.row_factory = None
    # 央行黄金快照
    rows = con.execute(
        "SELECT ts, value, amount_usd FROM facts WHERE entity='PBOC' "
        "AND metric='gold_reserve_wan_oz' ORDER BY ts DESC LIMIT 12").fetchall()
    if rows:
        lines.append("### 央行黄金储备（万盎司 / 折亿美元）")
        lines.append("")
        lines.append("| 月份 | 万盎司 | 折亿美元 | 环比(万盎司) |")
        lines.append("|---|---|---|---|")
        # ts DESC：下一行是更早的月份，环比 = 本行 - 下一行
        for i, r in enumerate(rows):
            d = "—" if i + 1 >= len(rows) else f"{r[1] - rows[i+1][1]:+,.0f}"
            usd = f"{r[2]:,.2f}" if r[2] is not None else "—"
            lines.append(f"| {r[0][:7]} | {r[1]:,.0f} | {usd} | {d} |")
        lines.append("")

    # 13F 快照
    f13 = con.execute(
        "SELECT entity, ts, COUNT(*) n, SUM(amount_usd)/1e8 total FROM facts "
        "WHERE source='SEC 13F' GROUP BY entity, ts ORDER BY ts DESC LIMIT 8").fetchall()
    if f13:
        lines.append("### 国家资本海外腿（13F）")
        lines.append("")
        lines.append("| 主体 | 报告期 | 持仓数 | 市值(亿美元) |")
        lines.append("|---|---|---|---|")
        for e, ts, n, total in f13:
            lines.append(f"| {e} | {ts} | {n} | {total:,.1f} |")
        lines.append("")

    if errors:
        lines.append("## 三、异常")
        lines.append("")
        for _, name, msg, _ in errors:
            lines.append(f"- {msg}")
        lines.append("")

    con.close()
    return "\n".join(lines)


def dump_signals(limit=30):
    con = db()
    con.row_factory = None
    rows = con.execute(
        "SELECT ts, rule, sentence FROM signals ORDER BY created DESC LIMIT ?",
        (limit,)).fetchall()
    con.close()
    return rows


def main(argv=None):
    argv = argv or sys.argv[1:]
    cmd = argv[0] if argv else "run"
    skip = set()
    out_path = None
    for a in argv:
        if a.startswith("--skip"):
            skip = set(x.strip() for x in a.split("=", 1)[-1].split(","))
        elif a.startswith("--out="):
            out_path = a.split("=", 1)[1]

    def emit(text):
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"已写入 {out_path}（{len(text)} 字符）")
        else:
            print(text)

    if cmd == "run":
        print("采集开始...")
        stats = collect(skip)
        print("\n生成报告...\n")
        emit(build_report())
    elif cmd == "report":
        emit(build_report())
    elif cmd == "signals":
        for ts, rule, s in dump_signals():
            print(f"[{ts}] ({rule}) {s}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
