# -*- coding: utf-8 -*-
"""最小验收测试（纯标准库，不依赖 pytest）。

运行：python test_smartmoney.py
"""
import os
import sqlite3
import sys
import tempfile

from smartmoney import core, rules


def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript(core.SCHEMA)
    return c, path


def t_reject_no_source(con):
    """第一道闸：无 source_url 的事实必须拒收。"""
    try:
        core.upsert_fact(con, ts="2026-01-01", entity="X", action="buy",
                         asset="gold", metric="m", value=1, unit="u",
                         source="s", source_url="")
    except ValueError:
        return
    raise AssertionError("无 source_url 的事实被放行")


def t_idempotent(con):
    """同一事实重复写入不应产生两行。"""
    kw = dict(ts="2026-01-01", entity="PBOC", action="hold", asset="gold",
              metric="gold_reserve_wan_oz", value=7419, unit="万盎司",
              source="SAFE", source_url="https://x")
    core.upsert_fact(con, **kw)
    core.upsert_fact(con, **kw)
    n = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    assert n == 1, f"期望 1 行，实际 {n}"


def t_gold_sentence(con):
    """句子带溯源尾巴，环比率值正确。"""
    for m, oz in [("2026-08-01", 7673.0), ("2026-09-01", 7747.0),
                  ("2026-10-01", 7830.0)]:
        core.upsert_fact(con, ts=m, entity="PBOC", action="hold", asset="gold",
                         metric="gold_reserve_wan_oz", value=oz, unit="万盎司",
                         source="SAFE", source_url="https://x")
    core.upsert_fact(con, ts="2026-10-01", entity="MARKET", action="hold",
                     asset="gold", metric="price_usd_oz", value=3885.0,
                     unit="美元/盎司", source="EM", source_url="https://y")
    core.upsert_fact(con, ts="2026-10-01", entity="MARKET", action="hold",
                     asset="gold", metric="price_cny_g", value=854.8,
                     unit="元/克", source="EM", source_url="https://y")

    out = rules.rule_pboc_gold(con)
    assert out, "应产出句子"
    _, _, sentence, payload = out[0]
    for tag in ("[源:", "置信:", "滞后:"):
        assert tag in sentence, f"句子缺溯源标签 {tag}"
    assert payload["delta_wan_oz"] == 83.0, payload


def t_cost_estimate(con):
    """成本 = 增量万盎司 × 10000 × 金价 / 1e8。"""
    for m, oz in [("2026-09-01", 7000.0), ("2026-10-01", 7100.0)]:
        core.upsert_fact(con, ts=m, entity="PBOC", action="hold", asset="gold",
                         metric="gold_reserve_wan_oz", value=oz, unit="万盎司",
                         source="SAFE", source_url="https://x")
    core.upsert_fact(con, ts="2026-10-01", entity="MARKET", action="hold",
                     asset="gold", metric="price_usd_oz", value=4000.0,
                     unit="美元/盎司", source="EM", source_url="https://y")
    payload = rules.rule_pboc_gold(con)[0][3]
    # 100 万盎司 × 4000 美元 = 40 亿美元
    assert abs(payload["cost_usd_yi"] - 40.0) < 0.01, payload


def t_negation_filter(con):
    """「未减持」「终止减持」不能算减持信号。"""
    titles = [
        ("A公司", "关于控股股东未减持公司股份的公告"),
        ("B公司", "关于控股股东终止减持计划的公告"),
        ("C公司", "关于控股股东减持股份的公告"),
    ]
    for ent, t in titles:
        core.upsert_fact(con, ts="2026-11-08", entity=ent, action="sell",
                         asset="equity", metric="announcement", value=None,
                         unit=None, source="巨潮", source_url="https://z",
                         detail={"title": t, "code": "000000"})
    payload = rules.rule_announcements(con, date="2026-11-08")[0][3]
    assert payload["hit"] == 3, payload
    assert payload["negated"] == 2, payload
    assert payload["sell"] == 1, payload


def t_empty_db_no_crash(con):
    """空库不产出句子，也不抛异常。"""
    assert rules.rule_pboc_gold(con) == []
    assert rules.rule_insider(con) == []
    assert rules.rule_block_trade(con) == []
    assert rules.rule_shouchu(con) == []


TESTS = [t_reject_no_source, t_idempotent, t_gold_sentence,
         t_cost_estimate, t_negation_filter, t_empty_db_no_crash]


def main():
    passed = failed = 0
    for fn in TESTS:
        con, path = fresh_db()
        try:
            fn(con)
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1
        finally:
            con.close()
            try:
                os.unlink(path)
            except OSError:
                pass
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
