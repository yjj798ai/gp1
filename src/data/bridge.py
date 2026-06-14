# -*- coding: utf-8 -*-
"""
数据桥接模块 — 连接旧系统SQLite数据库与新前端
当旧系统数据库可用时，从真实数据生成推荐结果
当数据库不可用时，回退到模拟数据
"""
import os
import sys
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# 新统一数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'holy_grail.db')
# 旧系统数据库路径（作为 fallback）
OLD_DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'a13', 'hot_rank.db')


def _get_active_db_path() -> str:
    """获取当前可用的数据库路径，优先使用新库，fallback 到旧库"""
    if os.path.exists(DB_PATH):
        return DB_PATH
    if os.path.exists(OLD_DB_PATH):
        return OLD_DB_PATH
    return DB_PATH  # 返回新库路径，让后续逻辑处理不可用的情况

log = logging.getLogger(__name__)


def db_available() -> bool:
    """检查数据库是否可用"""
    db_path = _get_active_db_path()
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=3)
            count = conn.execute("SELECT COUNT(*) FROM hot_rank_history").fetchone()[0]
            conn.close()
            return count > 0
    except Exception as e:
        log.debug(f"数据库不可用: {e}")
    return False


def get_real_recommendations(top_n: int = 10) -> Optional[List[Dict[str, Any]]]:
    """
    从旧系统数据库获取真实推荐数据
    返回格式与 generate_recommendations() 兼容的字典列表
    """
    if not db_available():
        return None

    try:
        conn = sqlite3.connect(_get_active_db_path(), timeout=5)
        conn.row_factory = sqlite3.Row

        # 获取最新日期
        latest = conn.execute("SELECT MAX(date) FROM hot_rank_history").fetchone()[0]
        if not latest:
            conn.close()
            return None

        # 获取合并3天的TOP股票
        dates_all = conn.execute(
            "SELECT DISTINCT date FROM hot_rank_history ORDER BY date DESC LIMIT 3"
        ).fetchall()

        codes_set = {}
        for d_row in dates_all:
            d = d_row['date']
            for row in conn.execute(
                'SELECT code, MIN(rank) as r FROM hot_rank_history WHERE date=? GROUP BY code',
                (d,)
            ).fetchall():
                code = row['code']
                rank = row['r']
                if code not in codes_set or rank < codes_set[code]:
                    codes_set[code] = rank

        if not codes_set:
            conn.close()
            return None

        codes = list(codes_set.keys())
        ph = ','.join(['?'] * len(codes))

        # 获取股票基本信息
        rows = conn.execute(
            f'SELECT code, name, price, change_pct, sector, concept, pe_ratio, market_cap '
            f'FROM stocks WHERE code IN ({ph}) AND price > 0',
            codes
        ).fetchall()

        stocks = []
        for r in rows:
            code = r['code']
            name = r['name'] or code
            if 'ST' in (name or '').upper():
                continue
            if not r['price'] or r['price'] <= 0:
                continue

            # 获取最新排名
            rank_row = conn.execute(
                'SELECT rank FROM hot_rank_history WHERE code=? AND date=? ORDER BY rank LIMIT 1',
                (code, latest)
            ).fetchone()

            # 获取概念信息
            concepts = []
            try:
                concept_rows = conn.execute(
                    'SELECT concept FROM stock_concepts WHERE code=?', (code,)
                ).fetchall()
                concepts = [cr['concept'] for cr in concept_rows]
            except:
                pass

            stocks.append({
                'code': code,
                'name': name,
                'rank': codes_set.get(code, 9999),
                'price': round(r['price'], 2),
                'change_pct': round(r['change_pct'] or 0, 2),
                'sector': r['sector'] or '',
                'concept': ', '.join(concepts[:5]) if concepts else (r['concept'] or '')[:60],
                'pe': round(r['pe_ratio'] or 0, 1),
                'market_cap': round((r['market_cap'] or 0) / 1e8, 1),
                'latest_rank': rank_row['rank'] if rank_row else 9999,
            })

        stocks.sort(key=lambda x: x['rank'])

        # 尝试调用旧系统的因子引擎计算评分
        try:
            # 添加旧系统路径
            old_sys_path = os.path.join(os.path.dirname(__file__), '..', '..', 'gp_project')
            if old_sys_path not in sys.path:
                sys.path.insert(0, old_sys_path)

            from core.factors import compute_all
            from core.config import load as load_config

            cfg = load_config()
            factor_weights = cfg.get('recommend_weights', cfg.get('factors', {}))
            today = datetime.now().strftime('%Y-%m-%d')

            # 预加载热度历史
            heat_history = {}
            codes_list = [s['code'] for s in stocks]
            if codes_list:
                placeholders = ','.join(['?'] * len(codes_list))
                heat_rows = conn.execute(
                    f'SELECT code, date, rank FROM hot_rank_history '
                    f'WHERE code IN ({placeholders}) AND rank IS NOT NULL ORDER BY date DESC',
                    codes_list
                ).fetchall()
                for hr in heat_rows:
                    heat_history.setdefault(hr['code'], []).append({
                        'date': hr['date'], 'rank': hr['rank']
                    })

            for s in stocks:
                ctx = {
                    'date': today,
                    'prev_ranks': {},
                    'heat_history': {s['code']: heat_history.get(s['code'], [])},
                    'capital_data': {},
                    'hour_rank': {},
                }
                factor_results = compute_all(s['code'], s, ctx)

                total_score = 0
                details = {}
                for fname, fr in factor_results.items():
                    w = factor_weights.get(fname, 1.0)
                    if w < 0.1:
                        continue
                    contribution = fr.score * w
                    total_score += contribution
                    if abs(fr.score) > 0:
                        details[fname] = {'score': fr.score, 'weight': w, 'reason': fr.reason}

                s['total_score'] = round(total_score, 1)
                s['factors'] = details

        except ImportError:
            log.warning("旧系统因子引擎不可用，使用排名作为评分")
            for s in stocks:
                # 简单评分: 排名越靠前分越高
                s['total_score'] = max(0, round(100 - s['rank'] * 0.5, 1))
                s['factors'] = {}

        conn.close()

        # 按评分排序，取TOP N
        stocks.sort(key=lambda x: -x.get('total_score', 0))
        top_stocks = stocks[:top_n]

        # 转换为前端格式
        results = []
        for i, s in enumerate(top_stocks):
            score = s.get('total_score', 0)
            concept_text = s.get('concept', '')
            # 从概念中提取关键词（取前3个概念词作为关键词）
            keyword_list = [c.strip() for c in concept_text.split(',') if c.strip()][:3]
            keyword_text = '、'.join(keyword_list) if keyword_list else ''

            results.append({
                "股票代码": s['code'],
                "股票名称": s['name'],
                "所属板块": s.get('sector', ''),
                "关联概念": concept_text,
                "对应关键词": keyword_text,
                "当前价格": s['price'],
                "综合评分": score,
                "推荐理由": _generate_reason(s),
            })

        return results

    except Exception as e:
        log.error(f"获取真实推荐失败: {e}")
        return None


