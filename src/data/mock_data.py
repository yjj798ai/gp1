"""
股神圣杯系统 - 模拟数据模块
用于前端开发阶段的假数据填充，后续替换为真实数据库查询
"""
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any

# ============================================================
# 基础配置
# ============================================================
INITIAL_CAPITAL = 2000.0
STOCK_PRICE_LIMIT = 20.0  # 筛选20元以下股票
MAX_POSITIONS = 5
MAX_POSITION_RATIO = 0.20  # 单只不超过20%

# 模拟板块列表
SECTORS = [
    {"code": "BK0477", "name": "人工智能", "phase": "启动期", "score": 4.2},
    {"code": "BK0478", "name": "新能源车", "phase": "爆发期", "score": 4.8},
    {"code": "BK0479", "name": "半导体", "phase": "启动期", "score": 3.9},
    {"code": "BK0480", "name": "医药生物", "phase": "潜伏期", "score": 2.1},
    {"code": "BK0481", "name": "白酒", "phase": "退潮期", "score": 1.8},
    {"code": "BK0482", "name": "军工", "phase": "启动期", "score": 3.5},
    {"code": "BK0483", "name": "光伏", "phase": "潜伏期", "score": 2.4},
    {"code": "BK0484", "name": "锂电池", "phase": "启动期", "score": 3.7},
    {"code": "BK0485", "name": "数字经济", "phase": "爆发期", "score": 4.5},
    {"code": "BK0486", "name": "机器人", "phase": "潜伏期", "score": 2.8},
    {"code": "BK0487", "name": "房地产", "phase": "退潮期", "score": 1.5},
    {"code": "BK0488", "name": "消费电子", "phase": "启动期", "score": 3.3},
]

# 模拟个股池（20元以下）
STOCKS = [
    {"code": "300001", "name": "特锐德", "sector": "BK0477", "price": 12.56},
    {"code": "300003", "name": "乐普医疗", "sector": "BK0480", "price": 8.92},
    {"code": "300014", "name": "亿纬锂能", "sector": "BK0484", "price": 18.45},
    {"code": "300015", "name": "爱尔眼科", "sector": "BK0480", "price": 15.23},
    {"code": "300033", "name": "同花顺", "sector": "BK0485", "price": 19.87},
    {"code": "300059", "name": "东方财富", "sector": "BK0485", "price": 16.34},
    {"code": "300124", "name": "汇川技术", "sector": "BK0482", "price": 17.56},
    {"code": "300142", "name": "沃森生物", "sector": "BK0480", "price": 11.78},
    {"code": "300223", "name": "北京君正", "sector": "BK0479", "price": 13.45},
    {"code": "300274", "name": "阳光电源", "sector": "BK0483", "price": 19.12},
    {"code": "300347", "name": "泰格医药", "sector": "BK0480", "price": 10.67},
    {"code": "300408", "name": "三环集团", "sector": "BK0479", "price": 14.89},
    {"code": "300413", "name": "芒果超媒", "sector": "BK0486", "price": 16.23},
    {"code": "300433", "name": "蓝思科技", "sector": "BK0488", "price": 12.34},
    {"code": "300454", "name": "深信服", "sector": "BK0477", "price": 18.90},
    {"code": "300457", "name": "赢合科技", "sector": "BK0484", "price": 11.56},
    {"code": "300496", "name": "中科创达", "sector": "BK0477", "price": 17.23},
    {"code": "300502", "name": "新易盛", "sector": "BK0479", "price": 15.67},
    {"code": "300628", "name": "亿联网络", "sector": "BK0488", "price": 19.45},
    {"code": "300750", "name": "宁德时代", "sector": "BK0484", "price": 19.98},
    {"code": "300760", "name": "迈瑞医疗", "sector": "BK0480", "price": 16.78},
    {"code": "300763", "name": "锦浪科技", "sector": "BK0483", "price": 13.90},
    {"code": "300769", "name": "德鲁伊", "sector": "BK0486", "price": 14.56},
    {"code": "300782", "name": "卓胜微", "sector": "BK0479", "price": 15.34},
    {"code": "300866", "name": "安克创新", "sector": "BK0488", "price": 18.12},
    {"code": "300869", "name": "康泰医学", "sector": "BK0480", "price": 9.87},
    {"code": "300888", "name": "稳健医疗", "sector": "BK0480", "price": 11.23},
    {"code": "300999", "name": "金龙鱼", "sector": "BK0481", "price": 12.45},
    {"code": "301039", "name": "中集车辆", "sector": "BK0478", "price": 10.89},
]


# ============================================================
# 数据生成函数
# ============================================================

