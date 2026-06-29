# Phase 1:项目脚手架 — 完成总结

> 2026-06-25 完成

## 已实现的功能

### ✅ 前端脚手架 (frontend/)

**技术栈:**
- Vue 3.13 + Vite 6 + TypeScript 5.7
- Tailwind CSS 4(新 @theme 语法,无 tailwind.config.js)
- vue-i18n 10(Composition API 模式,legacy: false)
- Pinia 2.2 状态管理
- @unhead/vue SEO 管理
- @intlify/unplugin-vue-i18n Vite 插件

**目录结构:**
```
frontend/
├── package.json
├── vite.config.ts          # Vite + Vue + Tailwind + vue-i18n 插件
├── tsconfig.json
├── index.html
├── .env.example
└── src/
    ├── main.ts             # Pinia + Router + vue-i18n + Unhead 挂载
    ├── App.vue             # 默认布局
    ├── styles/main.css     # Tailwind 4 @theme 定义
    ├── router/index.ts     # 8 个路由(含 requiresAuth/requiresVip meta)
    ├── stores/
    │   ├── user.ts         # Supabase Auth 集成占位
    │   ├── video.ts        # 视频解析状态
    │   └── summary.ts      # AI 总结状态
    ├── i18n/
    │   ├── index.ts        # createI18n 配置
    │   └── locales/
    │       ├── en/common.json
    │       ├── zh-CN/common.json
    │       └── ja/common.json
    ├── layouts/
    │   └── DefaultLayout.vue
    ├── components/
    │   └── LanguageSwitcher.vue
    └── pages/
        ├── HomePage.vue
        ├── DownloadPage.vue
        ├── SummaryPage.vue
        ├── MindmapPage.vue
        ├── QaPage.vue
        ├── BillingPage.vue
        ├── LoginPage.vue
        ├── DmcaPage.vue
        └── NotFoundPage.vue
```

**关键设计:**
- 路由懒加载 (`() => import(...)`)
- 语言切换: `useI18n()` + localStorage 持久化
- 代理配置: `/api` → `http://localhost:8000`
- 3 语言翻译文件(en/zh-CN/ja)已包含基础文案

### ✅ 后端脚手架 (backend/)

**技术栈:**
- FastAPI 0.115 + Uvicorn
- SQLAlchemy 2.0 async + aiosqlite(本地) / asyncpg(生产)
- pydantic-settings 环境变量管理
- python-jose JWT 验证
- Stripe SDK
- OpenAI SDK(OpenRouter 兼容)

**目录结构:**
```
backend/
├── requirements.txt
├── pyproject.toml
├── .env.example
└── app/
    ├── main.py             # FastAPI 入口 + CORS + 路由注册
    ├── config.py           # pydantic-settings Settings 类
    ├── database.py         # SQLAlchemy async engine + session + Base
    ├── models/
    │   └── user.py         # User 模型(Supabase auth.users.id 主键)
    ├── routers/
    │   ├── video.py        # /api/videos 占位
    │   ├── ai.py           # /api/ai 占位
    │   ├── payment.py      # /api/payment 占位
    │   └── auth.py         # /api/auth 占位
    ├── schemas/            # Pydantic schemas(预留)
    ├── deps/               # 依赖注入(预留)
    └── services/           # 业务服务层(预留)
```

**关键设计:**
- 全异步: `create_async_engine` + `async_sessionmaker` + `AsyncSession`
- 数据库切换: 改 `DATABASE_URL` 环境变量即可从 SQLite 迁移到 PostgreSQL
- CORS: 仅允许 `FRONTEND_URL` 域
- 路由模块化: 4 个业务模块(video/ai/payment/auth)独立 APIRouter

### ✅ 根目录文件

- `README.md`: 项目说明、技术栈、快速开始、环境变量模板
- `.gitignore`: Python + Node + 环境变量 + 数据库 + Cloudflare 规则

---

## 技术方案决策

| 决策 | 选择 | 理由 |
|---|---|---|
| Tailwind 版本 | Tailwind CSS 4 | 新 @theme 语法,无需 tailwind.config.js,性能更好 |
| vue-i18n 模式 | Composition API (legacy: false) | Vue 3 推荐模式,useI18n() 更灵活 |
| 数据库 ORM | SQLAlchemy async | 支持 SQLite → PostgreSQL 无缝切换 |
| 部署方案 | Cloudflare Pages + Render/Fly.io | 前端免费,后端 $2-7/月,性价比最高 |
| 后端部署平台 | 待定(Render $7/月 或 Fly.io ~$2/月 或 Railway Hobby $5/月) | FastAPI 不能跑 Cloudflare Workers(Pyodide 限制) |

---

## 待做事项

### Phase 2:核心功能(W2-4)
- [ ] Supabase Auth 集成(注册/登录/JWT 验证)
- [ ] OpenRouter 网关(语言路由 + fallback)
- [ ] yt-dlp 集成(抖音专用 + 主流平台)
- [ ] AI 总结 SSE 流式输出
- [ ] 思维导图前端渲染
- [ ] SQLite 表结构完整 DDL(11 表)

### Phase 3:支付与权限(W5-6)
- [ ] Stripe Checkout 流程
- [ ] Webhook 处理 + 幂等性
- [ ] 订阅管理(升级/降级/取消/试用)
- [ ] RBAC 权限检查(Free/Pro/Premium)
- [ ] VIP 限制逻辑(免费 3 次/天)

### Phase 4:多语言与 SEO(W7-8)
- [ ] 翻译文件补充(当前只有 common.json,需补充 download/summary/billing/errors)
- [ ] hreflang + OG 标签
- [ ] 语言切换 7 步 checklist 完整实现
- [ ] 欢迎邮件 + 支付成功邮件(Brevo)

### Phase 5:测试与上线(W9-10)
- [ ] 单元测试(后端 pytest + 前端 vitest)
- [ ] 集成测试(关键流程)
- [ ] E2E 测试(Playwright)
- [ ] 性能测试(Locust + k6)
- [ ] Cloudflare Pages + Render/Fly.io 部署

---

## 参考文档

- AGENTS.md: 项目设计纲要
- docs/FRONTEND.md: 前端架构规范
- docs/BACKEND.md: FastAPI 后端架构
- docs/DATABASE.md: 数据库设计规范
- docs/AUTHENTICATION.md: 认证系统设计
- docs/AI.md: AI 模型网关设计
- docs/PAYMENT.md: 支付系统设计
- docs/I18N.md: 多语言架构设计
- docs/SECURITY.md: 安全策略规范
- docs/DEPLOYMENT.md: 部署与运维规范
- docs/TESTING.md: 测试策略规范
