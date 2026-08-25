# -*- coding: utf-8 -*-
"""汇川技术校招适配器（纯HTTP，无需登录）。

数据源：POST https://recruit.inovance.com/prod-portal-api/position/ad/search
（recruitTypes=[1] 为校招；total≈310，按 pageNum 翻页）
"""
import time

from scraper.common import fetch, get_logger, make_session

log = get_logger("inovance")

API = "https://recruit.inovance.com/prod-portal-api/position/ad/search"
SITE_URL = "https://recruit.inovance.com/#/campus/jobs"
# 浏览器抓包获得的固定请求头（portal 标识，官方前端硬编码）
PORTAL_HEADERS = {
    "X-Portal-Id": "019daf7d-4d1a-7634-87af-1f089498b6f2",
    "X-Brizoo-Token": "bearer",
}
PAGE_SIZE = 20
MAX_PAGES = 20


def fetch_jobs():
    session = make_session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://recruit.inovance.com",
        "Referer": SITE_URL,
        **PORTAL_HEADERS,
    })

    jobs = []
    for page in range(1, MAX_PAGES + 1):
        payload = {
            "keyword": "", "recruitTypes": [1], "hotOnly": False,
            "topOnly": False, "longTermOnly": False,
            "pageNum": page, "pageSize": PAGE_SIZE, "sortBy": "recommended",
        }
        resp = fetch(session, API, method="POST", json=payload)
        if resp is None:
            break
        try:
            data = resp.json().get("data") or {}
        except Exception:  # noqa: BLE001
            break
        items = data.get("records") or []
        if not items:
            break
        for it in items:
            title = (it.get("adJobName") or "").strip()
            if not title:
                continue
            job_id = it.get("jobPostingId") or it.get("adId") or ""
            pub = str(it.get("publishTime") or "")[:16].replace("T", " ")
            # workLocation: [{'name': '苏州市', ...}, ...]
            locs = []
            for loc in it.get("workLocation") or []:
                name = (loc.get("name") or "").rstrip("市").strip() if isinstance(loc, dict) else str(loc)
                if name:
                    locs.append(name)
            jobs.append({
                "title": title,
                "company": "汇川技术",
                "locations": locs,
                "location_raw": " ".join(locs),
                "publish_time_raw": str(it.get("publishTime") or ""),
                "publish_time": pub,
                "source": "inovance",
                "url": f"https://recruit.inovance.com/#/campus/jobs/{job_id}" if job_id else "",
                "extra": {
                    "segment": it.get("segment") or "",
                },
            })
        log.info("inovance: page %d -> %d items (total %d)", page, len(items), len(jobs))
        total = int(data.get("total") or 0)
        if len(jobs) >= total or not data.get("hasMore", True):
            break
        time.sleep(0.6)

    log.info("inovance: %d jobs fetched", len(jobs))
    return jobs