def get_last_update_time() -> str:
    """获取上次更新时间"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def generate_recommendations() -> pd.DataFrame:
    """生成今日推荐股票列表 — 只取综合评分优秀的前10名"""
    # 从股票池中随机采样，生成评分后筛选优秀个股
    candidates = random.sample(STOCKS, k=min(20, len(STOCKS)))
    records = []
    for s in candidates:
        score = round(random.uniform(3.5, 5.0), 2)
        # 根据股票所属板块匹配概念关键词
        sector_name = next((sec["name"] for sec in SECTORS if sec["code"] == s["sector"]), "未知")
        concept_keywords = _get_concept_keywords(sector_name)
        records.append({
            "股票代码": s["code"],
            "股票名称": s["name"],
            "所属板块": sector_name,
            "关联概念": concept_keywords["concept"],
            "对应关键词": concept_keywords["keywords"],
            "当前价格": round(s["price"] * random.uniform(0.97, 1.03), 2),
            "综合评分": score,
            "推荐理由": random.choice([
                "均线密集度极高(CV<0.01)，技术面蓄势待发",
                "板块进入启动期，龙头股资金持续流入",
                "酿酒期检测信号强烈，多维共振",
                "资金面+技术面+消息面三维齐升",
                "板块轮动主线确认，个股评分领先",
                "概念资金连续3日流入，热度动量上升",
                "行业资金大幅净流入，龙头效应明显",
            ]),
        })
    df = pd.DataFrame(records)
    # 只取评分>=4.0的前10名
    df = df[df["综合评分"] >= 4.0].sort_values("综合评分", ascending=False).head(10).reset_index(drop=True)
    if df.empty:
        # 如果没有>=4.0的，取前10名
        df = pd.DataFrame(records).sort_values("综合评分", ascending=False).head(10).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "排名"
    return df


def _get_concept_keywords(sector_name: str) -> dict:
    """根据板块名称匹配关联概念和关键词"""
    concept_map = {
        "人工智能": {"concept": "AI应用、AIGC概念、ChatGPT概念", "keywords": "AI、大模型、智能"},
        "新能源车": {"concept": "锂电池、充电桩、智能驾驶", "keywords": "新能源、锂电、充电"},
        "半导体": {"concept": "芯片概念、国产替代、华为鲲鹏", "keywords": "芯片、半导体、国产"},
        "医药生物": {"concept": "创新药、医疗器械、CXO", "keywords": "医药、创新药、医疗"},
        "白酒": {"concept": "消费、白酒概念", "keywords": "白酒、消费、食品"},
        "军工": {"concept": "军工信息化、卫星互联网", "keywords": "军工、国防、卫星"},
        "光伏": {"concept": "光伏、碳中和、储能", "keywords": "光伏、储能、碳中和"},
        "锂电池": {"concept": "固态电池、储能、新能源", "keywords": "锂电、固态电池、储能"},
        "数字经济": {"concept": "数据要素、智慧城市、低空经济", "keywords": "数字经济、数据要素"},
        "机器人": {"concept": "人形机器人、机器视觉", "keywords": "机器人、人形、自动化"},
        "房地产": {"concept": "城中村改造、物业管理", "keywords": "地产、城中村、物业"},
        "消费电子": {"concept": "华为概念、消费电子", "keywords": "消费电子、华为、智能终端"},
    }
    return concept_map.get(sector_name, {"concept": "综合", "keywords": sector_name[:4]})


def generate_sector_rotation() -> pd.DataFrame:
    """生成板块轮动数据"""
    records = []
    for sec in SECTORS:
        records.append({
            "板块代码": sec["code"],
            "板块名称": sec["name"],
            "当前阶段": sec["phase"],
            "阶段评分": sec["score"],
            "涨停数": random.randint(0, 12),
            "资金净流入(亿)": round(random.uniform(-3.0, 8.0), 2),
            "3日累计流入(亿)": round(random.uniform(-5.0, 15.0), 2),
            "平均换手率(%)": round(random.uniform(1.5, 9.0), 2),
            "平均涨跌幅(%)": round(random.uniform(-3.0, 5.0), 2),
            "连续活跃天数": random.randint(0, 7),
            "是否主线": sec["score"] >= 4.0,
        })
    df = pd.DataFrame(records)
    df = df.sort_values("阶段评分", ascending=False).reset_index(drop=True)
    return df


def generate_sector_flow_direction() -> str:
    """生成板块流动方向文字说明"""
    now = datetime.now().strftime("%Y-%m-%d")
    exploding = [s["name"] for s in SECTORS if s["phase"] == "爆发期"]
    starting = [s["name"] for s in SECTORS if s["phase"] == "启动期"]
    retreating = [s["name"] for s in SECTORS if s["phase"] == "退潮期"]

    text = f"""## 板块流动方向分析 ({now})

### 当前主线方向
**爆发期板块：** {', '.join(exploding) if exploding else '无'}
资金正在集中流入以上板块，短期关注度高，为当前市场主线。

### 潜力启动方向
**启动期板块：** {', '.join(starting) if starting else '无'}
以上板块出现启动信号（涨停数增加+资金流入+连续活跃），可能成为下一阶段主线。

### 资金退出方向
**退潮期板块：** {', '.join(retreating) if retreating else '无'}
资金正在流出以上板块，短期应规避相关个股。

