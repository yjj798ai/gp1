# -*- coding: utf-8 -*-
"""
概念热力图 — 7天概念热度变化可视化
横向条形图：热的长冷的短，直观清晰
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
def load_concept_bars():
    """加载最新概念热度数据，用于条形图"""
    conn = _connect()
    rows = conn.execute("""
        SELECT name, rate, rise_and_fall, hot_tag, days_on_list
        FROM ths_concept_rank
        WHERE date = (SELECT MAX(date) FROM ths_concept_rank)
        ORDER BY rate DESC LIMIT 25
    """).fetchall()
    conn.close()

    if not rows:
        return None

    records = []
    for r in rows:
        days = int(r['days_on_list'] or 0)
        if days == 0:
            stage = "🆕新"
        elif days <= 5:
            stage = "🔥爆发"
        elif days <= 30:
            stage = "📈成长"
        else:
            stage = "⏳老"

        records.append({
            "概念": r['name'],
            "热度": float(r['rate'] or 0),
            "涨跌幅": float(r['rise_and_fall'] or 0),
            "标签": r['hot_tag'] or "",
            "上榜天数": days,
            "阶段": stage,
        })

    return pd.DataFrame(records)


@st.cache_data(ttl=300)
def load_concept_trend():
    """加载7天概念热度趋势"""
    conn = _connect()
    rows = conn.execute("""
        SELECT date, name, rate
        FROM ths_concept_rank
        WHERE date >= date('now', '-7 days')
          AND name IN (SELECT name FROM ths_concept_rank
                       WHERE date = (SELECT MAX(date) FROM ths_concept_rank)
                       ORDER BY rate DESC LIMIT 10)
        ORDER BY date, name
    """).fetchall()
    conn.close()

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=["日期", "概念", "热度"])
    return df.pivot_table(index="概念", columns="日期", values="热度", fill_value=0)


@st.cache_data(ttl=300)
def load_concept_detail(keyword):
    """加载概念详情"""
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
        LIMIT 15
    """, (f'%{keyword}%',)).fetchall()

    conn.close()

    return {
        'ths_rank': dict(ths) if ths else None,
        'xgt_fund': dict(xgt) if xgt else None,
        'stocks': [dict(s) for s in stocks],
    }


def render_concept_heatmap():
    """渲染概念热度页面"""
    st.title("概念热度")
    st.caption("热度越高条越长 | 颜色越深越热")

    df = load_concept_bars()
    if df is None or df.empty:
        st.warning("暂无数据，请等待采集")
        return

    # ── 主图：横向条形图 ──
    st.subheader("今日概念热度 TOP25")

    # 按热度排序，热的在上面
    df_sorted = df.sort_values("热度", ascending=True)

    # 颜色：热度越高越红
    max_rate = df_sorted["热度"].max()
    colors = []
    for v in df_sorted["热度"]:
        ratio = v / max_rate if max_rate > 0 else 0
        if ratio > 0.7:
            colors.append("#E53935")  # 红
        elif ratio > 0.4:
            colors.append("#FB8C00")  # 橙
        elif ratio > 0.2:
            colors.append("#FDD835")  # 黄
        else:
            colors.append("#66BB6A")  # 绿

    fig = go.Figure(go.Bar(
        x=df_sorted["热度"],
        y=df_sorted["概念"],
        orientation="h",
        marker_color=colors,
        text=df_sorted.apply(lambda r: f'{r["热度"]:.0f}  {r["阶段"]}  {r["涨跌幅"]:+.1f}%', axis=1),
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="概念: %{y}<br>热度: %{x:.0f}<br>涨跌: %{customdata:+.2f}%<extra></extra>",
        customdata=df_sorted["涨跌幅"],
    ))

    fig.update_layout(
        height=max(400, len(df_sorted) * 28),
        margin=dict(l=100, r=80, t=10, b=30),
        xaxis_title="热度值",
        yaxis=dict(autorange="reversed"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── 图例说明 ──
    st.caption("🟢冷(0-20)  🟡温(20-50)  🟠热(50-80)  🔴火爆(80+) | 🆕新概念  🔥爆发  📈成长  ⏳老概念")

    st.divider()

    # ── 7天趋势 ──
    st.subheader("TOP10 概念 7天趋势")
    trend = load_concept_trend()
    if trend is not None and not trend.empty:
        fig2 = go.Figure()
        for concept in trend.index:
            fig2.add_trace(go.Scatter(
                x=trend.columns,
                y=trend.loc[concept].values,
                mode="lines+markers",
                name=concept,
                line=dict(width=2),
                marker=dict(size=6),
            ))

        fig2.update_layout(
            height=400,
            margin=dict(l=40, r=20, t=20, b=40),
            xaxis_title="日期",
            yaxis_title="热度值",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("暂无7天趋势数据")

    st.divider()

    # ── 概念详情钻取 ──
    st.subheader("概念详情查询")
    keyword = st.text_input("输入概念名称", placeholder="如：半导体、人工智能...")

    if keyword:
        detail = load_concept_detail(keyword)

        if not detail['ths_rank'] and not detail['xgt_fund']:
            st.info(f"未找到概念「{keyword}」的数据")
            return

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**同花顺**")
            if detail['ths_rank']:
                ths = detail['ths_rank']
                st.metric("热度", f"{float(ths.get('rate', 0) or 0):.0f}")
                st.metric("涨跌", f"{float(ths.get('rise_and_fall', 0) or 0):+.2f}%")
                st.caption(f"{ths.get('hot_tag', '-')} | 上榜{ths.get('days_on_list', '-')}天")
            else:
                st.info("无数据")

        with col2:
            st.markdown("**选股通**")
            if detail['xgt_fund']:
                xgt = detail['xgt_fund']
                st.metric("资金流", f"{float(xgt.get('fund_flow_today', 0) or 0):+.2f}亿")
                st.metric("涨停", f"{xgt.get('limit_up', 0)}家")
                st.caption(f"领涨: {xgt.get('leader', '-')}")
            else:
                st.info("无数据")

        if detail['stocks']:
            st.markdown("**关联个股**")
            st.dataframe(pd.DataFrame(detail['stocks']), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render_concept_heatmap()
