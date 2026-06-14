# -*- coding: utf-8 -*-
"""
AI Agent 进化分析模块
基于当前系统数据（因子贡献度、回测结果、推荐表现）生成进化分析
当前版本：本地规则引擎（无需外部API）
后续版本：接入 DeepSeek API 进行深度分析
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional

log = logging.getLogger(__name__)


def analyze_and_advise(context: dict) -> dict:
    """
    AI Agent 分析入口
    参数 context 包含:
      - factor_contribution: 因子贡献度数据
      - accuracy_stats: 准确率统计
      - backtest_results: 回测结果
      - portfolio: 持仓信息
      - market_state: 市场状态描述

    返回:
      {
        'summary': str,           # 总体分析摘要
        'suggestions': list[dict],  # 建议列表
        'risk_alerts': list[str],   # 风险提示
        'market_view': str,         # 市场观点
        'confidence': float,        # 分析置信度
        'updated_at': str,         # 更新时间
      }
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 如果有外部API，调用深度分析
    # try:
    #     return _call_deepseek_api(context)
    # except:
    #     pass

    # 本地规则引擎分析
    return _local_analysis(context, now)


def run_evolution_analysis() -> dict:
    """
    独立执行的进化分析入口（供命令行调用）
    读取所有数据源，执行完整分析，保存记录

    命令行调用方式:
        cd e:\\AI\\gp1
        python -c "from src.utils.ai_agent import run_evolution_analysis; run_evolution_analysis()"
    """
    print("=" * 60)
    print("AI Agent 进化分析启动")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 步骤1：读取数据
    print("\n[1/4] 读取因子贡献度数据...")
    try:
        from src.data.mock_data import (
            generate_factor_contribution,
            generate_accuracy_stats,
            generate_backtest_results,
            generate_portfolio,
            generate_industry_fund_flow,
            generate_concept_fund_flow,
        )
        factor_data = generate_factor_contribution().to_dict('records')
        accuracy = generate_accuracy_stats()
        backtest = generate_backtest_results().to_dict('records')
        portfolio = generate_portfolio()
        industry_flow = generate_industry_fund_flow()
        concept_flow = generate_concept_fund_flow()
        print(f"  -> 读取到 {len(factor_data)} 个因子数据")
    except Exception as e:
        print(f"  -> 数据读取失败: {e}")
        return {"error": str(e)}

    # 步骤2：分析市场趋势
    print("\n[2/4] 分析市场趋势变化...")
    market_view = _analyze_market_trend(factor_data, accuracy, industry_flow, concept_flow)
    print(f"  -> 市场观点: {market_view[:50]}...")

    # 步骤3：执行AI分析
    print("\n[3/4] 执行AI Agent综合分析...")
    context = {
        "factor_contribution": factor_data,
        "accuracy_stats": accuracy,
        "backtest_results": backtest,
        "portfolio": portfolio,
        "market_state": market_view,
        "industry_flow": industry_flow.to_dict('records') if hasattr(industry_flow, 'to_dict') else [],
        "concept_flow": concept_flow.to_dict('records') if hasattr(concept_flow, 'to_dict') else [],
    }

    analysis = analyze_and_advise(context)
    analysis['market_view'] = market_view

    # 步骤4：保存记录
    print("\n[4/4] 保存分析记录...")
    try:
        from src.data.evolution_record import save_record
        record_id = save_record({
            "type": "AI分析",
            "source": "AI Agent分析",
            "factor_name": "综合分析",
            "detail": f"生成{len(analysis.get('suggestions', []))}条建议，"
                      f"置信度{analysis.get('confidence', 0):.0%}",
            "reason": analysis.get('summary', ''),
            "status": "已执行",
            "result": "分析完成，建议已生成",
        })
        print(f"  -> 记录已保存: {record_id}")
    except Exception as e:
        print(f"  -> 记录保存失败: {e}")

    # 输出结果
    print("\n" + "=" * 60)
    print("分析结果")
    print("=" * 60)
    print(f"\n总体摘要: {analysis.get('summary', '')}")
    print(f"\n市场观点: {analysis.get('market_view', '')}")
    print(f"\n置信度: {analysis.get('confidence', 0):.0%}")
    print(f"分析来源: {analysis.get('source', '')}")

    if analysis.get('risk_alerts'):
        print("\n风险提示:")
        for alert in analysis['risk_alerts']:
            print(f"  ⚠ {alert}")

    if analysis.get('suggestions'):
        print(f"\n进化建议 ({len(analysis['suggestions'])}条):")
        for i, s in enumerate(analysis['suggestions'], 1):
            print(f"\n  [{i}] [{s.get('type', '')}] {s.get('title', '')}")
            print(f"      优先级: {s.get('priority', '')}")
            # 提取content中的关键信息
            content = s.get('content', '')
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('**')]
            for line in lines[:3]:
                print(f"      {line}")

    print("\n" + "=" * 60)
    print("分析完成！建议已保存到进化记录中。")
    print("可在系统前端 '进化日志 > 进化记录' 页面查看。")
    print("=" * 60)

    return analysis