### 轮动预判
当前市场资金从【{retreating[0] if retreating else '消费'}】方向流向【{exploding[0] if exploding else '科技'}】方向，
建议重点关注启动期板块中的龙头个股，等待爆发期确认后加仓。
"""
    return text


def generate_factor_strategies() -> pd.DataFrame:
    """生成因子策略配置（含技术面形态因子 + 热度因子）"""
    factors = [
        # ── 技术面（33%）──
        {"维度": "技术面", "因子名称": "均线密集度因子", "权重": 0.10, "状态": "活跃",
         "说明": "CV=标准差/均值，CV<0.01评5.0，检测变盘前兆", "文件": "ma_density.py"},
        {"维度": "技术面", "因子名称": "MACD金叉因子", "权重": 0.08, "状态": "活跃",
         "说明": "DIF上穿DEA形成金叉评分，金叉+红柱放大评高分", "文件": "macd_cross.py"},
        {"维度": "技术面", "因子名称": "均线发散向上因子", "权重": 0.06, "状态": "活跃",
         "说明": "多头排列+均线发散角度评分，发散角度大+量能配合评高分", "文件": "ma_divergence.py"},
        {"维度": "技术面", "因子名称": "筹码集中度因子", "权重": 0.05, "状态": "活跃",
         "说明": "筹码密集在低位+集中度高评分，低位密集+单峰密集评高分", "文件": "chip_concentration.py"},
        {"维度": "技术面", "因子名称": "价格优势因子", "权重": 0.04, "状态": "活跃",
         "说明": "低价股优势评分，20元以下评高分，价格越低分越高", "文件": "price_advantage.py"},
        # ── 热度面（12%）── 从旧系统热度排名升级而来
        {"维度": "热度面", "因子名称": "热度值因子", "权重": 0.07, "状态": "活跃",
         "说明": "同花顺热度排行榜综合热度评分，热度越高分越高", "文件": "heat_value.py"},
        {"维度": "热度面", "因子名称": "热度动量因子", "权重": 0.05, "状态": "活跃",
         "说明": "近3日热度排名变化，排名持续上升评高分", "文件": "heat_momentum.py"},
        # ── 资金面（20%）──
        {"维度": "资金面", "因子名称": "资金流向因子", "权重": 0.10, "状态": "活跃",
         "说明": "主力资金净流入/流出评分，资金持续流入评高分", "文件": "main_capital.py"},
        {"维度": "资金面", "因子名称": "行业资金流向因子", "权重": 0.06, "状态": "活跃",
         "说明": "个股所属行业的3日资金净流入评分", "文件": "industry_fund.py"},
        {"维度": "资金面", "因子名称": "概念资金流入因子", "权重": 0.04, "状态": "活跃",
         "说明": "个股所属概念的3日资金净流入评分，概念资金持续流入评高分", "文件": "concept_fund.py"},
        # ── 板块面（15%）──
        {"维度": "板块面", "因子名称": "板块阶段因子", "权重": 0.09, "状态": "活跃",
         "说明": "板块所处轮动阶段评分，启动期/爆发期评高分", "文件": "sector_phase.py"},
        {"维度": "板块面", "因子名称": "酿酒期检测因子", "权重": 0.06, "状态": "活跃",
         "说明": "3信号加权(新词0.3+资金0.4+技术0.3)，检测爆发前蓄势", "文件": "brewing_detection.py"},
        # ── 概念面（10%）──
        {"维度": "概念面", "因子名称": "概念热度动量因子", "权重": 0.06, "状态": "活跃",
         "说明": "概念近3日热度排名变化，排名上升评高分", "文件": "concept_momentum.py"},
        {"维度": "概念面", "因子名称": "概念持续性因子", "权重": 0.04, "状态": "观察",
         "说明": "概念资金连续流入天数评分，3日以上连续流入评高分", "文件": "concept_persist.py"},
        # ── 消息面（5%）──
        {"维度": "消息面", "因子名称": "热词关联因子", "权重": 0.05, "状态": "活跃",
         "说明": "jieba分词+关键词匹配，新闻热度映射评分", "文件": "hot_topic.py"},
        # ── 市场面（5%）──
        {"维度": "市场面", "因子名称": "市场周期因子", "权重": 0.05, "状态": "活跃",
         "说明": "牛熊周期定位，调整整体策略倾向", "文件": "market_cycle.py"},
    ]
    return pd.DataFrame(factors)


def generate_evolution_log() -> pd.DataFrame:
    """生成进化日志（昨日推荐结果）"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    records = []
    for i in range(6):
        stock = random.choice(STOCKS)
        predicted_dir = random.choice(["up", "up", "down"])
        actual_change = round(random.uniform(-4.0, 5.0), 2)
        actual_dir = "up" if actual_change > 0.5 else ("down" if actual_change < -0.5 else "neutral")
        is_correct = predicted_dir == actual_dir
        records.append({
            "日期": yesterday,
            "股票代码": stock["code"],
            "股票名称": stock["name"],
            "预测方向": "上涨" if predicted_dir == "up" else "下跌",
            "预测评分": round(random.uniform(3.0, 5.0), 2),
            "实际涨跌幅(%)": actual_change,
            "实际方向": "上涨" if actual_dir == "up" else ("下跌" if actual_dir == "down" else "平盘"),
            "是否正确": "✅ 正确" if is_correct else "❌ 错误",
            "置信度": random.choice(["高", "中", "低"]),
        })
    return pd.DataFrame(records)


