"""
外部数据源采集器（ForgeRSS + QuantMind）
- 巨潮资讯网公告 (cninfo)
- 雪球讨论 (xueqiu)
"""
import sys, os, json, sqlite3
from datetime import datetime

BASE = "E:/AI/gp1"
FORGE_PATH = "E:/AI/ForgeRSS"
QUANT_PATH = "E:/AI/quant-mind"
DB_PATH = f"{BASE}/a13/hot_rank.db"

KNOWN_CONCEPTS = [
    "算力租赁","人工智能","芯片","半导体","新能源汽车","光伏","储能",
    "机器人","低空经济","军工","航天","信创","数据要素","AI应用",
    "大模型","CPO","光模块","液冷","HBM","先进封装","存储芯片",
    "消费电子","智能驾驶","华为","苹果","小米","特斯拉",
    "国企改革","中特估","一带一路","跨境支付","数字货币",
    "创新药","医疗器械","中药","减肥药","流感",
    "房地产","基建","建材","家居","家电","白酒","食品饮料",
    "煤炭","石油","天然气","有色金属","稀土","钢铁",
    "券商","银行","保险","多元金融",
    "教育","传媒","游戏","影视","旅游","酒店","航空"
]

def extract_concepts(text):
    return [c for c in KNOWN_CONCEPTS if c in text]

def _ensure_db_columns(conn):
    existing = {r[1] for r in conn.execute("PRAGMA table_info(news_cache)").fetchall()}
    for col, typ, default in [
        ("url", "TEXT", "''"),
        ("summary", "TEXT", "''"),
        ("source", "TEXT", "''"),
        ("related_concepts", "TEXT", "''"),
    ]:
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE news_cache ADD COLUMN {col} {typ} DEFAULT {default}")
            except Exception:
                pass
    conn.commit()

def collect_cninfo(keywords="", days=3, max_items=30):
    sys.path.insert(0, FORGE_PATH)
    os.environ['CNINFO_KEYWORDS'] = keywords or "业绩预增,重大合同,项目中标,算力,人工智能,芯片,新能源,机器人"
    os.environ['CNINFO_DAYS'] = str(days)
    os.environ['CNINFO_MAX_ITEMS'] = str(max_items)
    os.environ['CNINFO_DOWNLOAD_PDF'] = 'false'

    from generators.finance.cninfo_announcements import CninfoAnnouncementsGenerator
    gen = CninfoAnnouncementsGenerator()
    articles = gen.fetch_articles()

    results = []
    for a in articles:
        results.append({
            "title": a.title or '',
            "url": a.url or '',
            "published": str(a.published_at)[:19] if a.published_at else '',
            "summary": (a.summary or a.content or '')[:500],
            "source": "cninfo"
        })
    return results

def collect_xueqiu(max_items=20):
    sys.path.insert(0, FORGE_PATH)
    os.environ['XUEQIU_USER_ID'] = "8353550788"
    os.environ['XUEQIU_MAX_POSTS'] = str(max_items)

    from generators.finance.xueqiu.generator import XueqiuUserGenerator
    gen = XueqiuUserGenerator()
    articles = gen.fetch_articles()

    results = []
    for a in articles:
        results.append({
            "title": a.title or '',
            "url": a.url or '',
            "published": str(a.published_at)[:19] if a.published_at else '',
            "summary": (a.summary or a.content or '')[:500],
            "source": "xueqiu"
        })
    return results

def save_to_db(articles, source_name):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_PATH)
    _ensure_db_columns(conn)

    saved = 0
    for a in articles:
        try:
            concepts = extract_concepts(a['title'] + ' ' + a['summary'])
            conn.execute(
                """INSERT OR IGNORE INTO news_cache
                   (date, title, url, summary, source, related_concepts, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (today, a['title'], a['url'], a['summary'],
                 a.get('source', source_name),
                 ','.join(concepts[:5]))
            )
            saved += 1
        except Exception as e:
            print(f"  保存失败: {e}")

    conn.commit()
    conn.close()
    return saved

def run_all():
    print("=" * 60)
    print(f"  外部数据源采集  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    total = 0

    print("\n[1] 巨潮资讯网公告...")
    try:
        articles = collect_cninfo()
        n = save_to_db(articles, "cninfo")
        total += n
        print(f"  OK 保存 {n} 条")
        for a in articles[:3]:
            concepts = extract_concepts(a['title'])
            print(f"  · {a['title'][:50]}  -> {'/'.join(concepts) if concepts else '未匹配'}")
    except Exception as e:
        print(f"  FAIL {e}")

    print("\n[2] 雪球讨论...")
    try:
        articles = collect_xueqiu()
        n = save_to_db(articles, "xueqiu")
        total += n
        print(f"  OK 保存 {n} 条")
        for a in articles[:3]:
            concepts = extract_concepts(a['title'])
            print(f"  · {a['title'][:50]}  -> {'/'.join(concepts) if concepts else '未匹配'}")
    except Exception as e:
        print(f"  FAIL {e}")

    print(f"\n{'=' * 60}")
    print(f"  总计保存: {total} 条")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    run_all()
