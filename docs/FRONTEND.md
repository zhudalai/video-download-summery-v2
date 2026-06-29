# 前端架构规范

> 前端负责 UI 交互、多语言展示、SSE 流式渲染、思维导图。基于 Vue 3 + Vite 7 + Tailwind CSS 4,SPA 形态。

---

## 一、目录结构

```
src/
├── main.ts                    # 入口,挂载 vue-i18n、Pinia、Router
├── App.vue                    # 根组件,全局布局
├── components/                # 通用组件
│   ├── ui/                    # 基础 UI 按钮/输入框/卡片
│   ├── layout/                # Header/Footer/Sidebar
│   └── i18n/                  # LanguageSwitcher/RTLToggle
├── composables/               # 可复用逻辑
│   ├── useOpenRouter.ts      # SSE 流式请求封装
│   ├── useI18n.ts             # 语言切换扩展逻辑
│   └── useSEO.ts              # hreflang/OG 标签生成
├── layouts/                   # 页面布局(default/auth/blank)
├── locales/                   # 翻译文件
│   ├── en/                    # 英语(源语言)
│   │   ├── common.json        # 通用文案
│   │   ├── download.json      # 下载模块
│   │   ├── summary.json       # AI 总结模块
│   │   ├── billing.json       # 支付模块
│   │   └── errors.json        # 前端错误码
│   ├── zh/                    # 中文(简体)
│   └── ja/                    # 日语
├── pages/                     # 路由页面
│   ├── home.vue               # 着陆页
│   ├── download.vue           # 视频解析与下载
│   ├── summary.vue            # AI 总结详情
│   ├── mindmap.vue            # 思维导图
│   ├── qa.vue                 # AI 问答
│   ├── billing.vue            # 支付/订阅管理
│   ├── login.vue              # 登录(Supabase Auth)
│   └── errors/                # 错误页
│       ├── 404.vue
│       └── dmca.vue           # DMCA 政策页
├── router/                    # 路由配置
│   ├── index.ts               # 路由定义
│   └── guards.ts              # 认证守卫、语言自动路由
├── stores/                    # Pinia 状态管理
│   ├── user.ts                # 用户信息、VIP 状态
│   ├── video.ts               # 当前视频、下载状态
│   └── summary.ts             # AI 总结、SSE 状态
├── services/                  # API 调用层
│   ├── api.ts                 # axios 实例、拦截器
│   ├── video.ts               # 视频相关 API
│   ├── ai.ts                  # OpenRouter SSE 连接
│   └── payment.ts             # Stripe API
├── styles/                    # Tailwind 配置
│   ├── main.css               # 入口、@tailwind 指令
│   └── theme.ts               # 自定义主题(token)
├── types/                     # TypeScript 类型定义
│   ├── video.ts
│   ├── ai.ts
│   └── user.ts
└── vite-env.d.ts
```

---

## 二、技术选型与版本

| 库 | 版本 | 用途 |
|---|---|---|
| vue | ^3.5 | 核心框架 |
| vite | ^7.0 | 构建工具 |
| tailwindcss | ^4.0 | 原子化 CSS(新语法 `@theme`) |
| vue-router | ^4.4 | 前端路由 |
| pinia | ^2.2 | 状态管理 |
| vue-i18n | ^10.0 | 多语言 |
| @intlify/unplugin-vue-i18n | ^6.0 | Vite 插件,JSON → 内联 chunk |
| @unhead/vue | ^2.0 | SEO head 管理(hreflang/OG) |
| axios | ^1.7 | HTTP 客户端 |
| markmap-lib | ^0.17 | 思维导图解析 |
| marked | ^15.0 | Markdown 渲染 |
| @tailwindcss/typography | ^0.5 | Markdown 美化 |
| zod | ^3.23 | 表单校验 |

---

## 三、vue-i18n 配置规范

### 3.1 语言代码约定

采用 **BCP-47 标准**:

| 语言 | 代码 | 备注 |
|---|---|---|
| 英语(源语言) | `en` | 默认 fallback |
| 简体中文 | `zh-CN` | 中文站核心 |
| 日语 | `ja` | V1 第三语言 |

### 3.2 Key 命名规范

采用 `module.context.action` 层级结构:

```json
{
  "download": {
    "input": {
      "placeholder": "Paste video URL...",
      "submit": "Analyze"
    },
    "status": {
      "parsing": "Parsing video info...",
      "success": "Ready to download",
      "error": {
        "invalid_url": "Invalid video URL",
        "unsupported": "Unsupported platform"
      }
    }
  }
}
```

**规则:**
- 全小写 + 下划线分隔
- 按模块分文件,避免单文件过大
- 错误码统一用 `error.` 前缀
- 动态变量用花括号:`{name}`、`{count}`

### 3.3 语言切换流程

切换语言时必须完成 **7 步 checklist**:

1. 更新 `<html lang="xx">` 和 `document.dir`
2. 调用 `vue-i18n.setLocaleMessage()` 加载目标语言包
3. PATCH `/me/language` 同步到后端用户偏好
4. 刷新当前页面翻译内容
5. 重新请求带新语言的 API(错误消息会变化)
6. 刷新 `<title>` 和 OG 标签
7. 若当前有 AI 总结缓存,重新调 LLM(缓存键带 `lang`)

### 3.4 TypeScript 类型校验

使用 `vue-tsc` + `typescript-plugin` 在编译期检查缺失 key:

```ts
// types/i18n.d.ts
declare module 'vue-i18n' {
  export interface DefineLocaleMessage {
    download: typeof import('@/locales/en/download.json')
  }
}
```

---

## 四、Tailwind CSS 4 约定

### 4.1 新语法迁移

Tailwind 4 使用 `@theme` 定义 token,不再用 `tailwind.config.js`:

