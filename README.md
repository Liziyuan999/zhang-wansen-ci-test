---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f92a25702084128d164d6c111d7f7222_e041bdb8ce7a11f18de0525400de85a5
    ReservedCode1: RaBg86cwNyHGm1ViDvPwKMygyLEmkDymNesXl2zojsRagN5oT8b/dwNM6UIWOaj249p9+8UfqlR5H+QF2vDZi3brt7/UVDofCPRd3Rxs0RXBjs2fqXk7VfBlouhBWMgIzGM8gZILAm3wH1eERDq8a1msTV4fP7zsYrmQJsr5Mn3TI48615UoqcdU+7Y=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f92a25702084128d164d6c111d7f7222_e041bdb8ce7a11f18de0525400de85a5
    ReservedCode2: RaBg86cwNyHGm1ViDvPwKMygyLEmkDymNesXl2zojsRagN5oT8b/dwNM6UIWOaj249p9+8UfqlR5H+QF2vDZi3brt7/UVDofCPRd3Rxs0RXBjs2fqXk7VfBlouhBWMgIzGM8gZILAm3wH1eERDq8a1msTV4fP7zsYrmQJsr5Mn3TI48615UoqcdU+7Y=
---

# 知寻 KnowSeek — 企业级智能知识中枢

基于 FastAPI + LangGraph + Vue3 的企业级智能知识中枢系统，覆盖文档知识库、GraphRAG 知识图谱、RAG 智能问答、Agent 拖拽工作流、Copilot 助手、智能看板、演示模式、组织协同（部门树/团队）、打卡考勤、审批流、审计与登录安全，并提供管理后台。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue3 + TypeScript + Vite + Element Plus |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2 |
| 向量 | Chroma（生产可切换 PostgreSQL + pgvector） |
| 认证 | QQ 邮箱验证码 + JWT 双 token（access + refresh） |
| 大模型 | DeepSeek（OpenAI 兼容接口，未配置时本地降级） |

## 快速启动

### 方式一：一键启动（Windows）

双击项目根目录 `start.bat`，脚本将依次完成：
1. 安装后端依赖（pip install -r server/requirements.txt）
2. 初始化数据库（建表 + 种子数据）
3. 启动后端服务（http://127.0.0.1:8000，仅监听本机）
4. 安装前端依赖并启动（http://127.0.0.1:5174，固定端口）

### 方式二：手动启动

```bash
# 1. 后端
cd server
pip install -r requirements.txt
python scripts/init_db.py        # 首次初始化建表
python scripts/seed_data.py      # 可选：种子数据
uvicorn app.main:app --host 127.0.0.1 --port 8000   # 开发可加 --reload

# 2. 前端（另开终端）
cd web
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

## 测试与构建

```bash
# 后端冒烟回归（14 项，含注册/登录/文档/RAG/Agent）
cd server && python -u tests\test_smoke.py

# 新接口验证（admin 文档/会话/反馈、chat 分页/重置上下文/权限）
# 验证脚本 verify_new_apis_v2.py 位于开发工作区临时目录，按需执行

