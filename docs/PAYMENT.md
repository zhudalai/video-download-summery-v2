# Video Summary - Payment System Design Document
> Version: 1.0.0 | 更新日期：2006-06-25 | 维护团队：Video Summary Platform Team
> 适用范围：Web SPA (Vue 3 + Vite 7) + FastAPI 后端 + Stripe Billing
> 本文档覆盖账户配置、产品定价、Checkout、Webhook、订阅管理、PDF 回执、多币种、税务、Dunning、本地支付、退款、上线检查清单共 12 个章节。

---

## 目录

1. [Stripe 账户配置](#1-stripe-账户配置)
2. [产品与价格体系](#2-产品与价格体系)
3. [Checkout 结账流程](#3-checkout-结账流程)
4. [Webhook 事件处理](#4-webhook-事件处理)
5. [订阅管理](#5-订阅管理)
6. [PDF 回执自渲染](#6-pdf-回执自渲染)
7. [税务处理](#7-税务处理)
8. [多币种支持](#8-多币种支持)
9. [Dunning 催款流程](#9-dunning-催款流程)
10. [本地支付方式 (V2)](#10-本地支付方式-v2)
11. [退款政策](#11-退款政策)
12. [上线检查清单](#12-上线检查清单)

---

## 1. Stripe 账户配置

### 1.1 账户开通 (Stripe Atlas)

推荐走 **Stripe Atlas** 注册美国特拉华州 C-Corp 实体，获得以下优势：
- 公司信用卡 + EIN + 美国银行账户（Mercury）
- W-8BEN-E 表格自动处理，代扣 30% 美国预扣税可通过税收协定减免
- 一站式开通 Stripe Account

```bash
# Atlas 注册后得到的账号信息示例
# Account ID: acct_1NxYLfKXzQ7pR2mW
# 发布密钥: pk_live_YOUR_REAL_KEY_HERE
# 私密密钥: sk_live_YOUR_REAL_KEY_HERE
# Webhook 密钥: whsec_YOUR_REAL_KEY_HERE
```

### 1.2 环境变量配置

后端 `.env`（生产绝不发布 `.env`，仅作开发引用；生产使用 Vault/AWS Secrets Manager）：

```dotenv
# === Stripe API 密钥 ===
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# === Stripe Billing 配置 ===
STRIPE_TAX_RATE_ID=txr_xxxxxxxxxxxxxxxxxxxxxxxx   # 可选默认税率
STRIPE_TAX_ENABLED=true

# === 业务配置 ===
BILLING_DEFAULT_CURRENCY=usd
BILLING_TRIAL_DAYS=7
BILLING_REFUND_DAYS=14
BILLING_DUNNING_MAX_RETRIES=3

# === Webhook ===
WEBHOOK_BASE_URL=https://api.videosummary.com
WEBHOOK_ENDPOINT=/api/webhook/stripe

# === 邮件服务 (Brevo) ===
BREVO_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
BREVO_SENDER_EMAIL=billing@videosummary.com
BREVO_SENDER_NAME=Video Summary

# === Redis (Dunning / 队列) ===
REDIS_URL=redis://127.0.0.1:6379/1

# === PostgreSQL ===
DATABASE_URL=postgresql+asyncpg://user:pass@db.internal:5432/videosummary
```

前端 `.env`：

```dotenv
# 前端只暴露 PUBLISHABLE_KEY（无法发起敏感操作）
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
VITE_API_BASE_URL=https://api.videosummary.com
```

### 1.3 Webhook 端点注册

```python
# backend/config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    strIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_TAX_ENABLED: bool = True
    BILLING_DEFAULT_CURRENCY: str = "usd"
    BILLING_TRIAL_DAYS: int = 7
    BILLING_REFUND_DAYS: int = 14
    BILLING_DUNNING_MAX_RETRIES: int = 3
    WEBHOOK_BASE_URL: str
    BREVO_API_KEY: str
    REDIS_URL: str = "redis://127.0.0.1:6379/1"
    DATABASE_URL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

在 Stripe Dashboard → Developers → Webhooks → Add endpoint：

```
Endpoint URL: https://api.videosummary.com/api/webhook/stripe
Events to listen:
  - customer.subscription.created
  - customer.subscription.updated
  - customer.subscription.deleted
  - customer.subscription.trial_will_end
  - invoice.paid
  - invoice.payment_failed
  - invoice.upcoming
  - charge.refunded
  - payment_intent.payment_failed
  - checkout.session.completed
  - customer.updated
  - payment_method.attached
```

### 1.4 Dashboard 品牌设置

Finance → Settings → Business settings → Public details：
- **Company name**: Video Summary, Inc.
- **Support email**: support@videosummary.com
- **Support phone**: 可选（法律建议有）
- **Statement descriptor**: VIDSUM (少于 22 字符)
- **Logo**: SVG 白底
- **Receipt footer**: 包含公司注册地址、VAT ID（EU）

---

## 2. 产品与价格体系

### 2.1 定价策略

采用 **心理定价（Charming Pricing）**：
- $7.99 / $14.99 相比 $9.99 / $19.99 转化率长期高 12-18%（Stripe 内部基准）
- 年付给予 **40% 折扣**，鼓励现金流前置：
  - Pro 年付：$7.99 × 12 × (1 - 0.4) = $57.53 → 定价 $59.99
  - Premium 年付：$14.99 × 12 × (1 - 0.4) = $107.93 → 定价 $119.99

| 套餐 | 月付 | 年付（40% OFF） | 7 天试用 |
|------|------|-----------------|----------|
| Free | $0 | $0 | ✗ |
| Pro | $7.99/mo | $59.99/yr（$4.99/mo）| ✓ |
| Premium | $14.99/mo | $119.99/yr（$9.99/mo）| ✓ |

### 2.2 Price ID 命名规范

Stripe 建议每个 **product × currency × interval** 建一个 Price，命名清晰便于查询。

```
product_pro_usd_monthly       price_1NxYLfxxxxxxxxxxxx
product_pro_usd_annual        price_1NxYLfyyyyyyyyyyyy
product_premium_usd_monthly   price_1NxYLfzzzzzzzzzzzz
product_premium_usd_annual    price_1NxYLfwwwwwwwwwwww
```

> V2 上线后在中国/日本锁币种，分别建 `price_1NxYLfCNYProMonthly` 等。

### 2.3 环境变量管理方案

生产不该每次调 API 动态拉 Price List；价格更新流程：
1. 在 Stripe Dashboard 创建新 Price（原 Price 保留归档，不删）
2. 更新 `Price_ID` 环境变量
3. 重启后端；前端异步无需重启

```dotenv
# === Price IDs ===
STRIPE_PRICE_FREE_MONTHLY=free               # Free 套餐无需 Price
STRIPE_PRICE_PRO_MONTHLY=price_1NxYLfProMonthly
STRIPE_PRICE_PRO_ANNUAL=price_1NxYLfProAnnual
STRIPE_PRICE_PREMIUM_MONTHLY=price_1NxYLfPremiumMonthly
STRIPE_PRICE_PREMIUM_ANNUAL=price_1NxYLfPremiumAnnual
```

后端加载模块：

```python
# backend/config/pricing.py
from pydantic import BaseModel
from config.settings import settings

class PriceConfig(BaseModel):
    monthly: str | None
    annual: str | None

class PricingCatalog(BaseModel):
    free: None_ = None
    pro: PriceConfig
    premium: PriceConfig

PRICING = PricingCatalog(
    free=None,
    pro=PriceConfig(
        monthly=settings.STRIPE_PRICE_PRO_MONTHLY,
        annual=settings.STRIPE_PRICE_PRO_ANNUAL,
    ),
    premium=PriceConfig(
        monthly=settings.STRIPE_PRICE_PREMIUM_MONTHLY,
        annual=settings.STRIPE_PRICE_PREMIUM_ANNUAL,
    ),
)

def get_price_id(tier: str, interval: str, currency: str = "usd") -> str:
    tier_config = getattr(PRICING, tier, None)
    if tier_config is None:
        raise ValueError(f"Unknown tier: {tier}")
    price_id = getattr(tier_config, interval, None)
    if price_id is None:
        raise ValueError(f"Unknown interval: {interval}")
    return price_id
```

### 2.4 前端 Pricing API 定义

前端在访问 `/api/billing/pricing` 拿到当前价格（避免硬编码）：

```typescript
// src/types/billing.ts
export type BillingTier = 'free' | 'pro' | 'premium'
export type BillingInterval = 'monthly' | 'annual'
export type CurrencyCode = 'usd' | 'cny' | 'jpy' | 'eur' | 'gbp'

export interface PriceItem {
  priceId: string
  currency: CurrencyCode
  amount: number           // 单位：Stripe currency 最小单位（如 USD 为分）
  displayAmount: string    // 如 "$7.99"
  interval: BillingInterval
}

export interface TierDetail {
  tier: BillingTier
  name: string
  description: string
  features: string[]
  monthly: PriceItem | null
  annual: PriceItem | null
  annualDiscountPercent: number
}

export interface PricingResponse {
  defaultCurrency: CurrencyCode
  tiers: TierDetail[]
}
```

```typescript
// src/composables/usePricing.ts
import { ref, computed } from 'vue'
import type { PricingResponse, BillingTier, BillingInterval, PriceItem } from '@/types/billing'

const PRICING_CACHE_KEY = 'vs_pricing_v1'
const PRICING_CACHE_TTL_MS = 5 * 60 * 1000

let cached: { data: PricingResponse; ts: number } | null = null

export function usePricing() {
  const tiers = ref<PricingResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async () => {
    // 使用内存缓存减少请求
    if (cached && Date.now() - cached.ts < PRICING_CACHE_TTL_MS) {
      tiers.value = cached.data
      return
    }
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/billing/pricing`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: PricingResponse = await res.json()
      cached = { data, ts: Date.now() }
      tiers.value = data
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  const getPrice = (tier: BillingTier, interval: BillingInterval): PriceItem | null => {
    return tiers.value?.tiers.find(t => t.tier === tier)?.[interval] ?? null
  }

  return { tiers, loading, error, load, getPrice }
}
```

---

## 3. Checkout 结账流程

### 3.1 流程图

```
前端 Vue Component
    │  POST /api/payment/create-checkout
    ▼
FastAPI Endpoint
    │  1. 读取用户 + 订阅状态
    │  2. 校验 unpaid 订单
    │  3. stripe.checkout.Session.create(...)
    ▼
Stripe Checkout Hosted Page
    │  用户本地语言 + 本地币种
    │  输入卡号 → 3DS / Apple Pay / Google Pay
    │   Stripe 自动处理 VAT/GST
    ▼
Checkout 完成
    │  success_url=/payment/success?session_id={CHECKOUT_SESSION_ID}
    │  cancel_url=/payment/cancel
    ▼
前端拉 session → 跳转仪表盘
    │
    │  Stripe 异步 Webhook 最终落库
    ▼
customer.subscription.created / invoice.paid
```

### 3.2 前端 Vue 组件

```typescript
// src/composables/useCheckout.ts
import { ref } from 'vue'
import axios from '@/plugins/axios'

type CheckoutParams = {
  tier: 'pro' | 'premium'
  interval: 'monthly' | 'annual'
  currency?: 'usd' | 'cny' | 'jpy' | 'eur' | 'gbp'
}

type CheckoutResult = {
  url: string                       // Stripe 托管页 URL
  sessionId?: string               // 也可用 id 跳转
}

export function useCheckout() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  const createCheckout = async (params: CheckoutParams): Promise<CheckoutResult> => {
    loading.value = true
    error.value = null
    try {
      const { data } = await axios.post('/api/payment/create-checkout', {
        tier: params.tier,
        interval: params.interval,
        currency: params.currency ?? 'usd',
      })
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const startCheckout = async (params: CheckoutParams) => {
    const { url } = await createCheckout(params)
    // 在 SPA 中直接 window.location.href 跳转最稳
    window.location.href = url
  }

  const redirectToStripeBySessionId = async (params: CheckoutParams) => {
    const stripe = await loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY)
    const { sessionId } = await createCheckout(params)
    await stripe!.redirectToCheckout({ sessionId })
  }

  return { loading, error, createCheckout, startCheckout, redirectToStripeBySessionId }
}
```

```vue
<!-- src/components/Pricing.vue -->
<script setup lang="ts">
import { onMounted } from 'vue'
import { usePricing } from '@/composables/usePricing'
import { useCheckout } from '@/composables/useCheckout'
import { useSession } from '@/composables/useSession'

const { tiers, load, loading: pricingLoading } = usePricing()
const { startCheckout, loading: checkoutLoading } = useCheckout()
const { user } = useSession()

onMounted(() => load())

const handleSubscribe = async (tier: 'pro' | 'premium', interval: 'monthly' | 'annual') => {
  if (!user.value) {
    // 未登录先跳转登录
    window.location.href = `/login?redirect=/pricing&tier=${tier}&interval=${interval}`
    return
  }
  await startCheckout({ tier, interval, currency: 'usd' })
}
</script>

<template>
  <div class="pricing-grid" v-if="!pricingLoading">
    <div
      v-for="tier in tiers?.tiers"
      :key="tier.tier"
      class="pricing-card"
      :class="{ recommended: tier.tier === 'pro' }"
    >
      <h2>{{ tier.name }}</h2>
      <p class="desc">{{ tier.description }}</p>
      <ul class="features">
        <li v-for="f in tier.features" :key="f">✓ {{ f }}</li>
      </ul>

      <button
        @click="handleSubscribe(tier.tier as 'pro' | 'premium', 'monthly')"
        :disabled="checkoutLoading || tier.tier === 'free'"
      >
        {{ tier.monthly?.displayAmount }}/mo
      </button>

      <button
        class="annual"
        @click="handleSubscribe(tier.tier as 'pro' | 'premium', 'annual')"
        :disabled="checkoutLoading || tier.tier === 'free'"
      >
        {{ tier.annual?.displayAmount }}/yr
        <span class="badge">省 {{ tier.annualDiscountPercent }}%</span>
      </button>
    </div>
  </div>
  <div v-else>加载中…</div>
</template>
```

### 3.3 后端 Checkout 端点

```python
# backend/api/payment.py
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import settings
from services.billing_service import BillingService
from db.session import get_db
from models.user import User
from schemas.payment import CheckoutRequest, CheckoutResponse
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/payment", tags=["payment"])

SUCCESS_URL = f"{settings.WEBHOOK_BASE_URL}/payment/session-complete?session_id={{CHECKOUT_SESSION_ID}}"
CANCEL_URL = f"{settings.WEBHOOK_BASE_URL}/payment/cancel"

@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user: User = await get_current_user(request, db)

    # 1. 支持免费套餐：直接建立本地订阅，无需走 Stripe
    if body.tier == "free":
        await BillingService(db).downgrade_to_free(user.id)
        return CheckoutResponse(url=f"{settings.WEBHOOK_BASE_URL}/payment/free-success")

    # 2. 检查是否已有 active subscription（避免重复下单）
    existing = await BillingService(db).get_active_subscription(user.id)
    if existing:
        raise HTTPException(409, detail="您已有一个活跃订阅，请先在订阅管理页面变更。")

    # 3. 查询 price_id 并校验币种匹配
    try:
        pricer = PRICER.for_currency(body.currency)
        price_id = pricer.get(tier=body.tier, interval=body.interval)
    except (AttributeError, ValueError) as e:
        raise HTTPException(400, detail=str(e))

    # 4. 创建 Stripe Customer（如未绑定）
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.id)},
        )
        await BillingService(db).set_stripe_customer(user.id, customer.id)

    # 5. 创建 Stripe Checkout Session
    try:
        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            customer_update={"address": "auto"},
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            payment_method_types=["card"],  # V2 再加 ideal/pix/alipay
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            automatic_tax={"enabled": True},
            subscription_data={
                "trial_period_days": settings.BILLING_TRIAL_DAYS,
                "metadata": {
                    "user_id": str(user.id),
                    "tier": body.tier,
                    "interval": body.interval,
                },
            },
            metadata={
                "user_id": str(user.id),
                "tier": body.tier,
                "interval": body.interval,
                "currency": body.currency,
            },
            locale="auto",  # Stripe 根据 IP/浏览器自动本地化
            allow_promotion_codes=True,
            billing_address_collection="required",
            tax_id_collection={"enabled": True},
            consent={"terms_of_service": "required"},
            custom_text={
                "submit": {"message": "支持 7 天免费试用，到期自动扣款。可提前随时取消。"},
                "shipping_address": {
                    "message": "账单地址仅用于税务核算，不会发送邮件。"
                },
            },
        )
    except stripe.error.StripeError as e:
        raise HTTPException(502, detail=f"Stripe 创建会话失败：{e.user_message}")

    return CheckoutResponse(url=session.url, sessionId=session.id)
```

```python
# backend/schemas/payment.py
from pydantic import BaseModel, Field
from enum import Enum

class TierEnum(str, Enum):
    free = "free"
    pro = "pro"
    premium = "premium"

class IntervalEnum(str, Enum):
    monthly = "monthly"
    annual = "annual"

class CheckoutRequest(BaseModel):
    tier: TierEnum = Field(..., description="订阅档位")
    interval: IntervalEnum = Field(..., description="月付或年付")
    currency: str = Field(default="usd", min_length=3, max_length=3, description="ISO 4217 币种")

class CheckoutResponse(BaseModel):
    url: str
    sessionId: str | None = None
```

### 3.4 `locale="auto"` 的 30+ 语言自动本地化

Stripe Checkout 根据 Accept-Language 与 IP 推断语言，已覆盖：
`en`, `zh`, `zh-HK`, `zh-TW`, `ja`, `ko`, `fr`, `de`, `es`, `it`, `pt`, `pt-BR`, `nl`, `pl`, `ru`, `ar`, `hi`, `sv`, `da`, `nb`, `fi`, `fil`, `el`, `id`, `ms`, `th`, `tr`, `vi`, `uk`, `he`, `bg`, `cs`, `ro`, `hu`, `sk`, `sl`, `lt`, `lv`, `et`

币种跟随语言：`zh` → `CNY`、`ja` → `JPY`、`en-US` → `USD`、`de` → `EUR`、`fr` → `EUR`。

### 3.5 Returning Customer 优化

```python
# Returning customer（试用过期或已取消）
if user.stripe_customer_id:
    # 检查最近 30 天内一次取消过 billing 历史，跳过 trial
    trials = await BillingService(db).recent_trial_count(user.id, days=30)
    if trials > 0:
        session_kwargs["subscription_data"]["trial_period_days"] = 0
    # 优惠码可用
    if body.coupon_code:
        session_kwargs["allow_promotion_codes"] = True
        session_kwargs["discounts"] = [{"coupon": body.coupon_code}]
```

---

## 4. Webhook 事件处理

### 4.1 签名校验与中间件

```python
# backend/api/webhook.py
import stripe
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import settings
from db.session import get_db
from services.event_processor import EventProcessor
from services.queue import enqueue

router = APIRouter()

@router.post("/api/webhook/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # 1. 校验签名（关键安全点，任何前端/第三方都能 POST）
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(401, detail="Invalid signature")
    except Exception as e:
        raise HTTPException(400, detail=f"Webhook error: {e}")

    # 2. 幂等性校验
    event_id = event.id
    if await EventProcessor(db).is_processed(event_id):
        return {"status": "skipped", "event_id": event_id}

    # 3. 立即 respond 200，再异步处理（Stripe 5s 超时）
    await enqueue("stripe.webhook", {
        "event_id": event_id,
        "event_type": event.type,
        "data": event.data.object,
    })

    # 4. 幂等记录
    await EventProcessor(db).mark_queued(event_id, event.type)

    return {"status": "received", "event_id": event_id}
```

### 4.2 幂等表 design

```sql
-- migrations/20260625001_processed_events.sql
CREATE TABLE processed_events (
    id              BIGSERIAL PRIMARY KEY,
    event_id        TEXT UNIQUE NOT NULL,          -- evt_xxx
    event_type      TEXT NOT NULL,                 -- invoice.paid
    status          TEXT NOT NULL DEFAULT 'queued', -- queued -> processed -> failed
    attempts        SMALLINT NOT NULL DEFAULT 0,
    payload         JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_processed_events_status ON processed_events (status, updated_at);
```

```python
# backend/services/event_processor.py
from sqlalchemy import update, select
from db.models.processed_events import ProcessedEvent
from services.billing_service import BillingService

class EventProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_processed(self, event_id: str) -> bool:
        row = await self.db.execute(
            select(ProcessedEvent(event_id).where(ProcessedEvent.event_id == event_id)
        )
        return row.scalar_one_or_none() is not None

    async def mark_queued(self, event_id: str, event_type: str):
        self.db.add(ProcessedEvent(event_id=event_id, event_type=event_type, status="queued"))
        await self.db.commit()

    async def mark_processed(self, event_id: str):
        await self.db.execute(
            update(ProcessedEvent)
            .where(ProcessedEvent.event_id == event_id)
            .values(status="processed", updated_at=func.now())
        )
        await self.db.commit()

    async def mark_failed(self, event_id: str, error: str):
        await self.db.execute(
            update(ProcessedEvent)
            .where(ProcessedEvent.event_id == event_id)
            .values(status="failed", error_message=error, updated_at=func.now())
        )
        await self.db.commit()
```

### 4.3 事件处理分发

```python
# backend/services/queue.py
import redis
import json

r = redis.from_url(settings.REDIS_URL)

async def enqueue(topic: str, payload: dict):
    r.lpush(f"queue:{topic}", json.dumps(payload))

# backend/workers/worker.py (Celery / ARQ 等)
async def dispatch(topic: str, payload: dict):
    event_type = payload["event_type"]
    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "customer.subscription.created": handle_subscription_created,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "customer.subscription.trial_will_end": handle_trial_will_end,
        "invoice.paid": handle_invoice_paid,
        "invoice.payment_failed": handle_invoice_payment_failed,
        "invoice.upcoming": handle_invoice_upcoming,
        "charge.refunded": handle_charge_refunded,
        "payment_intent.payment_failed": handle_payment_intent_failed,
        "customer.updated": handle_customer_updated,
        "payment_method.attached": handle_payment_method_attached,
    }
    handler = handlers.get(event_type)
    if handler:
        await handler(payload["data"])
```

### 4.4 关键 Handler 示例

```python
# backend/services/billing_events.py
from services.billing_service import BillingService
from services.email import EmailService
from services.receipt import ReceiptService
from sqlalchemy.ext.asyncio import AsyncSession

async def handle_subscription_created(stripe_sub, db: AsyncSession):
    svc = BillingService(db)
    user = await svc.get_user_by_customer(stripe_sub.customer)
    if not user:
        return
    await svc.upsert_subscription(
        user_id=user.id,
        stripe_subscription_id=stripe_sub.id,
        stripe_price_id=stripe_sub.plan.id,
        status=stripe_sub.status,
        current_period_start=stripe_sub.current_period_start,
        current_period_end=stripe_sub.current_period_end,
        cancel_at=stripe_sub.cancel_at,
        cancel_at_period_end=stripe_sub.cancel_at_period_end,
        trial_start=stripe_sub.trial_start,
        trial_end=stripe_sub.trial_end,
    )

async def handle_invoice_paid(stripe_invoice, db: AsyncSession):
    svc = BillingService(db)
    if not stripe_invoice.subscription:
        return  # 单笔订单暂不支持
    sub = await svc.get_subscription_by_stripe_id(stripe_invoice.subscription)
    if not sub:
        return
    # 落库 invoices 表
    await svc.record_invoice(
        subscription_id=sub.id,
        stripe_invoice_id=stripe_invoice.id,
        amount_paid=stripe_invoice.amount_paid,
        currency=stripe_invoice.currency,
        hosted_invoice_url=stripe_invoice.hosted_invoice_url,
        invoice_pdf=stripe_invoice.invoice_pdf,
        status="paid",
    )
    # 发送 PDF 回执
    user = await svc.get_by_id(sub.user_id)
    pdf = await ReceiptService.render(user, stripe_invoice)
    await EmailService.send_receipt(user.email, stripe_invoice, pdf)

async def handle_subscription_updated(stripe_sub, db: AsyncSession):
    svc = BillingService(db)
    await svc.sync_subscription_from_stripe(stripe_sub.id)
    # 如果是 upgrade 发给用户确认邮件
    metadata = stripe_sub.metadata or {}
    if metadata.get("action") == "upgrade":
        user = await svc.get_subscription_owner(stripe_sub.id)
        await EmailService.send_upgrade_confirmation(user.email, stripe_sub)
```

### 4.5 Webhook 失败重试

```python
# ARQ 任务 retry 设置
# worker.py
@task(retries=5, retry_delay=60)  # 5 次，60s/120s/240s/480s/960s 退避
async def handle_stripe_webhook(payload):
    event_id = payload["event_id"]
    try:
        await dispatch("stripe.webhook", payload)
        await EventProcessor(db).mark_processed(event_id)
    except Exception as e:
        await EventProcessor(db).mark_failed(event_id, str(e))
        raise
```

本地开发用 Stripe CLI：

```bash
stripe listen --forward-to localhost:8000/api/webhook/stripe
```

---

## 5. 订阅管理

### 5.1 升级与降级（含比例化费）

Stripe Subscription Schedule 或直接改 Subscription：

```python
# backend/services/billing_service.py
async def change_subscription_plan(self, user_id: int, new_price_id: str):
    """
    升档：立即生效，时间比例化。
    降档：当前周期结束后生效。
    """
    user = await self.get(user_id)
    current_sub = await self.get_active_subscription(user_id)
    if not current_sub:
        raise ValueError("无活跃订阅")

    is_upgrade = self._is_upgrade(new_price_id, current_sub.stripe_price_id)

    if is_upgrade:
        # 立即变更，时间比例化
        subscription = stripe.Subscription.modify(
            current_sub.stripe_subscription_id,
            items=[{"id": current_sub.stripe_item_id, "price": new_price_id}],
            proration_behavior="create_prorations",
            payment_behavior="default_incomplete",
            metadata={"action": "upgrade", "user_id": str(user_id)},
        )
    else:
        # 降档：在周期末尾生效
        subscription_schedule = stripe.SubscriptionSchedule.create(
            from_subscription=current_sub.stripe_subscription_id,
            phases=[
                {
                    "items": [{"price": current_sub.stripe_price_id, "quantity": 1}],
                    "start_date": current_sub.current_period_start,
                    "end_date": current_sub.current_period_end,
                },
                {
                    "items": [{"price": new_price_id, "quantity": 1}],
                    "start_date": current_sub.current_period_end,
                    "iterations": 1,
                },
            ],
        )
```

### 5.2 两步式取消

第一步：收集原因（GET / 打开 modal）；第二步：POST 取消。

```python
# backend/api/subscription.py
@router.post("/api/subscription/cancel-preview")
async def cancel_preview(user=Depends(get_current_user), db=Depends(get_db)):
    sub = await BillingService(db).get_active_subscription(user.id)
    if not sub:
        raise HTTPException(404, detail="无活跃订阅")

    # 计算退费金额（14 天内）
    paid_invoice = await BillingService(db).get_last_paid_invoice(sub.id)
    refund_amount = None
    if paid_invoice and (datetime.utcnow() - paid_invoice.created_at).days <= settings.BILLING_REFUND_DAYS:
        refund_amount = paid_invoice.amount_paid

    # 计算剩余有效期
    remaining_days = (sub.current_period_end - datetime.utcnow()).days

    return CancelPreviewResponse(
        tier=sub.tier,
        current_period_end=sub.current_period_end,
        remaining_days=remaining_days,
        refund_amount=refund_amount,
        refund_currency=sub.currency,
        reasons=[
            {"id": "too_expensive", "label": "价格太高"},
            {"id": "not_using", "label": "使用频率低"},
            {"id": "missing_feature", "label": "缺少需要的功能"},
            {"id": "switched", "label": "已切换到其他工具"},
            {"id": "other", "label": "其他"},
        ],
    )

@router.post("/api/subscription/cancel")
async def cancel(body: CancelRequest, user=Depends(get_current_user), db=Depends(get_db)):
    sub = await BillingService(db).get_active_subscription(user.id)
    if not body.immediate:
        # 周期末尾失效（保留使用到周期结束）
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=True,
            metadata={"cancel_reason": body.reason},
        )
        await EmailService.send_pending_cancellation(user.email, sub.current_period_end)
    else:
        # 立即失效
        stripe.Subscription.delete(
            sub.stripe_subscription_id,
            cancellation_details={"comment": body.reason, "feedback": body.reason},
        )
        await BillingService(db).mark_canceled(sub.id, immediate=True, reason=body.reason)
        # 同步发 refund（若 14 天内）
        last_inv = await BillingService(db).get_last_paid_invoice(sub.id)
        if last_inv and (datetime.utcnow() - last_inv.created_at).days <= settings.BILLING_REFUND_DAYS:
            stripe.Refund.create(charge=last_inv.stripe_charge_id)

    await EmailService.send_cancellation_confirmed(user.email)
    return {"status": "canceled"}
```

```typescript
// src/composables/useSubscription.ts
import { ref } from 'vue'
import axios from '@/plugins/axios'

export function useSubscription() {
  const loading = ref(false)

  const cancelPreview = () => axios.post('/api/subscription/cancel-preview').then(r => r.data)

  const cancel = (immediate: boolean, reason: string) => {
    loading.value = true
    return axios.post('/api/subscription/cancel', { immediate, reason })
  }

  const changePrice = (tier: 'pro' | 'premium', interval: 'monthly' | 'annual') =>
    axios.post('/api/subscription/change', { tier, interval })

  return { loading, cancelPreview, cancel, changePrice }
}
```

```vue
<!-- src/components/CancelSubscriptionModal.vue -->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSubscription } from '@/composables/useSubscription'

const emit = defineEmits<{ (e: 'close'): void }>()
const { cancelPreview, cancel, loading } = useSubscription()

const step = ref<'reason' | 'confirm'>('reason')
const selectedReason = ref('')
const immediate = ref(false)
const preview = ref<any>(null)
const reasons = computed(() => preview.value?.reasons ?? [])

const next = async () => {
  preview.value = await cancelPreview()
  step.value = 'confirm'
}

const confirm = async () => {
  await cancel(immediate.value, selectedReason.value)
  emit('close')
}
</script>

<template>
  <div class="modal-backdrop">
    <div class="modal">
      <template v-if="step === 'reason'">
        <h2>很抱歉你决定离开</h2>
        <p>请告诉我们原因（可选）：</p>
        <label v-for="r in [
          { id: 'too_expensive', label: '价格太高' },
          { id: 'not_using', label: '使用频率低' },
          { id: 'missing_feature', label: '缺少功能' },
          { id: 'switched', label: '已换用其他工具' },
          { id: 'other', label: '其他' },
        ]" :key="r.id">
          <input type="radio" v-model="selectedReason" :value="r.id"> {{ r.label }}
        </label>
        <button @click="next" :disabled="!selectedReason">下一步</button>
      </template>

      <template v-else>
        <h2>确认取消</h2>
        <p>剩余有效期：{{ preview.remaining_days }} 天</p>
        <p v-if="preview.refund_amount">将获得 {{ preview.refund_currency }} {{ preview.refund_amount / 100 }} 退款</p>
        <label><input type="checkbox" v-model="immediate"> 立即取消（否则在 {{ preview.current_period_end }} 失效）</label>
        <button class="danger" @click="confirm" :disabled="loading">确认取消订阅</button>
      </template>
    </div>
  </div>
</template>
```

### 5.3 7 天免费试用

```python
# 在 Checkout 中已配置 trial_period_days=7
# 试用到期前 3 天发提醒邮件
async def handle_trial_will_end(stripe_sub, db):
    user = await BillingService(db).get_subscription_owner(stripe_sub.id)
    await EmailService.send_trial_ending_reminder(
        user.email,
        trial_end=stripe_sub.trial_end,
        plan=stripe_sub.plan.id,
    )
```

### 5.4 暂停 (V2)

```python
# 暂停 1-3 个月，期间不扣费
stripe.Subscription.modify(
    sub_id,
    pause_collection={"behavior": "void", "resumes_at": int(resume_ts)},
)
```

### 5.5 取消后留存

- 数据保留 30 天，期间用户可重新订阅恢复
- 30 天后自动软删除（GDPR 合规）
- 发送「我们想念你」邮件序列（Day 1 / Day 7 / Day 21）

---

## 6. PDF 回执自渲染

### 6.1 技术选型

- **reportlab**：Python 原生 PDF 渲染，无外部依赖
- **weasyprint**：HTML → PDF（复杂排版更灵活，但依赖 GTK/Pango）
- 本项目选 **reportlab**（轻量、Docker 镜像小）

```bash
pip install reportlab
```

### 6.2 模板设计

```
┌──────────────────────────────────────────────┐
│  [Logo]         Video Summary, Inc.          │
│                 123 Market St, Suite 400     │
│                 San Francisco, CA 94103       │
│                 US EIN: XX-XXXXXXX           │
├──────────────────────────────────────────────┤
│  Bill To:                                    │
│   张三 (zhangsan@example.com)                │
│   Stripe Customer: cus_XXXXXXX               │
├──────────────────────────────────────────────┤
│  Invoice ID: in_XXXXXXXXXXXXXXXX             │
│  Date: 2026-06-25                            │
│  Billing Period: 2026-05-25 → 2026-06-25     │
├──────────────────────────────────────────────┤
│  Description              Qty   Amount       │
│  Pro Plan (Monthly)        1    $7.99        │
│  ─────────────────────────────────────────── │
│  Subtotal                       $7.99        │
│  VAT (20%)                      $1.60        │
│  Total                         $9.59         │
├──────────────────────────────────────────────┤
│  Payment Method: Visa **** 4242              │
│  Transaction ID: txn_XXXXXXXXXXXXXXXX        │
│  Status: PAID                                │
├──────────────────────────────────────────────┤
│  This receipt is generated by Video Summary. │
│  For questions: billing@videosummary.com     │
└──────────────────────────────────────────────┘
```

### 6.3 渲染实现

```python
# backend/services/receipt.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from config.settings import settings

# 注册中文字体（Noto Sans CJK）
pdfmetrics.registerFont(TTFont('NotoSansCJK', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'))
pdfmetrics.registerFont(TTFont('NotoSansCJKBold', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'))

class ReceiptService:
    @staticmethod
    async def render(user, stripe_invoice) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='CN', fontName='NotoSansCJK', fontSize=10, leading=14))
        styles.add(ParagraphStyle(name='CN-Bold', fontName='NotoSansCJKBold', fontSize=10, leading=14))

        story = []

        # Header
        story.append(Paragraph("Video Summary, Inc.", styles['CN-Bold']))
        story.append(Paragraph("123 Market St, Suite 400<br/>San Francisco, CA 94103", styles['CN']))
        story.append(Paragraph(f"EIN: {settings.COMPANY_EIN}", styles['CN']))
        story.append(Spacer(1, 10*mm))

        # Bill To
        story.append(Paragraph("Bill To:", styles['CN-Bold']))
        story.append(Paragraph(f"{user.name or user.email}<br/>{user.email}", styles['CN']))
        story.append(Paragraph(f"Stripe Customer: {stripe_invoice.customer}", styles['CN']))
        story.append(Spacer(1, 8*mm))

        # Invoice meta
        story.append(Paragraph(f"Invoice ID: {stripe_invoice.id}", styles['CN']))
        story.append(Paragraph(f"Date: {stripe_invoice.created.strftime('%Y-%m-%d')}", styles['CN']))
        story.append(Spacer(1, 8*mm))

        # Line items table
        data = [["Description", "Qty", "Amount"]]
        for line in stripe_invoice.lines.data:
            data.append([
                line.description,
                str(line.quantity),
                f"{line.amount / 100:.2f} {line.currency.upper()}",
            ])
        data.append(["", "", ""])
        data.append(["Subtotal", "", f"{stripe_invoice.subtotal / 100:.2f} {stripe_invoice.currency.upper()}"])
        if stripe_invoice.tax:
            data.append(["Tax", "", f"{stripe_invoice.tax / 100:.2f} {stripe_invoice.currency.upper()}"])
        data.append(["Total", "", f"{stripe_invoice.total / 100:.2f} {stripe_invoice.currency.upper()}"])

        table = Table(data, colWidths=[80*mm, 30*mm, 60*mm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'NotoSansCJK'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e5e7eb')),
        ]))
        story.append(table)
        story.append(Spacer(1, 10*mm))

        # Payment method
        story.append(Paragraph(f"Payment Method: {stripe_invoice.payment_method_types}", styles['CN']))
        story.append(Paragraph(f"Transaction ID: {stripe_invoice.charge}", styles['CN']))
        story.append(Paragraph("Status: PAID", styles['CN-Bold']))
        story.append(Spacer(1, 10*mm))

        # Footer
        story.append(Paragraph("This receipt is generated by Video Summary.", styles['CN']))
        story.append(Paragraph("For questions: billing@videosummary.com", styles['CN']))

        doc.build(story)
        buffer.seek(0)
        return buffer.read()
```

### 6.4 多语言模板

```python
# backend/services/receipt_i18n.py
TRANSLATIONS = {
    "en": {
        "bill_to": "Bill To",
        "invoice_id": "Invoice ID",
        "date": "Date",
        "subtotal": "Subtotal",
        "tax": "Tax",
        "total": "Total",
        "payment_method": "Payment Method",
        "transaction_id": "Transaction ID",
        "status_paid": "PAID",
        "footer": "This receipt is generated by Video Summary.",
    },
    "zh": {
        "bill_to": "收票方",
        "invoice_id": "发票编号",
        "date": "日期",
        "subtotal": "小计",
        "tax": "税费",
        "total": "合计",
        "payment_method": "支付方式",
        "transaction_id": "交易编号",
        "status_paid": "已支付",
        "footer": "本回执由 Video Summary 自动生成。",
    },
    "ja": {
        "bill_to": "請求先",
        "invoice_id": "請求書番号",
        "date": "日付",
        "subtotal": "小計",
        "tax": "税額",
        "total": "合計",
        "payment_method": "支払方法",
        "transaction_id": "取引ID",
        "status_paid": "支払済",
        "footer": "この領収書は Video Summary により自動生成されました。",
    },
}

def t(key: str, locale: str = "en") -> str:
    return TRANSLATIONS.get(locale, TRANSLATIONS["en"]).get(key, key)
```

### 6.5 Brevo 邮件附件

```python
# backend/services/email.py
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from config.settings import settings

class EmailService:
    @staticmethod
    async def send_receipt(to_email: str, stripe_invoice, pdf_bytes: bytes):
        config = sib_api_v3_sdk.Configuration()
        config.api_key['api-key'] = settings.BREVO_API_KEY

        api = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(config))

        # Base64 编码 PDF
        import base64
        b64 = base64.b64encode(pdf_bytes).decode()

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            template_id=settings.BREVO_RECEIPT_TEMPLATE_ID,
            params={
                "invoice_id": stripe_invoice.id,
                "amount": f"{stripe_invoice.total / 100:.2f}",
                "currency": stripe_invoice.currency.upper(),
                "date": stripe_invoice.created.strftime("%Y-%m-%d"),
            },
            attachment=[
                {
                    "name": f"receipt-{stripe_invoice.id}.pdf",
                    "content": b64,
                }
            ],
        )

        try:
            api.send_transmtp_email(send_smtp_email)
        except ApiException as e:
            # 记录但不阻塞主流程
            logger.error(f"Brevo send failed: {e}")
```

---

## 7. 税务处理

### 7.1 Stripe Tax 自动征收

Stripe Tax 根据：
- 客户 IP 地址
- 账单地址
- 卡BIN 国家
- 客户提供的 tax_id

自动判定税率，覆盖：
- **EU VAT**：标准税率 17-27%（德国 19%、法国 20%、意大利 22%）
- **UK VAT**：20%
- **GST**：澳大利亚 10%、新加坡 9%、新西兰 15%
- **US Sales Tax**：各州不同（加州 7.25%、纽约 8%、得州 6.25%）
- **Japan Consumption Tax**：10%

### 7.2 启用配置

```python
# 在 Checkout Session 中
session = stripe.checkout.Session.create(
    ...
    automatic_tax={"enabled": True},
    customer_update={"address": "auto"},
    billing_address_collection="required",
    tax_id_collection={"enabled": True},
)

# 在 Customer 中
stripe.Customer.modify(
    customer_id,
    address={"line1": "...", "city": "...", "country": "DE", "postal_code": "..."},
    metadata={"tax_id": "DE123456789"},
)
```

### 7.3 费率

- **Stripe Tax 费率**：每笔交易 **0.5%**（最低 $0.5）
- **美国卡组织**：部分州 0.4%
- 合计约 **0.5-0.9%**，远低于自己注册 VAT 的合规成本

### 7.4 Dashboard 报告

Stripe Dashboard → Tax → Reports 可导出：
- 各国 VAT 汇总（用于 VAT OSS 申报）
- US Sales Tax nexus 报告
- GST 报告

```python
# 月度税务汇总 API
@router.get("/api/admin/tax/summary")
async def tax_summary(month: str, db=Depends(get_db)):
    rows = await db.execute(
        """
        SELECT currency, tax_country, SUM(tax_amount) as total_tax, COUNT(*) as cnt
        FROM invoices
        WHERE DATE_TRUNC('month', created_at) = :month
        GROUP BY currency, tax_country
        """,
        {"month": month},
    )
    return [dict(r) for r in rows]
```

### 7.5 日本特定商取引法

- 必须显示「事業者名称」「住所」「電話番号」「販売価格」「支払方法」
- 返品条件明示
- 在 Footer 与 /legal 页面展示

---

## 8. 多币种支持

### 8.1 默认 USD，按 locale 映射

```python
# backend/config/currency.py
LOCALE_TO_CURRENCY = {
    "en": "USD",
    "en-US": "USD",
    "en-GB": "GBP",
    "en-CA": "CAD",
    "en-AU": "AUD",
    "zh": "CNY",
    "zh-CN": "CNY",
    "zh-HK": "HKD",
    "zh-TW": "TWD",
    "ja": "JPY",
    "ko": "KRW",
    "de": "EUR",
    "de-AT": "EUR",
    "de-CH": "CHF",
    "fr": "EUR",
    "fr-CA": "CAD",
    "es": "EUR",
    "es-MX": "MXN",
    "it": "EUR",
    "pt": "EUR",
    "pt-BR": "BRL",
    "nl": "EUR",
    "pl": "PLN",
    "ru": "RUB",
    "ar": "SAR",
    "hi": "INR",
    "id": "IDR",
    "ms": "MYR",
    "th": "THB",
    "vi": "VND",
    "tr": "TRY",
    "uk": "UAH",
    "he": "ILS",
    "bg": "BGN",
    "cs": "CZK",
    "ro": "RON",
    "hu": "HUF",
    "sk": "EUR",
    "sl": "EUR",
    "lt": "EUR",
    "lv": "EUR",
    "et": "EUR",
    "da": "DKK",
    "sv": "SEK",
    "nb": "NOK",
    "fi": "EUR",
    "el": "EUR",
    "fil": "PHP",
}

def currency_for_locale(locale: str) -> str:
    return LOCALE_TO_CURRENCY.get(locale, "USD")
```

### 8.2 用户手动切换

```typescript
// src/composables/useCurrency.ts
import { ref, watch } from 'vue'
import type { CurrencyCode } from '@/types/billing'

const CURRENCIES: { code: CurrencyCode; label: string; symbol: string }[] = [
  { code: 'usd', label: 'USD - US Dollar', symbol: '$' },
  { code: 'cny', label: 'CNY - Chinese Yuan', symbol: '¥' },
  { code: 'jpy', label: 'JPY - Japanese Yen', symbol: '¥' },
  { code: 'eur', label: 'EUR - Euro', symbol: '€' },
  { code: 'gbp', label: 'GBP - British Pound', symbol: '£' },
  { code: 'cad', label: 'CAD - Canadian Dollar', symbol: 'CA$' },
  { code: 'aud', label: 'AUD - Australian Dollar', symbol: 'A$' },
  { code: 'hkd', label: 'HKD - Hong Kong Dollar', symbol: 'HK$' },
  { code: 'sgd', label: 'SGD - Singapore Dollar', symbol: 'S$' },
  { code: 'krw', label: 'KRW - Korean Won', symbol: '₩' },
  { code: 'inr', label: 'INR - Indian Rupee', symbol: '₹' },
  { code: 'brl', label: 'BRL - Brazilian Real', symbol: 'R$' },
]

export function useCurrency() {
  const stored = localStorage.getItem('vs_currency') as CurrencyCode | null
  const currency = ref<CurrencyCode>(stored || 'usd')

  watch(currency, (v) => localStorage.setItem('vs_currency', v))

  const setCurrency = (c: CurrencyCode) => { currency.value = c }

  return { currency, setCurrency, CURRENCIES }
}
```

```vue
<!-- src/components/CurrencySelector.vue -->
<script setup lang="ts">
import { useCurrency } from '@/composables/useCurrency'

const { currency, setCurrency, CURRENCIES } = useCurrency()
</script>

<template>
  <select :value="currency" @change="setCurrency(($event.target as HTMLSelectElement).value as any)">
    <option v-for="c in CURRENCIES" :key="c.code" :value="c.code">
      {{ c.label }}
    </option>
  </select>
</template>
```

### 8.3 后端按币种查 Price

```python
# backend/services/pricing.py
class Pricer:
    def __init__(self, currency: str):
        self.currency = currency.lower()

    def get(self, tier: str, interval: str) -> str:
        key = f"STRIPE_PRICE_{tier.upper()}_{interval.upper()}_{self.currency.upper()}"
        val = os.getenv(key)
        if not val:
            # fallback USD
            val = os.getenv(f"STRIPE_PRICE_{tier.upper()}_{interval.upper()}_USD")
        if not val:
            raise ValueError(f"No price configured for {tier}/{interval}/{self.currency}")
        return val
```

---

## 9. Dunning 催款流程

### 9.1 流程

```
invoice.payment_failed
    │
    ├─ Attempt 1 (Day 0): 立即发友好邮件
    ├─ Attempt 2 (Day 3): 提醒 + 提供更新支付方式链接
    ├─ Attempt 3 (Day 5): 严肃提醒 + 告知将暂停服务
    └─ Attempt 4 (Day 7): 最终通知 + 暂停订阅
```

### 9.2 状态机

```python
# backend/models/dunning.py
class DunningStatus(str, Enum):
    pending = "pending"
    email_sent = "email_sent"
    resolved = "resolved"        # 用户补款成功
    suspended = "suspended"      # 超过重试次数
    canceled = "canceled"        # 最终取消

class DunningRecord(Base):
    __tablename__ = "dunning_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    stripe_invoice_id = Column(String(255), unique=True)
    attempt = Column(SmallInteger, default=0)
    status = Column(Enum(DunningStatus), default=DunningStatus.pending)
    next_retry_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### 9.3 队列任务

```python
# backend/workers/dunning.py
from datetime import datetime, timedelta

DUNNING_SCHEDULE = [0, 3, 5, 7]  # days after failure

@task
async def process_dunning(invoice_id: str):
    db = get_db()
    record = await DunningService(db).get_by_invoice(invoice_id)
    if not record or record.status in (DunningStatus.resolved, DunningStatus.canceled):
        return

    if record.attempt >= len(DUNNING_SCHEDULE):
        # 超过重试次数：暂停订阅
        await DunningService(db).suspend_subscription(record.subscription_id)
        record.status = DunningStatus.suspended
        await db.commit()
        return

    days = DUNNING_SCHEDULE[record.attempt]
    if datetime.utcnow() < record.next_retry_at:
        return  # 还没到时间

    # 发邮件
    user = await DunningService(db).get_user(record.user_id)
    await EmailService.send_dunning_email(
        to=user.email,
        attempt=record.attempt + 1,
        max_attempts=len(DUNNING_SCHEDULE),
        update_url=f"{settings.WEBHOOK_BASE_URL}/billing/payment-method?user_id={user.id}",
    )
    record.attempt += 1
    record.next_retry_at = datetime.utcnow() + timedelta(days=1)
    record.status = DunningStatus.email_sent
    await db.commit()

    # 调度下一次
    if record.attempt < len(DUNNING_SCHEDULE):
        process_dunning.apply_async(
            args=[invoice_id],
            countdown=DUNNING_SCHEDULE[record.attempt] * 86400,
        )
```

### 9.4 友好邮件模板

```python
# backend/services/email_templates/dunning.html (Jinja2)
DUNNING_TEMPLATES = {
    1: {
        "subject": "您的付款遇到问题 - Video Summary",
        "body": """
            <p>Hi {{ user.name }},</p>
            <p>我们尝试处理您的订阅付款但没有成功。可能是卡片过期或余额不足。</p>
            <p>请 <a href="{{ update_url }}">点击此处更新支付方式</a>，您的服务不会受影响。</p>
            <p>如有疑问，回复此邮件即可。</p>
        """
    },
    2: {
        "subject": "付款再次失败 - 请更新支付方式",
        "body": """
            <p>Hi {{ user.name }},</p>
            <p>我们再次尝试扣款失败。为避免服务中断，请尽快更新支付方式。</p>
            <p><a href="{{ update_url }}">更新支付方式</a></p>
        """
    },
    3: {
        "subject": "重要：您的订阅即将暂停",
        "body": """
            <p>Hi {{ user.name }},</p>
            <p>这是最后一次提醒。如不更新支付方式，您的订阅将在 24 小时后暂停。</p>
            <p>您的数据将保留 30 天，期间可随时恢复。</p>
            <p><a href="{{ update_url }}">立即更新</a></p>
        """
    },
}
```

### 9.5 Stripe Customer Portal 集成

```python
# 用户自助更新支付方式
@router.post("/api/billing/portal")
async def create_portal_session(user=Depends(get_current_user), db=Depends(get_db)):
    if not user.stripe_customer_id:
        raise HTTPException(400, detail="无 Stripe 客户记录")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.WEBHOOK_BASE_URL}/dashboard",
    )
    return {"url": session.url}
```

---

## 10. 本地支付方式 (V2)

### 10.1 支付方式矩阵

| 方式 | 国家/地区 | 适用场景 | 激活条件 |
|------|-----------|----------|----------|
| iDEAL | 荷兰 | 荷兰用户首选 | 荷兰 IP 或 locale=nl |
| PIX | 巴西 | 巴西即时支付 | 巴西 IP 或 locale=pt-BR |
| Alipay | 中国 | 中国用户 | 中国 IP 或 locale=zh-CN |
| WeChat Pay | 中国 | 中国用户 | 中国 IP 或 locale=zh-CN |
| Bancontact | 比利时 | 比利时 | 比利时 IP |
| EPS | 奥地利 | 奥地利 | 奥地利 IP |
| Giropay | 德国 | 德国 | 德国 IP |
| P24 | 波兰 | 波兰 | 波兰 IP |

### 10.2 激活条件

```python
# backend/services/payment_methods.py
def get_payment_methods_for_request(locale: str, ip_country: str) -> list[str]:
    methods = ["card"]  # 始终支持卡

    country = ip_country.upper()
    lc = locale.lower()

    if country == "NL" or lc.startswith("nl"):
        methods.append("ideal")
    if country == "BE" or lc.startswith("be"):
        methods.append("bancontact")
    if country == "AT" or lc.startswith("at"):
        methods.append("eps")
    if country == "DE" or lc.startswith("de"):
        methods.append("giropay")
    if country == "PL" or lc.startswith("pl"):
        methods.append("p24")
    if country == "BR" or lc == "pt-br":
        methods.append("pix")
    if country == "CN" or lc.startswith("zh"):
        methods.extend(["alipay", "wechat_pay"])

    return methods
```

### 10.3 Checkout 集成

```python
# 在 create_checkout 中
payment_method_types = get_payment_methods_for_request(
    locale=body.locale,
    ip_country=request.headers.get("cf-ipcountry", "US"),
)

session = stripe.checkout.Session.create(
    ...
    payment_method_types=payment_method_types,
    ...
)
```

### 10.4 Stripe 激活步骤

1. Dashboard → Settings → Payment methods → Activate
2. 每种方式单独激活，部分需要提供业务信息
3. Alipay/WeChat 需要中国大陆实体（或 Stripe Partner）
4. 测试模式用 Stripe 测试卡号 + 本地方式测试账号

---

## 11. 退款政策

### 11.1 欧盟 14 天无条件退款

根据 EU Consumer Rights Directive 2011/83/EU：
- 数字商品购买后 14 天内可无条件退款
- 例外：用户明确同意放弃（如已使用超过阈值）
- 本产品在 14 天内一律退款，不询问原因

### 11.2 退款 API

```python
# backend/api/refund.py
@router.post("/api/admin/refund")
async def admin_refund(
    body: AdminRefundRequest,
    admin=Depends(get_admin_user),
    db=Depends(get_db),
):
    # 1. 查找 invoice
    invoice = await BillingService(db).get_invoice(body.invoice_id)
    if not invoice:
        raise HTTPException(404, detail="Invoice not found")

    # 2. 校验 14 天内
    if (datetime.utcnow() - invoice.created_at).days > settings.BILLING_REFUND_DAYS:
        raise HTTPException(400, detail="超过 14 天退款期")

    # 3. 调用 Stripe Refund
    refund = stripe.Refund.create(
        charge=invoice.stripe_charge_id,
        amount=body.amount,  # 部分退款支持
        reason="requested_by_customer",
        metadata={"admin_id": str(admin.id), "reason": body.reason},
    )

    # 4. 更新订阅状态
    await BillingService(db).mark_refunded(invoice.id, refund.id)

    # 5. 取消订阅（立即）
    await BillingService(db).cancel_subscription(invoice.subscription_id, immediate=True)

    # 6. 发送退款确认邮件
    user = await BillingService(db).get_user(invoice.user_id)
    await EmailService.send_refund_confirmation(user.email, refund)

    return {"refund_id": refund.id, "status": refund.status}
```

### 11.3 用户自助退款（VIP 通道）

```python
@router.post("/api/subscription/self-refund")
async def self_refund(user=Depends(get_current_user), db=Depends(get_db)):
    """VIP 用户 14 天内自助退款，无需联系客服"""
    sub = await BillingService(db).get_active_subscription(user.id)
    if not sub:
        raise HTTPException(404, detail="无活跃订阅")

    last_inv = await BillingService(db).get_last_paid_invoice(sub.id)
    if not last_inv:
        raise HTTPException(400, detail="无付费记录")

    if (datetime.utcnow() - last_inv.created_at).days > settings.BILLING_REFUND_DAYS:
        raise HTTPException(400, detail="超过 14 天退款期")

    # 立即退款 + 取消
    refund = stripe.Refund.create(charge=last_inv.stripe_charge_id)
    await BillingService(db).cancel_subscription(sub.id, immediate=True)
    await EmailService.send_refund_confirmation(user.email, refund)

    return {"refund_id": refund.id, "status": "refunded"}
```

### 11.4 退款状态同步

```python
async def handle_charge_refunded(stripe_charge, db):
    invoice = await BillingService(db).get_invoice_by_charge(stripe_charge.id)
    if invoice:
        await BillingService(db).mark_refunded(invoice.id, stripe_charge.refund.data[0].id)
```

---

## 12. 上线检查清单

### 12.1 账户与配置

- [ ] Stripe 账户完成验证（Identity verification）
- [ ] 公司信息填写完整（名称、地址、EIN、VAT ID）
- [ ] Dashboard 品牌设置（Logo、Statement descriptor、Support info）
- [ ] API 密钥切换到 Live 模式
- [ ] Webhook 端点注册并验证签名
- [ ] Stripe Tax 启用
- [ ] 邮件服务（Brevo）配置并验证 SPF/DKIM/DMARC

### 12.2 产品与价格

- [ ] Free / Pro / Premium 三个产品创建
- [ ] 每个产品 Monthly + Annual 价格创建
- [ ] 价格 ID 写入环境变量
- [ ] 心理定价核对（$7.99 / $14.99 / $59.99 / $119.99）
- [ ] 年付折扣核对（40% OFF）

### 12.3 Checkout 流程

- [ ] 未登录用户跳转登录页
- [ ] 已订阅用户提示去管理页
- [ ] `locale="auto"` 本地化验证（中/英/日/德）
- [ ] `automatic_tax` 启用验证
- [ ] `success_url` / `cancel_url` 跳转正确
- [ ] 7 天试用生效
- [ ] 优惠码可用
- [ ] 3DS 验证通过（测试卡 4242 4242 4242 4242）
- [ ] 失败卡（4000 0000 0000 0002）正确提示

### 12.4 Webhook

- [ ] 签名校验（错误签名返回 401）
- [ ] 幂等性（重复事件不重复处理）
- [ ] 超时保护（5s 内返回 200）
- [ ] 失败重试（5 次退避）
- [ ] 所有事件类型覆盖
- [ ] Stripe CLI 本地测试通过

### 12.5 订阅管理

- [ ] 升级立即生效 + 时间比例化
- [ ] 降档周期末生效
- [ ] 两步取消流程
- [ ] 取消原因收集
- [ ] 14 天内退款
- [ ] 试用到期前 3 天提醒
- [ ] 暂停功能（V2）
- [ ] Customer Portal 跳转

### 12.6 PDF 回执

- [ ] 中文字体渲染正常
- [ ] 日文/韩文渲染正常
- [ ] 金额计算准确
- [ ] 税务明细显示
- [ ] Brevo 邮件附件发送成功
- [ ] 回执下载链接可用

### 12.7 税务

- [ ] EU VAT 自动征收（测试各国）
- [ ] US Sales Tax 自动征收
- [ ] Japan Consumption Tax 10%
- [ ] Tax ID 收集（VAT/GST）
- [ ] 月度税务报告导出

### 12.8 多币种

- [ ] 默认 USD
- [ ] locale → currency 映射正确
- [ ] 用户手动切换持久化
- [ ] 各币种 Price ID 配置

### 12.9 Dunning

- [ ] payment_failed 触发
- [ ] 3/5/7 天重试
- [ ] 友好邮件发送
- [ ] 超过重试暂停订阅
- [ ] 用户补款后恢复
- [ ] Customer Portal 链接可用

### 12.10 本地支付 (V2)

- [ ] iDEAL 测试通过
- [ ] PIX 测试通过
- [ ] Alipay 测试通过
- [ ] WeChat Pay 测试通过
- [ ] 支付方式按地区显示

### 12.11 安全与合规

- [ ] API 密钥不暴露在前端
- [ ] Webhook 签名校验
- [ ] HTTPS 强制
- [ ] CSP 头配置
- [ ] GDPR 数据处理协议
- [ ] 隐私政策更新
- [ ] 服务条款更新
- [ ] Cookie 同意横幅

### 12.12 监控与告警

- [ ] Stripe 错误率监控
- [ ] Webhook 失败告警
- [ ] 订阅变更事件日志
- [ ] 收入日报（MRR/ARR/Churn）
- [ ] 异常大额订单告警
- [ ] 支付成功率监控

### 12.13 测试卡号

| 卡号 | 场景 |
|------|------|
| 4242 4242 4242 4242 | 成功（Visa）|
| 4000 0000 0000 3220 | 3DS 2 要求 |
| 4000 0000 0000 0002 | 通用失败 |
| 4000 0000 0000 9995 | 余额不足 |
| 4000 0000 0000 0069 | 过期卡 |
| 4000 0000 0000 0127 | CVC 失败 |

### 12.14 上线前最终验证

```bash
# 1. 冒烟测试脚本
python -m pytest tests/payment/test_checkout.py -v
python -m pytest tests/payment/test_webhook.py -v
python -m pytest tests/payment/test_subscription.py -v

# 2. 前端 E2E
npx playwright test tests/e2e/checkout.spec.ts
npx playwright test tests/e2e/subscription.spec.ts

# 3. 负载测试
k6 run --vus 50 --duration 5m tests/load/checkout.js

# 4. 安全扫描
npx owasp-zap scan https://api.videosummary.com
```

---

## 附录 A：数据库 Schema

```sql
-- 用户表扩展字段
ALTER TABLE users ADD COLUMN stripe_customer_id TEXT UNIQUE;
ALTER TABLE users ADD COLUMN locale TEXT DEFAULT 'en';
ALTER TABLE users ADD COLUMN currency TEXT DEFAULT 'usd';

-- 订阅表
CREATE TABLE subscriptions (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT NOT NULL REFERENCES users(id),
    stripe_customer_id      TEXT NOT NULL,
    stripe_subscription_id  TEXT UNIQUE,
    stripe_price_id         TEXT,
    tier                    TEXT NOT NULL,          -- free/pro/premium
    status                  TEXT NOT NULL,          -- active/trialing/past_due/canceled
    interval                TEXT NOT NULL,          -- monthly/annual
    currency                TEXT NOT NULL DEFAULT 'usd',
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    cancel_at               TIMESTAMPTZ,
    cancel_at_period_end    BOOLEAN NOT NULL DEFAULT FALSE,
    trial_start             TIMESTAMPTZ,
    trial_end               TIMESTAMPTZ,
    canceled_at             TIMESTAMPTZ,
    cancel_reason           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user ON subscriptions (user_id);
CREATE INDEX idx_subscriptions_stripe ON subscriptions (stripe_subscription_id);

-- 发票表
CREATE TABLE invoices (
    id                      BIGSERIAL PRIMARY KEY,
    subscription_id         BIGINT NOT NULL REFERENCES subscriptions(id),
    stripe_invoice_id      TEXT UNIQUE NOT NULL,
    stripe_charge_id        TEXT,
    amount_paid             INTEGER NOT NULL,       -- 最小单位（分）
    currency                TEXT NOT NULL,
    tax_amount              INTEGER DEFAULT 0,
    tax_country             TEXT,
    status                  TEXT NOT NULL,          -- paid/open/uncollectible/void
    hosted_invoice_url      TEXT,
    invoice_pdf             TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dunning 表（见 9.2 节）
-- processed_events 表（见 4.2 节）
```

## 附录 B：关键依赖

```txt
# backend/requirements.txt
stripe>=7.0.0
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
redis>=5.0.0
arq>=0.26.0
reportlab>=4.0.0
sib-api-v3-sdk>=7.6.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-jose[cryptography]>=3.3.0
```

```json
// frontend/package.json (节选)
{
  "dependencies": {
    "@stripe/stripe-js": "^3.0.0",
    "axios": "^1.6.0",
    "vue": "^3.4.0",
    "pinia": "^2.1.0"
  }
}
```

## 附录 C：监控指标

| 指标 | 告警阈值 | 数据源 |
|------|----------|--------|
| 支付成功率 | < 95% | Stripe Dashboard |
| Webhook 失败率 | > 1% | 应用日志 |
| MRR 周环比 | < -5% | 内部报表 |
| Churn Rate | > 5%/月 | 内部报表 |
| 平均退款率 | > 3% | Stripe Dashboard |
| Dunning 恢复率 | < 30% | 内部报表 |
| Checkout 转化率 | < 2% | 漏斗分析 |

---

> **文档维护说明**：本文档随产品迭代持续更新。重大变更（如新币种、新支付方式、价格调整）需在 PR 中同步更新本文档。
> 
> **联系方式**：billing-team@videosummary.com
