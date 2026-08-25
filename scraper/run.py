# -*- coding: utf-8 -*-
"""爬虫主入口：依次运行所有数据源适配器 → 分类 → 增量合并入库。

用法：
    python scraper/run.py            # 抓取所有来源并合并
    python scraper/run.py --source nowcoder   # 只跑指定来源（调试用）
    python scraper/run.py --verbose
"""
import argparse
import importlib
import sys
import traceback
from datetime import datetime

sys.path.insert(0, ".")
sys.path.insert(0, "..")

from engine import classify, store
from scraper.common import get_logger

log = get_logger("run")

# 注册的数据源适配器：模块名 -> 是否默认启用
SOURCES = {
    # 聚合源
    "yingjiesheng": True,
    "nowcoder": True,
    "nowcoder_schedule": True,
    # 本地源（需本机 boss login 扫码；CI 上自动跳过）
    "boss": True,
    # 自建官网源（纯HTTP）
    "xiaomi": True,
    "tencent": True,
    "alibaba": True,
    "netease": True,
    "vivo": True,
    "pdd": True,
    "inovance": True,
    # 自建官网源（Playwright/混合）
    "bytedance": True,
    "bilibili": True,
    # 待实现/被墙：jd(京东)、huawei(华为新版SPA岗位接口未公开)、zte(中兴挂MOKA且响应加密)、
    # dji(大疆投递挂MOKA)、honor(荣耀TLS异常)、hikvision(海康岗位接口需登录)、
    # byd(比亚迪需登录token)、catl(宁德域名未开放)、mihoyo(米哈游ATS需渠道参数)、unitree(宇树)
    "jd": False,
    "huawei": False,
}


def run_source(name: str, verbose=False):
    """运行单个适配器，返回 (job_dicts, error_msg)。适配器缺失或异常不中断整体。"""
    try:
        mod = importlib.import_module(f"scraper.{name}")
        jobs = mod.fetch_jobs()
        if verbose:
            log.info("[%s] fetched %d raw jobs", name, len(jobs))
        return jobs, None
    except ModuleNotFoundError:
        log.warning("[%s] adapter not implemented yet, skipped", name)
        return [], "adapter not implemented"
    except Exception as e:  # noqa: BLE001
        log.error("[%s] failed: %s", name, e)
        if verbose:
            traceback.print_exc()
        return [], str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="", help="只运行指定数据源")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    now = datetime.now()
    today = store.today_str()
    names = [args.source] if args.source else [n for n, on in SOURCES.items() if on]

    existing = store.load_jobs()
    log.info("existing jobs in db: %d", len(existing))

    incoming = []
    errors = {}
    for name in names:
        jobs, err = run_source(name, args.verbose)
        incoming.extend(jobs)
        if err:
            errors[name] = err

    # 逐条分类与归一化
    classified = []
    for raw in incoming:
        item = dict(raw)
        if not item.get("publish_time"):
            item["publish_time"] = classify.normalize_time(item.get("publish_time_raw", ""), now)
        key, label, priority = classify.classify_direction(item.get("title", ""), item.get("company", ""))
        item["direction"] = key
        item["direction_label"] = label
        item["priority"] = priority
        locs = item.get("locations") or classify.parse_locations(item.get("location_raw", ""))
        item["locations"] = locs
        item["region_level"] = classify.classify_region(locs)
        item["company_tag"] = classify.tag_company(item.get("company", ""))
        hq, size, industry = classify.company_info(item.get("company", ""))
        item["hq_city"] = hq
        item["size_bucket"] = size
        item["industry"] = industry
        item["url"] = item.get("url") or ""
        item["id"] = store.job_id(item.get("title", ""), item.get("company", ""), item.get("url"))
        classified.append(item)

    jobs, added = store.merge_jobs(existing, classified, today)
    store.save_jobs(jobs)
    log.info("merged: %d new jobs added, total %d in db", added, len(jobs))
    log.info("errors by source: %s", errors if errors else "none")

    # 汇总报告（供邮件/日志使用）
    report = {
        "date": today,
        "added": added,
        "total": len(jobs),
        "by_source": {},
        "errors": errors,
    }
    for item in classified:
        report["by_source"][item.get("source", "unknown")] = report["by_source"].get(item.get("source", "unknown"), 0) + 1
    return report


if __name__ == "__main__":
    main()