# 前端构建
cd web && npm run build
```

## 主要模块

- **认证**：`POST /api/auth/send-code`、`/register`、`/login`、`/refresh`；验证码 60s 发送间隔，SMTP 未配置时模拟打印
- **文档**：上传/解析/分片/打标签/版本/删除/导出，`GET /api/documents`
- **对话**：RAG SSE 流式问答（带溯源 citations）、消息分页、重置上下文
- **Agent**：任务创建、人工确认、执行（周报/文档对比/计划撰写）
- **管理后台**：用户/部门/文档/会话/反馈/审计日志/LLM 调用记录/系统配置

## 功能全景

| 模块 | 一句话说明 | 核心能力 |
|---|---|---|
| 知识库文档 | 企业文档统一接入 | 上传/解析/分片/标签/版本/删除/导出/下载水印 |
| RAG 智能问答 | 基于私有知识的流式问答 | SSE 流式、溯源 citations、上下文重置、部门级隔离 |
| 知识图谱 GraphRAG | 实体关系可视化与图谱问答 | 实体/关系抽取、图谱浏览、GraphRAG 检索增强 |
| Agent 工作流 | 拖拽编排 + LangGraph 执行 | 画布式编排、人工确认节点、周报/对比/计划模板、定时任务 |
| Copilot 助手 | 文档侧边智能辅助 | 摘要/问答/续写、随文档上下文联动 |
| 智能看板 | 数据洞察驾驶舱 | 文档/对话/Agent 多维统计、趋势图表 |
| 演示模式 | 开箱即用产品演示 | 一键生成演示部门与数据、Demo 账号 |
| 组织协同 | 部门树/团队协作 | 多级部门、团队、邀请加入、公告 |
| 打卡考勤 | 地理围栏考勤 | GPS 围栏打卡、补卡审批、考勤统计 |
| 审批流 | 下载/退出/补卡审批 | 审批流、超时催办、审计留痕 |
| 审计与安全 | 全域审计与登录防护 | 操作日志、LLM 调用记录、登录锁定、异地告警、双 token |

## 测试账号（本地预置）

| 账号 | 密码 | 角色 | 说明 |
|---|---|---|---|
| admin@knowseek.com | admin123456 | 管理员 | 完整后台权限（默认部门） |
| demo_market@knowseek.com | 验证码登录 | 员工 | 演示模式-市场部 |
| demo_rd@knowseek.com | 验证码登录 | 员工 | 演示模式-研发部 |

> 登录采用邮箱验证码模式：未配置 SMTP 时验证码打印在后端控制台（形如 `[DEV] ... code=123456`）。管理员账号由 `scripts/seed_data.py` 预置（未设 `ADMIN_INIT_PASSWORD` 时密码随机生成，当前库实例已设为 admin123456）；演示账号由演示模式自动生成（占位密码哈希、不支持密码登录），请用邮箱验证码登录演示账号，首次登录后建议修改密码。

## 部署

- **本地开发**：见上方快速启动；后端细节见 `server/README.md`。
- **容器化**：根目录 `docker compose up -d` 一键编排 PostgreSQL+pgvector / 后端(8000) / 前端 Nginx(80)，详见 `docker-compose.yml`、`server/Dockerfile`、`web/Dockerfile`。
- **生产反代**：`web/nginx.conf` 已内置前端 history 路由回退、`/api` 反向代理、SSE 关闭缓冲（流式对话不被阻塞）等配置。
- **上线路线**：见 [上线计划书.md](上线计划书.md)（域名/备案/HTTPS、PostgreSQL、真实凭据、安全加固、合规、CI/CD 等 P0-P2 清单）。
- **合规与验收**：`docs/用户协议.md`、`docs/隐私政策.md`；验收截图见 `docs/验收截图`。
- **CI**：`.github/workflows/ci.yml`。

## 目录结构

```
├── server/            # FastAPI 后端
│   ├── app/
│   │   ├── api/       # 16 组路由（auth/user/document/copilot/chat/agent/admin/team/kg/demo/audit 等）
│   │   ├── core/      # 配置、错误码、统一响应、JWT、依赖
│   │   ├── db/        # 引擎、会话、Base、迁移
│   │   ├── models/    # 33 张 ORM 表（认证/组织/文档/对话/Agent/团队/考勤/审批/审计等）
│   │   ├── schemas/   # Pydantic 模型
│   │   └── services/  # 邮件/向量库/LLM/解析/对话/Agent/知识图谱/Copilot/考勤/审批/审计/水印
│   ├── scripts/       # init_db.py / seed_data.py
│   ├── tests/         # test_smoke.py 等
│   └── .env           # 环境配置（JWT_SECRET/MAIL_USER/API_KEY 等）
├── web/               # Vue3 前端
│   └── src/
│       ├── api/       # 接口封装
│       ├── views/     # Login/Document/Chat/AgentTask/Admin
│       └── stores/    # Pinia 用户态
└── 知寻KnowSeek_企业级技术方案.md
```

## 环境变量（server/.env）

> 完整示例见 `server/.env.example`（逐项带注释）。下表列出全部可用项，未填则使用默认值。

| 变量 | 说明 | 默认 |
|---|---|---|
| `DATABASE_URL` | 数据库连接（SQLite / PostgreSQL，代码双兼容） | `sqlite:///./ai_assistant.db` |
| `CHROMA_DIR` | Chroma 向量库目录（相对路径以 server/ 为基准） | `./chroma_data` |
| `VECTOR_COLLECTION` | 向量集合名 | `kb_default` |
| `JWT_SECRET` | JWT 签名密钥（生产必换强随机值） | 开发占位值 |
| `JWT_ALGORITHM` | JWT 签名算法 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌有效期（分钟） | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 刷新令牌有效期（天） | `7` |
| `MAIL_HOST` / `MAIL_PORT` | QQ 邮箱 SMTP 服务地址/端口 | `smtp.qq.com` / `465` |
| `MAIL_USER` / `MAIL_PASS` / `MAIL_FROM` | SMTP 账号/授权码/发件人 | 空则模拟发送（控制台打印） |
| `EMAIL_CODE_EXPIRE_MINUTES` | 邮箱验证码有效期（分钟） | `5` |
| `EMAIL_SEND_INTERVAL_SECONDS` | 同一邮箱发送间隔（秒） | `60` |
| `DEEPSEEK_API_KEY` | LLM API Key（OpenAI 兼容） | 空则本地降级回答 |
| `LLM_MODEL` / `LLM_BASE_URL` | LLM 模型名/接口地址 | `deepseek-chat` / `https://api.deepseek.com/v1` |
| `LLM_TIMEOUT_SECONDS` | 单次 LLM 调用超时（秒） | `60` |
| `LLM_FIRST_TOKEN_TIMEOUT_SECONDS` | 首 token 超时（秒，SSE 场景） | `60` |
| `LLM_RETRY_TIMES` | LLM 失败重试次数 | `1` |
| `UPLOAD_DIR` | 上传文件落盘目录 | `./uploads` |
| `MAX_FILE_SIZE_MB` | 单文件大小上限（MB） | `50` |
| `ALLOWED_FILE_TYPES` | 允许上传的扩展名（JSON 数组） | pdf/docx/xlsx/pptx/txt/md/csv/png/jpg/jpeg |
| `OCR_ENABLED` | 扫描件 OCR（需安装 paddleocr） | `false` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 切片长度/重叠字符数 | `800` / `100` |
| `RAG_TOP_K` | 检索召回条数 | `5` |
| `CORS_ORIGINS` | 允许跨域来源（JSON 数组） | 本机 5173/5174 |
| `LOGIN_MAX_FAILS` / `LOGIN_LOCK_MINUTES` | 连续登录失败锁定阈值/时长 | `5` / `15` |
| `SEND_CODE_IP_LIMIT_PER_HOUR` | 单 IP 每小时发码上限 | `10` |
| `SEND_CODE_EMAIL_LIMIT_PER_DAY` | 单邮箱每日发码上限 | `10` |
| `APPROVAL_REMINDER_HOURS` / `APPROVAL_REMINDER_INTERVAL_MINUTES` | 审批超时催办阈值/轮询间隔 | `24` / `60` |
| `WATERMARK_ENABLED` | 共享库下载水印（防泄密溯源） | `true` |
| `DEV_PRINT_CODE` | 本地联调打印验证码明文到控制台 | `false` |

