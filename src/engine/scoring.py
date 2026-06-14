# -*- coding: utf-8 -*-
"""
股神圣杯系统 — 因子评分引擎（百分制）
满分100分，12维度加权，评分区间 0~100
"""
import sqlite3
import logging
from datetime import datetime, timedelta

log = logging.getLogger('scoring')

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


# ════════════════════════════════════════════
# 技术因子函数（新增5个）
# ════════════════════════════════════════════

def _ema(data: list, period: int) -> list:
    """指数移动平均(辅助函数)"""
    result = []
    k = 2 / (period + 1)
    for i, val in enumerate(data):
        if i == 0:
            result.append(float(val))
        else:
            result.append(float(val) * k + result[-1] * (1 - k))
    return result


def _calc_macd(code: str) -> float:
    """MACD金叉评分 0~10分

    从 price_5d 读取近60天收盘价
    计算 EMA12, EMA26 → DIF → DEA
    DIF上穿DEA=金叉→高分，DIF下穿DEA=死叉→低分
    数据不足26天时用简化版（5日/10日均线交叉代替）
    """
    try:
        conn = _connect()
        rows = conn.execute(
            'SELECT price FROM price_5d WHERE code=? ORDER BY date ASC',
            (code,)
        ).fetchall()
        conn.close()

        if len(rows) < 10:
            return 0  # 数据不足，不加分

        closes = [float(r['price']) for r in rows]

        if len(closes) >= 26:
            # 完整MACD
            ema12 = _ema(closes, 12)
            ema26 = _ema(closes, 26)
            dif = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
            dea = _ema(dif, 9)

            recent_dif = dif[-3:]
            recent_dea = dea[-3:]

            if recent_dif[-1] > recent_dea[-1] and recent_dif[-2] <= recent_dea[-2]:
                return 10
            if recent_dif[-1] > recent_dea[-1]:
                return 6
            if recent_dif[-1] < recent_dea[-1] and recent_dif[-2] >= recent_dea[-2]:
                return 2
            return 2
        else:
            # 简化版：5日/10日均线交叉
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes[-min(10, len(closes)):]) / min(10, len(closes))
            if ma5 > ma10:
                return 4  # 短期在长期上方
            return 0
    except Exception:
        return 0


def _calc_ma_divergence(code: str) -> float:
    """均线发散评分 0~8分

    MA5 > MA10 > MA20 = 多头排列 → 高分
    MA5-MA20差距越大=发散越好 → 更高分
    MA5 < MA10 < MA20 = 空头排列 → 低分
    """
    try:
        conn = _connect()
        rows = conn.execute(
            'SELECT price FROM price_5d WHERE code=? ORDER BY date DESC LIMIT 20',
            (code,)
        ).fetchall()
        conn.close()

        prices = [float(r['price']) for r in rows]
        if len(prices) < 10:
            return 0

        ma5 = sum(prices[:5]) / 5

        if len(prices) >= 20:
            ma10 = sum(prices[:10]) / 10
            ma20 = sum(prices) / 20

            if ma5 > ma10 > ma20:
                spread = (ma5 - ma20) / ma20 * 100
                if spread > 8: return 8
                if spread > 5: return 7
                if spread > 3: return 6
                if spread > 1: return 5
                return 4
            elif ma5 < ma10 < ma20:
                return 0
            else:
                return 0
        else:
            # 简化版：只有MA5
            if prices[0] > ma5:
                return 3  # 价格在MA5上方
            return 0
    except Exception:
        return 3


def _calc_chip_concentration(code: str) -> float:
    """筹码集中度评分 0~6分

    用近20天振幅判断：
    振幅越小=筹码越集中=变盘前兆=高分
    振幅越大=筹码分散=低分
    """
    try:
        conn = _connect()
        rows = conn.execute(
            'SELECT high, low FROM price_5d WHERE code=? ORDER BY date DESC LIMIT 20',
            (code,)
        ).fetchall()
        conn.close()

        if len(rows) < 3:
            return 0

        highs = [float(r['high']) for r in rows]
        lows = [float(r['low']) for r in rows]

        amplitude = (max(highs) - min(lows)) / min(lows) * 100

        if amplitude < 10: return 6
        if amplitude < 20: return 5
        if amplitude < 30: return 4
        if amplitude < 50: return 2
        return 0
    except Exception:
        return 0


