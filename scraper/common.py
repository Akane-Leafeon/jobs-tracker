# -*- coding: utf-8 -*-
"""爬虫公共模块：HTTP 会话、重试、日志。"""
import logging
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)


def get_logger(name):
    return logging.getLogger(name)


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
    })
    return s


def fetch(session, url, method="GET", retries=3, timeout=20, **kwargs):
    """带重试与退避的请求；返回 Response 或 None。"""
    last_err = None
    for i in range(retries):
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in (200, 201):
                return resp
            if resp.status_code in (403, 429):
                time.sleep(3 * (i + 1))
            last_err = RuntimeError(f"HTTP {resp.status_code} for {url}")
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (i + 1))
    get_logger("fetch").warning("fetch failed: %s (%s)", url, last_err)
    return None
