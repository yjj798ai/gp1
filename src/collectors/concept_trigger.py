"""
概念触发条件分析
关联公告→概念→股票，用于评分因子计算
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"

def analyze_concept_triggers(days=3):
    """
    分析每个概念近期的"触发信号"
    返回每个概念的活跃度得分
    """
    conn = sqlite3.connect(DB_PATH)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = conn.execute("""
        SELECT related_concepts, source, COUNT(*) as cnt
        FROM news_cache
        WHERE date >= ? AND related_concepts != ''
        GROUP BY related_concepts, source
    """, (cutoff,)).fetchall()

    rank_rows = conn.execute("""
        SELECT name, rate, rise_and_fall, days_on_list
        FROM ths_concept_rank
        WHERE date = (SELECT MAX(date) FROM ths_concept_rank)
    """).fetchall()

    fund_rows = []
    try:
        fund_rows = conn.execute("""
            SELECT concept, fund_flow_today, limit_up, up_down
            FROM xuangutong_cards
            WHERE date = (SELECT MAX(date) FROM xuangutong_cards)
        """).fetchall()
    except Exception:
        pass

    conn.close()

    concepts = {}
    for c in rank_rows:
        name = c[0]
        concepts[name] = {
            "热度": c[1] or 0,
            "涨幅": c[2] or 0,
            "活跃天数": c[3] or 0,
            "公告数": 0,
            "雪球讨论数": 0,
            "资金流": 0,
            "涨停家数": 0,
            "触发信号": 0
        }

    for related, source, cnt in rows:
        for c_name in related.split(','):
            c_name = c_name.strip()
            if c_name in concepts:
                if source == 'cninfo':
                    concepts[c_name]['公告数'] += cnt
                elif source == 'xueqiu':
                    concepts[c_name]['雪球讨论数'] += cnt

    for c in fund_rows:
        name = c[0]
        if name in concepts:
            concepts[name]['资金流'] = c[1] or 0
            concepts[name]['涨停家数'] = c[2] or 0

    for name, data in concepts.items():
        score = 0
        score += min(data['公告数'], 10) * 2
        score += min(data['雪球讨论数'], 10) * 1
        score += min(data['涨停家数'], 10) * 3
        score += min(abs(data['资金流']), 20)
        data['触发信号'] = score

    return concepts

def get_trigger_weight_adjustment():
    concepts = analyze_concept_triggers()
    sorted_c = sorted(concepts.items(), key=lambda x: -x[1]['触发信号'])

    active = [c[0] for c in sorted_c[:5] if c[1]['触发信号'] > 10]
    declining = [c[0] for c in sorted_c[-5:] if c[1]['活跃天数'] > 90 and c[1]['触发信号'] < 5]
    bonus = min(len(active) * 0.01, 0.05)

    return {
        "concept_weight_bonus": bonus,
        "top_active_concepts": active,
        "declining_concepts": declining,
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

if __name__ == "__main__":
    concepts = analyze_concept_triggers()
    sorted_c = sorted(concepts.items(), key=lambda x: -x[1]['触发信号'])

    print("=== 概念触发信号TOP10 ===\n")
    print(f"  {'概念':16s} {'触发信号':>8s} {'公告':>4s} {'雪球':>4s} {'涨停':>4s} {'资金流':>6s} {'活跃天':>6s}")
    print(f"  {'-'*55}")
    for name, data in sorted_c[:10]:
        print(f"  {name:<16s} {data['触发信号']:>8d} {data['公告数']:>4d} {data['雪球讨论数']:>4d} "
              f"{data['涨停家数']:>4d} {data['资金流']:>+5.1f}亿 {data['活跃天数']:>4d}天")

    adj = get_trigger_weight_adjustment()
    print(f"\n权重调整建议: +{adj['concept_weight_bonus']:.0%} 概念权重")
    print(f"活跃概念: {', '.join(adj['top_active_concepts'])}")
    print(f"衰退概念: {', '.join(adj['declining_concepts'])}")
