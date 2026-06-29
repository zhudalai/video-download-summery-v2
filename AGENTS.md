# AI 万能视频下载总结器 — 项目设计纲要

> 输入视频链接 → 自动解析 1800+ 平台视频下载 + AI 视频总结 + 思维导图 + 问答 + Stripe VIP 订阅。V1 支持英语/中文/日语,1-2 个月 MVP 上线。

---

## 一、技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | Vue 3 + Vite 7 + Tailwind CSS 4 | 原方案,SPA 形态,SEO 靠预渲染 + hreflang 补位 |
| 后端 | FastAPI (Python 异步) | 原方案,与 yt-dlp / OpenRouter SDK 天然集成 |
| 数据库 | SQLite (开发) → PostgreSQL (生产) | MVP 用 SQLite 零运维,用户过 1k 后迁移 |
| 认证 | Supabase Auth (云端版) | 国际化友好、GDPR 合规、Stripe 集成便利 |
| AI 模型 | OpenRouter 统一网关 | 按语言路由:中文→DeepSeek,英文→Claude/GPT |
| 视频下载 | yt-dlp | 1800+ 平台,含抖音专用解析 |
| 支付 | Stripe Checkout + Webhook | 30+ 语言自动本地化,135+ 币种 |
| 思维导图 | markmap-lib + markmap-view | 交互式、可导出 PNG/SVG |
| 流式输出 | SSE (Server-Sent Events) | Markdown 摘要实时推送 |
| i18n | vue-i18n + 依赖注入 LocalizedException | 前端文案 + 后端错误消息双语对齐 |
| 部署 | Cloudflare Pages(前端) + Workers(后端) + D1(数据库) | 全免费方案,全球 300+ CDN,Python Workers 原生支持 FastAPI |

---

## 二、核心业务流程

```
用户输入链接 → 平台分流(抖音/通用) → yt-dlp 解析视频信息
    → 提取字幕/转录文本 → OpenRouter 流式生成 Markdown 摘要(SSE)
    → 生成思维导图(markmap) → 支持基于字幕的自由问答
    → 可选:下载视频文件到本地(不持久化到服务器)
    → 免费用户 3 次/天,VIP 不限(Stripe 订阅)
```

---

## 三、多语言架构 (i18n)

- **URL 结构:** 子目录式 `/en/` `/zh/` `/ja/` (SEO 权重集中)
- **前端:** vue-i18n,按语言分文件夹,`import.meta.glob` 懒加载
- **后端:** 自定义 `LocalizedHTTPException`,依赖注入 `get_locale()` (从 JWT 用户偏好取)
- **AI 总结:** System prompt 内嵌语言指令,缓存键带 `lang` 部分
- **SEO:** `@unhead/vue` 注入 hreflang + OG 标签本地化
- **Email:** Brevo 事务邮件,模板硬编码三语言版本

---

## 四、核心功能模块

1. **视频解析与下载** — yt-dlp 引擎,抖音专用模块,格式/清晰度选择
2. **AI 视频总结** — OpenRouter 流式 Markdown,SSE 推送
3. **AI 思维导图** — markmap 交互式,支持全屏/缩放/导出
4. **AI 视频问答** — 基于字幕文本的 RAG 问答
5. **字幕导出** — SRT / VTT / TXT 格式
6. **用户认证** — Supabase Auth (Google/Apple/Email)
7. **VIP 订阅** — Stripe Checkout + Webhook 回调
8. **SEO/GEO** — hreflang + 结构化数据 + AI 优化文章生成

---

## 五、部署方案(免费优先)

### 5.1 MVP 全免费方案(Cloudflare 全家桶)

| 层 | 服务 | 免费额度 | 限制 |
|---|---|---|---|
| **前端** | Cloudflare Pages | 完全免费 | 500 次构建/月,100GB 带宽 |
| **后端** | Cloudflare Workers + Python | 10 万次请求/天,10ms CPU/次 | FastAPI 原生支持(2026 GA) |
| **数据库** | Cloudflare D1 | 5GB 存储,每天 500 万行读取 | SQLite 兼容,全球复制 |
| **域名** | Cloudflare Registrar | 成本价(.com ~$10/年) | 无加价 |
| **认证** | Supabase Auth | 50,000 MAU | 独立服务 |

