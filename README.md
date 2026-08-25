# 秋招岗位追踪器（jobs-tracker）

> 2027届秋招 · 每天北京时间 08:00 自动抓取新更新岗位 → 生成网页 → GitHub Pages 部署 → QQ邮箱推送新增摘要。

**线上页面：<https://akane-leafeon.github.io/jobs-tracker/>**

## 功能

- 多源抓取：牛客网、应届生网、字节跳动官网、小米官网（可扩展）
- 投递方向匹配：主投 **硬件设计 / 机器人·具身硬件**，副投 **器件设计 / PIE / PE / 硬件测试验证**（关键词规则见 `config.json`）
- 地区优先级：主投北京、副投上海（全部岗位仍收录，可筛选）
- 公司类型标签：硬件大厂 / 互联网大厂 / 具身智能头部 / 芯片半导体大厂 / 仪器仪表（**只打标签不过滤**，避免遗漏；名单在 `config.json` 里随时增删）
- 网页：按发布时间排序 + 搜索 + 多维度筛选 + 收藏（本地存储）+ 今日新收录/更新标记 + 深浅色主题
- 邮件：每日新增岗位摘要（QQ邮箱 SMTP）

## 工作原理

```
GitHub Actions (每天 08:00 北京时间 / 可手动触发)
  ├─ scraper/run.py     抓取各来源 → 分类 → 增量去重合并 → data/jobs.json（git追踪=备份）
  ├─ scripts/gen_page.py 生成 docs/ 静态网页
  ├─ scripts/send_email.py 邮件通知当日新增（无新增则静默跳过）
  └─ 提交并推送 → GitHub Pages 自动发布 docs/
```

## 数据源状态

| 来源 | 方式 | 说明 |
|---|---|---|
| 牛客网 | 纯 HTTP | SSR 页面内嵌 JSON（每日最新20条） |
| 应届生网 | Playwright | 阿里云 WAF JS 挑战，用真实浏览器过 |
| 字节跳动官网 | Playwright | API 有签名墙，浏览器拦截响应 |
| 小米官网 | 纯 HTTP | 公开 JSON API（type=2 校招） |

## 本地运行

```powershell
pip install -r requirements.txt playwright
python -m playwright install chromium

python scraper/run.py          # 抓取+入库
python scripts/gen_page.py     # 生成网页到 docs/
python -m http.server 8000 -d docs   # 本地预览 http://localhost:8000
```

## 部署到 GitHub（一次性配置）

1. 在 github.com 新建**空仓库** `jobs-tracker`（公开仓库；不要勾选任何初始化文件）
2. 本地推送：
   ```powershell
   git remote add origin https://github.com/<你的用户名>/jobs-tracker.git
   git push -u origin main
   ```
3. 仓库 Settings → Pages → Source 选 **Deploy from a branch** → 分支 `main`，目录 `/docs` → Save。等待 1~2 分钟即可访问 `https://<你的用户名>.github.io/jobs-tracker/`。
4. 配置邮件（可选）：Settings → Secrets and variables → Actions → New repository secret，添加三个：
   - `SMTP_USER`：你的QQ邮箱地址（如 `12345678@qq.com`）
   - `SMTP_PASS`：QQ邮箱 **SMTP授权码**（不是登录密码！获取步骤见下）
   - `TO_EMAIL`：收件邮箱（可以和发件相同）
5. Actions 页 → daily-crawl → Run workflow 手动触发一次验证。

### 获取QQ邮箱SMTP授权码

1. 网页登录 mail.qq.com → 设置 → 账号 → 开启「POP3/SMTP服务」（可能需要手机短信验证）
2. 生成授权码（一串16位字母），复制保存
3. 把授权码填到上面第4步的 `SMTP_PASS` Secret 中

## 定制

所有个性化配置都在 `config.json`：

- `regions`：主投/副投城市
- `job_directions`：投递方向及匹配关键词（`keywords` 命中、`exclude_keywords` 排除）
- `company_tags`：公司类型标签名单（增删公司直接改这里，下次运行生效）
- `filters.min_hours_back`：每个来源回溯小时数

## 备份

- `data/jobs.json` 每次运行随 git 提交，历史版本可追溯
- `logs/WORKLOG.md` 记录开发过程与决策
- GitHub 仓库本身即完整备份；本地 `C:\Personal_Files\Git\work\jobs-tracker` 为工作副本

## 免责声明

数据来自各公开页面，仅供个人求职参考；投递前请以官方信息为准。抓取频率低（每日一次），请勿用于商业用途。
