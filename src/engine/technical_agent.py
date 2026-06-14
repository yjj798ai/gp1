# -*- coding: utf-8 -*-
"""技术Agent — 独立技术评分模块

从 stocks/price_5d/hour_rank_snapshot 读取数据
输出: 技术评分(100分制) + 因子明细
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


class TechnicalAgent:
    """技术评分Agent — 评估个股的技术面"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_stock(self, code: str) -> dict:
        """读取stocks表基础数据"""
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT * FROM stocks WHERE code=?", (code,)
            ).fetchone()
            conn.close()
            if not row:
                return {}
            return dict(row)
        except Exception:
            return {}

    def _get_volume_trend(self, code: str, days=5) -> float:
        """成交量趋势: 近N天成交量是否递增"""
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT volume FROM price_5d WHERE code=? ORDER BY date DESC LIMIT ?",
                (code, days),
            ).fetchall()
            conn.close()

            vols = [float(r[0] or 0) for r in rows if r[0]]
            if len(vols) < 2:
                return 0

            # 近期平均 vs 更早期平均
            mid = len(vols) // 2
            recent = sum(vols[:mid]) / max(mid, 1)
            older = sum(vols[mid:]) / max(len(vols) - mid, 1)

            if older <= 0:
                return 0
            return (recent - older) / older
        except Exception:
            return 0

    def _get_rank_trend(self, code: str) -> dict:
        """排名趋势: 从hour_rank_snapshot读取"""
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT hour_order, hot_rank_chg FROM hour_rank_snapshot WHERE code=? ORDER BY time DESC LIMIT 5",
                (code,),
            ).fetchall()
            conn.close()

            if not rows:
                return {"trend": 0, "chg": 0}

            latest_chg = rows[0][1] or 0
            avg_chg = sum(r[1] or 0 for r in rows) / len(rows)
            return {"trend": avg_chg, "chg": latest_chg}
        except Exception:
            return {"trend": 0, "chg": 0}

    def score(self, code: str) -> dict:
        """技术评分 — 7维度, 满分100

        维度:
          趋势分  20  排名连续上升天数
          均线分  20  MA5>MA10>MA20多头
          量价分  15  量比>=1 + 成交量递增
          价位分  15  价格<=20元
          市值分  10  50~200亿最佳
          换手率分 10  5%~10%最佳
          形态分  10  额外加分

        返回: {"total_score", "factors", "detail"}
        """
        stock = self._get_stock(code)
        if not stock:
            return {"total_score": 0, "factors": {}, "detail": "无数据"}

        factors = {}
        price = stock.get("price", 0) or 0
        ma5 = stock.get("ma5", 0) or 0
        ma10 = stock.get("ma10", 0) or 0
        ma20 = stock.get("ma20", 0) or 0
        ma_bull = stock.get("ma_bull", 0) or 0
        volume_ratio = stock.get("volume_ratio", 0) or 0
        turnover_rate = stock.get("turnover_rate", 0) or 0
        market_cap = stock.get("market_cap", 0) or 0
        change_pct = stock.get("change_pct", 0) or 0

        # 1. 趋势分 (0~20)
        rank_info = self._get_rank_trend(code)
        trend_val = rank_info["trend"]
        if trend_val > 50:
            trend_score = 20
        elif trend_val > 20:
            trend_score = 15
        elif trend_val > 0:
            trend_score = 10
        elif trend_val > -20:
            trend_score = 5
        else:
            trend_score = 0
        factors["趋势分"] = {
            "score": trend_score, "weight": 0.20,
            "detail": f"排名趋势{trend_val:+.0f}",
        }

        # 2. 均线分 (0~20)
        if ma_bull and ma5 > 0:
            spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
            if spread > 5:
                ma_score = 20
            elif spread > 3:
                ma_score = 16
            elif spread > 1:
                ma_score = 12
            else:
                ma_score = 8
        elif ma5 > ma10 and ma5 > 0:
            ma_score = 6
        elif ma5 > 0:
            ma_score = 3
        else:
            ma_score = 0
        factors["均线分"] = {
            "score": ma_score, "weight": 0.20,
            "detail": "多头排列" if ma_bull else ("短期偏多" if ma5 > ma10 else "偏空"),
        }

        # 3. 量价分 (0~15)
        vol_trend = self._get_volume_trend(code)
        if volume_ratio >= 1 and vol_trend > 0:
            vol_score = 15
        elif volume_ratio >= 1:
            vol_score = 10
        elif vol_trend > 0:
            vol_score = 8
        elif volume_ratio >= 0.5:
            vol_score = 5
        else:
            vol_score = 2
        factors["量价分"] = {
            "score": vol_score, "weight": 0.15,
            "detail": f"量比{volume_ratio:.2f} 趋势{vol_trend:+.1%}",
        }

        # 4. 价位分 (0~15)
        if price <= 5:
            price_score = 15
        elif price <= 10:
            price_score = 12
        elif price <= 15:
            price_score = 8
        elif price <= 20:
            price_score = 5
        else:
            price_score = 0
        factors["价位分"] = {
            "score": price_score, "weight": 0.15,
            "detail": f"{price:.2f}元",
        }

        # 5. 市值分 (0~10)
        if 50 <= market_cap <= 200:
            mcap_score = 10
        elif 30 <= market_cap < 50 or 200 < market_cap <= 500:
            mcap_score = 7
        elif market_cap > 0:
            mcap_score = 4
        else:
            mcap_score = 3
        factors["市值分"] = {
            "score": mcap_score, "weight": 0.10,
            "detail": f"{market_cap:.0f}亿",
        }

        # 6. 换手率分 (0~10)
        if 5 <= turnover_rate <= 10:
            turnover_score = 10
        elif 3 <= turnover_rate < 5 or 10 < turnover_rate <= 15:
            turnover_score = 7
        elif turnover_rate > 0:
            turnover_score = 4
        else:
            turnover_score = 0
        factors["换手率分"] = {
            "score": turnover_score, "weight": 0.10,
            "detail": f"{turnover_rate:.2f}%",
        }

        # 7. 形态分 (0~10) — 涨幅适中+量价配合
        shape_score = 0
        if 0 < change_pct <= 5:
            shape_score += 5
        elif 5 < change_pct <= 9.9:
            shape_score += 3
        if volume_ratio > 1.5 and vol_trend > 0:
            shape_score += 5
        elif volume_ratio > 1:
            shape_score += 3
        shape_score = min(10, shape_score)
        factors["形态分"] = {
            "score": shape_score, "weight": 0.10,
            "detail": f"涨幅{change_pct:+.2f}%",
        }

        total = sum(f["score"] for f in factors.values())
        total = round(max(0, min(100, total)), 1)

        return {
            "total_score": total,
            "factors": factors,
            "detail": stock.get("name", code),
        }

    def evaluate_stock(self, code: str) -> dict:
        """评估单只股票"""
        return {"code": code, **self.score(code)}

    def batch_evaluate(self, codes: list) -> list:
        """批量评估"""
        return [self.evaluate_stock(c) for c in codes]


if __name__ == "__main__":
    agent = TechnicalAgent()

    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    sample = [r[0] for r in conn.execute(
        "SELECT code FROM stocks WHERE ma_bull=1 AND price>0 AND price<=20 LIMIT 5"
    ).fetchall()]
    conn.close()

    for code in sample:
        r = agent.evaluate_stock(code)
        print(f"{code} {r['detail']}: {r['total_score']}分")
        for k, v in r["factors"].items():
            print(f"  {k}: {v['score']} ({v['detail']})")
