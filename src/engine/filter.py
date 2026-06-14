# -*- coding: utf-8 -*-
"""股神圣杯系统 — 三层过滤漏斗"""
import sqlite3, re, pandas as pd, logging
from datetime import datetime

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
_DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


def _connect():
    return sqlite3.connect(_DB_PATH)


def filter_concepts() -> list:
    """第一层: 概念延续性评估"""
    try:
        conn = _connect()
        # 获取今日同花顺概念活跃数据
        ths = conn.execute('''
            SELECT concepts FROM ths_hot_stocks
            WHERE date=(SELECT MAX(date) FROM ths_hot_stocks)
            AND concepts IS NOT NULL
        ''').fetchall()
        
        concept_weights = {}
        for row in ths:
            for c in (row[0] or '').split(','):
                c = c.strip()
                if c and len(c) >= 2:
                    concept_weights[c] = concept_weights.get(c, 0) + 1
        
        # 取权重最高的15个
        sorted_c = sorted(concept_weights.items(), key=lambda x: -x[1])[:15]
        return [c[0] for c in sorted_c if c[1] >= 2]
    except:
        return ['芯片概念', '半导体', '人工智能', '储能', '锂电池', '新能源汽车', '机器人概念',
                '光伏', '军工', '创新药', 'PCB概念', '光纤概念', '小金属概念', '算力租赁', '固态电池']
    finally:
        try: conn.close()
        except: pass


def get_concept_freshness(concept_name):
    """判断概念新鲜度阶段"""
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT days_on_list FROM ths_concept_rank WHERE name=? ORDER BY date DESC LIMIT 1",
            (concept_name,)
        ).fetchone()
        conn.close()
        
        if not row or not row[0]:
            return '未知'
        
        days = row[0]
        if days <= 1:
            return '启动'
        elif days <= 5:
            return '爆发'
        elif days <= 90:
            return '持续'
        else:
            return '退潮'
    except:
        return '未知'


