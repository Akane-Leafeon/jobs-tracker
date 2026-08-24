# -*- coding: utf-8 -*-
"""牛客网校招适配器。

方案：抓取 SSR 页面 https://www.nowcoder.com/jobs/school/jobs，
从 window.__INITIAL_STATE__ 内嵌 JSON 中提取 jobListData（每页20条、按最新排序）。
无需登录、无签名。JSON API 被阿里云 WAF 保护，故用 SSR 方案（每日抓最新20条足够追踪新岗）。
"""
import json
import re
from datetime import datetime

from scraper.common import fetch, get_logger, make_session

log = get_logger("nowcoder")

PAGE_URL = "https://www.nowcoder.com/jobs/school/jobs"
DETAIL_URL = "https://www.nowcoder.com/jobs/detail/{job_id}"
STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;\(function", re.S)


def _ms_to_str(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, TypeError):
        return ""


def fetch_jobs():
    session = make_session()
    resp = fetch(session, PAGE_URL)
    if resp is None:
        return []
    m = STATE_RE.search(resp.text)
    if not m:
        log.warning("nowcoder: __INITIAL_STATE__ not found, page structure may have changed")
        return []
    try:
        state = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        log.warning("nowcoder: state json parse failed: %s", e)
        return []

    # 岗位列表挂在 state.app.<数字模块号>.jobListData（模块号会变，遍历查找）
    app = state.get("app") or {}
    raw_jobs = []
    for v in app.values():
        if isinstance(v, dict) and v.get("jobListData"):
            raw_jobs = v["jobListData"]
            break
    if not raw_jobs:
        log.warning("nowcoder: jobListData not found in state.app")
        return []

    jobs = []
    for it in raw_jobs:
        title = (it.get("jobTitle") or it.get("jobName") or "").strip()
        if not title:
            continue
        job_id = str(it.get("jobId") or "")
        create_ms = it.get("createTime")
        update_ms = it.get("updateTime")
        extra = it.get("extraInfo") or {}
        jobs.append({
            "title": title,
            "company": it.get("companyName") or it.get("companyNameText") or "",
            "locations": (it.get("jobCity") or "").split("/"),
            "location_raw": it.get("jobCity") or "",
            "publish_time_raw": _ms_to_str(create_ms) if create_ms else "",
            "publish_time": _ms_to_str(create_ms),
            "source": "nowcoder",
            "url": DETAIL_URL.format(job_id=job_id) if job_id else "",
            "extra": {
                "update_time": _ms_to_str(update_ms) if update_ms else "",
                "salary": it.get("salary") or it.get("salaryText") or "",
                "education": it.get("education") or "",
                "channel": extra.get("positionChannel_var") or "",
            },
        })
    log.info("nowcoder: %d jobs fetched", len(jobs))
    return jobs
