#!/usr/bin/env python3
"""同花顺热门股票榜单采集器

每日存储热门股票的概念标签和连板数据，用于分析板块轮动。
"""
import requests, json, sqlite3, time
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
URL = "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_hot_stocks() -> list:
    """获取同花顺热门股票榜单
    
    返回: [{
        "code": "002354", "name": "天娱数科",
        "order": 1, "hot_rank_chg": 0,
        "concepts": ["AI视频", "小红书概念"],
        "board_count": 4,  // 连板天数
        "board_label": "4天4板"
    }]
    """
    r = requests.get(URL, headers=HEADERS, timeout=10)
    data = r.json()
    
    if data.get("status_code") != 0:
        return []
    
    stocks = data.get("data", {}).get("stock_list", [])
    results = []
    
    for s in stocks:
        tag = s.get("tag", {}) or {}
        pop_tag = tag.get("popularity_tag", "")
        
        # 解析连板天数
        board_count = 0
        if "板" in pop_tag:
            import re
            m = re.search(r'(\d+)天(\d+)板', pop_tag)
            if m:
                board_count = int(m.group(2))
            elif "首板" in pop_tag:
                board_count = 1
        
        results.append({
            "code": s.get("code", ""),
            "name": s.get("name", ""),
            "order": s.get("order", 0),
            "hot_rank_chg": s.get("hot_rank_chg", 0),
            "concepts": tag.get("concept_tag", []),
            "board_count": board_count,
            "board_label": pop_tag,
        })
    
    return results


def save_hot_stocks(stocks: list):
    """保存到数据库，追加模式"""
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_PATH)
    
    # 建表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ths_hot_stocks (
            date TEXT, time TEXT, code TEXT, name TEXT,
            stock_order INTEGER, hot_rank_chg INTEGER,
            concepts TEXT, board_count INTEGER, board_label TEXT,
            PRIMARY KEY (date, code, time)
        )
    """)
    
    for s in stocks:
        concepts_str = ",".join(s["concepts"])
        conn.execute(
            "INSERT OR REPLACE INTO ths_hot_stocks VALUES (?,?,?,?,?,?,?,?,?)",
            (today, now, s["code"], s["name"], s["order"],
             s["hot_rank_chg"], concepts_str, s["board_count"], s["board_label"])
        )
    
    conn.commit()
    conn.close()
    return len(stocks)


def get_hot_concepts(stocks: list) -> dict:
    """统计今日热门概念
    
    返回: {"AI视频": 1, "小红书概念": 1, "氟化工概念": 2, ...}
    """
    concepts = {}
    for s in stocks:
        for c in s["concepts"]:
            concepts[c] = concepts.get(c, 0) + 1
    return dict(sorted(concepts.items(), key=lambda x: -x[1]))


def get_board_leaders(stocks: list, min_boards: int = 3) -> list:
    """获取连板≥N天的龙头股"""
    return [s for s in stocks if s["board_count"] >= min_boards]


def sync_concepts_to_stock_concepts():
    """将ths_hot_stocks的概念标签同步到stock_concepts表

    目的：让所有热门股都有概念标签，不再依赖P2增量采集
    """
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH, timeout=5)

    # 确保stock_concepts表存在
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_concepts (
            code TEXT, concept TEXT,
            PRIMARY KEY (code, concept)
        )
    """)

    # 读取今日ths_hot_stocks
    rows = conn.execute(
        'SELECT code, concepts FROM ths_hot_stocks WHERE date=?',
        (today,)
    ).fetchall()

    synced = 0
    for code, concepts_str in rows:
        if not concepts_str:
            continue
        concepts = [c.strip() for c in concepts_str.split(",") if c.strip()]
        for c in concepts:
            conn.execute(
                'INSERT OR IGNORE INTO stock_concepts (code, concept) VALUES (?, ?)',
                (code, c)
            )
            synced += 1

    conn.commit()
    conn.close()
    return synced


if __name__ == "__main__":
    stocks = fetch_hot_stocks()
    n = save_hot_stocks(stocks)
    
    print(f"同花顺热门股票榜单 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"共 {n} 只\n")
    
    print("📊 热门概念TOP:")
    for concept, cnt in list(get_hot_concepts(stocks).items())[:10]:
        print(f"  {concept}: {cnt}次")
    
    print(f"\n🔥 连板龙头:")
    for s in get_board_leaders(stocks, 2):
        print(f"  {s['name']} ({s['code']}) {s['board_label']} "
              f"概念:{','.join(s['concepts'][:3])}")
