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

### 实现过程中的关键决策与坑（当晚实战记录）
1. **应届生网**：日期页/行业页无登录时"共0条"（数据需登录渲染），首页岗位板块也是登录后 XHR。最终只收录入口页"近期截止网申"表格（GBK、纯HTTP、无需Playwright），定位为**截止倒计时提醒源**，条目含 deadline 字段，前端绿色显示"截止 MM-DD"。
2. **字节跳动**：XHR 拦截不稳定（风控时前端不发起请求），最终方案=**DOM 兜底**：页面总是渲染岗位卡片（`a[data-id]` + `[class*="positionItem-..."]` 前缀选择器），XHR 成功时用 JSON（含 publish_time），否则 DOM（无发布时间）。系统 Edge（msedge channel）+ stealth init script（webdriver 伪装）是成功关键；GitHub Actions 上退化 chromium，若被风控则该源自动跳过。
3. **PE/PIE 关键词误伤**：`re.search("pe")` 误命中 "S**pe**cialist"（小米海外岗大量误标 PIE），修复为英文缩写关键词加 `\b` 词边界（`_kw_pattern`）。新增 `scripts/reclassify.py` 全库重分类工具，改关键词后必跑。
4. 牛客 SSR `__INITIAL_STATE__` 正则要停在 `};(function` 边界；模块号是数字 key，遍历 `state.app` 找 `jobListData` 而非硬编码。
5. 小米 publishTime 是纯日期（无时分），统一补 "12:00"。

### 进度
- [x] 项目骨架、config.json、分类引擎、存储、reclassify 工具
- [x] 四个数据源适配器（牛客/应届生网/字节/小米）
- [x] 网页生成器 + 前端（表格/筛选/搜索/收藏/深浅色主题/截止展示）
- [x] GitHub Actions workflow + QQ邮件脚本
- [x] 本地全链路验证：1234 条入库（小米1009+字节200+牛客19+应届生网6），主投40/副投18，DOM 级交互测试全过
- [x] git 首次提交 925161e
- [ ] 等待用户创建 GitHub 空仓库 → 推送 + 启用 Pages + 配 Secrets + 线上验证
