# -*- coding: utf-8 -*-
"""腾讯校招适配器（纯HTTP，无需登录）。

数据源：POST https://join.qq.com/api/v1/position/searchPosition
（请求体为浏览器抓包复刻；projectMappingIdList 覆盖应届/实习等项目）
返回 positionList：positionTitle / workCities / postId / projectName / recruitLabelName。
无发布时间字段，publish_time 留空（入库时按 first_seen 追踪）。
"""
import time

from scraper.common import fetch, get_logger, make_session

log = get_logger("tencent")

API = "https://join.qq.com/api/v1/position/searchPosition"
DETAIL_URL = "https://join.qq.com/post.html?postId={post_id}"
PAGE_SIZE = 50
MAX_PAGES = 8  # 上限约400条，足够覆盖校招在招岗位


def fetch_jobs():
    session = make_session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://join.qq.com",
        "Referer": "https://join.qq.com/post.html",
    })

    jobs = []
    for page in range(1, MAX_PAGES + 1):
        payload = {
            "projectIdList": [],
            "projectMappingIdList": [1, 2, 104, 14, 20, 9],
            "keyword": "", "bgList": [], "workCountryType": 0,
            "workCityList": [], "recruitCityList": [], "positionFidList": [],
            "pageIndex": page, "pageSize": PAGE_SIZE,
        }
        resp = fetch(session, API, method="POST", json=payload)
        if resp is None:
            break
        data = resp.json().get("data") or {}
        items = data.get("positionList") or []
        if not items:
            break
        for it in items:
            title = (it.get("positionTitle") or "").strip()
            if not title:
                continue
            post_id = it.get("postId") or ""
            cities = [c.strip().replace("总部", "") for c in (it.get("workCities") or "").split() if c.strip()]
            jobs.append({
                "title": title,
                "company": "腾讯",
                "locations": cities,
                "location_raw": it.get("workCities") or "",
                "publish_time_raw": "",
                "publish_time": "",
                "source": "tencent",
                "url": DETAIL_URL.format(post_id=post_id) if post_id else "",
                "extra": {
                    "project": it.get("projectName") or "",
                    "recruit_label": it.get("recruitLabelName") or "",
                    "bgs": it.get("bgs") or "",
                },
            })
        log.info("tencent: page %d -> %d items (total %d)", page, len(items), len(jobs))
        if len(items) < PAGE_SIZE:
            break
        time.sleep(0.8)

    log.info("tencent: %d jobs fetched", len(jobs))
    return jobs
