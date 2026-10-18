"""历史记录与翻译缓存（SQLite，单文件，仅本机）。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time

from config_store import HISTORY_DB

_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None


def _conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(str(HISTORY_DB), check_same_thread=False, timeout=10)
        _CONN.row_factory = sqlite3.Row
        _CONN.execute("PRAGMA journal_mode=WAL")
        _CONN.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                direction TEXT NOT NULL,
                name TEXT,
                src_lang TEXT,
                target TEXT,
                original TEXT,
                translated TEXT,
                ms INTEGER,
                ok INTEGER,
                error TEXT
            )
            """
        )
        _CONN.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                ts REAL NOT NULL,
                value TEXT NOT NULL
            )
            """
        )
        _CONN.commit()
    return _CONN


def init() -> None:
    with _LOCK:
        _conn()


def add_history(direction, name, src_lang, target, original, translated, ms, ok, error=None) -> int:
    with _LOCK:
        c = _conn()
        cur = c.execute(
            "INSERT INTO history (ts,direction,name,src_lang,target,original,translated,ms,ok,error)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (time.time(), direction, name or "", src_lang or "", target or "",
             original or "", translated or "", int(ms or 0), 1 if ok else 0, error or ""),
        )
        c.commit()
        return int(cur.lastrowid)


def history(limit: int = 50, offset: int = 0, direction: str | None = None) -> list[dict]:
    limit = max(1, min(int(limit or 50), 500))
    with _LOCK:
        c = _conn()
        if direction in ("in", "out"):
            rows = c.execute(
                "SELECT * FROM history WHERE direction=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (direction, limit, offset),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM history ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    day_ago = time.time() - 86400
    with _LOCK:
        c = _conn()
        total = c.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        today = c.execute("SELECT COUNT(*) FROM history WHERE ts>=?", (day_ago,)).fetchone()[0]
        ok = c.execute(
            "SELECT COUNT(*) FROM history WHERE ts>=? AND ok=1", (day_ago,)
        ).fetchone()[0]
        avg = c.execute(
            "SELECT AVG(ms) FROM history WHERE ts>=? AND ok=1", (day_ago,)
        ).fetchone()[0]
    return {
        "total": total,
        "today": today,
        "today_ok": ok,
        "avg_ms": round(avg or 0),
    }


def cache_get(key: str, ttl: float = 6 * 3600):
    with _LOCK:
        c = _conn()
        row = c.execute("SELECT ts,value FROM cache WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    if time.time() - row["ts"] > ttl:
        return None
    try:
        return json.loads(row["value"])
    except ValueError:
        return None


def cache_put(key: str, value) -> None:
    with _LOCK:
        c = _conn()
        c.execute(
            "INSERT INTO cache(key,ts,value) VALUES(?,?,?)"
            " ON CONFLICT(key) DO UPDATE SET ts=excluded.ts,value=excluded.value",
            (key, time.time(), json.dumps(value, ensure_ascii=False, separators=(",", ":"))),
        )
        c.commit()


def cache_prune(max_age: float = 7 * 86400) -> None:
    with _LOCK:
        c = _conn()
        c.execute("DELETE FROM cache WHERE ts<?", (time.time() - max_age,))
        c.commit()
