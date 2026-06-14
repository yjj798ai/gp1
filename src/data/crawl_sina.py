# -*- coding: utf-8 -*-
"""新浪财经采集 — 每日涨跌幅排名

说明:
- 采集A股全市场，排除ST/科创板(688)/北交所(8/4/920)
- 价格>0，最终按涨跌幅排名存入hot_rank_history
- 默认采10页(约1000只)，主接口失败时降级到按code排序接口
"""
import urllib.request, json, ssl, time, sqlite3

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
DB_PATH = "E:/AI/gp1/a13/hot_rank.db"

_HEADERS = {'User-Agent': 'Mozilla/5.0'}


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers=_HEADERS)
    r = urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)
    return json.loads(r.read())


def fetch_sina_stocks(pages: int = 10):
    """采集新浪财经股票数据，排除ST/科创板/北交所

    Args:
        pages: 采集页数，每页100只，默认10页

    Returns:
        int: 入库的股票数量
    """
    all_data = []

    # 主接口: 按涨跌幅排序
    for page in range(1, pages + 1):
        url = ("https://vip.stock.finance.sina.com.cn/quotes_service/"
               f"api/json_v2.php/Market_Center.getHQNodeData?"
               f"page={page}&num=100&sort=changepercent&asc=0&node=hs_a")
        try:
            data = fetch_json(url)
            if data and isinstance(data, list):
                all_data.extend(data)
            time.sleep(0.2)
        except Exception:
            break

    # 备用接口: 按code排序（主接口被封时降级）
    if not all_data:
        for page in range(1, pages + 1):
            url = ("https://vip.stock.finance.sina.com.cn/quotes_service/"
                   f"api/json_v2.php/Market_Center.getHQNodeData?"
                   f"page={page}&num=100&sort=code&asc=1&node=hs_a&_s_r_a=init")
            try:
                data = fetch_json(url, timeout=8)
                if data and isinstance(data, list):
                    all_data.extend(data)
                time.sleep(0.2)
            except Exception:
                break

    if not all_data:
        return 0

    # 过滤: 排除ST / 科创板688 / 北交所8/4/920
    filtered = []
    seen = set()
    for s in all_data:
        code = s.get('code', '')
        name = s.get('name', '')
        if not code or code in seen:
            continue
        if 'ST' in (name or '').upper():
            continue
        if code.startswith(('688', '8', '4', '920')):
            continue
        try:
            price = float(s.get('trade', s.get('price', 0) or 0))
            if price <= 0:
                continue
        except:
            continue
        seen.add(code)
        filtered.append(s)

    today = time.strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH, timeout=10)

    n_stocks = 0
    for s in filtered:
        code = s.get('code', '')
        name = s.get('name', '')
        try:
            price = float(s.get('trade', s.get('price', 0) or 0))
            change = float(s.get('changepercent', 0) or 0)
            mcap = float(s.get('mktcap', 0) or 0) / 1e8
            volume = float(s.get('volume', 0) or 0)
            conn.execute(
                "INSERT OR REPLACE INTO stocks(code,name,price,change_pct,market_cap,volume) VALUES(?,?,?,?,?,?)",
                (code, name, price, change, mcap, volume))
            n_stocks += 1
        except Exception:
            pass

    # 按涨跌幅绝对值排序 → 写入hot_rank_history
    sorted_s = sorted(filtered,
                      key=lambda s: abs(float(s.get('changepercent', 0) or 0)),
                      reverse=True)
    for i, s in enumerate(sorted_s):
        code = s.get('code', '')
        try:
            change = float(s.get('changepercent', 0) or 0)
            price = float(s.get('trade', s.get('price', 0) or 0))
            conn.execute(
                "INSERT OR IGNORE INTO hot_rank_history(code,date,rank,price,change_pct) VALUES(?,?,?,?,?)",
                (code, today, i + 1, price, change))
        except Exception:
            pass

    conn.commit()
    conn.close()
    return len(filtered)
