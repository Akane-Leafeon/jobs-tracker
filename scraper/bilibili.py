# -*- coding: utf-8 -*-
"""哔哩哔哩校招适配器（Playwright 拦截 + 翻页点击）。

数据源：POST https://jobs.bilibili.com/api/campus/position/positionList
接口校验 ajSessionId（由页面风控JS生成，不在cookie中，纯requests 401），
故直接在真实浏览器里翻页并拦截 XHR JSON 响应。
浏览器失败时返回空列表，不影响其他源。
"""
import json
import time

from scraper.common import get_logger

log = get_logger("bilibili")

PAGE_URL = "https://jobs.bilibili.com/campus/positions"
LIST_API = "https://jobs.bilibili.com/api/campus/position/positionList"
WAIT_TIMEOUT = 25
MAX_PAGES = 10


def fetch_jobs():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("bilibili: playwright not installed, skipped")
        return []

    pw = sync_playwright().start()
    try:
        browser = None
        for channel in ("msedge", None):
            try:
                browser = pw.chromium.launch(
                    channel=channel, headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                break
            except Exception:  # noqa: BLE001
                continue
        if browser is None:
            return []
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            locale="zh-CN", ignore_https_errors=True,
        )
        page = ctx.new_page()
        pages_data = []

        def on_response(resp):
            try:
                if LIST_API not in resp.url:
                    return
                if resp.status != 200:
                    return
                body = json.loads(resp.text())
                if body.get("code") == 0:
                    pages_data.append(body.get("data") or {})
            except Exception:  # noqa: BLE001
                pass

        page.on("response", on_response)
        page.goto(PAGE_URL, timeout=30000, wait_until="domcontentloaded")
        deadline = time.time() + WAIT_TIMEOUT
        while time.time() < deadline and not pages_data:
            time.sleep(1)

        # 点击"下一页"翻页（element-plus 分页器），直到不可再翻或达上限
        for _ in range(MAX_PAGES - 1):
            try:
                nxt = page.locator("button.btn-next").first
                if not nxt.is_enabled():
                    break
                before = len(pages_data)
                nxt.click(timeout=3000)
                for _ in range(10):
                    if len(pages_data) > before:
                        break
                    time.sleep(0.8)
                if len(pages_data) == before:
                    break
            except Exception:  # noqa: BLE001
                break

        ctx.close()
        browser.close()

        jobs = []
        seen = set()
        for data in pages_data:
            for it in data.get("list") or []:
                title = (it.get("name") or it.get("positionName") or "").strip()
                job_id = str(it.get("id") or "")
                if not title or job_id in seen:
                    continue
                seen.add(job_id)
                locs = it.get("workLocationList") or []
                if not isinstance(locs, list):
                    locs = [str(locs)]
                jobs.append({
                    "title": title,
                    "company": "哔哩哔哩",
                    "locations": [str(x) for x in locs],
                    "location_raw": " ".join(str(x) for x in locs),
                    "publish_time_raw": str(it.get("publishTime") or ""),
                    "publish_time": "",
                    "source": "bilibili",
                    "url": f"https://jobs.bilibili.com/campus/positions?id={job_id}" if job_id else "",
                    "extra": {
                        "dept": it.get("deptName") or "",
                        "post_code": it.get("postCode") or "",
                    },
                })
        log.info("bilibili: %d jobs fetched from %d pages", len(jobs), len(pages_data))
        return jobs
    except Exception as e:  # noqa: BLE001
        log.warning("bilibili: failed: %s", e)
        return []
    finally:
        try:
            pw.stop()
        except Exception:  # noqa: BLE001
            pass
