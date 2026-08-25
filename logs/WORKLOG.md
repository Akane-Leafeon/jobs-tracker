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

## 2026-08-25 · 部署

- 确认 GitHub 用户名：**Akane-Leafeon**（原占位 koorye 全部改正：config.json / README / send_email.py / docs/meta.json）
- 空仓库已创建，代码推送完成（main 已跟踪 origin/main）；首次推送因 GCM 登录弹窗卡住超时，改由用户 `! git push` 交互授权后成功，凭据已缓存
- Pages 已生效（pages-build-deployment 运行过）；SMTP Secrets 待用户配置

## 2026-08-25/26 · 大规模扩展：4源→11源 + 公司信息库 + 每日两更

### 背景诊断（用户反馈"主投只有3家公司/更新不及时"）
- 数据分析确认：1234条中82%是小米全量目录；唯一多公司源牛客每日仅20条SSR；run.py 里 huawei/jd 一直是占位符。"主投只有华为/小米/字节"是**源覆盖问题**而非分类问题。
- "更新不及时"两层：①**daily-crawl 定时任务从未运行过**（Actions 里只有 Pages 构建），新仓库首次 cron 被 GitHub 跳过；②小米主投岗确实停在8.12（8.11集中重发792条后硬件线没发新岗），是官网真实状态。
- 对策：工作流加 `push` 触发（推送即跑全链路，不依赖cron）+ cron 加密到 08:00/20:00 两次 + timeout 45min。

### 新增数据源（每个都先探测API契约→写适配器→实测验证）
| 源 | 接口 | 关键坑 |
|---|---|---|
| 腾讯 | POST join.qq.com/api/v1/position/searchPosition | 请求体直接复刻浏览器抓包，400条全量 |
| 阿里 | POST talent-holding.alibaba.com/position/search | 必须先GET页面拿 XSRF-TOKEN cookie 作 `_csrf` 参数；batchId 从 listBatch 动态取 |
| 网易 | POST hr.163.com/api/hr163/position/queryPage | 池子是社招+实习混排，按"校招/应届/届"关键词过滤，且排除标题含"实习" |
| vivo | POST hr-campus.vivo.com/api/JobAd/GetJobAdPageList | PortalId 固定GUID；LocNames 服务端恒为空（无城市）；Category 过滤实习 |
| 拼多多 | POST careers.pddglobalhr.com/api/careers/api/recruit/position/list | 官网域名 careers.pinduoduo.com 直连403，API 在 pddglobalhr 子域；按岗位大类发布仅13条 |
| 汇川 | POST recruit.inovance.com/prod-portal-api/position/ad/search | 必须带 `X-Portal-Id` + `X-Brizoo-Token: bearer` 两个头（Playwright 抓包获得）；310条全量 |
| B站 | jobs.bilibili.com/api/campus/position/positionList | ajSessionId 风控（不在cookie、由页面JS生成）→ Playwright 加载后拦截XHR；翻页点击不稳定，先收第1页 |
| 应届生(增强) | /beijing/ 北京频道表 | 岗位级条目（标题/类型/城市/公司/发布日期五列）；标题前缀是半角`[]`非全角`【】`，日期正则要防 `2026-08-28` 里的 `26-08` 误匹配 |
| 牛客 | 维持20条/天 | pageNo/recruitType/jobType 等 SSR 参数全部实测无效，翻页走被WAF的API，放弃 |

### 探测过但放弃直连的源（聚合源牛客/应届生可覆盖其岗位）
- **华为**：新版 career.huawei.com/cn/campus-recruitment 是纯SPA，"查看职位"点击后只发 license 类接口，岗位列表接口未公开暴露；旧 reccampportal services 已404
- **OPPO**：openapi/position/project/list 可用（拿到 2027届应届生招聘 idRecruitProject=30），但职位列表接口藏在项目交互后未捕获
- **海康威视**：campushr.hikvision.com 首页接口全开放（含2027校招batchId），但 crsJobInfo/* 岗位接口 401 需登录
- **比亚迪**：portal-api 部分接口开放（material），岗位接口要登录 token
- **中兴/大疆**：投递挂 MOKA 平台，MOKA 的 group-by-job 响应是加密串
- **荣耀**：career.hihonor.com TLS 握手直接失败（requests 和 Chromium 都是）
- **宁德时代**：career.catl.com / catl.zhiye.com / catl.jobs.feishu.cn 均不可达
- **米哈游**：ats.openout.mihoyo.com/ats-portal/v1/job/list 存在但要求"职位渠道"参数（值未知）
- **宇树**：unitree.com/cn/job 404

### 公司信息库（解决"北京硬件厂100+人/京外大厂"筛选）
- 招聘API都不返回公司人数 → config.json 新增 `company_info`（约120家：别名/总部/规模档位100+~10000+/行业），人工整理公开资料
- 洞察：开官网校招的公司基本都>100人，白名单按"有校招"即收录
- classify.company_info() 回填 hq_city/size_bucket/industry；reclassify.py 全库重刷
- 前端新增两个筛选：**公司总部（北京/京外/未知）** + **公司规模（含档位包含逻辑：选1000+含10000+）**；公司格显示"总部XX"小标签，tooltip 带完整信息
- 头部新增"各来源最新岗位时间"行（一眼看出哪个源停更），meta.json 增加 source_freshness

### 全量运行结果（2026-08-26 00:41 本地）
- 11源全部成功零报错：新增981条，总库 2215 条
- **主投 40→81条，公司 3→6家**（小米35/汇川26/vivo9/腾讯6/字节4/华为1）
- 副投 18→34；北京841/上海262
- 场景验证：总部京外+主投=42条；总部北京+硬件行业=1011条
- 本地浏览器 DOM 级验证：新筛选器/总部标签/各源时间行/今日新增全部正常

### 遗留
- 网易 2027 秋招尚未开池（当前0条，开招后适配器自动收录）；阿里 2027 批次未开（当前10条为2026届）
- B站翻页点击不稳定（只收第1页10条）；bytedance DOM 通道无发布时间
- 华为/OPPO/海康等受限源待官方接口变化后再攻

