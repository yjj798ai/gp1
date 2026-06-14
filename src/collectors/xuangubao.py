# -*- coding: utf-8 -*-
"""
选股宝涨停池/跌停池/强势股 + 新闻快讯采集器

数据源:
  flash-api: https://flash-api.xuangubao.com.cn/api/pool/detail?pool_name=xxx
  baoer-api: https://baoer-api.xuangubao.com.cn/api/v6/message/newsflash

功能:
  fetch_pool(pool_name)        → 获取指定池子数据
  fetch_newsflash()             → 获取新闻快讯（需token）
  extract_related_plates(stocks) → 从涨停池提取关联板块热度
  update_sector_hot_tags(plates) → 用板块热度更新 sector_snapshot.hot_tag
  get_stock_reason(code)       → 获取个股涨停原因
  get_stock_news(code)         → 获取个股相关新闻
  update_all()                 → 全量采集+更新hot_tag+缓存新闻
"""

import requests
import json
import sqlite3
import logging
import time
from datetime import datetime

log = logging.getLogger('xuangubao')

API_URL = "https://flash-api.xuangubao.com.cn/api/pool/detail"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

_DB_PATH = "E:/AI/gp1/a13/hot_rank.db"

# 池子配置
POOLS = {
    "limit_up": "涨停池",
    "limit_down": "跌停池",
    "strong_stock": "强势股",
}


def fetch_pool(pool_name: str) -> list:
    """获取选股宝指定池子数据

    返回: list[dict]，每只股票42个字段
    """
    try:
        r = requests.get(
            f"{API_URL}?pool_name={pool_name}",
            headers=HEADERS, timeout=10
        )
        data = r.json()
        return data.get("data", []) or []
    except Exception as e:
        log.error(f"fetch_pool({pool_name}) failed: {e}")
        return []


def extract_related_plates(stocks: list) -> dict:
    """从涨停池提取关联板块 → 用于更新 hot_tag

    统计每个关联板块在涨停股中出现的次数

    返回: {"国产芯片": 13, "半导体": 5, "人工智能": 3, ...}
    """
    plates = {}
    for s in stocks:
        reason = s.get("surge_reason") or {}
        related = reason.get("related_plates") or []
        for rp in related:
            name = rp.get("plate_name", "")
            if name:
                plates[name] = plates.get(name, 0) + 1
    return plates


def update_sector_hot_tags(plates: dict):
    """用选股宝板块热度更新 sector_snapshot.hot_tag

    规则:
      出现 ≥5次 → "爆发"
      出现 ≥3次 → "启动"
      出现 ≥1次 → "关注"（可选）
    """
    if not plates:
        return

    conn = sqlite3.connect(_DB_PATH, timeout=5)

    # 获取 sector_snapshot 最新日期
    today_row = conn.execute('SELECT MAX(date) FROM sector_snapshot').fetchone()
    if not today_row or not today_row[0]:
        conn.close()
        return
    today = today_row[0]

    updated = 0
    for name, count in sorted(plates.items(), key=lambda x: -x[1]):
        if count >= 5:
            tag = "爆发"
        elif count >= 3:
            tag = "启动"
        else:
            continue

        # 尝试匹配 sector_snapshot 中的板块名（模糊匹配）
        matched = conn.execute(
            'SELECT name FROM sector_snapshot WHERE date=? AND name LIKE ?',
            (today, f'%{name}%')
        ).fetchall()

        for m in matched:
            conn.execute(
                'UPDATE sector_snapshot SET hot_tag=? WHERE date=? AND name=?',
                (tag, today, m[0])
            )
            updated += 1

        # 也尝试精确匹配
        exact = conn.execute(
            'SELECT name FROM sector_snapshot WHERE date=? AND name=?',
            (today, name)
        ).fetchall()
        for m in exact:
            conn.execute(
                'UPDATE sector_snapshot SET hot_tag=? WHERE date=? AND name=?',
                (tag, today, m[0])
            )
            updated += 1

    conn.commit()
    conn.close()
    log.info(f"hot_tag更新: {updated}个板块")
    return updated


def get_stock_reason(code: str, stocks: list = None) -> str:
    """获取个股涨停原因

    参数:
      code: 股票代码（如 '000001' 或 '000001.SZ'）
      stocks: 可选，已采集的涨停池数据（避免重复请求）

    返回: 涨停原因文字，如"全球太阳能电池主要供应商"
    """
    if not stocks:
        stocks = fetch_pool("limit_up")

    # 标准化代码
    code_clean = code.replace('.SZ', '').replace('.SS', '').replace('.SH', '')

    for s in stocks:
        symbol = s.get("symbol", "")
        s_clean = symbol.replace('.SZ', '').replace('.SS', '').replace('.SH', '')
        if s_clean == code_clean:
            reason = s.get("surge_reason") or {}
            return reason.get("stock_reason", "")

    return ""


