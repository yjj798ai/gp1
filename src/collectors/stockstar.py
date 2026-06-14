# -*- coding: utf-8 -*-
"""
证券之星行业/概念分类采集器 v2

数据源:
  行业列表: https://quote.stockstar.com/stock/industry.shtml
  行业详情: https://quote.stockstar.com/stock/industry_{letter}.shtml
  概念列表: https://quote.stockstar.com/stock/blockrank_5_1_1_{page}.html (23页)
  概念详情: https://quote.stockstar.com/stock/blockperformance_5_{code}_2_1_{page}.html

功能:
  fetch_industry_list()        → 行业列表（名称+股票数+涨跌家数）
  fetch_industry_stocks(letter) → 某行业成分股代码列表
  fetch_concept_list()         → 概念列表（遍历全部分页，约700个概念）
  fetch_concept_stocks(code)    → 某概念成分股代码列表（翻页获取全部）
  update_all()                 → 全量更新 stocks.sector + stock_concepts
"""

import re
import time
import sqlite3
import logging
from datetime import datetime

import requests

log = logging.getLogger('stockstar')

# ── 数据库路径 ──
_HOT_RANK_DB = "E:/AI/gp1/a13/hot_rank.db"
_HOLY_GRAIL_DB = "E:/AI/gp1/data/holy_grail.db"

# ── 请求头 ──
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)

# ── 行业代码映射（证监会行业分类字母代码）──
_INDUSTRY_LETTERS = {
    '信息传输、软件和信息技术服务业': 'I',
    '金融业': 'J',
    '批发和零售业': 'F',
    '交通运输、仓储和邮政业': 'G',
    '房地产业': 'K',
    '水利、环境和公共设施管理业': 'N',
    '建筑业': 'E',
    '科学研究和技术服务业': 'M',
    '文化、体育和娱乐业': 'R',
    '电力、热力、燃气及水生产和供应业': 'D',
    '租赁和商务服务业': 'L',
    '农、林、牧、渔业': 'A',
    '采矿业': 'B',
    '住宿和餐饮业': 'H',
    '制造业': 'C',
    '综合': 'S',
    '教育': 'P',
    '卫生和社会工作': 'Q',
    '公共管理、社会保障和社会组织': 'T',
}


def _extract_stock_codes(html: str) -> set:
    """从HTML中提取A股股票代码（排除北交所）"""
    codes = re.findall(r'\b(\d{6})\b', html)
    return set(c for c in codes if c.startswith(('0', '3', '6')))


def fetch_industry_list():
    """从证券之星获取行业列表

    返回: [{'name': str, 'stock_count': int, 'up': int, 'flat': int, 'down': int, 'market_cap': float}, ...]
    """
    try:
        url = 'https://quote.stockstar.com/stock/industry.shtml'
        r = _SESSION.get(url, timeout=10)
        r.encoding = 'gbk'

        trs = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)
        industries = []

        for tr in trs:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
            clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]

            if not clean or clean[0] == '行业名称' or len(clean) < 5:
                continue

            try:
                industries.append({
                    'name': clean[0],
                    'stock_count': int(clean[1]),
                    'up': int(clean[2]),
                    'flat': int(clean[3]),
                    'down': int(clean[4]),
                    'market_cap': float(clean[5]) if len(clean) > 5 else 0,
                })
            except (ValueError, IndexError):
                continue

        return industries

    except Exception as e:
        log.error(f'fetch_industry_list failed: {e}')
        return []


def fetch_industry_stocks(industry_name: str, max_pages: int = 10) -> list:
    """获取某个行业的成分股代码列表（支持翻页）"""
    letter = _INDUSTRY_LETTERS.get(industry_name)
    if not letter:
        return []

    all_codes = set()

    for page in range(max_pages):
        try:
            if page == 0:
                url = f'https://quote.stockstar.com/stock/industry_{letter}.shtml'
            else:
                url = f'https://quote.stockstar.com/stock/industry_{letter}_{page+1}.shtml'

            r = _SESSION.get(url, timeout=10)
            r.encoding = 'gbk'

            new_codes = _extract_stock_codes(r.text)

            if not new_codes:
                break

            before = len(all_codes)
            all_codes.update(new_codes)

            if len(all_codes) == before:
                break

        except Exception as e:
            log.debug(f'fetch_industry_stocks page {page+1} failed: {e}')
            break

        time.sleep(0.2)

    return sorted(all_codes)


def fetch_concept_list() -> list:
    """从证券之星获取全部概念板块列表（遍历所有分页）

    URL格式: blockrank_5_1_1_{page}.html
    共约23页，每页31个概念，总计约700个

    返回: [{'name': str, 'url_code': str, 'stock_count': int, 'up': int, 'down': int}, ...]
    """
    all_concepts = []
    seen_names = set()

    for page in range(1, 30):
        try:
            url = f'https://quote.stockstar.com/stock/blockrank_5_1_1_{page}.html'
            r = _SESSION.get(url, timeout=10)
            r.encoding = 'gbk'

            if r.status_code != 200 or len(r.text) < 10000:
                break

            # 解析表格行
            trs = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)

            page_count = 0
            for tr in trs:
                tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
                clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]

                if not clean or len(clean) < 5 or clean[0] in ('', '行业名称', '板块名称'):
                    continue

                # 提取概念名称和详情链接
                links = re.findall(r'href="(/stock/blockperformance_5_([^"]+))"', tr)
                # url_code 格式: chgn700095_2_1_1.html → 取第一段作为概念代码
                raw_code = links[0][1].split('_')[0] if links else ''
                url_code = raw_code.replace('.html', '')

                name = clean[0]
                if name and name not in seen_names:
                    seen_names.add(name)
                    try:
                        all_concepts.append({
                            'name': name,
                            'url_code': url_code,
                            'stock_count': int(clean[1]) if clean[1].isdigit() else 0,
                            'up': int(clean[2]) if clean[2].isdigit() else 0,
                            'down': int(clean[4]) if len(clean) > 4 and clean[4].isdigit() else 0,
                        })
                        page_count += 1
                    except (ValueError, IndexError):
                        continue

            if page_count == 0:
                break

            if page <= 2 or page % 10 == 0:
                log.info(f'概念列表 page={page}: {page_count}个  累计{len(all_concepts)}个')

        except Exception as e:
            log.error(f'fetch_concept_list page {page} failed: {e}')
            break

        time.sleep(0.3)

    return all_concepts


