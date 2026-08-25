# -*- coding: utf-8 -*-
"""岗位分类引擎：投递方向、地区优先级、公司类型标签、时间归一化。"""
import json
import os
import re
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT, "config.json")

_cfg = None


def _config():
    global _cfg
    if _cfg is None:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _cfg = json.load(f)
    return _cfg


# ---------- 投递方向 ----------

def _kw_pattern(kw):
    """英文缩写关键词加词边界（PE 不误伤 Specialist、PIE 不误伤 Pie 等）；中文按包含匹配。"""
    if re.fullmatch(r"[A-Za-z0-9]+", kw):
        return re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
    return re.compile(re.escape(kw), re.IGNORECASE)


def classify_direction(title: str, company: str = ""):
    """返回 (direction_key, label, priority)。主投硬件类优先匹配；不匹配返回空方向。"""
    cfg = _config()
    text = f"{title} {company}"
    # 先查 exclude 再查 include，避免"硬件测试工程师-器件方向"误判
    results = []
    for d in cfg["job_directions"]:
        if any(_kw_pattern(k).search(text) for k in d["exclude_keywords"]):
            continue
        hits = [k for k in d["keywords"] if _kw_pattern(k).search(text)]
        if hits:
            results.append((len(hits), hits, d))
    if not results:
        return None, "", ""
    # 命中关键词最多的方向胜出；并列时按配置顺序（主投在前）
    results.sort(key=lambda r: -r[0])
    best = results[0][2]
    return best["key"], best["label"], best["priority"]


# ---------- 地区 ----------

def classify_region(locations):
    """locations: list[str]。返回 primary/secondary/other/unknown。北京优先于上海。"""
    cfg = _config()
    if not locations:
        return "unknown"
    text = "".join(locations)
    if any(re.search(city, text) for city in cfg["regions"]["primary"]):
        return "primary"
    if any(re.search(city, text) for city in cfg["regions"]["secondary"]):
        return "secondary"
    # 有具体城市名但不是目标城市
    if re.search(r"[一-龥]{2,}", text):
        return "other"
    return "unknown"


def parse_locations(raw):
    """从字符串解析出城市列表，如 '北京·上海·深圳' → ['北京','上海','深圳']。"""
    if not raw:
        return []
    parts = re.split(r"[·,，/、\s|;；]+", raw.strip())
    cities = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 取末尾城市名：'北京市' → '北京'，'中国·上海' → '上海'
        m = re.search(r"([一-龥]{2,7}?)(?:市|省|地区)?$", p)
        if m:
            cities.append(m.group(1))
        else:
            cities.append(p)
    return cities


# ---------- 公司标签 ----------

def tag_company(company: str):
    """返回公司类型标签；不在名单内的公司返回 ''（仍收录，只是无标签）。"""
    cfg = _config()
    if not company:
        return ""
    for tag, names in cfg["company_tags"].items():
        for n in names:
            if n in company:
                return tag
    # 兜底关键词
    for tag, kws in cfg["company_tag_fallback"].items():
        for k in kws:
            if k.lower() in company.lower():
                return tag
    return ""


# ---------- 公司信息（总部/规模/行业） ----------

def company_info(company: str):
    """返回 (hq_city, size_bucket, industry)；未收录公司返回 ("", "", "")。
    名单在 config.json 的 company_info，人数为公开资料近似档位，仅供筛选参考。"""
    cfg = _config()
    if not company:
        return "", "", ""
    for c in cfg.get("company_info", []):
        for alias in c.get("match", []):
            if alias and alias in company:
                return c.get("hq", ""), c.get("size", ""), c.get("industry", "")
    return "", "", ""


# ---------- 时间归一化 ----------

def normalize_time(raw, now: datetime):
    """把各来源的时间字符串归一化为 'YYYY-MM-DD HH:MM'；无法解析返回 ''。"""
    if not raw:
        return ""
    raw = raw.strip()
    now = now.replace(tzinfo=None)
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?", raw)
    if m:
        base = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        m = re.search(r"(\d{1,2})[-/月](\d{1,2})日?", raw)
        if m:
            base = datetime(now.year, int(m.group(1)), int(m.group(2)))
            # 未来日期视为去年（跨年场景）
            if base > now + timedelta(days=1):
                base = base.replace(year=now.year - 1)
        else:
            rel = re.search(r"(今天|今日|昨天|昨日|刚刚|\d+分钟前|\d+小时前|\d+天前)", raw)
            if not rel:
                return ""
            r = rel.group(1)
            if "天前" in r:
                base = now - timedelta(days=int(re.search(r"\d+", r).group()))
            elif "小时前" in r:
                base = now - timedelta(hours=int(re.search(r"\d+", r).group()))
            elif "分钟前" in r or r in ("刚刚",):
                base = now - timedelta(minutes=1)
            elif r in ("今天", "今日"):
                base = now
            else:  # 昨天/昨日
                base = now - timedelta(days=1)
    tm = re.search(r"(\d{1,2}):(\d{2})", raw)
    if tm:
        base = base.replace(hour=int(tm.group(1)), minute=int(tm.group(2)))
    else:
        base = base.replace(hour=12, minute=0)
    if base > now + timedelta(days=1):
        return ""
    return base.strftime("%Y-%m-%d %H:%M")


def is_recent(publish_time: str, now: datetime, max_days: float = 30):
    """判断发布时间是否在 max_days 天内。"""
    if not publish_time:
        return False
    try:
        t = datetime.strptime(publish_time, "%Y-%m-%d %H:%M")
        return (now.replace(tzinfo=None) - t).total_seconds() <= max_days * 86400
    except ValueError:
        return False