def get_stock_tags(code: str, stocks: list = None) -> dict:
    """获取个股标签（连板/封板强度等）

    返回: {"limit_up_days": 2, "break_times": 0, "buy_lock": 0.05, ...}
    """
    if not stocks:
        stocks = fetch_pool("limit_up")

    code_clean = code.replace('.SZ', '').replace('.SS', '').replace('.SH', '')

    for s in stocks:
        symbol = s.get("symbol", "")
        s_clean = symbol.replace('.SZ', '').replace('.SS', '').replace('.SH', '')
        if s_clean == code_clean:
            return {
                "limit_up_days": s.get("limit_up_days", 0),
                "break_times": s.get("break_limit_up_times", 0),
                "buy_lock": s.get("buy_lock_volume_ratio", 0),
                "turnover": s.get("turnover_ratio", 0),
                "volume_bias": s.get("volume_bias_ratio", 0),
            }

    return {}


# ═══════════════════════════════════════════════════════════
# 涨停原因 → 概念标签提取
# ═══════════════════════════════════════════════════════════

# 关键词 → 概念标签映射表
_REASON_CONCEPT_MAP = {
    # 国企/国资
    "国资委": "国企改革", "央企": "国企改革", "国企": "国企改革",
    "国资": "国企改革", "地方国资": "国企改革", "省属国资": "国企改革",
    "实控人": "国企改革",
    # 地域
    "深圳": "深圳特区", "上海": "上海自贸", "北京": "北京板块",
    "西安": "西安板块", "长春": "东北振兴", "吉林": "东北振兴",
    "广东": "粤港澳大湾区", "海南": "海南自贸港", "成渝": "成渝特区",
    "浙江": "浙江板块", "江苏": "江苏板块", "山东": "山东板块",
    "福建": "海峡两岸", "安徽": "安徽板块", "四川": "四川板块",
    "湖南": "湖南板块", "湖北": "湖北板块", "河南": "河南板块",
    # 地产相关
    "房地产": "房地产", "地产开发": "房地产", "住宅开发": "房地产",
    "物业": "物业管理", "城建": "房地产", "置业": "房地产",
    "旧改": "城市更新", "城中村": "城市更新", "棚改": "城市更新",
    "保障房": "保障房", "租赁住房": "保障房",
    # 科技
    "芯片": "芯片概念", "半导体": "芯片概念", "集成电路": "芯片概念",
    "硅片": "芯片概念", "晶圆": "芯片概念", "封装": "芯片概念",
    "光刻": "光刻机", "靶材": "芯片概念",
    "AI": "人工智能", "人工智能": "人工智能", "大模型": "人工智能",
    "算力": "算力概念", "智算": "算力概念",
    "机器人": "机器人", "人形机器人": "机器人", "机械臂": "机器人",
    "自动驾驶": "自动驾驶", "智能驾驶": "自动驾驶",
    "鸿蒙": "鸿蒙概念", "华为": "华为概念",
    "光伏": "光伏", "太阳能": "光伏", "储能": "储能",
    "锂电": "锂电池", "锂离子": "锂电池", "固态电池": "固态电池",
    "碳酸锂": "锂电池",
    "PCB": "PCB概念", "覆铜板": "PCB概念", "玻纤布": "PCB概念",
    "电子树脂": "PCB概念", "层压": "PCB概念",
    "光模块": "光模块", "光通信": "光通信", "光纤": "光通信",
    "CPO": "共封装光学", "磷化铟": "光通信",
    "MLCC": "MLCC", "电容": "被动元件", "电阻": "被动元件",
    "液冷": "液冷", "温控": "液冷", "IDC": "数据中心",
    "数据中心": "数据中心", "云计算": "云计算",
    # 医药
    "医药": "医药", "创新药": "创新药", "中药": "中药",
    "CRO": "CRO", "医疗器械": "医疗器械", "生物制药": "生物制药",
    "基因": "基因编辑", "CXO": "CRO",
    # 新能源车
    "新能源车": "新能源汽车", "新能源汽车": "新能源汽车",
    "充电桩": "充电桩", "动力电池": "动力电池",
    "氢能": "氢能源", "燃料电池": "氢能源",
    # 航天/军工
    "航天": "商业航天", "火箭": "商业航天", "卫星": "卫星互联网",
    "军工": "军工", "兵装": "军工", "航空": "军工",
    "低空": "低空经济", "飞行汽车": "低空经济", "eVTOL": "低空经济",
    # 化工
    "环氧丙烷": "环氧丙烷", "环氧树脂": "环氧树脂",
    "氟化工": "氟化工", "六氟化硫": "氟化工", "六氟化钨": "氟化工",
    # 消费
    "消费": "大消费", "白酒": "白酒", "食品": "食品饮料",
    "家电": "家电", "零售": "新零售", "电商": "电商概念",
    "预制菜": "预制菜", "烘焙": "大消费",
    # 资产运作
    "重组": "资产重组", "并购": "并购重组", "收购": "并购重组",
    "借壳": "资产重组", "注入": "资产重组",
    "参股": "参股券商", "券商": "券商概念", "银行": "银行概念",
    # 其他
    "煤炭": "煤炭", "水泥": "水泥建材", "建材": "水泥建材",
    "钢铁": "钢铁", "有色": "有色金属", "稀土": "稀土",
    "天然气": "天然气", "氢气": "氢能源", "氧气": "工业气体",
    "PEEK": "PEEK材料", "碳纤维": "碳纤维",
    "分红": "高股息", "回购": "股份回购",
}


