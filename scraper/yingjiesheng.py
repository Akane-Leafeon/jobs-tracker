# -*- coding: utf-8 -*-
"""应届生网适配器 —— 网申截止提醒源。

数据：https://www.yingjiesheng.com/deadline/ 入口页的「近期截止网申」表格
（无需登录、无WAF、纯HTTP，GBK编码）。
注意：该站岗位列表页（行业/日期页）需登录才渲染，故只收录入口页的截止提醒。
条目为"公司/单位名"级别而非岗位级别，作为截止倒计时信号使用。
"""
import re
from datetime import datetime

from bs4 import BeautifulSoup

from scraper.common import fetch, get_logger, make_session

log = get_logger("yingjiesheng")

ENTRY_URL = "https://www.yingjiesheng.com/deadline/"
BASE_URL = "https://www.yingjiesheng.com"

DEADLINE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
CITY_RE = re.compile(r"^【([^】]+)】")


def fetch_jobs():
    session = make_session()
    resp = fetch(session, ENTRY_URL)
    if resp is None:
        return []
    html = resp.content.decode("gbk", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.jobul")
    if table is None:
        log.warning("yingjiesheng: table.jobul not found")
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
            city = m.group(1).strip()
        title = CITY_RE.sub("", text).strip()
        # 倒计时信息（在对应 clock 行的文本里，就近解析不到时留空）
        jobs.append({
            "title": text,
            "company": title,
            "locations": [city] if city else [],
            "location_raw": city,
            "publish_time_raw": "",
            "publish_time": "",  # 该源无发布时间，用截止时间字段替代展示
            "deadline": current_deadline,
            "source": "yingjiesheng",
            "url": BASE_URL + a["href"],
            "extra": {},
        })
    log.info("yingjiesheng: %d deadline reminders fetched", len(jobs))
    return jobs
