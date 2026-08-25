# -*- coding: utf-8 -*-
"""网易校招适配器（纯HTTP，无需登录）。

数据源：POST https://hr.163.com/api/hr163/position/queryPage
（网易招聘池：社招+实习混排；秋招季校招岗也发布于此）
策略：按 updateTime 倒序抓前几页，仅保留标题/要求中带校招语义的岗位
（校招|应届|2026届|2027届|秋招），避免社招噪声。
workPlaceNameList 是字符串化的列表（"['杭州市']"），需再解析。
"""
import ast
import re
import time

from scraper.common import fetch, get_logger, make_session

log = get_logger("netease")

API = "https://hr.163.com/api/hr163/position/queryPage"
DETAIL_URL = "https://hr.163.com/position/detail.do?id={job_id}"
PAGE_SIZE = 50
SCAN_PAGES = 4  # 共扫描约200条最新记录，足够覆盖在招校招岗
CAMPUS_RE = re.compile(r"校招|应届|秋招|202[5-8]届")


def _ms_to_str(ms):
    if not ms:
        return ""
    try:
        from datetime import datetime
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return ""


def _parse_city_list(raw):
    """"['杭州市', '北京市']" → ['杭州', '北京']"""
    if not raw:
        return []
    try:
        lst = ast.literal_eval(raw) if isinstance(raw, str) else list(raw)
    except Exception:  # noqa: BLE001
        lst = re.findall(r"[\u4e00-\u9fa5]{2,4}(?=市|'|\"|$)", str(raw))
    out = []
    for c in lst:
        c = str(c).rstrip("市").strip()
        if c:
            out.append(c)
    return out


def fetch_jobs():
    session = make_session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://hr.163.com",
        "Referer": "https://hr.163.com/",
    })

    jobs = []
    for page in range(1, SCAN_PAGES + 1):
        payload = {"currentPage": page, "pageSize": PAGE_SIZE}
        resp = fetch(session, API, method="POST", json=payload)
        if resp is None:
            break
        try:
            data = resp.json().get("data") or {}
        except Exception:  # noqa: BLE001
            break
        items = data.get("list") or []
        if not items:
            break
        for it in items:
            title = (it.get("name") or "").strip()
            if not title:
                continue
            req = it.get("requirement") or ""
            if "实习" in title:  # 实习岗非秋招正式岗，跳过
                continue
            if not (CAMPUS_RE.search(title) or CAMPUS_RE.search(req[:200])):
                continue
            cities = _parse_city_list(it.get("workPlaceNameList"))
            jobs.append({
                "title": title,
                "company": "网易",
                "locations": cities,
                "location_raw": " ".join(cities),
                "publish_time_raw": str(it.get("updateTime") or ""),
                "publish_time": _ms_to_str(it.get("updateTime")),
                "source": "netease",
                "url": DETAIL_URL.format(job_id=it.get("id") or ""),
                "extra": {
                    "dept": it.get("firstDepName") or "",
                    "post_type": it.get("firstPostTypeName") or "",
                    "education": it.get("reqEducationName") or "",
                },
            })
        time.sleep(0.6)

    log.info("netease: %d campus-ish jobs fetched", len(jobs))
    return jobs
