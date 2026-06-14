# -*- coding: utf-8 -*-
"""
数据库迁移脚本 — 将旧系统 hot_rank.db 数据迁移到统一数据库 holy_grail.db
功能：
  1. 读取旧数据库所有表数据
  2. 在新数据库中创建完整表结构（旧表 + 新表）
  3. 将旧数据复制到新数据库
  4. 创建新系统需要的额外表并初始化默认数据
  5. 打印迁移统计信息
"""
import os
import sys
import sqlite3
from datetime import datetime

# ============================================================
# 路径配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

OLD_DB_PATH = os.path.join(PROJECT_ROOT, 'a13', 'hot_rank.db')
NEW_DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'holy_grail.db')

# ============================================================
# 新数据库完整建表 SQL
# ============================================================
MIGRATED_TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS stocks (
        code TEXT PRIMARY KEY,
        name TEXT,
        price REAL,
        change_pct REAL,
        sector TEXT,
        concept TEXT,
        pe_ratio REAL,
        market_cap REAL,
        volume REAL,
        current_rank INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS hot_rank_history (
        code TEXT,
        date TEXT,
        rank INTEGER,
        price REAL,
        change_pct REAL,
        rate TEXT,
        PRIMARY KEY (code, date)
    )""",
    """CREATE TABLE IF NOT EXISTS price_5d (
        code TEXT,
        date TEXT,
        price REAL,
        open REAL,
        high REAL,
        low REAL,
        volume REAL,
        PRIMARY KEY (code, date)
    )""",
    """CREATE TABLE IF NOT EXISTS sector_snapshot (
        date TEXT,
        type TEXT,
        code TEXT,
        name TEXT,
        change_pct REAL,
        rate TEXT,
        tag TEXT,
        hot_tag TEXT,
        ranking INTEGER,
        volume REAL,
        amount REAL,
        net_flow REAL,
        up_count INTEGER,
        down_count INTEGER,
        leader TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS concept_hot (
        event_id TEXT,
        date TEXT,
        name TEXT,
        code TEXT,
        heat REAL,
        change_pct REAL,
        limit_up INTEGER,
        leader TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hour_rank_snapshot (
        code TEXT,
        time TEXT,
        hour_order INTEGER,
        rate TEXT,
        hot_rank_chg INTEGER,
        PRIMARY KEY (code, time)
    )""",
]

NEW_TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS stock_concepts (
        code TEXT PRIMARY KEY,
        concept TEXT,
        main_business TEXT,
        industry TEXT,
        update_time TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS industry_fund_flow (
        date TEXT,
        industry_name TEXT,
        industry_code TEXT,
        net_amount REAL,
        net_amount_3d REAL,
        PRIMARY KEY (date, industry_name)
    )""",
    """CREATE TABLE IF NOT EXISTS concept_fund_flow (
        date TEXT,
        concept_name TEXT,
        concept_code TEXT,
        net_amount REAL,
        net_amount_3d REAL,
        PRIMARY KEY (date, concept_name)
    )""",
    """CREATE TABLE IF NOT EXISTS prediction_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        code TEXT,
        name TEXT,
        score REAL,
        reason TEXT,
        actual_change_pct REAL,
        is_correct INTEGER,
        create_time TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS factor_weights (
        factor_name TEXT PRIMARY KEY,
        dimension TEXT,
        weight REAL,
        status TEXT,
        update_time TEXT,
        updated_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS evolution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        type TEXT,
        source TEXT,
        factor_name TEXT,
        detail TEXT,
        reason TEXT,
        status TEXT,
        result TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS portfolio_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        name TEXT,
        buy_price REAL,
        buy_date TEXT,
        quantity INTEGER,
        cost REAL,
        current_price REAL,
        pnl REAL,
        pnl_pct REAL,
        status TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        update_time TEXT
    )""",
]

# ============================================================
# 默认因子权重（16个因子）
# ============================================================
DEFAULT_FACTOR_WEIGHTS = [
    ('heat_value',        '热度',   10.0, 'active', None, '系统初始化'),
    ('heat_momentum',     '热度',   8.0,  'active', None, '系统初始化'),
    ('heat_rank',         '热度',   9.0,  'active', None, '系统初始化'),
    ('capital_inflow',    '资金',   8.0,  'active', None, '系统初始化'),
    ('capital_flow',      '资金',   7.0,  'active', None, '系统初始化'),
    ('concept_flow',      '资金',   6.0,  'active', None, '系统初始化'),
    ('price_advantage',   '价格',   5.0,  'active', None, '系统初始化'),
    ('sector_momentum',   '板块',   7.0,  'active', None, '系统初始化'),
    ('sector_phase',     '板块',   6.0,  'active', None, '系统初始化'),
    ('sector_score',     '板块',   5.0,  'active', None, '系统初始化'),
    ('ma5_position',      '技术',   5.0,  'active', None, '系统初始化'),
    ('volume_ratio',      '技术',   4.0,  'active', None, '系统初始化'),
    ('macd_cross',        '技术',   5.0,  'active', None, '系统初始化'),
    ('market_trend_20d',  '市场',   6.0,  'active', None, '系统初始化'),
    ('brewing_signal',    '题材',   7.0,  'active', None, '系统初始化'),
    ('theme_durability',  '题材',   6.0,  'active', None, '系统初始化'),
]

# ============================================================
# 默认系统配置
# ============================================================
DEFAULT_SYSTEM_CONFIG = [
    ('db_version',       '1.0.0', None),
    ('migration_time',   None,    None),
    ('source_db',        OLD_DB_PATH, None),
    ('created_at',       None,    None),
    ('last_data_update', None,   None),
]


def check_existing_data(new_conn):
    """检查新数据库是否已有数据，防止重复迁移"""
    try:
        count = new_conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        return count > 0
    except Exception:
        return False


def get_old_tables(old_conn):
    """获取旧数据库中所有用户表名"""
    rows = old_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def migrate_table(old_conn, new_conn, table_name):
    """将单个表的数据从旧库迁移到新库"""
    try:
        # 获取旧表数据
        rows = old_conn.execute(f"SELECT * FROM [{table_name}]").fetchall()
        if not rows:
            return 0

        # 获取列名
        cursor = old_conn.execute(f"SELECT * FROM [{table_name}] LIMIT 1")
        col_names = [desc[0] for desc in cursor.description]

        # 批量插入新表
        placeholders = ','.join(['?'] * len(col_names))
        col_str = ','.join(f'[{c}]' for c in col_names)
        insert_sql = f"INSERT OR IGNORE INTO [{table_name}] ({col_str}) VALUES ({placeholders})"

        new_conn.executemany(insert_sql, rows)
        return len(rows)
    except Exception as e:
        print(f"  [警告] 迁移表 {table_name} 失败: {e}")
        return 0


def init_factor_weights(new_conn):
    """初始化 factor_weights 表的默认数据"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows = []
    for factor_name, dimension, weight, status, _, updated_by in DEFAULT_FACTOR_WEIGHTS:
        rows.append((factor_name, dimension, weight, status, now, updated_by))
    new_conn.executemany(
        "INSERT OR IGNORE INTO factor_weights (factor_name, dimension, weight, status, update_time, updated_by) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows
    )
    return len(rows)


def init_system_config(new_conn):
    """初始化 system_config 表的默认数据"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows = []
    for key, value, _ in DEFAULT_SYSTEM_CONFIG:
        if key == 'migration_time':
            value = now
        elif key == 'created_at':
            value = now
        rows.append((key, value, now))
    new_conn.executemany(
        "INSERT OR IGNORE INTO system_config (`key`, value, update_time) VALUES (?, ?, ?)",
        rows
    )
    return len(rows)


def main():
    print("=" * 60)
    print("  数据库迁移工具 — hot_rank.db -> holy_grail.db")
    print("=" * 60)
    print()

    # 检查旧数据库是否存在
    if not os.path.exists(OLD_DB_PATH):
        print(f"[错误] 旧数据库不存在: {OLD_DB_PATH}")
        sys.exit(1)

    # 确保新数据库目录存在
    new_dir = os.path.dirname(NEW_DB_PATH)
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)
        print(f"[信息] 创建目录: {new_dir}")

    # 连接旧数据库
    print(f"[信息] 连接旧数据库: {OLD_DB_PATH}")
    old_conn = sqlite3.connect(OLD_DB_PATH, timeout=5)
    old_tables = get_old_tables(old_conn)
    print(f"[信息] 旧数据库包含 {len(old_tables)} 个表: {', '.join(old_tables)}")

    # 连接新数据库
    print(f"[信息] 连接新数据库: {NEW_DB_PATH}")
    new_conn = sqlite3.connect(NEW_DB_PATH, timeout=5)

    # 检查是否已有数据
    if check_existing_data(new_conn):
        print()
        print("[警告] 新数据库已存在数据，跳过迁移（防止重复）")
        print(f"        如需重新迁移，请先删除: {NEW_DB_PATH}")
        new_conn.close()
        old_conn.close()
        sys.exit(0)

    # ----------------------------------------------------------
    # 第一步：创建所有表结构
    # ----------------------------------------------------------
    print()
    print("--- 第一步：创建表结构 ---")

    # 创建从旧系统迁移的表
    for sql in MIGRATED_TABLES_SQL:
        new_conn.execute(sql)
    print(f"  [OK] 创建 {len(MIGRATED_TABLES_SQL)} 个迁移表")

    # 创建新系统新增的表
    for sql in NEW_TABLES_SQL:
        new_conn.execute(sql)
    print(f"  [OK] 创建 {len(NEW_TABLES_SQL)} 个新增表")

    new_conn.commit()

    # ----------------------------------------------------------
    # 第二步：迁移旧数据
    # ----------------------------------------------------------
    print()
    print("--- 第二步：迁移旧数据 ---")

    total_migrated = 0
    migration_stats = {}

    # 定义旧库中需要迁移的表（按旧库实际表名匹配）
    target_tables = ['stocks', 'hot_rank_history', 'price_5d', 'sector_snapshot',
                     'concept_hot', 'hour_rank_snapshot']

    for table_name in target_tables:
        if table_name in old_tables:
            count = migrate_table(old_conn, new_conn, table_name)
            migration_stats[table_name] = count
            total_migrated += count
            status = "OK" if count >= 0 else "FAIL"
            print(f"  [{status}] {table_name}: {count} 条记录")
        else:
            print(f"  [SKIP] {table_name}: 旧库中不存在此表")

    # 迁移旧库中可能存在的其他表（不在预期列表中的）
    extra_tables = [t for t in old_tables if t not in target_tables]
    for table_name in extra_tables:
        count = migrate_table(old_conn, new_conn, table_name)
        if count > 0:
            migration_stats[table_name] = count
            total_migrated += count
            print(f"  [OK] {table_name} (额外): {count} 条记录")

    new_conn.commit()

    # ----------------------------------------------------------
    # 第三步：初始化新表默认数据
    # ----------------------------------------------------------
    print()
    print("--- 第三步：初始化新表默认数据 ---")

    fw_count = init_factor_weights(new_conn)
    print(f"  [OK] factor_weights: 插入 {fw_count} 条默认因子权重")

    sc_count = init_system_config(new_conn)
    print(f"  [OK] system_config: 插入 {sc_count} 条系统配置")

    new_conn.commit()

    # ----------------------------------------------------------
    # 第四步：验证迁移结果
    # ----------------------------------------------------------
    print()
    print("--- 第四步：验证迁移结果 ---")

    all_tables = [sql.split('IF NOT EXISTS')[1].split('(')[0].strip()
                  for sql in MIGRATED_TABLES_SQL + NEW_TABLES_SQL]

    for table_name in all_tables:
        try:
            count = new_conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
            print(f"  {table_name}: {count} 条记录")
        except Exception as e:
            print(f"  {table_name}: 查询失败 ({e})")

    # 关闭连接
    new_conn.close()
    old_conn.close()

    # ----------------------------------------------------------
    # 打印迁移统计
    # ----------------------------------------------------------
    print()
    print("=" * 60)
    print("  迁移完成!")
    print("=" * 60)
    print(f"  旧数据库: {OLD_DB_PATH}")
    print(f"  新数据库: {NEW_DB_PATH}")
    print(f"  总迁移记录数: {total_migrated}")
    print()
    print("  各表迁移统计:")
    for table_name, count in migration_stats.items():
        print(f"    {table_name}: {count} 条")
    print()
    print(f"  新增表初始化:")
    print(f"    factor_weights: {fw_count} 条")
    print(f"    system_config: {sc_count} 条")
    print()
    print("  [提示] 旧数据库已保留，未做任何修改")
    print("=" * 60)


if __name__ == '__main__':
    main()
