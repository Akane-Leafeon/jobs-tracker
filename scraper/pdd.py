# -*- coding: utf-8 -*-
"""拼多多校招适配器（纯HTTP，无需登录）。

数据源：POST https://careers.pddglobalhr.com/api/careers/api/recruit/position/list
（官网 careers.pinduoduo.com 的真实 API 域；PDD 按岗位大类发布，在招条目不多）
字段：name / jobName / workLocationName / recruitTypeName / releaseTime（毫秒时间戳）。
"""
import time

from scraper.common import fetch, get_logger, make_session

log = get_logger("pdd")

API = "https://careers.pddglobalhr.com/api/careers/api/recruit/position/list"
PAGE_SIZE = 20
MAX_PAGES = 3


def _ms_to_str(ms):
    if not ms:
        return ""
    try:
        from datetime import datetime
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return ""


def fetch_jobs():
    session = make_session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://careers.pinduoduo.com",
        "Referer": "https://careers.pinduoduo.com/",
    })

    jobs = []
    for page in range(1, MAX_PAGES + 1):
        payload = {"page": page, "pageSize": PAGE_SIZE}
        resp = fetch(session, API, method="POST", json=payload)
        if resp is None:
            break
        try:
            result = (resp.json().get("result") or {})
        except Exception:  # noqa: BLE001
            break
        items = result.get("list") or []
        if not items:
            break
        for it in items:
            title = (it.get("name") or it.get("jobName") or "").strip()
            if not title:
                continue
            jobs.append({
                "title": title,
                "company": "拼多多",
                "locations": [it["workLocationName"]] if it.get("workLocationName") else [],
                "location_raw": it.get("workLocationName") or "",
                "publish_time_raw": str(it.get("releaseTime") or ""),
                "publish_time": _ms_to_str(it.get("releaseTime")),
                "source": "pdd",
                "url": "",
                "extra": {
                    "recruit_type": it.get("recruitTypeName") or "",
                    "graduation_year": it.get("graduationYear") or "",
                    "code": it.get("code") or "",
                },
            })
        log.info("pdd: page %d -> %d items (total %d)", page, len(items), len(jobs))
        total = int(result.get("total") or 0)
        if len(jobs) >= total or len(items) < PAGE_SIZE:
            break
        time.sleep(0.6)

    log.info("pdd: %d jobs fetched", len(jobs))
    return jobs
