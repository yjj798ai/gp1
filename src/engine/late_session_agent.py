# -*- coding: utf-8 -*-
"""尾盘选股Agent — 14:30八步筛选法

八步筛选:
  1. 涨幅3~5%
  2. 量比≥1
  3. 换手率5~10%
  4. 市值50~200亿
  5. 成交量递增
  6. 均线多头
  7. 分时均线上方
  8. 热点匹配
"""
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


class LateSessionAgent:
    """尾盘选股Agent — 14:30后执行八步筛选"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _step1_change_pct(self, stock, lo=3.0, hi=5.0):
        """步骤1: 涨幅3~5%"""
        chg = float(stock.get("change_pct", 0) or 0)
        return lo <= chg <= hi, chg

    def _step2_volume_ratio(self, stock, min_ratio=1.0):
        """步骤2: 量比≥1"""
        vr = float(stock.get("volume_ratio", 0) or 0)
        return vr >= min_ratio, vr

    def _step3_turnover_rate(self, stock, lo=5.0, hi=10.0):
        """步骤3: 换手率5~10%"""
        tr = float(stock.get("turnover_rate", 0) or 0)
        return lo <= tr <= hi, tr

    def _step4_market_cap(self, stock, lo=50.0, hi=200.0):
        """步骤4: 市值50~200亿"""
        mc = float(stock.get("market_cap", 0) or 0)
        return lo <= mc <= hi, mc

    def _step5_volume_increasing(self, code, days=5):
        """步骤5: 成交量递增"""
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT volume FROM price_5d WHERE code=? ORDER BY date DESC LIMIT ?",
                (code, days),
            ).fetchall()
            conn.close()

            vols = [float(r[0] or 0) for r in rows if r[0]]
            if len(vols) < 3:
                return False, 0

            recent = sum(vols[:len(vols)//2]) / max(len(vols)//2, 1)
            older = sum(vols[len(vols)//2:]) / max(len(vols) - len(vols)//2, 1)
            if older <= 0:
                return False, 0

            ratio = recent / older
            return ratio > 1.0, round(ratio, 2)
        except Exception:
            return False, 0

    def _step6_ma_bull(self, stock):
        """步骤6: 均线多头"""
        ma5 = float(stock.get("ma5", 0) or 0)
        ma10 = float(stock.get("ma10", 0) or 0)
        ma20 = float(stock.get("ma20", 0) or 0)
        ma_bull = stock.get("ma_bull", 0)
        if ma_bull:
            return True, f"MA5>{ma5:.2f} MA10>{ma10:.2f} MA20>{ma20:.2f}"
        if ma5 > ma10 > ma20 and ma5 > 0:
            return True, f"MA5>{ma5:.2f} MA10>{ma10:.2f} MA20>{ma20:.2f}"
        return False, f"MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f}"

    def _step7_above_vwap(self, stock):
        """步骤7: 分时均线上方（用当日均价与收盘价近似判断）"""
        price = float(stock.get("price", 0) or 0)
        avg_price = float(stock.get("avg_price", 0) or 0)
        if avg_price <= 0:
            avg_price = float(stock.get("vwap", 0) or 0)
        if avg_price <= 0:
            return None, "无均价数据"
        return price >= avg_price, f"价格{price:.2f} vs 均价{avg_price:.2f}"

    def _step8_hot_match(self, code):
        """步骤8: 热点匹配"""
        try:
            conn = self._connect()

            stock_concepts = set()
            for table, col in [
                ("stock_concepts", "concept"),
                ("stocks", "concept_primary"),
                ("ths_hot_stocks", "concepts"),
            ]:
                try:
                    for r in conn.execute(
                        f"SELECT {col} FROM {table} WHERE code=?", (code,)
                    ).fetchall():
                        for c in (r[0] or "").split(","):
                            c = c.strip()
                            if c and len(c) >= 2:
                                stock_concepts.add(c)
                except Exception:
                    pass

            if not stock_concepts:
                conn.close()
                return 0, []

            hot_rows = conn.execute(
                "SELECT concepts FROM ths_hot_stocks "
                "WHERE date=(SELECT MAX(date) FROM ths_hot_stocks) AND concepts IS NOT NULL"
            ).fetchall()
            conn.close()

            hot_weights = {}
            for row in hot_rows:
                for c in (row[0] or "").split(","):
                    c = c.strip()
                    if c and len(c) >= 2:
                        hot_weights[c] = hot_weights.get(c, 0) + 1

            matched = [c for c in stock_concepts if hot_weights.get(c, 0) >= 2]
            return len(matched), matched
        except Exception:
            return 0, []

    def evaluate_stock(self, code, stock=None):
        """评估单只股票，返回八步结果 + 综合评分"""
        if stock is None:
            try:
                conn = self._connect()
                row = conn.execute("SELECT * FROM stocks WHERE code=?", (code,)).fetchone()
                conn.close()
                if not row:
                    return None
                stock = dict(row)
            except Exception:
                return None

        steps = []
        passed = 0
        total = 8
        score = 0

        ok, val = self._step1_change_pct(stock)
        steps.append({"step": 1, "name": "涨幅3~5%", "pass": ok, "value": f"{val:.2f}%", "score": 15 if ok else 0})
        if ok:
            passed += 1; score += 15

        ok, val = self._step2_volume_ratio(stock)
        steps.append({"step": 2, "name": "量比≥1", "pass": ok, "value": f"{val:.2f}", "score": 12 if ok else 0})
        if ok:
            passed += 1; score += 12

        ok, val = self._step3_turnover_rate(stock)
        steps.append({"step": 3, "name": "换手率5~10%", "pass": ok, "value": f"{val:.2f}%", "score": 12 if ok else 0})
        if ok:
            passed += 1; score += 12

        ok, val = self._step4_market_cap(stock)
        steps.append({"step": 4, "name": "市值50~200亿", "pass": ok, "value": f"{val:.0f}亿", "score": 12 if ok else 0})
        if ok:
            passed += 1; score += 12

        ok, val = self._step5_volume_increasing(code)
        steps.append({"step": 5, "name": "成交量递增", "pass": ok, "value": f"{val:.2f}x", "score": 12 if ok else 0})
        if ok:
            passed += 1; score += 12

        ok, val = self._step6_ma_bull(stock)
        steps.append({"step": 6, "name": "均线多头", "pass": ok, "value": val, "score": 12 if ok else 0})
        if ok:
            passed += 1; score += 12

        ok, val = self._step7_above_vwap(stock)
        steps.append({"step": 7, "name": "分时均线上方", "pass": ok, "value": val, "score": 10 if ok else 0})
        if ok:
            passed += 1; score += 10

        cnt, matched = self._step8_hot_match(code)
        ok = cnt > 0
        steps.append({"step": 8, "name": "热点匹配", "pass": ok, "value": ", ".join(matched[:3]) if matched else "无", "score": 15 if ok else 0})
        if ok:
            passed += 1; score += 15

        return {
            "code": code,
            "name": stock.get("name", code),
            "price": float(stock.get("price", 0) or 0),
            "change_pct": float(stock.get("change_pct", 0) or 0),
            "passed_steps": passed,
            "total_steps": total,
            "score": score,
            "steps": steps,
            "hot_concepts": matched,
            "verdict": "强烈推荐" if passed >= 7 else ("推荐" if passed >= 5 else ("观望" if passed >= 3 else "不推荐")),
        }

    def run_screening(self, top_n=10):
        """执行尾盘八步筛选

        返回: (DataFrame, stats)
        """
        try:
            conn = self._connect()

            candidates = conn.execute("""
                SELECT s.* FROM stocks s
                WHERE s.price > 0 AND s.price <= 50
                  AND s.change_pct BETWEEN -1 AND 9.9
                ORDER BY s.change_pct DESC
            """).fetchall()
            conn.close()

            results = []
            for row in candidates:
                stock = dict(row)
                code = stock.get("code", "")
                if code.startswith(("688", "8", "4", "920")):
                    continue
                name = stock.get("name", "")
                if name and ("ST" in name or "*ST" in name):
                    continue

                ev = self.evaluate_stock(code, stock)
                if ev and ev["passed_steps"] >= 3:
                    results.append(ev)

            results.sort(key=lambda x: (-x["score"], -x["passed_steps"]))

            if not results:
                return pd.DataFrame(), {"total_candidates": 0, "qualified": 0}

            records = []
            for r in results[:top_n]:
                passed_names = [s["name"] for s in r["steps"] if s["pass"]]
                records.append({
                    "股票代码": r["code"],
                    "股票名称": r["name"],
                    "当前价格": r["price"],
                    "涨跌幅(%)": round(r["change_pct"], 2),
                    "通过步骤": f"{r['passed_steps']}/{r['total_steps']}",
                    "通过明细": ", ".join(passed_names),
                    "综合评分": r["score"],
                    "筛选结论": r["verdict"],
                    "热点概念": ", ".join(r["hot_concepts"][:3]),
                })

            df = pd.DataFrame(records)
            stats = {
                "total_candidates": len(candidates),
                "qualified": len(results),
                "returned": len(df),
            }
            return df, stats

        except Exception as e:
            return pd.DataFrame(), {"error": str(e)}


if __name__ == "__main__":
    agent = LateSessionAgent()
    df, stats = agent.run_screening(top_n=5)
    print(f"筛选完成: {stats}")
    if not df.empty:
        print(df.to_string(index=False))
