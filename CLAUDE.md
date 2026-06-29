# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI 万能视频下载总结器 — Input a video URL, auto-parse 1800+ platforms, AI video summary + mindmap + Q&A + Stripe VIP subscription. V1: English + Simplified Chinese + Japanese.

## Architecture

```
frontend/   → Vue 3 + Vite 7 + Tailwind CSS 4 + vue-i18n + Pinia (SPA)
backend/    → FastAPI (Python 3.12+ async) + yt-dlp + OpenRouter + Stripe
docs/       → 10 design documents (FRONTEND.md, BACKEND.md, DATABASE.md, etc.)
AGENTS.md   → Project design outline and documentation index
```

- **Frontend**: `/api/*` requests proxy to `http://localhost:8000` (Vite dev proxy)
- **Backend**: All API routes under `/api/` prefix (e.g., `/api/health`, `/api/auth/me`, `/api/videos/parse`, `/api/ai/summary`)
- **Auth**: Supabase Auth (RS256 JWT), verified by PyJWT + JWKS from Supabase `.well-known/jwks.json`
- **AI**: OpenRouter unified gateway, model `openrouter/owl-alpha`, SSE streaming
- **Video**: yt-dlp for parsing/downloading, blacklist for DMCA-protected sites
- **Database**: SQLite (dev) → PostgreSQL (prod), 11 tables via Alembic migrations
- **i18n**: vue-i18n + 3 locales (`en`, `zh-CN`, `ja`), language switch = 7-step checklist

## Key Commands

### Frontend (in `frontend/`)
```bash
npm install          # Install dependencies
npm run dev          # Dev server at http://localhost:5173
npm run build        # TypeScript check + Vite build
npm run type-check   # TypeScript type check only
```

### Backend (in `backend/`)
```bash
pip install -r requirements.txt   # Install Python dependencies
cp .env.example .env              # Copy env template (fill real values)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000   # Dev server
# OR
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run a single test
python -c "from app.services.video_service import extract_video_info_async; print('OK')"
```

### Health Checks
```bash
curl http://localhost:8000/api/health              # Backend health
curl http://localhost:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); [print(p) for p in sorted(d['paths'].keys())]"  # List all routes
```

## Environment Variables

**Backend `.env`** (in `backend/`):
- `DATABASE_URL` — SQLite for dev (`sqlite+aiosqlite:///./dev.db`), PostgreSQL for prod
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_ANON_KEY` — Supabase anonymous key (public, for JWKS fetching)
- `SUPABASE_JWT_SECRET` — Not needed (JWKS used instead)
- `OPENROUTER_API_KEY` — OpenRouter API key (model: `openrouter/owl-alpha`)
- `STRIPE_SECRET_KEY` — Stripe secret key
- `STRIPE_WEBHOOK_SECRET` — Stripe webhook signing secret
- `APP_ENV` — `development` or `production`
- `FRONTEND_URL` — `http://localhost:5173`

**Frontend `.env`** (in `frontend/`):
- `VITE_API_URL` — Backend API URL (`http://localhost:8000`)
- `VITE_SUPABASE_URL` — Supabase project URL
- `VITE_SUPABASE_ANON_KEY` — Supabase anonymous key

## Key Patterns

### SSE Streaming (AI Summary)
- Backend: `StreamingResponse` with `text/event-stream`, OpenAI-compatible chunks (`data.choices[0].delta.content`)
- Frontend: `fetch()` + `ReadableStream` reader, parse each `data:` line
- Heartbeat: `: ping` comment every 30s to keep connection alive
- Error handling: `data.error` field signals failure

### JWT Authentication
- Frontend: `@supabase/supabase-js` manages session (auto-refresh, `onAuthStateChange`)
- Backend: `python-jose` / `PyJWT` verifies RS256/ES256 JWT via JWKS
- Routes: `@router.get("/me")` with `Depends(get_current_user)`
- Error: 401 if token invalid/expired

### i18n
- Frontend: `vue-i18n` with `legacy: false`, locale files at `src/locales/{lang}/common.json`
- Backend: `LocalizedHTTPException` base class, `get_locale()` dependency from JWT
- Language switch: update `<html lang>`, locale messages, backend sync, page refresh, API re-request, title/OG update, cache reset

### Route Structure
- All routes defined in `router/index.ts` with `meta.requiresAuth` / `meta.requiresGuest`
- Layout component `DefaultLayout.vue` uses `<router-view />` (NOT `<slot />`)
- `App.vue` is minimal, only `<router-view />` (no layout wrapping)

## Common Pitfalls

