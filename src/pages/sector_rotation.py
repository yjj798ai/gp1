"""
股神圣杯系统 - 概念轮动监测页面
展示概念排行、资金流向、涨跌家数、涨停梯队
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3, json

DB = "E:/AI/gp1/a13/hot_rank.db"


def _conn():
    return sqlite3.connect(DB, timeout=5)


def render_sector_rotation():
    st.title("概念轮动监测")
    st.caption("基于同花顺+选股通+证券之星真实数据")

    tab1, tab2, tab3 = st.tabs(["🏆 概念排行榜", "📈 热度趋势", "🔗 概念→板块映射"])

    conn = _conn()

    # ── Tab1: 概念排行榜 ──
    with tab1:
        st.subheader("选股通概念排行（按资金流）")
        cards = conn.execute('''
            SELECT concept, change_pct, fund_flow_today, fund_flow_3d, up_down, limit_up, leader
            FROM xuangutong_cards ORDER BY abs(fund_flow_today) DESC
        ''').fetchall()

        if cards:
            rows = []
            for r in cards:
                rows.append({
                    "概念": r[0], "涨跌幅": f"{float(r[1] or 0):+.2f}%",
                    "今日资金": f"{float(r[2] or 0):+.1f}亿",
                    "3日资金": f"{float(r[3] or 0):+.1f}亿",
                    "涨跌家数": r[4] or "-",
                    "涨停": r[5] or 0,
                    "领涨": r[6][:20] if r[6] else "-",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, height=500)
        else:
            st.info("暂无数据")

        st.divider()

        st.subheader("同花顺概念排行（按热度）")
        ths = conn.execute('''
            SELECT name, rise_and_fall, tag, hot_tag, days_on_list, rate
            FROM ths_concept_rank ORDER BY rate DESC
        ''').fetchall()

        if ths:
            rows2 = []
            for r in ths:
                rows2.append({
                    "概念": r[0], "涨跌幅": f"{float(r[1] or 0):+.2f}%",
                    "标签": r[2] or "-", "热度标签": r[3] or "-",
                    "上榜天数": int(r[4] or 0),
                })
            df2 = pd.DataFrame(rows2)
            st.dataframe(df2, use_container_width=True, hide_index=True, height=500)
        else:
            st.info("暂无数据")

    # ── Tab2: 热度趋势 ──
    with tab2:
        st.subheader("概念发布时序（按新鲜度）")
        
        fresh = conn.execute('''
            SELECT name, rise_and_fall, days_on_list, hot_tag, rate
            FROM ths_concept_rank ORDER BY days_on_list ASC LIMIT 20
        ''').fetchall()

        if fresh:
            fresh_data = []
            for r in fresh:
                d = int(r[2] or 0)
                category = "🆕新概念" if d == 0 else ("🔥爆发期" if d <= 5 else ("📈成长期" if d <= 30 else "⏳老概念"))
                fresh_data.append({
                    "概念": r[0], "涨跌幅": f"{float(r[1] or 0):+.2f}%",
                    "上榜天数": f"{d}天", "标签": r[3] or "-", "阶段": category,
                })
            st.dataframe(pd.DataFrame(fresh_data), use_container_width=True, hide_index=True)
        else:
            st.info("暂无趋势数据")

        st.divider()

        # 阶段分布柱状图
        st.subheader("概念阶段分布")
        stages = {"新概念(首次)": 0, "爆发期(≤5天)": 0, "成长期(≤30天)": 0, 
                  "成熟期(≤90天)": 0, "老概念(>90天)": 0}
        for r in conn.execute('SELECT days_on_list FROM ths_concept_rank').fetchall():
            d = int(r[0] or 999)
            if d == 0: stages["新概念(首次)"] += 1
            elif d <= 5: stages["爆发期(≤5天)"] += 1
            elif d <= 30: stages["成长期(≤30天)"] += 1
            elif d <= 90: stages["成熟期(≤90天)"] += 1
            else: stages["老概念(>90天)"] += 1

        fig = go.Figure(data=[go.Bar(
            x=list(stages.keys()), y=list(stages.values()),
            marker_color=["#FF9800", "#F44336", "#4FC3F7", "#9E9E9E", "#616161"],
        )])
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"))
        st.plotly_chart(fig, use_container_width=True)

    # ── Tab3: 概念→板块映射 ──
    with tab3:
        st.subheader("概念与行业交叉映射")

        # 取xuangutong_cards前15概念
        top15 = conn.execute('''
            SELECT concept, fund_flow_today FROM xuangutong_cards
            ORDER BY abs(fund_flow_today) DESC LIMIT 15
        ''').fetchall()

        # 取stockstar行业数据
        sectors = {}
        try:
            for r in conn.execute('''
                SELECT concept, up_ratio FROM stockstar_concept_ranks
                ORDER BY up_ratio DESC LIMIT 10
            ''').fetchall():
                sectors[r[0]] = f"{float(r[1] or 0):.1%}"
        except:
            pass

        st.markdown("**今日资金流入TOP15概念**")
        for r in top15:
            st.markdown(f"- {r[0]:20s} 资金{float(r[1] or 0):+.1f}亿")

        if sectors:
            st.markdown("**行业上涨比率TOP10**")
            for name, ratio in sectors.items():
                st.markdown(f"- {name:20s} 上涨{ratio}")

    conn.close()


if __name__ == "__main__":
    render_sector_rotation()
