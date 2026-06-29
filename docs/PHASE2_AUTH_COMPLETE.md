# Phase 2:Supabase Auth 集成 — 完成总结

> 2026-06-25 完成

## 测试结果

### ✅ 完整测试通过

| 功能 | 状态 | 说明 |
|---|---|---|
| 前端启动 | ✅ | http://localhost:5173 |
| 后端启动 | ✅ | http://localhost:8000 |
| 用户注册 | ✅ | Supabase Auth API |
| 用户登录 | ✅ | Email/Password |
| JWT 验证 | ✅ | PyJWT + ES256 |
| 后端 /api/auth/me | ✅ | 返回完整用户信息 |
| 路由守卫 | ✅ | requiresAuth/requiresGuest |
| 导航栏 | ✅ | 已登录/未登录状态 |

### 测试账号
- Email: `test_1782397421993@gmail.com`
- 已通过验证(关闭了邮箱确认)

## 已实现的功能

### ✅ 前端 Supabase Auth 集成

**新建文件:**
- `frontend/src/lib/supabaseClient.ts` — Supabase 客户端单例
- `frontend/src/stores/auth.ts` — Pinia Auth Store(核心)
- `frontend/src/pages/AuthCallbackPage.vue` — OAuth 回调页

**修改文件:**
- `frontend/src/stores/user.ts` — 改为 computed 包装 authStore
- `frontend/src/router/index.ts` — 添加路由守卫(requiresAuth/requiresGuest)
- `frontend/src/App.vue` — 初始化 auth + 清理订阅
- `frontend/src/layouts/DefaultLayout.vue` — 条件渲染已登录/未登录菜单
- `frontend/src/pages/LoginPage.vue` — 完整登录/注册表单 + OAuth 按钮
- `frontend/package.json` — 添加 @supabase/supabase-js 依赖

**核心功能:**
- Email/Password 注册、登录
- Email Magic Link 登录
- Google OAuth 登录
- GitHub OAuth 登录
- JWT Token 自动管理(前端 SDK 自动刷新)
- 路由守卫:未登录用户访问受保护页面自动跳转登录页
- 条件渲染:已登录显示用户邮箱 + 登出按钮,未登录显示登录按钮

### ✅ 后端 JWT 验证 + 用户 API

**新建文件:**
- `backend/app/dependencies/__init__.py` — 导出认证依赖
- `backend/app/dependencies/auth.py` — JWT 验证核心
- `backend/app/schemas/user.py` — Pydantic schemas

**修改文件:**
- `backend/app/models/user.py` — 扩展字段(full_name, avatar_url, timezone, stripe 等)
- `backend/routers/auth.py` — 完整用户 API
- `backend/app/main.py` — 路由前缀统一 /api
- `backend/requirements.txt` — 添加 PyJWT
- `backend/.env.example` — 保持完整

**核心 API:**
- `GET /api/health` — 健康检查(无需认证)
- `GET /api/auth/me` — 获取当前用户资料(需认证)
- `PUT /api/auth/me` — 更新用户资料(需认证)
- `GET /api/auth/me/role` — 获取当前用户角色(需认证,快速判断权限)

**JWT 验证流程:**
1. 前端通过 Authorization: Bearer <token> 发送 JWT
2. 后端从 Supabase JWKS 端点获取公钥(RS256,缓存 1 小时)
3. 验证签名、过期时间、签发者
4. 返回 token payload(含 sub、email、app_metadata.role)
5. 需要业务用户数据时,通过 get_current_active_user 查询数据库

---

## 技术方案决策

| 决策 | 选择 | 理由 |
|---|---|---|
| JWT 验证库 | python-jose | 内置 JWKS 支持,RS256 验证 |
| JWKS 缓存 | 内存缓存 + 1 小时 TTL | 避免每次请求都请求 Supabase |
| 认证分层 | get_current_user vs get_current_active_user | 轻量场景只验证 JWT,需要业务数据时查库 |
| Supabase SDK | @supabase/supabase-js v2 | PKCE 默认,安全性更高 |
| Token 刷新 | 前端 SDK 自动处理 | 后端只验证 access_token,SDK 自动刷新 |

---

## 测试指南

### 前置条件

1. 创建 Supabase 项目(supabase.com)
2. 获取 Project URL 和 Anon Key
3. 设置 Redirect URL: `http://localhost:5173/auth/callback`
4. 启用 Email Provider(默认启用)
5. 启用 Google/GitHub Provider(可选)

