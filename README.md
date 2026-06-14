# 股神圣杯系统

> 概念驱动 · 多因子融合 · 进化闭环
> 双AI开发：Hermes（架构+验收）→ trae（实现）

---

## 快速启动

```bash
# FastAPI 前端（新，端口8521）
cd /e/AI/gp1
python fastapi_app.py

# 旧版 Streamlit 前端（弃用中，端口8520）
streamlit run app.py

# 全量数据采集
python run_collectors.py
```

## 目录结构

```
E:\AI\gp1\
├── app.py                  # Streamlit 入口（旧版，逐步弃用）
├── fastapi_app.py          # FastAPI 入口（新版，主推）
├── run_collectors.py       # 全量数据采集管线 P0~P9
├── src/
│   ├── engine/             # 核心引擎
│   │   ├── filter.py       # 三层过滤漏斗（概念匹配→个股排序→安全过滤）
│   │   ├── scoring.py      # 多因子评分模型
│   │   ├── evaluate.py     # 收盘评估
│   │   └── trade_sim.py    # 模拟交易引擎
│   ├── collectors/         # 10个数据采集器 P0~P9
│   ├── pages/              # Streamlit 页面（旧版）
│   └── utils/              # 工具函数
├── templates/              # FastAPI Jinja2 模板
│   ├── base.html           # 共享布局（深色主题+侧边栏）
│   ├── dashboard.html      # 市场总览
│   ├── recommendations.html # 智能推荐
│   ├── concepts.html       # 概念轮动
│   ├── portfolio.html      # 虚拟持仓
│   └── monitor.html        # 系统监测
├── a13/hot_rank.db         # 主数据库
└── data/holy_grail.db      # 行业/概念映射库
```

## 核心架构

```
数据采集 P0~P9 (10个源)
    ↓
概念延续性评估 (8维度)
    ↓
三层过滤漏斗：
  ① 概念匹配 (97%覆盖率)
  ② 多因子排序 (40+因子)
  ③ 安全过滤 (排除ST/科创板/高价等)
    ↓
收盘评估 → 推荐日志 → 进化调权
```

## 概念驱动评分模型

```
概念延续性 = 涨停强度 + 梯队结构 + 催化剂 + 新闻热度 + 上涨比率
个股评分   = 基础12因子 × 0.50 + 概念匹配 × 0.30 + 排名区间 × 0.12 + 均线多头 × 0.08
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI |
| 前端 | Jinja2 + HTML/CSS（深色主题） |
| 数据 | SQLite（hot_rank.db / holy_grail.db） |
| 采集 | requests + 正则 + BeautifulSoup |
| 定时 | Hermes cronjob（09:00-15:00 交易时段） |
| 旧版 | Streamlit（过渡中） |

## 核心哲学

- **因比果重要** — 概念驱动>板块框子，趋势>静态
- **涨停前的因** — 分析排名爬升/新闻预热/资金流入的链路
- **进化闭环** — 每日评估→自动调权→回测验证
- **不追高** — 涨停股排除，不推荐已涨停的股票

## 数据采集管线

| 步骤 | 数据源 | 内容 |
|------|--------|------|
| P0 | 新浪+同花顺 | 排名 800+ 条 |
| P1 | 板块快照 | 行业涨跌+资金 |
| P2 | 行业/概念分类 | 485只行业映射 |
| P3 | 腾讯K线 | K线数据 |
| P4 | 选股宝涨停池 | 涨停+原因 |
| P5 | 题材挖掘 | 50题材 |
| P6 | 同花顺热门 | 概念标签 |
| P7 | 选股通主题 | 驱动逻辑 |
| P8 | 证券之星概念 | 26概念×涨跌家数 |
| P9 | 选股通风口板块 | 31概念×资金流 |

> 开发团队：Hermes (架构) + trae (实现)
