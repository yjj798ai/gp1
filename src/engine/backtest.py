# -*- coding: utf-8 -*-
"""
股神圣杯系统 — 回测引擎（简化版）
基于多因子评分引擎做 T+1 验证
"""
import sqlite3, os, json
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def get_available_dates():
    """获取有数据的日期列表"""
    conn = _connect()
    rows = conn.execute('SELECT DISTINCT date FROM hot_rank_history ORDER BY date').fetchall()
    conn.close()
    return [r[0] for r in rows]


def run_simple_backtest(top_n=10):
    """
    简单回测：对每个有数据的日期，评分选Top N，验证次日涨跌
    
    返回:
    {
        "total_days": N,
        "total_picks": N, 
        "win_rate": 0.55,
        "avg_return": 0.02,
        "cumulative_return": 0.5,
        "max_drawdown": -0.05,
        "daily_results": [...],
        "simulated_portfolio": {...}
    }
    """
    dates = get_available_dates()
    if len(dates) < 2:
        return {"error": "数据不足，至少需要2个交易日"}
    
    from src.engine.scoring import compute_stock_score
    
    all_returns = []
    daily_results = []
    total_picks = 0
    wins = 0
    
    for i, date in enumerate(dates):
        # 跳过最后一天（没有次日数据）
        if i >= len(dates) - 1:
            break
        
        next_date = dates[i + 1]
        
        conn = _connect()
        rows = conn.execute('''
            SELECT h.code, h.rank, h.price, h.change_pct,
                   COALESCE(s.name, h.code) as name,
                   COALESCE(s.market_cap, 0) as mcap
            FROM hot_rank_history h
            LEFT JOIN stocks s ON h.code = s.code
            WHERE h.date = ? AND h.rank IS NOT NULL
            ORDER BY h.rank
        ''', (date,)).fetchall()
        
        scored = []
        for r in rows:
            code = r['code'] or ''
            if code.startswith(('8', '4', '920')): continue
            name = r['name'] or code
            if 'ST' in name.upper(): continue
            price = float(r['price'] or 0)
            if price <= 0: continue
            
            result = compute_stock_score(
                code=code,
                rank=int(r['rank'] or 999),
                price=price,
                change_pct=float(r['change_pct'] or 0),
                market_cap=float(r['mcap'] or 0),
            )
            scored.append({
                'code': code, 'name': name,
                'price': price, 'score': result['total_score'],
                'direction': result['direction'],
            })
        
        conn.close()
        
        # 取Top N
        scored.sort(key=lambda x: -x['score'])
        top_picks = scored[:top_n]
        
        # 验证次日涨跌
        conn = _connect()
        day_returns = []
        for pick in top_picks:
            row = conn.execute(
                'SELECT change_pct FROM hot_rank_history WHERE code=? AND date=?',
                (pick['code'], next_date)
            ).fetchone()
            actual = float(row[0]) if row and row[0] else 0
            win = actual > 0
            day_returns.append({
                'code': pick['code'], 'name': pick['name'],
                'score': pick['score'], 'price': pick['price'],
                'actual_return': round(actual, 2), 'win': win,
            })
            all_returns.append(actual)
            if win: wins += 1
            total_picks += 1
        
        conn.close()
        
        avg_ret = round(sum(r['actual_return'] for r in day_returns) / len(day_returns), 2) if day_returns else 0
        win_rate = round(sum(1 for r in day_returns if r['win']) / len(day_returns), 2) if day_returns else 0
        
        daily_results.append({
            'date': date,
            'next_date': next_date,
            'picks': len(day_returns),
            'avg_return': avg_ret,
            'win_rate': win_rate,
            'best': max(day_returns, key=lambda x: x['actual_return']) if day_returns else {},
            'worst': min(day_returns, key=lambda x: x['actual_return']) if day_returns else {},
        })
    
    # 计算总指标
    if total_picks == 0:
        return {"error": "无有效回测结果"}
    
    # 最大回撤
    peak = 0
    max_dd = 0
    cum = 0
    for r in all_returns:
        cum += r
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    
    summary = {
        "total_days": len(daily_results),
        "total_picks": total_picks,
        "win_count": wins,
        "win_rate": round(wins / total_picks, 4),
        "avg_return": round(sum(all_returns) / total_picks, 4),
        "cumulative_return": round(sum(all_returns), 2),
        "max_drawdown": round(max_dd, 2),
        "daily_results": daily_results,
    }
    
    return summary


def get_portfolio_from_backtest(top_n=5, initial_capital=2000.0):
    """
    基于回测结果生成模拟盘状态
    
    返回: dict (与 generate_portfolio 格式兼容)
    """
    result = run_simple_backtest(top_n=top_n)
    
    if result.get("error"):
        return {
            "initial_capital": initial_capital,
            "net_value": 1.0,
            "return_pct": 0.0,
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
            "total_market_value": 0.0,
            "total_cost": 0.0,
            "position_count": 0,
            "cash": initial_capital,
            "backtest_result": result,
            "positions": [],
        }
    
    # 模拟净值
    total_return = result["cumulative_return"]
    net_value = round(1.0 + total_return / 100, 4)
    return_pct = round(total_return, 2)
    total_pnl = round(initial_capital * total_return / 100, 2)
    
    # 生成持仓示例
    import pandas as pd
    positions = []
    if result["daily_results"]:
        last = result["daily_results"][-1]
        if last.get("best") and last["best"].get("code"):
            for pick_data in [last.get("best", {}), last.get("worst", {})]:
                if pick_data.get("code"):
                    code = pick_data["code"]
                    # 统一查询板块
                    sector = "其他"
                    try:
                        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                        from src.data.real_data import get_stock_sector
                        sector = get_stock_sector(code)
                    except:
                        pass
                    
                    positions.append({
                        "股票代码": code,
                        "股票名称": pick_data.get("name", "未知"),
                        "所属板块": sector,
                        "买入价格": pick_data.get("price", 0),
                        "当前价格": round(pick_data.get("price", 0) * (1 + pick_data.get("actual_return", 0) / 100), 2),
                        "持有数量": 100,
                        "成本": round(pick_data.get("price", 0) * 100, 2),
                        "市值": round(pick_data.get("price", 0) * 100, 2),
                        "盈亏": round(pick_data.get("actual_return", 0) * pick_data.get("price", 0), 2),
                        "盈亏比例(%)": pick_data.get("actual_return", 0),
                        "持有天数": 1,
                    })
    
    return {
        "initial_capital": initial_capital,
        "net_value": net_value,
        "return_pct": return_pct,
        "total_pnl": total_pnl,
        "total_pnl_pct": return_pct,
        "total_market_value": max(0, initial_capital + total_pnl - initial_capital * 0.5),
        "total_cost": initial_capital * 0.5,
        "position_count": len(positions),
        "cash": max(0, initial_capital - initial_capital * 0.5),
        "backtest_result": result,
        "positions": pd.DataFrame(positions),
    }
