"""
数据新鲜度检查
每次采集完成后检查各表的最新日期是否在阈值内
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"

FRESHNESS_RULES = {
    'ths_concept_rank': 60,       # 60分钟没更新算过期
    'ths_hot_stocks': 60,
    'xuangutong_cards': 120,
    'news_cache': 120,
    'limit_up_cache': 300,
    'stockstar_concept_ranks': 120,
    'concept_hot': 120,
}

def check_all_tables() -> list[dict]:
    """
    遍历FRESHNESS_RULES，检查每张表最新日期
    返回所有表的状态列表
    """
    results = []
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now()
    
    for table, max_age_min in FRESHNESS_RULES.items():
        try:
            row = conn.execute(f"SELECT MAX(date) FROM {table}").fetchone()
            if row and row[0]:
                last_date = row[0]
                # 计算距今多少分钟
                try:
                    last_dt = datetime.strptime(last_date, "%Y-%m-%d %H:%M")
                except:
                    try:
                        last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                    except:
                        last_dt = now
                age_min = (now - last_dt).total_seconds() / 60
                status = "ok" if age_min <= max_age_min else "stale"
            else:
                last_date = None
                age_min = None
                status = "missing"
        except Exception as e:
            last_date = None
            age_min = None
            status = f"error: {e}"
        
        results.append({
            "table": table,
            "last_date": last_date,
            "age_minutes": round(age_min, 1) if age_min else None,
            "threshold_minutes": max_age_min,
            "status": status
        })
    
    conn.close()
    return results

def get_stale_tables() -> list[dict]:
    """只返回过期的表"""
    return [t for t in check_all_tables() if t["status"] != "ok"]

if __name__ == "__main__":
    print("=== 数据新鲜度检查 ===\n")
    for t in check_all_tables():
        icon = {"ok": "✅", "stale": "⚠️", "missing": "❌"}.get(t["status"], "❓")
        age = f"{t['age_minutes']}分钟" if t['age_minutes'] else "无数据"
        print(f"  {icon} {t['table']:25s} {t['last_date'] or '--':18s} 距今{age:>10s} 阈值{t['threshold_minutes']}分钟")