def _calc_volume_anomaly(code: str) -> float:
    """成交量异动评分 0~6分

    当日成交量 > 5日均量×1.5 = 放量 = 资金关注
    当日成交量 < 5日均量×0.5 = 缩量 = 无人问津
    """
    try:
        conn = _connect()
        rows = conn.execute(
            'SELECT volume FROM price_5d WHERE code=? ORDER BY date DESC LIMIT 6',
            (code,)
        ).fetchall()
        conn.close()

        volumes = [float(r['volume']) for r in rows if r['volume']]
        if len(volumes) < 3:
            return 0

        today_vol = volumes[0]
        avg_vol = sum(volumes[1:]) / max(len(volumes) - 1, 1)

        if avg_vol <= 0:
            return 0

        ratio = today_vol / avg_vol
        if ratio > 3: return 6
        if ratio > 2: return 5
        if ratio > 1.5: return 4
        if ratio > 0.7: return 0
        return 0
    except Exception:
        return 0


def _calc_consecutive_trend(code: str) -> float:
    """连续涨跌评分 0~5分

    连续上涨天数越长=趋势越强=高分
    连续下跌天数越长=趋势越弱=低分
    """
    try:
        conn = _connect()
        rows = conn.execute(
            'SELECT price FROM price_5d WHERE code=? ORDER BY date DESC LIMIT 10',
            (code,)
        ).fetchall()
        conn.close()

        prices = [float(r['price']) for r in rows]
        if len(prices) < 3:
            return 0

        # 从最新往旧数，连续上涨天数
        up_days = 0
        for i in range(len(prices) - 1):
            if prices[i] > prices[i + 1]:
                up_days += 1
            else:
                break

        if up_days >= 5: return 5
        if up_days >= 3: return 4
        if up_days >= 1: return 3
        return 0
    except Exception:
        return 0


# ════════════════════════════════════════════
# 辅助评分函数（百分制）
# ════════════════════════════════════════════

def _get_sector_hot_tag(sector: str) -> tuple:
    """根据 stocks.sector(一级行业) 通过映射表查 sector_snapshot 的 hot_tag

    查询链:
      stocks.sector (level1)
      → sector_mapping.level1 → sector_mapping.level2
      → sector_snapshot.name (level2)
      → sector_snapshot.hot_tag

    返回: (tag: str|None, flow: float)
    """
    if not sector or sector in ('未知', '其他', ''):
        return (None, 0)

    try:
        conn = _connect()
        snap = conn.execute('SELECT MAX(date) FROM sector_snapshot').fetchone()
        if not snap or not snap[0]:
            conn.close()
            return (None, 0)

        # 通过映射表查二级行业列表
        level2_list = conn.execute(
            'SELECT level2 FROM sector_mapping WHERE level1=?',
            (sector,)
        ).fetchall()

        # 遍历二级行业，找第一个有 hot_tag 的
        for l2 in level2_list:
            row = conn.execute(
                'SELECT hot_tag, net_flow FROM sector_snapshot WHERE date=? AND name=?',
                (snap[0], l2[0])
            ).fetchone()
            if row and row['hot_tag']:
                tag = row['hot_tag']
                flow = float(row['net_flow'] or 0)
                conn.close()
                return (tag, flow)

        conn.close()
        return (None, 0)
    except Exception:
        return (None, 0)


