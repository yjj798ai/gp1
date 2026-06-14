#!/usr/bin/env python3
"""收盘后评估今日推荐的成功率 + 进化机制"""
import sqlite3, json, sys
from datetime import datetime
from collections import defaultdict

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
EVAL_LOG = "E:/AI/gp1/logs/evaluation.jsonl"


def save_recommendations(recs_df):
    """保存当日推荐结果到 recommendation_log + factor_log"""
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")
    conn = sqlite3.connect(DB_PATH)

    # 建表（含因子字段）
    conn.execute('''
        CREATE TABLE IF NOT EXISTS recommendation_log (
            date TEXT, time TEXT, code TEXT, name TEXT,
            rec_price REAL, rec_score REAL, sector TEXT,
            close_price REAL DEFAULT 0, change_pct REAL DEFAULT 0, is_win INTEGER DEFAULT 0,
            PRIMARY KEY (date, code)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS factor_log (
            date TEXT, code TEXT,
            total_score REAL, factor_concept REAL, factor_pre REAL,
            factor_fresh REAL, factor_sector REAL, factor_penalty REAL,
            rec_price REAL, concept_name TEXT,
            PRIMARY KEY (date, code)
        )
    ''')

    saved = 0
    for _, x in recs_df.iterrows():
        try:
            code = x["股票代码"]; name = x["股票名称"]
            price = float(x["当前价格"]); score = float(x["综合评分"])
            sector = x.get("所属板块", x.get("触发概念", ""))
            
            # 主日志
            conn.execute('''
                INSERT OR REPLACE INTO recommendation_log
                (date, time, code, name, rec_price, rec_score, sector)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (today, now, code, name, price, score, sector))
            
            # 因子明细（用于进化调权）
            conn.execute('''
                INSERT OR REPLACE INTO factor_log
                (date, code, total_score, factor_concept, factor_pre,
                 factor_fresh, factor_sector, factor_penalty,
                 rec_price, concept_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, code, score,
                x.get("concept_bonus", 0), x.get("pre_breakout", 0),
                x.get("concept_fresh_bonus", 0), x.get("sector_bonus", 0),
                x.get("limit_up_penalty", 0), price, sector
            ))
            saved += 1
        except Exception as e:
            pass
    conn.commit()
    conn.close()
    return saved