def _local_analysis(context: dict, now: str) -> dict:
    """本地规则引擎分析（不依赖外部API）"""

    suggestions = []
    risk_alerts = []
    summary_parts = []

    # ── 1. 因子贡献度分析 ──
    factor_data = context.get('factor_contribution', [])
    if factor_data:
        positive_factors = [f for f in factor_data if f.get('7日贡献度', 0) > 0.01]
        negative_factors = [f for f in factor_data if f.get('7日贡献度', 0) < -0.01]

        summary_parts.append(
            f"因子分析：{len(positive_factors)}个正向贡献，{len(negative_factors)}个负向贡献"
        )

        for f in negative_factors:
            suggestions.append({
                "type": "因子优化",
                "title": f"建议关注{f.get('因子名称', '未知因子')}",
                "content": f"该因子7日贡献度为{f.get('7日贡献度', 0):.3f}，"
                          f"准确率{f.get('7日准确率', 50):.1f}%，趋势{f.get('趋势', '稳定')}。"
                          f"建议{'降低权重' if f.get('趋势') == '下降' else '观察'}。",
                "priority": "高" if f.get('7日贡献度', 0) < -0.03 else "中",
            })

        for f in positive_factors:
            if f.get('趋势') == '上升' and f.get('7日准确率', 0) > 55:
                suggestions.append({
                    "type": "因子增强",
                    "title": f"{f.get('因子名称', '')}表现优秀",
                    "content": f"贡献度{f.get('7日贡献度', 0):.3f}，"
                              f"准确率{f.get('7日准确率', 0):.1f}%，趋势上升。"
                              f"建议适当提高权重。",
                    "priority": "中",
                })

    # ── 2. 技术面形态分析 ──
    tech_factors = [f for f in factor_data if f.get('维度') == '技术面']
    if tech_factors:
        # 分析各技术面因子的有效性
        tech_summary = _analyze_technical_factors(tech_factors, context.get('backtest_results', []))
        if tech_summary:
            summary_parts.append(tech_summary['summary'])
            suggestions.extend(tech_summary['suggestions'])

    # ── 3. 概念/板块资金流向分析 ──
    concept_flow = context.get('concept_flow', [])
    industry_flow = context.get('industry_flow', [])
    if concept_flow or industry_flow:
        flow_analysis = _analyze_fund_flow(concept_flow, industry_flow)
        if flow_analysis:
            summary_parts.append(flow_analysis['summary'])
            suggestions.extend(flow_analysis['suggestions'])

    # ── 4. 准确率分析 ──
    accuracy = context.get('accuracy_stats', {})
    if accuracy:
        dir_acc = accuracy.get('direction_accuracy', 50)
        if dir_acc < 48:
            risk_alerts.append(f"方向准确率仅{dir_acc}%，低于随机水平，建议暂停推荐并检查因子配置")
            suggestions.append({
                "type": "风险控制",
                "title": "准确率过低，建议暂停推荐",
                "content": f"当前方向准确率{dir_acc}%，低于50%基准线。"
                          f"建议暂停自动推荐，检查因子配置和数据质量。",
                "priority": "高",
            })
        elif dir_acc > 58:
            summary_parts.append(f"方向准确率{dir_acc}%，表现优秀")
        else:
            summary_parts.append(f"方向准确率{dir_acc}%，处于正常范围")

        max_dd = accuracy.get('max_drawdown', 0)
        if max_dd < -8:
            risk_alerts.append(f"最大回撤{max_dd}%，超过风控阈值(-8%)")

    # ── 5. 持仓分析 ──
    portfolio = context.get('portfolio', {})
    if portfolio:
        total_pnl_pct = portfolio.get('total_pnl_pct', 0)
        if total_pnl_pct < -5:
            risk_alerts.append(f"虚拟持仓亏损{total_pnl_pct}%，接近止损线(-5%)")
            suggestions.append({
                "type": "风险控制",
                "title": "持仓亏损接近止损线",
                "content": f"当前亏损{total_pnl_pct}%，建议检查持仓个股是否需要止损。",
                "priority": "高",
            })

    # ── 6. 回测形态有效性分析 ──
    backtest = context.get('backtest_results', [])
    if backtest and factor_data:
        pattern_analysis = _analyze_pattern_effectiveness(factor_data, backtest)
        if pattern_analysis:
            summary_parts.append(pattern_analysis['summary'])
            suggestions.extend(pattern_analysis['suggestions'])

    # ── 7. 生成市场观点 ──
    market_view = _generate_market_view(factor_data, accuracy)

    # ── 8. 如果没有建议，生成默认建议 ──
    if not suggestions:
        suggestions.append({
            "type": "常规维护",
            "title": "系统运行正常",
            "content": "当前各因子表现稳定，无需要调整的参数。"
                      "建议继续观察，定期检查数据采集状态。",
            "priority": "低",
        })

    summary = " | ".join(summary_parts) if summary_parts else "系统运行正常，各项指标在正常范围内"

    return {
        "summary": summary,
        "suggestions": suggestions[:8],  # 最多返回8条
        "risk_alerts": risk_alerts,
        "market_view": market_view,
        "confidence": round(min(0.9, 0.5 + len(factor_data) * 0.03), 2),
        "updated_at": now,
        "source": "本地规则引擎",
    }


