# -*- coding: utf-8 -*-
"""辩论机制 — 概念Agent vs 技术Agent

差值<=10 -> 取平均
差值>30 -> 按历史胜率加权
中间值 -> 按胜率加权
记录辩论日志
"""
import sqlite3
from datetime import datetime

DB_PATH = "E:/AI/gp1/a13/hot_rank.db"


class DebateEngine:
    """辩论引擎 — 融合概念评分和技术评分"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化辩论日志表"""
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS debate_log (
                date TEXT,
                code TEXT,
                concept_score REAL,
                tech_score REAL,
                diff REAL,
                method TEXT,
                concept_weight REAL,
                tech_weight REAL,
                final_score REAL,
                PRIMARY KEY (date, code)
            )
        """)
        conn.commit()
        conn.close()

    def get_win_rates(self) -> dict:
        """获取历史胜率"""
        try:
            conn = self._connect()
            rows = conn.execute("""
                SELECT code, concept_score, tech_score, final_score
                FROM debate_log
                WHERE date >= date('now', '-30 days')
            """).fetchall()
            conn.close()

            if not rows:
                return {"concept": 0.5, "tech": 0.5}

            concept_wins = 0
            tech_wins = 0
            for r in rows:
                cs = r[1] or 0
                ts = r[2] or 0
                if cs > ts:
                    concept_wins += 1
                elif ts > cs:
                    tech_wins += 1

            total = concept_wins + tech_wins
            if total == 0:
                return {"concept": 0.5, "tech": 0.5}

            return {
                "concept": concept_wins / total,
                "tech": tech_wins / total,
            }
        except Exception:
            return {"concept": 0.5, "tech": 0.5}

    def debate(self, concept_score: float, tech_score: float, code: str = "") -> dict:
        """辩论: 融合两个Agent的评分

        规则:
          差值<=10 -> 取平均
          10<差值<=30 -> 按胜率加权
          差值>30 -> 按胜率加权(更极端)

        返回: {
            "final_score": 融合后分数,
            "method": 使用的融合方法,
            "concept_weight": 概念权重,
            "tech_weight": 技术权重,
            "diff": 两分差值,
        }
        """
        diff = abs(concept_score - tech_score)
        win_rates = self.get_win_rates()
        cw = win_rates["concept"]
        tw = win_rates["tech"]

        if diff <= 10:
            # 差值小: 取平均
            final = (concept_score + tech_score) / 2
            method = "average"
            cw, tw = 0.5, 0.5
        elif diff <= 30:
            # 差值中: 按胜率加权
            total = cw + tw
            if total > 0:
                cw_norm = cw / total
                tw_norm = tw / total
            else:
                cw_norm, tw_norm = 0.5, 0.5
            final = concept_score * cw_norm + tech_score * tw_norm
            method = "weighted"
            cw, tw = cw_norm, tw_norm
        else:
            # 差值大: 更极端的加权
            total = cw + tw
            if total > 0:
                cw_norm = cw / total
                tw_norm = tw / total
            else:
                cw_norm, tw_norm = 0.5, 0.5
            # 放大权重差异
            cw_extreme = cw_norm ** 2 / (cw_norm ** 2 + tw_norm ** 2)
            tw_extreme = 1 - cw_extreme
            final = concept_score * cw_extreme + tech_score * tw_extreme
            method = "extreme_weighted"
            cw, tw = cw_extreme, tw_extreme

        # 记录日志
        if code:
            self._log_debate(code, concept_score, tech_score, diff, method, cw, tw, final)

        return {
            "final_score": round(final, 1),
            "method": method,
            "concept_weight": round(cw, 3),
            "tech_weight": round(tw, 3),
            "diff": round(diff, 1),
        }

    def _log_debate(self, code, cs, ts, diff, method, cw, tw, final):
        """记录辩论日志"""
        try:
            conn = self._connect()
            today = datetime.now().strftime("%Y-%m-%d")
            conn.execute("""
                INSERT OR REPLACE INTO debate_log
                (date, code, concept_score, tech_score, diff, method, concept_weight, tech_weight, final_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (today, code, cs, ts, diff, method, cw, tw, final))
            conn.commit()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    engine = DebateEngine()

    # 测试不同场景
    tests = [
        ("接近", 70, 65),
        ("中等", 80, 50),
        ("极端", 90, 30),
        ("反向", 40, 85),
    ]

    for name, cs, ts in tests:
        r = engine.debate(cs, ts)
        print(f"[{name}] 概念{cs} vs 技术{ts} -> {r['final_score']}分 ({r['method']})")
