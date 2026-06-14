# -*- coding: utf-8 -*-
"""
快速采集器 — 多线程并发版
优化观点情绪 + 异动解析（原版逐个采集太慢）

用法:
  from src.utils.fast_collectors import fast_collect_all
  result = fast_collect_all(max_stocks=100)
"""
import os, json, time, sqlite3
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "a13", "hot_rank.db")
NEWS_DIR = os.path.join(BASE_DIR, "a13", "docs", "data", "news")
CONFIG_PATH = os.path.join(BASE_DIR, "gp_project", "config.json")
os.makedirs(NEWS_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36'}


def _get_cookie(key="ths_cookie"):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            ck = json.load(f).get(key, '')
        cookies = {}
        for item in ck.split(';'):
            item = item.strip().strip("'")
            if '=' in item:
                k, v = item.split('=', 1)
                cookies[k.strip()] = v.strip()
        return cookies
    except:
        return {}


def _get_pool(limit=100):
    """获取待采集股票池"""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    today = conn.execute('SELECT MAX(date) FROM hot_rank_history').fetchone()[0]
    rows = conn.execute('''
        SELECT DISTINCT h.code, COALESCE(s.name,"") as name
        FROM hot_rank_history h LEFT JOIN stocks s ON h.code=s.code
        WHERE h.date=? AND h.rank IS NOT NULL ORDER BY h.rank LIMIT ?
    ''', (today, limit)).fetchall()
    conn.close()
    pool = []
    for code, name in rows:
        c = str(code).zfill(6)
        if 'ST' in str(name).upper(): continue
        if c.startswith(('8', '4', '920')): continue
        pool.append((c, name or c))
    return pool


def _fetch_viewpoint(code, name):
    """单只股票观点情绪"""
    cookies = _get_cookie("ths_cookie")
    if not cookies:
        return None
    market = '17' if code.startswith('6') else '33'
    now = datetime.now()
    start_ts = int((now - timedelta(days=7)).timestamp() * 1000)
    end_ts = int(now.timestamp() * 1000)
    
    try:
        r = requests.get(
            'https://chat.touzime.net/open-api/chat/sidebar/hotspot/v1/viewpoint_count',
            params={'start_time': str(start_ts), 'end_time': str(end_ts),
                    'stock_code': code, 'stock_market': market},
            headers={**HEADERS, 'Cookie': '; '.join(f'{k}={v}' for k,v in cookies.items())},
            timeout=10
        )
        d = r.json()
        if d.get('status_code') != 0:
            return None
        vp_list = d.get('data', {}).get('list', [])
        if not vp_list:
            return None
        total = sum(v['count'] for v in vp_list)
        up = sum(v['up_count'] for v in vp_list)
        down = sum(v['down_count'] for v in vp_list)
        return {
            'code': code, 'name': name,
            'viewpoint': {
                'total': total, 'up': up, 'down': down,
                'ratio': round(up/max(up+down,1)*100, 1) if up+down>0 else 50,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }
        }
    except:
        return None


def _fetch_anomaly(code, name):
    """单只股票异动解析"""
    cookies = _get_cookie("ths_cookie")
    if not cookies:
        return None
    market = '1' if code.startswith('6') else '0'
    
    try:
        url = f'https://dq.10jqka.com.cn/fuyao/transaction_history/service/v1/get/{market}_{code}.txt'
        r = requests.get(url, headers={**HEADERS, 'Cookie': '; '.join(f'{k}={v}' for k,v in cookies.items()),
                         'Referer': 'https://dq.10jqka.com.cn/'}, timeout=10)
        d = r.json()
        if not d.get('data'):
            return None
        items = d['data'].get('list', [])
        if not items:
            return None
        
        reasons = []
        keywords = set()
        tags = set()
        for item in items:
            kw = item.get('keywordList', [])
            for k in kw:
                if k.get('name'):
                    keywords.add(k['name'])
            reasons.append(item.get('reason', ''))
            tag = item.get('tagName', '')
            if tag:
                tags.add(tag)
        
        return {
            'code': code, 'name': name,
            'anomaly': {
                'keyword': '; '.join(list(keywords)[:5]),
                'keyword_list': list(keywords)[:10],
                'concept_tags': list(tags),
                'reasons': reasons[:3],
                'count': len(items),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }
        }
    except:
        return None


def _save_result(data: dict, data_type: str):
    """保存采集结果到JSON文件"""
    if not data or not data.get('code'):
        return
    code = data['code']
    fp = os.path.join(NEWS_DIR, f'{code}.json')
    cached = {}
    if os.path.exists(fp):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                cached = json.load(f)
        except:
            pass
    
    if data_type == 'viewpoint' and 'viewpoint' in data:
        cached['viewpoint'] = data['viewpoint']
    elif data_type == 'anomaly' and 'anomaly' in data:
        cached.update(data['anomaly'])
    
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(cached, f, ensure_ascii=False, indent=2)


def fast_collect_viewpoint(pool, max_workers=10):
    """多线程采集观点情绪"""
    results = {'success': 0, 'fail': 0, 'items': []}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_viewpoint, code, name): (code, name) for code, name in pool}
        for f in as_completed(futures):
            data = f.result()
            if data:
                _save_result(data, 'viewpoint')
                results['success'] += 1
                results['items'].append(data['code'])
            else:
                results['fail'] += 1
    return results


def fast_collect_anomaly(pool, max_workers=10):
    """多线程采集异动解析"""
    results = {'success': 0, 'fail': 0, 'items': []}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_anomaly, code, name): (code, name) for code, name in pool}
        for f in as_completed(futures):
            data = f.result()
            if data:
                _save_result(data, 'anomaly')
                results['success'] += 1
                results['items'].append(data['code'])
            else:
                results['fail'] += 1
    return results


def fast_collect_all(max_stocks=100):
    """一键采集：观点+异动，多线程并发"""
    print(f"\n{'='*50}")
    print(f"  快速采集器 — 多线程并发")
    print(f"{'='*50}")
    
    pool = _get_pool(limit=max_stocks)
    print(f"股票池: {len(pool)}只")
    
    t0 = time.time()
    
    # 观点情绪（10线程）
    print(f"\n--- 观点情绪 ({len(pool)}只, 10线程) ---")
    vp = fast_collect_viewpoint(pool)
    print(f"  ✅ {vp['success']} / ❌ {vp['fail']}")
    
    # 异动解析（10线程）
    print(f"\n--- 异动解析 ({len(pool)}只, 10线程) ---")
    an = fast_collect_anomaly(pool)
    print(f"  ✅ {an['success']} / ❌ {an['fail']}")
    
    elapsed = round(time.time() - t0, 1)
    print(f"\n{'='*50}")
    print(f"  完成! 观点:{vp['success']} 异动:{an['success']} 耗时:{elapsed}s")
    print(f"{'='*50}")
    
    return {'viewpoint': vp, 'anomaly': an, 'elapsed': elapsed}


if __name__ == '__main__':
    fast_collect_all(max_stocks=100)
