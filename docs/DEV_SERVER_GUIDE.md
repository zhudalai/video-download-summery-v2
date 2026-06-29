# 开发服务速查

## 启动命令

### 后端 (FastAPI)
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端 (Vite + Vue 3)
```bash
cd frontend
npm run dev
```

## 服务地址

| 服务 | 地址 | 说明 |
|---|---|---|
| 前端首页 | http://localhost:5173 | Vue 3 SPA |
| 后端 API | http://localhost:8000 | FastAPI |
| Swagger 文档 | http://localhost:8000/docs | API 文档 |
| ReDoc | http://localhost:8000/redoc | API 文档(可读性更好) |
| OAuth 回调 | http://localhost:5173/auth/callback | Google/GitHub 登录回调 |

## 健康检查端点

```bash
# 后端主健康检查
curl http://localhost:8000/api/health
# 响应: {"status":"ok","version":"0.1.0"}

# 认证模块
curl http://localhost:8000/api/auth/health
# 响应: {"status":"auth module ready"}

# 视频模块
curl http://localhost:8000/api/videos/health
# 响应: {"status":"video module ready"}

# AI 模块
curl http://localhost:8000/api/ai/health
# 响应: {"status":"ai module ready"}

# 支付模块
curl http://localhost:8000/api/payment/health
# 响应: {"status":"payment module ready"}
```

## 测试注册/登录流程

### 前置条件
1. Supabase 项目已创建
2. Email Provider 已启用(默认启用)
3. Redirect URL 已配置: `http://localhost:5173/auth/callback`

### 测试步骤

1. **打开浏览器** → http://localhost:5173/login

2. **测试注册**
   - 输入邮箱(如 `test@example.com`)
   - 输入密码(至少 6 位)
   - 点击 "Sign Up"
   - 检查邮箱是否收到验证邮件

3. **测试登录**
   - 输入已注册的邮箱和密码
   - 点击 "Sign In"
   - 成功后会跳转到首页,右上角显示邮箱地址

4. **测试 OAuth**(如果已配置 Google/GitHub)
   - 点击 "Google" 或 "GitHub" 按钮
   - 跳转到 OAuth 授权页面
   - 授权后回调到 `/auth/callback`
   - 自动跳转回首页

5. **测试受保护端点**
   ```bash
   # 获取 JWT(从浏览器 DevTools → Application → Cookies/Storage 或 Network)
   # 前端登录后,DevTools Network 面板找 /api/auth/me 请求,复制 Authorization header
   
   curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/api/auth/me
   ```

## 常见问题

### 1. 端口被占用
```bash
# Windows 查看端口占用
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# 结束任务
taskkill /PID <PID> /F
```

### 2. 后端启动失败
- 检查 `.env` 文件是否存在且环境变量正确
- 检查 dependencies/auth.py 是否存在
- 检查 routers/__init__.py 是否导出 video, ai, payment, auth

### 3. 前端启动失败
- 检查 `node_modules` 是否存在(不存在运行 `npm install`)
- 检查 `.env` 文件是否存在且 VITE_SUPABASE_URL/VITE_SUPABASE_ANON_KEY 正确

### 4. OAuth 回调失败
- 检查 Supabase Dashboard → Authentication → URL Configuration
  - Site URL: `http://localhost:5173`
  - Redirect URLs: `http://localhost:5173/auth/callback`
- 检查 Provider 是否已启用(Google/GitHub 需要额外配置 OAuth App)

## 下一步功能开发

完成测试后,可以继续开发:
1. **yt-dlp 集成**(视频解析)
2. **OpenRouter 网关**(AI 总结)
3. **用户资料页面**
4. **Stripe 支付集成**

每个功能完成后,记得更新文档。
