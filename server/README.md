# 知寻 KnowSeek 后端服务

「知寻 KnowSeek —— 企业级智能知识中枢」后端。基于 FastAPI + SQLAlchemy 2.0 + Pydantic v2，支持 QQ 邮箱验证码注册登录、JWT 双 token、文档上传/解析/重叠切片/Chroma 向量化、RAG SSE 流式对话与溯源、Agent 任务人工确认、管理员后台、部门隔离、审计日志与 LLM 调用记录。

## 技术栈

- Python 3.11+（本机实测 Python 3.14）/ FastAPI / Uvicorn
- SQLAlchemy 2.0（ORM，默认 SQLite，可平滑切换 PostgreSQL+pgvector）
- Chroma 向量库（未安装时自动降级内存向量，保证本地可运行）
- Pydantic v2 / pydantic-settings
- QQ 邮箱 SMTP 验证码；DeepSeek（OpenAI 兼容接口，未配置时本地降级回答）

## 目录结构

```
server/
├── app/
│   ├── main.py               # 应用入口（建表/CORS/审计中间件/路由注册）
│   ├── api/                  # 接口层：16 组路由（auth/user/document/document_copilot/chat/agent/admin/team/notice/audit/dashboard/report/model_provider/org_extra/kg/demo）
│   ├── core/                 # 配置、错误码、统一响应、JWT/密码、依赖
│   ├── db/                   # 引擎、会话、Base、业务索引定义（indexes.py）
│   ├── models/               # 34 张 ORM 表
│   ├── schemas/              # Pydantic 请求/响应模型
│   └── services/             # 邮件/向量库/LLM/解析/文档/对话/Agent/审计
├── migrations/               # Alembic 迁移目录（env.py / script.py.mako / versions/）
│   └── versions/             # 迁移脚本（baseline + 增量，按 revision 串联）
├── scripts/
│   ├── init_db.py            # 建表（空库初始化，含业务索引）
│   └── seed_data.py          # 默认部门 + 管理员账号
├── alembic.ini               # Alembic 配置（URL 由 env.py 从 .env/settings 读取）
├── requirements.txt
├── .env.example              # 配置模板
├── .env                      # 本地配置
└── README.md
```

## 34 张 ORM 表

| 模块 | 表 |
|---|---|
| 认证/安全 | user、refresh_token、email_code、security_event |
| 组织/团队 | department、team、team_member、team_invitation、team_notice、team_notice_read、team_log、team_role、team_exit_approval |
| 文档/知识 | document、doc_tag、doc_tag_rel、doc_chunk、download_approval、vector_orphan |
| 对话 | conversation、conversation_msg、feedback |
| Agent/模型 | agent_task、agent_template、model_provider |
| 考勤 | attendance_record、team_geo_config、attendance_fix_approval |
| 通知 | user_notification |
| 知识图谱 | entity、entity_relation |
| 系统 | sys_config、operation_log、llm_call_log |

## 快速启动

```bash
cd E:\AI-Agent知识库\server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 初始化数据库（应用启动时也会自动建表）
python scripts/init_db.py
python scripts/seed_data.py   # 可选：创建默认部门与管理员 admin@knowseek.com（密码来自 ADMIN_INIT_PASSWORD，未设则随机生成并打印）

# 启动后端（本机实测：Python 3.14 绝对路径，127.0.0.1 无 reload；通用环境可用 PATH 中的 uvicorn）
C:\Users\10102\AppData\Local\Programs\Python\Python314\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 http://localhost:8000/docs 查看 Swagger 接口文档；健康检查 GET /api/health。

## 数据库迁移（Alembic）

项目已接入 Alembic 作为唯一的库结构演进入口，所有命令**必须在 `server` 目录下执行**（`alembic.ini`、`migrations/`、`ai_assistant.db` 均以该目录为基准）。

- 连接串复用 `app/core/config.py` 的 `settings.DATABASE_URL`：`env.py` 读取该值，若为相对 sqlite 路径（如 `sqlite:///./ai_assistant.db`）会自动拼接 `BASE_DIR` 转为绝对路径，因此与工作目录无关（仍建议在 `server` 下执行）；引擎默认复用 `app/db/session.py` 的 `engine`，元数据为 `app.db.base.Base.metadata`（自动 import `app.models`）。
- 临时指向其他库（如验证脚本）：`alembic -x db_url=sqlite:///D:/tmp/test.db upgrade head`，或设置环境变量 `ALEMBIC_DATABASE_URL`。
- 27 条业务索引定义在 `app/db/indexes.py`（原生 DDL），未写入 ORM metadata；`env.py` 通过 `include_object` 显式忽略它们，避免 `revision --autogenerate` / `alembic check` 误生成 `drop_index`。索引新增仍改 `indexes.py`，需要落库版本化的再补一条显式迁移。

