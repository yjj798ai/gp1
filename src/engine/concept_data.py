"""
概念数据层 — 概念驱动×多因子融合

聚合3个数据源获取股票关联概念：
  1. ths_hot_stocks.concepts（同花顺官方概念标签）
  2. limit_up_cache.reason → extract_concepts_from_reason（涨停原因关键词提取）
  3. theme_stock_cache（题材挖掘关联）

计算今日活跃概念强度 = 概念关联涨停数 × 连板系数
"""

import sqlite3
import logging
from collections import Counter
from datetime import datetime

log = logging.getLogger(__name__)

_DB_PATH = "a13/hot_rank.db"


def _connect():
    return sqlite3.connect(_DB_PATH, timeout=5)


# ═══════════════════════════════════════════════════════════
# 概念→板块映射（概念跨板块时取主板块）
# ═══════════════════════════════════════════════════════════

CONCEPT_SECTOR_MAP = {
    "电算协同": "电力", "AI算力": "计算机", "算力概念": "计算机",
    "PCB概念": "电子", "PCB板": "电子", "光纤概念": "通信", "光通信": "通信",
    "氟化工": "基础化工", "有机硅": "基础化工", "环氧丙烷": "基础化工",
    "芯片概念": "半导体", "半导体": "半导体", "存储芯片": "半导体",
    "人工智能": "计算机", "AI大模型": "计算机", "人工智能大模型": "计算机",
    "人形机器人": "机械设备", "机器人": "机械设备",
    "国企改革": "综合", "央国企改革": "综合",
    "创新药": "医药", "医药": "医药", "中药": "医药",
    "煤炭": "能源", "有色金属": "采掘", "稀土永磁": "采掘",
    "新能源": "电力设备", "储能": "电力设备", "光伏": "电力设备",
    "房地产": "房地产", "物业管理": "房地产",
    "跨境电商": "商贸零售", "大消费": "商贸零售",
    "锂电池": "电力设备", "固态电池": "电力设备",
    "低空经济": "国防军工", "商业航天": "国防军工",
    "光刻机": "电子", "先进封装": "电子",
    "液冷": "计算机", "数据中心": "计算机", "云计算": "计算机",
    "华为概念": "电子", "鸿蒙概念": "计算机",
    "工业气体": "基础化工",
    "MLCC": "电子", "被动元件": "电子",
    "共封装光学": "通信",
}


# ═══════════════════════════════════════════════════════════
# 获取股票关联概念
# ═══════════════════════════════════════════════════════════

def get_stock_concepts(code: str, name: str = "", reason: str = "") -> list:
    """获取股票关联的所有活跃概念

    聚合来源:
    1. ths_hot_stocks.concepts（同花顺官方标签）
    2. stock_concepts表（ths热门+涨停原因提取的缓存）
    3. limit_up_cache.reason（涨停原因关键词实时提取）
    4. theme_stock_cache（题材挖掘关联）

    返回: ["芯片概念", "先进封装", "PCB概念", ...]
    """
    concepts = set()

    try:
        conn = _connect()
        today = datetime.now().strftime("%Y-%m-%d")

        # 来源1+2: stock_concepts表（已包含ths热门标签+涨停原因提取）
        rows = conn.execute(
            'SELECT concept FROM stock_concepts WHERE code=?', (code,)
        ).fetchall()
        for (c,) in rows:
            if c:
                concepts.add(c)

        # 来源3: 涨停原因关键词实时提取（如果stock_concepts没覆盖到）
        if not concepts and reason:
            from src.collectors.xuangubao import extract_concepts_from_reason
            for c in extract_concepts_from_reason(reason):
                concepts.add(c)

        # 来源4: 题材挖掘关联
        rows = conn.execute(
            'SELECT theme_name FROM theme_stock_cache WHERE stock_code=? AND date=?',
            (code, today)
        ).fetchall()
        for (t,) in rows:
            if t:
                concepts.add(t)

        conn.close()
    except Exception as e:
        log.debug(f"get_stock_concepts({code}) failed: {e}")

    return list(concepts)


# ═══════════════════════════════════════════════════════════
# 获取今日活跃概念及强度
# ═══════════════════════════════════════════════════════════

def get_active_concepts() -> dict:
    """获取今日活跃概念列表及强度

    强度 = 该概念关联的涨停数 × 连板系数
    连板系数: 首板×1, 2板×1.5, 3板×2, 4板×2.5, 5板+×3

    返回: {"国产芯片": 18, "PCB板": 12, "AI大模型": 10, ...}
    """
    try:
        conn = _connect()
        today = datetime.now().strftime("%Y-%m-%d")

        concept_counter = Counter()

        # 从涨停股的关联板块统计涨停数
        try:
            from src.collectors.xuangubao import fetch_pool, extract_related_plates
            limit_up_stocks = fetch_pool("limit_up")
            plates = extract_related_plates(limit_up_stocks)

            # 获取连板信息
            board_map = {}
            for s in limit_up_stocks:
                code = s.get("symbol", "").replace(".SZ", "").replace(".SS", "")
                name = s.get("stock_chi_name", "")
                board_days = s.get("limit_up_days", 0) or 0
                if code:
                    board_map[code] = board_days

            # 获取涨停股代码列表
            limit_up_codes = set()
            for s in limit_up_stocks:
                code = s.get("symbol", "").replace(".SZ", "").replace(".SS", "")
                if code:
                    limit_up_codes.add(code)

            # 从stock_concepts获取每只涨停股的概念
            for code in limit_up_codes:
                stock_concepts = get_stock_concepts(code)
                board_days = board_map.get(code, 1)
                # 连板系数
                if board_days >= 5:
                    coef = 3.0
                elif board_days >= 4:
                    coef = 2.5
                elif board_days >= 3:
                    coef = 2.0
                elif board_days >= 2:
                    coef = 1.5
                else:
                    coef = 1.0

                for c in stock_concepts:
                    concept_counter[c] += coef

        except Exception as e:
            log.debug(f"涨停概念统计失败: {e}")
            # 降级：直接用选股宝关联板块
            try:
                from src.collectors.xuangubao import fetch_pool, extract_related_plates
                stocks = fetch_pool("limit_up")
                plates = extract_related_plates(stocks)
                for name, cnt in plates.items():
                    concept_counter[name] += cnt
            except Exception:
                pass

        conn.close()
        return dict(concept_counter)

    except Exception as e:
        log.error(f"get_active_concepts failed: {e}")
        return {}


def calc_concept_bonus(code: str, name: str = "", reason: str = "",
                       active_concepts: dict = None) -> dict:
    """计算个股的概念因子加成（0~50分）

    返回: {
        "bonus": 18,
        "matched": ["电算协同", "智能电网"],
        "details": [("电算协同", 8, 3), ("智能电网", 6, 2)]
    }
    """
    if active_concepts is None:
        active_concepts = get_active_concepts()

    if not active_concepts:
        return {"bonus": 0, "matched": [], "details": []}

    stock_concepts = get_stock_concepts(code, name, reason)

    matched = []
    details = []

    for c in stock_concepts:
        if c in active_concepts:
            strength = active_concepts[c]
            matched.append(c)
            details.append((c, strength, len(matched)))

    # 加成: 每关联一个活跃概念+2~8分，上限50分
    bonus = min(50, len(matched) * 8)

    return {
        "bonus": bonus,
        "matched": matched,
        "details": details,
    }
