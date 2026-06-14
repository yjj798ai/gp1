# -*- coding: utf-8 -*-
"""
行业分类和概念数据采集器 v3

数据来源:
  东方财富 emweb CoreConception API (主)
  URL: http://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax?code=SZ000001

核心策略:
  - 逐只股票调 emweb CoreConception API
  - ssbk 字段包含: 行业分类(前3项) + 概念板块(后续项)
  - 用 BOARD_RANK 区分: rank 1-3 为行业, rank 4+ 为概念
  - 用 ThreadPoolExecutor 并发采集，控制频率

功能:
  - fetch_stock_info(code)    : 获取单只股票行业+概念
  - update_all_stocks()        : 批量更新所有股票
  - ensure_tables()            : 确保数据库表存在
"""

import os
import re
import time
import sqlite3
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

log = logging.getLogger('stock_info_crawler')

# ── 默认数据库路径 ──
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'holy_grail.db'
)

# ── 请求头 ──
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://emweb.securities.eastmoney.com/',
    'Accept': '*/*',
}

# ── 行业关键词 (用于从ssbk中识别行业分类) ──
# 东方财富的行业板块名称通常包含这些关键词
_INDUSTRY_KEYWORDS = {
    '银行', '保险', '证券', '房地产', '建筑', '建材', '钢铁', '煤炭', '有色金属',
    '石油', '化工', '汽车', '家电', '食品饮料', '白酒', '医药', '生物', '电力',
    '新能源', '光伏', '风电', '电子', '半导体', '计算机', '通信', '传媒', '游戏',
    '农业', '牧业', '渔业', '军工', '航天', '航空', '铁路', '公路', '港口',
    '航运', '物流', '旅游', '酒店', '餐饮', '零售', '商贸', '纺织', '服装',
    '造纸', '包装', '环保', '水务', '燃气', '综合', '采掘', '交运', '机械设备',
    '轻工', '美容', '护婴', '家居', '消费电子', '元件', '电池', '电网',
}

# ── 概念排除词 (这些不是真正的概念板块) ──
_EXCLUDE_CONCEPTS = {
    '板块', '风格', '大盘', '小盘', '中盘', '价值', '成长', '长期', '短期',
    '破净', '标普', '富时', '深证', '上证', '创业', '科创', '北证',
    '深股通', '沪股通', '融资融券', '转融通', '机构重仓', '证金持股',
    'HS300', '深成', '中证', '标准普尔',
}


# ═══════════════════════════════════════════════════════════
# 1. 获取单只股票行业+概念
# ═══════════════════════════════════════════════════════════

def fetch_stock_info(code: str) -> dict:
    """
    从 emweb CoreConception API 获取单只股票的行业分类和概念

    URL: http://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax?code=SZ000001

    返回:
        {
            "industry_chain": str,   # 完整行业链: "银行--银行Ⅱ--股份制银行Ⅲ"
            "level1": str,           # 一级行业: "银行"
            "level2": str,           # 二级行业: "银行Ⅱ"
            "level3": str,           # 三级行业: "股份制银行Ⅲ"
            "concepts": list[str],   # 概念列表: ["跨境支付", "区块链", ...]
        }
        失败返回 None
    """
    try:
        c = str(code).zfill(6)
        prefix = 'SZ' if c.startswith(('0', '3')) else 'SH'
        url = f'http://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax?code={prefix}{c}'

        resp = requests.get(url, headers=_HEADERS, timeout=10)
        data = resp.json()

        if not data:
            return None

        ssbk = data.get('ssbk', [])
        if not ssbk:
            return None

        result = {
            'industry_chain': '',
            'level1': '',
            'level2': '',
            'level3': '',
            'concepts': [],
        }

        # 按 BOARD_RANK 排序
        ssbk_sorted = sorted(ssbk, key=lambda x: x.get('BOARD_RANK', 999))

        # 行业分类: rank 1-3 (东方财富的三级行业体系)
        industry_levels = []
        for item in ssbk_sorted:
            rank = item.get('BOARD_RANK', 999)
            name = item.get('BOARD_NAME', '').strip()
            if rank <= 3 and name:
                industry_levels.append(name)

        if industry_levels:
            result['industry_chain'] = '--'.join(industry_levels)
            result['level1'] = industry_levels[0] if len(industry_levels) > 0 else ''
            result['level2'] = industry_levels[1] if len(industry_levels) > 1 else ''
            result['level3'] = industry_levels[2] if len(industry_levels) > 2 else ''

        # 概念板块: rank > 3 的项
        for item in ssbk_sorted:
            rank = item.get('BOARD_RANK', 999)
            name = item.get('BOARD_NAME', '').strip()
            if rank > 3 and name:
                # 排除非概念项
                if any(ex in name for ex in _EXCLUDE_CONCEPTS):
                    continue
                if name.endswith('风格') or name.endswith('股'):
                    continue
                result['concepts'].append(name)

        # 去重
        result['concepts'] = list(dict.fromkeys(result['concepts']))

        if result['industry_chain'] or result['concepts']:
            return result

        return None

    except Exception as e:
        log.debug(f'fetch_stock_info({code}) failed: {e}')
        return None


