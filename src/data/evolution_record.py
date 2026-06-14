"""
进化记录存储模块
================
使用JSON文件持久化存储进化调整记录，支持记录的增删改查和统计。

文件路径: e:\\AI\\gp1\\data\\evolution_records.json
"""

import os
import json
import threading
from datetime import datetime

# JSON存储文件路径
RECORDS_FILE = os.path.join("e:", os.sep, "AI", "gp1", "data", "evolution_records.json")

# 线程锁，防止并发写入
_lock = threading.Lock()

# 操作类型常量
TYPE_WEIGHT_ADJUST = "权重调整"
TYPE_RULE_ADJUST = "规则调整"
TYPE_RULE_ENHANCE = "规则增强"
TYPE_NEW_FACTOR = "新增因子"

# 来源常量
SOURCE_AI_AGENT = "AI Agent分析"
SOURCE_MANUAL = "人工调整"
SOURCE_AUTO_EVOLVE = "自动进化"

# 状态常量
STATUS_EXECUTED = "已执行"
STATUS_REVOKED = "已撤销"
STATUS_PENDING = "待执行"

# 合法的操作类型集合
VALID_TYPES = {TYPE_WEIGHT_ADJUST, TYPE_RULE_ADJUST, TYPE_RULE_ENHANCE, TYPE_NEW_FACTOR}
# 合法的来源集合
VALID_SOURCES = {SOURCE_AI_AGENT, SOURCE_MANUAL, SOURCE_AUTO_EVOLVE}
# 合法的状态集合
VALID_STATUSES = {STATUS_EXECUTED, STATUS_REVOKED, STATUS_PENDING}


def _ensure_file():
    """确保JSON文件和目录存在。如果文件不存在则创建空记录列表。"""
    file_dir = os.path.dirname(RECORDS_FILE)
    if not os.path.exists(file_dir):
        os.makedirs(file_dir, exist_ok=True)
    if not os.path.exists(RECORDS_FILE):
        with open(RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def _load_records():
    """从JSON文件加载所有记录。"""
    _ensure_file()
    try:
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        if not isinstance(records, list):
            records = []
        return records
    except (json.JSONDecodeError, IOError):
        return []


def _save_records(records):
    """将所有记录写入JSON文件（线程安全）。"""
    with _lock:
        try:
            with open(RECORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except IOError as e:
            raise IOError(f"写入进化记录文件失败: {e}")


def _generate_record_id(records):
    """
    生成记录ID，格式: EVO-REC-YYYYMMDD-NNN
    NNN为当天记录的序号（3位数字，从001开始）。
    """
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = f"EVO-REC-{today_str}-"

    # 统计当天已有的记录数量
    today_count = 0
    for rec in records:
        if rec.get("id", "").startswith(prefix):
            today_count += 1

    seq = today_count + 1
    return f"{prefix}{seq:03d}"


def save_record(record: dict) -> str:
    """
    保存一条进化记录。

    Parameters
    ----------
    record : dict
        记录字典，应包含以下字段：
        - type: 操作类型（权重调整/规则调整/规则增强/新增因子）
        - source: 来源（AI Agent分析/人工调整/自动进化）
        - factor_name: 因子名称
        - detail: 调整内容描述
        - reason: 调整原因
        - status: 状态（已执行/已撤销/待执行）
        - result: 执行结果描述
        - related_suggestion: 关联的进化建议ID（可选）

    Returns
    -------
    str
        生成的记录ID，格式为 EVO-REC-YYYYMMDD-NNN
    """
    records = _load_records()

    # 校验操作类型
    record_type = record.get("type", "")
    if record_type not in VALID_TYPES:
        raise ValueError(
            f"无效的操作类型: '{record_type}'，"
            f"有效值为: {', '.join(sorted(VALID_TYPES))}"
        )

    # 校验来源
    source = record.get("source", "")
    if source not in VALID_SOURCES:
        raise ValueError(
            f"无效的来源: '{source}'，"
            f"有效值为: {', '.join(sorted(VALID_SOURCES))}"
        )

    # 校验状态
    status = record.get("status", "")
    if status not in VALID_STATUSES:
        raise ValueError(
            f"无效的状态: '{status}'，"
            f"有效值为: {', '.join(sorted(VALID_STATUSES))}"
        )

    # 生成记录ID
    record_id = _generate_record_id(records)

    # 构建完整记录
    full_record = {
        "id": record_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": record_type,
        "source": source,
        "factor_name": record.get("factor_name", ""),
        "detail": record.get("detail", ""),
        "reason": record.get("reason", ""),
        "status": status,
        "result": record.get("result", ""),
        "related_suggestion": record.get("related_suggestion", ""),
    }

    records.append(full_record)
    _save_records(records)

    return record_id


def get_records(limit=50) -> list:
    """
    获取最近的进化记录。

    Parameters
    ----------
    limit : int
        返回的最大记录数量，默认50条。

    Returns
    -------
    list
        最近的记录列表，按时间倒序排列（最新在前）。
    """
    records = _load_records()
    # 按时间倒序返回
    return list(reversed(records[-limit:]))


def get_stats() -> dict:
    """
    获取进化记录的统计信息。

    Returns
    -------
    dict
        包含以下统计字段的字典：
        - total: 总调整次数
        - by_type: 各操作类型的次数
        - by_source: 各来源的次数
        - by_status: 各状态的次数
        - success_count: 成功执行次数（结果包含"成功"的记录）
        - success_rate: 成功率（百分比，保留1位小数）
        - last_update: 最近一次更新时间
    """
    records = _load_records()

    total = len(records)

    by_type = {}
    by_source = {}
    by_status = {}
    success_count = 0
    last_update = ""

    for rec in records:
        # 按类型统计
        t = rec.get("type", "未知")
        by_type[t] = by_type.get(t, 0) + 1

        # 按来源统计
        s = rec.get("source", "未知")
        by_source[s] = by_source.get(s, 0) + 1

        # 按状态统计
        st = rec.get("status", "未知")
        by_status[st] = by_status.get(st, 0) + 1

        # 统计成功次数
        result = rec.get("result", "")
        if "成功" in result:
            success_count += 1

        # 最近更新时间
        ts = rec.get("timestamp", "")
        if ts > last_update:
            last_update = ts

    # 计算成功率：成功次数 / (已执行 + 已记录) 总数
    executed_count = by_status.get(STATUS_EXECUTED, 0) + by_status.get("已记录", 0)
    if executed_count > 0:
        success_rate = round(success_count / executed_count * 100, 1)
    else:
        success_rate = 0.0

    return {
        "total": total,
        "by_type": by_type,
        "by_source": by_source,
        "by_status": by_status,
        "success_count": success_count,
        "success_rate": success_rate,
        "last_update": last_update,
    }


def undo_record(record_id: str) -> bool:
    """
    撤销一条进化记录。

    将指定记录的状态改为"已撤销"，并更新执行结果。

    Parameters
    ----------
    record_id : str
        要撤销的记录ID，格式为 EVO-REC-YYYYMMDD-NNN。

    Returns
    -------
    bool
        撤销成功返回True，记录不存在或已撤销返回False。
    """
    records = _load_records()

    found = False
    for rec in records:
        if rec.get("id") == record_id:
            if rec.get("status") == STATUS_REVOKED:
                # 已经撤销过，不再重复操作
                return False
            rec["status"] = STATUS_REVOKED
            rec["result"] = f"已撤销（原结果: {rec.get('result', '无')}）"
            found = True
            break

    if found:
        _save_records(records)
        return True

    return False