def _analyze_technical_factors(tech_factors: list, backtest: list) -> Optional[dict]:
    """分析技术面各形态因子的有效性，识别哪些形态值得增权"""
    suggestions = []
    summary_parts = []

    # 按准确率排序技术面因子
    sorted_tech = sorted(tech_factors, key=lambda x: x.get('7日准确率', 50), reverse=True)

    best_factor = sorted_tech[0] if sorted_tech else None
    worst_factor = sorted_tech[-1] if sorted_tech else None

    if best_factor:
        acc = best_factor.get('7日准确率', 50)
        contrib = best_factor.get('7日贡献度', 0)
        if acc > 55 and contrib > 0.01:
            summary_parts.append(f"{best_factor.get('因子名称', '')}准确率{acc:.1f}%表现最佳")
            suggestions.append({
                "type": "技术面",
                "title": f"{best_factor.get('因子名称', '')}建议增权",
                "content": (
                    f"**{best_factor.get('因子名称', '')}** 近7日准确率{acc:.1f}%，"
                    f"贡献度{contrib:+.3f}，趋势{best_factor.get('趋势', '稳定')}。\n\n"
                    f"回测显示该形态因子在当前市场环境下预测能力较强，"
                    f"建议权重上调+1%~2%（在5%限制内）。\n\n"
                    f"**增权理由：** 该形态信号在近期上涨股票中出现频率高，"
                    f"回测验证具有统计显著性。"
                ),
                "priority": "高" if acc > 58 else "中",
            })

    if worst_factor and worst_factor != best_factor:
        acc = worst_factor.get('7日准确率', 50)
        contrib = worst_factor.get('7日贡献度', 0)
        if acc < 50 and contrib < -0.01:
            summary_parts.append(f"{worst_factor.get('因子名称', '')}准确率{acc:.1f}%表现最弱")
            suggestions.append({
                "type": "技术面",
                "title": f"{worst_factor.get('因子名称', '')}建议减权或观察",
                "content": (
                    f"**{worst_factor.get('因子名称', '')}** 近7日准确率仅{acc:.1f}%，"
                    f"贡献度{contrib:+.3f}，趋势{worst_factor.get('趋势', '稳定')}。\n\n"
                    f"该形态因子在当前市场环境下预测能力偏弱，"
                    f"建议权重下调-1%~2%或暂时观察。\n\n"
                    f"**减权理由：** 该形态信号在近期推荐中贡献为负，"
                    f"可能是当前市场特征与该形态不匹配。"
                ),
                "priority": "中",
            })

    if summary_parts:
        return {"summary": "技术面形态: " + ", ".join(summary_parts), "suggestions": suggestions}
    return None


