"""数据库路径配置 - 自动适配Windows/Linux"""
import os, sys

# 项目根目录
if sys.platform == "win32":
    BASE = "E:/AI/gp1"
else:
    BASE = "/opt/gp1"

# 主数据库
HOT_RANK_DB = os.path.join(BASE, "a13", "hot_rank.db")
# 辅助数据库
HOLY_GRAIL_DB = os.path.join(BASE, "data", "holy_grail.db")

# Cookie配置
CONFIG_JSON = os.path.join(BASE, "src", "gp_project", "config.json")

# 日志目录
LOGS_DIR = os.path.join(BASE, "logs")


def get_conn(db="hot_rank"):
    """获取数据库连接"""
    path = HOT_RANK_DB if db == "hot_rank" else HOLY_GRAIL_DB
    import sqlite3
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
