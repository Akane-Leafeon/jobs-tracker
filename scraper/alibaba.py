# -*- coding: utf-8 -*-
"""阿里巴巴校招适配器（纯HTTP，无需登录）。

流程（浏览器行为复刻）：
1. GET 校招职位列表页 → 拿 XSRF-TOKEN cookie
2. GET searchCondition/listBatch → 拿当前校招 batchId（如"阿里控股2026届秋季应届生招聘"）
3. POST position/search?_csrf=<token> 翻页拉取 datas
返回字段：name / workLocations / modifyTime（毫秒时间戳，作发布时间近似）/ id。
"""
import time

from scraper.common import fetch, get_logger, make_session

log = get_logger("alibaba")

PAGE_URL = "https://talent-holding.alibaba.com/campus/position-list?lang=zh"
BATCH_API = "https://talent-holding.alibaba.com/searchCondition/listBatch"
SEARCH_API = "https://talent-holding.alibaba.com/position/search"
PAGE_SIZE = 40
MAX_PAGES = 5


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
        "Origin": "https://talent-holding.alibaba.com",
        "Referer": PAGE_URL,
    })

    # 1. 首页拿 cookie（XSRF-TOKEN）
    page = fetch(session, PAGE_URL)
    if page is None:
        return []
    csrf = ""
    for c in session.cookies:
        if c.name.upper() == "XSRF-TOKEN":
            csrf = c.value
            break
    if not csrf:
        log.warning("alibaba: XSRF-TOKEN cookie not found")
        return []

    # 2. 当前校招批次（POST + csrf）
    resp = fetch(session, BATCH_API, method="POST", params={"_csrf": csrf}, json={})
    batch_id = ""
    if resp is not None:
        content = (resp.json().get("content") or {})
        grad = content.get("graduate") or []
        if grad:
            batch_id = str(grad[0].get("id") or "")
    if not batch_id:
        log.warning("alibaba: no graduate batch found")
        return []

    # 3. 翻页搜索
    jobs = []
    for idx in range(1, MAX_PAGES + 1):
        payload = {
            "channel": "campus_group_official_site", "language": "zh",
            "pageSize": PAGE_SIZE, "batchId": batch_id, "subCategories": "",
            "regions": "", "customDeptCode": "", "corpCode": "",
            "pageIndex": idx, "key": "", "categoryType": "freshman",
        }
        resp = fetch(session, SEARCH_API, method="POST", json=payload, params={"_csrf": csrf})
        if resp is None:
            break
        content = (resp.json().get("content") or {})
        items = content.get("datas") or []
        if not items:
            break
        for it in items:
            title = (it.get("name") or "").strip()
            if not title:
                continue
            job_id = it.get("id") or ""
            pub = _ms_to_str(it.get("modifyTime"))
            jobs.append({
                "title": title,
                "company": "阿里巴巴",
                "locations": list(it.get("workLocations") or []),
                "location_raw": " ".join(it.get("workLocations") or []),
                "publish_time_raw": str(it.get("modifyTime") or ""),
                "publish_time": pub,
                "source": "alibaba",
                "url": f"https://talent-holding.alibaba.com/campus/position-detail?lang=zh&positionId={job_id}" if job_id else "",
                "extra": {
                    "batch_id": batch_id,
                    "dept": it.get("deptName") or it.get("customDeptName") or "",
                },
            })
        log.info("alibaba: page %d -> %d items (total %d)", idx, len(items), len(jobs))
        if len(items) < PAGE_SIZE:
            break
        time.sleep(0.8)

    log.info("alibaba: %d jobs fetched", len(jobs))
    return jobs