def _calc_sector_score(sector: str) -> float:
    """板块强度评分 0~25分（权重25%）

    通过 sector_mapping 映射表匹配 sector_snapshot 的 hot_tag:
      爆发期 + 大资金流入 → 25
      爆发期 → 22
      启动期 + 大资金流入 → 20
      启动期 → 18
      有板块但不在sector_snapshot → 14
      无板块/未知 → 10
      退潮期 → 5
    """
    if not sector or sector in ('未知', '其他', ''):
        return 10  # 无板块

    tag, flow = _get_sector_hot_tag(sector)

    if tag == '爆发':
        score = 22
        if flow > 50:
            score = 25
    elif tag == '启动':
        score = 18
        if flow > 50:
            score = 20
    elif tag == '退潮':
        score = 5
    else:
        return 14  # 有板块但不在快照中

    if flow > 50 and score < 25:
        score += 2
    if flow < -50:
        score = max(0, score - 3)

    return max(0, min(25, score))


def _calc_concept_score(concepts: list) -> float:
    """概念评分 0~20分（权重20%）
    
    映射:
      ≥5个概念 → 20
      3~4个 → 15
      2个 → 10
      1个 → 8
      0个 → 0
    """
    if not concepts:
        return 0
    n = len(concepts)
    if n >= 8:
        return 20
    if n >= 5:
        return 18
    if n >= 3:
        return 12
    if n >= 2:
        return 10
    return 6  # 只有1个概念


def _calc_trend_score(prev_rank: int, rank: int) -> float:
    """排名趋势评分 0~5分（权重5%）"""
    if prev_rank and rank and prev_rank > 0 and prev_rank > rank:
        diff = prev_rank - rank
        if diff > 50:
            return 5
        if diff > 20:
            return 4
        if diff > 10:
            return 3
        if diff > 0:
            return 2
    return 1


# ════════════════════════════════════════════
# 推荐理由生成
# ════════════════════════════════════════════

