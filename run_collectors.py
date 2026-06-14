# -*- coding: utf-8 -*-
"""
定时采集任务入口
按优先级分阶段执行各采集器
支持 --quick 增量模式 和 --skip-p2.5 跳过证券之星
"""
import sys
import time
import subprocess
import sqlite3
from datetime import datetime
from src.collectors.retry_runner import run_with_retry

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run_step(label: str, cmd: str, timeout: int = 120) -> bool:
    """执行一步采集任务"""
    log(f"开始: {label}")
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, "-c", cmd],
            timeout=timeout,
            capture_output=True,
            text=True,
            cwd="E:/AI/gp1",
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            log(f"完成: {label} ({elapsed:.1f}s)")
            return True
        else:
            log(f"失败: {label} (exit={result.returncode}): {result.stderr[-200:]}")
            return False
    except subprocess.TimeoutExpired:
        log(f"超时: {label} ({timeout}s)")
        return False
    except Exception as e:
        log(f"异常: {label} ({e})")
        return False


def run(quick=False, skip_p2_5=False):
    """外部调用入口"""
    log("=" * 50)
    log("股神圣杯系统 - 定时采集任务开始")
    log(f"模式: {'增量' if quick else '全量'}")
    log("=" * 50)

    results = {}

    # P0: 核心数据采集（全量+增量都跑）
    log("\n--- P0: 核心数据 ---")
    results["股价更新"] = run_with_retry("股价更新",
        lambda: run_step("新浪股价采集", "from src.data.crawl_sina import fetch_sina_stocks; fetch_sina_stocks()", timeout=60))
    results["热度排名"] = run_with_retry("热度排名",
        lambda: run_step("同花顺热度排名", "from gp_project.core.collectors.today_hot import run as r; r()", timeout=120))
    results["量比换手率"] = run_with_retry("量比换手率",
        lambda: run_step("腾讯行情-量比/换手率", "from src.collectors.fetch_quote import run; run()", timeout=30))

    if not quick:
        # P1: 板块/概念数据（仅全量）
        log("\n--- P1: 板块/概念数据 ---")
        results["板块快照"] = run_with_retry("板块快照",
            lambda: run_step("板块快照采集", "from gp_project.core.collectors.sector_snap import run as r; r()", timeout=60))
        results["行业资金"] = run_with_retry("行业资金",
            lambda: run_step("行业资金流向", "from gp_project.core.collectors.sector_flow import fetch_instant as fi, save_instant as si; d=fi(); si(d); print(f'采集 {len(d)} 条')", timeout=60))

        # P2: 行业/概念分类（仅全量）
        log("\n--- P2: 行业/概念分类 ---")
        results["行业概念"] = run_with_retry("行业概念",
            lambda: run_step("行业/概念增量采集(100只)", "from src.collectors.stock_info_crawler import update_all_stocks; update_all_stocks(concurrency=5, max_stocks=100)", timeout=120))

        # P2.5: 证券之星（可跳过）
        if not skip_p2_5:
            log("\n--- P2.5: 证券之星行业/概念 ---")
            results["证券之星"] = run_with_retry("证券之星",
                lambda: run_step("证券之星行业/概念采集(50个概念)", "from src.collectors.stockstar import update_all; update_all(max_concepts=50)", timeout=300))

        # P2.6-P2.7: 同步+回填（仅全量）
        log("\n--- P2.6-P2.7: 同步+回填 ---")
        results["数据库同步"] = run_with_retry("数据库同步",
            lambda: run_step("同步行业/概念到hot_rank.db", "from scripts.sync_db import sync_industry_concepts; sync_industry_concepts()", timeout=30))
        results["hot_tag回填"] = run_with_retry("hot_tag回填",
            lambda: run_step("回填 sector_snapshot.hot_tag", "import sqlite3; conn=sqlite3.connect('E:/AI/gp1/a13/hot_rank.db'); conn.execute(\"UPDATE sector_snapshot SET hot_tag=CASE WHEN change_pct>2.0 AND net_flow>0 THEN '爆发' WHEN change_pct>1.0 AND net_flow>0 THEN '启动' WHEN change_pct<-1.0 AND net_flow<0 THEN '退潮' ELSE NULL END WHERE hot_tag IS NULL\"); conn.commit(); print('hot_tag回填完成')", timeout=10))

        # P3: K线更新 + 均线计算（仅全量）
        log("\n--- P3: K线增量更新 + 均线计算 ---")
        results["K线更新"] = run_with_retry("K线更新",
            lambda: run_step("K线增量更新(60天/600只)", "from fetch_kline import run; run(threads=10, days=60, max_stocks=600)", timeout=120))
        results["均线计算"] = run_with_retry("均线计算",
            lambda: run_step("MA5/MA10/MA20均线计算", "from src.collectors.compute_ma import compute_ma; n=compute_ma(); print(f'Updated {n} stocks')", timeout=30))

        # P4-P5: 选股宝+题材（仅全量）
        log("\n--- P4-P5: 选股宝+题材 ---")
        results["选股宝"] = run_with_retry("选股宝",
            lambda: run_step("选股宝涨停池/跌停池/强势股 + hot_tag更新", "from src.collectors.xuangubao import update_all; update_all()", timeout=60))
        results["题材挖掘"] = run_with_retry("题材挖掘",
            lambda: run_step("题材挖掘API(50题材+关联股票)", "from src.collectors.xuangubao import update_themes; update_themes()", timeout=120))

    # P6: 同花顺热门（全量+增量都跑）
    log("\n--- P6: 同花顺热门榜单 ---")
    results["同花顺热门"] = run_with_retry("同花顺热门",
        lambda: run_step("同花顺热门榜单(100只+概念+连板)", "from src.collectors.ths_hot_stocks import fetch_hot_stocks, save_hot_stocks; stocks = fetch_hot_stocks(); save_hot_stocks(stocks)", timeout=30))

    if not quick:
        # P6.5: 概念同步（仅全量）
        log("\n--- P6.5: 概念标签补采 ---")
        results["概念同步"] = run_with_retry("概念同步",
            lambda: run_step("概念标签同步(ths热门100只+涨停原因75只→stock_concepts)", "from src.collectors.ths_hot_stocks import sync_concepts_to_stock_concepts; from src.collectors.xuangubao import sync_limit_up_concepts; n1 = sync_concepts_to_stock_concepts(); n2 = sync_limit_up_concepts(); f'同步{n1+n2}条概念标签'", timeout=15))

        # P7: 选股通主题（仅全量）
        log("\n--- P7: 选股通主题库 ---")
        results["选股通主题"] = run_with_retry("选股通主题",
            lambda: run_step("选股通主题库(3主题+驱动逻辑)", "from src.collectors.xuangutong import fetch_themes, save_themes; t = fetch_themes(); save_themes(t)", timeout=30))

        # P8: 证券之星概念涨跌（仅全量）
        log("\n--- P8: 证券之星概念涨跌排行 ---")
        results["概念涨跌"] = run_with_retry("概念涨跌",
            lambda: run_step("证券之星概念排行(26概念×涨跌家数)", "from src.collectors.stockstar_concepts import fetch_concept_ranks, save_concept_ranks; c = fetch_concept_ranks(); save_concept_ranks(c)", timeout=40))

    # P9: 选股通风口板块（全量+增量都跑）
    log("\n--- P9: 选股通风口板块 ---")
    results["风口板块"] = run_with_retry("风口板块",
        lambda: run_step("选股通风口板块(31概念×涨跌/涨停/资金流/领涨股)", "from src.collectors.xuangutong_cards import fetch_all, save; d = fetch_all(); save(d)", timeout=30))

    # P10: 同花顺概念排行（全量+增量都跑）
    log("\n--- P10: 同花顺概念排行 ---")
    results["同花顺概念"] = run_with_retry("同花顺概念",
        lambda: run_step("同花顺概念排行(TOP20概念×涨跌/涨停/上榜单天数)", "from src.collectors.ths_concept_rank import fetch_concept_rank, save; d = fetch_concept_rank(); save(d)", timeout=20))

    # P11: 生成推荐（全量+增量都跑）
    log("\n--- P11: 生成推荐 ---")
    try:
        from src.engine.filter import run_filter_pipeline
        r, s = run_filter_pipeline(top_n=15)
        log(f"推荐: {len(r)}只, 评分分布: {s}")
        results["推荐生成"] = f"OK {len(r)}只"
    except Exception as e:
        log(f"推荐失败: {e}")
        results["推荐生成"] = f"FAIL {e}"

    # 汇总
    log("\n" + "=" * 50)
    log("采集任务汇总")
    log("=" * 50)
    for name, ok in results.items():
        status = "成功" if ok else "失败"
        log(f"  {name}: {status}")

    success = sum(1 for v in results.values() if v)
    total = len(results)
    log(f"\n总计: {success}/{total} 成功")

    # 新鲜度检查
    try:
        from src.health.check_freshness import get_stale_tables
        stale = get_stale_tables()
        if stale:
            print(f"\nWARNING: {len(stale)}张表数据过期:")
            for t in stale:
                print(f"  {t['table']}: 最新={t['last_date']}, 距今{t['age_minutes']}分钟(阈值{t['threshold_minutes']}分钟)")
        else:
            print("\n所有数据表新鲜度正常")
    except Exception as e:
        print(f"\n新鲜度检查失败: {e}")

    # 更新采集时间
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value, update_time) VALUES (?, ?, ?)",
            ("last_collect_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return success == total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='股神圣杯系统采集器')
    parser.add_argument('--quick', action='store_true', help='增量模式（只跑核心步骤）')
    parser.add_argument('--skip-p2.5', dest='skip_p2_5', action='store_true', help='跳过证券之星采集')
    args = parser.parse_args()
    success = run(quick=args.quick, skip_p2_5=args.skip_p2_5)
    sys.exit(0 if success else 1)
