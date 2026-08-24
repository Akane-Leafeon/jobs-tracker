# -*- coding: utf-8 -*-
"""小米校招适配器。

数据源：https://hr.xiaomi.com/website/api/agent/searchJobPage?type=2
（type: 1社招 2校招 3实习 4顶尖人才；无需登录，带浏览器UA即可）
详情链接走旧域名 xiaomi.jobs.f.mioffice.cn。
"""
import math
import time

from scraper.common import fetch, get_logger, make_session

log = get_logger("xiaomi")

API = "https://hr.xiaomi.com/website/api/agent/searchJobPage"
DETAIL_URL = "https://xiaomi.jobs.f.mioffice.cn/campus/position/{job_id}/detail"
PAGE_SIZE = 100


def fetch_jobs():
    session = make_session()
    session.headers["Accept"] = "application/json, text/plain, */*"

    # 第一页确定总量
    first = fetch(session, API, params={
        "keyword": "", "cityZhNames": "", "pageSize": PAGE_SIZE, "pageNum": 1, "type": 2,
    })
    if first is None:
        return []
    data = first.json().get("data") or {}
    total = int(data.get("total") or 0)
    if total == 0:
        log.warning("xiaomi: empty result")
        return []

    pages = math.ceil(total / PAGE_SIZE)
    log.info("xiaomi: %d jobs in %d pages", total, pages)
    items = list(data.get("list") or [])

    for page in range(2, pages + 1):
        resp = fetch(session, API, params={
            "keyword": "", "cityZhNames": "", "pageSize": PAGE_SIZE, "pageNum": page, "type": 2,
        })
        if resp is None:
            continue
        items.extend((resp.json().get("data") or {}).get("list") or [])
        time.sleep(0.5)  # 官网有防抖设计，礼貌限速

    jobs = []
    for it in items:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        job_id = it.get("jobPostId") or it.get("jobId") or ""
        pub = it.get("publishTime") or ""
        jobs.append({
            "title": title,
            "company": "小米",
            "locations": list(it.get("cityZhNames") or []),
            "location_raw": " ".join(it.get("cityZhNames") or []),
            "publish_time_raw": pub,
            "publish_time": f"{pub} 12:00" if pub else "",
            "source": "xiaomi",
            "url": DETAIL_URL.format(job_id=job_id) if job_id else "",
            "extra": {
                "department": it.get("levelOneDeptName") or "",
                "lark_job_code": it.get("larkJobCode") or "",
            },
        })
    return jobs