- **`<slot />` vs `<router-view />`**: Layout components in Vue Router use `<router-view />`, not `<slot />`. If you see blank content areas, check the layout template.
- **`btn-primary` class**: Defined in `src/styles/main.css` as a utility class, NOT Tailwind-generated. Ensure it's imported.
- **Supabase JWKS URL**: Correct URL is `/auth/v1/.well-known/jwks.json`, NOT `/auth/v1/keys`. The `apikey` header must be sent for JWKS requests.
- **PyJWT ES256**: Supabase uses ES256 algorithm (not RS256). Use `algorithms=["ES256", "RS256"]` in JWT decode.
- **OpenRouter SSE format**: Returns OpenAI-compatible chunks (`data.choices[0].delta.content`), NOT plain `{content: "..."}`. Frontend must parse the nested structure.
- **Node.js v24 + `$` in passwords**: Node.js 24 has Type Stripping that may eat `Test` after `$` in passwords. Use `String.fromCharCode(84) + 'est123456'` to build passwords in JS test scripts.
- **uvicorn reload**: On Windows, `--reload` can be unreliable. If routes don't appear in openapi.json, stop all Python processes and restart without `--reload` or with `--reload-dir app`.
- **UVICORN port conflicts**: Windows sometimes holds port 8000 after uvicorn stops. Use `netstat -ano | findstr :8000` to find the PID, then `Stop-Process -Id <PID> -Force`.

## Documentation

| File | Content |
|---|---|
| `AGENTS.md` | Project design outline, deployment, timeline, decisions |
| `docs/FRONTEND.md` | Vue 3 architecture, vue-i18n, Tailwind 4, SSE |
| `docs/BACKEND.md` | FastAPI layout, routing, dependency injection, SSE |
| `docs/DATABASE.md` | 11-table schema, SQLite→PostgreSQL migration, Alembic |
| `docs/AUTHENTICATION.md` | Supabase Auth, JWT, RBAC, user preferences |
| `docs/AI.md` | OpenRouter gateway, language routing, prompt templates |
| `docs/PAYMENT.md` | Stripe Checkout, webhook, subscription, PDF receipt |
| `docs/I18N.md` | Multi-language architecture, translation workflow |
| `docs/SECURITY.md` | DMCA, GDPR, rate limiting, webhook security |
| `docs/DEPLOYMENT.md` | Cloudflare Pages + Workers + D1, CI/CD |
| `docs/TESTING.md` | Unit/integration/E2E testing strategy |
| `docs/PHASE1_COMPLETE.md` | Phase 1 deliverables |
| `docs/PHASE2_COMPLETE.md` | Phase 2 deliverables |
| `docs/DEV_SERVER_GUIDE.md` | Dev server startup guide |

## Tech Stack Summary

| Layer | Stack |
|---|---|
| Frontend | Vue 3, Vite 7, Tailwind CSS 4 (`@theme`), vue-i18n 10, Pinia, @unhead/vue |
| Backend | FastAPI, uvicorn, SQLAlchemy async, aiosqlite/asyncpg, yt-dlp, httpx |
| Auth | Supabase Auth (cloud), PyJWT (backend verification), ES256/RS256 |
| AI | OpenRouter (`openrouter/owl-alpha`), SSE streaming, fallback chain |
| Database | SQLite (dev) → PostgreSQL (prod), Alembic migrations |
| Payments | Stripe Checkout + Webhook, PDF receipt (reportlab) |
| i18n | vue-i18n, 3 locales (en/zh-CN/ja), LocalizedHTTPException |
| Deploy | Cloudflare Pages (frontend), Render/Fly.io (backend) |

## Tool Usage Rules

- **Chrome DevTools**: 使用 `chrome-devtools` 系列工具时，**禁止使用 `take_screenshot`**。查看网页内容请使用 `take_snapshot`（无障碍树快照）或 `evaluate_script` / `list_console_messages` / `list_network_requests` 等其他工具。
- **路由位置**: 后端路由**只放在 `backend/app/routers/`**，旧的 `backend/routers/` 目录已删除。新增路由请放到 `app/routers/<name>.py`，并在 `main.py` 用 `from app.routers import <name>` 注册。不要创建 `routers/` 目录。
- **端到端测试**:用长视频 `https://www.youtube.com/watch?v=nWAunQIZ9ZQ`(用户指定)，不用短视频(Rick Astley dQw4w9WgXcQ 仅开发联调)。

## Page Architecture

- **工作台模式**:前端是**单页两栏工作台**，不是多页面跳转。`/download` 路由 = 工作台入口(顶部输入 + 左栏视频信息 + 右栏 4 个 Tab:总结/字幕/导图/问答)。
- **不再跳转 SummaryPage**:原 `/summary/:id` 路由保留(分享链接用)，但默认从工作台内 Tabs 访问 AI 功能。
- **组件位置**:工作台组件在 `frontend/src/components/`(TabPanel、VideoInfoPanel)和 `frontend/src/components/Tabs/`(SummaryTab、SubtitleTab、MindmapTab、QaTab)。

## CLAUDE.md Maintenance

- This file is auto-generated by `/init` command.
- Update when adding new features, changing tech stack, or discovering new pitfalls.
- Keep it concise — avoid listing every file (use `docs/` for detailed documentation).
- Prefer commands and patterns over prose.