def fetch_concept_stocks(url_code: str, max_pages: int = 50) -> list:
    """获取某个概念的成分股代码列表（翻页获取全部）

    URL格式: blockperformance_5_{code}_2_1_{page}.html
    页码在最后一段

    返回: ['000001', '600519', ...]
    """
    if not url_code:
        return []

    all_codes = set()

    for page in range(1, max_pages + 1):
        try:
            url = f'https://quote.stockstar.com/stock/blockperformance_5_{url_code}_2_1_{page}.html'
            r = _SESSION.get(url, timeout=10)
            r.encoding = 'gbk'

            new_codes = _extract_stock_codes(r.text)

            if not new_codes:
                break

            before = len(all_codes)
            all_codes.update(new_codes)

            if len(all_codes) == before:
                break

        except Exception as e:
            log.debug(f'fetch_concept_stocks page {page} failed: {e}')
            break

        time.sleep(0.15)

    return sorted(all_codes)


# ═══════════════════════════════════════════════════════════
# 数据库更新
# ═══════════════════════════════════════════════════════════

def update_all(max_industries: int = 0, max_concepts: int = 0) -> dict:
    """全量更新行业和概念数据"""
    stats = {
        'industries': 0,
        'industry_stocks': 0,
        'concepts': 0,
        'concept_stocks': 0,
    }

    conn_hr = sqlite3.connect(_HOT_RANK_DB, timeout=5)
    conn_hg = sqlite3.connect(_HOLY_GRAIL_DB, timeout=5)

    # ── 1. 行业分类 ──
    print('\n[1/2] 行业分类采集...')
    industries = fetch_industry_list()
    if max_industries > 0:
        industries = industries[:max_industries]

    print(f'  行业数: {len(industries)}')
    stats['industries'] = len(industries)

    for i, ind in enumerate(industries):
        name = ind['name']
        stocks = fetch_industry_stocks(name)
        stats['industry_stocks'] += len(stocks)

        for code in stocks:
            try:
                conn_hr.execute('UPDATE stocks SET sector = ? WHERE code = ?', (name, code))
            except Exception:
                pass
            try:
                conn_hg.execute('UPDATE stocks SET sector = ? WHERE code = ?', (name, code))
            except Exception:
                pass

        if (i + 1) % 5 == 0 or i == len(industries) - 1:
            print(f'  进度: {i+1}/{len(industries)}  累计股票: {stats["industry_stocks"]}')
            conn_hr.commit()
            conn_hg.commit()

        time.sleep(0.3)

    conn_hr.commit()
    conn_hg.commit()

    # ── 2. 概念分类 ──
    print('\n[2/2] 概念分类采集...')
    concepts = fetch_concept_list()
    if max_concepts > 0:
        concepts = concepts[:max_concepts]

    print(f'  概念数: {len(concepts)}')
    stats['concepts'] = len(concepts)

    for i, con in enumerate(concepts):
        name = con['name']
        url_code = con['url_code']
        stock_count = con.get('stock_count', 0)

        # 跳过股票数太多的概念（如融资融券3472只，翻页太多）
        # 限制每个概念最多翻50页（约1500只）
        stocks = fetch_concept_stocks(url_code, max_pages=50)
        stats['concept_stocks'] += len(stocks)

        for code in stocks:
            try:
                conn_hg.execute(
                    'INSERT OR IGNORE INTO stock_concepts (code, concept) VALUES (?, ?)',
                    (code, name)
                )
            except Exception:
                pass
            try:
                conn_hr.execute(
                    'INSERT OR IGNORE INTO stock_concepts (code, concept) VALUES (?, ?)',
                    (code, name)
                )
            except Exception:
                pass

        if (i + 1) % 10 == 0 or i == len(concepts) - 1:
            print(f'  进度: {i+1}/{len(concepts)}  累计记录: {stats["concept_stocks"]}')
            conn_hr.commit()
            conn_hg.commit()

        time.sleep(0.3)

    conn_hr.commit()
    conn_hg.commit()
    conn_hr.close()
    conn_hg.close()

    print(f'\n{"=" * 50}')
    print(f'  行业: {stats["industries"]} 个, 覆盖股票: {stats["industry_stocks"]} 只')
    print(f'  概念: {stats["concepts"]} 个, 覆盖记录: {stats["concept_stocks"]} 条')
    print(f'{"=" * 50}')

    return stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    print('=' * 60)
    print('  证券之星行业/概念分类采集器 v2')
    print('=' * 60)

    print('\n[测试] 行业列表...')
    industries = fetch_industry_list()
    print(f'  {len(industries)} 个行业')
    for ind in industries[:3]:
        print(f'  {ind["name"]}: {ind["stock_count"]}只 涨{ind["up"]} 跌{ind["down"]}')

    print('\n[测试] 概念列表...')
    concepts = fetch_concept_list()
    print(f'  {len(concepts)} 个概念')
    for con in concepts[:5]:
        print(f'  {con["name"]} ({con.get("stock_count", "?")}只)')
