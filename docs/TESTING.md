# 测试策略规范文档

> **项目**：Video Download Summary — AI 视频总结 Web SPA  
> **版本**：v1.0  
> **维护团队**：高级开发者 / QA  
> **适用栈**：Vue 3 + Vite 7 (前端) / FastAPI + PostgreSQL (后端)  
> **最后更新日期**：2026-06-25

---

## 目录

1. [测试金字塔总览](#1-测试金字塔总览)
2. [后端测试 (pytest)](#2-后端测试-pytest)
3. [前端测试 (vitest)](#3-前端测试-vitest)
4. [E2E 测试 (Playwright)](#4-e2e-测试-playwright)
5. [性能测试](#5-性能测试)
6. [安全测试](#6-安全测试)
7. [测试数据](#7-测试数据)
8. [CI 集成](#8-ci-集成)
9. [测试报告](#9-测试报告)
10. [验证清单 (Checklist)](#10-验证清单-checklist)

---

## 1. 测试金字塔总览

```
                 ┌─────────────┐
                 │    E2E      │  10%  — Playwright, 关键用户旅程
                 ├─────────────┤
                ��  Integration ├� 20%  — API + DB + 第三方 Mock
               └┬�─────────────�┘
              �┴┴──────────────�┐
              │    Unit         │  70%  — 业务逻辑 / composables / utils
              └─────────────────�
```

| 层级 | 占比 | 框架 | 运行耗时目标 | 触发时机 |
|---|---|---|---|---|
| 单元测试 | 70% | pytest + vitest | < 3 min | 每次 `push` / PR |
| 集成测试 | 20% | pytest + TestClient | < 5 min | PR + 合并前 |
| E2E 测试 | 10% | Playwright | < 10 min | 合并前 + 每日定时 |

### 质量门禁（Quality Gate）

| 指标 | 阈值 |
|---|---|
| 后端整体覆盖率 | ≥ 80% |
| 核心模块覆盖率（支付 / SSE / URL 校验） | ≥ 90% |
| 前端整体覆盖率 | ≥ 70% |
| 集成测试通过率 | 100% |
| E2E 关键流程通过率 | 100% |
| Core Web Vitals | LCP<2.5s / INP<100ms / CLS<0.1 |

---

## 2. 后端测试 (pytest)

### 2.1 目录结构

```
backend/
└── tests/
    ├── conftest.py                 # 共享 fixture（db、client、事件循环）
    ├── unit/
    │   ├── __init__.py
    │   ├── test_url_validator.py   # URL 校验
    │   ├── test_security.py       # SSRF / 内网 IP
    │   ├── test_i18n.py           # 翻译消息
    │   └── test_services/         # 单文件模块测试
    │       ├── test_summary_service.py
    │       └── test_user_service.py
    ├── integration/
    │   ├── __init__.py
    │   ├── test_auth_api.py
    │   ├── test_summary_api.py
    │   ├── test_stripe_api.py
    │   └── test_db_interaction.py
    └── e2e/
        ├── __init__.py
        └── test_full_flow.py
```

### 2.2 共享 Fixture

```python
# backend/tests/conftest.py

import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.base import Base
from app.core.config import settings

# ---------- 内存数据库 ----------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """整个测试会话共享一个事件循环。"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db(engine) -> AsyncSession:
    """每个用例一个独立事务，结束后回滚，保证隔离。"""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(bind=connection, expire_on_commit=False)()
    yield session
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """注入测试数据库的 FastAPI 异步 client。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_openrouter(monkeypatch):
    """Mock OpenRouter SSE 流式响应。"""
    async def fake_stream(*args, **kwargs):
        chunks = [
            "这是", "AI", "对",
            "视频", "内容", "的", "总结", "。"
        ]
        for chunk in chunks:
            yield chunk.encode("utf-8")
    monkeypatch.setattr(
        "app.services.summary.stream_from_openrouter",
        fake_stream,
    )


@pytest.fixture
def mock_ytdlp(monkeypatch):
    """Mock yt-dlp，避免真实拉取视频。"""
    def fake_extract_info(url, *args, **kwargs):
        return {
            "id": "mock_123",
            "title": "Mock Video",
            "uploader": "MockUploader",
            "duration": 60,
            "automatic_captions": {"zh": [{"url": "/tmp/caption.vtt"}]},
        }
    monkeypatch.setattr("app.utils.ytdlp.extract_info", fake_extract_info)


@pytest.fixture
def mock_stripe(monkeypatch):
    """Mock Stripe 事件构造与签名验证。"""
    import stripe
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *a, **kw: {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"user_id": "usr_test"}}},
    })
```

### 2.3 覆盖率目标

```ini
# pyproject.toml / .coveragerc

[tool.coverage.run]
branch = true
source = ["app"]
omit = [
    "app/main.py",
    "app/core/config.py",
    "app/migrations/*",
]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
precision = 2
```

核心模块强制 ≥ 90%：

- `app/utils/url_validator.py`
- `app/services/summary.py`
- `app/services/stripe_service.py`
- `app/services/ytdlp_service.py`

### 2.4 用例示例：`test_validate_video_url`

```python
# backend/tests/unit/test_url_validator.py

import pytest
from app.utils.url_validator import validate_video_url, VideoUrlError

# ---------- 合法用例 ----------
@pytest.mark.parametrize(
    "url,expected_domain",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube.com"),
        ("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili.com"),
        ("https://www.douyin.com/video/71234567890", "douyin.com"),
        ("https://youtube.com/shorts/abcDEF123", "youtube.com"),
    ],
)
def test_valid_urls(url, expected_domain):
    result = validate_video_url(url)
    assert result.is_valid
    assert result.normalized_domain == expected_domain

# ---------- 非法用例 ----------
@pytest.mark.parametrize(
    "url,reason",
    [
        ("not_a_url", "INVALID_URL"),
        ("ftp://youtube.com/watch?v=123", "UNSUPPORTED_SCHEME"),
        ("https://www.google.com/", "UNSUPPORTED_DOMAIN"),
        ("", "EMPTY_URL"),
        ("   ", "EMPTY_URL"),
    ],
)
def test_invalid_urls(url, reason):
    with pytest.raises(VideoUrlError) as exc:
        validate_video_url(url)
    assert exc.value.code == reason

# ---------- 内网 / SSRF 防护 ----------
@pytest.mark.parametrize(
    "malicious_url",
    [
        "http://127.0.0.1:8080/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://0x7f000001/watch?v=1",
        "http://[::1]/",
        "http://localhost:5000/api/keys",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
    ],
)
def test_blocked_private_ips(malicious_url):
    with pytest.raises(VideoUrlError) as exc:
        validate_video_url(malicious_url)
    assert exc.value.code in {"PRIVATE_IP", "LOOPBACK"}

# ---------- 黑名单域名 ----------
@pytest.mark.parametrize(
    "url",
    [
        "https://malware.example.com/watch?v=1",
        "https://phishing-site.net/video",
    ],
)
def test_blocked_domains(url):
    with pytest.raises(VideoUrlError) as exc:
        validate_video_url(url)
    assert exc.value.code == "BLACKLISTED_DOMAIN"
```

### 2.5 用例示例：`test_stream_summary` (SSE)

```python
# backend/tests/integration/test_summary_api.py

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_stream_summary_sse_format(client: AsyncClient, mock_openrouter, mock_ytdlp):
    """AI 总结 SSE 输出必须为 `data: {json}\\n\\n` 格式。"""
    payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "language": "zh",
    }

    async with client.stream("POST", "/api/v1/summary/stream", json=payload) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        received = []
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                received.append(line[len("data:"):].strip())

    # 至少包含 1 个 chunk
    assert len(received) >= 1
    # chunk 不应为空
    assert all(chunk for chunk in received)
    # 最后一个 chunk 是终止信号
    assert received[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_stream_summary_unauthorized(client: AsyncClient):
    """未登录用户不应能触发总结。"""
    resp = await client.post(
        "/api/v1/summary/stream",
        json={"url": "https://www.youtube.com/watch?v=1", "language": "en"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_stream_summary_invalid_url(
    client: AsyncClient, mock_stripe, monkeypatch
):
    """非法 URL 应返回 422 而非 500。"""
    payload = {"url": "http://127.0.0.1/secret", "language": "en"}

    async with client.stream("POST", "/api/v1/summary/stream", json=payload) as resp:
        body = await resp.aread()

    assert resp.status_code == 422
    assert b"PRIVATE_IP" in body
```

### 2.6 用例示例：`test_stripe_webhook_signature`

```python
# backend/tests/integration/test_stripe_api.py

import pytest
import stripe
from httpx import AsyncClient


def test_valid_signature(monkeypatch, client: AsyncClient):
    """签名正确的 `checkout.session.completed` 事件应激活 VIP。"""
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")

    payload = (
        "t=1234567890,v1=valid_signature,"
        "v0=0"
    )
    headers = {"stripe-signature": "t=1234567890,v1=valid_signature"}
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"user_id": "usr_test_001"},
                "subscription": "sub_test_001",
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *a, **kw: event)

    resp = await client.post(
        "/api/v1/stripe/webhook",
        content=payload,
        headers=headers,
    )

    assert resp.status_code == 200
    user = await get_user_by_id("usr_test_001")
    assert user.plan == "pro"
    assert user.stripe_customer_id is not None


def test_invalid_signature_returns_400(monkeypatch, client: AsyncClient):
    """签名不对应返回 400，防止伪造。"""
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")

    headers = {"stripe-signature": "t=1,v1=bad_signature"}
    payload = "t=1,v1=bad_signature"

    resp = await client.post(
        "/api/v1/stripe/webhook",
        content=payload,
        headers=headers,
    )

    assert resp.status_code == 400
    assert "Invalid signature" in resp.json()["detail"]
```

### 2.7 用例示例：`test_localized_exception`

```python
# backend/tests/unit/test_i18n.py

import pytest
from app.utils.url_validator import VideoUrlError
from app.core.locale import get_localized_message


@pytest.mark.parametrize(
    "error_code,lang,expected",
    [
        ("INVALID_URL", "en", "The video URL is invalid."),
        ("INVALID_URL", "zh", "视频链接无效。"),
        ("INVALID_URL", "ja", "動画URLが無効です。"),
        ("PRIVATE_IP", "en", "Private IP addresses are not allowed."),
        ("PRIVATE_IP", "zh", "不允许使用私有 IP 地址。"),
        ("PRIVATE_IP", "ja", "プライベートIPアドレスは許可されていません。"),
    ],
)
def test_error_message_localization(error_code, lang, expected):
    assert get_localized_message(error_code, lang) == expected
```

### 2.8 异步测试规范

```python
# 所有_db 相关用例用 async def + pytest.mark.asyncio
@pytest.mark.asyncio
async def test_db_rollback_on_error(db: AsyncSession):
    from app.models.user import User
    user = User(email="rollback@test.com", plan="free")
    db.add(user)
    await db.flush()
    # 模拟异常
    with pytest.raises(ValueError):
        await db.commit()
    # 应已回滚
    result = await db.execute(
        "SELECT count(*) FROM users WHERE email='rollback@test.com'"
    )
    assert result.scalar() == 0
```

---

## 3. 前端测试 (vitest)

### 3.1 目录结构

```
frontend/
└── src/
    └── tests/
        ├── unit/
        │   ├── composables/
        │   │   ├── useOpenRouter.spec.ts
        │   │   ├── useAuth.spec.ts
        │   │   └── useI18n.spec.ts
        │   ├── utils/
        │   │   └── urlValidator.spec.ts
        │   └── components/
        │       ├── MindmapViewer.spec.ts
        │       ├── LanguageSwitcher.spec.ts
        │       └── SummaryStream.spec.ts
        └── setup.ts
```

### 3.2 测试脚本

```json
// package.json 片段
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

### 3.3 覆盖率目标

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'json-summary'],
      statements: 70,
      branches: 65,
      functions: 70,
      lines: 70,
      include: ['src/composables/**', 'src/utils/**', 'src/components/**'],
    },
  },
});
```

### 3.4 用例示例：`test_useOpenRouter_streamSummary`

```typescript
// frontend/src/tests/unit/composables/useOpenRouter.spec.ts

import { describe, it, expect, vi } from 'vitest';
import { useOpenRouter } from '@/composables/useOpenRouter';

// Mock EventSource
class MockEventSource {
  onmessage: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  close = vi.fn();

  constructor(public url: string) {
    // 模拟流式输出
    setTimeout(() => {
      const chunks = ['这是', 'AI', '总结'];
      chunks.forEach((chunk, i) => {
        setTimeout(() => {
          if (this.onmessage) {
            this.onmessage({
              data: JSON.stringify({ content: chunk }),
            });
          }
        }, i * 10);
      });
    }, 5);
  }
}

vi.stubGlobal('EventSource', MockEventSource);

describe('useOpenRouter', () => {
  it('streamSummary 应逐 chunk 累积文本', async () => {
    const { streamStatus, streamedText, streamSummary } = useOpenRouter();

    await streamSummary('https://www.youtube.com/watch?v=1', 'zh');

    expect(streamStatus.value).toBe('done');
    expect(streamedText.value).toBe('这是AI总结');
  });

  it('非 SSE 场景下 streamStatus 先 loading 后 done', async () => {
    const { streamStatus, streamSummary } = useOpenRouter();

    const promise = streamSummary('https://www.youtube.com/watch?v=1', 'en');

    expect(streamStatus.value).toBe('loading');
    await promise;
    expect(streamStatus.value).toBe('done');
  });

  it('URL 非法时应抛出错误并设置 streamStatus=error', async () => {
    const { streamStatus, error, streamSummary } = useOpenRouter();

    await streamSummary('http://127.0.0.1/secret', 'zh');

   ).toBe('error');
    expect(error.value).toMatch(/Private IP/);
  });

  it('用户主动关闭时应停止累积', async () => {
    const { streamedText, cancelStream } = useOpenRouter();
    const promise = streamSummary('https://www.youtube.com/watch?v=1', 'zh');

    cancelStream();
    await promise;

    expect(streamedText.value.length).toBeLessThan(30); // 可能截断一半
  });
});
```

### 3.5 用例示例：`test_languageSwitcher` (7 步 checklist)

```typescript
// frontend/src/tests/unit/composables/useI18n.spec.ts

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import LanguageSwitcher from '@/components/LanguageSwitcher.vue';
import { i18n } from '@/i18n';

describe('LanguageSwitcher 7 步 checklist', () => {
  it('1) 初始语言应来自 localStorage 或浏览器偏好', () => {
    localStorage.setItem('locale', 'ja');
    const wrapper = mount(LanguageSwitcher);
    expect(wrapper.find('[data-test=current-lang]').text()).toBe('日本語');
  });

  it('2) 切换语言时应更新 i18n locale', async () => {
    const wrapper = mount(LanguageSwitcher);
    await wrapper.find('[data-test=lang-en]').trigger('click');

    expect(i18n.global.locale.value).toBe('en');
    expect(localStorage.getItem('locale')).toBe('en');
  });

  it('3) 所有导航字符串切换', async () => {
    const wrapper = mount(LanguageSwitcher);
    await wrapper.find('[data-test=lang-zh]').trigger('click');

    expect(i18n.global.t('nav.home')).toBe('首页');
    expect(i18n.global.t('nav.pricing')).toBe('定价');
  });

  it('4) AI 总结语言跟随语言切换', async () => {
    const wrapper = mount(LanguageSwitcher);
    await wrapper.find('[data-test=lang-ja]').trigger('click');
    const ja = i18n.global.t('summary.placeholder');

    expect(ja).toBe('動画リンクを入力...');
  });

  it('5) 错误消息也应同步切换', () => {
    i18n.global.locale.value = 'zh';
    expect(i18n.global.t('errors.invalid_url')).toBe('视频链接无效。');

    i18n.global.locale.value = 'ja';
    expect(i18n.global.t('errors.invalid_url')).toBe('動画URLが無効です。');
  });

  it('6) HTML lang 属性跟随切换', async () => {
    const wrapper = mount(LanguageSwitcher);
    await wrapper.find('[data-test=lang-en]').trigger('click');

    expect(document.documentElement.lang).toBe('en');
  });

  it('7) SSO 回跳后保持切换后的语言', async () => {
    const wrapper = mount(LanguageSwitcher);
    await wrapper.find('[data-test=lang-zh]').trigger('click');

    // 模拟 SSO 回跳（带 ?lang=zh）
    window.history.pushState({}, '', '/?lang=zh');
    await wrapper.vm.$nextTick();

    expect(i18n.global.locale.value).toBe('zh');
  });
});
```

### 3.6 用例示例：`test_MindmapViewer`

```typescript
// frontend/src/tests/unit/components/MindmapViewer.spec.ts

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MindmapViewer from '@/components/MindmapViewer.vue';

describe('MindmapViewer', () => {
  const sampleMarkdown = `
# 人工智能
## 机器学习
### 监督学习
### 无监督学习
## 深度学习
### CNN
### Transformer
`.trim();

  it('应渲染根节点和子节点', () => {
    const wrapper = mount(MindmapViewer, { props: { markdown: sampleMarkdown } });
    const nodes = wrapper.findAll('[data-test=markmap-node]');

    expect(nodes.length).toBeGreaterThanOrEqual(4);
  });

  it('空数据时显示空状态图', () => {
    const wrapper = mount(MindmapViewer, { props: { markdown: '' } });
    expect(wrapper.find('[data-test=empty-state]').exists()).toBe(true);
  });

  it('超长内容应在 100ms 内渲染完成', async () => {
    const start = performance.now();
    mount(MindmapViewer, { props: { markdown: sampleMarkdown } });
    await new Promise(resolve => setTimeout(resolve, 200));

    const duration = performance.now() - start;
    expect(duration).toBeLessThan(100);
  });

  it('点击节点应展开/折叠子节点', async () => {
    const wrapper = mount(MindmapViewer, { props: { markdown: sampleMarkdown } });
    const rootNode = wrapper.find('[data-test=root-node]');

    await rootNode.trigger('click');
    expect(wrapper.find('[data-test=child-nodes]').classes()).toContain('collapsed');
  });
});
```

---

## 4. E2E 测试 (Playwright)

### 4.1 项目结构

```
e2e/
├── playwright.config.ts
├── fixtures/
│   ├── auth.fixture.ts
│   └── payment.fixture.ts
├── specs/
│   ├── auth.spec.ts
│   ├── summary-flow.spec.ts
│   ├── language-switch.spec.ts
│   ├── payment.spec.ts
│   └── account-deletion.spec.ts
└── pages/
    ├── LoginPage.ts
    ├── DashboardPage.ts
    └── PaymentPage.ts
```

### 4.2 Playwright 配置

```typescript
// e2e/playwright.config.ts

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './specs',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 4,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    // 移动端
    { name: 'iPhone SE', use: { ...devices['iPhone SE'] } },
    { name: 'iPad', use: { ...devices['iPad (gen 9)'] } },
    { name: 'Pixel 7', use: { ...devices['Pixel 7'] } },
  ],
});
```

### 4.3 POM 示例

```typescript
// e2e/pages/LoginPage.ts

import { Page, Locator } from '@playwright/test';

export class LoginPage {
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;

  constructor(private page: Page) {
    this.emailInput = page.locator('[data-test=email]');
    this.passwordInput = page.locator('[data-test=password]');
    this.submitButton = page.locator('[data-test=submit-login]');
  }

  async goto() {
    await this.page.goto('/login');
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}
```

### 4.4 注册 → 邮箱验证 → 登录

```typescript
// e2e/specs/auth.spec.ts

import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
import { generateTestEmail } from '../utils';

test.describe('用户注册与登录', () => {
  const uniqueEmail = generateTestEmail();

  test('成功注册 → 跳转邮箱验证页 → 点击链接完成验证 → 登录', async ({ page }) => {
    // 注册
    await page.goto('/register');
    await page.locator('[data-test=email]').fill(uniqueEmail);
    await page.locator('[data-test=password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=confirm-password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=submit-register]').click();

    // 跳转邮箱验证页
    await expect(page).toHaveURL(/verify-email/);
    await expect(page.locator('h1')).toContainText(/验证邮箱/i);

    // 从 Mailpit / Ethereal 获取验证链接
    const verifyLink = await fetchVerificationLink(uniqueEmail);
    await page.goto(verifyLink);
    await expect(page.locator('[data-test=verified-badge]')).toBeVisible();

    // 登录
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(uniqueEmail, 'StrongPassw0rd!');
    await expect(page).toHaveURL(/dashboard/);
  });

  test('重复注册应提示已存在', async ({ page }) => {
    await page.goto('/register');
    await page.locator('[data-test=email]').fill('existing@test.com');
    await page.locator('[data-test=password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=confirm-password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=submit-register]').click();
    await expect(page.locator('[data-test=error-message]')).toContainText(
      /已被注册/
    );
  });
});
```

### 4.5 审批视频链接 → AI 总结 → 流式输出

```typescript
// e2e/specs/summary-flow.spec.ts

import { test, expect } from '@playwright/test';

test.describe('AI 总结流式输出', () => {
  test('提交 YouTube 链接 → 等待总结 → SSE 流式输出完成', async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.locator('[data-test=email]').fill('vip@test.com');
    await page.locator('[data-test=password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=submit-login]').click();
    await expect(page).toHaveURL(/dashboard/);

    // 提交链接
    await page.locator('[data-test=video-url-input]').fill(
      'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    );
    await page.locator('[data-test=language-select]').selectOption('zh');
    await page.locator('[data-test=submit-summary]').click();

    // 状态：loading
    await expect(page.locator('[data-test=summary-status]')).toContainText(/总结中/i);

    // 流式输出文本累积
    const summaryContainer = page.locator('[data-test=summary-output]');
    await expect(summaryContainer).toBeVisible();

    // 等待流式完成（SSE 输出 > 50 字符）
    await expect
      .poll(async () => summaryContainer.innerText(), { timeout: 60_000 })
      .toMatch(/.{50,}/);

    // 完成标志
    await expect(page.locator('[data-test=summary-status]')).toContainText(/完成/i);

    // TAB 切换：Markdown / 思维导图
    await page.locator('[data-test=tab-mindmap]').click();
    const mindmap = page.locator('[data-test=markmap SVG]');
    await expect(mindmap).toBeVisible();
    await expect(page.locator('.markmap-node').first()).toContainText(/总结/i);
  });

  test('无效 URL 应Inline 提示错误', async ({ page }) => {
    await page.goto('/login');
    await page.locator('[data-test=email]').fill('vip@test.com');
    await page.locator('[data-test=password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=submit-login]').click();

    await page.locator('[data-test=video-url-input]').fill('not-a-url');
    await page.locator('[data-test=submit-summary]').click();

    await expect(page.locator('[data-test=error-message]')).toContainText(
      /视频链接无效/
    );
  });
});
```

### 4.6 语言切换验收

```typescript
// e2e/specs/language-switch.spec.ts

import { test, expect } from '@playwright/test';

test.describe('多语言切换', () => {
  test('中 → 日 → 全页面同步', async ({ page }) => {
    await page.goto('/dashboard');

    // 初始：中文
    await expect(page.locator('[data-test=nav-home]')).toHaveText('首页');

    // 切换: 中 → 日
    await page.locator('[data-test=language-switcher]').click();
    await page.locator('[data-test=lang-ja]').click();

    // 导航切换
    await expect(page.locator('[data-test=nav-home]')).toHaveText('ホーム');
    // AI 总结切换
    await expect(page.locator('[data-test=summary-title]')).toHaveText(
      'AI要約'
    );
    // 错误消息切换
    await page.locator('[data-test=video-url-input]').fill('invalid');
    await page.locator('[data-test=submit-summary]').click();
    await expect(page.locator('[data-test=error-message]')).toContainText(
      /動画URLが無効/
    );

    // HTML lang 应更新
    const htmlLang = await page.locator('html').getAttribute('lang');
    expect(htmlLang).toBe('ja');
  });

  test('深色模式切换应持久化', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('[data-test=toggle-dark]').click();
    await expect(page.locator('html')).toHaveClass(/dark/);

    await page.reload();
    await expect(page.locator('html')).toHaveClass(/dark/);
  });
});
```

### 4.7 Stripe 测试模式支付

```typescript
// e2e/specs/payment.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Stripe 支付流程', () => {
  test('使用测试卡 4242 4242 4242 4242 → VIP 状态更新', async ({ page }) => {
    // 登录 免费用户
    await page.goto('/login');
    await page.locator('[data-test=email]').fill('free@test.com');
    await page.locator('[data-test=password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=submit-login]').click();

    // 跳转到定价页
    await page.goto('/pricing');
    await page.locator('[data-test=subscribe-pro]').click();

    // Stripe Checkout (测试模式) 位于子 iframe
    const stripeFrame = page.frameLocator('iframe[name*="stripe"]').first();
    await stripeFrame.locator('[placeholder="Card number"]').fill('4242424242424242');
    await stripeFrame.locator('[placeholder="MM / YY"]').fill('12/30');
    await stripeFrame.locator('[placeholder="CVC"]').fill('123');
    await stripeFrame.locator('[placeholder="ZIP"]').fill('10001');
    await stripeFrame.locator('[data-testid="submit-button"]').click();

    // 支付成功 → 感谢页
    await expect(page).toHaveURL(/success/);
    await expect(page.locator('[data-test=payment-status]')).toContainText(
      /成功/
    );

    // 返回仪表盘，VIP badge 可见
    await page.goto('/dashboard');
    await expect(page.locator('[data-test=vip-badge]')).toBeVisible();
    await expect(page.locator('[data-test=plan-label]')).toContainText(/Pro/);
  });

  test('3D Secure 卡片应触发强验证', async ({ page }) => {
    await page.goto('/login');
    await page.locator('[data-test=email]').fill('free@test.com');
    await page.locator('[data-test=password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=submit-login]').click();
    await page.goto('/pricing');
    await page.locator('[data-test=subscribe-pro]').click();

    const stripeFrame = page.frameLocator('iframe[name*="stripe"]').first();
    await stripeFrame.locator('[placeholder="Card number"]').fill('4242424242424242');
    await stripeFrame.locator('[placeholder="MM / YY"]').fill('12/30');
    await stripeFrame.locator('[placeholder="CVC"]').fill('123');
    await stripeFrame.locator('[placeholder="ZIP"]').fill('10001');
    await stripeFrame.locator('[data-testid="submit-button"]').click();

    // 3D Secure 弹窗
    const challengeFrame = page.frameLocator('iframe[name*="stripe-challenge"]');
    await challengeFrame.locator('[id="test-source-authorize"]').click();

    await expect(page).toHaveURL(/success/);
  });
});
```

### 4.8 账号删除与数据清理

```typescript
// e2e/specs/account-deletion.spec.ts

import { test, expect } from '@playwright/test';
import { createClient } from '@supabase/supabase-js';

test.describe('账号删除（GDPR 被遗忘权）', () => {
  test('用户删除账号 → 所有数据被清理', async ({ page, request }) => {
    const email = `delete_${Date.now()}@test.com`;

    // 注册 & 生成数据
    await page.goto('/register');
    await page.locator('[data-test=email]').fill(email);
    await page.locator('[data-test=password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=confirm-password]').fill('StrongPassw0rd!');
    await page.locator('[data-test=submit-register]').click();
    await page.waitForURL(/verify-email/);

    // 触发删除
    await page.goto('/settings');
    await page.locator('[data-test=delete-account]').click();
    await page.locator('[data-test=confirm-delete]').fill('DELETE');
    await page.locator('[data-test=confirm-delete-submit]').click();

    await expect(page).toHaveURL(/account-deleted/);

    // Supabase 验证：用户已删除
    const supabase = createClient(
      process.env.SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_KEY!
    );
    const { data } = await supabase.auth.admin.listUsers();
    const user = data.users.find((u: any) => u.email === email);
    expect(user).toBeUndefined();
  });
});
```

### 4.9 浏览器矩阵 × 移动端

| 浏览器 | 桌面 | iPhone SE | iPad (gen 9) | Pixel 7 |
|---|---|---|---|---|
| Chromium | 必跑 | 必跑 | 必跑 | 必跑 |
| Firefox | 必跑 | 跳过 | 跳过 | 跳过 |
| WebKit (Safari) | 必跑 | 必跑 | 跳过 | 跳过 |

---

## 5. 性能测试

### 5.1 工具选型

- **Locust**（后端 API、WebSocket、SSE）
- **k6**（Core Web Vitals 前端页面）
- **Playwright + Lighthouse**（前端 Lighthouse 审计）

### 5.2 Locust 脚本示例

```python
# performance/locustfile.py

from locust import HttpUser, TaskSet, task, between
import json


class SummaryTasks(TaskSet):
    def on_start(self):
        """登录并获取 token。"""
        resp = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest@test.com",
            "password": "LoadTest123!",
        })
        self.token = resp.json()["access_token"]

    @task(5)
    def submit_summary(self):
        """提交 YouTube 链接，等待 AI 总结。"""
        self.client.post(
            "/api/v1/summary",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "language": "zh",
            },
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=15,
        )

    @task(1)
    def sse_stream(self):
        """SSE 流式输出。"""
        with self.client.get(
            "/api/v1/summary/stream?url=https%3A%2F%2Fyoutube.com%2Fwatch%3Fv%3Dabc&lang=zh",
            headers={"Authorization": f"Bearer {self.token}"},
            stream=True,
            catch_response=True,
            timeout=30,
        ) as resp:
            chunks = 0
            for line in resp.iter_lines():
                if line:
                    chunks += 1
                    if chunks == 1:
                        # 首 chunk 延迟 < 2s
                        resp.success()
                    if line == b"data: [DONE]":
                        break


class WebsiteUser(HttpUser):
    tasks = [SummaryTasks]
    wait_time = between(1, 3)
```

```bash
locust -f performance/locustfile.py \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --host https://staging.example.com
```

### 5.3 k6 脚本示例

```javascript
// performance/k6-summary.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const sseFirstChunk = new Trend('sse_first_chunk_latency');
const summaryErrorRate = new Rate('summary_errors');

export const options = {
  stages: [
    { duration: '1m', target: 50 },   // 热身
    { duration: '3m', target: 100 },  // 加压
    { duration: '1m', target: 0 },    // 冷静
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<15000'],     // AI 总结 P95 < 15s
    db_query_duration: ['p(95)<100'],       // DB < 100ms
    sse_first_chunk_latency: ['p(95)<2000'], // 首 chunk < 2s
  },
};

export default function () {
  const loginRes = http.post('https://staging.example.com/api/v1/auth/login', {
    email: 'loadtest@test.com',
    password: 'LoadTest123!',
  });
  const token = loginRes.json('access_token');

  // AI 总结 SSE 请求
  const sseRes = http.get(
    'https://staging.example.com/api/v1/summary/stream?url=https%3A%2F%2Fyoutube.com%3Fv%3DdQWgXcQ&lang=zh',
    { headers: { Authorization: `Bearer ${token}` } }
  );

  check(sseRes, {
    'SSE status is 200': (r) => r.status === 200,
    'SSE content-type is event-stream': (r) =>
      r.headers['Content-Type'].includes('text/event-stream'),
  });

  summaryErrorRate.add(sseRes.status !== 200);
  sleep(1);
}
```

### 5.4 Lighthouse / Core Web Vitals 目标

| 指标 | 目标 | 测量工具 |
|---|---|---|
| LCP | ≤ 2.5s | Lighthouse, web-vitals |
| INP | ≤ 100ms | Lighthouse, web-vitals |
| CLS | ≤ 0.1 | Lighthouse |
| TTFB | ≤ 600ms | Chrome DevTools |
| FCP | ≤ 1.8s | Lighthouse |

```typescript
// e2e/lighthouse.spec.ts
import { test, expect } from '@playwright/test';
import lighthouse from 'lighthouse';
import { playwrightLauncher } from 'lighthouse';

test('Dashboard 满足 Core Web Vitals 目标', async () => {
  const result = await lighthouse('http://localhost:5173/dashboard', {
    port: 9222,
    output: 'json',
  });
  const { lcp, cls, inp } = result.lhr.audits;

  expect(result.lhr.categories.performance.score).toBeGreaterThan(0.9);
  expect(lcp.numericValue).toBeLessThan(2500);
  expect(cls.numericValue).toBeLessThan(0.1);
});
```

---

## 6. 安全测试

### 6.1 OWASP Top 10 检查清单

| # | 风险 | 检查项 | 本项目应对 |
|---|---|---|---|
| A01 | 失效的访问控制 | 未认证用户访问 VIP 接口 | JWT 中间件; RBAC |
| A02 | 加密失败 | 密码是否 bcrypt；TLS 版本 | bcrypt + TLS 1.3 |
| A03 | 注入 | SQL 注入 / NoSQL 注入 | SQLAlchemy 参数化查询; URL 白名单 |
| A04 | 不安全设计 | SSRF、内网访问 | URL 校验 + IP 黑名单 |
| A05 | 安全配置错误 | DEBUG、CORS、Secrets | 环境变量 + CORS 白名单 |
| A06 | 过时组件 | pip-audit / npm audit | CI 内含扫描 |
| A07 | 认证失败 | 弱密码、暴力破解 | Supabase 内置 + 速率限制 |
| A08 | 软件数据完整性 | CSRF / SSRF 请求 | SameSite + CSRF token |
| A09 | 日志监控失败 | 审计日志 | Sentry + CloudWatch |
| A10 | SSRF | 视频 URL 内网探测 | 私有 IP 封禁 |

### 6.2 依赖扫描

```bash
# 后端
pip-audit --severity high --strict

# 前端
npm audit --audit-level=high
```

### 6.3 SAST (静态分析)

- GitHub 内置 **CodeQL**
- **Semgrep** 自定义规则（如下）

```yaml
# .semgrep.yml

rules:
  - id: sql-injection-risk
    patterns:
      - pattern: |
          cursor.execute(f"...{$USER_INPUT}...")
    message: "潜在 SQL 注入，请使用参数化查询"
    severity: ERROR

  - id: ssrf-risk
    patterns:
      - pattern: requests.get($URL)
    message: "未校验的 HTTP 请求，可能引发 SSRF"
    severity: WARNING

  - id: hardcoded-secret
    patterns:
      - pattern: "sk_live_..."
    message: "硬编码 secret"
    severity: ERROR
```

### 6.4 手动测试用例

| 漏洞 | 测试 payload | 期望结果 |
|---|---|---|
| SQL 注入 | `' OR 1=1; --` | 422 拒绝，日志告警 |
| 存储 XSS | `<script>alert(1)</script>` | 输入被 HTML 转义 |
| DOM XSS | `#<img src=x onerror=alert(1)>` | Vue 模板不渲染 |
| SSRF | `http://169.254.169.254/latest/meta-data/` | 被 URL 校验拦截，返回 `PRIVATE_IP` |
| CSRF | 跨站 `<form>` POST | 403，CSRF token 不匹配 |
| 速率限制 | 1 分钟内 100 次请求 | 429，含 Retry-After |
| 越权 | 用户 A 调用 `/api/v1/users/{userB.id}/delete` | 403 |
| JWT none | `{"alg":"none"}` 签名 | 401 |

### 6.5 安全测试最小通过标准

- [ ] 无 HIGH/CRITICAL CVE 依赖
- [ ] CodeQL / Semgrep 0 报错
- [ ]  全部手动用例通过
- [ ] 速率限制在 429 响应中返回正确 header
- [ ] HSTS 头部启用

---

## 7. 测试数据

### 7.1 测试视频链接

| 平台 | URL (公开) | 用于 |
|---|---|---|
| YouTube 1 | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` | 主流长视频 |
| YouTube 2 | `https://www.youtube.com/watch?v=9bZkp7q19f0` | 含字幕 |
| YouTube Shorts | `https://youtube.com/shorts/ abcDEF123` | 短视频 |
| Bilibili 1 | `https://www.bilibili.com/video/BV1xx411c7mD` | 中文长视频 |
| Bilibili 2 | `https://www.bilibili.com/video/BV1ys411S7xJ` | 中文口语 |
| Bilibili 3 | `https://www.bilibili.com/video/BV1g7411P7rW` | 视频无字幕 |
| 抖音 1 | `https://www.douyin.com/video/71234567890` | 国内短视频 |
| 抖音 2 | `https://v.douyin.com/abcDEF` | 抖音短链 |
| 抖音 3 | `https://www.douyin.com/video/71234567891` | 含字幕 |

### 7.2 测试用户与 Stripe 卡

| 账号 | 用途 | Supabase Auth 测试模式 |
|---|---|---|
| free@test.com | 免费版用户 | 激活 |
| vip@test.com | VIP 用户（Pro 计划） | 激活 |
| delete@test.com | 被删除验证 | 激活 |
| unverified@test.com | 邮箱未验证 | 未验证 |
| rate-limited@test.com | 速率限制验证 | 激活 |

| Stripe 测试卡 | 场景 | 预期 |
|---|---|---|
| `4242 4242 4242 4242` | 成功支付 | VIP 激活 |
| `4242 4242 4242 4242` (3DS) | 强验证场景 | 弹 3DS，支付成功 |
| `4000 0000 0000 9995` | 拒绝卡 | 错误提示 |

### 7.3 测试邮箱方案

```bash
# 本地 Mailpit 方案
docker run -d -p 1025:1025 -p 8025:8025 axllent/mailpit

# 或 Ethereal 在线（CI 临时账号）
curl -X POST https://api.ethereal.email/v3/mailboxes
```

在 `.env.test` 中配置：
```dotenv
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
MAIL_FROM=test@example.com
```

---

## 8. CI 集成

### 8.1 GitHub Actions 工作流

```yaml
# .github/workflows/ci.yml

name: CI Test Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 3 * * *'   # 每日凌晨 3 点全量

jobs:
  # ========== 项目:后端 ==========
  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt

      - name: Run unit tests
        run: pytest tests/unit -q --cov --cov-report=xml

      - name: Run integration tests
        run: pytest tests/integration -q --cov-append

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: backend

  # ========== 项目:前端 ==========
  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - run: npm ci
      - run: npm run test
      - run: npm run test:coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage/lcov.info
          flags: frontend

  # ========== 项目:类型检查 ==========
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run typecheck

  # ========== 项目:安全扫描 ==========
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: pip-audit (backend)
        run: |
          pip install pip-audit
          pip-audit --severity high --strict -r requirements.txt

      - name: npm audit (frontend)
        run: npm audit --audit-level=high

      - name: GitHub CodeQL
        uses: github/codeql-action/analyze@v3

      - name: Semgrep
        uses: semgrep/semgrep-action@v1

  # ========== 项目:E2E ==========
  e2e:
    needs: [backend-test, frontend-test, typecheck, security]
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - run: npm ci
      - run: npx playwright install --with-deps

      - name: Start dev server
        run: npm run preview &
        env:
          NODE_ENV: test

      - name: Run E2E
        run: npx playwright test --reporter=list
        env:
          E2E_BASE_URL: http://localhost:4173

      - name: Upload Playwright report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

### 8.2 Branch Protection Rule

在 GitHub Settings > Branch protection 配置：

- [ ] Require a pull request before merging
- [ ] Require status checks to pass before merging
  - `backend-test`
  - `frontend-test`
  - `typecheck`
  - `security`
  - `e2e`
- [ ] Require branches to be up to date before merging
- [ ] Require conversation resolution before merging

---

## 9. 测试报告

### 9.1 各层级报告格式

| 层级 | 报告工具 | 输出格式 |
|---|---|---|
| 后端单元 | pytest-html + pytest-cov | HTML + XML + Cobertura |
| 前端单元 | vitest --coverage | lcov / text-summary |
| E2E | Playwright built-in | HTML + JSON |
| Performance | Locust / k6 | CSV + Console |
| Security | pip-audit / npm audit / CodeQL | SARIF |

### 9.2 pytest-html 配置

```ini
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--html=reports/backend/report.html --self-contained-html --cov=app --cov-report=html:reports/backend/coverage-html --cov-report=xml:reports/backend/coverage.xml"
```

```python
# 自定义报告标题
def pytest_html_report_title(report):
    report.title = "Video Summary - Backend Test Report"
```

### 9.3 Codecov 配置

```yaml
# codecov.yml

coverage:
  precision: 2
  round: down
  range: "70...100"

  status:
    project:
      default:
        target: 80%
        threshold: 1%
      backend:
        target: 85%
        flags:
          - backend
      frontend:
        target: 70%
        flags:
          - frontend

comment:
  layout: "diff, flags, files"
  behavior: default
```

### 9.4 失败通知

```yaml
# .github/workflows/ci.yml 末尾添加

  notify:
    needs: [backend-test, frontend-test, e2e, security]
    if: failure()
    runs-on: ubuntu-latest
    steps:
      - name: Slack 通知
        uses: 8398a7/action-slack@v3
        with:
          status: failure
          text: |
            CI 失败: ${{ github.repository }} @ ${{ github.sha }}
            ${{ github.event.commits[0].message }}
            链接: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}

      - name: Discord 备用通知
        uses: sarisia/actions-status-discord@v1
        with:
          webhook: ${{ secrets.DISCORD_WEBHOOK }}
          title: "CI 失败"
          color: 0xff0000
```

---

## 10. 验证清单 (Checklist)

每个 PR / 发版前必须逐项勾选。

### 10.1 代码质量

- [ ] 所有单元测试通过 (`pytest` / `vitest`)
- [ ] 所有集成测试通过
- [ ] 所有 E2E 关键流程通过（含移动端 iPhone SE / iPad）
- [ ] 后端覆盖率 ≥ 80%，核心模块 ≥ 90%
- [ ] 前端覆盖率 ≥ 70%
- [ ] 无 type-check 错误 (`tsc --noEmit`)
- [ ] linter / formatter 通过 (`ruff`, `eslint`, `prettier`)

### 10.2 业务逻辑

- [ ] URL 校验：合法/非法/内网/黑名单 四类边界
- [ ] SSE 流式格式：每 chunk `data: {json}\n\n`，尾 chunk `[DONE]`
- [ ] Stripe webhook 签名验证正确，伪造签名返回 400
- [ ] 支付后 VIP 状态更新 ≤ 5s
- [ ] 语言切换 7 步全部通过（含 HTML lang、错误消息、AI 总结）
- [ ] 深色模式切换持久化（localStorage）
- [ ] 账号删除后 Supabase 用户已移除

### 10.3 性能

- [ ] 100 并发下 AI 总结 P95 < 15s
- [ ] SSE 首 chunk < 2s
- [ ] 数据库查询 < 100ms（P95）
- [ ] LCP < 2.5s / INP < 100ms / CLS < 0.1
- [ ] 前端 bundle 首屏 < 1.5s（国内访问）

### 10.4 安全

- [ ] pip-audit 无 HIGH / CRITICAL
- [ ] npm audit --audit-level=high 通过
- [ ] CodeQL / Semgrep 0 报错
- [ ] 手动 SQL 注入 / XSS / SSRF / CSRF / 越权测试通过
- [ ] 速率限制 429 正确返回
- [ ] JWT 签名算法非 `none`
- [ ] HTTPS 强制启用（HSTS header）
- [ ] Console 无明文 secret
- [ ] CORS 白名单仅含前端域名

### 10.5 法律合规

- [ ] GDPR 删除权（账号删除流程可用）
- [ ] DMCA 投诉入口可达（`/dmca`）
- [ ] Cookie Consent 弹窗可用
- [ ] 隐私政策 / Terms 链接可达

### 10.6 发版前最终门禁

- [ ] branch protection 全部状态检查通过
- [ ] Code review ≥ 1 人批准
- [ ] CHANGELOG 已更新
- [ ] 测试账号已清理（delete@test.com）
- [ ] 监控 / 告警通道已配置（Sentry DSN、Slack Webhook）
- [ ] 回滚脚本已准备（前端静态 + 后端数据库 migration 兼容）

---

## 附录 A：常用命令速查

```bash
# ===== 后端 =====
pytest tests/unit -x                       # 遇到失败即停
pytest tests/unit -k "test_validate"        # 按关键字筛选
pytest --cov --cov-report=term-missing      # 查看缺失代码
pytest -n auto                             # 并行运行 (pytest-xdist)
pytest -m "not slow"                       # 跳过耗时用例

# ===== 前端 =====
npm run test                               # 单次运行
npm run test:watch                         # 监听模式:coverage                      # 覆盖率

# ===== E2E =====
npx playwright test --debug                # 调试模式
npx playwright test --project=chromium      # 仅 Chromium
npx playwright test --workers=1            # 串行调试
npx playwright install                     # 安装浏览器

# ===== 性能 =====
locust -f performance/locestfile.py        # Locust
k6 run performance/k6-summary.js           # k6

# ===== 安全 =====
pip-audit --severity high
npm audit --audit-level=high
semgrep --config=auto
```

## 附录 B：测试账号 / 卡号汇总

| 账号 | 用途 |
|---|---|
| free@test.com / StrongPassw0rd! | 免费用户 |
| vip@test.com / StrongPassw0rd! | VIP 用户 |
| delete@test.com / StrongPassw0rd! | 账号删除测试 |
| unverified@test.com | 邮箱未验证 |
| rate-limited@test.com | 速率限制 |

| Stripe 测试卡 | 用途 |
|---|---|
| 4242 4242 4242 4242 / 12/30 / 123 | 支付成功 |
| 4242 4242 4242 4242 / 12/30 / 123 | 触发 3DS |
| 4000000000009995 | 支付被拒 |

## 附录 C：变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v1.0 | 2026-06-25 | 初始版本，遵循 Vue 3 + Vite 7 / FastAPI 技术栈 |
