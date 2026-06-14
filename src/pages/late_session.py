# -*- coding: utf-8 -*-
"""
尾盘选股页面 — 14:30八步筛选法
展示八步筛选结果、通过率统计、逐股筛选详情
"""
import streamlit as st
import pandas as pd
import time


def render_late_session():
    """渲染尾盘选股页面"""
    st.markdown('<div class="main-header">尾盘选股 Agent</div>', unsafe_allow_html=True)
    st.caption("14:30 八步筛选法 | 涨幅·量比·换手率·市值·成交量·均线·分时·热点")

    st.divider()

    top_n = st.slider("推荐数量", 5, 30, 10)

    run_btn = st.button("🚀 执行尾盘筛选", type="primary", use_container_width=True)

    if run_btn:
        progress = st.progress(0, text="正在初始化...")
        status = st.empty()

        progress.progress(10, text="正在加载股票数据...")
        status.caption("📊 读取实时行情...")
        time.sleep(0.3)

        try:
            from src.engine.late_session_agent import LateSessionAgent
            agent = LateSessionAgent()

            progress.progress(30, text="正在执行八步筛选...")
            status.caption("🔍 涨幅→量比→换手率→市值→成交量→均线→分时→热点...")
            time.sleep(0.5)

            df, stats = agent.run_screening(top_n=top_n)

            progress.progress(80, text="正在整理结果...")
            status.caption("📋 排序中...")
            time.sleep(0.3)

        except Exception as e:
            st.error(f"尾盘筛选异常：{e}")
            progress.progress(100, text="异常终止")
            return

        progress.progress(100, text="完成 ✓")
        status.caption("")
        time.sleep(0.3)
        progress.empty()

        if df.empty:
            st.warning("暂无符合条件的股票，请等待数据更新")
            return

        st.subheader(f"尾盘推荐 TOP{len(df)}")

        col1, col2, col3 = st.columns(3)
        col1.metric("候选池", f"{stats.get('total_candidates', 0)} 只")
        col2.metric("通过筛选", f"{stats.get('qualified', 0)} 只")
        col3.metric("最终推荐", f"{stats.get('returned', 0)} 只")

        st.divider()

        display_df = df.copy()
        display_df["名称"] = display_df.apply(
            lambda r: f"https://stockpage.10jqka.com.cn/{r['股票代码']}/#{r['股票名称']}",
            axis=1
        )

        col_config = {
            "股票代码": None,
            "名称": st.column_config.LinkColumn("名称", width=110, display_text=r"#(.*)$"),
            "股票名称": None,
            "当前价格": st.column_config.NumberColumn("价格", format="¥%.2f", width=70),
            "涨跌幅(%)": st.column_config.NumberColumn("涨跌幅", format="%.2f%%", width=80),
            "通过步骤": st.column_config.TextColumn("通过步骤", width=60),
            "通过明细": st.column_config.TextColumn("通过明细", width=260),
            "综合评分": st.column_config.NumberColumn("评分", format="%d", width=60),
            "筛选结论": st.column_config.TextColumn("结论", width=80),
            "热点概念": st.column_config.TextColumn("热点概念", width=130),
        }

        st.dataframe(display_df, column_config=col_config, use_container_width=True, hide_index=True, height=500)

        st.divider()

        st.subheader("筛选详情")
        for _, row in df.iterrows():
            code = row["股票代码"]
            name = row["股票名称"]
            score = row["综合评分"]
            verdict = row["筛选结论"]
            passed = row["通过步骤"]

            emoji = "🟢" if verdict == "强烈推荐" else ("🟡" if verdict == "推荐" else ("⚪" if verdict == "观望" else "🔴"))

            with st.expander(f"{emoji} {name} ({code}) — {verdict} | 评分{score} | {passed}"):
                st.markdown(f"**通过明细**：{row['通过明细']}")
                st.markdown(f"**热点概念**：{row.get('热点概念', '无')}")
                st.caption(f"当前价格 ¥{row['当前价格']:.2f} | 涨跌幅 {row['涨跌幅(%)']:+.2f}%")

    st.divider()

    st.info("""
    **八步筛选法说明：**
    1. 涨幅3~5% — 主力控盘、未到高位
    2. 量比≥1 — 当日成交活跃
    3. 换手率5~10% — 筹码活跃但不过度
    4. 市值50~200亿 — 中盘股、弹性好
    5. 成交量递增 — 资金持续进场
    6. 均线多头 — 趋势向上
    7. 分时均线上方 — 主力护盘
    8. 热点匹配 — 踩中市场热点

    通过≥7步=强烈推荐 | ≥5步=推荐 | ≥3步=观望
    """)


if __name__ == "__main__":
    render_late_session()