def extract_concepts_from_reason(reason_text: str) -> list:
    """从涨停原因文本中提取概念标签

    参数:
      reason_text: 涨停原因文本（如"吉林长春国资委旗下，主营水泥建材、医药、地产等"）

    返回: ["国企改革", "东北振兴", "水泥建材", "医药", "房地产"]
    """
    if not reason_text:
        return []

    found = []
    seen = set()

    # 按关键词长度降序匹配（优先匹配更长的词）
    sorted_keywords = sorted(_REASON_CONCEPT_MAP.keys(), key=len, reverse=True)

    for keyword in sorted_keywords:
        if keyword in reason_text:
            concept = _REASON_CONCEPT_MAP[keyword]
            if concept not in seen:
                found.append(concept)
                seen.add(concept)

    return found


def sync_limit_up_concepts():
    """将涨停原因提取的概念标签同步到stock_concepts表

    覆盖全部75只涨停股（包括ths_hot_stocks没覆盖到的）
    """
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    today = datetime.now().strftime("%Y-%m-%d")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_concepts (
            code TEXT, concept TEXT,
            PRIMARY KEY (code, concept)
        )
    """)

    rows = conn.execute(
        'SELECT code, reason FROM limit_up_cache WHERE date=?',
        (today,)
    ).fetchall()

    synced = 0
    for code, reason in rows:
        concepts = extract_concepts_from_reason(reason)
        for c in concepts:
            conn.execute(
                'INSERT OR IGNORE INTO stock_concepts (code, concept) VALUES (?, ?)',
                (code, c)
            )
            synced += 1

    conn.commit()
    conn.close()
    return synced


def update_all() -> dict:
    """全量采集所有池子 + 更新 hot_tag"""
    stats = {}

    for pool_name, pool_label in POOLS.items():
        stocks = fetch_pool(pool_name)
        stats[pool_label] = len(stocks)
        log.info(f"{pool_label}: {len(stocks)}只")

        if pool_name == "limit_up" and stocks:
            # 提取关联板块热度
            plates = extract_related_plates(stocks)
            log.info(f"关联板块: {len(plates)}个")

            # 更新 hot_tag
            update_sector_hot_tags(plates)

            # 缓存涨停池数据（供其他模块查询）
            _cache_limit_up(stocks)

        time.sleep(0.5)

    # ── 新闻快讯采集 ──
    log.info("新闻快讯采集...")
    messages = fetch_newsflash(limit=50)
    if messages:
        _cache_newsflash(messages)
        _update_news_sentiment()
        stats["新闻快讯"] = len(messages)

        # 热词提取（三合一：bkj_infos + jieba分词）
        hot_kw = extract_hot_keywords(messages, top_n=20)
        if hot_kw:
            _cache_hot_keywords(hot_kw)
            stats["热词TOP5"] = hot_kw[:5]
            log.info(f"今日热词: {hot_kw[:5]}")

    return stats


def _cache_limit_up(stocks: list):
    """缓存涨停池数据到数据库（供推荐理由查询）"""
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    today = datetime.now().strftime("%Y-%m-%d")

    # 创建缓存表（如果不存在）
    conn.execute('''
        CREATE TABLE IF NOT EXISTS limit_up_cache (
            date TEXT,
            code TEXT,
            name TEXT,
            reason TEXT,
            limit_days INTEGER,
            break_times INTEGER,
            buy_lock REAL,
            turnover REAL,
            volume_bias REAL,
            PRIMARY KEY (date, code)
        )
    ''')

    # 清除今日旧数据
    conn.execute('DELETE FROM limit_up_cache WHERE date=?', (today,))

    for s in stocks:
        symbol = s.get("symbol", "")
        code = symbol.replace('.SZ', '').replace('.SS', '').replace('.SH', '')
        name = s.get("stock_chi_name", "")
        reason_obj = s.get("surge_reason") or {}
        reason = reason_obj.get("stock_reason", "")

        conn.execute('''
            INSERT OR REPLACE INTO limit_up_cache
            (date, code, name, reason, limit_days, break_times, buy_lock, turnover, volume_bias)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            today, code, name, reason,
            s.get("limit_up_days", 0),
            s.get("break_limit_up_times", 0),
            s.get("buy_lock_volume_ratio", 0),
            s.get("turnover_ratio", 0),
            s.get("volume_bias_ratio", 0),
        ))

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════
# 新闻快讯
# ═══════════════════════════════════════════════════════════

_NEWSFLASH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://xuangutong.com.cn",
    "Referer": "https://xuangutong.com.cn/live",
    "x-ivanka-token": "",
    "x-appgo-platform": "device=pc",
    "x-track-info": '{"AppId":"com.xuangutong.web","AppVersion":"1.0.0"}',
}

def _get_newsflash_token() -> str:
    """从config读取选股通token"""
    try:
        from src.utils.cookie_manager import get_cookie_value
        token = get_cookie_value("xuangutong_token")
        if token:
            return token.strip()
    except:
        pass
    return ""


def fetch_newsflash(limit: int = 50) -> list:
    """获取选股通新闻快讯（zaozhidao）

    返回: list[dict]，每条新闻含 title/stocks/bkj_infos/created_at
    """
    try:
        token = _get_newsflash_token()
        if not token:
            log.warning("选股通token未配置，请在侧边栏→Cookie管理→选股通 填入token")
            return []
        headers = dict(_NEWSFLASH_HEADERS)
        headers["x-ivanka-token"] = token

        # 先试 zaozhidao/contents（用户确认的端点）
        r = requests.get(
            "https://baoer-api.xuangubao.com.cn/api/v6/provision/zaozhidao/contents",
            params={"category_ids": "", "limit": str(limit), "sources": "message"},
            headers=headers,
            timeout=10,
        )
        d = r.json()
        if d.get("code") == 20000:
            items = d.get("data", {}).get("items", [])
            if items:
                return items

        # 备用：走 newsflash 端点
        r2 = requests.get(
            "https://baoer-api.xuangubao.com.cn/api/v6/message/newsflash",
            params={"limit": str(limit), "subj_ids": "9,10,723,35,469,821", "platform": "pcweb"},
            headers=headers,
            timeout=10,
        )
        d2 = r2.json()
        if d2.get("code") == 20000:
            return d2.get("data", {}).get("messages", [])
        
        log.warning(f"newsflash API code={d2.get('code')}")
        return []
    except Exception as e:
        log.error(f"fetch_newsflash failed: {e}")
        return []

def _cache_newsflash(messages: list):
    """缓存新闻快讯到数据库（只缓存有股票关联的新闻）"""
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    today = datetime.now().strftime("%Y-%m-%d")

    # 删除24小时前的旧新闻（热词只保留新鲜的）
    conn.execute("DELETE FROM news_cache WHERE date < ?",
                 (datetime.now().strftime("%Y-%m-%d"),))
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS news_cache (
            date TEXT,
            msg_id INTEGER,
            title TEXT,
            stock_codes TEXT,
            sector_names TEXT,
            created_at INTEGER,
            PRIMARY KEY (date, msg_id)
        )
    ''')

    conn.execute('DELETE FROM news_cache WHERE date=?', (today,))

    cached = 0
    for msg in messages:
        stocks = msg.get("stocks") or msg.get("all_stocks") or []
        # 从zaozhidao格式提取: message.stocks
        if not stocks and 'message' in msg:
            stocks = msg['message'].get('stocks', [])

        codes = []
        for s in stocks:
            if isinstance(s, dict):
                symbol = s.get("symbol", "") or s.get("code", "") or ""
                code = symbol.replace('.SZ', '').replace('.SS', '').replace('.SH', '')
            elif isinstance(s, (list, tuple)) and len(s) >= 2:
                code = str(s[0]) if s[0] else ""
            else:
                continue
            if code:
                codes.append(code)

        # 关键词→概念匹配（补股票和板块信息）
        title = msg.get("title", "") or msg.get("message", {}).get("title", "")
        KEYWORD_CONCEPT_MAP = {
            "钼": "小金属概念", "钨": "小金属概念", "稀土": "稀土永磁",
            "锂": "锂电池", "钴": "小金属概念", "镍": "小金属概念",
            "有色": "有色金属", "黄金": "黄金概念",
            "芯片": "芯片概念", "半导体": "半导体", "存储": "存储芯片",
            "AI": "人工智能", "算力": "算力租赁", "边缘算力": "算力租赁",
            "边缘计算": "算力租赁", "大模型": "人工智能",
            "机器人": "人形机器人", "光纤": "光纤概念", "光通信": "光纤概念",
            "光伏": "光伏", "储能": "储能", "固态电池": "固态电池",
            "创新药": "创新药", "医药": "医药",
            "军工": "军工", "航天": "军工",
            "PCB": "PCB概念", "先进封装": "先进封装",
            "消费": "大消费", "汽车": "新能源汽车",
            "核电": "核电", "氢能": "氢能源", "六氟化钨": "氟化工",
            "工业气体": "基础化工", "HBM": "存储芯片",
            "鸿蒙": "华为鸿蒙", "数据中心": "算力租赁",
            "太空算力": "算力租赁", "AIPC": "消费电子概念",
            "AI安全": "人工智能", "AI医疗": "创新药",
        }
        
        matched_sectors = set()
        for kw, concept in KEYWORD_CONCEPT_MAP.items():
            if kw in title:
                matched_sectors.add(concept)
                # 查该概念下的股票
                code_rows = conn.execute('''
                    SELECT code FROM stock_concepts WHERE concept LIKE ? LIMIT 20
                ''', (f'%{concept}%',)).fetchall()
                for cr in code_rows:
                    c = cr[0]
                    if c and c not in codes:
                        codes.append(c)

        if not codes and not matched_sectors:
            continue

        bkj = msg.get("bkj_infos") or []
        sector_names = [b.get("name", "") for b in bkj if b.get("name")]
        # 加入关键词匹配的板块
        sector_names.extend(matched_sectors)

        conn.execute('''
            INSERT OR REPLACE INTO news_cache
            (date, msg_id, title, stock_codes, sector_names, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            today,
            msg.get("id", 0) or msg.get("content_id", 0),
            title[:200],
            ",".join(codes),
            ",".join(sector_names),
            msg.get("created_at", 0),
        ))
        cached += 1

    conn.commit()
    conn.close()
    log.info(f"新闻缓存: {cached}条有股票关联")
    return cached


def get_stock_news(code: str) -> list:
    """获取个股相关新闻标题

    返回: ['新闻标题1', '新闻标题2', ...]
    """
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            'SELECT title FROM news_cache WHERE date=? AND stock_codes LIKE ?',
            (today, f'%{code}%')
        ).fetchall()
        conn.close()
        return [r[0] for r in rows[:3]]
    except Exception:
        return []


def get_news_concept_heat() -> dict:
    """分析今日新闻中概念的热度频率
    
    返回: {"小金属概念": 3, "算力租赁": 4, "半导体": 2, ...}
    次数越多 = 越热
    """
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 从 sector_names 字段统计概念出现次数
        concept_counts = {}
        rows = conn.execute(
            "SELECT sector_names FROM news_cache WHERE date=?",
            (today,)
        ).fetchall()
        conn.close()
        
        for r in rows:
            for c in (r[0] or "").split(","):
                c = c.strip()
                if c and len(c) >= 2:
                    concept_counts[c] = concept_counts.get(c, 0) + 1
        
        return dict(sorted(concept_counts.items(), key=lambda x: -x[1]))
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════
# 新闻情绪分类 + 热词提取
# ═══════════════════════════════════════════════════════════

POSITIVE_KEYWORDS = {
    "中标", "签约", "增长", "突破", "投产", "量产", "交付",
    "获批", "合作", "投资", "增持", "回购", "分红", "扭亏",
    "新高", "龙头", "领跑", "市占率提升", "订单", "扩产",
    "超预期", "利好", "大涨", "涨停", "净利", "营收",
    "创新高", "反弹", "复苏", "升级", "获批", "获奖",
}

NEGATIVE_KEYWORDS = {
    "亏损", "减持", "诉讼", "调查", "处罚", "退市", "st",
    "下调", "预警", "风险", "违约", "破产", "欠款", "逾期",
    "召回", "整改", "停工", "裁员", "降薪", "暴跌",
    "跌停", "下滑", "回落", "收紧", "制裁", "违规",
    "减持", "终止", "失败", "下跌", "亏损", "利空",
}

# 热词提取用的停用词
STOP_WORDS = {
    # 基础停用词
    "的", "了", "在", "是", "和", "与", "为", "对", "等", "将",
    "到", "被", "把", "从", "上", "下", "中", "不", "有", "也",
    "公司", "股份", "集团", "有限", "表示", "公告", "关于",
    "万元", "亿元", "美元", "万股", "占比", "同比", "环比",
    "预计", "本次", "相关", "该", "其", "已", "将", "还",
    "记者", "获悉", "据", "称", "指出", "认为", "透露",
    # 宏观数据噪音词
    "万桶", "前值", "预期", "公布", "数据", "日当周",
    "变动", "初值", "终值", "修正", "年率", "月率",
    "季调", "未季调", "名义", "实际",
    # 无意义高频词
    "我们", "他们", "目前", "市场", "投资者", "分析师",
    "美国", "加拿大", "伊朗", "欧洲", "全球", "中国",
    "指数", "央行", "利率", "通胀", "统计局", "BLS", "EIA",
    "行长", "库存", "涨超", "跌幅", "涨幅", "涨跌",
    "涨至", "跌至", "报收", "收报", "收盘", "开盘",
    "成交额", "成交量", "换手", "振幅",
    # 常见无意义词
    "如果", "已经", "核心", "回应", "以来", "前一天",
    " secretary", "彭博", "提名", "经济", "战争",
    "燃油", "标普", "石油",
}


def classify_news_sentiment(title: str, summary: str = "") -> str:
    """新闻情绪分类: positive / negative / neutral"""
    text = f"{title} {summary}".lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def extract_hot_keywords(messages: list, top_n: int = 20) -> list:
    """从新闻快讯中提取热词（三合一）

    ① bkj_infos提取板块热词（权重3，因为是编辑标注的精准板块）
    ② jieba分词提取标题热词（权重1）
    ③ 合并去重 → 按综合得分排序

    返回: [("芯片", 15), ("半导体", 12), ...]
    """
    import re
    from collections import Counter
    import jieba

    counter = Counter()

    # ── ① bkj_infos板块热词（权重3）──
    for msg in messages:
        bkj = msg.get("bkj_infos") or []
        for b in bkj:
            name = b.get("name", "").strip()
            if name and len(name) >= 2:
                counter[name] += 3  # 板块名权重高

    # ── ② jieba分词标题热词（权重1）──
    # 金融领域自定义词
    finance_words = {
        "涨停", "跌停", "封板", "连板", "打板", "炸板", "地天板",
        "龙头", "妖股", "牛市", "熊市", "抄底", "逃顶",
        "北向资金", "融资融券", "主力资金", "机构席位",
        "市盈率", "市净率", "换手率", "量比",
        "光模块", "PCB", "MLCC", "CPO", "算力", "储能",
        "固态电池", "锂电", "光伏", "风电", "氢能",
        "人工智能", "大模型", "机器人", "自动驾驶", "脑机接口",
        "半导体", "芯片", "晶圆", "封装", "光刻",
        "商业航天", "卫星互联网", "低空经济", "飞行汽车",
        "鸿蒙", "华为", "苹果", "英伟达", "特斯拉",
        "稀土", "碳酸锂", "铜箔", "铝箔",
        "中药", "创新药", "CRO", "医疗器械",
        "数据中心", "液冷", "温控", "服务器",
        "数字货币", "区块链", "Web3",
        "国企改革", "中特估", "一带一路",
    }
    for word in finance_words:
        jieba.add_word(word)

    for msg in messages:
        title = msg.get("title", "")
        # jieba精确模式分词
        segs = jieba.cut(title)
        for seg in segs:
            seg = seg.strip()
            if len(seg) < 2:
                continue
            if seg in STOP_WORDS:
                continue
            # 过滤纯数字和英文单字母
            if re.match(r'^[\d\.\%]+$', seg):
                continue
            # 过滤纯短英文（1-2字母无意义）
            if re.match(r'^[a-zA-Z]{1,2}$', seg):
                continue
            counter[seg] += 1

    return counter.most_common(top_n)


def get_today_hot_keywords() -> list:
    """获取今日热词（从news_hot_keywords表读取）

    返回: [("芯片", 15), ("半导体", 12), ...]
    """
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            'SELECT keyword, score FROM news_hot_keywords WHERE date=? ORDER BY score DESC LIMIT 20',
            (today,)
        ).fetchall()
        conn.close()
        return [(r[0], r[1]) for r in rows]
    except Exception:
        # 降级：从news_cache实时提取
        return _extract_keywords_from_cache()


def _extract_keywords_from_cache() -> list:
    """降级方案：从news_cache标题实时提取热词"""
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            'SELECT title FROM news_cache WHERE date=?',
            (today,)
        ).fetchall()
        conn.close()

        if not rows:
            return []

        import re
        from collections import Counter
        import jieba

        all_text = " ".join(r[0] for r in rows)
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', all_text)
        words = [w for w in words if w not in STOP_WORDS and len(w) >= 2]
        counter = Counter(words)
        return counter.most_common(20)
    except Exception:
        return []


def _cache_hot_keywords(keywords: list):
    """缓存热词到 news_hot_keywords 表

    参数:
      keywords: [("芯片", 15), ("半导体", 12), ...]
    """
    if not keywords:
        return

    conn = sqlite3.connect(_DB_PATH, timeout=5)
    today = datetime.now().strftime("%Y-%m-%d")

    conn.execute('''
        CREATE TABLE IF NOT EXISTS news_hot_keywords (
            date TEXT,
            keyword TEXT,
            score INTEGER,
            PRIMARY KEY (date, keyword)
        )
    ''')

    conn.execute('DELETE FROM news_hot_keywords WHERE date=?', (today,))

    for kw, score in keywords:
        conn.execute(
            'INSERT OR REPLACE INTO news_hot_keywords (date, keyword, score) VALUES (?, ?, ?)',
            (today, kw, score)
        )

    conn.commit()
    conn.close()
    log.info(f"热词缓存: {len(keywords)}条")


def _update_news_sentiment():
    """更新news_cache中的情绪分类"""
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        today = datetime.now().strftime("%Y-%m-%d")

        # 检查是否有sentiment列
        cols = [r[1] for r in conn.execute('PRAGMA table_info(news_cache)').fetchall()]
        if 'sentiment' not in cols:
            conn.execute('ALTER TABLE news_cache ADD COLUMN sentiment TEXT DEFAULT "neutral"')

        rows = conn.execute(
            'SELECT msg_id, title FROM news_cache WHERE date=? AND (sentiment IS NULL OR sentiment="neutral")',
            (today,)
        ).fetchall()

        updated = 0
        for msg_id, title in rows:
            sentiment = classify_news_sentiment(title)
            conn.execute(
                'UPDATE news_cache SET sentiment=? WHERE date=? AND msg_id=?',
                (sentiment, today, msg_id)
            )
            updated += 1

        conn.commit()
        conn.close()
        if updated > 0:
            log.info(f"新闻情绪分类: {updated}条")
    except Exception as e:
        log.debug(f"_update_news_sentiment failed: {e}")


# ═══════════════════════════════════════════════════════════
# 题材挖掘（优品科技 upchina.com）
# ═══════════════════════════════════════════════════════════

_THEME_API = "https://prx.upchina.com/json/specialTheme/getTSDataNewThemeByDate"
_STOCK_DETAIL_API = "https://gateway.upchina.com/json/stockextweb/stockExtDetail"

_THEME_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def fetch_themes(count: int = 50) -> list:
    """获取题材挖掘列表

    数据源: prx.upchina.com (优品科技)
    无需认证，直接POST即可

    返回: list[dict]，每个题材含:
      sPlateName: 题材名称（如"800V电源"）
      sPlateCode: 题材代码（如"911698"）
      effectiveTime: 生效日期（如20260610）
      parentName: 层级标签（如"AI算力|英伟达供应商|800V电源"）
      driveLogic: 投资逻辑（100-300字专业分析）
      iConsTotal: 关联股票数量
      iLevel: 题材级别
    """
    try:
        r = requests.post(
            _THEME_API,
            json={"stReq": {"uiStart": 0, "uiCount": count}},
            headers=_THEME_HEADERS,
            timeout=15,
        )
        data = r.json()
        return data.get("stRsp", {}).get("vThemeData") or []
    except Exception as e:
        log.error(f"fetch_themes failed: {e}")
        return []


def fetch_theme_stocks(plate_code: str, size: int = 50) -> list:
    """获取题材关联的股票详情

    参数:
      plate_code: 题材代码（如"911698"）

    返回: list[dict]，每只股票含:
      code: 股票代码
      name: 股票名称
      m1['4']: 涨跌幅(%)
      m1['3']: 市盈率PE
      m1['5']: 市净率PB
      m1['53']: 5日涨跌(%)
      m1['56']: 10日涨跌(%)
    """
    try:
        payload = {
            "stReq": {
                "stHeader": {"sSource": "题材挖掘-common/service/clue/getStockExtDetail"},
                "lDate": 0, "iType": 6, "iId": 0, "iExt": 0,
                "sExt": plate_code,
                "vFilterType": [], "vStock": [],
                "eColumn": 4, "eSort": 2,
                "iStart": 0, "iSize": size,
                "bFromCache": True, "stFrom": {},
                "vBitmap": [28, 64, 0, 0, 0, 0, 68, 254, 248, 32, 0, 0, 0, 48],
                "mapIncFlag": {}, "mapReq": {},
                "bDetail": False, "iReqType": 1,
            }
        }
        r = requests.post(
            _STOCK_DETAIL_API,
            json=payload,
            headers=_THEME_HEADERS,
            timeout=15,
        )
        data = r.json()
        return data.get("stRsp", {}).get("vDataSimple") or []
    except Exception as e:
        log.error(f"fetch_theme_stocks({plate_code}) failed: {e}")
        return []


def _cache_themes(themes: list):
    """缓存题材数据到数据库"""
    if not themes:
        return

    conn = sqlite3.connect(_DB_PATH, timeout=5)
    today = datetime.now().strftime("%Y-%m-%d")

    conn.execute('''
        CREATE TABLE IF NOT EXISTS theme_cache (
            date TEXT,
            code TEXT,
            name TEXT,
            tags TEXT,
            drive_logic TEXT,
            stock_count INTEGER,
            level INTEGER,
            effective_date TEXT,
            PRIMARY KEY (date, code)
        )
    ''')

    conn.execute('DELETE FROM theme_cache WHERE date=?', (today,))

    for t in themes:
        conn.execute('''
            INSERT OR REPLACE INTO theme_cache
            (date, code, name, tags, drive_logic, stock_count, level, effective_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            today,
            t.get("sPlateCode", ""),
            t.get("sPlateName", ""),
            t.get("parentName", ""),
            t.get("driveLogic", "")[:500],
            t.get("iConsTotal", 0),
            t.get("iLevel", 0),
            str(t.get("effectiveTime", "")),
        ))

    conn.commit()
    conn.close()
    log.info(f"题材缓存: {len(themes)}个")


def _cache_theme_stocks(themes: list):
    """采集并缓存题材关联股票（只取最近5个题材的股票，避免过多请求）"""
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    today = datetime.now().strftime("%Y-%m-%d")

    conn.execute('''
        CREATE TABLE IF NOT EXISTS theme_stock_cache (
            date TEXT,
            theme_code TEXT,
            theme_name TEXT,
            stock_code TEXT,
            stock_name TEXT,
            change_pct REAL,
            pe REAL,
            pb REAL,
            chg_5d REAL,
            chg_10d REAL,
            PRIMARY KEY (date, theme_code, stock_code)
        )
    ''')

    conn.execute('DELETE FROM theme_stock_cache WHERE date=?', (today,))

    # 只取最近5个题材的股票详情（避免50个API请求）
    recent_themes = themes[:5]
    total_stocks = 0

    for t in recent_themes:
        code = t.get("sPlateCode", "")
        name = t.get("sPlateName", "")
        if not code:
            continue

        stocks = fetch_theme_stocks(code, size=50)
        for s in stocks:
            m1 = s.get("m1") or {}
            conn.execute('''
                INSERT OR REPLACE INTO theme_stock_cache
                (date, theme_code, theme_name, stock_code, stock_name,
                 change_pct, pe, pb, chg_5d, chg_10d)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, code, name,
                s.get("code", ""),
                s.get("name", ""),
                m1.get("4", 0),
                m1.get("3", 0),
                m1.get("5", 0),
                m1.get("53", 0),
                m1.get("56", 0),
            ))
            total_stocks += 1

        time.sleep(0.3)  # 礼貌延迟

    conn.commit()
    conn.close()
    log.info(f"题材股票缓存: {total_stocks}条（{len(recent_themes)}个题材）")


def get_stock_themes(code: str) -> list:
    """获取个股关联的题材（含投资逻辑）

    参数:
      code: 股票代码（如'600673'）

    返回: [
        {"name": "800V电源", "tags": "AI算力|英伟达供应商|800V电源",
         "logic": "NVDA在GTC...", "stock_count": 8},
        ...
    ]
    """
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        today = datetime.now().strftime("%Y-%m-%d")

        # 从 theme_stock_cache 查找关联题材
        rows = conn.execute(
            '''SELECT DISTINCT t.code, t.name, t.tags, t.drive_logic, t.stock_count
               FROM theme_cache t
               JOIN theme_stock_cache ts ON t.date=ts.date AND t.code=ts.theme_code
               WHERE t.date=? AND ts.stock_code=?
               ORDER BY t.stock_count DESC''',
            (today, code)
        ).fetchall()
        conn.close()

        return [
            {"name": r[1], "tags": r[2], "logic": r[3], "stock_count": r[4]}
            for r in rows[:3]  # 最多返回3个题材
        ]
    except Exception:
        return []


def update_themes() -> dict:
    """采集题材挖掘数据（题材列表 + 关联股票）

    返回: {"themes": 50, "theme_stocks": 42, "top_themes": [...]}
    """
    stats = {}

    # 1. 获取题材列表
    themes = fetch_themes(count=50)
    stats["themes"] = len(themes)
    log.info(f"题材挖掘: {len(themes)}个题材")

    if themes:
        # 2. 缓存题材
        _cache_themes(themes)

        # 3. 采集并缓存关联股票（最近5个题材）
        _cache_theme_stocks(themes)

        stats["top_themes"] = [
            {"name": t["sPlateName"], "stocks": t["iConsTotal"]}
            for t in themes[:5]
        ]

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    print('=' * 60)
    print('  选股宝涨停池采集器')
    print('=' * 60)

    stats = update_all()
    print(f'\n采集结果: {stats}')
