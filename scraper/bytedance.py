# -*- coding: utf-8 -*-
"""字节跳动校招适配器。

API 有自研混淆VM签名墙（纯HTTP 405），故用 Playwright 真实浏览器加载校招搜索页。
双通道抓取：①优先拦截带签名的 search/job/posts JSON（字段最全，含发布时间）
②DOM 兜底解析（页面总会渲染岗位列表，不依赖XHR时序）。
抓取两路：硬件分类全量（limit=100）+ 校招全量最新2页（覆盖器件/芯片等无分类岗位）。
"""
import json
import re
import time
from datetime import datetime

from scraper.common import get_logger

log = get_logger("bytedance")

CAMPUS_URL = "https://jobs.bytedance.com/campus/position"
DETAIL_URL = "https://jobs.bytedance.com/campus/position/{job_id}/detail"
HW_CATEGORY = "6938376045242353957"  # 研发 > 硬件（分类ID实测确认）
WAIT_TIMEOUT = 25  # 单页最长等待秒数

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || {runtime: {}};
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""

CITY_RE = re.compile(r"^(.*?)(?:等\s*\d+\s*个城市)?$")


def _launch():
    """启动浏览器：优先系统 Edge（指纹更真实），CI 环境退化为 chromium。"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    for channel in ("msedge", None):
        try:
            browser = pw.chromium.launch(
                channel=channel, headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            return pw, browser
        except Exception as e:  # noqa: BLE001
            log.warning("bytedance: launch channel=%s failed: %s", channel or "chromium", e)
    pw.stop()
    raise RuntimeError("bytedance: no browser available")


def _parse_cities(text):
    """'北京、上海、杭州等 4 个城市' → ['北京','上海','杭州']；'北京' → ['北京']。"""
    if not text:
        return []
    m = CITY_RE.match(text.strip())
    base = m.group(1).strip() if m else text.strip()
    if not base:
        return []
    return [c.strip() for c in base.split("、") if c.strip()]


def _parse_json(data):
    """从拦截到的 JSON 响应解析岗位。"""
    jobs = []
    if not data:
        return jobs
    lst = (data.get("data") or {}).get("job_post_list") or []
    for it in lst:
        jid = str(it.get("id") or "")
        title = (it.get("title") or "").strip()
        if not title or not jid:
            continue
        pub = it.get("publish_time")
        pub_str = ""
        if pub:
            try:
                pub_str = datetime.fromtimestamp(int(pub) / 1000).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                pub_str = ""
        subject = ((it.get("job_subject") or {}).get("name") or {}).get("zh_cn", "")
        jobs.append({
            "title": title,
            "company": "字节跳动",
            "locations": [c.get("name") for c in (it.get("city_list") or []) if c.get("name")],
            "location_raw": " ".join(c.get("name") or "" for c in (it.get("city_list") or [])),
            "publish_time_raw": str(pub) if pub else "",
            "publish_time": pub_str,
            "source": "bytedance",
            "url": DETAIL_URL.format(job_id=jid),
            "extra": {
                "category": (it.get("job_category") or {}).get("name", ""),
                "recruit_type": (it.get("recruit_type") or {}).get("name", ""),
                "subject": subject,
                "code": it.get("code") or "",
            },
        })
    return jobs


def _parse_dom(page):
    """DOM 兜底：解析渲染出的岗位卡片（无发布时间字段）。"""
    jobs = []
    try:
        items = page.locator("a[data-id]").all()
    except Exception:  # noqa: BLE001
        return jobs
    for el in items:
        try:
            jid = el.get_attribute("data-id") or ""
            title = el.locator('[class*="positionItem-title-text"]').first.inner_text().strip()
            sub = el.locator('[class*="positionItem-subTitle"]').first
            city_span = sub.locator(":scope > span").first.inner_text()
            category = ""
            try:
                category = sub.locator('[class*="infoText-category"]').first.inner_text().strip()
            except Exception:  # noqa: BLE001
                pass
            info_texts = sub.locator('[class*="infoText"]').all_inner_texts()
            subject = ""
            recruit = ""
            for t in info_texts:
                t = t.strip()
                if "届" in t and "招聘" in t:
                    subject = t
                elif t in ("正式", "实习", "日常实习"):
                    recruit = t
        except Exception:  # noqa: BLE001
            continue
        if not title or not jid:
            continue
        jobs.append({
            "title": title,
            "company": "字节跳动",
            "locations": _parse_cities(city_span),
            "location_raw": city_span.strip(),
            "publish_time_raw": "",
            "publish_time": "",
            "source": "bytedance",
            "url": DETAIL_URL.format(job_id=jid),
            "extra": {"category": category, "recruit_type": recruit, "subject": subject, "code": ""},
        })
    return jobs


def _fetch_page(ctx, category, page_no, limit=50):
    """加载一页，返回 (jobs, 通道名)。XHR 优先，DOM 兜底。"""
    page = ctx.new_page()
    xhr_data = []

    def on_resp(resp):
        if "search/job/posts" not in resp.url or resp.status != 200:
            return
        try:
            d = resp.json()
            if d.get("code") == 0 and (d.get("data") or {}).get("job_post_list"):
                xhr_data.append(d)
        except Exception:  # noqa: BLE001
            pass

    page.on("response", on_resp)
    url = (f"{CAMPUS_URL}?keywords=&category={category}&location=&type=&"
           f"current={page_no}&limit={limit}&functionCategory=")
    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception as e:  # noqa: BLE001
        log.warning("bytedance: page goto failed: %s", e)
        page.close()
        return [], "none"

    # 等待：XHR 成功 或 DOM 渲染出岗位项
    deadline = time.time() + WAIT_TIMEOUT
    while time.time() < deadline:
        if xhr_data:
            jobs = _parse_json(xhr_data[0])
            page.close()
            return jobs, "xhr"
        try:
            if page.locator("a[data-id]").count() > 0:
                jobs = _parse_dom(page)
                page.close()
                return jobs, "dom"
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    page.close()
    return [], "timeout"


def fetch_jobs():
    pw, browser = _launch()
    try:
        ctx = browser.new_context(user_agent=UA, locale="zh-CN",
                                  viewport={"width": 1366, "height": 900})
        ctx.add_init_script(STEALTH)

        collected, channels = [], []
        # 路1：硬件分类全量（limit=100 一页）
        jobs, ch = _fetch_page(ctx, HW_CATEGORY, 1, limit=100)
        collected.extend(jobs)
        channels.append(("hardware", ch, len(jobs)))
        # 路2：校招全量最新2页
        for page_no in (1, 2):
            jobs, ch = _fetch_page(ctx, "", page_no, limit=50)
            collected.extend(jobs)
            channels.append((f"all-p{page_no}", ch, len(jobs)))
            if not jobs:
                break
            time.sleep(2)

        log.info("bytedance: pages=%s", channels)

        # 按详情URL去重
        seen, jobs = set(), []
        for j in collected:
            if j["url"] in seen:
                continue
            seen.add(j["url"])
            jobs.append(j)
        log.info("bytedance: %d jobs fetched", len(jobs))
        return jobs
    finally:
        browser.close()
        pw.stop()
