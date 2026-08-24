# -*- coding: utf-8 -*-
"""网页生成器：把 web/ 前端 + data/jobs.json 组装进 docs/（GitHub Pages 发布目录）。"""
import json
import os
import shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
DOCS_DIR = os.path.join(ROOT, "docs")
DATA_FILE = os.path.join(ROOT, "data", "jobs.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")


def main():
    os.makedirs(DOCS_DIR, exist_ok=True)

    # 拷贝前端静态资源
    for name in ("index.html", "style.css", "app.js"):
        shutil.copyfile(os.path.join(WEB_DIR, name), os.path.join(DOCS_DIR, name))

    # 拷贝岗位数据
    if os.path.exists(DATA_FILE):
        shutil.copyfile(DATA_FILE, os.path.join(DOCS_DIR, "jobs.json"))
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)
    else:
        jobs = []
        with open(os.path.join(DOCS_DIR, "jobs.json"), "w", encoding="utf-8") as f:
            json.dump([], f)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # 统计
    total = len(jobs)
    added_today = sum(1 for j in jobs if j.get("first_seen") == today)
    primary = sum(1 for j in jobs if j.get("priority") == "主投")
    secondary = sum(1 for j in jobs if j.get("priority") == "副投")
    beijing = sum(1 for j in jobs if j.get("region_level") == "primary")
    shanghai = sum(1 for j in jobs if j.get("region_level") == "secondary")

    meta = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "updated_date": today,
        "totals": {
            "total": total,
            "added_today": added_today,
            "primary": primary,
            "secondary": secondary,
            "beijing": beijing,
            "shanghai": shanghai,
        },
        "directions": cfg["job_directions"],
        "company_tags": list(cfg["company_tags"].keys()),
        "site_url": cfg["deploy"]["site_url"],
    }
    with open(os.path.join(DOCS_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    print(f"page generated: total={total}, added_today={added_today}, primary={primary}, secondary={secondary}")
    print(f"output dir: {DOCS_DIR}")


if __name__ == "__main__":
    main()