def rank_stocks(concepts: list, top_n: int = 50) -> pd.DataFrame:
    """第二层: 个股匹配+趋势延续性评分"""
    if not concepts:
        return pd.DataFrame()

    from src.engine.scoring import compute_stock_score
    conn = _connect()
    
    # 找有排名数据的最新日期
    rank_date = conn.execute('''
        SELECT date FROM hot_rank_history 
        WHERE (SELECT COUNT(*) FROM hot_rank_history h2 WHERE h2.date=hot_rank_history.date) > 500
        ORDER BY date DESC LIMIT 1
    ''').fetchone()
    rank_date = rank_date[0] if rank_date else ''
    if not rank_date:
        conn.close()
        return pd.DataFrame()

    # 对每个概念找关联股票
    stock_map = {}
    for concept in concepts:
        codes = set()
        for table, col in [
            ('stock_concepts', 'concept'), ('stocks', 'concept_primary'),
            ('ths_hot_stocks', 'concepts'),
        ]:
            try:
                for r in conn.execute(f'SELECT code FROM {table} WHERE {col} LIKE ? LIMIT 30',
                                       (f'%{concept}%',)).fetchall():
                    codes.add(r[0])
            except: pass
        for c in codes:
            if c not in stock_map:
                stock_map[c] = []
            if concept not in stock_map[c]:
                stock_map[c].append(concept)

    if not stock_map:
        conn.close()
        return pd.DataFrame()

    records = []
    for code, matched in stock_map.items():
        if code.startswith(('688','8','4','920')):
            continue
        try:
            row = conn.execute('''
                SELECT s.name, s.price, h.rank, h.change_pct, s.sector, s.concept_primary
                FROM stocks s LEFT JOIN hot_rank_history h ON s.code=h.code AND h.date=?
                WHERE s.code=?
            ''', (rank_date, code)).fetchone()
        except:
            continue
        if not row or not row[0]:
            continue
        name = row[0]
        price = float(row[1] or 0)
        rank = int(row[2]) if row[2] and row[2] != 'None' else 999
        chg = float(row[3] or 0)
        sector = row[4] or ''
        cp = row[5] or ''

        if price <= 0 or price > 20:
            continue

        # === 新评分逻辑：趋势延续性优先 ===
        score = 0
        reason_parts = []
        
        # 1. 概念匹配分 (权重0.20)
        concept_count = len(matched)
        concept_score = min(concept_count * 3.0, 20.0)
        score += concept_score * 0.20
        if concept_count > 0:
            reason_parts.append(f"🔥 概念: {', '.join(matched[:2])}")
        
        # 2. 趋势预判分 (权重0.15) — 核心改动
        pre_3day_change = 0
        try:
            prev_rows = conn.execute(
                'SELECT change_pct FROM hot_rank_history WHERE code=? AND date<? ORDER BY date DESC LIMIT 3',
                (code, rank_date)
            ).fetchall()
            if prev_rows:
                pre_3day_change = sum(abs(float(r[0] or 0)) for r in prev_rows) / len(prev_rows)
        except:
            pass
        
        if 51 <= rank <= 100 and pre_3day_change < 2:
            trend_score = 15  # 最佳买点：排名51-100起涨位
            reason_parts.append(f"📊 趋势: 排名{rank}起涨位+前3日平稳({pre_3day_change:.1f}%)")
        elif 1 <= rank <= 50:
            trend_score = 5   # 高位，减分
            reason_parts.append(f"📊 趋势: 排名{rank}靠前(高位)")
        else:
            trend_score = 10
            reason_parts.append(f"📊 趋势: 排名{rank}")
        
        # 涨停股惩罚
        if abs(chg) >= 9.9:
            trend_score -= 10
            reason_parts.append("🚨 风险: 涨停高位")
        elif abs(chg) >= 5:
            reason_parts.append(f"📈 涨幅: {chg:+.2f}%")
        
        score += trend_score * 0.15
        
        # 3. 概念新鲜度分 (权重0.08)
        freshness = get_concept_freshness(matched[0] if matched else '')
        if freshness == '启动':
            freshness_score = 6
            reason_parts.append("🔥 概念: 启动期")
        elif freshness == '爆发':
            freshness_score = 4
            reason_parts.append("🔥 概念: 爆发期")
        elif freshness == '退潮':
            freshness_score = -3
            reason_parts.append("⚠️ 概念: 退潮期")
        else:
            freshness_score = 0
        
        score += freshness_score * 0.08
        
        # 4. 板块支撑分 (权重0.15)
        sector_score = 10  # 默认值
        try:
            xgt = conn.execute(
                "SELECT fund_flow_today, limit_up FROM xuangutong_cards WHERE concept LIKE ? ORDER BY date DESC LIMIT 1",
                (f'%{matched[0]}%' if matched else '%',)
            ).fetchone()
            if xgt:
                fund = abs(float(xgt[0] or 0))
                limit = int(xgt[1] or 0)
                sector_score = min(fund / 2, 10) + min(limit * 2, 10)
                if fund > 10:
                    reason_parts.append(f"💰 资金: 板块净流入{fund:.1f}亿")
                if limit > 0:
                    reason_parts.append(f"🚀 涨停: 板块{limit}家涨停")
        except:
            pass
        score += sector_score * 0.15
        
        # 5. 个股基础分 (权重0.25)
        ma_bull = False
        try:
            kline = conn.execute(
                "SELECT price FROM price_5d WHERE code=? ORDER BY date DESC LIMIT 5",
                (code,)
            ).fetchall()
            if len(kline) >= 2:
                prices = [float(r[0] or 0) for r in kline]
                ma5 = sum(prices[:5]) / min(len(prices), 5)
                ma10 = sum(prices) / len(prices)
                ma_bull = ma5 > ma10
        except:
            pass
        
        if price <= 10 and ma_bull:
            base_score = 15
            reason_parts.append(f"📊 低价+均线多头({price:.2f}元)")
        elif ma_bull:
            base_score = 10
        else:
            base_score = 5
        
        score += base_score * 0.25
        
        # 6. 风险惩罚
        penalty = 0
        if name.startswith('ST') or name.startswith('*ST'):
            penalty -= 20
            reason_parts.append("🚨 风险: ST股")
        if code.startswith('688'):
            penalty -= 10
            reason_parts.append("🚨 风险: 科创板")
        
        score += penalty
        
        records.append({
            'code': code, 'name': name, 'sector': sector or '其他',
            'price': round(price, 2), 'change_pct': round(chg, 2),
            'total_score': round(score, 1),
            'match_cnt': len(matched), 'concepts': matched,
            'reason': ' | '.join(reason_parts) if reason_parts else f'📰{sector or "其他"}概念匹配',
        })

    conn.close()
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    return df.sort_values('total_score', ascending=False).head(top_n).reset_index(drop=True)