# ═══════════════════════════════════════════════════════════
# 2. 数据库表管理
# ═══════════════════════════════════════════════════════════

def ensure_tables(db_path: str = None):
    """确保数据库表存在"""
    if db_path is None:
        db_path = _DEFAULT_DB_PATH

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS stock_industry (
                code TEXT PRIMARY KEY,
                level1 TEXT,
                level2 TEXT,
                level3 TEXT,
                industry_chain TEXT,
                updated_at TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS stock_concepts (
                code TEXT,
                concept TEXT,
                PRIMARY KEY (code, concept)
            )
        ''')
        conn.commit()
        conn.close()
        log.info('stock_industry/stock_concepts 表已就绪')
    except Exception as e:
        log.error(f'ensure_tables failed: {e}')


# ═══════════════════════════════════════════════════════════
# 3. 处理单只股票
# ═══════════════════════════════════════════════════════════

def _process_one(code: str, db_path: str) -> dict:
    """
    处理单只股票: 采集 + 写入数据库

    返回: {"code": str, "success": bool, "has_industry": bool, "has_concept": bool, "concept_count": int}
    """
    try:
        info = fetch_stock_info(code)
        if not info:
            return {'code': code, 'success': False, 'has_industry': False, 'has_concept': False, 'concept_count': 0}

        conn = sqlite3.connect(db_path, timeout=5)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        has_industry = False
        has_concept = False

        # a. 更新 stocks 表的 sector 列（一级行业）
        level1 = info.get('level1', '')
        if level1:
            try:
                conn.execute('UPDATE stocks SET sector = ? WHERE code = ?', (level1, code))
                has_industry = True
            except Exception:
                pass

        # b. 更新 stocks 表的 concept 列
        concepts = info.get('concepts', [])
        if concepts:
            concept_str = '\u3001'.join(concepts)
            try:
                conn.execute('UPDATE stocks SET concept = ? WHERE code = ?', (concept_str, code))
                has_concept = True
            except Exception:
                pass

            # 写入 stock_concepts 表
            try:
                conn.execute('DELETE FROM stock_concepts WHERE code = ?', (code,))
                for c in concepts:
                    conn.execute(
                        'INSERT OR IGNORE INTO stock_concepts (code, concept) VALUES (?, ?)',
                        (code, c.strip())
                    )
            except Exception:
                pass

        # c. 写入 stock_industry 表
        industry_chain = info.get('industry_chain', '')
        if industry_chain:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO stock_industry (code, level1, level2, level3, industry_chain, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    code,
                    info.get('level1', ''),
                    info.get('level2', ''),
                    info.get('level3', ''),
                    industry_chain,
                    now,
                ))
                has_industry = True
            except Exception:
                pass

        conn.commit()
        conn.close()

        return {
            'code': code,
            'success': True,
            'has_industry': has_industry,
            'has_concept': has_concept,
            'concept_count': len(concepts),
        }

    except Exception as e:
        log.debug(f'process {code} failed: {e}')
        return {'code': code, 'success': False, 'has_industry': False, 'has_concept': False, 'concept_count': 0}


# ═══════════════════════════════════════════════════════════
# 4. 批量更新所有股票
# ═══════════════════════════════════════════════════════════

def update_all_stocks(db_path: str = None, concurrency: int = 5, max_stocks: int = 0) -> dict:
    """
    批量更新所有股票的行业分类和概念数据

    数据源: emweb CoreConception API (东方财富)
    策略: ThreadPoolExecutor 并发采集，控制频率避免被封

    参数:
      db_path: 数据库路径
      concurrency: 并发线程数，默认5
      max_stocks: 最大处理数量，0=全部

    返回:
      {
        "total": int,
        "success": int,
        "failed": int,
        "has_industry": int,
        "has_concept": int,
        "total_concepts": int,
      }
    """
    if db_path is None:
        db_path = _DEFAULT_DB_PATH

    ensure_tables(db_path)

    # 读取所有股票代码
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        rows = conn.execute('SELECT code FROM stocks ORDER BY code').fetchall()
        conn.close()
    except Exception as e:
        log.error(f'读取stocks表失败: {e}')
        return {'total': 0, 'success': 0, 'failed': 0, 'has_industry': 0, 'has_concept': 0, 'total_concepts': 0}

    codes = [str(r[0]).zfill(6) for r in rows]
    if max_stocks > 0:
        codes = codes[:max_stocks]

    total = len(codes)
    if total == 0:
        log.warning('No stocks found in database')
        return {'total': 0, 'success': 0, 'failed': 0, 'has_industry': 0, 'has_concept': 0, 'total_concepts': 0}

    log.info(f'开始批量采集: {total} 只股票, 并发={concurrency}')

    stats = {
        'total': total,
        'success': 0,
        'failed': 0,
        'has_industry': 0,
        'has_concept': 0,
        'total_concepts': 0,
    }

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {}
        for code in codes:
            futures[pool.submit(_process_one, code, db_path)] = code
            # 控制提交频率
            time.sleep(0.2)

        for future in as_completed(futures):
            code = futures[future]
            try:
                result = future.result()
                if result.get('success'):
                    stats['success'] += 1
                    success_count += 1
                    if result.get('has_industry'):
                        stats['has_industry'] += 1
                    if result.get('has_concept'):
                        stats['has_concept'] += 1
                    stats['total_concepts'] += result.get('concept_count', 0)
                else:
                    stats['failed'] += 1
                    fail_count += 1
            except Exception as e:
                log.error(f'{code} future error: {e}')
                stats['failed'] += 1
                fail_count += 1

            # 进度输出
            done = success_count + fail_count
            if done % 50 == 0 or done == total:
                rate = round(success_count / max(done, 1) * 100)
                print(f'  进度: {done}/{total} ({rate}%)  成功={success_count}  失败={fail_count}')

    print(f'\n{"=" * 50}')
    print(f'  采集完成汇总:')
    print(f'  总股票数: {stats["total"]}')
    print(f'  成功: {stats["success"]}  失败: {stats["failed"]}')
    print(f'  有行业数据: {stats["has_industry"]}')
    print(f'  有概念数据: {stats["has_concept"]}')
    print(f'  概念记录总数: {stats["total_concepts"]}')
    print(f'{"=" * 50}')

    log.info(f'update_all_stocks 完成: {stats}')
    return stats


# ═══════════════════════════════════════════════════════════
# 直接运行测试
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    print('=' * 60)
    print('  行业分类和概念数据采集器 v3 (emweb CoreConception)')
    print('=' * 60)

    # 单只测试
    print('\n[测试] 采集 000001 (平安银行)...')
    info = fetch_stock_info('000001')
    print(f'  行业链: {info.get("industry_chain", "N/A")}')
    print(f'  概念数: {len(info.get("concepts", []))}')
    print(f'  概念: {info.get("concepts", [])[:5]}')

    print('\n[测试] 采集 300866 (安克创新)...')
    info2 = fetch_stock_info('300866')
    print(f'  行业链: {info2.get("industry_chain", "N/A")}')
    print(f'  概念数: {len(info2.get("concepts", []))}')
    print(f'  概念: {info2.get("concepts", [])[:5]}')
