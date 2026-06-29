# 安全策略规范

> 版权合规、GDPR、速率限制、输入校验、Webhook 安全。这是项目法律风险的根基,上线前必须全部通过。

---

## 一、版权与 DMCA 合规

### 1.1 核心原则

**不持久化视频文件** — 这是所有法律风险的根基:

- 用户提交 URL → 服务器下载到临时目录 → 提取字幕/转录 → 生成 AI 总结 → **立即删除视频二进制**
- 只保留:视频元信息(标题、时长、平台) + 转录文本 + AI 总结 Markdown
- 临时文件使用 `tempfile` + 请求级生命周期,异常退出时靠进程清理脚本兜底

### 1.2 DMCA Agent 注册

**上线前必须完成(成本 $6):**

1. 访问 [DMCA Agent 注册页面](https://www.dmca.com/onlineAgentRegistration/)
2. 填写代理名称、地址、电话、邮箱
3. 在网站 `/dmca` 页面公开代理信息
4. 保留注册证书

### 1.3 DMCA 响应流程

```
收到 DMCA 通知 → 48h 内确认收悉 → 72h 内移除侵权内容(特定 URL 的 AI 总结)
    → 通知提交者 → 记录事件到 audit log → 重复侵权用户封禁账号
```

### 1.4 敏感站点黑名单

**默认不支持的站点(流媒体商业站点):**

```python
BLACKLISTED_DOMAINS = [
    # 流媒体
    'netflix.com', 'spotify.com', 'music.apple.com',
    'hulu.com', 'disneyplus.com', 'hbomax.com', 'primevideo.com',
    # 付费课程
    'udemy.com', 'coursera.org', 'skillshare.com',
    # 成人内容(示例,按需补充)
    # ...
]
```

**处理方式:**

- 解析阶段检测域名 → 命中黑名单 → 返回 `ERR_BLACKLISTED` 错误码
- 前端展示友好提示:"该平台视频受版权保护,暂不支持下载"
- 黑名单可远程配置(从 `/api/config/blacklist` 拉取,支持热更新)

### 1.5 用户责任声明

在以下位置明确告知用户责任:

- 注册/登录页勾选:"我理解我对下载内容的合法性负责"
- 下载按钮点击时二次提示:"请确认您有权下载此视频"
- 隐私政策/TOS 中明确用户责任条款

---

## 二、GDPR 合规(欧盟)

### 2.1 Cookie 同意

使用 **Complianz** 或 **Cookiebot** CMP(同意管理平台):

- 必要 Cookie(会话、认证):默认启用,不可禁用
- 分析 Cookie(GA4、Mixpanel):默认禁用,需 explicit opt-in
- 营销 Cookie:默认禁用,需 explicit opt-in

**实现:**

```ts
// 仅在用户同意后加载分析脚本
if (consent.granted('analytics')) {
  loadAnalytics()
}
```

### 2.2 用户权利实现

| 权利 | 条款 | 实现方式 |
|---|---|---|
| 访问权(Art. 15) | 用户可下载其所有数据 | GET `/api/me/export` 返回 JSON |
| 删除权(Art. 17) | 用户可删除账号及所有数据 | DELETE `/api/me` 30 天内响应 |
| 更正权(Art. 16) | 用户可修改个人信息 | PATCH `/api/me` |
| 限制处理权(Art. 18) | 用户可暂停 AI 处理 | 暂停按钮 + 队列停止 |
| 数据可携带权(Art. 20) | 数据以通用格式导出 | JSON 格式下载 |

### 2.3 删除账号流程

```
用户请求删除 → 验证身份(邮箱确认) → 删除 Supabase Auth 用户
    → 删除 Stripe Customer(保留收据合规 7 年)
    → 删除业务数据库所有记录
    → 删除 AI 总结缓存
    → 发送确认邮件
    → 记录审计日志(保留 1 年)
```

### 2.4 数据处理协议(DPA)

与以下第三方签署 DPA(Supabase、Stripe、Brevo 均提供):

- Supabase:GDPR DPA 在设置 → 隐私中签署
- Stripe:GDPR DPA 在 Dashboard → Legal 中签署
- Brevo:GDPR DPA 在账户设置中签署

### 2.5 隐私政策必须包含

- 控制者身份(公司名称、地址、DPO 联系方式)
- 处理目的(AI 总结、支付、客服)
- 数据保留期限(AI 总结 30 天、账号数据账号存续期、收据 7 年)
- 第三方共享清单(Supabase、Stripe、Brevo、OpenRouter)
- 用户权利清单(访问、删除、更正、限制、可携带)
- 跨境数据传输说明(EU-US Data Privacy Framework)

---

## 三、CCPA 合规(加州)

### 3.1 关键要求

- "Do Not Sell My Info" 链接(即使不卖数据也得放)
- 隐私政策披露数据类别和第三方接收者
- 12 个月内响应访问/删除请求,45 天内回复

### 3.2 触发门槛

- 年收入 > $25M **或**
- 数据规模 > 100,000 用户 **或**
- 50%+ 收入来自出售个人信息

**MVP 阶段可能未触发,但建议提前合规(成本低)。**

---

## 四、中国《个人信息保护法》(PIPL)

### 4.1 触发条件

- 面向中国用户(.cn 域名或显著中文界面)
- 处理中国境内用户个人信息

### 4.2 关键要求

- **境内数据本地化存储**:用户数据必须存储在中国境内
- **单独同意**:AI 生成总结视为"自动化决策",需单独同意
- **出境数据**:需通过安全评估、认证或签署标准合同
- **个人信息保护影响评估(PIA)**:处理敏感信息前需评估

### 4.3 建议策略

**如果 V1 不面向中国用户:**

- 使用 `.com` 域名(非 `.cn`)
- 中文站通过香港/新加坡实体运营域名
- Stripe 使用非中国大陆实体(如 Stripe Atlas 美国实体)
- 明确 ToS 中"不面向中国大陆用户"

**如果 V1 面向中国用户:**

- 使用境内服务器(阿里云/腾讯云)
- 与境内认证服务集成(而非 Supabase)
- 接入支付宝/微信支付(而非仅 Stripe)
- 完成 PIA 并向网信办备案

---

## 五、速率限制与防滥用

### 5.1 全局速率限制

```python
# 使用 slowapi 或自定义中间件
RATE_LIMITS = {
    "global": "100/minute",        # 全局请求限制
    "anonymous": "20/minute",     # 匿名用户
    "authenticated": "60/minute", # 认证用户
    "ai_summary": {
        "free": "3/day",           # 免费用户 AI 总结
        "vip": "100/day"           # VIP 用户
    },
    "video_download": {
        "free": "5/day",
        "vip": "50/day"
    }
}
```

### 5.2 视频 URL 校验

```python
import re
from urllib.parse import urlparse

def validate_video_url(url: str) -> bool:
    # 1. 必须是合法 URL
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False

    # 2. 不能是内网地址(SSRF 防护)
    if is_internal_ip(parsed.hostname):
        return False

    # 3. 域名白名单或黑名单检查
    if is_blacklisted(parsed.hostname):
        return False

    # 4. 长度限制
    if len(url) > 2000:
        return False

    return True
```

### 5.3 输入净化

- URL 参数使用 Pydantic `HttpUrl` 类型校验
- 用户输入(问答、搜索)使用 `bleach` 净化 HTML
- 文件路径使用 `pathlib` + 规范化,防止路径遍历

---

## 六、Webhook 安全(Stripe)

### 6.1 签名验证

```python
import stripe

@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationException:
        raise HTTPException(400, "Invalid signature")
```

### 6.2 幂等性

```python
# 数据库中存储已处理的 event_id
processed_events = set()

async def handle_webhook(event):
    if event.id in processed_events:
        return  # 已处理,直接返回 200

    # 处理事件...
    processed_events.add(event.id)
    await db.execute(
        "INSERT INTO processed_events (event_id) VALUES (?)",
        event.id
    )
```

### 6.3 关键事件处理

| 事件 | 处理逻辑 |
|---|---|
| `customer.subscription.created` | 创建订阅记录,更新 VIP 状态 |
| `customer.subscription.updated` | 处理升级/降级(proration) |
| `customer.subscription.deleted` | 取消 VIP,发送挽留邮件 |
| `invoice.paid` | 发送收据 PDF |
| `invoice.payment_failed` | 发送支付失败提醒,进入 dunning |

### 6.4 队列化处理

Webhook 接收 → 入队(Redis Queue / Celery) → 异步处理 → 失败重试 3 次

**不要**在 webhook 处理器中做耗时操作(发邮件、调 LLM),否则 Stripe 超时重试导致重复处理。

---

## 七、认证安全(Supabase Auth)

### 7.1 JWT 验证

```python
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    try:
        payload = jwt.decode(
            token.credentials,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        user_id = payload["sub"]
        return await get_user(user_id)
    except JWTError:
        raise HTTPException(401, "Invalid token")
```

### 7.2 用户偏好存储

```python
# 用户偏好存储在业务数据库,不直接改 Supabase auth.users
class UserPreferences(BaseModel):
    user_id: str          # 对应 auth.users.id
    language: str = "en"  # BCP-47
    currency: str = "USD"
    timezone: str = "UTC"
```

### 7.3 密码策略(如果启用 Email 登录)

- 最小长度 8 字符
- 必须包含大小写字母 + 数字
- 使用 zod 前端校验 + Pydantic 后端双重校验
- Supabase Auth 默认使用 bcrypt,无需自研

---

## 八、依赖安全

### 8.1 依赖扫描

```bash
# Python
pip-audit

# JavaScript
npm audit
npm audit fix
```

### 8.2 锁定版本

- Python:使用 `pip-compile` 生成 `requirements.txt` 带哈希
- JavaScript:使用 `package-lock.json` 或 `pnpm-lock.yaml`
- CI 中定期运行 `npm audit --audit-level=high`

### 8.3 关键依赖监控

| 依赖 | 风险等级 | 监控方式 |
|---|---|---|
| yt-dlp | 高 | GitHub issue + Reddit r/ytdl |
| Supabase | 高 | Supabase Status Page |
| Stripe | 高 | Stripe Status Page |
| OpenRouter | 中 | OpenRouter Status |
| FastAPI | 中 | GitHub Security Advisories |

---

## 九、日志与监控

### 9.1 审计日志

```python
# 记录所有敏感操作
audit_log = {
    "user_id": "uuid",
    "action": "delete_account",
    "timestamp": "2026-06-25T10:00:00Z",
    "ip": "1.2.3.4",
    "user_agent": "Mozilla/5.0...",
    "metadata": {"reason": "user_request"}
}
```

### 9.2 监控指标

- 请求成功率(目标 > 99.5%)
- AI 总结延迟(P50 < 5s,P95 < 15s)
- Stripe Webhook 成功率
- 速率限制触发次数
- DMCA 通知次数

### 9.3 告警规则

- 5xx 错误率 > 1% 持续 5 分钟 → PagerDuty
- Stripe Webhook 失败 3 次 → 邮件告警
- DMCA 通知 1 小时内 > 5 次 → 人工审核

---

## 十、上线前安全 Checklist

### 版权

- [ ] DMCA Agent 已注册
- [ ] `/dmca` 页面可访问,包含代理信息
- [ ] 敏感站点黑名单生效
- [ ] 用户责任声明在注册页可见

### 隐私

- [ ] CMP 同意横幅部署(Complianz/Cookiebot)
- [ ] 隐私政策包含 GDPR 必要条款
- [ ] 用户删除账号功能可用
- [ ] 用户数据导出功能可用
- [ ] 与 Supabase/Stripe/Brevo 签署 DPA

### 安全

- [ ] 全局速率限制生效
- [ ] 视频 URL 校验(SSRF 防护)
- [ ] Stripe Webhook 签名验证
- [ ] Stripe Webhook 幂等性
- [ ] JWT 验证中间件
- [ ] 依赖扫描通过(pip-audit + npm audit)
- [ ] 审计日志记录敏感操作

### 监控

- [ ] 5xx 错误告警配置
- [ ] Stripe Webhook 失败告警
- [ ] DMCA 通知监控
- [ ] AI 总结延迟监控

---

## 十一、风险清单

| # | 风险 | 可能性 | 影响 | 缓解措施 |
|---|---|---|---|---|
| 1 | DMCA/版权诉讼 | 中 | 高 | 不持久化视频、DMCA Agent、黑名单 |
| 2 | GDPR 罚款 | 低 | 致命 | CMP、DPA、用户删除权 |
| 3 | Stripe 账户冻结 | 中 | 高 | 3D Secure、风控规则、多账户分散 |
| 4 | yt-dlp 解析失败 | 高 | 中 | 备用解析方案、用户反馈回路 |
| 5 | LLM 总结质量差 | 中 | 高 | 多模型 fallback、用户反馈 |
| 6 | 速率限制被绕过 | 中 | 中 | IP + 用户双重限制、行为分析 |
| 7 | 内网 SSRF 攻击 | 低 | 高 | URL 校验、内网 IP 黑名单 |
| 8 | 密码泄露 | 低 | 高 | bcrypt、Supabase Auth 内置防护 |