def evaluate():
    """收盘评估：读取recommendation_log + 对比收盘价"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)

    # 读取今日推荐记录（取当日最新一批）
    recs = conn.execute('''
        SELECT code, name, rec_price, rec_score, sector
        FROM recommendation_log
        WHERE date=? ORDER BY time DESC
    ''', (today,)).fetchall()

    # 去重（取最新的一条）
    seen = set()
    unique_recs = []
    for r in recs:
        if r[0] not in seen:
            seen.add(r[0])
            unique_recs.append(r)

    if not unique_recs:
        conn.close()
        return {"date": today, "error": "no recommendations recorded"}

    results = []
    wins = 0
    losses = 0

    for r in unique_recs:
        code, name, rec_price, rec_score, sector = r
        rec_price = float(rec_price or 0)
        rec_score = float(rec_score or 0)

        # 用盘后最新价格
        row = conn.execute('''
            SELECT price, change_pct, rank FROM hot_rank_history
            WHERE code=? AND date=? ORDER BY date DESC LIMIT 1
        ''', (code, today)).fetchone()

        if not row:
            continue

        close_price = float(row[0] or rec_price)
        chg = float(row[1] or 0)
        rank = int(row[2] or 999)

        is_win = chg > 0

        # 更新日志表中的收盘数据
        conn.execute('''
            UPDATE recommendation_log SET
                close_price=?, change_pct=?, is_win=?
            WHERE code=? AND date=?
        ''', (close_price, chg, 1 if is_win else 0, code, today))

        result = {
            "code": code, "name": name,
            "rec_price": round(rec_price, 2),
            "close_price": round(close_price, 2),
            "change_pct": round(chg, 2),
            "rank": rank, "score": rec_score,
            "sector": sector, "win": is_win,
        }
        results.append(result)
        if is_win:
            wins += 1
        else:
            losses += 1

    conn.commit()
    conn.close()

    total = wins + losses
    win_rate = wins / total * 100 if total > 0 else 0

    evaluation = {
        "date": today,
        "time": datetime.now().strftime("%H:%M"),
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "results": results,
    }

    # 保存到 evaluation_summary 表
    conn2 = sqlite3.connect(DB_PATH)
    conn2.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_summary (
            date TEXT PRIMARY KEY,
            total INTEGER,
            wins INTEGER,
            losses INTEGER,
            win_rate REAL,
            details TEXT
        )
    ''')
    conn2.execute('''
        INSERT OR REPLACE INTO evaluation_summary
        (date, total, wins, losses, win_rate, details)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (today, total, wins, losses, round(win_rate, 1),
          json.dumps(results, ensure_ascii=False)))
    conn2.commit()
    conn2.close()

    # 追加到日志
    with open(EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(evaluation, ensure_ascii=False) + "\n")

    return evaluation


def get_evaluation_history(days=30):
    """获取历史评估记录"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT date, total, wins, losses, win_rate
        FROM evaluation_summary ORDER BY date DESC LIMIT ?
    ''', (days,)).fetchall()
    conn.close()
    return rows


def get_evolution_insights():
    """分析历史数据，生成进化建议"""
    history = get_evaluation_history(30)
    if len(history) < 3:
        return "数据不足，需积累更多评估结果"

    # 胜率趋势
    win_rates = [(r[0], r[4]) for r in history if r[4] > 0]
    if not win_rates:
        return "暂无有效评估数据"

    avg_win_rate = sum(w for _, w in win_rates) / len(win_rates)

    # 分析失败股票的共同特征
    conn = sqlite3.connect(DB_PATH)
    losses = conn.execute('''
        SELECT code, name, rec_price, rec_score, change_pct, sector
        FROM recommendation_log
        WHERE is_win=0 AND change_pct < 0
        ORDER BY date DESC LIMIT 20
    ''').fetchall()
    conn.close()

    insights = {
        "总评估天数": len(win_rates),
        "平均胜率": f"{avg_win_rate:.1f}%",
        "最新胜率": f"{win_rates[0][1]:.1f}%",
        "待优化": [],
    }

    if losses:
        # 失败股票的评分分布
        avg_lose_score = sum(float(r[3]) for r in losses if r[3]) / len(losses)
        insights["待优化"].append(f"失败股平均评分{avg_lose_score:.0f}（阈值可调整）")
        # 失败股所属板块
        sectors = [r[5] for r in losses if r[5]]
        if sectors:
            from collections import Counter
            top_sectors = Counter(sectors).most_common(3)
            insights["待优化"].append(f"表现差的板块: {[s for s,c in top_sectors]}")

    return insights


def update_weights_from_evaluation():
    """根据评估结果自动调整评分权重（进化闭环）"""
    insights = get_evolution_insights()
    if isinstance(insights, str):
        return insights

    try:
        from src.engine.auto_weights import run_evolution
        evo_result = run_evolution()
        insights["evolution_result"] = evo_result
    except Exception as e:
        insights["evolution_error"] = str(e)

    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute('''
        INSERT OR REPLACE INTO system_config (key, value)
        VALUES ('evolution_insight', ?)
    ''', (json.dumps(insights, ensure_ascii=False),))
    conn.commit()
    conn.close()

    return insights


def analyze_factor_contribution():
    """分析每个因子对今日推荐的贡献"""
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 读取今日因子明细
    rows = conn.execute("""
        SELECT factor_concept, factor_pre, factor_fresh, factor_sector, factor_penalty
        FROM factor_log WHERE date=?
    """, (today,)).fetchall()
    conn.close()
    
    if not rows:
        return None
    
    # 计算每个因子的平均贡献
    factors = {
        '概念匹配': [r[0] for r in rows],
        '趋势预判': [r[1] for r in rows],
        '概念新鲜度': [r[2] for r in rows],
        '板块支撑': [r[3] for r in rows],
        '风险惩罚': [r[4] for r in rows],
    }
    
    result = {}
    for name, values in factors.items():
        avg = sum(values) / len(values) if values else 0
        result[name] = round(avg, 2)
    
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        # 保存推荐结果（由pipeline调用）
        print("使用: from src.engine.evaluate import save_recommendations")
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--insights":
        ins = get_evolution_insights()
        print(json.dumps(ins, ensure_ascii=False, indent=2))
        sys.exit(0)

    ev = evaluate()
    if "error" in ev:
        print(f"[{ev['date']}] 评估: {ev['error']}")
        sys.exit(0)
    
    print(f"收盘评估 {ev['date']}  {ev['time']}")
    print(f"推荐{ev['total']}只 OK{ev['wins']}只 FAIL{ev['losses']}只")
    print(f"胜率: {ev['win_rate']}%")
    print()

    if ev['losses'] > 0:
        print("失败原因分析:")
        for r in ev['results']:
            if not r['win']:
                print(f"  {r['name']} 评分{r['score']} 推荐{r['rec_price']}→收盘{r['close_price']} ({r['change_pct']:+.1f}%)")
    else:
        print("🎉 全胜！")

    print("\n📈 进化建议:")
    ins = get_evolution_insights()
    if not isinstance(ins, str):
        for item in ins.get("待优化", []):
            print(f"  • {item}")
