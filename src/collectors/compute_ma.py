# -*- coding: utf-8 -*-
"""均线计算 — 从price_5d计算MA5/MA10/MA20并写入stocks表"""
import sqlite3

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


def compute_ma():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    codes = [r[0] for r in conn.execute(
        "SELECT DISTINCT code FROM price_5d"
    ).fetchall()]

    n = 0
    for code in codes:
        rows = conn.execute(
            "SELECT price FROM price_5d WHERE code=? ORDER BY date DESC LIMIT 20",
            (code,),
        ).fetchall()
        prices = [float(r[0]) for r in rows if r[0]]
        if len(prices) < 5:
            continue

        ma5 = sum(prices[:5]) / 5
        ma10 = sum(prices[:10]) / min(len(prices), 10) if len(prices) >= 10 else ma5
        ma20 = sum(prices) / len(prices) if len(prices) >= 20 else ma10
        ma_bull = 1 if (ma5 > ma10 > ma20 and len(prices) >= 20) else 0

        conn.execute(
            "UPDATE stocks SET ma5=?, ma10=?, ma20=?, ma_bull=? WHERE code=?",
            (round(ma5, 3), round(ma10, 3), round(ma20, 3), ma_bull, code),
        )
        n += 1

    conn.commit()
    conn.close()
    return n


if __name__ == "__main__":
    n = compute_ma()
    print(f"Updated MA for {n} stocks")
