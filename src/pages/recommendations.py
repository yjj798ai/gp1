# -*- coding: utf-8 -*-
"""
股神圣杯系统 - 推荐股票页面
展示今日推荐股票TOP15（概念匹配→因子评分→安全检查→多维度交叉评分）
"""
import streamlit as st
import pandas as pd
import time

# 推荐股票页面
from src.data.real_data import get_last_update_time


def render_recommendations():
    """渲染推荐股票页面"""

    # ============================================================
    # 页面标题
    # ============================================================
    st.markdown('<div class="main-header">推荐股票</div>', unsafe_allow_html=True)

    # ============================================================
    # 显示上次更新时间
    # ============================================================
    last_update = get_last_update_time()
    st.caption(f"上次更新时间：{last_update}")

    st.divider()

    # ============================================================
    # 三层过滤漏斗 — 带进度条
    # ============================================================
    progress_bar = st.progress(0, text="正在初始化...")
    status_text = st.empty()
    filter_stats = {}

    # 步骤1：概念匹配（替代板块筛选）
    progress_bar.progress(10, text="第一层：概念匹配...")
    status_text.caption("🔍 正在分析今日活跃概念，匹配关联个股...")
    time.sleep(0.3)
    status_text.caption("🔍 正在分析今日活跃概念，匹配关联个股...")
    time.sleep(0.3)

    try:
        from src.engine.filter import run_dual_pipeline, run_filter_pipeline
        try:
            recommendations, filter_stats = run_dual_pipeline(top_n=10)
            data_source = "双Agent评分（概念Agent + 技术Agent + 辩论）"
            has_dual = True
        except Exception as e:
            st.warning(f"双Agent管线异常：{e}，使用基础推荐")
            recommendations, filter_stats = run_filter_pipeline(top_n=10)
            data_source = "三层过滤漏斗（概念匹配→因子评分→安全检查）"
            has_dual = False
    except Exception as e:
        st.warning(f"推荐管线执行异常：{e}，回退到基础推荐")
        recommendations = pd.DataFrame()
        filter_stats = {}
        data_source = "异常回退"
        has_dual = False

    # 如果三层过滤无结果，直接提示
    if recommendations.empty:
        progress_bar.progress(100, text="加载完成（无数据）")
        status_text.caption("")
        st.warning("暂无推荐数据，请等待系统分析完成")
        return

    # 步骤2：显示过滤统计
    progress_bar.progress(70, text="正在校验数据格式...")
    status_text.caption("🔎 正在检查数据完整性...")
    time.sleep(0.2)

    # 确保必要列存在
    required_cols = ["股票代码", "股票名称", "当前价格", "综合评分", "推荐理由"]
    if not all(c in recommendations.columns for c in required_cols):
        progress_bar.progress(100, text="数据格式异常")
        status_text.caption("")
        st.error("数据格式异常，缺少必要字段")
        return

    # 步骤3：准备展示数据
    progress_bar.progress(85, text="正在准备展示数据...")
    status_text.caption("📋 正在整理推荐列表...")
    time.sleep(0.2)

    # 显示过滤漏斗统计
    if filter_stats:
        st.caption(f"数据来源：{data_source}")
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("概念/板块", f"{filter_stats.get('concept_count', filter_stats.get('sector_count', '-'))} 个")
        col_s2.metric("候选股票", f"{filter_stats.get('candidate_count', '-')} 只")
        col_s3.metric("最终推荐", f"{filter_stats.get('after_safety', '-')} 只")
    else:
        st.caption(f"数据来源：{data_source}")

    # ============================================================
    # 今日推荐股票表格
    # ============================================================
    st.subheader(f"今日推荐股票 TOP{len(recommendations)}")

    has_dual_scores = has_dual and "概念评分" in recommendations.columns and "技术评分" in recommendations.columns

    if has_dual_scores:
        display_cols = ["股票代码", "股票名称", "当前价格", "所属板块", "关联概念",
                         "概念评分", "技术评分", "综合评分", "辩论方法", "推荐理由"]
    else:
        display_cols = ["股票代码", "股票名称", "当前价格", "所属板块", "关联概念",
                         "综合评分", "推荐理由"]
    display_cols = [c for c in display_cols if c in recommendations.columns]

    display_df = recommendations[display_cols].copy()

    for col in ["综合评分", "概念评分", "技术评分"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: round(float(x), 1) if pd.notna(x) else 0)

    display_df["名称"] = display_df.apply(
        lambda r: f"https://stockpage.10jqka.com.cn/{r['股票代码']}/#{r['股票名称']}",
        axis=1
    )

    column_config = {
        "股票代码": None,
        "名称": st.column_config.LinkColumn("名称", width=110, display_text=r"#(.*)$"),
        "股票名称": None,
        "当前价格": st.column_config.NumberColumn("价格", format="¥%.2f", width=70),
        "触发概念": st.column_config.TextColumn("触发概念", width=100),
        "关联概念": st.column_config.TextColumn("关联概念", width=130),
        "综合评分": st.column_config.NumberColumn("综合评分", format="%.1f", width=70),
        "推荐理由": st.column_config.TextColumn("推荐理由", width=250),
    }
    if has_dual_scores:
        column_config["概念评分"] = st.column_config.NumberColumn("概念评分", format="%.1f", width=70)
        column_config["技术评分"] = st.column_config.NumberColumn("技术评分", format="%.1f", width=70)
        if "辩论方法" in display_df.columns:
            method_labels = {
                "average": "平均融合",
                "weighted": "胜率加权",
                "extreme_weighted": "极端加权",
            }
            display_df["辩论方法"] = display_df["辩论方法"].map(lambda x: method_labels.get(x, x))
            column_config["辩论方法"] = st.column_config.TextColumn("辩论方法", width=90)

    st.dataframe(
        display_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=500,
    )

    if has_dual_scores:
        st.subheader("双Agent评分对比")
        chart_df = display_df[["股票名称", "概念评分", "技术评分", "综合评分"]].copy() if "股票名称" in display_df.columns else None
        if chart_df is not None and len(chart_df) > 0:
            chart_df = chart_df.set_index("股票名称")
            st.bar_chart(chart_df, height=300)

    # ============================================================
    # 推荐统计摘要
    # ============================================================
    low_price_count = len(display_df[display_df["当前价格"] < 20])
    avg_score = display_df["综合评分"].mean()
    max_score = display_df["综合评分"].max()
    min_score = display_df["综合评分"].min()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("推荐数量", f"{len(display_df)} 只")
    col2.metric("平均评分", f"{avg_score:.2f}")
    col3.metric("最高评分", f"{max_score:.2f}")
    col4.metric("低价股(<20元)", f"{low_price_count} 只")

    # 完成
    progress_bar.progress(100, text="加载完成 ✓")
    status_text.caption("")
    time.sleep(0.5)
    progress_bar.empty()

    st.divider()

    # ============================================================
    # 说明
    # ============================================================
    if has_dual_scores:
        st.info("""
        **双Agent推荐逻辑：**
        - **概念Agent**：评估个股的概念热度、新鲜度、板块支撑（0~40分）
        - **技术Agent**：评估趋势、均线、量价、市值、换手率等7维度（0~100分）
        - **辩论融合**：差值≤10取平均，差值>10按历史胜率加权，差值>30极端加权
        - 安全检查排除：ST股、涨跌停股、股价>20元
        """)
    else:
        st.info("""
        **推荐逻辑说明：**
        - **三层过滤漏斗**：概念匹配 → 因子评分排序 → 安全检查
        - 安全检查排除：ST股、涨跌停股、股价>20元
        - 推荐理由包含因子评分明细
        """)

    st.caption(f"数据更新时间：{last_update} | 数据来源：{data_source}")
