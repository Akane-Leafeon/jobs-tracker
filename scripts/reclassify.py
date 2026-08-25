# -*- coding: utf-8 -*-
"""全库重分类：修改 config.json 的关键词/地区/公司名单后，运行此脚本刷新 data/jobs.json 的分类字段。
用法：python scripts/reclassify.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import classify, store


def main():
    jobs = store.load_jobs()
    for j in jobs.values():
        key, label, priority = classify.classify_direction(j.get("title", ""), j.get("company", ""))
        j["direction"] = key
        j["direction_label"] = label
        j["priority"] = priority
        locs = j.get("locations") or classify.parse_locations(j.get("location_raw", ""))
        j["locations"] = locs
        j["region_level"] = classify.classify_region(locs)
        j["company_tag"] = classify.tag_company(j.get("company", ""))
        hq, size, industry = classify.company_info(j.get("company", ""))
        j["hq_city"] = hq
        j["size_bucket"] = size
        j["industry"] = industry
    store.save_jobs(jobs)
    print(f"reclassified {len(jobs)} jobs")


if __name__ == "__main__":
    main()
