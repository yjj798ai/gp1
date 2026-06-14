"""
虚拟持仓管理页面
展示账户概览、持仓明细、交易记录、复盘报告
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3, json

from src.engine.trade_sim import get_portfolio_summary

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


def render_portfolio():
    st.title("💰 模拟交易账户")
    st.markdown("---")

    summary = get_portfolio_summary()

    # ── 账户概览 ──
    st.subheader("账户概览")
    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    with col1:
        st.metric("初始资金", f"¥{summary['initial_capital']:,.2f}")
    with col2:
        st.metric("当前现金", f"¥{summary['cash']:,.2f}")
    with col3:
        st.metric("持仓市值", f"¥{summary['position_value']:,.2f}")
    with col4:
        st.metric("总资产", f"¥{summary['total_value']:,.2f}")
    with col5:
        delta = "normal" if summary['total_profit'] >= 0 else "inverse"
        st.metric("总盈亏", f"¥{summary['total_profit']:+,.2f}",
                  delta=f"{summary['profit_pct']:+.1f}%", delta_color=delta)
    with col6:
        st.metric("持仓数", f"{len(summary['positions'])}只")
    st.divider()

    # ── 持仓明细 ──
    st.subheader("📋 当前持仓")
    if summary['positions']:
        pos_data = []
        for p in summary['positions']:
            pos_data.append({
                "代码": p[0], "名称": p[1],
                "买入日": p[2], "买入价": f"¥{p[3]:.2f}",
                "买入金额": f"¥{p[5]:.2f}",
                "现价": f"¥{p[6]:.2f}" if p[6] else "-",
                "盈亏": f"{p[8]:+.1f}%" if p[8] else "0.0%",
                "买入逻辑": p[9][:50] if p[9] else "-",
            })
        df_pos = pd.DataFrame(pos_data)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)
    else:
        st.info("暂无持仓，下次cronjob触发后自动买入")

    st.divider()

    # ── 交易记录 ──
    st.subheader("📜 交易记录")
    if summary['trades']:
        trade_data = []
        for t in summary['trades']:
            trade_data.append({
                "日期": t[1], "操作": "买入" if t[2] == "buy" else "卖出",
                "代码": t[3], "名称": t[4],
                "金额": f"¥{t[7]:.0f}",
                "盈亏": f"{t[9]:+.1f}%" if t[9] else "-",
                "原因": t[8][:40],
            })
        df_trade = pd.DataFrame(trade_data)
        st.dataframe(df_trade, use_container_width=True, hide_index=True)
    else:
        st.info("暂无交易记录")
    st.divider()

    # ── 推荐效果评估 ──
    st.subheader("📊 推荐效果评估")
    try:
        conn = sqlite3.connect(DB_PATH)
        today = pd.Timestamp.now().strftime("%Y-%m-%d")
        eval_row = conn.execute(
            "SELECT total, wins, losses, win_rate, details FROM evaluation_summary WHERE date=?",
            (today,)).fetchone()
        if eval_row:
            total, wins, losses, win_rate, details = eval_row
            ca, cb, cc, cd = st.columns(4)
            ca.metric("推荐数", total)
            cb.metric("成功", wins)
            cc.metric("失败", losses)
            cd.metric("胜率", f"{win_rate:.1f}%")
            if details:
                df_eval = pd.DataFrame(json.loads(details))
                st.dataframe(
                    df_eval[["name", "rec_price", "close_price", "change_pct", "win"]].rename(
                        columns={"name": "名称", "rec_price": "推荐价",
                                 "close_price": "收盘价", "change_pct": "涨跌幅", "win": "结果"}
                    ),
                    use_container_width=True, hide_index=True)
        else:
            st.info("今日暂无评估数据，15:00收盘后自动评估")

        # 胜率趋势
        history = conn.execute(
            "SELECT date, win_rate FROM evaluation_summary "
            "WHERE win_rate > 0 ORDER BY date DESC LIMIT 30"
        ).fetchall()
        conn.close()

        if len(history) >= 2:
            hist_df = pd.DataFrame(history, columns=["日期", "胜率(%)"])
            hist_df = hist_df.sort_values("日期")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hist_df["日期"], y=hist_df["胜率(%)"],
                mode='lines+markers', name='胜率',
                line=dict(color='#4fc3f7', width=2),
                marker=dict(size=8, color='#4fc3f7')
            ))
            fig.add_hline(y=50, line_dash="dash", line_color="gray",
                          annotation_text="50%基准线")
            fig.update_layout(
                title="推荐胜率趋势",
                xaxis_title="日期", yaxis_title="胜率(%)",
                height=300, margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e0e0e0')
            )
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"评估加载中...")

    st.divider()
    st.caption(
        f"数据更新时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"初始资金 ¥{summary['initial_capital']:,.2f} | "
        f"自动买入：盘前推荐TOP5（每只20%仓位，最多5只）"
    )


if __name__ == "__main__":
    render_portfolio()
