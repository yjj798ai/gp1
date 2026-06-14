#!/usr/bin/env python3
"""模拟交易引擎 - 按推荐自动买卖"""
import sqlite3, json
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"
INITIAL_CAPITAL = 10000.0
MAX_POSITIONS = 3           # 最多持仓3只（2000元买不了5只）
PER_TRADE_PCT = 0.30       # 每只股票占30%


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, action TEXT,
            code TEXT, name TEXT,
            price REAL, shares INTEGER,
            amount REAL, reason TEXT,
            review TEXT DEFAULT '',
            profit_pct REAL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS position (
            code TEXT PRIMARY KEY,
            name TEXT, buy_date TEXT,
            buy_price REAL, shares INTEGER,
            cost REAL, current_price REAL,
            market_value REAL,
            profit_pct REAL DEFAULT 0,
            reason TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS account (
            key TEXT PRIMARY KEY,
            value REAL
        )
    """)
    # 初始化账户
    conn.execute("INSERT OR IGNORE INTO account VALUES ('cash', ?)", (INITIAL_CAPITAL,))
    conn.execute("INSERT OR IGNORE INTO account VALUES ('initial_capital', ?)", (INITIAL_CAPITAL,))
    conn.commit()
    conn.close()


def get_cash():
    conn = sqlite3.connect(DB_PATH)
    cash = conn.execute("SELECT value FROM account WHERE key='cash'").fetchone()
    conn.close()
    return float(cash[0]) if cash else INITIAL_CAPITAL


def buy_stock(code, name, price, reason):
    """买入股票"""
    conn = sqlite3.connect(DB_PATH)
    cash = float(conn.execute("SELECT value FROM account WHERE key='cash'").fetchone()[0])
    positions = conn.execute("SELECT COUNT(*) FROM position").fetchone()[0]
    
    if positions >= MAX_POSITIONS:
        conn.close()
        return False, "已达最大持仓数"
    
    if price <= 0 or price > 20:
        conn.close()
        return False, "价格超出范围"
    
    # 计算可买股数（模拟盘允许1股，展示资金利用率）
    trade_amount = min(cash * PER_TRADE_PCT, cash)
    shares = int(trade_amount / price)  # 模拟盘：不限制100股
    if shares <= 0:
        conn.close()
        return False, "资金不足"
    
    cost = round(shares * price, 2)
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn.execute("INSERT OR REPLACE INTO position VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (code, name, today, price, shares, cost, price, cost, 0, reason))
    conn.execute("UPDATE account SET value=value-? WHERE key='cash'", (cost,))
    conn.execute("INSERT INTO trade_log (date, action, code, name, price, shares, amount, reason) VALUES (?,?,?,?,?,?,?,?)",
                 (today, 'buy', code, name, price, shares, cost, reason))
    
    conn.commit()
    conn.close()
    return True, f"买入{name} {shares}股 ¥{price}"


def sell_stock(code):
    """卖出股票"""
    conn = sqlite3.connect(DB_PATH)
    pos = conn.execute("SELECT * FROM position WHERE code=?", (code,)).fetchone()
    if not pos:
        conn.close()
        return False, "未持仓"
    
    name, buy_price, shares = pos[1], pos[3], pos[4]
    cost = pos[5]
    
    # 以当前价卖出
    row = conn.execute("""
        SELECT price FROM hot_rank_history 
        WHERE code=? AND date=(SELECT MAX(date) FROM hot_rank_history)
    """, (code,)).fetchone()
    sell_price = float(row[0]) if row else buy_price
    
    amount = round(sell_price * shares, 2)
    profit_pct = round((sell_price - buy_price) / buy_price * 100, 1)
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn.execute("DELETE FROM position WHERE code=?", (code,))
    conn.execute("UPDATE account SET value=value+? WHERE key='cash'", (amount,))
    conn.execute("""
        INSERT INTO trade_log (date, action, code, name, price, shares, amount, reason, profit_pct)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (today, 'sell', code, name, sell_price, shares, amount, f"止盈/止损", profit_pct))
    
    conn.commit()
    conn.close()
    return True, f"卖出{name} {shares}股 ¥{sell_price} (盈亏{profit_pct:+.1f}%)"


