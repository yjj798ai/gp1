# -*- coding: utf-8 -*-
"""腾讯行情API采集 — 量比 + 换手率

从腾讯批量行情API获取实时数据，写入stocks表
"""
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
TENCENT_BATCH = "https://qt.gtimg.cn/q="
HEADERS = {"User-Agent": "Mozilla/5.0"}
PROXIES = {"http": None, "https": None}


def _code_to_tencent(code: str) -> str:
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}{code}"


def _parse_quote(line: str) -> dict:
    parts = line.split("~")
    if len(parts) < 50:
        return None
    try:
        return {
            "code": parts[2],
            "name": parts[1],
            "price": float(parts[3]) if parts[3] else 0,
            "volume_ratio": float(parts[49]) if parts[49] else 0,
            "turnover_rate": float(parts[38]) if parts[38] else 0,
        }
    except (ValueError, IndexError):
        return None


def fetch_quotes_batch(codes: list, batch_size: int = 50) -> list:
    results = []
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        tencent_codes = [_code_to_tencent(c) for c in batch]
        try:
            resp = requests.get(
                TENCENT_BATCH + ",".join(tencent_codes),
                headers=HEADERS, timeout=10, proxies=PROXIES,
            )
            for line in resp.text.strip().split(";"):
                line = line.strip()
                if not line or "~" not in line:
                    continue
                q = _parse_quote(line)
                if q and q["code"]:
                    results.append(q)
        except Exception:
            pass
    return results


def save(quotes: list) -> int:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    n = 0
    for q in quotes:
        try:
            conn.execute(
                "UPDATE stocks SET volume_ratio=?, turnover_rate=? WHERE code=?",
                (q["volume_ratio"], q["turnover_rate"], q["code"]),
            )
            if conn.total_changes:
                n += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return n


def run():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    codes = [r[0] for r in conn.execute(
        "SELECT code FROM stocks WHERE price > 0 ORDER BY volume DESC LIMIT 800"
    ).fetchall()]
    conn.close()

    if not codes:
        print("No stocks to update")
        return 0

    quotes = fetch_quotes_batch(codes)
    n = save(quotes)
    print(f"Updated {n}/{len(codes)} stocks with volume_ratio/turnover_rate")
    return n


if __name__ == "__main__":
    run()
