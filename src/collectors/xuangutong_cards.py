#!/usr/bin/env python3
"""选股通 - 概念卡片+资金流表 合并采集"""
import requests, re, sqlite3, json
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
URL = "https://xuangutong.com.cn/zhutiku"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _get_token_cookie():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.utils.cookie_manager import get_cookie_value
    t = get_cookie_value("xuangutong_token")
    return {"token": t.strip()} if t else {}


def fetch_all() -> list:
    cookies = _get_token_cookie()
    r = requests.get(URL, headers=HEADERS, cookies=cookies, timeout=15)
    text = r.text

    result = {}

    # ── 1. 风口板块卡片（3条，含代表股）──
    cards = re.findall(r'<li class="plate_[^"]*">(.*?)</li>', text, re.DOTALL)
    for item in cards:
        name = re.search(r'<span>([^<]{2,30}?)</span>', item)
        if not name:
            continue
        concept = name.group(1).strip()
        pct = re.search(r'([+-]\d+\.\d+)%', item)
        driver = re.search(r'<div class="intro_[^"]*">([^<]+)</div>', item)
        stocks = []
        for s in re.finditer(r'<span class="name_[^"]*">([^<]+)</span>.*?([+-]\d+\.\d+)%', item, re.DOTALL):
            stocks.append({"n": s.group(1).strip(), "c": float(s.group(2))})

        if concept not in result:
            result[concept] = {
                "concept": concept,
                "change_pct": float(pct.group(1)) if pct else 0,
                "driver": driver.group(1).strip() if driver else "",
                "stocks": stocks,
                "fund_flow_today": 0,
                "fund_flow_3d": 0,
            }

    # ── 2. 资金流表（全部概念）──
    rows = re.findall(r'<tr class="x-table-body_row">(.*?)</tr>', text, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 2:
            continue
        # 从链接标签提取概念名（排除驱动文字）
        name_match = re.search(r'platelist-name-link[^>]*>([^<]+)</a>', cells[1])
        name = name_match.group(1).strip() if name_match else ""
        if not name or len(name) > 20:
            continue
        
        # 模糊匹配：表格名可能和卡片名不完全一致（如"钼" vs "有色 · 钼"）
        matched_key = None
        for existing_name in list(result.keys()):
            if name in existing_name or existing_name in name:
                matched_key = existing_name
                break
        
        target_key = matched_key or name
        if target_key not in result:
            result[target_key] = {"concept": target_key, "change_pct": 0, "driver": "", "stocks": [],
                                  "fund_flow_today": 0, "fund_flow_3d": 0,
                                  "up_down": "", "limit_up": 0, "leader": ""}

        # 涨跌幅（从表格取）
        if len(cells) > 2 and not result[target_key]["change_pct"]:
            pct = re.search(r'([+-]\d+\.\d+)%', cells[2])
            if pct: result[target_key]["change_pct"] = float(pct.group(1))

        # 涨跌家数
        if len(cells) > 3:
            ud = re.sub(r'<[^>]+>', '', cells[3]).strip()
            result[target_key]["up_down"] = ud

        # 涨停家数
        if len(cells) > 4:
            lu = re.sub(r'<[^>]+>', '', cells[4]).strip()
            result[target_key]["limit_up"] = int(lu) if lu.isdigit() else 0

        # 领涨股
        if len(cells) > 5:
            leader = re.sub(r'<[^>]+>', '', cells[5]).strip()[:60]
            result[target_key]["leader"] = leader

        # 资金流
        for ci in [6, 7]:  # 6=今日, 7=3日
            if ci < len(cells):
                fm = re.search(r'([+-])(?:<[^>]*>)*\s*(\d+\.\d+)(万|亿)?', cells[ci])
                if fm:
                    val = float(fm.group(2))
                    unit = fm.group(3) or '亿'
                    fv = val if fm.group(1) == '+' else -val
                    if unit == '万':
                        fv = fv / 10000
                    if ci == 6:
                        result[target_key]["fund_flow_today"] = round(fv, 2)
                    else:
                        result[target_key]["fund_flow_3d"] = round(fv, 2)

    return list(result.values())


def save(data: list):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS xuangutong_cards")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xuangutong_cards (
            date TEXT, concept TEXT,
            change_pct REAL, driver TEXT,
            stocks TEXT, fund_flow_today REAL, fund_flow_3d REAL,
            up_down TEXT, limit_up INTEGER, leader TEXT,
            PRIMARY KEY (date, concept)
        )
    """)
    for d in data:
        conn.execute("""
            INSERT OR REPLACE INTO xuangutong_cards
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (today, d["concept"], d["change_pct"], d["driver"],
              json.dumps(d["stocks"], ensure_ascii=False),
              d["fund_flow_today"], d["fund_flow_3d"],
              d.get("up_down",""), d.get("limit_up",0), d.get("leader","")))
    conn.commit()
    conn.close()
    return len(data)


if __name__ == "__main__":
    data = fetch_all()
    n = save(data)
    print(f"选股通数据: {n}条\n")
    for d in sorted(data, key=lambda x: -abs(x.get('fund_flow_today',0)))[:5]:
        stocks = ", ".join([f"{s['n']} {s['c']:+.1f}%" for s in d['stocks'][:2]])
        print(f"  {d['concept']:20s} {d['change_pct']:+.2f}% 资金:{d['fund_flow_today']:+.2f}亿  {stocks}")
