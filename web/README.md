# 知寻 KnowSeek · 前端

企业级智能知识中枢前端（Vue3 + TypeScript + Pinia + Element Plus）。

## 技术栈

- Vite 5 + Vue 3（script setup）
- TypeScript 严格模式
- Pinia（用户状态持久化）
- Vue Router（鉴权守卫 + 管理员路由）
- Axios（token 注入 + 401 刷新重放）
- Element Plus（企业样式：科技蓝 + 深色导航）

## 目录结构

```
web/
├── index.html
├── package.json
├── vite.config.ts          # /api 代理 → localhost:8000
├── .env.development
├── README.md
└── src/
    ├── main.ts
    ├── App.vue             # 深色顶栏 + 导航
    ├── api/                # 接口封装（auth/document/tag/conversation/chat/agent/admin）
    │   ├── request.ts      # Axios 实例：code 统一处理、401 刷新重放
    │   ├── auth.ts
    │   ├── document.ts
    │   ├── tag.ts
    │   ├── conversation.ts
    │   ├── chat.ts         # SSE 流式（fetch + ReadableStream）
    │   ├── agent.ts
    │   └── admin.ts
    ├── components/
    │   ├── UploadProgress.vue    # 上传四阶段进度条
    │   └── CitationsDialog.vue   # 溯源引用弹窗
    ├── router/index.ts
    ├── stores/user.ts
    ├── styles/theme.css    # 科技蓝变量 + 深色导航
    ├── types/index.ts      # 全量类型（与后端 schema 对齐）
    └── views/
        ├── LoginView.vue      # QQ 邮箱验证码注册/登录
        ├── DocumentView.vue   # 文档库（上传/版本/标签/筛选/删除/下载/导出）
        ├── ChatView.vue       # 对话（SSE 流式/溯源/反馈/重置上下文）
        ├── AgentTaskView.vue  # Agent 任务（人工确认流程）
        └── AdminView.vue      # 管理后台（部门/用户/文档/日志/LLM/配置）
```

## 启动方式

```bash
# 1. 先启动后端（见 ../server/README.md，默认 localhost:8000）
# 2. 安装依赖并启动前端
cd E:\AI-Agent知识库\web
npm install
npm run dev
# 打开 http://localhost:5173
```

生产构建：`npm run build`（产物在 dist/，需将 /api 反向代理到后端）。

## 关键说明

- 登录：QQ 邮箱验证码注册 + 登录，未配置 SMTP 时验证码打印在后端控制台（`GET /api/auth/send-code` 响应体亦有 demo_code）。
- 默认管理员：`admin@knowseek.com / admin123456`（需用验证码登录流程）。
- 上传四阶段进度：上传后前端每 2s 轮询文档详情，实时展示「上传完成 → 文本提取 → 解析抽取 → 索引入库」四阶段进度条。
- 对话：`/api/chat/ask` 为 SSE（citations → delta → done），流式渲染 + 溯源引用弹窗 + 好/差反馈；「重置上下文」走后端 `PUT /api/chat/conversations/{id}/reset-context`。
- 参考文档多选：后端未提供精确限定检索接口，选择后以「参考资料：xxx」前缀带入提问。
- 管理后台「对话总览」「反馈记录」：后端未提供 `/admin/conversations`、`/admin/feedback` 接口，页面已预留并给出空态说明，补齐接口即可复用。

## 默认管理员登录提示

后端默认管理员 `admin@knowseek.com`，发送验证码后经邮件收取（或 `DEV_PRINT_CODE=true` 时控制台打印），登录后自动展示「管理后台」导航。