### 生产运行参数（本地实机）

| 项 | 值 | 说明 |
|---|---|---|
| 后端启动 | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` | 工作目录必须是 `server/`（`BASE_DIR` 由 `app/core/config.py` 反推，DB/向量库/上传目录均相对其定位）；生产不加 `--reload`，避免改码热重载带来的状态丢失与内存翻倍 |
| 后端解释器 | 本项目实测环境 `C:\Users\<用户>\AppData\Local\Programs\Python\Python314\python.exe` | 需 3.11+；用绝对路径启动可避免多版本 `python` 混淆 |
| 前端启动 | `cd web && npm run dev -- --host 127.0.0.1 --port 5174` | 生产用 `npm run build` 产出 `web/dist`，由 Nginx 托管 |
| 健康检查 | `GET http://127.0.0.1:8000/api/health` → `code=0` | 探活/看门狗脚本建议 10s 一次，连续 3 次失败再重启 |
| 端口占用排查 | `Get-NetTCPConnection -LocalPort 8000 -State Listen` | 旧进程残留会导致"改了代码不生效"，重启前先确认 PID 与启动时间 |
| 数据备份 | `server/ai_assistant.db` + `server/uploads/` + `server/chroma_data/` | 三者需成套备份，否则会出现文档记录与物理文件/向量不一致 |

详细设计见 [知寻KnowSeek_企业级技术方案.md](知寻KnowSeek_企业级技术方案.md)。
*（内容由AI生成，仅供参考）*