**优势:**
- 前端 + 后端 + 数据库**全免费**(仅域名年付 ~$10)
- 全球 300+ 数据中心,性能极佳
- 无冷启动(Render/Railway 都会休眠)
- D1 是 SQLite 兼容,与 MVP 技术栈一致
- Workers Python 支持 FastAPI、httpx、pydantic

**限制:**
- Workers CPU 限制 10ms/次 → LLM 调用需放到外部(OpenRouter)
- D1 是单区域主数据库(读延迟可能高),但 MVP 足够
- Supabase Free 7 天不活跃会暂停(需每周至少一次请求)

### 5.2 Workers CPU 不够时的备用方案

**方案 A(推荐):升级 Workers**
- $5/月 → 500 万请求,放宽 CPU 限制
- 前端仍用 Pages(免费)

**方案 B:后端改用 Render**
- 前端:Cloudflare Pages(免费)
- 后端:Render Starter $7/月(512MB RAM,无 CPU 限制)
- 数据库:Supabase Free(免费)
- **总计 ~$8/月**

### 5.3 其他平台 2026 年免费额度对比

| 平台 | 免费额度 | 付费起步 | 备注 |
|---|---|---|---|
| **Cloudflare Workers** | 10 万请求/天 | $5/月(500 万) | 最佳免费方案,CPU 限制严 |
| **Vercel Hobby** | 完全免费 | $20/月 Pro | 前端首选,后端需 Edge Functions |
| **SnapDeploy** | 完全免费(10 次部署/天) | 无付费档 | 适合原型,功能有限 |
| **Render** | 无永久免费(只有试用) | $7/月 Starter | 15 分钟休眠,冷启动 30-60s |
| **Railway** | $5 试用金(30 天) | $1/月起(按需) | 已取消永久免费 |
| **Fly.io** | 无永久免费(只有试用) | ~$2/月(最小 VM) | 需信用卡 |

### 5.4 部署决策树

```
MVP 阶段(0-1000 用户)
├─ 前端: Cloudflare Pages(免费)
├─ 后端: Cloudflare Workers(免费,10 万请求/天)
├─ 数据库: Cloudflare D1(免费,5GB)
├─ 认证: Supabase Auth(免费,50k MAU)
└─ 域名: Cloudflare Registrar($10/年)
    → 总成本:$10/年(仅域名)

成长阶段(1000-10000 用户)
├─ Workers 升级到 $5/月(如果 CPU 不够)
├─ D1 升级到 $1.5/月(如果存储不够)
├─ Supabase 升级到 $25/月(如果 MAU 超 50k)
└─ 后端可迁移到 Render $7/月(如果需要无 CPU 限制)
    → 总成本:$7-30/月

规模化(10000+ 用户)
├─ 迁移到 Render/Fly.io + Supabase Pro
├─ 后端 $7-25/月 + 数据库 $25/月
└─ 总成本:$32-50/月
```

---

## 六、V1 范围 (1-2 个月)

**语言:** 英语 + 中文(简体) + 日语
**功能:** URL 解析 + 转录 + AI 总结 + 基本思维导图 + Stripe 支付(信用卡/Apple Pay/Google Pay)
**SEO:** hreflang 三语言 + 子目录 URL + FAQ schema
**客服:** Email(英/中) + Discord 英社区
**不做:** 团队订阅、API、本地支付方式、移动 App、管理后台 i18n

---

## 七、V2 扩展 (6-18 个月)

- 新增语言: 韩语 + 西班牙语 + 繁体中文
- Stripe 本地支付: iDEAL(荷兰) / PIX(巴西) / Alipay+WeChat(中国)
- 移动 App (React Native / Flutter)
- 浏览器扩展 (Chrome/Firefox/Edge)
- 团队知识库 + API 端点
- GEO 优化文章矩阵(月 15 篇 AI 辅助 + 人工编辑)

---

## 八、文档索引