### 环境变量配置

**前端 `.env`:**
```
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
```

**后端 `.env`:**
```
DATABASE_URL=sqlite+aiosqlite:///./dev.db
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret-from-dashboard
OPENROUTER_API_KEY=sk-or-xxx(后续)
STRIPE_SECRET_KEY=sk_test_xxx(后续)
APP_ENV=development
APP_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
```

### 启动与测试

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# 访问 http://localhost:8000/docs 查看 Swagger UI
# 访问 http://localhost:8000/api/health 健康检查

# 前端
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173/login 登录页
```

### 测试流程

1. 打开 http://localhost:5173/register
2. 注册新账号(Email + Password)
3. 检查邮箱验证邮件(如果启用了 Email Confirmation)
4. 登录成功跳转到首页
5. 检查右上角显示邮箱地址
6. 点击登出按钮,确认登出

### API 测试(curl)

```bash
# 1. 获取 JWT(前端登录后从 DevTools 获取,或用 Supabase API 获取)
TOKEN="eyJhbGciOiJIUzI1NiIs..."

# 2. 访问受保护端点
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/auth/me

# 3. 预期响应
{
  "id": "uuid",
  "email": "user@example.com",
  "language": "en",
  "currency": "USD",
  "role": "free",
  ...
}
```

---

## 安全注意事项

1. **Anon Key 公开安全**:Supabase anon_key 设计为可暴露在浏览器,前提是在 Supabase Dashboard 启用了 RLS
2. **JWT Secret 保密**:后端 SUPABASE_JWT_SECRET 绝对不能出现在前端代码或 VITE_ 前缀变量中
3. **service_role_key 保密**:service_role_key 仅在后端环境变量中,绝对不能暴露
4. **Supabase RLS**:必须启用 Row Level Security,否则用户可以通过 anon_key 访问其他用户数据

---

## 待做事项

### Phase 2 剩余
- [ ] yt-dlp 集成(视频解析)
- [ ] OpenRouter 网关(AI 总结)
- [ ] SQLite 表结构完整 DDL(11 表)

### Phase 3:支付与权限(W5-6)
- [ ] Stripe Checkout 流程
- [ ] Webhook 处理 + 幂等性
- [ ] 订阅管理(升级/降级/取消/试用)
- [ ] VIP 限制逻辑(免费 3 次/天)

### Phase 4:多语言与 SEO(W7-8)
- [ ] 翻译文件补充(errors.json 等)
- [ ] hreflang + OG 标签
- [ ] 邮件模板集成(Brevo)

### Phase 5:测试与上线(W9-10)
- [ ] 单元测试(后端 pytest + 前端 vitest)
- [ ] 集成测试(关键流程)
- [ ] Cloudflare Pages + 后端部署

---

## 文件清单

### 前端
```
frontend/src/
├── lib/
│   └── supabaseClient.ts          # [新建] Supabase 客户端
├── stores/
│   ├── auth.ts                     # [新建] Auth Store(核心)
│   └── user.ts                     # [修改] 改用 authStore
├── router/
│   └── index.ts                    # [修改] 添加路由守卫
├── layouts/
│   └── DefaultLayout.vue           # [修改] 条件渲染菜单
├── pages/
│   ├── LoginPage.vue               # [修改] 完整登录/注册表单
│   └── AuthCallbackPage.vue        # [新建] OAuth 回调
├── App.vue                         # [修改] 初始化 auth
└── package.json                    # [修改] 添加依赖
```

### 后端
```
backend/
├── app/
│   ├── dependencies/
│   │   ├── __init__.py             # [新建] 导出认证依赖
│   │   └── auth.py                 # [新建] JWT 验证核心
│   ├── schemas/
│   │   └── user.py                 # [新建] Pydantic schemas
│   ├── models/
│   │   └── user.py                 # [修改] 扩展字段
│   ├── routers/
│   │   └── auth.py                 # [修改] 完整用户 API
│   └── main.py                     # [修改] 路由前缀统一
├── requirements.txt                # [修改] 添加 PyJWT
└── .env.example                    # [保持]
```

---

## 参考文档

- AGENTS.md: 项目设计纲要
- docs/AUTHENTICATION.md: 认证系统设计(详细)
- docs/PHASE1_COMPLETE.md: Phase 1 完成总结