def generate_portfolio() -> Dict[str, Any]:
    """生成虚拟持仓数据"""
    positions = []
    available = INITIAL_CAPITAL
    selected = random.sample(STOCKS, k=min(4, len(STOCKS)))
    for s in selected:
        buy_price = round(s["price"] * random.uniform(0.95, 1.0), 2)
        shares = int(min(available * MAX_POSITION_RATIO, available) / buy_price)
        if shares <= 0:
            continue
        cost = buy_price * shares
        current_price = round(buy_price * random.uniform(0.96, 1.08), 2)
        market_value = current_price * shares
        pnl = market_value - cost
        pnl_pct = round((pnl / cost) * 100, 2) if cost > 0 else 0
        positions.append({
            "股票代码": s["code"],
            "股票名称": s["name"],
            "所属板块": next((sec["name"] for sec in SECTORS if sec["code"] == s["sector"]), "未知"),
            "买入价格": buy_price,
            "当前价格": current_price,
            "持有数量": shares,
            "成本": round(cost, 2),
            "市值": round(market_value, 2),
            "盈亏": round(pnl, 2),
            "盈亏比例(%)": pnl_pct,
            "持有天数": random.randint(1, 5),
        })
        available -= cost

    total_market_value = sum(p["市值"] for p in positions)
    total_cost = sum(p["成本"] for p in positions)
    total_pnl = total_market_value - total_cost
    cash = INITIAL_CAPITAL - total_cost
    net_value = cash + total_market_value
    return {
        "positions": pd.DataFrame(positions),
        "initial_capital": INITIAL_CAPITAL,
        "total_market_value": round(total_market_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round((total_pnl / total_cost) * 100, 2) if total_cost > 0 else 0,
        "cash": round(cash, 2),
        "net_value": round(net_value, 2),
        "return_pct": round(((net_value - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100, 2),
        "position_count": len(positions),
    }


def generate_net_value_curve() -> pd.DataFrame:
    """生成净值曲线数据（模拟30天）"""
    dates = [datetime.now() - timedelta(days=i) for i in range(30)]
    dates.reverse()
    nv = INITIAL_CAPITAL / 1000.0  # 从2.0开始
    benchmark_nv = 2.0
    records = []
    for d in dates:
        nv += random.uniform(-0.03, 0.04)
        benchmark_nv += random.uniform(-0.025, 0.03)
        records.append({
            "日期": d.strftime("%Y-%m-%d"),
            "策略净值": round(nv, 4),
            "基准净值(沪深300)": round(benchmark_nv, 4),
            "策略累计收益率(%)": round((nv - 2.0) / 2.0 * 100, 2),
            "基准累计收益率(%)": round((benchmark_nv - 2.0) / 2.0 * 100, 2),
        })
    return pd.DataFrame(records)


def generate_system_status() -> Dict[str, Any]:
    """生成系统运行状态"""
    return {
        "last_data_update": get_last_update_time(),
        "last_recommendation": get_last_update_time(),
        "last_backtest": get_last_update_time(),
        "data_status": {
            "日K线数据": {"status": "正常", "last_update": "2026-06-09 15:30:00", "records": "486,230"},
            "板块资金数据": {"status": "正常", "last_update": "2026-06-09 15:35:00", "records": "12,450"},
            "新闻数据": {"status": "延迟", "last_update": "2026-06-09 14:20:00", "records": "3,890"},
            "涨停池数据": {"status": "正常", "last_update": "2026-06-09 15:30:00", "records": "8,560"},
            "龙虎榜数据": {"status": "正常", "last_update": "2026-06-09 16:00:00", "records": "2,340"},
            "市场概况": {"status": "正常", "last_update": "2026-06-09 15:30:00", "records": "180"},
        },
        "error_log": [
            {"time": "2026-06-09 15:32:01", "level": "WARNING", "message": "新闻数据采集延迟12分钟，使用缓存数据"},
            {"time": "2026-06-09 14:15:22", "level": "ERROR", "message": "AKShare接口stock_news_em超时，重试成功(第2次)"},
            {"time": "2026-06-09 09:35:10", "level": "INFO", "message": "每日定时任务启动，开始采集数据"},
            {"time": "2026-06-08 15:30:05", "level": "INFO", "message": "回测完成，方向准确率52.3%"},
        ],
        "performance": {
            "数据采集耗时": "3.2秒",
            "因子计算耗时": "1.8秒",
            "评分引擎耗时": "0.5秒",
            "推荐生成耗时": "0.3秒",
            "总耗时": "5.8秒",
        },
        "db_size": "256 MB",
        "db_tables": 16,
    }


def generate_keywords() -> List[Dict[str, Any]]:
    """生成关键词数据"""
    keywords = [
        {"word": "人工智能", "count": 156, "factor": "热词关联因子", "weight": 0.85},
        {"word": "新能源", "count": 134, "factor": "题材持续性因子", "weight": 0.78},
        {"word": "芯片", "count": 128, "factor": "热词关联因子", "weight": 0.82},
        {"word": "锂电池", "count": 112, "factor": "题材持续性因子", "weight": 0.71},
        {"word": "数字经济", "count": 98, "factor": "热词关联因子", "weight": 0.68},
        {"word": "机器人", "count": 89, "factor": "题材持续性因子", "weight": 0.62},
        {"word": "军工", "count": 78, "factor": "热词关联因子", "weight": 0.55},
        {"word": "光伏", "count": 72, "factor": "题材持续性因子", "weight": 0.50},
        {"word": "半导体", "count": 95, "factor": "热词关联因子", "weight": 0.73},
        {"word": "白酒", "count": 65, "factor": "题材持续性因子", "weight": 0.45},
        {"word": "医药", "count": 58, "factor": "热词关联因子", "weight": 0.40},
        {"word": "房地产", "count": 52, "factor": "题材持续性因子", "weight": 0.35},
        {"word": "消费电子", "count": 88, "factor": "热词关联因子", "weight": 0.60},
        {"word": "碳中和", "count": 76, "factor": "题材持续性因子", "weight": 0.53},
        {"word": "元宇宙", "count": 45, "factor": "热词关联因子", "weight": 0.30},
        {"word": "储能", "count": 82, "factor": "题材持续性因子", "weight": 0.58},
        {"word": "智能驾驶", "count": 91, "factor": "热词关联因子", "weight": 0.65},
        {"word": "数据中心", "count": 70, "factor": "热词关联因子", "weight": 0.48},
        {"word": "国产替代", "count": 105, "factor": "题材持续性因子", "weight": 0.70},
        {"word": "低空经济", "count": 67, "factor": "热词关联因子", "weight": 0.43},
        {"word": "量子计算", "count": 38, "factor": "热词关联因子", "weight": 0.25},
        {"word": "卫星互联网", "count": 42, "factor": "题材持续性因子", "weight": 0.28},
        {"word": "鸿蒙", "count": 86, "factor": "热词关联因子", "weight": 0.63},
        {"word": "固态电池", "count": 74, "factor": "题材持续性因子", "weight": 0.52},
        {"word": "人形机器人", "count": 93, "factor": "热词关联因子", "weight": 0.67},
    ]
    return keywords


def generate_accuracy_stats() -> Dict[str, Any]:
    """生成准确率统计"""
    return {
        "direction_accuracy": round(random.uniform(50, 62), 1),
        "rank_accuracy_spearman": round(random.uniform(0.3, 0.6), 3),
        "total_predictions": random.randint(180, 260),
        "correct_predictions": 0,
        "win_rate": round(random.uniform(45, 58), 1),
        "max_drawdown": round(random.uniform(-8, -3), 2),
        "sharpe_ratio": round(random.uniform(0.5, 1.8), 2),
        "weekly_accuracy": [
            {"week": f"第{w}周", "accuracy": round(random.uniform(48, 65), 1)}
            for w in range(1, 9)
        ],
    }


def generate_industry_fund_flow() -> pd.DataFrame:
    """生成行业资金流入数据（同花顺 hyzjl 接口模拟）
    数据来源: https://data.10jqka.com.cn/funds/hyzjl/
    包含: 行业名称、涨跌幅、流入/流出/净额、公司家数、领涨股、3日/5日净额
    """
    industries = [
        "电子", "计算机", "电力设备", "机械设备", "医药生物",
        "汽车", "传媒", "通信", "国防军工", "有色金属",
        "基础化工", "食品饮料", "家用电器", "房地产", "银行",
        "非银金融", "建筑材料", "建筑装饰", "钢铁", "煤炭",
        "石油石化", "环保", "交通运输", "商贸零售", "社会服务",
        "纺织服饰", "轻工制造", "农林牧渔", "综合", "公用事业",
    ]
    records = []
    for ind in industries:
        today_net = round(random.uniform(-15.0, 25.0), 2)
        records.append({
            "行业名称": ind,
            "行业指数": round(random.uniform(800, 12000), 2),
            "涨跌幅(%)": round(random.uniform(-4.0, 6.0), 2),
            "流入资金(亿)": round(abs(today_net) + random.uniform(5, 30), 2),
            "流出资金(亿)": round(abs(today_net) + random.uniform(3, 20), 2),
            "今日净额(亿)": today_net,
            "3日净额(亿)": round(today_net * random.uniform(1.5, 4.0), 2),
            "5日净额(亿)": round(today_net * random.uniform(2.0, 6.0), 2),
            "公司家数": random.randint(15, 180),
            "领涨股": random.choice(["龙头A", "龙头B", "龙头C", "龙头D"]),
            "领涨股涨跌幅(%)": round(random.uniform(0, 20), 2),
        })
    df = pd.DataFrame(records)
    df = df.sort_values("今日净额(亿)", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "排名"
    return df


def generate_concept_fund_flow() -> pd.DataFrame:
    """生成概念资金流入数据（同花顺 gnzjl 接口模拟）
    数据来源: https://data.10jqka.com.cn/funds/gnzjl/
    包含: 概念名称、涨跌幅、流入/流出/净额、公司家数、领涨股、3日/5日净额
    """
    concepts = [
        "人工智能", "机器人概念", "新能源车", "半导体", "锂电池",
        "数字经济", "光伏", "军工", "低空经济", "AIGC概念",
        "华为概念", "元宇宙", "碳中和", "智能驾驶", "数据要素",
        "国产替代", "消费电子", "芯片概念", "物联网", "储能",
        "ChatGPT概念", "虚拟现实", "华为鲲鹏", "卫星互联网", "固态电池",
        "鸿蒙概念", "人形机器人", "百度概念", "智慧城市", "新质生产力",
        "量子计算", "IP经济", "融资融券", "脑机接口", "星闪概念",
    ]
    records = []
    for c in concepts:
        today_net = round(random.uniform(-10.0, 20.0), 2)
        records.append({
            "概念名称": c,
            "涨跌幅(%)": round(random.uniform(-5.0, 8.0), 2),
            "流入资金(亿)": round(abs(today_net) + random.uniform(3, 25), 2),
            "流出资金(亿)": round(abs(today_net) + random.uniform(2, 18), 2),
            "今日净额(亿)": today_net,
            "3日净额(亿)": round(today_net * random.uniform(1.5, 4.5), 2),
            "5日净额(亿)": round(today_net * random.uniform(2.0, 7.0), 2),
            "公司家数": random.randint(8, 120),
            "领涨股": random.choice(["龙头A", "龙头B", "龙头C", "龙头D"]),
            "领涨股涨跌幅(%)": round(random.uniform(0, 20), 2),
        })
    df = pd.DataFrame(records)
    df = df.sort_values("今日净额(亿)", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "排名"
    return df


def generate_concept_rotation_summary() -> str:
    """生成概念轮动方向文字说明"""
    now = datetime.now().strftime("%Y-%m-%d")
    df = generate_concept_fund_flow()
    top5 = df.head(5)["概念名称"].tolist()
    bottom5 = df.tail(5)["概念名称"].tolist()
    inflow = df[df["今日净额(亿)"] > 0]
    outflow = df[df["今日净额(亿)"] < 0]

    text = f"""## 概念轮动方向分析 ({now})

### 资金流入TOP5概念
**{', '.join(top5)}**
资金正在集中流入以上概念板块，短期关注度高。

### 资金流出TOP5概念
**{', '.join(bottom5)}**
资金正在流出以上概念，短期应规避相关个股。

### 轮动概况
- 资金净流入概念: **{len(inflow)}** 个
- 资金净流出概念: **{len(outflow)}** 个
- 流入/流出比: **{len(inflow)/max(len(outflow),1):.1f}:1**

### 轮动预判
当前资金从传统消费方向流向科技成长方向，
建议重点关注资金持续3日流入的概念板块，等待爆发确认。
"""
    return text


def generate_factor_contribution() -> pd.DataFrame:
    """生成因子贡献度数据（回测依据）
    每个因子在过去7天的贡献度、准确率、覆盖率
    """
    factors = [
        {"因子名称": "均线密集度因子", "维度": "技术面", "权重": 0.10,
         "7日贡献度": round(random.uniform(-0.02, 0.05), 3),
         "7日准确率": round(random.uniform(52, 62), 1),
         "覆盖率": round(random.uniform(85, 98), 1),
         "趋势": random.choice(["上升", "上升", "稳定", "下降"])},
        {"因子名称": "MACD金叉因子", "维度": "技术面", "权重": 0.08,
         "7日贡献度": round(random.uniform(-0.03, 0.04), 3),
         "7日准确率": round(random.uniform(48, 60), 1),
         "覆盖率": round(random.uniform(70, 90), 1),
         "趋势": random.choice(["上升", "稳定", "下降", "上升"])},
        {"因子名称": "均线发散向上因子", "维度": "技术面", "权重": 0.06,
         "7日贡献度": round(random.uniform(-0.02, 0.03), 3),
         "7日准确率": round(random.uniform(50, 58), 1),
         "覆盖率": round(random.uniform(65, 85), 1),
         "趋势": random.choice(["稳定", "上升", "下降"])},
        {"因子名称": "筹码集中度因子", "维度": "技术面", "权重": 0.05,
         "7日贡献度": round(random.uniform(-0.01, 0.04), 3),
         "7日准确率": round(random.uniform(51, 61), 1),
         "覆盖率": round(random.uniform(75, 92), 1),
         "趋势": random.choice(["上升", "上升", "稳定"])},
        {"因子名称": "价格优势因子", "维度": "技术面", "权重": 0.04,
         "7日贡献度": round(random.uniform(-0.01, 0.02), 3),
         "7日准确率": round(random.uniform(48, 56), 1),
         "覆盖率": round(random.uniform(95, 100), 1),
         "趋势": random.choice(["稳定", "稳定", "上升"])},
        {"因子名称": "热度值因子", "维度": "热度面", "权重": 0.07,
         "7日贡献度": round(random.uniform(-0.02, 0.05), 3),
         "7日准确率": round(random.uniform(53, 63), 1),
         "覆盖率": round(random.uniform(90, 99), 1),
         "趋势": random.choice(["上升", "上升", "稳定"])},
        {"因子名称": "热度动量因子", "维度": "热度面", "权重": 0.05,
         "7日贡献度": round(random.uniform(-0.02, 0.04), 3),
         "7日准确率": round(random.uniform(50, 60), 1),
         "覆盖率": round(random.uniform(85, 95), 1),
         "趋势": random.choice(["上升", "稳定", "下降"])},
        {"因子名称": "资金流向因子", "维度": "资金面", "权重": 0.10,
         "7日贡献度": round(random.uniform(-0.03, 0.04), 3),
         "7日准确率": round(random.uniform(48, 58), 1),
         "覆盖率": round(random.uniform(80, 95), 1),
         "趋势": random.choice(["上升", "稳定", "稳定", "下降"])},
        {"因子名称": "行业资金流向因子", "维度": "资金面", "权重": 0.06,
         "7日贡献度": round(random.uniform(-0.02, 0.03), 3),
         "7日准确率": round(random.uniform(49, 58), 1),
         "覆盖率": round(random.uniform(85, 98), 1),
         "趋势": random.choice(["上升", "稳定", "下降"])},
        {"因子名称": "概念资金流入因子", "维度": "资金面", "权重": 0.04,
         "7日贡献度": round(random.uniform(-0.01, 0.04), 3),
         "7日准确率": round(random.uniform(50, 62), 1),
         "覆盖率": round(random.uniform(75, 92), 1),
         "趋势": random.choice(["上升", "上升", "稳定"])},
        {"因子名称": "板块阶段因子", "维度": "板块面", "权重": 0.09,
         "7日贡献度": round(random.uniform(-0.02, 0.03), 3),
         "7日准确率": round(random.uniform(50, 60), 1),
         "覆盖率": round(random.uniform(90, 99), 1),
         "趋势": random.choice(["上升", "稳定", "下降", "下降"])},
        {"因子名称": "酿酒期检测因子", "维度": "板块面", "权重": 0.06,
         "7日贡献度": round(random.uniform(-0.02, 0.04), 3),
         "7日准确率": round(random.uniform(51, 60), 1),
         "覆盖率": round(random.uniform(80, 95), 1),
         "趋势": random.choice(["上升", "稳定", "上升"])},
        {"因子名称": "概念热度动量因子", "维度": "概念面", "权重": 0.06,
         "7日贡献度": round(random.uniform(-0.02, 0.03), 3),
         "7日准确率": round(random.uniform(46, 56), 1),
         "覆盖率": round(random.uniform(70, 88), 1),
         "趋势": random.choice(["稳定", "上升", "下降"])},
        {"因子名称": "概念持续性因子", "维度": "概念面", "权重": 0.04,
         "7日贡献度": round(random.uniform(-0.01, 0.02), 3),
         "7日准确率": round(random.uniform(48, 57), 1),
         "覆盖率": round(random.uniform(60, 80), 1),
         "趋势": random.choice(["稳定", "上升", "下降"])},
        {"因子名称": "热词关联因子", "维度": "消息面", "权重": 0.05,
         "7日贡献度": round(random.uniform(-0.05, 0.02), 3),
         "7日准确率": round(random.uniform(45, 55), 1),
         "覆盖率": round(random.uniform(60, 85), 1),
         "趋势": random.choice(["下降", "稳定", "下降"])},
        {"因子名称": "市场周期因子", "维度": "市场面", "权重": 0.05,
         "7日贡献度": round(random.uniform(-0.01, 0.01), 3),
         "7日准确率": round(random.uniform(49, 55), 1),
         "覆盖率": round(random.uniform(98, 100), 1),
         "趋势": random.choice(["稳定", "稳定"])},
    ]
    return pd.DataFrame(factors)


def generate_backtest_results() -> pd.DataFrame:
    """生成回测详细结果数据（30天每日收益）
    为回测引擎提供数据依据
    """
    records = []
    base_date = datetime.now()
    daily_return = 0.0
    benchmark_return = 0.0
    for i in range(30):
        date = base_date - timedelta(days=i)
        daily_return = round(random.uniform(-2.5, 3.5), 2)
        benchmark_return = round(random.uniform(-2.0, 2.8), 2)
        win_count = random.randint(1, 5)
        lose_count = random.randint(0, 3)
        records.append({
            "日期": date.strftime("%Y-%m-%d"),
            "策略日收益率(%)": daily_return,
            "基准日收益率(%)": benchmark_return,
            "超额收益(%)": round(daily_return - benchmark_return, 2),
            "推荐股票数": win_count + lose_count,
            "上涨股票数": win_count,
            "下跌股票数": lose_count,
            "当日胜率(%)": round(win_count / max(win_count + lose_count, 1) * 100, 1),
            "最大持仓收益(%)": round(random.uniform(-3, 8), 2),
            "最大持仓亏损(%)": round(random.uniform(-6, 1), 2),
        })
    df = pd.DataFrame(records)
    df = df.sort_values("日期").reset_index(drop=True)
    return df


def generate_evolution_suggestions() -> list:
    """生成AI进化建议（含概念策略优化 + 技术面形态权重调整）
    每条建议包含: 类型、标题、内容、优先级、建议操作
    """
    return [
        {
            "id": "EVO-001",
            "type": "概念策略",
            "title": "概念资金流入因子权重上调建议",
            "content": (
                "**概念资金流入因子近7日贡献度为+0.035，准确率58.3%，表现优异。**\n\n"
                "分析：概念资金流入因子在过去7天的预测贡献度为正，准确率高于整体平均水平(52.1%)。"
                "尤其是\"人工智能\"和\"机器人概念\"两个概念的资金持续流入，相关个股推荐胜率达到62%。\n\n"
                "**建议操作：**\n"
                "1. 概念资金流入因子权重从 0.05 上调至 0.07（+2%，在5%限制内）\n"
                "2. 增加\"概念3日资金连续流入\"作为加分条件\n"
                "3. 对资金流入TOP5概念的个股给予额外0.5分加分"
            ),
            "priority": "高",
            "action": "权重调整",
            "status": "待采纳",
        },
        {
            "id": "EVO-002",
            "type": "技术面",
            "title": "筹码集中度因子权重上调建议",
            "content": (
                "**筹码集中度因子近7日准确率59.1%，贡献度+0.032，在上涨股票中表现突出。**\n\n"
                "回测分析：推荐后上涨的股票中，80%以上筹码呈现低位密集特征（单峰密集+集中度>70%）。"
                "说明筹码集中度是识别主力吸筹完成、即将拉升的有效信号。\n\n"
                "**建议操作：**\n"
                "1. 筹码集中度因子权重从 0.05 上调至 0.07（+2%）\n"
                "2. 增加\"低位单峰密集\"作为强确认信号（额外+1分）\n"
                "3. 筹码集中度>80%且位于低位的价格区间给予双倍评分"
            ),
            "priority": "高",
            "action": "权重调整",
            "status": "待采纳",
        },
        {
            "id": "EVO-003",
            "type": "技术面",
            "title": "MACD金叉因子有效性验证及权重建议",
            "content": (
                "**MACD金叉因子准确率54.2%，贡献度+0.015，表现中等偏上。**\n\n"
                "回测分析：MACD金叉信号在趋势行情中表现优秀（准确率62%），"
                "但在震荡行情中频繁发出假信号（准确率仅41%）。\n\n"
                "**建议操作：**\n"
                "1. 维持MACD金叉因子权重0.08不变\n"
                "2. 增加\"MACD金叉+均线多头排列\"双确认条件\n"
                "3. 震荡行情中（市场周期因子判断）降低MACD因子权重至0.04"
            ),
            "priority": "中",
            "action": "规则增强",
            "status": "待采纳",
        },
        {
            "id": "EVO-004",
            "type": "技术面",
            "title": "均线发散向上因子权重调整建议",
            "content": (
                "**均线发散向上因子准确率52.8%，贡献度+0.008，表现一般。**\n\n"
                "回测分析：均线发散向上（多头排列+发散角度>15度）的股票平均涨幅+1.8%，"
                "但出现发散后回落的概率也较高（38%），说明单一发散信号不够可靠。\n\n"
                "**建议操作：**\n"
                "1. 均线发散向上因子权重从 0.06 降至 0.04（-2%）\n"
                "2. 增加\"发散+成交量放大\"作为确认条件\n"
                "3. 发散角度<10度的弱发散信号不评分"
            ),
            "priority": "中",
            "action": "权重调整",
            "status": "待采纳",
        },
        {
            "id": "EVO-005",
            "type": "板块策略",
            "title": "板块轮动策略优化",
            "content": (
                "**启动期板块的胜率高于爆发期，建议提前布局。**\n\n"
                "统计显示，启动期板块的推荐胜率为58.2%，而爆发期板块为51.7%。"
                "爆发期板块虽然涨幅更大，但波动性也更高，导致方向预测难度增加。\n\n"
                "**建议操作：**\n"
                "1. 在板块阶段因子中，提高启动期的评分权重（+1分）\n"
                "2. 对爆发期板块增加止损条件（-3%即止损）\n"
                "3. 增加板块资金流入持续性的判断条件（至少连续3日流入）"
            ),
            "priority": "高",
            "action": "规则调整",
            "status": "待采纳",
        },
        {
            "id": "EVO-006",
            "type": "消息面",
            "title": "消息面因子调优建议",
            "content": (
                "**热词关联因子贡献度为-0.023，连续两周为负。**\n\n"
                "过去一周消息面因子的预测贡献度为负，主要原因是新闻数据采集延迟（平均12分钟），"
                "导致时效性下降。题材持续性因子覆盖率为62%，数据不足。\n\n"
                "**建议操作：**\n"
                "1. 热词关联因子权重从 0.05 降至 0.03（-2%）\n"
                "2. 增加新闻数据源的冗余采集通道\n"
                "3. 引入新闻时效性衰减系数，2小时以上的新闻权重降低50%"
            ),
            "priority": "中",
            "action": "权重调整",
            "status": "待采纳",
        },
        {
            "id": "EVO-007",
            "type": "技术面",
            "title": "均线密集度因子增强建议",
            "content": (
                "**均线密集度因子(CV<0.01)过去4周准确率均超过55%，是最稳定因子。**\n\n"
                "**建议操作：**\n"
                "1. 增加均线周期组合（当前仅5/10/20日，建议加入30/60日）\n"
                "2. 对CV阈值进行动态调整，根据市场波动率自适应\n"
                "3. 结合成交量密集度，形成双因子确认机制"
            ),
            "priority": "低",
            "action": "规则增强",
            "status": "待采纳",
        },
        {
            "id": "EVO-008",
            "type": "风险控制",
            "title": "止损机制优化建议",
            "content": (
                "**当前最大回撤为-6.8%，发生在持仓集中度过高时。**\n\n"
                "**建议操作：**\n"
                "1. 严格执行单只持仓不超过20%的规则\n"
                "2. 增加-5%自动止损机制\n"
                "3. 持有超过5天且未达预期的个股强制清仓\n"
                "4. 连续亏损3天时降低仓位至50%"
            ),
            "priority": "高",
            "action": "规则调整",
            "status": "待采纳",
        },
    ]
