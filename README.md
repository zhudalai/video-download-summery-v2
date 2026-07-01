# AI 万能视频下载总结器

> 输入视频链接,自动解析 1800+ 平台,AI 视频总结 + 思维导图 + 问答 + 字幕下载 + 多语言翻译。

[![Vue 3](https://img.shields.io/badge/Vue-3.x-42b883)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776ab)](https://python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## ✨ 功能特性

### 核心功能
- 🎬 **视频解析** — 支持 YouTube、Vimeo、Dailymotion 等 1800+ 平台(基于 yt-dlp)
- 📥 **视频下载** — 高清选择(1080P/720P/仅音频),自动 ffmpeg 合并音视频
- 📝 **AI 视频总结** — OpenRouter 流式生成 Markdown 格式总结(SSE 实时推送)
- 🧠 **思维导图** — 基于总结自动生成可交互 markmap,支持缩放/全屏/导出 PNG(4K)/SVG
- 💬 **AI 问答** — 基于视频内容的 RAG 问答,流式回答
- 📄 **字幕下载** — 支持原始字幕下载,SRT/VTT/TXT 格式导出
- 🌐 **字幕翻译** — 下载原始字幕 + LLM 按需翻译(任何语言互译)
- 🌍 **多语言支持** — 英语/中文/日语,一键切换全部 UI + AI 内容

### 技术亮点
- 单页工作台设计,无需页面跳转
- SSE 流式输出(总结/问答实时显示)
- Tab 切换内容保留(v-show 显隐,不重新加载)
- 4 个 Tab 同时加载(总结/字幕/导图/问答)
- 响应式布局,移动端友好
- 语言切换后自动重新生成所有内容

## 🖥️ 界面截图

### 双栏工作台
![工作台](localhost_5173_.png)

### AI 总结摘要
![总结](localhost_5173_%20(1).png)

### 字幕文本
![字幕](localhost_5173_%20(2).png)

### 思维导图
![导图](localhost_5173_%20(3).png)

## 🏗️ 技术栈

### 前端
| 技术 | 用途 |
|---|---|
| Vue 3 + TypeScript | 框架 |
| Vite 7 | 构建工具 |
| Tailwind CSS 4 | 原子化 CSS |
| vue-i18n | 多语言 |
| Pinia | 状态管理 |
| marked + DOMPurify | Markdown 渲染 + XSS 防护 |
| markmap-lib + markmap-view | 思维导图 |

### 后端
| 技术 | 用途 |
|---|---|
| FastAPI (Python 异步) | Web 框架 |
| SQLAlchemy async + aiosqlite | ORM + 数据库 |
| yt-dlp | 视频解析/下载 |
| OpenRouter | AI 模型网关 |
| Supabase Auth | 用户认证 |
| Stripe | 支付订阅 |

## 🚀 快速开始

### 前置要求
- Node.js 20+
- Python 3.12+
- FFmpeg(用于音视频合并,可选)

### 1. 克隆仓库
```bash
git clone https://github.com/zhudalai/video-download-summery-v2.git
cd video-download-summery-v2
```

### 2. 启动后端
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 启动
python -m uvicorn app.main:app --reload --port 8000
```

### 3. 启动前端
```bash
cd frontend
npm install
npm run dev
```

### 4. 访问
打开浏览器访问 http://localhost:5173

## 🔧 环境变量

### 后端 `.env`
```env
# 数据库
DATABASE_URL=sqlite+aiosqlite:///./dev.db

# Supabase Auth
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# OpenRouter(模型网关)
OPENROUTER_API_KEY=sk-or-xxxxxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Stripe(支付)
STRIPE_SECRET_KEY=sk_test_xxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxx

# 应用配置
APP_ENV=development
FRONTEND_URL=http://localhost:5173

# 字幕配置
# 是否下载自动生成字幕(YouTube 自动字幕可能触发 429 限流)
# False: 只下载人工字幕(默认,稳定)
# True: 同时下载自动字幕(可能触发 429,但能获取更多字幕)
DOWNLOAD_AUTO_SUBTITLES=False
```

### 前端 `.env`
```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

## ⚙️ 配置说明

### 模型切换
AI 模型配置在 `backend/app/config/router.py`:
```python
MODEL = "openrouter/free"  # 改为其他模型如 "openrouter/owl-alpha"
```

### 字幕自动下载
通过环境变量 `DOWNLOAD_AUTO_SUBTITLES` 控制:
- `False`(默认): 只下载人工字幕,稳定可靠
- `True`: 同时下载自动字幕,但可能触发 YouTube 429 限流

### 字幕语言
前端默认使用 `language="auto"`,后端会下载所有可用字幕语言。如需指定语言,修改 `frontend/src/components/VideoSummary.vue` 中 `startSummarize()` 的 `lang` 参数。

## 📁 项目结构

```
video-download-summery/
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── components/     # 通用组件
│   │   │   ├── VideoSummary.vue    # 核心:4 Tab 内容
│   │   │   ├── VideoInfoPanel.vue  # 左栏:视频信息
│   │   │   ├── TabPanel.vue        # Tab 导航
│   │   │   └── LanguageSwitcher.vue
│   │   ├── pages/          # 页面
│   │   │   └── WorkshopPage.vue    # 工作台主页面
│   │   ├── stores/         # Pinia 状态
│   │   │   ├── video.ts            # 视频状态
│   │   │   ├── summary.ts          # 总结状态
│   │   │   ├── auth.ts             # 认证状态
│   │   │   └── user.ts             # 用户信息
│   │   ├── i18n/           # 翻译文件(en/zh-CN/ja)
│   │   └── styles/         # Tailwind CSS
│   └── package.json
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── routers/        # API 路由
│   │   │   ├── video.py            # 视频解析/字幕/下载
│   │   │   ├── ai.py               # AI 总结/问答
│   │   │   ├── auth.py             # 用户认证
│   │   │   └── payment.py          # 支付
│   │   ├── services/       # 业务逻辑
│   │   │   ├── video_service.py    # 视频/字幕下载
│   │   │   ├── summary_service.py  # AI 总结服务
│   │   │   └── llm_client.py       # LLM 客户端
│   │   ├── models/         # 数据模型
│   │   ├── prompts/        # AI Prompt 模板
│   │   └── config/         # 配置(路由/模型)
│   └── requirements.txt
├── docs/                   # 设计文档
└── CLAUDE.md               # 项目开发指南
```

## 📖 API 端点

### 视频
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/videos/parse` | 解析视频信息 |
| POST | `/api/videos/subtitles` | 下载字幕(JSON) |
| GET  | `/api/videos/download/subtitles` | 下载字幕文件(SRT/VTT/TXT) |
| POST | `/api/videos/translate` | 翻译字幕 |
| POST | `/api/videos/download` | 下载视频文件 |

### AI
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ai/summary` | AI 总结(SSE 流式) |
| POST | `/api/ai/qa` | AI 问答(SSE 流式) |

### 认证
| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/api/auth/me` | 当前用户信息 |
| GET  | `/api/auth/me/role` | 当前用户角色 |

## 🌐 多语言

支持三种语言,翻译文件位于 `frontend/src/i18n/locales/`:
- `en` — English
- `zh-CN` — 简体中文
- `ja` — 日本語

切换语言后,以下内容会自动重新生成:
- 总结摘要
- 思维导图
- 字幕(翻译)
- 问答内容

## 📄 License

MIT License

---

**开发工具**: 本项目使用 Claude Code 辅助开发。