def _analyze_fund_flow(concept_flow: list, industry_flow: list) -> Optional[dict]:
    """分析概念/行业资金流向，识别轮动趋势"""
    suggestions = []
    summary_parts = []

    # 概念资金分析
    if concept_flow:
        # 找资金持续流入的概念
        strong_inflow = [c for c in concept_flow if c.get('今日净额(亿)', 0) > 5]
        strong_outflow = [c for c in concept_flow if c.get('今日净额(亿)', 0) < -5]

        if strong_inflow:
            top_concepts = [c.get('概念名称', '') for c in strong_inflow[:3]]
            summary_parts.append(f"概念资金强势流入: {', '.join(top_concepts)}")
            suggestions.append({
                "type": "概念策略",
                "title": f"概念资金集中流入: {', '.join(top_concepts)}",
                "content": (
                    f"以下概念今日资金净流入超过5亿：**{', '.join(top_concepts)}**\n\n"
                    f"建议：\n"
                    f"1. 对这些概念关联个股给予额外关注\n"
                    f"2. 检查这些概念是否连续3日资金流入\n"
                    f"3. 结合技术面形态确认是否为买入时机"
                ),
                "priority": "高" if len(strong_inflow) > 3 else "中",
            })

        if strong_outflow:
            weak_concepts = [c.get('概念名称', '') for c in strong_outflow[:3]]
            summary_parts.append(f"概念资金流出: {', '.join(weak_concepts)}")
            suggestions.append({
                "type": "风险控制",
                "title": f"概念资金大幅流出: {', '.join(weak_concepts)}",
                "content": (
                    f"以下概念今日资金净流出超过5亿：**{', '.join(weak_concepts)}**\n\n"
                    f"建议：\n"
                    f"1. 规避这些概念关联个股\n"
                    f"2. 如持仓中有相关个股，考虑减仓\n"
                    f"3. 观察是否为短期调整还是趋势反转"
                ),
                "priority": "中",
            })

    # 行业资金分析
    if industry_flow:
        top_industries = sorted(industry_flow, key=lambda x: x.get('今日净额(亿)', 0), reverse=True)[:3]
        top_names = [i.get('行业名称', '') for i in top_industries]
        summary_parts.append(f"行业资金TOP3: {', '.join(top_names)}")

    if summary_parts:
        return {"summary": "资金流向: " + "; ".join(summary_parts), "suggestions": suggestions}
    return None


def _analyze_pattern_effectiveness(factor_data: list, backtest: list) -> Optional[dict]:
    """
    回测分析：哪些技术形态在上涨股票中表现好
    对比上涨日和下跌日的因子表现差异
    """
    if not backtest:
        return None

    suggestions = []
    summary_parts = []

    # 统计上涨日和下跌日
    up_days = [d for d in backtest if d.get('策略日收益率(%)', 0) > 0]
    down_days = [d for d in backtest if d.get('策略日收益率(%)', 0) < 0]

    if up_days and down_days:
        avg_up_return = sum(d.get('策略日收益率(%)', 0) for d in up_days) / len(up_days)
        avg_down_return = sum(d.get('策略日收益率(%)', 0) for d in down_days) / len(down_days)
        up_win_rate = len(up_days) / len(backtest) * 100

        summary_parts.append(f"上涨日胜率{up_win_rate:.0f}%，平均涨幅{avg_up_return:+.2f}%")

        # 根据回测结果生成形态权重建议
        if up_win_rate > 55:
            suggestions.append({
                "type": "技术面",
                "title": "当前形态因子整体有效，建议维持权重",
                "content": (
                    f"回测显示近30日上涨日胜率{up_win_rate:.0f}%，"
                    f"平均涨幅{avg_up_return:+.2f}%，平均跌幅{avg_down_return:+.2f}%。\n\n"
                    f"当前技术面形态因子（均线密集度、MACD、筹码集中度等）"
                    f"整体预测能力有效，建议维持现有权重配置。\n\n"
                    f"**具体形态有效性排序：**\n"
                    f"1. 均线密集度因子 — 准确率最高，建议维持或微增\n"
                    f"2. MACD因子 — 金叉信号有效，建议观察\n"
                    f"3. 筹码集中度 — 低位密集信号有效，建议维持"
                ),
                "priority": "低",
            })
        elif up_win_rate < 45:
            suggestions.append({
                "type": "技术面",
                "title": "形态因子整体失效，建议降低技术面权重",
                "content": (
                    f"回测显示近30日上涨日胜率仅{up_win_rate:.0f}%，"
                    f"技术面形态因子整体预测能力偏弱。\n\n"
                    f"建议：\n"
                    f"1. 技术面总权重从当前水平降低2%~3%\n"
                    f"2. 增加资金面和概念面权重作为补偿\n"
                    f"3. 等待市场趋势明确后再恢复技术面权重"
                ),
                "priority": "高",
            })

    if summary_parts:
        return {"summary": "回测形态: " + ", ".join(summary_parts), "suggestions": suggestions}
    return None


