"""
AAA 调度器 — APScheduler 全量定时采集
启动: nohup python E:\r\AAA\scheduler.py > E:\r\AAA\logs\scheduler.log 2>&1 &
"""
import os, sys, time, logging, io
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from core.collectors.capital_stock import run as _cap_run

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'scheduler.log'), encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger('scheduler')


# ═══════════════════════════
# 任务定义 (多线程)
# ═══════════════════════════

def job_price():
    """价格K线 — 增量更新"""
    log.info("[PRICE] 价格K线...")
    try:
        from core.collectors.batch_price import run as run_price
        run_price(threads=8)
    except Exception as e:
        log.error(f"价格K线失败: {e}")


def job_sector_flow():
    """行业资金流 + 快照 — ~1s"""
    log.info("[SECTOR] 行业资金采集...")
    try:
        from core.collectors.sector_flow import fetch_instant, save_instant, save_snapshot
        data = fetch_instant()
        save_instant(data)
        save_snapshot(data)
        log.info(f"[OK] {len(data)}行业")
    except Exception as e:
        log.error(f"行业资金失败: {e}")


def job_capital_stock():
    """个股资金流 — 正常+补漏"""
    log.info("[CAPITAL] 个股资金采集...")
    try:
        from core.collectors.capital_stock import run as cap_run
        cap_run(retry_only=False)  # 正常采集
        cap_run(retry_only=True)   # 补漏
    except Exception as e:
        log.error(f"个股资金失败: {e}")


def job_history():
    """历史排名补全 — 每天补最新1天"""
    log.info("[HIST] 历史排名补全...")
    try:
        from core.collectors.history_fill import run
        run(1)  # 只补昨天
    except Exception as e:
        log.error(f"历史排名失败: {e}")


def job_anomaly():
    """异动解析 — 每4小时"""
    log.info("[ANOMALY] 异动解析采集...")
    try:
        from core.collectors.anomaly import run as ano_run
        ano_run()
    except Exception as e:
        log.error(f"异动解析失败: {e}")


def job_today_hot():
    """同花顺概念热词— 每2小时（先于韭研）"""
    log.info("[CONCEPT] 同花顺概念热词采集...")
    try:
        from core.collectors.today_hot import run as th_run
        th_run(1)
    except Exception as e:
        log.error(f"同花顺概念失败: {e}")


def job_jiuyan():
    """韭研热词 — 每2小时"""
    log.info("[HOT] 韭研热词采集...")
    try:
        from core.collectors.jiuyan import run as jy_run
        jy_run()
    except Exception as e:
        log.error(f"韭研失败: {e}")


def job_viewpoint():
    """观点情绪"""
    log.info("[VIEW] 观点采集...")
    try:
        from core.collectors.viewpoint import run as vp_run
        vp_run()
    except Exception as e:
        log.error(f"观点失败: {e}")


def job_cleanup():
    """数据清理 — 余数据删除"""
    log.info("[CLEAN] 数据清理...")
    try:
        from core.collectors.cleanup import run as clean_run
        clean_run()
    except Exception as e:
        log.error(f"清理失败: {e}")


def job_ensure():
    """数据完整性 — 新进补全+退榜清理"""
    log.info("[CHECK] 数据完整性检查...")
    try:
        from core.collectors.ensure_data import run as ensure_run
        ensure_run()
    except Exception as e:
        log.error(f"完整性检查失败: {e}")


def job_rank_history():
    """个股排名历史补全"""
    log.info("[RANK] 排名历史补全...")
    try:
        from core.collectors.rank_history import run as rank_run
        rank_run(50, 60)  # 每天补50只
    except Exception as e:
        log.error(f"排名补全失败: {e}")


def job_sector_snap():
    """同花顺行业一览表"""
    log.info('[SECTOR_SNAP] 行业一览...')
    try:
        from core.collectors.sector_snap import run as snap_run
        snap_run()
    except Exception as e: log.error(f'行业一览失败: {e}')


def job_today_hot():
    """今天炒什么 概念板块"""
    log.info('[HOT_CPT] 热门概念...')
    try:
        from core.collectors.today_hot import run as hot_run
        hot_run()
    except Exception as e: log.error(f'概念失败: {e}')


def job_iwencai():
    """问财热门排行前200"""
    log.info("[IWENCAI] 问财热榜...")
    try:
        from core.collectors.iwencai import run as iwc_run
        iwc_run()
    except Exception as e: log.error(f"问财失败: {e}")


def job_stock_info():
    """个股基本面信息: 主营业务+行业分类+概念板块 (每周更新)"""
    log.info("[STOCK_INFO] 个股基本面信息采集...")
    try:
        from core.collectors.stock_info import run as si_run
        si_run(threads=4)
    except Exception as e: log.error(f"个股基本面失败: {e}")


