"""
采集步骤的失败自动重试包装器
"""
import time, sqlite3, traceback
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"

def _ensure_alert_log():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            step_name TEXT,
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def _log_alert(step_name, error, retry_count):
    _ensure_alert_log()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO alert_log (date, step_name, error, retry_count) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d"), step_name, str(error)[:500], retry_count)
    )
    conn.commit()
    conn.close()

def run_with_retry(step_name, func, max_retries=3, retry_delay=300):
    """
    包装一个采集步骤，失败自动重试
    
    规则：
    - 失败后等 retry_delay 秒重试（默认300秒=5分钟）
    - 最多重试 max_retries 次
    - 每次重试写入 alert_log
    - 3次都失败 → 记录但不raise（不阻断后续步骤）
    - 返回 {"success": bool, "message": str, "retries": int}
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = func()
            if attempt > 0:
                _log_alert(step_name, f"第{attempt}次重试成功", attempt)
            return {"success": True, "message": str(result)[:200], "retries": attempt}
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"  ⚠️ {step_name} 失败(第{attempt+1}次), {retry_delay}秒后重试: {e}")
                _log_alert(step_name, f"失败待重试: {e}", attempt)
                time.sleep(retry_delay)
            else:
                print(f"  ❌ {step_name} 失败{max_retries+1}次, 放弃: {e}")
                _log_alert(step_name, f"最终失败({max_retries+1}次): {e}", attempt)
    
    return {"success": False, "message": str(last_error)[:200], "retries": max_retries}