#!/usr/bin/env python3
"""同花顺概念排行采集器（官方API）
返回TOP20概念：涨跌幅、涨停家数、热度标签(连续上榜单天数)、热度值
"""
import requests, json, sqlite3
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate?type=concept"
COOKIE_NAME = "ths_v_cookie"


def _get_cookie() -> dict:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.utils.cookie_manager import get_cookie_value
    v = get_cookie_value(COOKIE_NAME)
    return {"v": v} if v else {}


def fetch_concept_rank() -> list:
    cookies = _get_cookie()
    if not cookies or not cookies.get("v"):
        print("⚠️ 同花顺cookie未配置，请在config.json设置ths_v_cookie")
        return []
    
    r = requests.get(URL, headers={
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://eq.10jqka.com.cn",
        "Referer": "https://eq.10jqka.com.cn/",
    }, cookies=cookies, timeout=10)
    
    plates = r.json().get("data", {}).get("plate_list", [])
    
    result = []
    for p in plates:
        # 解析热度标签中的天数
        hot_tag = p.get("hot_tag", "")
        days_on_list = 0
        if "天" in hot_tag:
            import re
            m = re.search(r'(\d+)天', hot_tag)
            if m:
                days_on_list = int(m.group(1))
            elif "连续" in hot_tag:
                m2 = re.search(r'连续(\d+)天上榜', hot_tag)
                if m2:
                    days_on_list = int(m2.group(1))
        
        result.append({
            "name": p.get("name", ""),
            "code": p.get("code", ""),
            "rise_and_fall": p.get("rise_and_fall", 0),
            "tag": p.get("tag", ""),           # "8家涨停"
            "hot_tag": hot_tag,                  # "5天3次上榜"
            "days_on_list": days_on_list,        # 上榜单天数
            "hot_rank_chg": p.get("hot_rank_chg", 0),
            "rate": float(p.get("rate", 0)),     # 热度值
        })
    
    return result


def save(data: list):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS ths_concept_rank")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ths_concept_rank (
            date TEXT, name TEXT, code TEXT,
            rise_and_fall REAL, tag TEXT, hot_tag TEXT,
            days_on_list INTEGER, hot_rank_chg INTEGER,
            rate REAL,
            PRIMARY KEY (date, name)
        )
    """)
    for d in data:
        conn.execute("""
            INSERT OR REPLACE INTO ths_concept_rank
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (today, d["name"], d["code"], d["rise_and_fall"],
              d["tag"], d["hot_tag"], d["days_on_list"],
              d["hot_rank_chg"], d["rate"]))
    conn.commit()
    conn.close()
    return len(data)


if __name__ == "__main__":
    data = fetch_concept_rank()
    n = save(data)
    print(f"同花顺概念排行: {n}条\n")
    for d in sorted(data, key=lambda x: -abs(x.get('rise_and_fall',0)))[:10]:
        print(f"  {d['name']:15s} {d['rise_and_fall']:+.2f}% {d['tag']:10s} {d['hot_tag']:15s} 热度值{d['rate']:.0f}")
