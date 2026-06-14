# -*- coding: utf-8 -*-
"""
Cookie 管理模块 — 采集器认证信息配置
"""
import os, json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'gp_project', 'config.json')


def load_config() -> dict:
    """读取 config.json"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_config(cfg: dict):
    """保存 config.json"""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_cookie_info() -> dict:
    """返回 Cookie 状态摘要"""
    cfg = load_config()
    cookies = {
        "同花顺(ths_cookie)": {
            "status": "✅ 已配置" if cfg.get("ths_cookie") else "❌ 未配置",
            "exists": bool(cfg.get("ths_cookie")),
            "key": "ths_cookie",
            "hint": "用于: 排名数据、行业一览、板块资金流、实时价格",
            "source": "浏览器登录 10jqka.com.cn → F12 → Application → Cookies → 复制全部",
        },
        "韭研(jiuyan_cookie)": {
            "status": "✅ 已配置" if cfg.get("jiuyan_cookie") else "❌ 未配置",
            "exists": bool(cfg.get("jiuyan_cookie")),
            "key": "jiuyan_cookie",
            "hint": "用于: 大V文章热词采集",
            "source": "浏览器登录 jiuyangongshe.com → F12 → Application → Cookies → 复制全部",
        },
        "问财(iwencai_cookie)": {
            "status": "✅ 已配置" if cfg.get("iwencai_cookie") else "❌ 未配置",
            "exists": bool(cfg.get("iwencai_cookie")),
            "key": "iwencai_cookie",
            "hint": "用于: 问财热榜前200",
            "source": "浏览器登录 iwencai.com → F12 → Application → Cookies → 复制全部",
        },
        "选股通(xuangutong_token)": {
            "status": "✅ 已配置" if cfg.get("xuangutong_token") else "❌ 未配置",
            "exists": bool(cfg.get("xuangutong_token")),
            "key": "xuangutong_token",
            "hint": "用于: 选股通新闻快讯(baoer-api)",
            "source": "浏览器登录 xuangutong.com.cn → F12 → Network → 找baoer-api请求 → 复制x-ivanka-token",
        },
    }
    cfg_short = {k: "***已配置***" if v else "空" for k, v in {
        "ths_cookie": bool(cfg.get("ths_cookie")),
        "jiuyan_cookie": bool(cfg.get("jiuyan_cookie")),
        "iwencai_cookie": bool(cfg.get("iwencai_cookie")),
        "xuangutong_token": bool(cfg.get("xuangutong_token")),
        "jiuyan_users": len(cfg.get("jiuyan_users", [])),
    }.items()}
    return {"cookies": cookies, "summary": cfg_short}


def update_cookie(key: str, value: str) -> bool:
    """更新指定 Cookie"""
    valid_keys = ["ths_cookie", "jiuyan_cookie", "iwencai_cookie", "xuangutong_token"]
    if key not in valid_keys:
        return False
    cfg = load_config()
    cfg[key] = value.strip()
    save_config(cfg)
    return True


def get_cookie_value(key: str) -> str:
    """读取指定 Cookie 值（用于采集器调用）"""
    cfg = load_config()
    return cfg.get(key, "")


def get_jiuyan_users() -> list:
    """读取韭研用户列表"""
    cfg = load_config()
    return cfg.get("jiuyan_users", [])
