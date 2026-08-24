# 工作日志（备份用）

> 记录本项目开发过程与关键决策，随 git 一起备份。

## 2026-08-24 · 项目启动

### 需求确认（与用户逐项确认）
- **目标**：秋招新更新岗位每日追踪助手，2027届
- **投递方向**：主投 硬件设计（板级/单板/机器人硬件），副投 器件设计、PIE、PE（简历解析结论：北大彭练矛团队器件科研背景使器件方向竞争力强于预期；具身智能硬件岗为黄金匹配方向，单独列为重点）
- **地区**：主投北京，副投上海；其余地区照常收录
- **数据源**：牛客网 + 应届生网 + 大厂官网校招页
- **公司策略**：不做白名单过滤（用户担心遗漏），改为给全部岗位打公司类型标签（硬件大厂/互联网大厂/具身智能头部/芯片半导体大厂/仪器仪表），网页可按标签筛选，名单可随时在 config.json 增删
- **部署**：新建独立 GitHub 仓库 + GitHub Pages（docs 目录）
- **邮件**：QQ邮箱 SMTP 每日摘要
- **更新频率**：每天北京时间 08:00（GitHub Actions cron `0 0 * * *` UTC）

### 技术探测结论（2026-08-24 实地验证）
| 来源 | 结论 |
|---|---|
| 牛客网 | JSON API 被阿里云 WAF 拦截；改用 SSR 页面 `window.__INITIAL_STATE__` 内嵌 JSON（每日最新20条，够追踪新岗） |
| 应届生网 | 入口页可抓（GBK 编码）；日期内容页有 `acw_sc__v2` JS 挑战（50位 arg1 新变体，公开40位算法不适用）→ 用 Playwright 过 |
| 字节跳动 | `search/job/posts` 有自研混淆VM签名墙，纯HTTP 405；filters/csrf 端点开放；硬件分类ID=6938376045242353957，校招=recruitment_id_list ["201"] → Playwright 拦截响应 |
| 小米 | `hr.xiaomi.com/website/api/agent/searchJobPage?type=2` 公开可用，无需登录；详情链接走旧域名 |

### 架构决策
- Python 3 + requests/bs4 为主，Playwright（Chromium）仅用于 WAF/签名源
- 数据模型：jobs.json 增量合并，`first_seen`/`last_seen` 区分"新收录"与"更新"
- 前端：纯静态（无外部依赖），fetch 同源 JSON，收藏存 localStorage（个人状态不上传）
- 隐私：仓库公开（Pages 免费版要求），不含任何个人简历/联系方式；SMTP 凭据只存 GitHub Secrets

### 进度
- [x] 项目骨架、config.json、分类引擎（classify.py）、存储（store.py）
- [x] 小米适配器、牛客适配器
- [x] 网页生成器 + 前端（表格/筛选/搜索/收藏/主题）
- [x] GitHub Actions workflow + 邮件脚本
- [ ] 应届生网适配器（Playwright）
- [ ] 字节适配器（Playwright）
- [ ] 仓库创建、Pages 启用、全链路验证
