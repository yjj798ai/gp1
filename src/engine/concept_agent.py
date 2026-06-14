# -*- coding: utf-8 -*-
"""概念Agent — 独立概念评分模块

从现有评分代码提取概念因子，封装为独立类
输出: 概念评分 + 因子明细
"""
import sqlite3
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


class ConceptAgent:
    """概念评分Agent — 评估个股的概念热度与新鲜度"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def get_hot_concepts(self, top_n=15) -> list:
        """获取当前热门概念（来自同花顺热门榜）"""
        try:
            conn = self._connect()
            rows = conn.execute("""
                SELECT concepts FROM ths_hot_stocks
                WHERE date=(SELECT MAX(date) FROM ths_hot_stocks)
                AND concepts IS NOT NULL
            """).fetchall()
            conn.close()

            weights = {}
            for row in rows:
                for c in (row[0] or "").split(","):
                    c = c.strip()
                    if c and len(c) >= 2:
                        weights[c] = weights.get(c, 0) + 1

            sorted_c = sorted(weights.items(), key=lambda x: -x[1])[:top_n]
            return [c[0] for c in sorted_c if c[1] >= 2]
        except Exception:
            return []

    def get_concept_freshness(self, concept_name: str) -> str:
        """判断概念新鲜度: 启动/爆发/持续/退潮/未知"""
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT days_on_list FROM ths_concept_rank WHERE name=? ORDER BY date DESC LIMIT 1",
                (concept_name,),
            ).fetchone()
            conn.close()

            if not row or not row[0]:
                return "未知"

            days = row[0]
            if days <= 1:
                return "启动"
            elif days <= 5:
                return "爆发"
            elif days <= 90:
                return "持续"
            else:
                return "退潮"
        except Exception:
            return "未知"

    def match_stock_concepts(self, code: str) -> list:
        """匹配个股关联概念"""
        try:
            conn = self._connect()
            concepts = set()

            for table, col in [
                ("stock_concepts", "concept"),
                ("stocks", "concept_primary"),
                ("ths_hot_stocks", "concepts"),
            ]:
                try:
                    for r in conn.execute(
                        f"SELECT {col} FROM {table} WHERE code=?",
                        (code,),
                    ).fetchall():
                        val = r[0] or ""
                        for c in val.split(","):
                            c = c.strip()
                            if c and len(c) >= 2:
                                concepts.add(c)
                except Exception:
                    pass

            conn.close()
            return list(concepts)
        except Exception:
            return []

    def score_concepts(self, concepts: list) -> dict:
        """概念评分: 数量分 + 新鲜度分 + 板块支撑分

        返回:
        {
            "total_score": 0~40,
            "count_score": 0~20,
            "freshness_score": -3~6,
            "sector_score": 0~14,
            "detail": {...},
        }
        """
        if not concepts:
            return {
                "total_score": 0, "count_score": 0,
                "freshness_score": 0, "sector_score": 0,
                "detail": {"concepts": [], "freshness": "未知"},
            }

        # 1. 概念数量分 (0~20)
        n = len(concepts)
        if n >= 8:
            count_score = 20
        elif n >= 5:
            count_score = 18
        elif n >= 3:
            count_score = 12
        elif n >= 2:
            count_score = 10
        else:
            count_score = 6

        # 2. 概念新鲜度分 (-3~6)
        primary = concepts[0] if concepts else ""
        freshness = self.get_concept_freshness(primary)
        if freshness == "启动":
            freshness_score = 6
        elif freshness == "爆发":
            freshness_score = 4
        elif freshness == "退潮":
            freshness_score = -3
        else:
            freshness_score = 0

        # 3. 板块支撑分 (0~14)
        sector_score = 0
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT fund_flow_today, limit_up FROM xuangutong_cards WHERE concept LIKE ? ORDER BY date DESC LIMIT 1",
                (f"%{primary}%",),
            ).fetchone()
            conn.close()
            if row:
                fund = abs(float(row[0] or 0))
                limit = int(row[1] or 0)
                sector_score = min(fund / 2, 10) + min(limit * 2, 4)
        except Exception:
            pass

        total = count_score + freshness_score + sector_score

        return {
            "total_score": max(0, total),
            "count_score": count_score,
            "freshness_score": freshness_score,
            "sector_score": sector_score,
            "detail": {
                "concepts": concepts[:5],
                "freshness": freshness,
                "primary": primary,
            },
        }

    def evaluate_stock(self, code: str) -> dict:
        """评估单只股票的概念得分

        返回: {
            "code": "000001",
            "concepts": [...],
            "score": {...},
        }
        """
        concepts = self.match_stock_concepts(code)
        score = self.score_concepts(concepts)
        return {"code": code, "concepts": concepts, "score": score}

    def batch_evaluate(self, codes: list) -> list:
        """批量评估多只股票"""
        results = []
        for code in codes:
            results.append(self.evaluate_stock(code))
        return results


if __name__ == "__main__":
    agent = ConceptAgent()

    print("=== 热门概念 ===")
    hot = agent.get_hot_concepts()
    for i, c in enumerate(hot[:10]):
        f = agent.get_concept_freshness(c)
        print(f"  {i+1}. {c} ({f})")

    print("\n=== 示例评估 ===")
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    sample = [r[0] for r in conn.execute(
        "SELECT code FROM stocks WHERE price>0 AND price<=20 LIMIT 5"
    ).fetchall()]
    conn.close()

    for code in sample:
        r = agent.evaluate_stock(code)
        s = r["score"]
        print(f"  {code}: 总分{s['total_score']} 数量{s['count_score']} "
              f"新鲜度{s['freshness_score']}({s['detail']['freshness']}) "
              f"板块{s['sector_score']}")