def run_filter_pipeline(top_n: int = 15):
    """完整管线: 概念过滤→个股排序→安全过滤"""
    try:
        concepts = filter_concepts()
        df = rank_stocks(concepts, top_n=top_n * 6)
        
        # 保底: 排名靠前+低价
        if df.empty or len(df) < top_n:
            conn = _connect()
            rdate = conn.execute('SELECT MAX(date) FROM hot_rank_history').fetchone()[0]
            existing = set(df['code']) if not df.empty else set()
            extras = conn.execute('''
                SELECT h.code, s.name, s.price, h.rank, h.change_pct, COALESCE(s.concept_primary, '') as cp
                FROM hot_rank_history h LEFT JOIN stocks s ON h.code=s.code
                WHERE h.date=? AND h.rank IS NOT NULL
                  AND COALESCE(s.price,0) BETWEEN 1 AND 20
                ORDER BY h.rank LIMIT ?
            ''', (rdate, top_n * 3)).fetchall()
            conn.close()
            new_recs = []
            for r in extras:
                if r[0] not in existing:
                    price = float(r[2] or 0)
                    score = max(10, 50 - int(r[3] or 999) * 0.3)
                    new_recs.append({
                        'code': r[0], 'name': r[1] or r[0], 'sector': r[5] or '',
                        'price': price, 'change_pct': float(r[4] or 0),
                        'total_score': round(score, 1),
                        'match_cnt': 0, 'concepts': [r[5]] if r[5] else [],
                        'reason': '📊排名靠前+低价保底',
                    })
            if new_recs:
                extra_df = pd.DataFrame(new_recs)
                df = pd.concat([df, extra_df], ignore_index=True) if not df.empty else extra_df
                df = df.sort_values('total_score', ascending=False).head(top_n).reset_index(drop=True)

        # 重命名列
        df = df.rename(columns={
            'code': '股票代码', 'name': '股票名称', 'price': '当前价格',
            'sector': '所属板块', 'concepts': '关联概念',
            'total_score': '综合评分', 'reason': '推荐理由'
        })
        if '关联概念' in df.columns:
            df['关联概念'] = df['关联概念'].apply(
                lambda x: ', '.join(x[:3]) if isinstance(x, list) else str(x)[:60]
            )

        # 安全过滤
        df = df[~df['股票代码'].str.startswith(('688','8','4','920','300'))]
        df = df[df['当前价格'] <= 20]
        df = df.sort_values('综合评分', ascending=False).head(top_n).reset_index(drop=True)

        stats = {
            'concept_count': len(concepts),
            'candidate_count': len(df),
            'after_safety': len(df),
        }
        return df, stats
    except Exception as e:
        logger.error(f'pipeline: {e}')
        return pd.DataFrame(), {'concept_count': 0, 'candidate_count': 0, 'after_safety': 0}


def run_dual_pipeline(top_n: int = 15):
    """双Agent管线: 概念Agent + 技术Agent + 辩论

    返回: (df, stats)
    df包含: 股票代码, 股票名称, 概念评分, 技术评分, 综合评分, 辩论方法, 推荐理由
    """
    from src.engine.concept_agent import ConceptAgent
    from src.engine.technical_agent import TechnicalAgent
    from src.engine.debate import DebateEngine

    concept_agent = ConceptAgent()
    tech_agent = TechnicalAgent()
    debate_engine = DebateEngine()

    try:
        # 1. 获取热门概念
        hot_concepts = concept_agent.get_hot_concepts()
        if not hot_concepts:
            hot_concepts = filter_concepts()

        # 2. 获取候选股票(来自原管线)
        base_df, base_stats = run_filter_pipeline(top_n=top_n * 4)
        if base_df.empty:
            return base_df, base_stats

        # 3. 双Agent评分 + 辩论
        records = []
        for _, row in base_df.iterrows():
            code = row.get('股票代码', '')
            if not code:
                continue

            # 概念Agent评分
            concept_result = concept_agent.evaluate_stock(code)
            cs = concept_result['score']['total_score']

            # 技术Agent评分
            tech_result = tech_agent.evaluate_stock(code)
            ts = tech_result['total_score']

            # 辩论融合
            debate_result = debate_engine.debate(cs, ts, code)

            # 构建因子明细
            concept_factors = concept_result['score']['detail']
            tech_factors = tech_result.get('factors', {})

            reason_parts = []
            if concept_factors.get('concepts'):
                reason_parts.append("概念: " + "/".join(concept_factors['concepts'][:2]))
            if concept_factors.get('freshness') and concept_factors['freshness'] != '未知':
                reason_parts.append(concept_factors['freshness'])
            if tech_factors:
                # 找最高分因子
                best_tech = max(tech_factors.items(), key=lambda x: x[1].get('score', 0))
                if best_tech[1].get('score', 0) > 0:
                    reason_parts.append(best_tech[0])

            records.append({
                '股票代码': code,
                '股票名称': row.get('股票名称', ''),
                '当前价格': row.get('当前价格', 0),
                '所属板块': row.get('所属板块', ''),
                '关联概念': ', '.join(concept_result['concepts'][:3]),
                '概念评分': cs,
                '技术评分': ts,
                '综合评分': debate_result['final_score'],
                '辩论方法': debate_result['method'],
                '概念权重': debate_result['concept_weight'],
                '技术权重': debate_result['tech_weight'],
                '推荐理由': ' | '.join(reason_parts) if reason_parts else '综合评分',
            })

        if not records:
            return pd.DataFrame(), base_stats

        df = pd.DataFrame(records)
        df = df.sort_values('综合评分', ascending=False).head(top_n).reset_index(drop=True)

        stats = {
            'concept_count': len(hot_concepts),
            'candidate_count': len(records),
            'after_safety': len(df),
            'agents': 'concept+tech+debate',
        }
        return df, stats

    except Exception as e:
        logger.error(f'dual_pipeline: {e}')
        return pd.DataFrame(), {'concept_count': 0, 'candidate_count': 0, 'after_safety': 0}