def update_positions():
    """更新持仓市值"""
    conn = sqlite3.connect(DB_PATH)
    today = conn.execute("SELECT MAX(date) FROM hot_rank_history").fetchone()
    today_str = today[0] if today else datetime.now().strftime("%Y-%m-%d")
    
    for pos in conn.execute("SELECT code, buy_price, shares, cost FROM position").fetchall():
        code, buy_price, shares, cost = pos
        row = conn.execute("""
            SELECT price FROM hot_rank_history 
            WHERE code=? AND date=? LIMIT 1
        """, (code, today_str)).fetchone()
        current_price = float(row[0]) if row else buy_price
        market_value = round(current_price * shares, 2)
        profit_pct = round((current_price - buy_price) / buy_price * 100, 1)
        
        conn.execute("""
            UPDATE position SET current_price=?, market_value=?, profit_pct=?
            WHERE code=?
        """, (current_price, market_value, profit_pct, code))
    
    conn.commit()
    conn.close()


def check_stop_loss():
    """检查止损条件"""
    conn = sqlite3.connect(DB_PATH)
    sold = []
    for pos in conn.execute("SELECT code, name, buy_price, profit_pct FROM position").fetchall():
        code, name, buy_price, profit_pct = pos
        if profit_pct <= -8:  # 止损线 -8%
            sold.append(sell_stock(code))
    conn.close()
    return sold


def auto_buy_from_recommendations():
    """从今日推荐自动买入（按价格排序，优先买便宜的）"""
    try:
        from src.engine.filter import run_filter_pipeline
        recs, _ = run_filter_pipeline(top_n=20)
    except:
        return []
    
    if recs.empty:
        return []
    
    # 按价格升序排列，优先买便宜的
    recs = recs.sort_values("当前价格")
    
    conn = sqlite3.connect(DB_PATH)
    existing = set(r[0] for r in conn.execute("SELECT code FROM position").fetchall())
    conn.close()
    
    results = []
    bought = 0
    for _, x in recs.iterrows():
        if bought >= MAX_POSITIONS:
            break
        code = x["股票代码"]
        if code in existing:
            continue
        name = x["股票名称"]
        price = float(x["当前价格"])
        reason = x.get("推荐理由", "")[:60]
        
        ok, msg = buy_stock(code, name, price, reason)
        if ok:
            bought += 1
        results.append(msg)
    
    return results


def get_portfolio_summary():
    """获取持仓概览"""
    conn = sqlite3.connect(DB_PATH)
    cash = float(conn.execute("SELECT value FROM account WHERE key='cash'").fetchone()[0])
    initial = float(conn.execute("SELECT value FROM account WHERE key='initial_capital'").fetchone()[0])
    positions = conn.execute("SELECT * FROM position").fetchall()
    trades = conn.execute("SELECT * FROM trade_log ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    
    position_value = sum(float(p[7] or 0) for p in positions)
    total_value = cash + position_value
    total_profit = round(total_value - initial, 2)
    profit_pct = round(total_profit / initial * 100, 1) if initial > 0 else 0
    
    return {
        "cash": round(cash, 2),
        "position_value": round(position_value, 2),
        "total_value": round(total_value, 2),
        "initial_capital": initial,
        "total_profit": total_profit,
        "profit_pct": profit_pct,
        "positions": positions,
        "trades": trades[:10],
    }


if __name__ == "__main__":
    import sys
    init_db()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--buy":
        results = auto_buy_from_recommendations()
        for r in results:
            print(r)
        print(f"\n当前现金: ¥{get_cash():.2f}")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--update":
        update_positions()
        summary = get_portfolio_summary()
        print(f"持仓市值: ¥{summary['position_value']}")
        print(f"总资产: ¥{summary['total_value']}")
        print(f"总盈亏: {summary['total_profit']:+.2f} ({summary['profit_pct']:+.1f}%)")
        print(f"持仓: {len(summary['positions'])}只")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--status":
        summary = get_portfolio_summary()
        print(f"💰 模拟交易账户")
        print(f"初始资金: ¥{summary['initial_capital']:.2f}")
        print(f"当前现金: ¥{summary['cash']:.2f}")
        print(f"持仓市值: ¥{summary['position_value']:.2f}")
        print(f"总资产:  ¥{summary['total_value']:.2f}")
        print(f"总盈亏:  {summary['total_profit']:+.2f} ({summary['profit_pct']:+.1f}%)")
        print(f"\n持仓明细:")
        for p in summary['positions']:
            print(f"  {p[1]:10s} 买入¥{p[3]:<6} 现价¥{p[6]:<6} {p[8]:+.1f}% {p[9][:40]}")
        print(f"\n最近交易:")
        for t in summary['trades']:
            print(f"  {t[1]} {t[2]:4s} {t[4]:10s} ¥{t[5]:<6} {t[6]:3d}股 {t[7]:.0f}元 {t[8][:30]}")
    
    else:
        print("用法: python trade_sim.py --buy|--update|--status")
