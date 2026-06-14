# -*- coding: utf-8 -*-
"""
股神圣杯系统 - 因子策略配置页面
展示因子权重分布、维度汇总、状态统计等信息
"""
import streamlit as st
import pandas as pd
import plotly.express as px

def _load_factor_strategies():
    """从数据库读取真实因子策略配置（基于实际9维度评分模型）"""
    import sqlite3
    conn = sqlite3.connect('E:/AI/gp1/a13/hot_rank.db', timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        # 从 evaluation_summary 获取最新胜率评估用作权重参考
        ev_row = conn.execute(
            'SELECT AVG(win_rate) as avg_wr, COUNT(*) as cnt FROM evaluation_summary'
        ).fetchone()
        avg_win_rate = float(ev_row['avg_wr'] or 50) if ev_row else 50
        conn.close()
    except Exception:
        avg_win_rate = 50
        conn.close()

    # 实际9维度评分模型权重 (详见 scoring.py)
    factors_data = [
        # 基础12因子 × 0.40 → 拆分为12个基础子因子
        {"维度": "技术面", "因子名称": "MACD金叉因子", "权重": 0.04, "状态": "活跃", "文件": "macd_cross.py",
         "说明": "DIF上穿DEA金叉评分，金叉+红柱放大评高分"},
        {"维度": "技术面", "因子名称": "均线发散向上因子", "权重": 0.04, "状态": "活跃", "文件": "ma_divergence.py",
         "说明": "多头排列+均线发散角度评分"},
        {"维度": "技术面", "因子名称": "价格优势因子", "权重": 0.03, "状态": "活跃", "文件": "price_advantage.py",
         "说明": "低价股优势评分，20元以下评高分"},
        {"维度": "技术面", "因子名称": "筹码集中度因子", "权重": 0.03, "状态": "活跃", "文件": "chip_concentration.py",
         "说明": "筹码密集在低位+集中度高高分"},
        {"维度": "热度面", "因子名称": "热度值因子", "权重": 0.04, "状态": "活跃", "文件": "heat_value.py",
         "说明": "同花顺热度排名评分"},
        {"维度": "热度面", "因子名称": "热度动量因子", "权重": 0.04, "状态": "活跃", "文件": "heat_momentum.py",
         "说明": "热度排名上升趋势评分"},
        {"维度": "资金面", "因子名称": "资金流向因子", "权重": 0.05, "状态": "活跃", "文件": "fund_flow.py",
         "说明": "主力资金净流入评分"},
        {"维度": "资金面", "因子名称": "行业资金流向因子", "权重": 0.03, "状态": "活跃", "文件": "industry_fund.py",
         "说明": "行业资金净流入评分"},
        {"维度": "资金面", "因子名称": "概念资金流入因子", "权重": 0.02, "状态": "活跃", "文件": "concept_fund.py",
         "说明": "概念资金净流入评分"},
        {"维度": "板块面", "因子名称": "板块阶段因子", "权重": 0.04, "状态": "活跃", "文件": "sector_phase.py",
         "说明": "板块生命周期阶段评分"},
        {"维度": "板块面", "因子名称": "酿酒期检测因子", "权重": 0.02, "状态": "活跃", "文件": "brew_signal.py",
         "说明": "起涨前技术形态评分"},
        {"维度": "消息面", "因子名称": "热词关联因子", "权重": 0.02, "状态": "观察", "文件": "keyword_correlation.py",
         "说明": "新闻热词与股票关联评分"},
        # 概念匹配 × 0.25
        {"维度": "概念面", "因子名称": "概念匹配因子", "权重": 0.25, "状态": "活跃", "文件": "concept_matching.py",
         "说明": "股票所属概念与当前热点概念匹配度评分"},
        # 排名区间 × 0.08
        {"维度": "市场面", "因子名称": "排名区间因子", "权重": 0.08, "状态": "活跃", "文件": "rank_range.py",
         "说明": "同花顺排名区间评分"},
        # 均线多头 × 0.06
        {"维度": "技术面", "因子名称": "均线多头排列因子", "权重": 0.06, "状态": "活跃", "文件": "ma_bullish.py",
         "说明": "5日/10日/20日均线多头排列评分"},
        # 起涨前信号 × 0.06
        {"维度": "技术面", "因子名称": "起涨前信号因子", "权重": 0.06, "状态": "活跃", "文件": "pre_breakout.py",
         "说明": "CV<0.01变盘前兆检测评分"},
        # 概念资金流 × 0.05
        {"维度": "资金面", "因子名称": "概念资金流动因子", "权重": 0.05, "状态": "活跃", "文件": "concept_flow.py",
         "说明": "概念3日资金连续流入评分"},
        # 新闻关联 × 0.05
        {"维度": "消息面", "因子名称": "新闻关联因子", "权重": 0.05, "状态": "观察", "文件": "news_correlation.py",
         "说明": "新闻标题中股票代码/简称匹配评分"},
        # 涨停梯队 × 0.05
        {"维度": "热度面", "因子名称": "涨停梯队因子", "权重": 0.05, "状态": "活跃", "文件": "limit_up_chain.py",
         "说明": "涨停板梯队完整性评分"},
    ]

    # 根据数据库胜率数据微调权重
    if avg_win_rate > 55:
        # 胜率偏高时维持高权重
        pass
    elif avg_win_rate < 45:
        # 胜率偏低时降低高风险因子权重
        for f in factors_data:
            if f["因子名称"] in ("热词关联因子",):
                f["权重"] = round(f["权重"] * 0.8, 3)
                f["状态"] = "停用"

    # 归一化确保总权重=1.0
    total = sum(f["权重"] for f in factors_data)
    if abs(total - 1.0) > 0.001:
        for f in factors_data:
            f["权重"] = round(f["权重"] / total, 3)
        # 修正舍入误差
        diff = 1.0 - sum(f["权重"] for f in factors_data)
        if factors_data:
            factors_data[0]["权重"] = round(factors_data[0]["权重"] + diff, 3)

    return pd.DataFrame(factors_data)


def render_factor_strategy():
    """渲染因子策略配置页面"""

    # ============================================================
    # 页面标题
    # ============================================================
    st.title("因子策略配置")
    st.caption("多因子评分体系 · 权重自动进化 · 冷却期保护")

    st.divider()

    # ============================================================
    # 因子策略表格
    # ============================================================
    st.subheader("因子策略列表")

    # 生成因子策略数据
    df_factors = _load_factor_strategies()

    # 重命名"文件"列为"文件路径"，与需求一致
    df_display = df_factors.rename(columns={"文件": "文件路径"})

    # 用st.dataframe展示表格
    st.dataframe(
        df_display.style.format(
            {"权重": "{:.0%}"}
        ),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    st.divider()

    # ============================================================
    # 图表区域：权重饼图 + 维度柱状图
    # ============================================================
    chart_col1, chart_col2 = st.columns(2)

    # --- 因子权重分布饼图 ---
    with chart_col1:
        st.subheader("因子权重分布")

        # 饼图颜色
        pie_colors = [
            "#1E88E5",  # 蓝色
            "#43A047",  # 绿色
            "#FB8C00",  # 橙色
            "#8E24AA",  # 紫色
            "#E53935",  # 红色
            "#00ACC1",  # 青色
            "#FFB300",  # 琥珀色
        ]

        fig_pie = px.pie(
            df_factors,
            values="权重",
            names="因子名称",
            hole=0.4,  # 环形饼图
            title="各因子权重占比",
            color_discrete_sequence=pie_colors,
        )
        fig_pie.update_traces(
            textposition="inside",
            textinfo="label+percent",
            textfont_size=11,
        )
        fig_pie.update_layout(
            showlegend=True,
            legend_title_text="因子名称",
            height=400,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 维度权重汇总柱状图 ---
    with chart_col2:
        st.subheader("维度权重汇总")

        # 按维度汇总权重
        df_dim_weight = (
            df_factors.groupby("维度")["权重"]
            .sum()
            .reset_index()
            .sort_values("权重", ascending=False)
        )

        # 维度颜色映射
        dim_colors = {
            "技术面": "#1E88E5",
            "热度面": "#FF6F00",
            "资金面": "#43A047",
            "板块面": "#FB8C00",
            "概念面": "#9C27B0",
            "消息面": "#2196F3",
            "市场面": "#E53935",
        }

        fig_bar = px.bar(
            df_dim_weight,
            x="维度",
            y="权重",
            color="维度",
            color_discrete_map=dim_colors,
            title="各维度总权重",
            text="权重",
        )
        fig_bar.update_traces(
            texttemplate="%{text:.0%}",
            textposition="outside",
        )
        fig_bar.update_layout(
            xaxis_title="维度",
            yaxis_title="总权重",
            yaxis_tickformat=".0%",
            height=400,
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # ============================================================
    # 因子状态统计
    # ============================================================
    st.subheader("因子状态统计")

    # 统计各状态的因子数量
    status_counts = df_factors["状态"].value_counts().reset_index()
    status_counts.columns = ["状态", "数量"]

    # 状态颜色映射
    status_color_map = {
        "活跃": "#4CAF50",
        "观察": "#FF9800",
        "停用": "#9E9E9E",
    }

    col_status = st.columns(len(status_counts))
    for i, row in status_counts.iterrows():
        status_name = row["状态"]
        count = row["数量"]
        color = status_color_map.get(status_name, "#1E88E5")
        with col_status[i]:
            st.markdown(
                f"""
                <div style="
                    background-color: {color};
                    color: white;
                    padding: 1.2rem;
                    border-radius: 10px;
                    text-align: center;
                    font-size: 1.1rem;
                    font-weight: bold;
                ">
                    {status_name}
                    <br/>
                    <span style="font-size: 2rem;">{count}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ============================================================
    # 底部说明
    # ============================================================
    st.caption(
        "说明：因子权重由进化引擎自动调整，单次调整不超过5%，冷却期7天。"
    )
