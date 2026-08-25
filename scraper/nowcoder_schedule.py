# -*- coding: utf-8 -*-
"""牛客校招日程适配器（纯HTTP，SSR免登录）。

数据源：https://www.nowcoder.com/school/schedule 校招日程聚合页
（全库22000+家公司的校招网申状态；SSR 首屏渲染最新更新的20家，API被WAF，
故每日增量收录当日最新更新的公司条目——正好用于监控"谁刚开/刚截止网申"）
条目为公司级：网申起止日期 / 城市列表 / 官网投递直链 / 招聘批次。
"""
import json
import re
from datetime import datetime

from scraper.common import fetch, get_logger, make_session

log = get_logger("nowcoder_schedule")

PAGE_URL = "https://www.nowcoder.com/school/schedule"
STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;\(function", re.S)


def _ms_to_date(ms):
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return ""


def fetch_jobs():
    session = make_session()
    resp = fetch(session, PAGE_URL)
    if resp is None:
        return []
    m = STATE_RE.search(resp.text)
    if not m:
        log.warning("nowcoder_schedule: __INITIAL_STATE__ not found")
        return []
    try:
        state = json.loads(m.group(1))
    except Exception as e:  # noqa: BLE001
        log.warning("nowcoder_schedule: state json parse failed: %s", e)
        return []

    datas = []
    for v in state.get("app", {}).values():
        if isinstance(v, dict) and "scheduleData" in v:
            datas = ((v["scheduleData"] or {}).get("datas")) or []
            break
    if not datas:
        log.warning("nowcoder_schedule: scheduleData.datas empty")
        return []

    jobs = []
    for it in datas:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        begin = _ms_to_date(it.get("wangshenBeginDate"))
        end = _ms_to_date(it.get("wangshenEndDate"))
        url = ""
        ad = it.get("adInfo") or {}
        if isinstance(ad, dict):
            url = ad.get("rawUrl") or ""
        cities = [c for c in (it.get("cityList") or []) if c]
        jobs.append({
            "title": f"{name} 校招网申（{it.get('batchName') or '秋招'}）",
            "company": name,
            "locations": cities,
            "location_raw": " ".join(cities),
            "publish_time_raw": begin,
            "publish_time": f"{begin} 12:00" if begin else "",
            "deadline": end,
            "source": "nowcoder_schedule",
            "url": url,
            "extra": {
                "batch": it.get("batchName") or "",
                "job_count": it.get("companyJobCount") or 0,
                "industry": " ".join(it.get("industryList") or []),
                "careers": " ".join((it.get("careerNameList") or [])[:6]),
                "note": (it.get("companyEvaluation") or "")[:120],
            },
        })
    log.info("nowcoder_schedule: %d company entries fetched (库容 %s)",
             len(jobs), (state.get("app", {}) and "22000+"))
    return jobs