def _generate_reason(stock: dict) -> str:
    """根据因子数据生成推荐理由"""
    factors = stock.get('factors', {})
    if not factors:
        rank = stock.get('rank', 9999)
        if rank <= 10:
            return f"热度排名第{rank}名，市场关注度极高"
        elif rank <= 30:
            return f"热度排名第{rank}名，关注度较高"
        return f"热度排名第{rank}名"

    # 找贡献最大的因子
    sorted_factors = sorted(factors.items(), key=lambda x: -abs(x[1]['score'] * x[1]['weight']))
    top_factors = sorted_factors[:3]

    reasons = []
    # 英文因子名 → 中文显示名（完整映射）
    display_names = {
        'heat_value': '热度值', 'heat_momentum': '热度动量', 'heat_rank': '热度排名',
        'capital_inflow': '资金流入', 'capital_flow': '资金流向',
        'price_advantage': '价格优势', 'sector_momentum': '板块动量',
        'sector_phase': '板块阶段', 'sector_score': '板块评分',
        'ma5_position': '均线位置', 'ma_density': '均线密集度',
        'volume_ratio': '量比', 'turnover_anomaly': '换手率异动',
        'market_trend_20d': '20日趋势', 'market_trend': '市场趋势',
        'concept_flow': '概念资金', 'concept_momentum': '概念动量',
        'macd_cross': 'MACD金叉', 'ma_divergence': '均线发散',
        'chip_concentration': '筹码集中度',
        'brewing_signal': '酿酒期信号', 'hot_topic': '热词关联',
        'theme_durability': '题材持续性',
    }

    for fname, fd in top_factors:
        name = display_names.get(fname, fname)
        if fd['score'] > 0:
            reasons.append(f"{name}正向(+{fd['score']:.0f})")
        else:
            reasons.append(f"{name}负向({fd['score']:.0f})")

    return "、".join(reasons) if reasons else "多因子综合评分"


def get_real_sector_data() -> Optional[List[Dict[str, Any]]]:
    """从数据库获取真实板块数据"""
    if not db_available():
        return None
    # TODO: 后续从数据库读取真实板块数据
    return None


def get_data_source_label() -> str:
    """获取当前数据来源标签"""
    if db_available():
        return "真实数据（统一数据库）"
    return "模拟数据（测试阶段）"
