# -*- coding: utf-8 -*-
"""vivo校招适配器（纯HTTP，无需登录）。

数据源：POST https://hr-campus.vivo.com/api/JobAd/GetJobAdPageList
（PortalId 为官网固定值；返回 Count 总数与 Data 列表）
只保留校招/正式类目（过滤实习），PostDate 常为空则按 first_seen 追踪。
"""
import time

from scraper.common import fetch, get_logger, make_session

log = get_logger("vivo")

API = "https://hr-campus.vivo.com/api/JobAd/GetJobAdPageList"
PORTAL_ID = "903cbcbf-4898-46e1-817c-da522a9752b1"
SITE_URL = "https://hr-campus.vivo.com/"
PAGE_SIZE = 50
MAX_PAGES = 6
EXCLUDE_CAT = ("实习",)


def fetch_jobs():
    session = make_session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://hr-campus.vivo.com",
        "Referer": SITE_URL,
    })

    jobs = []
    for page in range(MAX_PAGES):
        payload = {
            "PageIndex": page, "PageSize": PAGE_SIZE, "KeyWords": "",
            "SpecialType": 0, "PortalId": PORTAL_ID,
            "DisplayFields": ["Category", "Location", "PostDate", "Org"],
        }
        resp = fetch(session, API, method="POST", json=payload)
        if resp is None:
            break
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            break
        items = data.get("Data") or []
        if not items:
            break
        for it in items:
            title = (it.get("JobAdName") or "").strip()
            if not title:
                continue
            cat = it.get("Category") or ""
            if any(k in cat for k in EXCLUDE_CAT):
                continue
            pub_raw = (it.get("PostDate") or "")
            if pub_raw.startswith("0001"):
                pub_raw = ""
            # "2026-08-20T16:36:37" → "2026-08-20 16:36"
            pub = pub_raw[:16].replace("T", " ") if pub_raw else ""
            jobs.append({
                "title": title,
                "company": "vivo",
                "locations": list(it.get("LocNames") or []),
                "location_raw": " ".join(it.get("LocNames") or []),
                "publish_time_raw": pub_raw,
                "publish_time": pub,
                "source": "vivo",
                "url": "",
                "extra": {
                    "category": cat,
                    "job_ad_id": it.get("JobAdId") or "",
                    "org": it.get("Org") or "",
                },
            })
        log.info("vivo: page %d -> %d items (kept %d)", page, len(items), len(jobs))
        total = int(data.get("Count") or 0)
        if len(jobs) >= total or len(items) < PAGE_SIZE:
            break
        time.sleep(0.8)

    log.info("vivo: %d jobs fetched", len(jobs))
    return jobs
