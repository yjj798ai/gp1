# -*- coding: utf-8 -*-
"""
数据库同步脚本 — 将 holy_grail.db 的行业/概念数据同步到 hot_rank.db

用法:
  python scripts/sync_db.py          # 全量同步
  python scripts/sync_db.py --check  # 只检查不同步的数据量

同步内容:
  1. stock_industry 表（行业分类）
  2. stock_concepts 表（概念板块）
  3. stocks 表的 sector 列（一级行业）
  4. stocks 表的 concept 列（概念，顿号分隔）
"""
import sqlite3
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('sync_db')

SRC_DB = "E:/AI/gp1/data/holy_grail.db"
DST_DB = "E:/AI/gp1/a13/hot_rank.db"


def sync_industry_concepts(dry_run=False):
    """将 holy_grail 的行业/概念数据同步到 hot_rank"""
    src = sqlite3.connect(SRC_DB, timeout=5)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(DST_DB, timeout=5)

    stats = {"industry": 0, "concepts": 0, "sector_updated": 0, "concept_updated": 0}

    # ── 1. 创建目标表（如果不存在）──
    dst.execute('''
        CREATE TABLE IF NOT EXISTS stock_industry (
            code TEXT PRIMARY KEY,
            level1 TEXT, level2 TEXT, level3 TEXT,
            industry_chain TEXT, updated_at TEXT
        )
    ''')
    dst.execute('''
        CREATE TABLE IF NOT EXISTS stock_concepts (
            code TEXT NOT NULL, concept TEXT NOT NULL,
            PRIMARY KEY (code, concept)
        )
    ''')

    # ── 2. 同步 stock_industry ──
    rows = src.execute('SELECT * FROM stock_industry').fetchall()
    if rows:
        if not dry_run:
            dst.execute('DELETE FROM stock_industry')
            for r in rows:
                dst.execute(
                    'INSERT OR REPLACE INTO stock_industry VALUES (?,?,?,?,?,?)',
                    (r['code'], r['level1'], r['level2'], r['level3'],
                     r['industry_chain'], r['updated_at'])
                )
        stats["industry"] = len(rows)
    log.info(f'stock_industry: {len(rows)} 行')

    # ── 3. 同步 stock_concepts ──
    rows2 = src.execute('SELECT * FROM stock_concepts').fetchall()
    if rows2:
        if not dry_run:
            dst.execute('DELETE FROM stock_concepts')
            for r in rows2:
                dst.execute(
                    'INSERT OR REPLACE INTO stock_concepts VALUES (?,?)',
                    (r['code'], r['concept'])
                )
        stats["concepts"] = len(rows2)
    log.info(f'stock_concepts: {len(rows2)} 行')

    # ── 4. 同步 stocks 表的 sector 列 ──
    src_stocks = src.execute(
        'SELECT code, sector FROM stocks WHERE sector IS NOT NULL AND sector != ""'
    ).fetchall()
    if src_stocks and not dry_run:
        for r in src_stocks:
            try:
                dst.execute('UPDATE stocks SET sector = ? WHERE code = ?', (r['sector'], r['code']))
                if dst.total_changes:
                    stats["sector_updated"] += 1
            except Exception:
                pass
    log.info(f'stocks.sector 更新: {len(src_stocks)} 只')

    # ── 5. 同步 stocks 表的 concept 列 ──
    src_concepts = src.execute(
        'SELECT code, concept FROM stocks WHERE concept IS NOT NULL AND concept != ""'
    ).fetchall()
    if src_concepts and not dry_run:
        for r in src_concepts:
            try:
                dst.execute('UPDATE stocks SET concept = ? WHERE code = ?', (r['concept'], r['code']))
                if dst.total_changes:
                    stats["concept_updated"] += 1
            except Exception:
                pass
    log.info(f'stocks.concept 更新: {len(src_concepts)} 只')

    if not dry_run:
        dst.commit()
    src.close()
    dst.close()

    return stats


