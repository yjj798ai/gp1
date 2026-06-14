"""
Dashboard - 市场总览
合并FastAPI市场风向数据
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3, os, json
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"

st.set_page_config(page_title="股神圣杯系统", layout="wide", page_icon="📈")


def get_conn():
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=120)
def load_today_data():
    conn = get_conn()
    today = conn.execute("SELECT MAX(date) FROM hot_rank_history").fetchone()[0]
    market = {"date": today, "stocks_total": 0, "stocks_up": 0, "stocks_down": 0}
    if today:
        market["stocks_total"] = conn.execute("SELECT COUNT(*) FROM hot_rank_history WHERE date=?", (today,)).fetchone()[0]
        market["stocks_up"] = conn.execute("SELECT COUNT(*) FROM hot_rank_history WHERE date=? AND change_pct>0", (today,)).fetchone()[0]
        market["stocks_down"] = conn.execute("SELECT COUNT(*) FROM hot_rank_history WHERE date=? AND change_pct<0", (today,)).fetchone()[0]
    
    concepts = []
    cd = conn.execute("SELECT MAX(date) FROM xuangutong_cards").fetchone()[0]
    if cd:
        rows = conn.execute("""
            SELECT concept, change_pct, up_down, limit_up, fund_flow_today, leader
            FROM xuangutong_cards WHERE date=? ORDER BY limit_up DESC, fund_flow_today DESC LIMIT 15
        """, (cd,)).fetchall()
        concepts = list(rows)
    
    conn.close()
    return market, concepts, today


@st.cache_data(ttl=120)
def load_market_wind():
    """加载市场风向数据 — 从FastAPI迁移"""
    CONCEPT_MAP = {
        '有色 · 钼': '有色金属', '有色 · 钨': '有色金属',
        '有色 · 铜': '有色金属', '有色 · 钴': '有色金属',
        '有色 · 锌': '有色金属', '有色 · 锑': '有色金属',
        '有色 · 锆': '有色金属', '有色 · 锡': '有色金属',
        '有色 · 铋': '有色金属', '有色 · 镍': '有色金属',
        '有色 · 铅': '有色金属', '有色 · 铝': '有色金属',
        '有色 · 镁': '有色金属', '有色 · 钛': '有色金属',
        '券商': '金融业', '银行': '金融业', '保险': '金融业',
        '半导体': '半导体', '芯片': '芯片概念',
        '人工智能': '人工智能', 'AI': '人工智能',
        '新能源车': '新能源车', '新能源汽车': '新能源车',
        '光伏': '太阳能（光伏）', '储能': '储能',
        '军工': '航天军工', '航天': '航天军工',
        '创新药': '创新药', '医药': '创新药',
    }

    result = {}
    try:
        conn = get_conn()

        # 资金流TOP10
        xuangutong = {}
        for r in conn.execute("""
            SELECT concept, fund_flow_today, limit_up, change_pct
            FROM xuangutong_cards
            WHERE date=(SELECT MAX(date) FROM xuangutong_cards)
        """).fetchall():
            xuangutong[r[0]] = {'fund': float(r[1] or 0), 'limit': int(r[2] or 0), 'chg': float(r[3] or 0)}

        merged = {}
        for name, xd in xuangutong.items():
            mapped = CONCEPT_MAP.get(name, name)
            if mapped in merged:
                merged[mapped]['fund_flow'] += xd['fund']
                merged[mapped]['limit_up'] += xd['limit']
            else:
                merged[mapped] = {'concept': mapped, 'fund_flow': xd['fund'], 'limit_up': xd['limit'], 'change_pct': xd['chg']}

        result['fund_flow_top'] = sorted(merged.values(), key=lambda x: -abs(x['fund_flow']))[:10]

        # 热度TOP10
        heat_rows = conn.execute("""
            SELECT name, rate, rise_and_fall, hot_tag
            FROM ths_concept_rank
            WHERE date = (SELECT MAX(date) FROM ths_concept_rank)
            ORDER BY rate DESC LIMIT 10
        """).fetchall()
        result['heat_top'] = [{
            'name': r[0], 'rate': round(float(r[1] or 0)),
            'rise_and_fall': round(float(r[2] or 0), 2),
            'hot_tag': r[3] or '',
        } for r in heat_rows]

        # 市场汇总
        total_up = conn.execute("""
            SELECT SUM(CAST(SUBSTR(up_down, 1, INSTR(up_down, '/')-1) AS INTEGER))
            FROM xuangutong_cards
        """).fetchone()[0] or 0
        total_down = conn.execute("""
            SELECT SUM(CAST(
                SUBSTR(up_down, INSTR(up_down, '/')+1,
                       INSTR(SUBSTR(up_down, INSTR(up_down, '/')+1), '/')-1)
            AS INTEGER))
            FROM xuangutong_cards
        """).fetchone()[0] or 0
        total_limit = conn.execute("""
            SELECT SUM(limit_up) FROM xuangutong_cards
        """).fetchone()[0] or 0
        result['market_summary'] = {
            'up': total_up, 'down': total_down, 'limit_up': total_limit,
        }

        conn.close()
    except Exception as e:
        result['error'] = str(e)
    return result


def render_dashboard():
    st.title("📊 市场总览")
    st.markdown("---")

    market, concepts, today = load_today_data()

    # ── 市场概览卡片 ──
    if today:
        up_ratio = market["stocks_up"] / market["stocks_total"] * 100 if market["stocks_total"] > 0 else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("数据日期", today)
        c2.metric("上涨", f'{market["stocks_up"]}', delta=f'{up_ratio:.1f}%')
        c3.metric("下跌", f'{market["stocks_down"]}')
        c4.metric("总数", f'{market["stocks_total"]}')
    else:
        st.warning("暂无数据，请等待采集")

    st.divider()

    # ── 市场风向（从FastAPI迁移） ──
    wind = load_market_wind()
    if wind.get('market_summary'):
        ms = wind['market_summary']
        st.subheader("📈 市场风向")
        wc1, wc2, wc3 = st.columns(3)
        wc1.metric("板块上涨", f"{ms['up']}个")
        wc2.metric("板块下跌", f"{ms['down']}个")
        wc3.metric("涨停总数", f"{ms['limit_up']}只")

    # ── 资金流TOP10 ──
    if wind.get('fund_flow_top'):
        st.subheader("💰 板块资金流TOP10")
        fund_df = pd.DataFrame(wind['fund_flow_top'])
        st.dataframe(fund_df, use_container_width=True, hide_index=True)

    # ── 热度TOP10 ──
    if wind.get('heat_top'):
        st.subheader("🔥 概念热度TOP10（同花顺）")
        heat_df = pd.DataFrame(wind['heat_top'])
        st.dataframe(heat_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── 概念热度 ──
    st.subheader("🟢 概念热度排行（涨停家数+资金流）")
    if concepts:
        df = pd.DataFrame(concepts, columns=["概念", "涨跌幅", "涨跌比", "涨停", "资金(亿)", "领涨股"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("概念数据采集中...")

    st.divider()

    # ── 系统状态 ──
    st.subheader("⚙️ 系统状态")
    conn = get_conn()
    tables = ["hot_rank_history", "ths_hot_stocks", "xuangutong_cards",
              "stockstar_concept_ranks", "news_cache", "recommendation_log"]
    status = []
    for t in tables:
        try:
            d = conn.execute(f"SELECT MAX(date) FROM {t}").fetchone()[0]
            c = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            icon = "✅" if d == today else "⚠️"
            status.append(f"{icon} {t}({c}条, {d})")
        except:
            status.append(f"❌ {t}")
    conn.close()

    st.markdown(" | ".join(f'<span style="font-size:0.85rem">{s}</span>' for s in status), unsafe_allow_html=True)

    st.caption(f"页面刷新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if st.button("🔄 手动刷新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    render_dashboard()