```css
/* styles/main.css */
@import "tailwindcss";

@theme {
  --color-primary: #6366f1;
  --color-primary-hover: #4f46e5;
  --font-sans: "Inter", "Noto Sans SC", "Noto Sans JP", sans-serif;
  --breakpoint-4xl: 1920px;
}
```

### 4.2 多语言字体

中日韩需要专门字体栈:

```css
@theme {
  --font-zh: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-ja: "Noto Sans JP", "Hiragino Sans", "Yu Gothic", sans-serif;
}
```

### 4.3 非拉丁排版注意事项

- 中日韩 line-height 比英文大(1.7-1.8 vs 1.5)
- 中文标点符号(书名号、省略号)需要特殊处理
- 德语复合词很长,按钮最小宽度要留足
- 日语敬语体系影响文案长度(同一意思日语比英语长 30-50%)

---

## 五、SSE 流式输出实现

### 5.1 前端封装

```ts
// composables/useOpenRouter.ts
export function useOpenRouter() {
  const summary = ref('')
  const isStreaming = ref(false)

  async function streamSummary(videoId: string, locale: string) {
    const response = await fetch(`/api/ai/summary?video_id=${videoId}&lang=${locale}`, {
      headers: { Accept: 'text/event-stream' }
    })
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value)
      // SSE 格式: data: {...}\n\n
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          summary.value += data.content
        }
      }
    }
  }

  return { summary, isStreaming, streamSummary }
}
```

### 5.2 UX 规范

- 流式过程中显示"打字中"动画(三点 pulse)
- 第一个 chunk 到达前显示骨架屏
- 流式完成后自动渲染 Markdown + 生成思维导图
- 流式过程中禁止用户切换语言(避免内容割裂)

---

## 六、思维导图集成

### 6.1 markmap 使用

```ts
// components/MindmapViewer.vue
import { transform } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const markdown = ref('# AI Summary\n## Topic 1\n- Key point')
const svgRef = ref<SVGSVGElement>()

onMounted(() => {
  const { root } = transform(markdown.value)
  Markmap.create(svgRef.value!, root)
})
```

### 6.2 交互功能

- 全屏按钮(调用 `Fullscreen API`)
- 缩放 +/- 按钮(鼠标滚轮也支持)
- 导出 PNG(使用 `html2canvas` 或 `canvg`)
- 导出 SVG(直接从 DOM 序列化)

---

## 七、SEO 实现

### 7.1 hreflang 生成

```ts
// composables/useSEO.ts
import { useHead } from '@unhead/vue'

export function useHreflang(currentPath: string) {
  const languages = ['en', 'zh-CN', 'ja']
  const baseUrl = 'https://yourdomain.com'

  useHead({
    link: [
      ...languages.map(lang => ({
        rel: 'alternate',
        hreflang: lang,
        href: `${baseUrl}/${lang}${currentPath}`
      })),
      {
        rel: 'alternate',
        hreflang: 'x-default',
        href: `${baseUrl}/en${currentPath}`
      }
    ]
  })
}
```

### 7.2 OG 标签本地化

每个页面必须包含:

- `og:title` — 本地化标题
- `og:description` — 本地化描述
- `og:locale` — 当前语言
- `og:locale:alternate` — 其他可用语言
- `og:image` — 语言特定封面图(不是直接翻译)

---

## 八、路由与守卫

### 8.1 语言自动路由

```ts
// router/guards.ts
router.beforeEach((to, from, next) => {
  const supported = ['en', 'zh-CN', 'ja']
  const lang = to.params.lang as string

  if (!supported.includes(lang)) {
    // 按 Accept-Language 或浏览器语言重定向
    const browserLang = navigator.language
    const matched = supported.find(l => browserLang.startsWith(l.split('-')[0]))
    next(`/${matched || 'en'}${to.path}`)
  } else {
    next()
  }
})
```

### 8.2 认证守卫

```ts
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth) {
    const user = await supabase.auth.getUser()
    if (!user) next('/login')
  }
  if (to.meta.requiresVip) {
    const isVip = store.getters.isVip
    if (!isVip) next('/billing')
  }
})
```

---

## 九、状态管理 (Pinia)

### 9.1 核心 Store

```ts
// stores/summary.ts
export const useSummaryStore = defineStore('summary', () => {
  const videoId = ref('')
  const content = ref('')
  const status = ref<'idle' | 'streaming' | 'done' | 'error'>('idle')
  const locale = ref('en')

  async function generate(videoId: string, lang: string) {
    status.value = 'streaming'
    content.value = ''
    locale.value = lang
    // SSE 流式接收
  }

  return { videoId, content, status, locale, generate }
})
```

---

## 十、性能优化

### 10.1 路由懒加载

```ts
const routes = [
  {
    path: '/summary',
    component: () => import('@/pages/summary.vue')
  }
]
```

### 10.2 翻译文件懒加载

```ts
async function loadLocaleMessages(locale: string) {
  const messages = await import(`@/locales/${locale}/common.json`)
  i18n.setLocaleMessage(locale, messages)
}
```

### 10.3 图片优化

- 使用 `<picture>` + `WebP` 格式
- 封面图使用 `loading="lazy"`
- OG 图尺寸固定 1200×630

---

## 十一、验证清单

- [ ] 语言切换 7 步 checklist 全部执行
- [ ] SSE 流式输出实时渲染 Markdown
- [ ] 思维导图可缩放/全屏/导出
- [ ] hreflang 三语言互相指向
- [ ] OG 标签本地化
- [ ] 路由懒加载生效
- [ ] TypeScript 编译无缺失 key 警告
- [ ] 中日韩排版 line-height 正确
- [ ] 德语长词按钮不溢出
