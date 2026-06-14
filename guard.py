"""
Streamlit 守护脚本 — 检测进程存活，挂了自动重启

用法:
  python guard.py              # 前台运行（调试用）
  python guard.py --daemon     # 后台运行
  python guard.py --stop       # 停止守护
"""

import subprocess
import time
import sys
import os
import logging
import signal
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GUARD] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("guard.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

APP_CMD = ["python", "-m", "streamlit", "run", "app.py", "--server.port", "8501", "--server.headless", "true"]
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_INTERVAL = 30       # 每30秒检查一次
MAX_RESTART = 50          # 最多重启次数（防止无限重启循环）
RESTART_COOLDOWN = 60     # 重启后冷却60秒再检查
PID_FILE = os.path.join(WORK_DIR, ".guard.pid")


def get_streamlit_pids():
    """获取所有streamlit相关进程PID"""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Process -Name python -ErrorAction SilentlyContinue | "
             "Where-Object { $_.CommandLine -match 'streamlit' } | "
             "Select-Object -ExpandProperty Id"],
            capture_output=True, text=True, timeout=10
        )
        pids = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and line.isdigit():
                pids.append(int(line))
        return pids
    except Exception:
        return []


def is_server_alive():
    """检查Streamlit服务是否正常响应"""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8501/_stcore/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_server():
    """启动Streamlit服务"""
    log.info(f"启动Streamlit: {' '.join(APP_CMD)}")
    proc = subprocess.Popen(
        APP_CMD,
        cwd=WORK_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    log.info(f"Streamlit已启动, PID={proc.pid}")
    return proc


def stop_server():
    """停止所有streamlit进程"""
    pids = get_streamlit_pids()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            log.info(f"已停止进程 PID={pid}")
        except Exception:
            pass
    time.sleep(2)
    # 强制清理
    pids = get_streamlit_pids()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            log.info(f"强制停止 PID={pid}")
        except Exception:
            pass


def run_guard():
    """主守护循环"""
    log.info("=" * 50)
    log.info("Streamlit守护启动")
    log.info(f"工作目录: {WORK_DIR}")
    log.info(f"检查间隔: {CHECK_INTERVAL}秒")
    log.info(f"最大重启: {MAX_RESTART}次")
    log.info("=" * 50)

    restart_count = 0
    last_restart_time = 0

    while restart_count < MAX_RESTART:
        now = time.time()

        # 冷却期（刚重启后等一会儿再检查）
        if now - last_restart_time < RESTART_COOLDOWN:
            time.sleep(CHECK_INTERVAL)
            continue

        # 检查服务是否存活
        alive = is_server_alive()

        if alive:
            pids = get_streamlit_pids()
            log.info(f"服务正常 (PIDs: {pids}, 重启次数: {restart_count})")
        else:
            pids = get_streamlit_pids()
            log.warning(f"服务异常! PIDs: {pids}")

            # 先尝试杀掉残留进程
            stop_server()
            time.sleep(3)

            # 重新启动
            try:
                start_server()
                restart_count += 1
                last_restart_time = time.time()
                log.info(f"重启成功 (第{restart_count}次)")
            except Exception as e:
                log.error(f"重启失败: {e}")
                restart_count += 1
                last_restart_time = time.time()

        time.sleep(CHECK_INTERVAL)

    log.error(f"已达最大重启次数({MAX_RESTART})，守护退出")
    log.info("请检查系统状态后手动重启")


if __name__ == "__main__":
    if "--stop" in sys.argv:
        log.info("停止守护和Streamlit...")
        stop_server()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        log.info("已停止")
    elif "--daemon" in sys.argv:
        # Windows后台运行
        log.info("以守护模式启动...")
        # 写入PID文件
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
        run_guard()
    else:
        run_guard()
