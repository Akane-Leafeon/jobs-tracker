# -*- coding: utf-8 -*-
"""BOSS直聘适配器（本地数据源，基于 boss-agent-cli，需用户本机登录）。

依赖：pip install boss-agent-cli && boss login（浏览器扫码，登录态存本地 ~/.boss-agent/）
原理：subprocess 调用 `boss search <kw> --json`，解析其 JSON 信封 {ok, data, ...}。
      未安装 / 未登录 / 接口风控时返回空列表（CI 上自动跳过，不影响其他源）。
过滤：BOSS 以社招为主，仅收录标题/标签带 校招/应届/202X届 的岗位，宁缺毋滥。
字段：JobItem 自带 salary / scale(公司规模) / industry / education / skills 等，
      scale 会同步刷新到 company_info 静态库未覆盖的公司。
"""
import json
import re
import subprocess
import time

from scraper.common import get_logger

log = get_logger("boss")

QUERIES = [
    "硬件工程师", "硬件开发", "电子工程师", "嵌入式硬件",
    "机器人工程师", "硬件测试",
]
CAMPUS_RE = re.compile(r"校招|校园招聘|应届|202[5-8]届")
PAGES_PER_QUERY = 2
CMD_TIMEOUT = 120


def _run_search(query: str, page: int):
    """执行一次 boss search，返回 (data列表, 是否登录缺失)；失败返回 (None, False)。"""
    cmd = ["boss", "--json", "search", query, "--page", str(page)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=CMD_TIMEOUT)
    except FileNotFoundError:
        log.warning("boss: boss-agent-cli not installed, skipped")
        return None, True
    except subprocess.TimeoutExpired:
        log.warning("boss: search timeout for %r", query)
        return None, False
    out = (proc.stdout or "").strip()
    if not out:
        err = (proc.stderr or "").strip()[:200]
        log.warning("boss: empty stdout for %r: %s", query, err)
        return None, False
    try:
        envelope = json.loads(out)
    except Exception:  # noqa: BLE001
        log.warning("boss: non-json output for %r", query)
        return None, False
    if not envelope.get("ok"):
        err = (envelope.get("error") or {})
        code = err.get("code", "")
        log.info("boss: search %r failed: %s %s", query, code, err.get("message", "")[:80])
        if code == "AUTH_REQUIRED":
            log.warning("boss: 未登录（CI或首次使用），本源自动跳过；本机启用请运行: boss login")
            return None, True
        return None, False
    data = envelope.get("data")
    return (data if isinstance(data, list) else []), False


def fetch_jobs():
    jobs = []
    seen = set()
    for query in QUERIES:
        for page in range(1, PAGES_PER_QUERY + 1):
            items, no_auth = _run_search(query, page)
            if no_auth:
                return jobs  # 未安装或未登录：整体跳过
            if items is None or not items:
                break
            for it in items:
                title = (it.get("title") or "").strip()
                job_id = it.get("job_id") or ""
                if not title or job_id in seen:
                    continue
                seen.add(job_id)
                labels = " ".join(it.get("job_labels") or [])
                if not CAMPUS_RE.search(title + " " + labels):
                    continue  # 社招岗，跳过
                if it.get("employment_type") == "实习":
                    continue
                city = (it.get("city") or "").replace("市", "").strip()
                jobs.append({
                    "title": title,
                    "company": (it.get("company") or "").strip(),
                    "locations": [city] if city else [],
                    "location_raw": city,
                    "publish_time_raw": "",
                    "publish_time": "",  # 搜索结果无发布时间，入库后按 first_seen 追踪
                    "source": "boss",
                    "url": f"https://www.zhipin.com/job_detail/{job_id}.html" if job_id else "",
                    "extra": {
                        "salary": it.get("salary") or "",
                        "scale": it.get("scale") or "",
                        "industry": it.get("industry") or "",
                        "experience": it.get("experience") or "",
                        "education": it.get("education") or "",
                        "skills": (it.get("skills") or [])[:8],
                        "welfare": (it.get("welfare") or [])[:8],
                    },
                })
            time.sleep(1.5)  # 礼貌间隔（CLI 自身还有高斯节流）
        log.info("boss: after %r -> %d campus jobs", query, len(jobs))

    log.info("boss: %d campus jobs fetched", len(jobs))
    return jobs