def job_stock_info_new():
    """新进股票基本面信息补全 (每日)"""
    log.info("[STOCK_INFO_NEW] 新进股票基本面补全...")
    try:
        from core.collectors.stock_info import get_missing_info_count, run as si_run
        missing = get_missing_info_count()
        if missing > 0:
            log.info(f"  缺少基本面信息的股票: {missing}只, 开始补全...")
            si_run(threads=4)
        else:
            log.info("  全部股票基本面信息完整, 跳过")
    except Exception as e: log.error(f"新进基本面补全失败: {e}")


def job_full():
    """全量: 采集+完整性"""
    log.info("[FULL] 全量采集...")
    job_price()
    job_sector_flow()
    job_capital_stock()
    job_history()
    job_jiuyan()
    job_viewpoint()
    job_anomaly()
    job_ensure()
    job_rank_history()
    job_iwencai()
    job_today_hot()
    job_stock_info_new()  # 每日补全新进股票的基本面
    log.info("[OK] 全量完成")


# ═══════════════════════════
# 调度器
# ═══════════════════════════

scheduler = BackgroundScheduler(timezone='Asia/Shanghai')

# 盘中每10分钟: 实时价格 (高频)
scheduler.add_job(lambda: (lambda: __import__('core.collectors.price_live',fromlist=['run']).run())(),
                  CronTrigger(day_of_week='mon-fri', hour='9-11,13-14', minute='*/10'),
                  id='price_live', name='实时价格')

# 每天一次: 价格K线增量
scheduler.add_job(job_price, CronTrigger(hour='*/2', minute='5'), id='price', name='价格K线')

# 每2小时: 行业+个股资金
scheduler.add_job(job_sector_flow, CronTrigger(hour='*/2', minute='10'), id='sector')
scheduler.add_job(job_capital_stock, CronTrigger(hour='*/2', minute='15'), id='capital')
# 同花顺概念热词先于韭研运行，确保数据新鲜
scheduler.add_job(job_today_hot, CronTrigger(hour='*/2', minute='18'), id='today_hot')
scheduler.add_job(job_jiuyan, CronTrigger(hour='*/2', minute='20'), id='jiuyan')
scheduler.add_job(job_anomaly, CronTrigger(hour='*/4', minute='30'), id='anomaly')
scheduler.add_job(job_viewpoint, CronTrigger(hour='*/2', minute='40'), id='viewpoint')
# 凌晨0:30 — 全量补齐
scheduler.add_job(lambda: (lambda: __import__('core.collectors.fill_all',fromlist=['run_all']).run_all())(),
                  CronTrigger(hour='0', minute='30'), id='fill_all')

# 凌晨1:00 — 快速进化
scheduler.add_job(lambda: (lambda: __import__('core.auto_evolve',fromlist=['quick_evolve']).quick_evolve())(),
                  CronTrigger(hour='1', minute='0'), id='quick_evolve')

# 凌晨1:50 — 补漏 (在进化之后)
scheduler.add_job(lambda: _cap_run(retry_only=True), CronTrigger(hour='1', minute='50'), id='retry_cap')

# 凌晨2:00 — 数据清理
scheduler.add_job(job_cleanup, CronTrigger(hour='2', minute='0'), id='cleanup')

# 凌晨2:30 — 数据完整性
scheduler.add_job(job_ensure, CronTrigger(hour='2', minute='30'), id='ensure')

# 凌晨3:00 — 全量采集 (最后执行, 前面都已完成)
scheduler.add_job(job_full, CronTrigger(hour='3', minute='0'), id='night')

# 每周一凌晨3:30 — 全量更新个股基本面信息 (概念容易新增, 需每周刷新)
scheduler.add_job(job_stock_info, CronTrigger(
    day_of_week='mon', hour='3', minute='30'
), id='stock_info_weekly', name='个股基本面(周更)')

# 15:05 收盘 — 全量
scheduler.add_job(job_full, CronTrigger(
    day_of_week='mon-fri', hour='15', minute='5'
), id='close', name='收盘全量')


if __name__ == '__main__':
    print("=" * 50)
    print("  AAA 调度器 (APScheduler)")
    print("=" * 50)
    print(f"  日志: {LOG_DIR}/scheduler.log")
    print()
    for job in scheduler.get_jobs():
        print(f"  [{job.id}] {job.name}: {job.trigger}")
    print()

    # 首次立即全量采集
    print("[首次] 全量采集...")
    job_full()

    scheduler.start()
    print("\n[OK] 调度器已启动")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[STOP] 已停止")
        scheduler.shutdown()