常用命令：

```bash
# 查看当前库版本 / 迁移历史
alembic current
alembic history --verbose

# 升级到最新（幂等：已是 head 时不执行任何 DDL）
alembic upgrade head

# 升级/回退指定步数或指定 revision
alembic upgrade +1
alembic downgrade -1
alembic downgrade base          # 清空到初始状态（SQLite 会删表，谨慎）

# 把已存在但未被 Alembic 管理的库标记为某版本（不改表结构、不动数据）
alembic stamp head

# 修改模型后生成新迁移脚本（务必人工复核生成的 upgrade/downgrade）
alembic revision --autogenerate -m "add xxx column"
alembic revision -m "manual ddl"     # 生成空脚本，手写 op.xxx

# 校验"模型 vs 库"是否一致（CI 可用；一致时输出 No new upgrade operations detected）
alembic check
```

迁移脚本约定：

- 文件名形如 `20261111_cae9dcf72c38_baseline_schema.py`（`file_template` 带日期前缀，便于排序）；
- `20261111_cae9dcf72c38` 为 baseline：包含 34 张表 + 28 条 ix_ 索引（27 条业务索引 + `ix_security_event_user_id`）。空库 `upgrade head` 即可一次建全；**存量库一律 `stamp head` 标记，不要对已有库执行 baseline 的 upgrade**（否则重复建表）；
- `20261111_924992ded229`：把历史 `create_all` 遗留的 12 个"nullable + 带 server_default"列对齐为 `NOT NULL` 且无 server_default（SQLite 走 batch 重建，重建后自动补回该表业务索引）；
- 新增迁移请保持 `downgrade()` 可回滚；SQLite 下改列需 `op.batch_alter_table`。

> 说明：`app/main.py` 启动钩子仍保留 `create_all` 与 `apply_column_patches`（幂等），用于兼容未接入 Alembic 的空白环境；**正式的表结构变更请走 Alembic 迁移**，不要依赖启动时自动建表。

## 认证与验证码说明

- 注册/登录流程：`POST /api/auth/send-code`（purpose=register/login）→ 输入邮箱验证码完成注册/登录。
- 未配置 `MAIL_USER/MAIL_PASS` 时验证码不会真实发送，而是打印到后端控制台（形如 `[DEV] ... code=123456`），便于本地联调。
- 配置 QQ 邮箱：在 QQ 邮箱设置中开启 SMTP 服务获取授权码，填入 `.env` 的 `MAIL_USER/MAIL_PASS/MAIL_FROM`。

## LLM 说明

- 未配置 `DEEPSEEK_API_KEY` 时，RAG 对话与 Agent 任务返回本地降级回答（检索片段已生效），服务保持可用；
- 配置后即走 DeepSeek `deepseek-chat` 流式生成，调用记录写入 `llm_call_log`。

## 部门隔离与权限

- 所有文档/检索严格按 `dept_id` 隔离，普通用户仅能访问本部门数据。
- 角色：`staff`（员工）/ `admin`（管理员）；管理员后台接口需 `admin` 角色。

## 错误码约定

统一响应 `{code, message, data}`；`code=0` 表示成功。常见错误码：

| code | 含义 |
|---|---|
| 10001 | 参数错误 |
| 10002 | 未登录 / token 无效 |
| 10003 | 无权限 |
| 10004 | 资源不存在 |
| 10006 | 验证码错误或过期 |
| 20001 | 文件解析失败 |
| 30001 | LLM 未配置 |
| 40001 | 任务状态不允许 |
| 50000 | 服务器内部错误 |
