#!/usr/bin/env python3
"""证券之星概念板块排行采集器

每天获取每个概念的：总股票数、上涨家数、平盘、下跌家数
用于计算概念强度（上涨比率越高=概念越强）
"""
import requests, re, sqlite3
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
URL = "https://quote.stockstar.com/stock/blockrank_5_1_1_1.html"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_concept_ranks() -> list:
    """获取概念板块涨跌排行

    返回: [{
        "concept": "芯片概念",
        "total": 856,
        "up": 342,
        "flat": 5,
        "down": 509,
        "up_ratio": 0.40,
        "up_down_ratio": 0.67
    }]
    """
    r = requests.get(URL, headers=HEADERS, timeout=30)
    text = r.content.decode("gbk", errors="replace")
    
    # 提取表格行
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.DOTALL)
    
    results = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 6:
            continue
        
        # 提取纯文本
        texts = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        
        name = texts[0] if len(texts) > 0 else ""
        total = texts[1] if len(texts) > 1 else "0"
        up = texts[2] if len(texts) > 2 else "0"
        flat = texts[3] if len(texts) > 3 else "0"
        down = texts[4] if len(texts) > 4 else "0"
        
        # 过滤表头和市值数据
        if name in ("行业名称", "融资融券", "小盘", "中盘", "大盘", "低价"):
            continue
        if not total.isdigit() or not up.isdigit():
            continue
        
        total_n = int(total)
        up_n = int(up)
        down_n = int(down)
        flat_n = int(flat)
        
        if total_n == 0:
            continue
        
        up_ratio = round(up_n / total_n, 3)
        up_down_ratio = round(up_n / down_n, 2) if down_n > 0 else up_n
        
        results.append({
            "concept": name,
            "total": total_n,
            "up": up_n,
            "flat": flat_n,
            "down": down_n,
            "up_ratio": up_ratio,
            "up_down_ratio": up_down_ratio,
        })
    
    return results


def fetch_industry_ranks() -> list:
    """获取行业板块涨跌排行"""
    url_industry = "https://quote.stockstar.com/stock/industry.shtml"
    r = requests.get(url_industry, headers=HEADERS, timeout=30)
    text = r.content.decode("gbk", errors="replace")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.DOTALL)
    
    results = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 6:
            continue
        texts = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        name = texts[0] if len(texts) > 0 else ""
        total = texts[1] if len(texts) > 1 else "0"
        up = texts[2] if len(texts) > 2 else "0"
        flat = texts[3] if len(texts) > 3 else "0"
        down = texts[4] if len(texts) > 4 else "0"
        
        if name in ("行业名称",) or not total.isdigit():
            continue
        
        total_n, up_n, down_n = int(total), int(up), int(down)
        if total_n == 0:
            continue
        
        results.append({
            "concept": name, "total": total_n,
            "up": up_n, "flat": int(flat), "down": down_n,
            "up_ratio": round(up_n / total_n, 3),
            "up_down_ratio": round(up_n / down_n, 2) if down_n > 0 else up_n,
        })
    return results


def save_concept_ranks(concepts: list):
    """保存到数据库"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stockstar_concept_ranks (
            date TEXT, concept TEXT,
            total INTEGER, up INTEGER, flat INTEGER, down INTEGER,
            up_ratio REAL, up_down_ratio REAL,
            PRIMARY KEY (date, concept)
        )
    """)
    
    for c in concepts:
        conn.execute("""
            INSERT OR REPLACE INTO stockstar_concept_ranks
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (today, c["concept"], c["total"], c["up"], c["flat"],
              c["down"], c["up_ratio"], c["up_down_ratio"]))
    
    conn.commit()
    conn.close()
    return len(concepts)


if __name__ == "__main__":
    concepts = fetch_concept_ranks()
    n = save_concept_ranks(concepts)
    
    # 输出TOP15
    print(f"证券之星概念排行 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"共{n}个概念\n")
    
    # 按上涨比率排序
    sorted_by_ratio = sorted(concepts, key=lambda x: -x["up_ratio"])
    print("🟢 上涨比率最高TOP10（概念强度最强）:")
    print(f"  {'概念':12s} {'总':>5s} {'涨':>4s} {'跌':>4s} {'上涨比率':>8s}")
    for c in sorted_by_ratio[:10]:
        print(f"  {c['concept']:12s} {c['total']:5d} {c['up']:4d} {c['down']:4d} {c['up_ratio']:>7.1%}")
    
    # 按上涨家数排序
    print("\n🟠 上涨家数最多TOP10:")
    sorted_by_up = sorted(concepts, key=lambda x: -x["up"])
    for c in sorted_by_up[:10]:
        print(f"  {c['concept']:12s} {c['up']:3d}涨/{c['total']}只 {c['up_ratio']:.1%}")
