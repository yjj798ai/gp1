"""
板块轮动六维度评分模型

对每个板块/概念，综合6个维度计算热度分（0~100分）：
  涨停活跃(30分) + 资金认可(20分) + 热榜共振(15分)
  + 新闻催化(15分) + 题材新鲜度(10分) + 热词匹配(10分)
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
# 概念名称映射（解决不同数据源名称不统一问题）
# ═══════════════════════════════════════════════════════════

# 主概念 → 别名列表（用于模糊匹配）
_CONCEPT_ALIAS = {
    "国产芯片": ["芯片", "半导体", "存储芯片", "集成电路", "光刻", "先进封装", "芯片概念"],
    "PCB板": ["PCB", "PCB概念", "覆铜板", "印制电路板", "电子化学品"],
    "人工智能大模型": ["AI", "人工智能", "大模型", "AIGC", "ChatGPT", "算力"],
    "大消费": ["消费", "白酒", "食品饮料", "零售", "新零售", "预制菜"],
    "云计算数据中心": ["云计算", "数据中心", "IDC", "云服务", "算力租赁"],
    "工业气体": ["气体", "六氟化钨", "六氟化硫", "三氟化氮", "特种气体"],
    "光通信": ["光模块", "光通信", "光纤", "CPO", "共封装光学", "磷化铟"],
    "商业航天": ["航天", "火箭", "卫星互联网", "卫星", "低轨卫星", "太空"],
    "新能源车": ["新能源汽车", "充电桩", "动力电池", "智能驾驶", "自动驾驶", "锂电"],
    "医药": ["医药", "创新药", "中药", "CRO", "医疗器械", "生物制药", "CXO"],
    "房地产": ["地产", "房地产", "物业", "保障房", "城市更新", "旧改"],
    "国企改革": ["国企", "央企", "国资", "国企改革", "央企改革", "中特估"],
    "光伏": ["光伏", "太阳能", "储能", "逆变器"],
    "锂电池": ["锂电", "锂电池", "碳酸锂", "固态电池", "钠离子电池"],
    "机器人": ["机器人", "人形机器人", "机械臂", "减速器", "伺服电机"],
    "低空经济": ["低空", "飞行汽车", "eVTOL", "无人机", "通用航空"],
    "华为概念": ["华为", "鸿蒙", "昇腾", "华为汽车", "华为手机"],
    "军工": ["军工", "国防军工", "航空发动机", "导弹", "兵装"],
    "氟化工": ["氟化工", "氟", "制冷剂", "三代制冷剂"],
    "环氧丙烷": ["环氧丙烷", "环氧树脂", "聚氨酯"],
}

# 反向映射：别名 → 主概念
_ALIAS_TO_MAIN = {}
for main, aliases in _CONCEPT_ALIAS.items():
    for alias in aliases:
        _ALIAS_TO_MAIN[alias] = main


def normalize_concept(name: str) -> str:
    """将任意概念名归一化到主概念名"""
    if not name:
        return ""
    # 直接匹配主概念
    if name in _CONCEPT_ALIAS:
        return name
    # 别名匹配
    if name in _ALIAS_TO_MAIN:
        return _ALIAS_TO_MAIN[name]
    # 包含匹配（"芯片概念" → "国产芯片"）
    for main, aliases in _CONCEPT_ALIAS.items():
        if main in name or any(a in name for a in aliases if len(a) >= 2):
            return main
    return name  # 无法映射，保持原名


# ═══════════════════════════════════════════════════════════
# 六维度评分
# ═══════════════════════════════════════════════════════════

def _score_limit_up_activity(plate_name: str, plates_dict: dict) -> tuple:
    """维度1: 涨停活跃（30分）— 选股宝涨停池关联板块涨停数"""
    count = plates_dict.get(plate_name, 0)
    if count >= 10:
        return 30, count
    elif count >= 5:
        return 20, count
    elif count >= 3:
        return 10, count
    elif count >= 1:
        return 5, count
    return 0, 0


def _score_capital_flow(plate_name: str, industry_map: dict) -> tuple:
    """维度2: 资金认可（20分）— sector_snapshot净流入"""
    # 先尝试直接匹配，再尝试归一化匹配
    ind = industry_map.get(plate_name, {})
    if not ind:
        norm = normalize_concept(plate_name)
        for name, data in industry_map.items():
            if normalize_concept(name) == norm:
                ind = data
                break

    net_flow = ind.get("net_flow", 0)
    change_pct = ind.get("change_pct", 0)

    # 资金流入为正且涨幅>0
    if net_flow > 5 and change_pct > 1:
        return 20, net_flow
    elif net_flow > 0 and change_pct > 0:
        return 15, net_flow
    elif net_flow > -2:
        return 8, net_flow
    else:
        return 2, net_flow


def _score_hotlist_resonance(plate_name: str, ths_concept_stocks: dict) -> tuple:
    """维度3: 热榜共振（15分）— 同花顺热门榜单中该概念的热门股数量"""
    count = ths_concept_stocks.get(plate_name, 0)
    if count >= 5:
        return 15, count
    elif count >= 3:
        return 10, count
    elif count >= 1:
        return 5, count
    return 0, 0


def _score_news_catalyst(plate_name: str, news_sectors: dict) -> tuple:
    """维度4: 新闻催化（15分）— news_cache中关联板块的新闻数量"""
    count = news_sectors.get(plate_name, 0)
    if count >= 5:
        return 15, count
    elif count >= 3:
        return 10, count
    elif count >= 1:
        return 5, count
    return 0, 0


def _score_theme_freshness(plate_name: str, theme_dates: dict) -> tuple:
    """维度5: 题材新鲜度（10分）— theme_cache/xuangutong_themes生效日期"""
    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    today_dash = today.strftime("%Y-%m-%d")

    # 检查多个可能的日期格式
    for date_fmt in [today_str, today_dash]:
        if date_fmt in theme_dates:
            return 10, "今日"

    # 检查3天内
    for date_str, theme_name in theme_dates.items():
        norm = normalize_concept(theme_name)
        if norm == plate_name or plate_name in theme_name:
            try:
                # 尝试解析日期
                if len(date_str) == 8 and date_str.isdigit():
                    d = datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
                elif "-" in date_str:
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    continue
                days_ago = (today - d).days
                if days_ago <= 1:
                    return 10, f"{days_ago}天前"
                elif days_ago <= 3:
                    return 7, f"{days_ago}天前"
                elif days_ago <= 7:
                    return 3, f"{days_ago}天前"
            except Exception:
                continue

    return 0, "无"


def _score_hot_keyword(plate_name: str, hot_keywords: list) -> tuple:
    """维度6: 热词匹配（10分）— 板块名在热词榜中的得分"""
    for i, (kw, score) in enumerate(hot_keywords):
        # 检查热词是否与板块名相关
        norm_kw = normalize_concept(kw)
        if norm_kw == plate_name or plate_name in kw or kw in plate_name:
            if i < 3:
                return 10, kw
            elif i < 8:
                return 5, kw
            else:
                return 2, kw
    return 0, "无"


# ═══════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════

def calc_sector_heat_score(plate_name: str, plates_dict: dict,
                           industry_map: dict, ths_concept_stocks: dict,
                           news_sectors: dict, theme_dates: dict,
                           hot_keywords: list) -> dict:
    """计算单个板块的六维度热度分

    返回: {
        "name": "国产芯片",
        "total": 85,
        "scores": {"涨停活跃": (30, 13), "资金认可": (15, 48.8), ...}
    }
    """
    scores = {}

    s1, v1 = _score_limit_up_activity(plate_name, plates_dict)
    scores["涨停活跃"] = (s1, v1)

    s2, v2 = _score_capital_flow(plate_name, industry_map)
    scores["资金认可"] = (s2, v2)

    s3, v3 = _score_hotlist_resonance(plate_name, ths_concept_stocks)
    scores["热榜共振"] = (s3, v3)

    s4, v4 = _score_news_catalyst(plate_name, news_sectors)
    scores["新闻催化"] = (s4, v4)

    s5, v5 = _score_theme_freshness(plate_name, theme_dates)
    scores["题材新鲜度"] = (s5, v5)

    s6, v6 = _score_hot_keyword(plate_name, hot_keywords)
    scores["热词匹配"] = (s6, v6)

    total = s1 + s2 + s3 + s4 + s5 + s6

    return {
        "name": plate_name,
        "total": total,
        "scores": scores,
    }


def get_sector_rotation_top(top_n: int = 10) -> list:
    """获取板块轮动TOP N（六维度综合评分）— 缓存5分钟"""
    return _get_sector_rotation_top_impl(top_n)


def _get_sector_rotation_top_impl(top_n: int = 10) -> list:
    """获取板块轮动TOP N（六维度综合评分）

    返回: [
        {"name": "国产芯片", "total": 85, "phase": "爆发期",
         "scores": {"涨停活跃": (30, 13), ...}},
        ...
    ]
    """
    try:
        conn = _connect()
        today = datetime.now().strftime("%Y-%m-%d")

        # ── 收集各维度原始数据 ──

        # 1. 选股宝涨停池关联板块
        try:
            from src.collectors.xuangubao import fetch_pool, extract_related_plates
            limit_up_stocks = fetch_pool("limit_up")
            plates_dict = extract_related_plates(limit_up_stocks)
        except Exception:
            plates_dict = {}

        # 2. sector_snapshot行业板块
        latest_date = conn.execute('SELECT MAX(date) FROM sector_snapshot').fetchone()[0] or ""
        industry_map = {}
        if latest_date:
            conn.row_factory = sqlite3.Row
            for r in conn.execute('''
                SELECT name, AVG(change_pct) as change_pct, AVG(net_flow) as net_flow
                FROM sector_snapshot WHERE date=?
                GROUP BY name
            ''', (latest_date,)).fetchall():
                industry_map[r["name"]] = {
                    "change_pct": float(r["change_pct"] or 0),
                    "net_flow": float(r["net_flow"] or 0),
                }

        # 3. 同花顺热门榜单概念统计
        ths_concept_stocks = Counter()
        try:
            rows = conn.execute(
                'SELECT concepts FROM ths_hot_stocks WHERE date=?', (today,)
            ).fetchall()
            for (concepts_str,) in rows:
                if concepts_str:
                    for c in concepts_str.split(","):
                        c = c.strip()
                        if c:
                            ths_concept_stocks[c] += 1
        except Exception:
            pass

        # 4. 新闻关联板块统计
        news_sectors = Counter()
        try:
            rows = conn.execute(
                'SELECT sector_names FROM news_cache WHERE date=?', (today,)
            ).fetchall()
            for (sectors_str,) in rows:
                if sectors_str:
                    for s in sectors_str.split(","):
                        s = s.strip()
                        if s:
                            news_sectors[s] += 1
        except Exception:
            pass

        # 5. 题材日期
        theme_dates = {}
        try:
            for r in conn.execute(
                'SELECT name, effective_date FROM theme_cache WHERE date=?', (today,)
            ).fetchall():
                theme_dates[str(r["effective_date"])] = r["name"]
            # 也加入选股通
            for r in conn.execute(
                'SELECT theme, date FROM xuangutong_themes WHERE date=?', (today,)
            ).fetchall():
                theme_dates[r["date"]] = r["theme"]
        except Exception:
            pass

        # 6. 热词
        hot_keywords = []
        try:
            rows = conn.execute(
                'SELECT keyword, score FROM news_hot_keywords WHERE date=? ORDER BY score DESC LIMIT 20',
                (today,)
            ).fetchall()
            hot_keywords = [(r[0], r[1]) for r in rows]
        except Exception:
            pass

        conn.close()

        # ── 计算所有板块的六维度得分 ──
        # 候选板块：选股宝关联板块 + 同花顺热门概念 + sector_snapshot行业
        all_plates = set(plates_dict.keys())
        all_plates.update(ths_concept_stocks.keys())
        all_plates.update(industry_map.keys())

        results = []
        for plate in all_plates:
            # 过滤无意义板块
            if plate in ("ST股", "科创板", "北交所", "创业板", "新股"):
                continue
            if plate.startswith("ST") or len(plate) < 2:
                continue

            score = calc_sector_heat_score(
                plate, plates_dict, industry_map,
                dict(ths_concept_stocks), dict(news_sectors),
                theme_dates, hot_keywords
            )
            if score["total"] > 0:
                # 阶段判定
                total = score["total"]
                s1 = score["scores"]["涨停活跃"][0]
                s2 = score["scores"]["资金认可"][0]
                if total >= 60 and s1 >= 20:
                    phase = "爆发期"
                elif total >= 40 and s1 >= 10:
                    phase = "启动期"
                elif total < 20:
                    phase = "退潮期"
                else:
                    phase = "潜伏期"
                score["phase"] = phase
                results.append(score)

        # 按总分降序排序
        results.sort(key=lambda x: x["total"], reverse=True)
        return results[:top_n]

    except Exception as e:
        log.error(f"get_sector_rotation_top failed: {e}")
        return []