def check_sync_status():
    """检查两个库的数据差异"""
    src = sqlite3.connect(SRC_DB, timeout=5)
    dst = sqlite3.connect(DST_DB, timeout=5)

    print('\n数据对比:')
    print(f'{"表/字段":20s} {"holy_grail":>12s} {"hot_rank":>12s} {"状态":>8s}')

    # stocks
    src_s = src.execute('SELECT COUNT(*) FROM stocks').fetchone()[0]
    dst_s = dst.execute('SELECT COUNT(*) FROM stocks').fetchone()[0]
    print(f'{"stocks":20s} {src_s:>12d} {dst_s:>12d} {"✅" if dst_s >= src_s else "⚠️"}')

    # stock_industry
    try:
        src_i = src.execute('SELECT COUNT(*) FROM stock_industry').fetchone()[0]
    except Exception:
        src_i = 0
    try:
        dst_i = dst.execute('SELECT COUNT(*) FROM stock_industry').fetchone()[0]
    except Exception:
        dst_i = 0
    print(f'{"stock_industry":20s} {src_i:>12d} {dst_i:>12d} {"✅" if dst_i >= src_i else "❌"}')

    # stock_concepts
    try:
        src_c = src.execute('SELECT COUNT(*) FROM stock_concepts').fetchone()[0]
    except Exception:
        src_c = 0
    try:
        dst_c = dst.execute('SELECT COUNT(*) FROM stock_concepts').fetchone()[0]
    except Exception:
        dst_c = 0
    print(f'{"stock_concepts":20s} {src_c:>12d} {dst_c:>12d} {"✅" if dst_c >= src_c else "❌"}')

    # sector_snapshot
    src_ss = src.execute('SELECT COUNT(*) FROM sector_snapshot').fetchone()[0]
    dst_ss = dst.execute('SELECT COUNT(*) FROM sector_snapshot').fetchone()[0]
    print(f'{"sector_snapshot":20s} {src_ss:>12d} {dst_ss:>12d} {"✅" if dst_ss >= src_ss else "⚠️"}')

    # hot_rank_history
    src_h = src.execute('SELECT COUNT(*) FROM hot_rank_history').fetchone()[0]
    dst_h = dst.execute('SELECT COUNT(*) FROM hot_rank_history').fetchone()[0]
    print(f'{"hot_rank_history":20s} {src_h:>12d} {dst_h:>12d} {"✅" if dst_h >= src_h else "⚠️"}')

    # price_5d
    src_p = src.execute('SELECT COUNT(*) FROM price_5d').fetchone()[0]
    dst_p = dst.execute('SELECT COUNT(*) FROM price_5d').fetchone()[0]
    print(f'{"price_5d":20s} {src_p:>12d} {dst_p:>12d} {"✅" if dst_p >= src_p else "⚠️"}')

    # stocks 有 sector 的
    src_sec = src.execute("SELECT COUNT(*) FROM stocks WHERE sector IS NOT NULL AND sector != ''").fetchone()[0]
    dst_sec = dst.execute("SELECT COUNT(*) FROM stocks WHERE sector IS NOT NULL AND sector != ''").fetchone()[0]
    print(f'{"stocks有sector":20s} {src_sec:>12d} {dst_sec:>12d} {"✅" if dst_sec >= src_sec else "❌"}')

    src.close()
    dst.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='数据库同步工具')
    parser.add_argument('--check', action='store_true', help='只检查不同步状态')
    args = parser.parse_args()

    if args.check:
        check_sync_status()
    else:
        print('=' * 50)
        print('  数据库同步: holy_grail.db → hot_rank.db')
        print('=' * 50)
        stats = sync_industry_concepts(dry_run=False)
        print(f'\n同步完成:')
        print(f'  stock_industry: {stats["industry"]} 行')
        print(f'  stock_concepts: {stats["concepts"]} 行')
        print(f'  stocks.sector: {stats["sector_updated"]} 只更新')
        print(f'  stocks.concept: {stats["concept_updated"]} 只更新')
        print()
        check_sync_status()