def _build_rich_reason(code: str, name: str, rank: int, price: float,
                       change_pct: float, prev_rank: int = None,
                       sector: str = None, concepts: list = None,
                       total_score: float = None) -> str:
    """生成按因子维度分类的推荐理由

    输出格式:
    基础化工板块 | 涨幅+10.01% | 连板2天 | 均线密集 | 趋势向上 | 高位区间
    不包含评分（表格已有评分列）
    """
    # ── 概念标签 ──
    sector_label = ""
    if sector and sector not in ('未知', '其他', ''):
        sector_label = f"📰{sector}"

    # ── 因子信号（按维度归类）──
    signals = []

    # 涨跌幅信号
    if abs(change_pct) > 0.5:
        signals.append(f"涨幅{change_pct:+.2f}%")

    # 排名变化信号
    if prev_rank and rank and prev_rank > 0:
        rank_change = prev_rank - rank
        if rank_change > 0:
            signals.append(f"热度上升{rank_change}位")
        elif rank_change < -5:
            signals.append(f"热度下降{abs(rank_change)}位")

    # 均线+趋势信号
    try:
        conn = _connect()
        rows = conn.execute(
            'SELECT price FROM price_5d WHERE code=? ORDER BY date DESC LIMIT 20',
            (code,)
        ).fetchall()
        conn.close()

        if len(rows) >= 10:
            prices = [float(r['price']) for r in rows if r['price'] and float(r['price']) > 0]
            if len(prices) >= 10:
                ma5 = sum(prices[:5]) / 5
                ma10 = sum(prices[:10]) / 10
                if ma10 > 0:
                    cv = abs(ma5 - ma10) / ma10
                    if cv < 0.01:
                        signals.append("均线高度密集，变盘在即")
                    elif cv < 0.03:
                        signals.append("均线趋于密集")
                if price > 0 and ma5 > 0:
                    ratio = price / ma5
                    if ratio < 0.95:
                        signals.append("低于5日均线，有反弹空间")
                    elif ratio > 1.05:
                        signals.append("站上5日均线，趋势向上")
                high_20d = max(prices[:20]) if len(prices) >= 20 else max(prices)
                low_20d = min(prices[:20]) if len(prices) >= 20 else min(prices)
                price_range = high_20d - low_20d
                if price_range > 0:
                    pos = (price - low_20d) / price_range
                    if pos < 0.3:
                        signals.append("处于20日低位")
                    elif pos > 0.8:
                        signals.append("处于20日高位")
    except Exception:
        pass

    # 涨停/连板信号
    try:
        conn = _connect()
        today = datetime.now().strftime("%Y-%m-%d")
        row = conn.execute(
            'SELECT limit_days, break_times FROM limit_up_cache WHERE code=? AND date=?',
            (code, today)
        ).fetchone()
        conn.close()

        if row:
            limit_days = row[0] or 0
            break_times = row[1] or 0
            if limit_days >= 2:
                signals.append(f"连板{limit_days}天")
            elif limit_days == 1:
                signals.append("今日涨停")
            if break_times > 0:
                signals.append(f"炸板{break_times}次")
    except Exception:
        pass

    # 概念信号
    if concepts and len(concepts) > 0:
        top = concepts[:3]
        signals.append(f"涵盖{'/'.join(top)}")
    
    # 📢 板块龙头信号
    leader_signal = ""
    try:
        conn = _connect()
        row = conn.execute('''
            SELECT name FROM limit_up_cache WHERE reason LIKE ? AND date=(SELECT MAX(date) FROM limit_up_cache)
        ''', (f'%{sector[:4]}%',)).fetchone()
        conn.close()
        if row:
            leader_signal = f"{row[0]}领涨"
    except:
        pass

    # ── 组装结构化信息（借鉴AI决策报告格式）──
    parts = []
    
    # 📰 催化：概念标签
    if sector_label:
        parts.append(sector_label)
    
    # 📊 趋势信号：涨跌幅+均线+排名
    trend_parts = []
    if abs(change_pct) > 0.5:
        trend_parts.append(f"{change_pct:+.1f}%")
    for sig in signals:
        if any(kw in sig for kw in ['均线', '趋势', '站上', '低于', '反弹', '变盘']):
            trend_parts.append(sig[:12])
    if trend_parts:
        parts.append("📊" + "|".join(trend_parts[:3]))
    
    # 🚨 风险：涨幅过大/排名下降
    risk_parts = []
    if abs(change_pct) > 9:
        risk_parts.append("涨停")
    if prev_rank and rank and prev_rank > 0 and (prev_rank - rank) < -5:
        risk_parts.append("热度降")
    if risk_parts:
        parts.append("🚨" + "|".join(risk_parts))
    
    # 📢 动态：涨停/连板/龙头 + 驱动逻辑
    news_parts = []
    for sig in signals:
        if any(kw in sig for kw in ['涨停', '连板', '炸板']):
            news_parts.append(sig)
    if leader_signal:
        news_parts.append(leader_signal)
    # 查询题材驱动逻辑（xuangutong_themes）
    if not news_parts:
        try:
            conn = _connect()
            # 先按板块匹配驱动逻辑
            if sector:
                row = conn.execute('''
                    SELECT description FROM xuangutong_themes 
                    WHERE date=(SELECT MAX(date) FROM xuangutong_themes) 
                    AND (theme LIKE ? OR description LIKE ?) LIMIT 1
                ''', (f'%{sector}%', f'%{sector[:4]}%')).fetchone()
                if row and row[0]:
                    news_parts.append(row[0][:25])
                else:
                    # 取第一条驱动逻辑兜底
                    row2 = conn.execute('''
                        SELECT description FROM xuangutong_themes 
                        WHERE date=(SELECT MAX(date) FROM xuangutong_themes) LIMIT 1
                    ''').fetchone()
                    if row2 and row2[0]:
                        news_parts.append(row2[0][:25])
            conn.close()
        except:
            pass
    if news_parts:
        parts.append("📢" + "|".join(news_parts[:2]))
    
    return " ".join(parts) if parts else "综合评分较高"


# ════════════════════════════════════════════
# 涨停池热度因子
# ════════════════════════════════════════════