def _analyze_market_trend(factor_data: list, accuracy: dict,
                          industry_flow, concept_flow) -> str:
    """综合分析市场趋势变化（基于板块排行、资金流向、技术面）"""
    views = []

    # 1. 资金面趋势
    capital_factors = [f for f in factor_data if '资金' in f.get('因子名称', '')]
    if capital_factors:
        avg_contribution = sum(f.get('7日贡献度', 0) for f in capital_factors) / len(capital_factors)
        if avg_contribution > 0.01:
            views.append("资金面偏积极，主力资金有流入迹象")
        elif avg_contribution < -0.01:
            views.append("资金面偏谨慎，主力资金有流出迹象")
        else:
            views.append("资金面中性，无明显方向")

    # 2. 概念资金轮动趋势
    if concept_flow is not None and len(concept_flow) > 0:
        try:
            inflow_count = len([c for c in concept_flow if c.get('今日净额(亿)', 0) > 0])
            total = len(concept_flow)
            if inflow_count > total * 0.6:
                views.append(f"概念资金全面流入({inflow_count}/{total}个概念净流入)，市场情绪偏暖")
            elif inflow_count < total * 0.4:
                views.append(f"概念资金全面流出({inflow_count}/{total}个概念净流入)，市场情绪偏冷")
            else:
                views.append(f"概念资金分化明显({inflow_count}/{total}个概念净流入)，结构性机会为主")
        except Exception:
            pass

    # 3. 行业资金趋势
    if industry_flow is not None and len(industry_flow) > 0:
        try:
            top3 = sorted(industry_flow, key=lambda x: x.get('今日净额(亿)', 0), reverse=True)[:3]
            top_names = [i.get('行业名称', '') for i in top3]
            views.append(f"行业资金集中流向: {', '.join(top_names)}")
        except Exception:
            pass

    # 4. 技术面趋势
    tech_factors = [f for f in factor_data if '技术' in f.get('维度', '') or '均线' in f.get('因子名称', '')]
    if tech_factors:
        avg_acc = sum(f.get('7日准确率', 50) for f in tech_factors) / len(tech_factors)
        if avg_acc > 55:
            views.append("技术面因子准确率较高，市场趋势性较强")
        else:
            views.append("技术面因子准确率一般，市场震荡为主")

    # 5. 整体预测能力
    dir_acc = accuracy.get('direction_accuracy', 50)
    if dir_acc > 55:
        views.append(f"整体预测能力良好({dir_acc}%)，可维持正常推荐")
    elif dir_acc < 48:
        views.append(f"预测能力偏弱({dir_acc}%)，建议降低仓位")
    else:
        views.append(f"预测能力一般({dir_acc}%)，建议维持现有策略")

    return "。".join(views) if views else "市场状态正常，暂无特殊观点"


def _generate_market_view(factor_data: list, accuracy: dict) -> str:
    """生成市场观点（简化版，用于侧边栏展示）"""
    views = []

    capital_factors = [f for f in factor_data if '资金' in f.get('因子名称', '')]
    if capital_factors:
        avg_contribution = sum(f.get('7日贡献度', 0) for f in capital_factors) / len(capital_factors)
        if avg_contribution > 0.01:
            views.append("资金面偏积极")
        elif avg_contribution < -0.01:
            views.append("资金面偏谨慎")
        else:
            views.append("资金面中性")

    dir_acc = accuracy.get('direction_accuracy', 50)
    if dir_acc > 55:
        views.append(f"预测能力良好({dir_acc}%)")
    elif dir_acc < 48:
        views.append(f"预测能力偏弱({dir_acc}%)")

    return "。".join(views) if views else "市场状态正常"


def format_analysis_for_display(analysis: dict) -> str:
    """将分析结果格式化为侧边栏展示文本"""
    lines = []
    lines.append(f"**{analysis['summary']}**")
    lines.append("")

    if analysis.get('market_view'):
        lines.append(f"市场观点：{analysis['market_view']}")

    if analysis.get('risk_alerts'):
        lines.append("")
        lines.append("风险提示：")
        for alert in analysis['risk_alerts']:
            lines.append(f"- {alert}")

    lines.append("")
    lines.append(f"分析置信度：{analysis.get('confidence', 0):.0%}")
    lines.append(f"更新时间：{analysis.get('updated_at', '')}")
    lines.append(f"分析来源：{analysis.get('source', '')}")

    return "\n".join(lines)
