# -*- coding: utf-8 -*-
"""应届生网适配器 —— 网申截止提醒 + 北京频道全职列表。

数据（均无需登录、无WAF、纯HTTP，GBK编码）：
1. https://www.yingjiesheng.com/deadline/ 入口页「近期截止网申」表格
   （条目为公司级，作为截止倒计时信号使用）
2. https://www.yingjiesheng.com/beijing/ 北京频道「北京全职招聘」表格
   （条目为岗位级：标题/类型/城市/公司/发布日期，长尾公司的重要补充源）
"""
import re
from datetime import datetime

from bs4 import BeautifulSoup

from scraper.common import fetch, get_logger, make_session

log = get_logger("yingjiesheng")

ENTRY_URL = "https://www.yingjiesheng.com/deadline/"
BEIJING_URL = "https://www.yingjiesheng.com/beijing/"
BASE_URL = "https://www.yingjiesheng.com"

DEADLINE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
CITY_RE = re.compile(r"^\[([^\]]+)\]|^【([^】]+)】")
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})(?!\d)")


def _fetch_deadlines(session):
    """入口页截止提醒表（原有逻辑）。"""
    resp = fetch(session, ENTRY_URL)
    if resp is None:
        return []
    html = resp.content.decode("gbk", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.jobul")
    if table is None:
        log.warning("yingjiesheng: deadline table not found")
        return []

    jobs = []
    current_deadline = ""
    for tr in table.find_all("tr"):
        cls = tr.get("class") or []
        if "clock" in cls:
            m = DEADLINE_RE.search(tr.get_text())
            if m:
                current_deadline = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            continue
        if not ("bg0" in cls or "bg1" in cls):
            continue
        a = tr.find("a")
        if a is None or not a.get("href"):
            continue
        text = a.get_text(strip=True)
        if not text:
            continue
        city = ""
        m = CITY_RE.match(text)
        if m:
            city = (m.group(1) or m.group(2) or "").strip()
        title = CITY_RE.sub("", text).strip()
        jobs.append({
            "title": text,
            "company": title,
            "locations": [city] if city else [],
            "location_raw": city,
            "publish_time_raw": "",
            "publish_time": "",  # 该部分无发布时间，用截止时间字段替代展示
            "deadline": current_deadline,
            "source": "yingjiesheng",
            "url": BASE_URL + a["href"],
            "extra": {"section": "deadline"},
        })
    log.info("yingjiesheng: %d deadline reminders fetched", len(jobs))
    return jobs


def _fetch_beijing(session):
    """北京频道全职列表：行结构 = 标题(带【城市】前缀) / 类型 / 城市 / 公司 / 发布日期。"""
    resp = fetch(session, BEIJING_URL)
    if resp is None:
        return []
    html = resp.content.decode("gbk", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#tb_job_list")
    if table is None:
        jobul_tables = soup.select("table.jobul")
        table = jobul_tables[-1] if jobul_tables else None
    if table is None:
        log.warning("yingjiesheng: beijing table not found")
        return []

    now = datetime.now()
    jobs = []
    for tr in table.find_all("tr"):
        cls = tr.get("class") or []
        if "jobli" not in cls:
            continue
        tds = tr.find_all("td")
        if not tds:
            continue
        a = tds[0].find("a")
        if a is None or not a.get("href"):
            continue
        text = a.get_text(strip=True)
        if not text:
            continue
        city = ""
        m = CITY_RE.match(text)
        if m:
            city = (m.group(1) or m.group(2) or "").strip()
        title = CITY_RE.sub("", text).strip()
        # 列顺序：标题 / 类型 / 城市 / 公司(span.sub) / 发布日期
        kind = tds[1].get_text(strip=True) if len(tds) > 1 else ""
        row_city = tds[2].get_text(strip=True) if len(tds) > 2 else ""
        company = tds[3].get_text(strip=True) if len(tds) > 3 else ""
        date_txt = tds[4].get_text(strip=True) if len(tds) > 4 else ""
        loc = city or row_city
        pub = ""
        dm = DATE_RE.search(date_txt)
        if dm:
            base = datetime(now.year, int(dm.group(1)), int(dm.group(2)))
            if base > now:
                base = base.replace(year=now.year - 1)
            pub = base.strftime("%Y-%m-%d 12:00")
        jobs.append({
            "title": title or text,
            "company": company or title,
            "locations": [loc] if loc else [],
            "location_raw": loc,
            "publish_time_raw": date_txt,
            "publish_time": pub,
            "source": "yingjiesheng",
            "url": BASE_URL + a["href"] if a["href"].startswith("/") else a["href"],
            "extra": {"section": "beijing", "kind": kind},
        })
    log.info("yingjiesheng: %d beijing jobs fetched", len(jobs))
    return jobs


def fetch_jobs():
    session = make_session()
    jobs = _fetch_deadlines(session)
    jobs.extend(_fetch_beijing(session))
    return jobs
