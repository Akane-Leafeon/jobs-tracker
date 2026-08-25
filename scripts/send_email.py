# -*- coding: utf-8 -*-
"""每日新增岗位邮件通知（QQ邮箱 SMTP）。

环境变量（全部通过 GitHub Secrets 注入，不写进代码）：
    SMTP_HOST  SMTP_PORT  SMTP_USER  SMTP_PASS  TO_EMAIL
    FORCE_SEND=1 时即使没有新增也发一封"今日无新增"确认邮件（调试用）。
"""
import json
import os
import smtplib
import sys
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "data", "jobs.json")

SOURCE_NAMES = {
    "yingjiesheng": "应届生网",
    "nowcoder": "牛客网",
    "xiaomi": "小米官网",
    "bytedance": "字节官网",
    "tencent": "腾讯官网",
    "alibaba": "阿里官网",
    "netease": "网易官网",
    "bilibili": "B站官网",
    "vivo": "vivo官网",
    "pdd": "拼多多官网",
    "oppo": "OPPO官网",
    "hikvision": "海康官网",
    "inovance": "汇川官网",
    "mihoyo": "米哈游官网",
    "jd": "京东官网",
    "huawei": "华为官网",
}


def load_new_jobs(today):
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    new = [j for j in jobs if j.get("first_seen") == today]
    new.sort(key=lambda j: j.get("publish_time") or "", reverse=True)
    return new


def build_content(jobs, today):
    primary = [j for j in jobs if j.get("priority") == "主投"]
    secondary = [j for j in jobs if j.get("priority") == "副投"]
    others = [j for j in jobs if not j.get("priority")]

    lines_html = []
    lines_text = []
    total = len(jobs)
    subject = f"【秋招追踪】{today} 新增 {total} 个岗位（主投 {len(primary)} · 副投 {len(secondary)}）"

    def render_group(title, group):
        if not group:
            return
        lines_html.append(f"<h3 style='margin:18px 0 8px'>{title}（{len(group)}）</h3>")
        lines_text.append(f"\n===== {title}（{len(group)}）=====")
        lines_html.append("<ul style='margin:0;padding-left:20px'>")
        for j in group[:30]:  # 邮件里最多列每组前30条，全量在网页看
            t = (j.get("publish_time") or "")[:16]
            title = j.get("title") or ""
            company = j.get("company") or ""
            city = "、".join(j.get("locations") or [])
            url = j.get("url") or ""
            label = j.get("direction_label") or ""
            line_text = f"[{t}] {company} | {title} | {city} {label}"
            if url:
                lines_html.append(
                    f"<li style='margin:6px 0'><b>{company}</b>｜{title}｜{city}"
                    f"<span style='color:#666'>（{label}）</span><br>"
                    f"<span style='font-size:12px;color:#888'>{t}</span> "
                    f"<a href='{url}'>投递/详情</a></li>")
            else:
                lines_html.append(f"<li style='margin:6px 0'>{line_text}</li>")
            lines_text.append(line_text)
        lines_html.append("</ul>")

    render_group("主投 · 硬件设计/机器人硬件", primary)
    render_group("副投 · 器件/PIE/PE/测试验证", secondary)
    render_group("其他相关", others)

    body_html = (
        f"<div style='font-family:sans-serif;font-size:14px;color:#111;max-width:640px'>"
        f"<h2 style='margin:0 0 4px'>秋招岗位追踪 · {today}</h2>"
        f"<p style='color:#555;margin:0 0 12px'>今日新增 {total} 个岗位，"
        f"<a href='https://akane-leafeon.github.io/jobs-tracker/'>点击查看完整列表</a></p>"
        + "".join(lines_html) +
        "<p style='color:#999;font-size:12px;margin-top:18px'>本邮件由自动化脚本发送，"
        "投递前请以官方信息为准。</p></div>")
    body_text = f"秋招岗位追踪 {today}\n今日新增 {total} 个岗位，完整列表：https://akane-leafeon.github.io/jobs-tracker/\n" \
        + "\n".join(lines_text)

    return subject, body_html, body_text


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    jobs = load_new_jobs(today)
    force = os.environ.get("FORCE_SEND") == "1"

    if not jobs and not force:
        print(f"[email] {today}: no new jobs, skip sending")
        return

    if not jobs:
        subject = f"【秋招追踪】{today} 今日无新增岗位"
        body_html = f"<p>今日（{today}）没有抓取到新岗位，可能是来源站点暂无更新或抓取异常，"
                    f"请到 <a href='https://akane-leafeon.github.io/jobs-tracker/'>网页</a> 查看最新数据。</p>"
        body_text = f"今日（{today}）无新增岗位。"
    else:
        subject, body_html, body_text = build_content(jobs, today)

    user = os.environ.get("SMTP_USER", "")
    pwd = os.environ.get("SMTP_PASS", "")
    host = os.environ.get("SMTP_HOST", "smtp.qq.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    to = os.environ.get("TO_EMAIL", "")

    if not (user and pwd and to):
        print("[email] SMTP env not configured, skip sending", file=sys.stderr)
        return

    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = f"秋招追踪 <{user}>"
    msg["To"] = to

    with smtplib.SMTP_SSL(host, port, timeout=30) as server:
        server.login(user, pwd)
        server.sendmail(user, [to], msg.as_string())
    print(f"[email] sent: {subject}")


if __name__ == "__main__":
    main()