def _calc_limit_up_heat(sector: str, code: str = None) -> float:
    """涨停池热度评分 0~7分

    从 limit_up_cache 统计今日涨停股数
    如果个股所在板块有涨停 → 高分（跟风效应）

    规则:
      个股本身在涨停池 → 7分
      个股所在板块有≥3只涨停 → 7分
      个股所在板块有1~2只涨停 → 4分
      无涨停 → 0分
    """
    if not sector or sector in ('未知', '其他', ''):
        return 0

    try:
        conn = _connect()
        today = datetime.now().strftime("%Y-%m-%d")

        if code:
            in_pool = conn.execute(
                'SELECT 1 FROM limit_up_cache WHERE code=? AND date=?',
                (code, today)
            ).fetchone()
            if in_pool:
                conn.close()
                return 7

        # 统计今日涨停总数
        total = conn.execute(
            'SELECT COUNT(*) FROM limit_up_cache WHERE date=?',
            (today,)
        ).fetchone()[0]

        conn.close()

        if total >= 50:
            return 7   # 市场大涨，大面积涨停
        elif total >= 20:
            return 4   # 市场活跃
        else:
            return 0

    except Exception:
        return 0


# ════════════════════════════════════════════
# 主评分函数
# ════════════════════════════════════════════

def compute_stock_score(code: str, rank: int, price: float, change_pct: float,
                        market_cap: float = 0, prev_rank: int = None,
                        sector: str = None, concepts: list = None) -> dict:
    """多因子评分 — 12维度加权，满分100分

    权重分布:
      板块强度    15分  — 板块阶段(爆发/启动/退潮) + 资金净流入
      概念热度    10分  — 概念数量(≥5→满分)
      涨跌幅动量  10分  — 今日涨幅大小
      价格优势    10分  — 5元以下高弹性
      排名热度     5分  — 排名靠前
      市值因子     5分  — 50亿以下加分
      排名趋势     3分  — 排名上升
      MACD金叉    10分  — DIF/DEA金叉=高分
      均线发散     8分  — MA5>MA10>MA20多头排列
      筹码集中度   6分  — 近20天振幅越小=越集中
      成交量异动   6分  — 放量=资金关注
      连续涨跌     5分  — 连续上涨天数

    返回:
    {
        "total_score": 0~100,
        "factors": {...},
        "direction": "buy/hold",
        "confidence": "高/中/低",
        "reason": "..."
    }
    """
    factors = {}

    # ── 1. 板块强度 (满分15分) ──
    sec_score = _calc_sector_score(sector)
    factors["板块强度"] = {
        "score": round(sec_score * 0.6, 1),  # 25→15
        "weight": 0.15,
        "detail": f"{sector or '未知'}",
    }

    # ── 2. 概念热度 (满分10分) ──
    con_score = _calc_concept_score(concepts)
    factors["概念热度"] = {
        "score": round(con_score * 0.5, 1),  # 20→10
        "weight": 0.10,
        "detail": f"{len(concepts or [])}个概念",
    }

    # ── 3. 涨跌幅动量 (满分10分) ──
    if change_pct > 9:
        m_score = 10
    elif change_pct > 5:
        m_score = 8
    elif change_pct > 2:
        m_score = 6
    elif change_pct > 0:
        m_score = 4
    elif change_pct > -3:
        m_score = 2
    else:
        m_score = 1
    factors["涨跌幅动量"] = {
        "score": m_score,
        "weight": 0.10,
        "detail": f"{change_pct:+.2f}%",
    }

    # ── 4. 价格优势 (满分10分) ──
    if price <= 0:
        p_score = 0
    elif price <= 5:
        p_score = 10
    elif price <= 10:
        p_score = 8
    elif price <= 15:
        p_score = 5
    elif price <= 20:
        p_score = 3
    else:
        p_score = 0
    factors["价格优势"] = {
        "score": p_score,
        "weight": 0.10,
        "detail": f"¥{price:.2f}",
    }

    # ── 5. 排名热度 (满分5分) ──
    if rank <= 10:
        h_score = 5
    elif rank <= 30:
        h_score = 4
    elif rank <= 50:
        h_score = 3
    elif rank <= 100:
        h_score = 2
    else:
        h_score = 1
    factors["排名热度"] = {
        "score": h_score,
        "weight": 0.05,
        "detail": f"第{rank}名",
    }

    # ── 6. 市值因子 (满分5分) ──
    if market_cap <= 0:
        mcap_score = 3
    elif market_cap <= 50:
        mcap_score = 5
    elif market_cap <= 100:
        mcap_score = 4
    elif market_cap <= 500:
        mcap_score = 2
    else:
        mcap_score = 1
    factors["市值因子"] = {
        "score": mcap_score,
        "weight": 0.05,
        "detail": f"{market_cap:.0f}亿",
    }

    # ── 7. 排名趋势 (满分3分) ──
    trend_score = _calc_trend_score(prev_rank, rank)
    factors["排名趋势"] = {
        "score": round(trend_score * 0.6, 1),  # 5→3
        "weight": 0.03,
        "detail": f"{'↑' if prev_rank and rank and prev_rank>rank else '—'}",
    }

    # ── 8. MACD金叉 (满分10分) ──
    macd_score = _calc_macd(code)
    factors["MACD金叉"] = {
        "score": macd_score,
        "weight": 0.10,
        "detail": "金叉" if macd_score >= 8 else ("多头" if macd_score >= 5 else "死叉/空头"),
    }

    # ── 9. 均线发散 (满分8分) ──
    ma_score = _calc_ma_divergence(code)
    factors["均线发散"] = {
        "score": ma_score,
        "weight": 0.08,
        "detail": "多头排列" if ma_score >= 5 else ("空头排列" if ma_score <= 2 else "均线纠缠"),
    }

    # ── 10. 筹码集中度 (满分6分) ──
    chip_score = _calc_chip_concentration(code)
    factors["筹码集中度"] = {
        "score": chip_score,
        "weight": 0.06,
        "detail": "高度集中" if chip_score >= 5 else ("分散" if chip_score <= 2 else "一般"),
    }

    # ── 11. 成交量异动 (满分6分) ──
    vol_score = _calc_volume_anomaly(code)
    factors["成交量异动"] = {
        "score": vol_score,
        "weight": 0.06,
        "detail": "放量" if vol_score >= 5 else ("缩量" if vol_score <= 2 else "正常"),
    }

    # ── 12. 连续涨跌 (满分5分) ──
    trend_5d = _calc_consecutive_trend(code)
    factors["连续涨跌"] = {
        "score": trend_5d,
        "weight": 0.05,
        "detail": f"连涨{int(trend_5d)}天" if trend_5d >= 3 else "正常",
    }

    # ── 13. 涨停池热度 (满分7分) ──
    # 个股所在板块今日有涨停 → 加分（跟风效应）
    limit_heat = _calc_limit_up_heat(sector, code)
    factors["涨停池热度"] = {
        "score": limit_heat,
        "weight": 0.07,
        "detail": f"板块{limit_heat}分" if limit_heat > 0 else "无涨停",
    }

    # ── 综合评分 (0~107→cap at 100) ──
    total_score = sum(f["score"] for f in factors.values())
    total_score = round(max(0, min(100, total_score)), 1)

    # ── 推荐方向 ──
    if total_score >= 80:
        direction = "buy"
        confidence = "高"
    elif total_score >= 60:
        direction = "buy"
        confidence = "中"
    elif total_score >= 40:
        direction = "hold"
        confidence = "中"
    else:
        direction = "hold"
        confidence = "低"

    # ── 推荐理由 ──
    try:
        reason_text = _build_rich_reason(
            code=code, name='', rank=rank, price=price,
            change_pct=change_pct, prev_rank=prev_rank,
            sector=sector, concepts=concepts,
            total_score=total_score,
        )
    except Exception:
        reason_text = f"评分{total_score:.0f}分"

    return {
        "total_score": total_score,
        "factors": factors,
        "direction": direction,
        "confidence": confidence,
        "reason": reason_text,
    }
