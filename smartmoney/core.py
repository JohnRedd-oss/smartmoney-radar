# -*- coding: utf-8 -*-
"""smartmoney.core — 基础设施：HTTP 会话、SQLite、归一化 schema。

schema 设计原则：一条记录 = 一个可验证的事实，必须带 source_url。
没有 source_url 的记录不进库。这是防止日报变成谣言的第一道闸。
"""
import sqlite3
import time
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

import requests

CST = timezone(timedelta(hours=8))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "smartmoney.db")

UA_POOL = {
    "default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # SEC 要求可识别 UA，带联系方式
    "sec": "Zhudong Research research@example.com",
}


def session(kind="default"):
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA_POOL.get(kind, UA_POOL["default"]),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    return s


def now_cst():
    return datetime.now(CST)


# ---------------------------------------------------------------- schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id          TEXT PRIMARY KEY,
    ts          TEXT NOT NULL,      -- 数据所属期 YYYY-MM-DD
    collected   TEXT NOT NULL,      -- 采集时刻
    entity      TEXT NOT NULL,      -- 主体：PBOC / Wutongshu / 某上市公司
    action      TEXT NOT NULL,      -- buy / sell / hold / issue / announce
    asset       TEXT NOT NULL,      -- gold / equity / house / bond
    metric      TEXT NOT NULL,      -- 指标名，如 gold_reserve_oz
    value       REAL,
    unit        TEXT,
    amount_usd  REAL,               -- 折算美元，可为空
    price       REAL,               -- 单价，可为空
    detail      TEXT,               -- JSON 扩展
    source      TEXT NOT NULL,      -- 源标识
    source_url  TEXT NOT NULL,
    confidence  TEXT NOT NULL,      -- high / medium / low
    lag_days    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_facts_ts ON facts(ts);
CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity, metric);

CREATE TABLE IF NOT EXISTS signals (
    id          TEXT PRIMARY KEY,
    ts          TEXT NOT NULL,
    rule        TEXT NOT NULL,
    sentence    TEXT NOT NULL,
    payload     TEXT,
    created     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);

CREATE TABLE IF NOT EXISTS runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    started  TEXT,
    ended    TEXT,
    ok       INTEGER,
    stats    TEXT
);
"""


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def fid(*parts):
    """确定性 id，保证同一事实重复采集幂等。"""
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return h[:20]


def upsert_fact(con, **kw):
    """写入一条事实。source_url 为空直接拒收。"""
    if not kw.get("source_url"):
        raise ValueError("拒收：无 source_url 的事实不进库")
    key = fid(kw["entity"], kw["metric"], kw["ts"], kw.get("value"), kw["source"])
    kw.setdefault("collected", now_cst().isoformat(timespec="seconds"))
    kw.setdefault("confidence", "high")
    kw.setdefault("lag_days", 0)
    kw.setdefault("detail", None)
    if isinstance(kw.get("detail"), (dict, list)):
        kw["detail"] = json.dumps(kw["detail"], ensure_ascii=False)
    cols = ["id", "ts", "collected", "entity", "action", "asset", "metric",
            "value", "unit", "amount_usd", "price", "detail", "source",
            "source_url", "confidence", "lag_days"]
    kw["id"] = key
    vals = [kw.get(c) for c in cols]
    ph = ",".join("?" * len(cols))
    con.execute(f"INSERT OR REPLACE INTO facts ({','.join(cols)}) VALUES ({ph})", vals)
    return key


def save_signal(con, ts, rule, sentence, payload=None):
    sid = fid(rule, ts, sentence)
    con.execute(
        "INSERT OR REPLACE INTO signals (id, ts, rule, sentence, payload, created) "
        "VALUES (?,?,?,?,?,?)",
        (sid, ts, rule, sentence,
         json.dumps(payload, ensure_ascii=False) if payload else None,
         now_cst().isoformat(timespec="seconds")))
    return sid


def polite_sleep(lo=0.4, hi=0.9):
    """对外源保持克制，避免被封。"""
    time.sleep(lo + (hi - lo) * (os.getpid() % 10) / 10.0)


def fetch_json(s, url, params=None, retries=3, backoff=2.0):
    last = None
    for i in range(retries):
        try:
            r = s.get(url, params=params, timeout=25)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(backoff * (i + 1))
    raise RuntimeError(f"fetch_json 失败 {url}: {last}")


def fetch_bytes(s, url, params=None, retries=3):
    last = None
    for i in range(retries):
        try:
            r = s.get(url, params=params, timeout=40)
            if r.status_code == 200:
                return r.content
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"fetch_bytes 失败 {url}: {last}")
