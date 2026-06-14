# -*- coding: utf-8 -*-
"""
股神圣杯系统 - 主应用入口
Streamlit 多页面应用（6页面架构）
"""
import streamlit as st

st.set_page_config(
    page_title="股神圣杯系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1a73e8;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .dataframe th {
        background-color: #1a73e8;
        color: white;
        font-weight: bold;
    }
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    .phase-starting { color: #f57c00; font-weight: bold; }
    .phase-exploding { color: #d32f2f; font-weight: bold; }
    .phase-retreating { color: #388e3c; font-weight: bold; }
    .phase-dormant { color: #757575; }
    .success { color: #2e7d32; font-weight: bold; }
    .failure { color: #c62828; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 侧边栏导航（6页面架构）
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/stock.png", width=60)
    st.title("股神圣杯系统")
    st.caption("AI量化选股 · 板块轮动 · 智能进化")

    st.divider()

    # 系统状态（所有页面可见）
    try:
        from src.data.real_data import get_last_update_time
        update_time = get_last_update_time()
        st.caption(f"📅 数据更新: {update_time}")
    except Exception:
        st.caption("📅 数据更新: 未知")

    st.divider()

    st.subheader("导航菜单")
    page = st.radio(
        label="选择页面",
        options=[
            "📊 市场总览",
            "🎯 智能推荐",
            "🌙 尾盘选股",
            "🔄 概念轮动",
            "📈 概念热力图",
            "⚙️ 策略中心",
            "💰 虚拟持仓",
            "🔍 系统监测",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    st.subheader("系统信息")
    try:
        from src.data.bridge import get_data_source_label
        st.write(f"数据来源：{get_data_source_label()}")
    except Exception:
        st.write("数据来源：模拟数据")
    st.write(f"虚拟资金：2,000 元")

    st.divider()
    st.caption("v2.5 | Python + Streamlit + AI Agent")

    # ════════════════════════════════════════
    # 🔑 Cookie 管理（可折叠）
    # ════════════════════════════════════════
    with st.expander("🔑 采集器 Cookie 管理", expanded=False):
        from src.utils.cookie_manager import get_cookie_info, update_cookie
        info = get_cookie_info()
        for name, detail in info["cookies"].items():
            st.markdown(f"**{name}** {detail['status']}")
        st.caption("Cookie 过期时，从浏览器复制粘贴更新")
        cookie_key = st.selectbox(
            "选择 Cookie", ["ths_cookie", "jiuyan_cookie", "iwencai_cookie", "xuangutong_token"],
            label_visibility="collapsed", key="ck_sel")
        labels = {"ths_cookie":"同花顺","jiuyan_cookie":"韭研","iwencai_cookie":"问财",
                  "xuangutong_token":"选股通"}
        st.markdown(f"**{labels.get(cookie_key,cookie_key)}**")
        new_val = st.text_area("粘贴", height=80, label_visibility="collapsed", key="ck_in",
            placeholder="key1=val1; key2=val2...")
        if st.button("💾 保存", use_container_width=True):
            if update_cookie(cookie_key, new_val):
                st.success("✅ 已更新"); st.rerun()
            else:
                st.error("保存失败")

# ============================================================
# 页面路由（8项）
# ============================================================
if page == "📊 市场总览":
    from src.pages.dashboard import render_dashboard
    render_dashboard()
elif page == "🎯 智能推荐":
    from src.pages.recommendations import render_recommendations
    render_recommendations()
elif page == "🌙 尾盘选股":
    from src.pages.late_session import render_late_session
    render_late_session()
elif page == "🔄 板块轮动":
    from src.pages.sector_rotation import render_sector_rotation
    render_sector_rotation()
elif page == "📈 概念热力图":
    from src.pages.concept_heatmap import render_concept_heatmap
    render_concept_heatmap()
elif page == "⚙️ 策略中心":
    from src.pages.strategy_center import render_strategy_center
    render_strategy_center()
elif page == "💰 虚拟持仓":
    from src.pages.portfolio import render_portfolio
    render_portfolio()
elif page == "🔍 系统监测":
    from src.pages.system_monitor import render_system_monitor
    render_system_monitor()
