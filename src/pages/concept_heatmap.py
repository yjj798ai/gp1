# -*- coding: utf-8 -*-
"""
概念热力图 — 7天概念热度变化可视化
从FastAPI迁移：/api/concept-heatmap + /api/concept-detail
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=300)
def load_heatmap_data():
    """加载7天概念热度数据"""
    conn = _connect()
    rows = conn.execute("""
        SELECT date, name, rate, rise_and_fall
        FROM ths_concept_rank
        WHERE date >= date('now', '-7 days')
        ORDER BY date, rate DESC
    """).fetchall()
    conn.close()

    if not rows:
        return None, None, None

    dates = sorted(set(r[0] for r in rows))
    concepts = sorted(set(r[1] for r in rows))

    values = []
    for concept in concepts:
        row = []
        for date in dates:
            match = [r for r in rows if r[0] == date and r[1] == concept]
            if match:
                row.append(round(float(match[0][2] or 0), 1))
            else:
                row.append(0)
        values.append(row)

    return dates, concepts[:20], values[:20]


@st.cache_data(ttl=300)
def load_concept_detail(keyword):
    """加载概念详情：排行+资金流+关联股票"""
    conn = _connect()

    ths = conn.execute("""
        SELECT * FROM ths_concept_rank
        WHERE name LIKE ? ORDER BY date DESC LIMIT 1
    """, (f'%{keyword}%',)).fetchone()

    xgt = conn.execute("""
        SELECT * FROM xuangutong_cards
        WHERE concept LIKE ? ORDER BY date DESC LIMIT 1
    """, (f'%{keyword}%',)).fetchone()

    stocks = conn.execute("""
        SELECT s.code, s.name, s.price, s.change_pct
        FROM stocks s
        JOIN stock_concepts sc ON s.code = sc.code
        WHERE sc.concept LIKE ?
        ORDER BY s.change_pct DESC
        LIMIT 20
    """, (f'%{keyword}%',)).fetchall()

    conn.close()

    return {
        'ths_rank': dict(ths) if ths else None,
        'xgt_fund': dict(xgt) if xgt else None,
        'stocks': [dict(s) for s in stocks],
    }


def render_concept_heatmap():
    """渲染概念热力图页面"""
    st.title("概念热力图")
    st.caption("7天概念热度变化 | 同花顺概念排名数据")
    st.divider()

    dates, concepts, values = load_heatmap_data()

    if not dates or not concepts:
        st.warning("暂无概念热力图数据，请等待采集")
        return

    # ── 热力图 ──
    fig = go.Figure(data=go.Heatmap(
        z=values,
        x=dates,
        y=concepts,
        colorscale='RdYlGn',
        text=values,
        texttemplate='%{text:.0f}',
        textfont={"size": 10},
        hovertemplate='概念: %{y}<br>日期: %{x}<br>热度: %{z:.0f}<extra></extra>',
    ))

    fig.update_layout(
        xaxis_title="日期",
        yaxis_title="概念",
        height=500,
        margin=dict(l=120, r=30, t=30, b=50),
        yaxis=dict(autorange="reversed"),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── 概念详情钻取 ──
    st.subheader("概念详情查询")
    keyword = st.text_input("输入概念名称", placeholder="如：半导体、人工智能...")

    if keyword:
        detail = load_concept_detail(keyword)

        if not detail['ths_rank'] and not detail['xgt_fund']:
            st.info(f"未找到概念「{keyword}」的相关数据")
            return

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**同花顺概念排名**")
            if detail['ths_rank']:
                ths = detail['ths_rank']
                st.metric("热度排名", f"{ths.get('rate', 0):.0f}")
                st.metric("涨跌", f"{ths.get('rise_and_fall', 0):+.2f}%")
                st.caption(f"标签: {ths.get('hot_tag', '-')} | 上榜天数: {ths.get('days_on_list', '-')}")
            else:
                st.info("无同花顺数据")

        with col2:
            st.markdown("**选股通资金流**")
            if detail['xgt_fund']:
                xgt = detail['xgt_fund']
                st.metric("今日资金流", f"{float(xgt.get('fund_flow_today', 0) or 0):+.2f}亿")
                st.metric("涨停数", f"{xgt.get('limit_up', 0)}")
                st.caption(f"领涨: {xgt.get('leader', '-')} | 涨跌: {xgt.get('up_down', '-')}")
            else:
                st.info("无选股通数据")

        if detail['stocks']:
            st.markdown("**关联个股**")
            stocks_df = pd.DataFrame(detail['stocks'])
            st.dataframe(stocks_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render_concept_heatmap()
