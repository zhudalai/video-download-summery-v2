# 部署与运维规范文档

> 项目: Video Download Summary
> 版本: 1.0.0
> 最后更新: 2026-06-25
> 维护者: DevOps / 高级开发者

---

## 目录

1. [部署架构图](#1-部署架构图)
2. [CI/CD 流程](#2-cicd-流程)
3. [环境变量管理](#3-环境变量管理)
4. [域名与 DNS](#4-域名与-dns)
5. [CDN 与缓存](#5-cdn-与缓存)
6. [监控与告警](#6-监控与告警)
7. [日志管理](#7-日志管理)
8. [备份与恢复](#8-备份与恢复)
9. [扩缩容](#9-扩缩容)
10. [验证清单](#10-验证清单)

---

## 1. 部署架构图

### 1.1 逻辑架构图

```
                                    ┌─────────────────────────────────────────────────┐
                                    │                 用户 (浏览器)                    │
                                    └───────────────────────�─────────────────────────�
                                                            │ HTTPS
                                                            ▼
                                    �─────────────────────────────────────────────────┐
                                    │            Cloudflare CDN (全球)                 │
                                    │  �──────────────┐   ┌────────────────────────�    │
                                    │  │  DNS 解析     │   │  DDoS 防护 / WAF        │    │
                                    │  │  SSL 终结     │   │  边缘缓存 / 压缩        │    │
                                    │  └──────┬───────┘   └────────────┬───────────┘    │
                                    └─────────�────────────────────────┼─────────────────┘
                                              │                        │
                   ┌──────────────────────────┼────────────────────────┼─────────────────────────�
                   │                          │                        │                         |
                   │  Frontend (SPA)          │   Backend API          │   辅助服务              │
                   │                          │                        │                         |
                   ▼                          ▼                        ▼
┌────────────────────────────�  ┌─────────────────────────────�  �─────────────────────�
│       Vercel Edge          │  │     Railway / Fly.io        │  │   Supabase Auth     │
│                            │  │                             │  │   (独立服务)         │
│  Vue 3 + Vite 7           │  │  FastAPI (Python 3.12)     │  └─────────�───────────�
│  - HTML/CSS/JS             │  │  - REST API                 │            │
│  - 自动 PR 预览            │  │  - AI 总结服务               │            │
│  - Web Vitals 优化         │  │  - Webhook 处理              │            │
│                            │  │  - PDF 生成                 │            │
└────────────────────────────┘  └──────────┬──────────────────┘            │
                                           │                               │
                   ┌───────────────────────┼───────────────────────────────┼──────────────┐
                   │                       │                               │              │
                   ▼                       ▼                               ▼              ▼
     ┌──────────────────┐    ┌──────────────────┐          ┌──────────────────┐  ┌─────────────�
     │  Upstash Redis   │    │  Cloudflare R2   │          │     Stripe       │  │   Brevo     │
     │  (缓存 + 队列)    │    │  (对象存储)       │          │    (支付)        │  │   (邮件)    │
     └──────────────────┘    └──────────────────�          └──────────────────┘  └─────────────┘
                   │                       │
                   │                       │
                   ▼                       ▼
     �──────────────────�    �──────────────────�          ┌──────────────────┐
     │   PostgreSQL     │    │    OpenRouter    │          │    Sentry        │
     │   (数据库)        │    │   (AI 模型)      │          │   (错误监控)      │
     └──────────────────┘    └──────────────────�          └──────────────────┘
```

### 1.2 数据流图

```
用户请求 (前端)
     │
     ▼
�────────────────�
│  Cloudflare CDN │ ← SSL/TLS 1.3
│  (边缘节点)     │ ← Brotli 压缩
└───────┬────────�
        │
        ├─ 静态资源 (JS/CSS/图片) → Vercel Edge (缓存 1 年)
        │
        └─ API 请求 (/api/*) → Railway/Fly.io (无缓存/私密缓存)
                                │
                                ├─ 认证中间件 → Supabase Auth (JWT 校验)
                                ├─ AI 总结 → OpenRouter API
                                ├─ 支付 → Stripe API
                                ├─ PDF 上传 → Cloudflare R2
                                ├─ 缓存查询 → Upstash Redis
                                └─ 数据读写 → PostgreSQL
```

### 1.3 第三方服务依赖矩阵

| 服务 | 用途 | 必要性 | SLA 要求 |
|---|---|---|---|
| Vercel | 前端托管 + CDN | 必需 | 99.99% |
| Railway / Fly.io | 后端计算 | 必需 | 99.95% |
| Supabase Auth | 用户认证 | 必需 | 99.9% |
| Stripe | 支付处理 | 必需 | 99.99% |
| PostgreSQL (托管) | 主数据库 | 必需 | 99.95% |
| OpenRouter | AI 总结 | 必需 | 99.9% |
| Brevo | 邮件发送 | 必需 | 99.9% |
| Upstash Redis | 缓存/队列 | 可选 (Phase 2) | 99.9% |
| Cloudflare R2 | PDF 存储 | 可选 (Phase 2) | 99.99% |
| Sentry | 错误监控 | 必需 | 99.9% |
| UptimeRobot | 可用性监控 | 必需 | - |

---

## 2. CI/CD 流程

### 2.1 工作流文件结构

```
.github/
└── workflows/
    ├── ci.yml                 # 主 CI 工作流 (PR 检查)
    ├── deploy-frontend.yml   # 前端部署 (main 分支触发)
    ├── deploy-backend.yml    # 后端部署 (main 分支触发)
    ├── security-scan.yml     # 安全扫描 (每日 + PR)
    └── db-migrate.yml        # 数据库迁移 (手动触发 + main 分支自动)
```

### 2.2 CI 主工作流 (`ci.yml`)

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  # ==================== 前端 CI ====================
  frontend-lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ./frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm type-check   # vue-tsc --noEmit

  frontend-test:
    runs-on: ubuntu-latest
    needs: frontend-lint
    defaults:
      run:
        working-directory: ./frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
      - run: pnpm install --frozen-lockfile
 pnpm test -- --coverage
      - uses: actions/upload-artifact@v4
        with:
          name: frontend-coverage
          path: frontend/coverage/
          retention-days: 14

  frontend-build:
    runs-on: ubuntu-latest
    needs: frontend-test
    defaults:
      run:
        working-directory: ./frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm build
      # 验证构建产物大小 < 500KB (gzip)
      - name: Check bundle size
        run: |
          du -sh dist/assets/*.js | awk '$1 > "500KB" {exit 1}'
      - uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist/
          retention-days: 7

  # ==================== 后端 CI ====================
  backend-lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ./backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: mypy app/ --strict

  backend-test:
    runs-on: ubuntu-latest
    needs: backend-lint
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    defaults:
      run:
        working-directory: ./backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run Alembic migrations
        run: alembic upgrade head
      - name: Run pytest with coverage
        run: pytest --cov=app --cov-report=xml --cov-report=term-missing
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
      # 覆盖率不能低于 main 分支
      - name: Check coverage threshold
        run: |
          coverage report --fail-under=80
      - uses: actions/upload-artifact@v4
        with:
          name: backend-coverage
          path: backend/coverage.xml
          retention-days: 14

  # ==================== 集成测试 ====================
  e2e-test:
    runs-on: ubuntu-latest
    needs: [frontend-build, backend-test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - name: Install Playwright
        run: npx playwright install --with-deps chromium
      - name: Run E2E tests
        run: npx playwright test
        env:
          BASE_URL: http://localhost:3000
      - uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 7

  # ==================== 安全检查 ====================
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
          format: 'sarif'
          output: 'trivy-results.sarif'
      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'
      - name: Run pip-audit (backend)
        run: |
          pip install pip-audit
          cd backend && pip-audit -r requirements.txt
```

### 2.3 前端部署工作流 (`deploy-frontend.yml`)

```yaml
# .github/workflows/deploy-frontend.yml
name: Deploy Frontend

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
      - '.github/workflows/deploy-frontend.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Vercel CLI
        run: npm install -g vercel

      # PR 预览部署
      - name: Deploy Preview
        if: github.event_name == 'pull_request'
        run: |
          vercel pull --yes --environment=preview --token=${{ secrets.VERCEL_TOKEN }}
          vercel build --preview --token=${{ secrets.VERCEL_TOKEN }}
          vercel deploy --prebuilt --token=${{ secrets.VERCEL_TOKEN }}

      # 生产部署
      - name: Deploy Production
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: |
          vercel pull --yes --environment=production --token=${{ secrets.VERCEL_TOKEN }}
          vercel build --prod --token=${{ secrets.VERCEL_TOKEN }}
          vercel deploy --prebuilt --prod --token=${{ secrets.VERCEL_TOKEN }}

      # Web Vitals 检查
      - name: Check Web Vitals
        run: |
          # 调用 Vercel Analytics API 验证 LCP < 2.5s
          curl -s "https://api.vercel.com/v1/analytics/web-vitals" \
            -H "Authorization: Bearer ${{ secrets.VERCEL_TOKEN }}" | \
            jq '.lcp.p75' | xargs -I {} test {} -lt 2500
```

### 2.4 后端部署工作流 (`deploy-backend.yml`)

```yaml
# .github/workflows/deploy-backend.yml
name: Deploy Backend

on:
  push:
    branches: [main]
    paths:
      - 'backend/**'
      - 'Dockerfile'
      - '.github/workflows/deploy-backend.yml'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # 构建 Docker 镜像
      - name: Build Docker image
        run: |
          docker build -t backend:${{ github.sha }} ./backend
          docker tag backend:${{ github.sha }} backend:latest

      # 推送镜像到 Railway/Fly.io 仓库
      - name: Push to Registry (Fly.io 示例)
        uses: superfly/flyctl-actions/setup-flyctl@master
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
        run: |
          flyctl deploy --image backend:${{ github.sha }} \
            --config fly.production.toml \
            --wait-timeout 300

      # Railway 方案 (备选)
      # - name: Deploy to Railway
      #   uses: bervProject/actions@v1
      #   with:
      #     railway_token: ${{ secrets.RAILWAY_TOKEN }}
      #     service: backend-service

      # 烟气测试
      - name: Smoke Test
        run: |
          curl -f https://api.yourdomain.com/health || exit 1
          curl -f https://api.yourdomain.com/api/v1/health/db || exit 1
          curl -f https://api.yourdomain.com/api/v1/health/redis || exit 1

      # 回滚 (如果烟气测试失败)
      - name: Rollback on failure
        if: failure()
        run: |
          flyctl releases rollback --config fly.production.toml
```

### 2.5 数据库迁移工作流 (`db-migrate.yml`)

```yaml
# .github/workflows/db-migrate.yml
name: Database Migration

on:
  workflow_dispatch:   # 手动触发
    inputs:
      environment:
        description: '目标环境'
        required: true
        default: 'production'
        type: choice
        options:
          - staging
          - production
  push:
    branches: [main]
    paths:
      - 'backend/alembic/**'

jobs:
  migrate:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'production' }}
    steps:
      - uses: actions/checkout@v4
    
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
    
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
    
      # 迁移前备份 (安全网)
      - name: Pre-migration backup
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          # 使用 Railway/Fly.io CLI 触发即时备份
              flyctl pg dump --config fly.production.toml > backup_$(date +%Y%m%d_%H%M%S).sql
      
      # 执行迁移
      - name: Run Alembic upgrade
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          alembic upgrade head
      
      # 验证迁移成功
      - name: Verify migration
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          alembic current
```

### 2.6 PR 检查规则

合并 PR 前必须满足以下条件:

| 检查项 | 工具 | 阈值/要求 |
|---|---|---|
| ESLint | `eslint` | 0 errors, warnings < 10 |
| TypeScript | `vue-tsc` | 0 type errors |
| 前端测试 | `vitest` | 全部通过 |
| 前端覆盖率 | `vitest --coverage` | ≥ 80%, 不低于 main |
| Ruff | `ruff check` | 0 errors |
| Mypy | `mypy --strict` | 0 errors |
| 后端测试 | `pytest` | 全部通过 |
| 后端覆盖率 | `pytest --cov` | ≥ 80%, 不低于 main |
| 安全扫描 | `trivy` | 无 CRITICAL/HIGH |
| 依赖审计 | `pip-audit` | 无已知漏洞 |
| 构建产物 | `du` | JS bundle < 500KB gzip |
| E2E | `playwright` | 核心流程通过 |

---

## 3. 环境变量管理

### 3.1 变量分类

#### 前端变量 (`frontend/.env.example`)

```bash
# ============================================
# 前端环境变量 (提交到 Git 的示例文件)
# 注意: 所有 VITE_ 前缀的变量会打包到客户端 JS
# ============================================

# ---- 必需 ----
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_REPLACE_WITH_REAL_KEY
VITE_SENTRY_DSN=https://xxxxx@o123456.ingest.sentry.io/123456

# ---- 可选 ----
VITE_APP_NAME=Video Summary
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_AI_SUMMARY=true
VITE_MAX_VIDEO_DURATION_SECONDS=7200

# ---- 敏感变量 (不要加 VITE_ 前缀,仅构建时使用) ----
# VERCEL_TOKEN=xxxxx   (仅 CI 使用,不写入 .env.example)
```

#### 后端变量 (`backend/.env.example`)

```bash
# ============================================
# 后端环境变量 (提交到 Git 的示例文件)
# ============================================

# ---- 应用 ----
APP_NAME=video-summary
APP_ENV=production
APP_DEBUG=false
APP_SECRET_KEY=change-me-in-production
APP_LOG_LEVEL=info

# ---- 服务器 ----
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=4
SERVER_ALLOWED_HOSTS=api.yourdomain.com

# ---- 数据库 ----
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
DATABASE_POOL_MIN=5
DATABASE_POOL_MAX=20
DATABASE_POOL_TIMEOUT=30

# ---- Redis (可选) ----
REDIS_URL=redis://default:pass@host:6379/0
REDIS_CACHE_TTL=2592000

# ---- Supabase ----
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxx
SUPABASE_JWT_SECRET=xxxxx

# ---- Stripe ----
STRIPE_SECRET_KEY=sk_live_REPLACE_WITH_REAL_KEY
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_ID=price_xxxxx

# ---- OpenRouter (AI) ----
OPENROUTER_API_KEY=sk-or-xxxxx
OPENROUTER_MODEL=google/gemini-2.0-flash-001
OPENROUTER_MAX_TOKENS=4096

# ---- Brevo (邮件) ----
BREVO_API_KEY=xxxxx
BREVO_FROM_EMAIL=noreply@yourdomain.com
BREVO_FROM_NAME=Video Summary

# ---- Cloudflare R2 (可选) ----
R2_ENDPOINT=https://xxxxx.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=xxxxx
R2_SECRET_ACCESS_KEY=xxxxx
R2_BUCKET=video-summary-receipts
R2_PUBLIC_URL=https://receipts.yourdomain.com

# ---- Sentry ----
SENTRY_DSN=https://xxxxx@o123456.ingest.sentry.io/123456
SENTRY_TRACES_SAMPLE_RATE=0.1

# ---- 安全 ----
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
ENCRYPTION_KEY=xxxxx
```

### 3.2 环境文件规范

| 文件 | 用途 | 提交 Git | 说明 |
|---|---|---|---|
| `.env.example` | 变量清单 | 是 | 所有必需 + 可选变量,值为占位符 |
| `.env.local` | 本地开发 | 否 | 真实值,加入 `.gitignore` |
| `.env.test` | 测试环境 | 否 | CI 使用,通过 GitHub Secrets 注入 |
| `.env.production` | 生产环境 | 否 | 通过平台 Dashboard/CLI 设置 |

### 3.3 平台 Secret 设置

#### Vercel (前端)

```bash
# 通过 CLI 设置
vercel env add VITE_SUPABASE_ANON_KEY production
vercel env add VITE_STRIPE_PUBLISHABLE_KEY production

# 通过 Dashboard 设置
# Settings → Environment Variables → Add New
```

#### Railway (后端)

```bash
# 通过 CLI 设置
railway variables set DATABASE_URL="postgresql+..."
railway variables set STRIPE_SECRET_KEY="sk_live_..."

# 通过 Dashboard 设置
# Project → Variables → Add Variable
```

#### Fly.io (后端)

```bash
# 通过 CLI 设置 (推荐)
flyctl secrets set DATABASE_URL="postgresql+..."
flyctl secrets set STRIPE_SECRET_KEY="sk_live_..."

# 批量设置
flyctl secrets set $(cat .env.production | grep -v '^#' | xargs)

# 通过 Dashboard 设置
# Dashboard → App → Secrets → Add Secret
```

### 3.4 Secret 轮换策略

| Secret 类型 | 轮换周期 | 轮换流程 | 影响范围 |
|---|---|---|---|
| JWT Secret (`APP_SECRET_KEY`) | 90 天 | 1. 生成新密钥 2. 双密钥并行 7 天 3. 停用旧密钥 | 所有用户需重新登录 |
| Supabase Service Key | 180 天 | 1. Supabase Dashboard 重新生成 2. 更新平台 Secret | 后端服务重启 |
| Stripe API Key | 180 天 | 1. Stripe Dashboard 重新生成 2. 更新平台 Secret 3. 验证 Webhook | 支付功能中断 5 分钟 |
| OpenRouter API Key | 180 天 | 1. OpenRouter Dashboard 重新生成 2. 更新平台 Secret | AI 总结功能中断 5 分钟 |
| Brevo API Key | 180 天 | 1. Brevo Dashboard 重新生成 2. 更新平台 Secret | 邮件发送中断 5 分钟 |
| R2 Access Key | 180 天 | 1. Cloudflare Dashboard 重新生成 2. 更新平台 Secret | PDF 上传中断 5 分钟 |
| Database 密码 | 365 天 | 1. 平台 Dashboard 修改 2. 更新连接字符串 | 需重启服务 |

### 3.5 敏感变量清单

| 变量 | 敏感级别 | 存储方式 | 可提交 Git | 说明 |
|---|---|---|---|---|
| `VITE_*` (前端) | 低 | Vercel Env | 是 (占位符) | 打包到客户端 JS |
| `DATABASE_URL` | 高 | 平台 Secret | 否 | 含密码 |
| `STRIPE_SECRET_KEY` | 高 | 平台 Secret | 否 | 支付核心 |
| `STRIPE_WEBHOOK_SECRET` | 高 | 平台 Secret | 否 | Webhook 验证 |
| `SUPABASE_SERVICE_ROLE_KEY` | 高 | 平台 Secret | 否 | 绕过 RLS |
| `SUPABASE_JWT_SECRET` | 高 | 平台 Secret | 否 | JWT 签名 |
| `OPENROUTER_API_KEY` | 高 | 平台 Secret | 否 | AI API 计费 |
| `BREVO_API_KEY` | 高 | 平台 Secret | 否 | 邮件 API |
| `R2_SECRET_ACCESS_KEY` | 高 | 平台 Secret | 否 | 对象存储 |
| `APP_SECRET_KEY` | 高 | 平台 Secret | 否 | 应用加密 |
| `ENCRYPTION_KEY` | 高 | 平台 Secret | 否 | 数据加密 |
| `SENTRY_DSN` | 中 | 平台 Secret | 是 (占位符) | 仅上报,风险低 |

---

## 4. 域名与 DNS

### 4.1 域名注册

| 注册商 | 优势 | 劣势 | 推荐场景 |
|---|---|---|---|
| Cloudflare Registrar | 成本价,免费 DNSSEC,集成 CDN | 仅支持部分 TLD | **首选** |
| Namecheap | 免费 WhoisGuard,支持 .com | 需单独配置 DNS | 备选 |
| Porkbun | 成本价,免费 Whois | 较新 | 备选 |

**推荐**: 使用 Cloudflare Registrar 注册 `.com` 域名,自动集成 DNS + CDN + SSL。

### 4.2 DNS 配置

#### Cloudflare DNS 面板配置

| 类型 | 名称 | 内容 | TTL | 代理状态 |
|---|---|---|---|---|
| CNAME | `yourdomain.com` | `cname.vercel-dns.com` | 自动 | 仅 DNS (Vercel 自带 CDN) |
| CNAME | `www` | `cname.vercel-dns.com` | 自动 | 仅 DNS |
| CNAME | `api` | `railway.app` 或 `fly.dev` | 自动 | 仅 DNS (后端不需要 Cloudflare 代理) |
| CNAME | `docs` | `gitbook.io` | 自动 | 仅 DNS |
| CNAME | `status` | `stats.uptimerobot.com` | 自动 | 仅 DNS |
| MX | `@` | `mx1.improvmx.com` (优先级 10) | 自动 | 仅 DNS |
| MX | `@` | `mx2.improvmx.com` (优先级 20) | 自动 | 仅 DNS |
| TXT | `@` | `v=spf1 include:spf.improvmx.com ~all` | 自动 | 仅 DNS |

#### 注意事项

- **不要开启 Cloudflare 代理 (橙色云) 给 API 子域名**: Stripe Webhook 需要稳定 IP
- **根域名必须用 CNAME Flattening**: Cloudflare 支持将 CNAME 在根域名解析为 A 记录
- **CAA 记录**: 限制 Let's Encrypt 签发证书

| 类型 | 名称 | 内容 |
|---|---|---|
| CAA | `@` | `0 issue "letsencrypt.org"` |
| CAA | `@` | `0 issuewild "letsencrypt.org"` |

### 4.3 SSL 证书

- **Vercel**: 自动签发 Let's Encrypt,支持通配符 `*.yourdomain.com`
- **Railway**: 自动签发 Let's Encrypt
- **Fly.io**: 自动签发 Let's Encrypt (需先配置 DNS)
- **Cloudflare**: 提供边缘证书 (访客 ↔ Cloudflare)

**证书层级**:
```
访客 ←── Cloudflare Universal SSL ──→ Cloudflare
Cloudflare ←── Let's Encrypt ──→ Vercel/Railway/Fly.io
```

### 4.4 子域名规划

| 子域名 | 目标 | 用途 |
|---|---|---|
| `yourdomain.com` | Vercel | 主站 (前端 SPA) |
| `www.yourdomain.com` | Vercel | 301 → `yourdomain.com` |
| `api.yourdomain.com` | Railway/Fly.io | API 服务 |
| `docs.yourdomain.com` | GitBook | 用户文档 |
| `status.yourdomain.com` | UptimeRobot | 状态页 |
| `receipts.yourdomain.com` | Cloudflare R2 | PDF 收据 CDN |

### 4.5 重定向规则

```nginx
# Vercel vercel.json
{
  "redirects": [
    {
      "source": "/www",
      "destination": "https://yourdomain.com",
      "permanent": true
    },
    {
      "source": "/:path*",
      "destination": "/index.html",
      "statusCode": 200
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

---

## 5. CDN 与缓存

### 5.1 Vercel Edge Cache

Vercel 自动为所有静态资源提供边缘缓存,无需额外配置。

#### 缓存层级

```
浏览器缓存 (Cache-Control)
    ↓ miss
Service Worker (可选,PWA)
    ↓ miss
Vercel Edge Cache (全球 100+ PoP)
    ↓ miss
Vercel Build Output (S3 存储)
```

### 5.2 静态资源缓存策略

#### Vite 构建产物 (带 hash)

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        // 文件名带 content hash,可长期缓存
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
  },
})
```

#### HTTP 响应头 (Vercel `headers` 配置)

```json
{
  "headers": [
    {
      "source": "/assets/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    },
    {
      "source": "/(.*).html",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=0, must-revalidate"
        }
      ]
    },
    {
      "source": "/sw.js",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=0, must-revalidate"
        }
      ]
    }
  ]
}
```

### 5.3 API 响应缓存策略

```python
# backend/app/middleware/cache.py
from functools import wraps
from fastapi import Request, Response

CACHE_RULES = {
    # 公开接口: 允许 CDN 缓存 5 分钟,浏览器不缓存
    "/api/v1/videos/:id/summary": {
        "public": True,
        "max_age": 300,
        "s_maxage": 300,
        "stale_while_revalidate": 60,
    },
    # 敏感接口: 不缓存
    "/api/v1/me": {
        "public": False,
        "max_age": 0,
        "no_store": True,
        "no_cache": True,
    },
    "/api/v1/videos/download": {
        "public": False,
        "max_age": 0,
        "no_store": True,
    },
    # 通用接口: 允许浏览器缓存 1 分钟
    "/api/v1/videos": {
        "public": True,
        "max_age": 60,
    },
}

def cache_control(endpoint: str):
    """缓存控制装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)
            rule = CACHE_RULES.get(endpoint)
            if rule:
                if rule.get("no_store"):
                    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                elif rule.get("public"):
                    directives = [f"public", f"max-age={rule['max_age']}"]
                    if "s_maxage" in rule:
                        directives.append(f"s-maxage={rule['s_maxage']}")
                    response.headers["Cache-Control"] = ", ".join(directives)
            return response
        return wrapper
    return decorator
```

### 5.4 AI 总结缓存 (Redis)

```python
# backend/app/services/cache.py
import hashlib
import json
from redis.asyncio import Redis

class SummaryCache:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.ttl = 30 * 24 * 3600  # 30 天

    def _make_key(self, video_url: str, lang: str) -> str:
        """生成缓存键"""
        url_hash = hashlib.sha256(f"{video_url}:{lang}".encode()).hexdigest()[:16]
        return f"summary:{url_hash}"

    async def get(self, video_url: str, lang: str) -> dict | None:
        key = self._make_key(video_url, lang)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(self, video_url: str, lang: str, summary: dict):
        key = self._make_key(video_url, lang)
        await self.redis.setex(key, self.ttl, json.dumps(summary, ensure_ascii=False))

    async def invalidate_user(self, user_id: str):
        """用户删除账号时清理所有缓存"""
        # 使用 Redis SCAN 遍历 (生产环境用)
        async for key in self.redis.scan_iter(f"summary:*"):
            # 如果需要按用户清理,需在缓存 value 中存储 user_id
            await self.redis.delete(key)

    async def warmup(self, db_session):
        """服务启动时预热热门视频总结"""
        from app.models import Video
        popular_videos = await Video.get_popular(limit=50, db=db_session)
        for video in popular_videos:
            if not await self.get(video.url, "zh"):
                # 异步预热,不阻塞启动
                asyncio.create_task(self._generate_and_cache(video))
```

### 5.5 缓存失效策略

| 场景 | 失效方式 | 实现 |
|---|---|---|
| 用户删除账号 | 清理该用户所有 AI 总结缓存 | `invalidate_user()` |
| 视频总结更新 | 按 URL hash 删除 | `redis.delete(f"summary:{hash}")` |
| 模型升级 | 批量清理所有缓存 | `redis.flushdb()` (仅 AI 缓存 DB) |
| 部署新版本 | 静态资源 hash 自动失效 | Vite content hash |
| 紧急清理 | 管理后台触发 | `POST /api/v1/admin/cache/clear` |

---

## 6. 监控与告警

### 6.1 监控体系概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        监控体系                                  │
├─────────────────�───────────────────┬───────────────────────────┤
│   可用性监控     │     错误监控       │       性能监控             │
│                 │                   │                           │
│  UptimeRobot    │  Sentry           │  Vercel Analytics         │
│  (1 分钟间隔)    │  (实时)           │  (Web Vitals)             │
│                 │                   │                           │
│  端点:          │  前端 JS 错误     │  LCP < 2.5s              │
│  - / (前端)     │  - Vue 异常       │  INP < 100ms             │
│  - /health      │  - API 错误响应   │  CLS < 0.1               │
│  - /api/health  │                   │                           │
├─────────────────┴───────────────────┴───────────────────────────�
│                        告警通道                                  │
│  Discord Webhook (主) / 邮件 (辅) / PagerDuty (紧急)            │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 UptimeRobot 配置

| 监控项 | URL | 间隔 | 超时 | 告警阈值 |
|---|---|---|---|---|
| 前端首页 | `https://yourdomain.com` | 1 分钟 | 10s | 连续 2 次失败 |
| 前端 WWW | `https://www.yourdomain.com` | 1 分钟 | 10s | 连续 2 次失败 |
| 后端健康 | `https://api.yourdomain.com/health` | 1 分钟 | 5s | 连续 2 次失败 |
| 后端 DB | `https://api.yourdomain.com/api/v1/health/db` | 5 分钟 | 10s | 连续 2 次失败 |
| 后端 Redis | `https://api.yourdomain.com/api/v1/health/redis` | 5 分钟 | 10s | 连续 2 次失败 |

### 6.3 Sentry 配置

#### 前端 Sentry

```typescript
// frontend/src/main.ts
import * as Sentry from "@sentry/vue";

Sentry.init({
  app,
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.MODE,
  release: `v${import.meta.env.VITE_APP_VERSION}`,
  
  // 性能监控
  tracesSampleRate: 0.1,  // 10% 采样
  
  // 会话重放 (可选,付费功能)
  replaysSessionSampleRate: 0.01,  // 1% 采样
  replaysOnErrorSampleRate: 1.0,   // 错误时 100% 采样
  
  // 敏感信息过滤
  beforeSend(event) {
    // 移除用户邮箱
    if (event.user) {
      delete event.user.email;
    }
    return event;
  },
  
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration(),
  ],
});
```

#### 后端 Sentry

```python
# backend/app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.APP_ENV,
    release=f"v{settings.APP_VERSION}",
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    
    # 敏感信息过滤
    send_default_pii=False,
    before_send=filter_sensitive_data,
    
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration(),
    ],
)

def filter_sensitive_data(event, hint):
    """脱敏处理"""
    # 移除请求体中的密码
    if "request" in event and "data" in event["request"]:
        for key in ["password", "token", "secret", "credit_card"]:
            if key in event["request"]["data"]:
                event["request"]["data"][key] = "[Filtered]"
    return event
```

### 6.4 告警规则

| 告警项 | 条件 | 持续时间 | 告警级别 | 通知渠道 |
|---|---|---|---|---|
| 5xx 错误率 | > 1% | 5 分钟 | P1 紧急 | Discord + 邮件 + PagerDuty |
| 5xx 错误率 | > 0.5% | 10 分钟 | P2 高 | Discord + 邮件 |
| 前端 JS 错误 | > 50 次/小时 | 即时 | P3 中 | Discord |
| API 延迟 P95 | > 2s | 5 分钟 | P2 高 | Discord + 邮件 |
| AI 总结延迟 P95 | > 15s | 10 分钟 | P2 高 | Discord + 邮件 |
| Stripe Webhook 失败 | 3 次 | 即时 | P1 紧急 | Discord + 邮件 |
| DMCA 通知 | > 5 次 | 1 小时 | P2 高 | 邮件 (人工审核) |
| 数据库连接池耗尽 | > 80% | 5 分钟 | P1 紧急 | Discord + 邮件 |
| Redis 连接失败 | 1 次 | 即时 | P2 高 | Discord |
| 磁盘使用率 | > 85% | 10 分钟 | P2 高 | Discord + 邮件 |
| SSL 证书过期 | < 14 天 | 每日检查 | P2 高 | 邮件 |
| 域名续费 | < 30 天 | 每日检查 | P2 高 | 邮件 |

### 6.5 Discord Webhook 告警格式

```python
# backend/app/services/alerting.py
import httpx
from datetime import datetime

async def send_discord_alert(
    title: str,
    description: str,
    level: str = "warning",
    fields: list[dict] | None = None,
):
    color_map = {
        "info": 0x3498DB,      # 蓝色
        "warning": 0xF39C12,   # 黄色
        "error": 0xE74C3C,     # 红色
        "critical": 0x8B0000,  # 深红
    }
    
    embed = {
        "title": f"[{level.upper()}] {title}",
        "description": description,
        "color": color_map.get(level, 0x95A5A6),
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": f"Environment: {settings.APP_ENV}"},
        "fields": fields or [],
    }
    
    payload = {"embeds": [embed]}
    
    async with httpx.AsyncClient() as client:
        await client.post(
            settings.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10,
        )
```

---

## 7. 日志管理

### 7.1 日志格式

使用 **structlog** 输出结构化 JSON 日志:

```python
# backend/app/core/logging.py
import structlog
from pythonjsonlogger import jsonlogger

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        # 生产环境用 JSON 格式
        structlog.processors.JSONRenderer() if settings.APP_ENV == "production"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.INFO if settings.APP_ENV == "production" else logging.DEBUG
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### 7.2 日志输出示例

```json
{
  "timestamp": "2026-06-25T10:30:45.123Z",
  "level": "info",
  "event": "video_summary_generated",
  "user_id": "usr_abc123",
  "video_id": "vid_xyz789",
  "duration_ms": 8500,
  "model": "google/gemini-2.0-flash-001",
  "tokens_used": 3200,
  "request_id": "req_123456",
  "trace_id": "trace_abcdef"
}
```

### 7.3 日志聚合平台

| 平台 | 用途 | 保留期 | 成本 |
|---|---|---|---|
| **Logtail** (推荐) | 结构化日志聚合 + 搜索 | 30 天 | $8/月 (1GB) |
| Railway Logs | 后端实时日志 | 24 小时 | 内置 |
| Fly.io Logs | 后端实时日志 | 7 天 | 内置 |
| Vercel Logs | 前端部署日志 + 函数日志 | 3-7 天 | 内置 |
| Sentry | 错误日志 | 90 天 | $0 (免费档) |

### 7.4 敏感信息脱敏

```python
# backend/app/core/sanitizers.py
import re

SENSITIVE_PATTERNS = [
    # 密码
    (re.compile(r'("password"\s*:\s*)"[^"]*"'), r'\1"[Filtered]"'),
    # Token
    (re.compile(r'("token"\s*:\s*)"[^"]*"'), r'\1"[Filtered]"'),
    # Email
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '[Email]'),
    # 信用卡
    (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CreditCard]'),
    # API Key
    (re.compile(r'("api_key"\s*:\s*)"[^"]*"'), r'\1"[Filtered]"'),
    # JWT
    (re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), '[JWT]'),
]

def sanitize_log_message(message: str) -> str:
    """脱敏日志消息"""
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message
```

### 7.5 审计日志

```python
# backend/app/services/audit.py
from datetime import datetime
from app.core.database import get_db

class AuditLogger:
    """关键事件审计日志"""
    
    @staticmethod
    async def log(
        event_type: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        metadata: dict | None = None,
        ip_address: str | None = None,
    ):
        """
        event_type: user | payment | video | dmca | admin
        action: create | update | delete | login | logout | download
        """
        async for db in get_db():
            await db.execute(
                """
                INSERT INTO audit_logs 
                (event_type, user_id, resource_type, resource_id, action, metadata, ip_address, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                event_type, user_id, resource_type, resource_id,
                action, 
                json.dumps(metadata) if metadata else None,
                ip_address,
                datetime.utcnow(),
            )
            await db.commit()

# 使用示例
await AuditLogger.log(
    event_type="user",
    user_id="usr_abc123",
    resource_type="user",
    resource_id="usr_abc123",
    action="delete",
    metadata={"reason": "user_requested"},
    ip_address="1.2.3.4",
)
```

### 7.6 日志保留策略

| 日志类型 | 保留期 | 存储 | 合规要求 |
|---|---|---|---|
| 应用日志 | 30 天 | Logtail | GDPR |
| 访问日志 | 90 天 | Logtail | 安全审计 |
| 审计日志 | 1 年 | PostgreSQL + S3 | SOC 2 |
| 错误日志 | 90 天 | Sentry | - |
| 部署日志 | 30 天 | GitHub Actions | - |

---

## 8. 备份与恢复

### 8.1 备份策略

```
┌─────────────────────────────────────────────────────────────────┐
│                        备份策略                                  │
├──────────────────┬──────────────────────────────────────────────�
│   PostgreSQL     │  Railway/Fly.io 内置自动备份 (每日)           │
│                  │  + 手动快照 (部署前)                          │
│                  │  + pg_dump 导出到 R2 (每周)                   │
├──────────────────┼──────────────────────────────────────────────┤
│   SQLite (MVP)   │  每日 pg_dump → S3/R2                        │
│                  │  + 实时 WAL 流复制                            │
├──────────────────┼──────────────────────────────────────────────┤
│   Redis          │  RDB 快照 (每小时)                            │
│                  │  AOF 持久化 (always)                          │
├──────────────────�──────────────────────────────────────────────┤
│   配置文件        │  Git 仓库 (基础设施即代码)                     │
│                  │  + 环境变量导出 (每月)                        │
├──────────────────┼──────────────────────────────────────────────�
│   用户上传        │  Cloudflare R2 版本控制 + 跨区域复制           │
└──────────────────┴──────────────────────────────────────────────┘
```

### 8.2 PostgreSQL 自动备份

#### Railway 内置备份

```toml
# railway.toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "./Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

Railway 自动:
- 每日全量备份 (保留 7 天)
- 时间点恢复 (PITR,最近 24 小时)
- 手动触发备份 (Dashboard 或 CLI)

#### Fly.io 手动备份

```bash
# 创建备份
flyctl pg dump --config fly.production.toml > backup_$(date +%Y%m%d_%H%M%S).sql

# 上传到 R2
aws s3 cp backup_*.sql s3://video-summary-backups/ \
  --endpoint-url https://xxxxx.r2.cloudflarestorage.com \
  --profile r2

# 恢复
flyctl pg connect --config fly.production.toml < backup_20260625_120000.sql
```

### 8.3 SQLite 备份 (MVP 阶段)

```bash
#!/bin/bash
# scripts/backup_sqlite.sh

set -euo pipefail

DB_PATH="./data/db.sqlite3"
BACKUP_DIR="./backups"
R2_BUCKET="s3://video-summary-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="sqlite_backup_${DATE}.sql.gz.enc"

mkdir -p "$BACKUP_DIR"

# 导出 + 压缩 + 加密
sqlite3 "$DB_PATH" .dump | gzip | \
  openssl enc -aes-256-cbc -salt -pass pass:"${BACKUP_ENCRYPTION_KEY}" \
  > "$BACKUP_DIR/$BACKUP_FILE"

# 上传到 R2
aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" "$R2_BUCKET/sqlite/" \
  --endpoint-url "${R2_ENDPOINT}" \
  --profile r2

# 清理本地 7 天前的备份
find "$BACKUP_DIR" -name "*.enc" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

### 8.4 备份加密

```python
# backend/app/services/backup.py
from cryptography.fernet import Fernet
import gzip

class BackupEncryption:
    def __init__(self, encryption_key: str):
        self.fernet = Fernet(encryption_key.encode())
    
    def encrypt_dump(self, dump_data: bytes) -> bytes:
        """加密数据库导出"""
        compressed = gzip.compress(dump_data, compresslevel=9)
        encrypted = self.fernet.encrypt(compressed)
        return encrypted
    
    def decrypt_dump(self, encrypted_data: bytes) -> bytes:
        """解密数据库导出"""
        compressed = self.fernet.decrypt(encrypted_data)
        dump_data = gzip.decompress(compressed)
        return dump_data
```

### 8.5 恢复演练

| 频率 | 演练内容 | 验证项 | 负责人 |
|---|---|---|---|
| 每月 | 从 Railway/Fly.io 内置备份恢复 | 数据完整性,服务启动 | DevOps |
| 每季度 | 从 R2 加密备份恢复 | 解密成功,数据完整,服务正常 | DevOps |
| 每半年 | 全量灾难恢复 (新环境) | 从 0 部署,恢复数据,验证功能 | 全团队 |

#### 恢复演练检查清单

```markdown
- [ ] 下载最新备份文件
- [ ] 解密备份文件 (如加密)
- [ ] 创建新的 PostgreSQL 实例
- [ ] 导入备份数据
- [ ] 验证数据完整性 (行数/校验和)
- [ ] 启动后端服务
- [ ] 运行健康检查
- [ ] 验证核心功能 (登录/支付/AI 总结)
- [ ] 记录恢复时间 (RTO)
- [ ] 记录数据丢失量 (RPO)
- [ ] 清理演练环境
```

### 8.6 备份监控

```yaml
# .github/workflows/backup-check.yml
name: Backup Health Check

on:
  schedule:
    - cron: '0 8 * * *'  # 每天 UTC 8:00

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: Check latest backup age
        run: |
          LATEST_BACKUP=$(aws s3 ls s3://video-summary-backups/ --recursive \
            | sort | tail -1 | awk '{print $1" "$2}')
          BACKUP_TIME=$(date -d "$LATEST_BACKUP" +%s)
          NOW=$(date +%s)
          AGE_HOURS=$(( (NOW - BACKUP_TIME) / 3600 ))
          
          if [ $AGE_HOURS -gt 26 ]; then
            echo "::error::Latest backup is ${AGE_HOURS} hours old!"
            exit 1
          fi
          
      - name: Notify on failure
        if: failure()
        run: |
          curl -X POST "${{ secrets.DISCORD_WEBHOOK_URL }}" \
            -H "Content-Type: application/json" \
            -d '{"embeds":[{"title":"[CRITICAL] Backup Check Failed","color":16711680}]}'
```

---

## 9. 扩缩容

### 9.1 自动扩缩容策略

#### Railway

```toml
# railway.toml
[deploy]
# 自动扩缩容配置
minReplicas = 1
maxReplicas = 10
# 基于 CPU > 70% 或内存 > 80% 扩容
```

#### Fly.io

```toml
# fly.production.toml
app = "video-summary-backend"
primary_region = "iad"  # 美国东部

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false   # 生产环境不自动停止
  auto_start_machines = true
  min_machines_running = 1     # 最小实例数 (避免冷启动)
  max_machines_running = 10

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512

# 多地域部署
[regions]
  iad = 1   # 美国东部
  sfo = 1   # 美国西部
  nrt = 1   # 日本 (亚洲用户)
```

### 9.2 数据库连接池配置

```python
# backend/app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,              # 最小连接数
    max_overflow=15,          # 最大溢出连接 (总计 20)
    pool_timeout=30,          # 获取连接超时 (秒)
    pool_recycle=1800,        # 连接回收时间 (30 分钟)
    pool_pre_ping=True,       # 连接前检测,避免断连
    echo=settings.APP_DEBUG,  # 调试模式打印 SQL
)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
```

### 9.3 缓存预热

```python
# backend/app/core/startup.py
from app.services.cache import SummaryCache

async def on_startup():
    """服务启动时预热缓存"""
    logger.info("Starting cache warmup...")
    
    async for db in get_db():
        # 预热热门视频总结
        cache = SummaryCache(redis)
        await cache.warmup(db)
        
        # 预热配置
        await redis.set("config:models", json.dumps(SUPPORTED_MODELS), ex=3600)
        
    logger.info("Cache warmup completed")
```

### 9.4 冷启动优化

| 优化项 | 方案 | 效果 |
|---|---|---|
| 最小实例数 | `min_machines_running = 1` | 避免冷启动延迟 |
| 懒加载 | 非关键服务延迟初始化 | 启动时间 < 3s |
| 连接池预热 | 启动时创建最小连接数 | 首次请求不等待 |
| 健康检查 | `/health` 快速响应 | 快速接入负载均衡 |
| 镜像优化 | 多阶段构建,Docker 镜像 < 200MB | 快速拉取 |

### 9.5 容量规划

| 阶段 | 用户数 | 后端实例 | 数据库 | Redis | 月成本估算 |
|---|---|---|---|---|---|
| MVP | < 1000 | 1 × 512MB | 共享 PostgreSQL 0.5GB | 无 | ~$15 |
| 增长 | 1000-10000 | 2 × 1GB | 共享 PostgreSQL 2GB | Upstash 免费 | ~$50 |
| 规模 | 10000-100000 | 4 × 2GB | 专用 PostgreSQL 8GB | Upstash 1GB | ~$200 |
| 企业 | 100000+ | 8 × 4GB | 专用 PostgreSQL 32GB | Upstash 10GB | ~$800 |

---

## 10. 验证清单

### 10.1 部署前检查

```markdown
# 部署前 Checklist

## 代码质量
- [ ] 所有测试通过 (pytest + vitest + playwright)
- [ ] 代码覆盖率 ≥ 80%
- [ ] ESLint / Ruff / Mypy 无错误
- [ ] 无 CRITICAL/HIGH 安全漏洞
- [ ] 依赖审计通过 (pip-audit)

## 构建
- [ ] 前端构建成功,产物 < 500KB gzip
- [ ] 后端 Docker 镜像构建成功
- [ ] Docker 镜像大小 < 200MB

## 数据库
- [ ] Alembic 迁移通过
- [ ] 迁移前备份已创建
- [ ] 回滚脚本已准备

## 环境变量
- [ ] 所有必需变量已设置
- [ ] 敏感变量已加密存储
- [ ] .env.example 已更新

## 监控
- [ ] Sentry DSN 已配置
- [ ] UptimeRobot 监控已添加
- [ ] Discord Webhook 已测试
- [ ] 告警规则已配置

## DNS
- [ ] 域名已解析
- [ ] SSL 证书有效
- [ ] 子域名已配置
- [ ] CAA 记录已设置

## 备份
- [ ] 自动备份已启用
- [ ] 备份恢复演练已完成
- [ ] 备份加密密钥已保存
```

### 10.2 部署后验证

```markdown
# 部署后 Smoke Test

## 前端
- [ ] https://yourdomain.com 返回 200
- [ ] 首页加载时间 LCP < 2.5s
- [ ] 静态资源缓存头正确
- [ ] SPA 路由刷新正常 (无 404)
- [ ] 暗色/亮色主题切换正常

## 后端
- [ ] https://api.yourdomain.com/health 返回 200
- [ ] /api/v1/health/db 返回 200
- [ ] /api/v1/health/redis 返回 200
- [ ] CORS 头正确
- [ ] 速率限制生效

## 核心功能
- [ ] 用户注册/登录 (Supabase Auth)
- [ ] 视频 URL 提交
- [ ] AI 总结生成
- [ ] Stripe 支付流程
- [ ] 邮件发送 (Brevo)
- [ ] PDF 收据下载 (R2)

## 监控
- [ ] Sentry 收到测试事件
- [ ] UptimeRobot 显示 UP
- [ ] Vercel Analytics 有数据
- [ ] 日志聚合平台有日志
```

### 10.3 运维日常检查

```markdown
# 每日运维检查

- [ ] 检查 UptimeRobot 状态 (全部 UP)
- [ ] 检查 Sentry 错误数 (无突增)
- [ ] 检查 Vercel Analytics Web Vitals (LCP/INP/CLS 达标)
- [ ] 检查数据库连接池使用率 (< 80%)
- [ ] 检查 Redis 内存使用率 (< 80%)
- [ ] 检查磁盘使用率 (< 70%)
- [ ] 检查备份状态 (最新备份 < 26 小时)

# 每周运维检查

- [ ] 审查慢查询日志 (> 1s)
- [ ] 审查 API 延迟 P95/P99
- [ ] 检查 SSL 证书有效期 (> 14 天)
- [ ] 检查域名续费状态 (> 30 天)
- [ ] 更新依赖 (安全补丁)
- [ ] 审查访问日志 (异常模式)

# 每月运维检查

- [ ] 轮换敏感 Secret (如到期)
- [ ] 恢复演练 (从备份恢复)
- [ ] 容量评估 (是否需要扩缩容)
- [ ] 成本分析 (优化机会)
- [ ] 安全扫描 (Trivy + pip-audit)
- [ ] 更新本文档
```

### 10.4 故障处理流程

```markdown
# 故障处理 SOP

## 1. 发现故障
- 监控告警触发 → 值班人员确认
- 用户反馈 → 客服转值班人员

## 2. 评估严重性
- P1 (紧急): 服务完全不可用 / 数据泄露
- P2 (高): 核心功能不可用 / 性能严重下降
- P3 (中): 非核心功能异常
- P4 (低): 轻微问题 / UI 异常

## 3. 应急响应
- P1: 立即响应,全员 on-call
- P2: 15 分钟内响应
- P3: 2 小时内响应
- P4: 24 小时内响应

## 4. 故障处理
1. 止损 (回滚/降级/限流)
2. 定位 (日志/监控/追踪)
3. 修复 (热修复/配置变更)
4. 验证 (smoke test)

## 5. 事后复盘
- 时间线梳理
- 根因分析
- 改进措施
- 文档归档
```

---

## 附录

### A. 技术栈版本锁定

| 组件 | 版本 | 锁定原因 |
|---|---|---|
| Node.js | 20 LTS | Vite 7 要求 |
| Python | 3.12 | FastAPI 最新支持 |
| PostgreSQL | 16 | Railway/Fly.io 默认 |
| Redis | 7 | Upstash 默认 |
| Vue | 3.5 | 最新稳定版 |
| Vite | 7 | 最新稳定版 |
| FastAPI | 0.115 | 最新稳定版 |
| SQLAlchemy | 2.0 | 异步支持 |
| Alembic | 1.13 | SQLAlchemy 配套 |

### B. 第三方服务账号清单

| 服务 | 账号类型 | 权限级别 | 负责人 |
|---|---|---|---|
| Cloudflare | 域名 + CDN + R2 | Owner | DevOps |
| Vercel | 前端托管 | Owner | DevOps |
| Railway / Fly.io | 后端部署 | Owner | DevOps |
| Supabase | 数据库 + Auth | Owner | 后端开发 |
| Stripe | 支付 | Admin | 产品经理 |
| OpenRouter | AI API | Member | 后端开发 |
| Brevo | 邮件 | Admin | 后端开发 |
| GitHub | 代码仓库 | Owner | DevOps |
| Sentry | 错误监控 | Member | DevOps |
| UptimeRobot | 可用性监控 | Free | DevOps |

### C. 成本估算 (月度)

| 服务 | MVP 阶段 | 增长阶段 | 规模阶段 |
|---|---|---|---|
| Vercel Pro | $20 | $20 | $20 |
| Railway / Fly.io | $5-15 | $50-100 | $200-500 |
| Supabase Pro | $0 | $25 | $100 |
| Upstash | $0 | $0 | $10 |
| Cloudflare R2 | $0 | $1 | $5 |
| Sentry | $0 | $0 | $29 |
| OpenRouter | $10-30 | $50-100 | $200-500 |
| Brevo | $0 | $25 | $100 |
| 域名 | $10/年 | $10/年 | $10/年 |
| **总计** | **~$40-70/月** | **~$200-300/月** | **~$700-1200/月** |

### D. 联系方式

| 角色 | 联系方式 | 响应时间 |
|---|---|---|
| DevOps 值班 | Discord #on-call | P1: 5 分钟, P2: 15 分钟 |
| 安全事件 | security@yourdomain.com | 1 小时内 |
| 滥用举报 | abuse@yourdomain.com | 24 小时内 |
| DMCA | dmca@yourdomain.com | 24 小时内 |

---

> 本文档由 AI 辅助生成,需根据实际项目情况调整。
> 最后更新: 2026-06-25
