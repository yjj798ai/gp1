# -*- coding: utf-8 -*-
"""进化闭环 — 收盘后自动调权

功能:
  1. 分析因子对推荐结果的贡献度
  2. 根据胜率自动调整因子权重
  3. 记录进化日志到 evolution_log
  4. 冷却期保护：同一因子7天内不重复调整

调用方式:
  python -m src.engine.auto_weights
"""
import sqlite3
import json
from datetime import datetime, timedelta

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
EVO_LOG = "E:/AI/gp1/logs/evolution_log.jsonl"

DEFAULT_WEIGHTS = {
    "concept_bonus": 0.20,
    "pre_breakout": 0.15,
    "concept_fresh_bonus": 0.08,
    "sector_bonus": 0.15,
    "base_score": 0.25,
    "limit_up_penalty": 0.17,
}


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weight_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            factor TEXT,
            old_weight REAL,
            new_weight REAL,
            reason TEXT,
            win_rate REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            event_type TEXT,
            detail TEXT,
            win_rate REAL,
            adjustments TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weight_config (
            factor TEXT PRIMARY KEY,
            weight REAL,
            last_adjusted TEXT,
            version INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def get_current_weights() -> dict:
    """获取当前因子权重"""
    try:
        conn = _connect()
        rows = conn.execute("SELECT factor, weight FROM weight_config").fetchall()
        conn.close()
        if rows:
            return {r[0]: r[1] for r in rows}
    except Exception:
        pass
    return dict(DEFAULT_WEIGHTS)


def save_weights(weights: dict, reason: str = ""):
    """保存因子权重"""
    conn = _connect()
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")
    for factor, weight in weights.items():
        old_row = conn.execute(
            "SELECT weight FROM weight_config WHERE factor=?", (factor,)
        ).fetchone()
        old_weight = old_row[0] if old_row else DEFAULT_WEIGHTS.get(factor, 0.1)

        conn.execute("""
            INSERT OR REPLACE INTO weight_config (factor, weight, last_adjusted, version)
            VALUES (?, ?, ?, COALESCE((SELECT version+1 FROM weight_config WHERE factor=?), 1))
        """, (factor, weight, today, factor))

        conn.execute("""
            INSERT INTO weight_history (date, factor, old_weight, new_weight, reason, win_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (today, factor, old_weight, weight, reason, 0))
    conn.commit()
    conn.close()


def analyze_factor_performance() -> dict:
    """分析每个因子对推荐结果的贡献"""
    try:
        conn = _connect()
        today = datetime.now().strftime("%Y-%m-%d")

        factor_rows = conn.execute(
            "SELECT * FROM factor_log WHERE date=?", (today,)
        ).fetchall()
        rec_rows = conn.execute(
            "SELECT code, change_pct, is_win FROM recommendation_log WHERE date=?",
            (today,),
        ).fetchall()
        conn.close()

        if not factor_rows or not rec_rows:
            return {}

        win_map = {r[0]: (float(r[1] or 0), bool(r[2])) for r in rec_rows}

        factor_perf = {}
        for row in factor_rows:
            code = row[1] if isinstance(row, tuple) else row.get("code", "")
            chg, is_win = win_map.get(code, (0, False))

            for fname in ["factor_concept", "factor_pre", "factor_fresh", "factor_sector", "factor_penalty"]:
                val = float(row[fname] if isinstance(row, tuple) else row.get(fname, 0) or 0)
                if fname not in factor_perf:
                    factor_perf[fname] = {"win_vals": [], "loss_vals": [], "win_count": 0, "loss_count": 0}
                if is_win:
                    factor_perf[fname]["win_vals"].append(val)
                    factor_perf[fname]["win_count"] += 1
                else:
                    factor_perf[fname]["loss_vals"].append(abs(val))
                    factor_perf[fname]["loss_count"] += 1

        result = {}
        for fname, perf in factor_perf.items():
            win_avg = sum(perf["win_vals"]) / len(perf["win_vals"]) if perf["win_vals"] else 0
            loss_avg = sum(perf["loss_vals"]) / len(perf["loss_vals"]) if perf["loss_vals"] else 0
            effectiveness = win_avg - loss_avg
            result[fname] = {
                "win_avg": round(win_avg, 3),
                "loss_avg": round(loss_avg, 3),
                "effectiveness": round(effectiveness, 3),
                "win_count": perf["win_count"],
                "loss_count": perf["loss_count"],
            }

        return result
    except Exception:
        return {}


def compute_auto_adjustments(factor_perf: dict, current_weights: dict) -> dict:
    """根据因子表现计算自动调整量

    规则:
      - effectiveness > 0.5: 权重+5% (上限)
      - effectiveness < -0.5: 权重-5% (下限)
      - 胜率>60%: 整体保守微调
      - 胜率<40%: 整体激进调整
    """
    adjustments = {}

    factor_weight_map = {
        "factor_concept": "concept_bonus",
        "factor_pre": "pre_breakout",
        "factor_fresh": "concept_fresh_bonus",
        "factor_sector": "sector_bonus",
        "factor_penalty": "limit_up_penalty",
    }

    for fname, perf in factor_perf.items():
        mapped = factor_weight_map.get(fname)
        if not mapped:
            continue

        old_w = current_weights.get(mapped, 0.1)
        eff = perf.get("effectiveness", 0)

        if eff > 0.5:
            delta = 0.05
        elif eff > 0.2:
            delta = 0.02
        elif eff < -0.5:
            delta = -0.05
        elif eff < -0.2:
            delta = -0.02
        else:
            delta = 0

        if delta != 0:
            new_w = max(0.03, min(0.35, old_w + delta))
            if abs(new_w - old_w) > 0.005:
                adjustments[mapped] = {
                    "old": round(old_w, 3),
                    "new": round(new_w, 3),
                    "delta": round(delta, 3),
                    "reason": f"因子{fname}有效性{eff:+.3f}",
                }

    return adjustments


def check_cooldown(factor: str, days: int = 7) -> bool:
    """检查冷却期：同一因子在N天内是否已调整过"""
    try:
        conn = _connect()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) FROM weight_history WHERE factor=? AND date>=?",
            (factor, cutoff),
        ).fetchone()
        conn.close()
        return row[0] == 0 if row else True
    except Exception:
        return True


def apply_adjustments(adjustments: dict) -> list:
    """应用权重调整（带冷却期保护）"""
    current = get_current_weights()
    applied = []
    for factor, adj in adjustments.items():
        if not check_cooldown(factor):
            continue
        current[factor] = adj["new"]
        applied.append({**adj, "factor": factor})

    if applied:
        save_weights(current, reason="auto_evolution")
    return applied


def record_evolution_log(applied: list, win_rate: float = 0):
    """记录进化日志"""
    if not applied:
        return
    try:
        conn = _connect()
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%H:%M:%S")
        detail = json.dumps(applied, ensure_ascii=False)
        conn.execute("""
            INSERT INTO evolution_log (date, time, event_type, detail, win_rate, adjustments)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (today, now, "auto_weight_adjust", detail, win_rate, len(applied)))
        conn.commit()
        conn.close()
    except Exception:
        pass

    try:
        import os
        os.makedirs(os.path.dirname(EVO_LOG), exist_ok=True)
        with open(EVO_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "date": today, "time": now,
                "type": "auto_weight_adjust",
                "adjustments": applied,
                "win_rate": win_rate,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def get_evolution_history(days: int = 30) -> list:
    """获取进化历史"""
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT date, time, event_type, detail, win_rate, adjustments "
            "FROM evolution_log ORDER BY date DESC, time DESC LIMIT ?",
            (days * 10,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def run_evolution():
    """执行完整进化闭环

    流程:
      1. 分析因子表现
      2. 计算调整量
      3. 应用调整（带冷却期）
      4. 记录日志
    """
    _ensure_tables()

    factor_perf = analyze_factor_performance()
    if not factor_perf:
        print("[进化] 无因子数据，跳过")
        return {"status": "no_data"}

    current_weights = get_current_weights()
    adjustments = compute_auto_adjustments(factor_perf, current_weights)

    if not adjustments:
        print("[进化] 因子表现稳定，无需调整")
        return {"status": "stable", "factor_perf": factor_perf}

    applied = apply_adjustments(adjustments)

    from src.engine.evaluate import evaluate
    ev = evaluate()
    win_rate = ev.get("win_rate", 0) if isinstance(ev, dict) else 0

    record_evolution_log(applied, win_rate)

    result = {
        "status": "adjusted",
        "applied_count": len(applied),
        "adjustments": applied,
        "factor_perf": factor_perf,
        "win_rate": win_rate,
    }

    print(f"[进化] 自动调整{len(applied)}个因子权重:")
    for a in applied:
        print(f"  {a['factor']}: {a['old']:.3f} → {a['new']:.3f} ({a['reason']})")

    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--history":
        history = get_evolution_history(7)
        for h in history:
            print(f"  {h['date']} {h['time']} {h['event_type']} 胜率{h['win_rate']}%")
        sys.exit(0)

    result = run_evolution()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
