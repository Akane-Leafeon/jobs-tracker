# -*- coding: utf-8 -*-
"""岗位数据存储：增量去重合并，历史全量保留在 data/jobs.json（git 追踪 = 备份）。"""
import hashlib
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "data", "jobs.json")


def job_id(title, company, url):
    """同一岗位唯一标识：来源URL优先，否则用标题+公司+地点。"""
    key = url or f"{company}|{title}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]


def load_jobs():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        # 兼容旧格式：按 id 建索引
        return {j.get("id") or job_id(j.get("title", ""), j.get("company", ""), j.get("url", "")): j for j in data}
    return data


def save_jobs(jobs: dict):
    jobs_list = sorted(jobs.values(), key=lambda j: (j.get("publish_time") or ""), reverse=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs_list, f, ensure_ascii=False, indent=1)
    return jobs_list


def merge_jobs(existing: dict, incoming: list, today: str) -> dict:
    """增量合并：新岗位加入，老岗位刷新 last_seen；返回合并后的 dict 与新增数量。"""
    jobs = {k: dict(v) for k, v in existing.items()}
    added = 0
    for raw in incoming:
        jid = raw["id"]
        if jid in jobs:
            old = jobs[jid]
            # 若抓取到更精确的发布时间则更新
            if raw.get("publish_time") and (not old.get("publish_time") or raw["publish_time"] > old["publish_time"]):
                old["publish_time"] = raw["publish_time"]
            old["last_seen"] = today
        else:
            raw.setdefault("first_seen", today)
            raw["last_seen"] = today
            jobs[jid] = raw
            added += 1
    return jobs, added


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")