| 文档 | 内容 |
|---|---|
| [docs/FRONTEND.md](docs/FRONTEND.md) | 前端架构、组件规范、vue-i18n 配置、Tailwind 4 约定 |
| [docs/BACKEND.md](docs/BACKEND.md) | FastAPI 项目结构、路由设计、依赖注入、SSE 实现 |
| [docs/DATABASE.md](docs/DATABASE.md) | SQLite → PostgreSQL 迁移路径、表结构、索引策略 |
| [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) | Supabase Auth 集成、JWT 验证、用户偏好存储 |
| [docs/AI.md](docs/AI.md) | OpenRouter 网关、语言路由、Prompt 模板、缓存策略 |
| [docs/PAYMENT.md](docs/PAYMENT.md) | Stripe Checkout、Webhook、订阅管理、PDF 收据 |
| [docs/I18N.md](docs/I18N.md) | 多语言架构、翻译流程、hreflang、SEO 本地化 |
| [docs/SECURITY.md](docs/SECURITY.md) | 安全策略、DMCA、GDPR、版权风险、速率限制 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Cloudflare Pages + Workers + D1 部署、CI/CD、环境变量 |
| [docs/TESTING.md](docs/TESTING.md) | 测试策略、单元/集成/E2E 测试规范 |

---

## 九、MVP 时间线

| 周 | 任务 |
|---|---|
| W1-2 | 项目脚手架、Supabase Auth、OpenRouter 网关、yt-dlp 集成 |
| W3-4 | AI 总结 SSE 流式、思维导图、SQLite 表结构 |
| W5-6 | Stripe 支付、VIP 限制逻辑、用户偏好 |
| W7-8 | vue-i18n 三语言、hreflang、OG 标签、SEO 基础 |
| W9-10 | 测试、DMCA 页面、隐私政策、Cloudflare Pages + Workers 部署上线 |

---

## 十、关键决策记录

- **为什么 SPA 而非 SSR?** 团队熟悉 Vue 3,Vite 生态成熟;SEO 靠预渲染 + hreflang 可补位;后续有需要可加 Vite SSR
- **为什么 SQLite / D1?** MVP 阶段零运维,Cloudflare D1 是 SQLite 兼容,与 Cloudflare Workers 天然集成;用户过 1k 后迁移 PostgreSQL
- **为什么 OpenRouter?** 统一网关可灵活路由(中文 DeepSeek 成本优先,英文 Claude 质量优先),避免 vendor lock-in
- **为什么完整下载功能?** 差异化定位需要(竞品 Summarize.tech 只做总结);法律风险通过"不持久化 + DMCA + 黑名单"缓解
- **为什么三语言 V1?** 英语(全球) + 中文(DeepSeek 最强) + 日语(付费意愿高);日语审校预算约 $200-300
- **为什么 Cloudflare Workers + D1?** 2026 年唯一的全免费部署方案(前端+后端+数据库),全球 300+ CDN,无冷启动问题;Workers 已 GA 支持 Python/FastAPI

---

## 十一、验证清单

### 功能
- [ ] 输入 B 站链接 → 解析视频信息 → 生成中文 AI 总结(SSE 流式)
- [ ] 输入 YouTube 链接 → 生成英文 AI 总结 + 思维导图
- [ ] 语言切换:中→日,页面文案 + AI 总结 + 错误消息全部切换
- [ ] Stripe 支付:信用卡购买 Pro 订阅,Webhook 回调更新 VIP 状态
- [ ] SEO:`/zh/` `/en/` `/ja/` 三页面 hreflang 互相指向

### 部署(Cloudflare)
- [ ] Cloudflare Pages 前端部署成功,自定义域名 HTTPS 生效
- [ ] Cloudflare Workers 后端部署成功,/api/docs Swagger UI 可访问
- [ ] Cloudflare D1 数据库连接成功,表迁移完成
- [ ] 环境变量(Supabase/OpenRouter/Stripe)注入 Workers

### 性能
- [ ] LCP < 2.5s
- [ ] INP < 100ms
- [ ] CLS < 0.1
- [ ] AI 总结 P95 < 15s
- [ ] Workers 日请求 < 10 万(MVP 阶段)
