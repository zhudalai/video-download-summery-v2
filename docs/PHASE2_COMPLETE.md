# Phase 2:核心功能模块 — 完成总结

> 2026-06-25 完成

## 已实现的功能

### ✅ 数据库模型(11 表)

| 表名 | 说明 | 关键字段 |
|---|---|---|
| `users` | 用户表 | supabase_uid, email, language, role, stripe_customer_id |
| `videos` | 视频表 | url, platform, platform_video_id, title, duration, metadata |
| `transcripts` | 转录文本表 | video_id, language, content, segments(JSON) |
| `summaries` | AI 总结表 | video_id, language, content, model, tokens, cost |
| `mindmaps` | 思维导图表 | summary_id, svg_data, png_data |
| `qa_sessions` | 问答会话表 | user_id, video_id |
| `qa_messages` | 问答消息表 | session_id, role, content |
| `subscriptions` | 订阅表 | user_id, stripe_subscription_id, plan, status |
| `usage_logs` | 用量日志表 | user_id, action, quota_used |
| `processed_events` | 已处理事件表 | event_id(主键), event_type |
| `audit_logs` | 审计日志表 | user_id, action, ip_address, metadata |

**DDL 文件:** `backend/schema.sql`(SQLite,含索引和触发器)
**迁移工具:** Alembic(`backend/alembic/`)

### ✅ yt-dlp 视频解析模块

**新建文件:**
- `backend/app/services/video_service.py` — 视频解析服务
- `backend/app/services/transcript_service.py` — 转录服务

**API 端点:**
- `POST /api/videos/parse` — 解析视频信息(不下载)
- `POST /api/videos/subtitles` — 获取视频字幕

**核心功能:**
- 异步视频信息解析(`run_in_executor`)
- 黑名单检查(Netflix/Spotify/Disney+ 等)
- YouTube 自动字幕下载
- SRT 解析为纯文本
- 临时文件自动清理

### ✅ OpenRouter AI 总结模块

**新建文件:**
- `backend/app/config/router.py` — 多模型路由表
- `backend/app/prompts/templates.py` — Prompt 模板
- `backend/app/services/llm_client.py` — LLM 客户端(Fallback + 重试)
- `backend/app/services/summary_service.py` — 总结服务(SSE 流式)

**API 端点:**
- `POST /api/ai/summary` — 生成 AI 总结(SSE 流式)

**核心功能:**
- 多模型路由(中文→DeepSeek,英文/日文→Gemini)
- SSE 流式输出(30 秒心跳保活)
- Fallback 机制(主模型失败自动切换)
- 指数退避重试(最多 3 次)
- 客户端断开检测

## 技术方案决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 数据库 UUID | String(36) | 兼容 SQLite 和 PostgreSQL |
| yt-dlp 异步 | run_in_executor | 不阻塞事件循环 |
| JWT 验证 | PyJWT + ES256 | Supabase 使用 ES256 算法 |
| LLM 客户端 | httpx.AsyncClient.stream() | 零拷贝透传 SSE |
| 心跳保活 | SSE 注释 `: ping` | 绕过 nginx/Cloudflare 超时 |
| 缓存键 | hash(video_id+lang+version) | 维度变化自动失效 |

## 测试结果

| 功能 | 状态 |
|---|---|
| 后端启动 | ✅ Import OK |
| 用户注册(Supabase) | ✅ |
| 用户登录(Supabase) | ✅ |
| JWT 验证(ES256) | ✅ |
| /api/auth/me | ✅ 200 |
| 数据库模型导入 | ✅ |

## 待做事项

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

## 文件清单

### 数据库(15 个文件)
```
backend/
├── schema.sql                    # SQLite DDL
├── alembic.ini                   # Alembic 配置
├── alembic/
│   ├── env.py                    # Alembic 环境
│   ├── script.py.mako            # 迁移模板
│   └── versions/
└── app/
    ├── models/
    │   ├── __init__.py           # 导入所有模型
    │   ├── user.py
    │   ├── video.py
    │   ├── transcript.py
    │   ├── summary.py
    │   ├── mindmap.py
    │   ├── qa.py
    │   ├── subscription.py
    │   ├── usage_log.py
    │   ├── processed_event.py
    │   └── audit_log.py
    └── schemas/
        ├── __init__.py
        ├── common.py
        ├── video.py
        ├── transcript.py
        ├── summary.py
        ├── mindmap.py
        ├── qa.py
        └── user.py
```

### 视频模块(2 个文件)
```
backend/app/
├── services/
│   ├── video_service.py          # yt-dlp 视频解析
│   └── transcript_service.py     # 字幕/转录服务
└── routers/
    └── video.py                  # /api/videos/* 端点
```

### AI 模块(5 个文件)
```
backend/app/
├── config/
│   └── router.py                 # 多模型路由表
├── prompts/
│   ├── __init__.py
│   └── templates.py              # Prompt 模板
├── services/
│   ├── llm_client.py             # OpenRouter 客户端
│   └── summary_service.py        # 总结服务(SSE)
└── routers/
    └── ai.py                     # /api/ai/* 端点
```

## 参考文档

- AGENTS.md: 项目设计纲要
- docs/AUTHENTICATION.md: 认证系统设计
- docs/PHASE1_COMPLETE.md: Phase 1 完成总结
- docs/PHASE2_AUTH_COMPLETE.md: Phase 2 Auth 完成总结
- docs/DEV_SERVER_GUIDE.md: 开发服务速查
