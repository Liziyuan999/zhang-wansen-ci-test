---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f92a25702084128d164d6c111d7f7222_baa72bb5d6ac11f1ad9c525400cd780f
    ReservedCode1: cP+EJTJoF9aC+s703azEdqGOn4akLvuHub7IRZKOToK25AuuRJM9A/OXO9P+MCrNo5uNazm44jQs6jn55a1+9CvY3YujS5ofmN1clvy7I87z77Wg5EAX1dM7Z/ZbSDSTo29Stci1jx1X35HTFjlw63LgwmLINZezMy41yB4mTVQ98YjF3gE2CBwvxHI=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f92a25702084128d164d6c111d7f7222_baa72bb5d6ac11f1ad9c525400cd780f
    ReservedCode2: cP+EJTJoF9aC+s703azEdqGOn4akLvuHub7IRZKOToK25AuuRJM9A/OXO9P+MCrNo5uNazm44jQs6jn55a1+9CvY3YujS5ofmN1clvy7I87z77Wg5EAX1dM7Z/ZbSDSTo29Stci1jx1X35HTFjlw63LgwmLINZezMy41yB4mTVQ98YjF3gE2CBwvxHI=
---

# 知寻 KnowSeek 核心功能与亮点详解

> 版本：v1.0 ｜ 日期：2026-11-02 ｜ 适用对象：开发工程师 / 产品经理 / 交付实施 / 客户演示
> 项目根目录：`E:\AI-Agent知识库`（`server/` 为 FastAPI 后端，`web/` 为 Vue3 前端）

---

## 目录

1. [项目概览](#1-项目概览)
2. [功能核心与亮点清单](#2-功能核心与亮点清单)
3. [登录认证与账号安全](#3-登录认证与账号安全)
4. [文档知识库](#4-文档知识库)
5. [RAG 智能对话](#5-rag-智能对话)
6. [文档 Copilot](#6-文档-copilot)
7. [知识图谱 GraphRAG](#7-知识图谱-graphrag)
8. [Agent 拖拽工作流](#8-agent-拖拽工作流)
9. [团队组织与审批（共享知识库 / 下载审批 / 退出审批）](#9-团队组织与审批)
10. [企业打卡（四段班次 + 地理围栏）](#10-企业打卡)
11. [智能看板](#11-智能看板)
12. [演示模式](#12-演示模式)
13. [安全与审计](#13-安全与审计)
14. [工程化与运维（健康体检修复）](#14-工程化与运维)
15. [演示与验收指南](#15-演示与验收指南)

---

## 1. 项目概览

知寻 KnowSeek 是一套面向企业内网的**企业级知识中枢系统**，以「文档知识库 + RAG 大模型问答 + 知识图谱 + Agent 自动化 + 组织协作」为核心，把企业内部散落的文档资料转化为可检索、可问答、可分析、可自动生成的智能资产。

**技术栈**

| 层 | 技术 |
|---|---|
| 后端 | Python 3.14 / FastAPI / SQLAlchemy / SQLite（可切 PostgreSQL）/ Uvicorn |
| 向量检索 | ChromaDB（内存模式降级兜底，哈希嵌入向量） |
| 前端 | Vue 3 / Vite / TypeScript / Element Plus / Pinia / ECharts / x6（流程图） |
| 模型接入 | 自研 LLM 网关（多供应商、多模型、失败回退），OpenAI 兼容协议 |

**启动方式（本地开发）**

- 后端：`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- 前端：`npm run dev -- --host 127.0.0.1 --port 5174`（Vite 代理 `/api` → `127.0.0.1:8000`）
- 测试账号：`admin@knowseek.com / admin123456`

---

## 2. 功能核心与亮点清单

### 2.1 功能核心（按产品主线划分）

| 模块 | 能力 | 一句话说明 |
|---|---|---|
| 登录认证 | 注册 / 验证码 / 密码登录 / JWT 双 Token | 企业账号体系，Token 自动续期 |
| 账号安全 | 登录失败锁定 / 异地登录告警 / SSO 预留 | 防爆破、防盗号、可对接企业 SSO |
| 文档知识库 | 上传 / 魔数校验 / 异步解析 / 切片向量化 / 版本 / 标签 / 回收站 / 导出 | 知识资产入库与生命周期管理 |
| RAG 智能对话 | 部门级检索 / SSE 流式回答 / 引用溯源 / 联网兜底 / 敏感词过滤 | 基于知识库的可靠问答 |
| 文档 Copilot | 总结 / 问答 / 续写 / 翻译 四种动作 | 文档即开即问，AI 直接产出 |
| 知识图谱 GraphRAG | 实体抽取 / 关系构建 / 图可视化 / 关联实体推荐 | 从文档中提炼结构化知识网络 |
| Agent 工作流 | 周报 / 文档对比 / 方案撰写 / 拖拽画布编排 / LangGraph | 知识检索 → 人工确认 → 自动生成 |
| 团队组织 | 多级部门树 / 团队共享知识库 / 下载审批 / 退出审批 | 组织协作与权限边界 |
| 企业打卡 | 四段班次 / 地理围栏 / 防重复 / 防篡改 / 限流 | 移动办公考勤 |
| 智能看板 | 文档统计 / 检索热度 / 部门活跃 / 趋势 / 模型用量 | 数据驱动运营 |
| 演示模式 | 一键灌入演示数据 / 一键清除 | 交付与 Demo 利器 |
| 安全审计 | 全量操作日志 / 下载水印 / 敏感词 / 提示注入防护 | 合规可追溯 |

### 2.2 差异化亮点（竞品不具备或弱于）

1. **知识图谱 GraphRAG**：不止向量检索，还能从文档中抽取实体与关系，形成"知识图谱 + RAG"双通道，回答时可联动展示关联图谱。
2. **Agent 拖拽工作流**：无需写代码，拖拽节点连线编排"规划→检索→生成→反思→精修"，支持 LangGraph 引擎切换。
3. **文档 Copilot**：打开任意文档即可对话式总结/问答/续写/翻译，不离开文档页面完成深度加工。
4. **智能看板**：检索热度、部门活跃、模型用量实时聚合，运营一屏可见。
5. **演示模式**：一键生成完整演示数据集（用户、部门、文档、知识图谱、任务），演示前 10 秒准备完毕。
6. **企业级能力**：多级部门、打卡定位围栏、下载/退出审批、全量审计、下载水印、登录锁定、SSO 预留。

---

## 3. 登录认证与账号安全

### 3.1 功能说明

系统提供完整的账号体系：注册（可选邮箱验证码）、密码登录、JWT 双 Token（Access + Refresh）自动续期、登录失败锁定、异地登录告警，并预留 SSO 配置能力，为后续对接企业统一身份认证提供接口位。

### 3.2 执行流程

```
1. 用户打开登录页，输入邮箱/密码（或点击"发送验证码"完成注册）
2. 前端 POST /api/auth/login → 后端校验密码（bcrypt）与锁定状态
3. 校验通过 → 签发 access_token（短时效）+ refresh_token（长时效）返回前端
4. 前端将双 Token 存入 Pinia store 与本地缓存
5. 后续请求自动带 Authorization: Bearer <access_token>
6. 任一请求返回 401 → 前端拦截器自动用 refresh_token 换新 Token 并重放原请求（仅一次）
7. 若 refresh 也失败 → 静默清理登录态并跳转登录页
8. 登录成功/失败都会写入登录安全日志；连续失败达到阈值 → 锁定账号并通知管理员
9. 检测到异地/新设备登录 → 向本人发送异地登录告警
```

### 3.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/send-code` | 发送邮箱验证码 |
| POST | `/api/auth/register` | 注册（邮箱 + 验证码 + 密码） |
| POST | `/api/auth/login` | 登录，返回双 Token |
| POST | `/api/auth/refresh` | 刷新 Token |
| GET | `/api/auth/lock-status` | 查询当前账号锁定状态 |
| POST | `/api/auth/unlock` | 管理员解锁账号 |
| GET | `/api/auth/sso-config` | 读取 SSO 预留配置（供对接） |

**登录请求/响应示例**

```json
// POST /api/auth/login
{"email": "admin@knowseek.com", "password": "admin123456"}
// 响应
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### 3.4 核心代码（带注释）

**后端签发 Token（`server/app/core/security.py`）**

```python
def create_token(user_id: int, token_type: str, expires_delta: timedelta | None = None) -> str:
    """签发 JWT。
    原理：将用户 ID 与 Token 类型编码进 JWT 载荷，并用 JWT_SECRET 签名。
    签名保证 Token 不可伪造；过期时间保证 Token 有时效性（Access 短、Refresh 长）。
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        # 默认按 Access Token 的时效；Refresh Token 由调用方显式传入更长时效
    )
    payload = {
        "sub": str(user_id),      # subject：用户 ID，解析时据此定位用户
        "type": token_type,       # access / refresh：区分两类 Token 用途
        "exp": expire,            # 过期时间（UTC）
        "iat": datetime.now(timezone.utc),  # 签发时间
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    # settings.JWT_SECRET 来自 .env；体检已替换为 64 位强随机密钥
```

**登录 + 锁定判断（`server/app/api/auth.py` 中 login 核心段）**

```python
# 1. 先查锁定状态：若账号被锁定，直接拒绝登录（防爆破）
lock = login_security.check_lock(db, user.id)
if lock and lock.locked_until and lock.locked_until > datetime.now():
    raise BizError(ACCOUNT_LOCKED, f"账号已锁定，请稍后再试或联系管理员解锁")

# 2. 校验密码：bcrypt 比对哈希，不存储明文
if not verify_password(password, user.hashed_password):
    login_security.record_login_fail(db, user.id, request)   # 记录失败并累计阈值
    raise BizError(BAD_CREDENTIALS, "邮箱或密码错误")

# 3. 成功后重置失败计数，签发双 Token 并记录审计
login_security.record_login_success(db, user.id, request)
access_token = create_token(user.id, "access")
refresh_token = create_token(user.id, "refresh",
                             timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS))
record_audit(db, user, "login", "auth", "登录成功", ip=client_ip)
```

**锁定与异地告警（`server/app/services/login_security.py`）**

```python
def record_login_fail(db, user_id, request):
    """登录失败计数：同用户 30 分钟内失败 ≥ 5 次 → 锁定 30 分钟并通知管理员。"""
    now = datetime.now()
    fails = db.query(LoginFailLog).filter(
        LoginFailLog.user_id == user_id,
        LoginFailLog.created_at >= now - timedelta(minutes=30),
    ).count()
    if fails + 1 >= settings.LOGIN_MAX_FAILS:   # 达到阈值
        lock = db.query(LoginLock).filter(LoginLock.user_id == user_id).first()
        if not lock:
            lock = LoginLock(user_id=user_id)
            db.add(lock)
        lock.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        db.commit()
        notify_user(db, user_id, "账号安全提醒", "登录失败次数过多，账号已临时锁定")
        return
    # 未达阈值也记录失败日志，供审计追溯
    db.add(LoginFailLog(user_id=user_id, ip=client_ip(request), user_agent=...))
    db.commit()

def record_login_success(db, user_id, request):
    """登录成功：重置失败计数；若检测到与上次登录 IP 不同则推送异地告警。"""
    # 重置失败计数
    # 对比最近一次成功登录的 IP / UA：
    #   若与历史不一致 → notify_user(..., "异地登录提醒", "检测到新设备/新地点登录")
```

**前端 401 自动续期（`web/src/api/request.ts` 拦截器核心段）**

```typescript
// 响应拦截器：业务 code 非 0 统一报错；HTTP 401 走刷新重放
instance.interceptors.response.use(
  (response) => { /* code!==0 时 ElMessage.error 并 reject */ },
  async (error) => {
    const status = error.response?.status
    const original = error.config as AxiosRequestConfig & { _retry?: boolean }
    // 401 且带 refresh_token 且未重试过 → 刷新后重放一次
    if (status === 401 && !original._retry && userStore.refreshToken) {
      if (isRefreshing) {
        // 已有请求在刷新：进入等待队列，刷新完成后统一重放（避免并发重复刷新）
        return new Promise((resolve, reject) => {
          pendingQueue.push((token) => {
            if (!token) return reject(error)
            original._retry = true
            original.headers = { ...(original.headers || {}), Authorization: `Bearer ${token}` }
            resolve(instance(original))   // 重放原请求
          })
        })
      }
      original._retry = true
      isRefreshing = true
      try {
        // 用 refresh_token 换新双 Token
        const refreshResp = await axios.post('/api/auth/refresh', {
          refresh_token: userStore.refreshToken,
        })
        userStore.setTokens(refreshResp.data.data)
        flushQueue(refreshResp.data.data.access_token)  // 唤醒排队请求
        original.headers = { ...(original.headers || {}), Authorization: `Bearer ${refreshResp.data.data.access_token}` }
        return instance(original)  // 重放原始请求
      } catch (refreshError) {
        flushQueue(null)
        await handleAuthFailure()   // 静默清登录态跳登录页
        return Promise.reject(refreshError)
      } finally { isRefreshing = false }
    }
    // 无 refresh_token 的 401：直接视为登录失效
    if (status === 401) { await handleAuthFailure(); return Promise.reject(error) }
    ElMessage.error(error.response?.data?.message || '网络请求失败')
    return Promise.reject(error)
  },
)
```

### 3.5 怎么完成 / 演示效果

1. 打开登录页 → 用 `admin@knowseek.com / admin123456` 登录，右上角出现用户信息与 Token 有效期。
2. 连续输错 5 次密码 → 账号锁定提示，管理员在"系统管理-账号安全"解锁。
3. 换一台电脑登录同一账号 → 原设备收到"异地登录提醒"站内信。
4. 系统管理页可配置 SSO 对接参数（预留位）。

---

## 4. 文档知识库

### 4.1 功能说明

文档知识库是企业知识的入库管道：支持常见办公格式（PDF/Word/Excel/PPT/图片/TXT/MD），上传后异步完成「解析 → 切片 → 向量化 → 摘要生成」，按**部门**隔离数据（每个部门只能看到本部门文档），并提供标签、多版本、回收站、批量导出等管理能力。

### 4.2 执行流程

```
1. 前端选择文件，POST /api/documents/upload（multipart，带 doc_name、tag_names）
2. 后端校验：扩展名白名单 → 大小限制 → 文件头魔数校验（防伪造扩展名）→ 落盘到
   uploads/dept_{部门ID}/ 目录，存储名为 uuid（物理文件名与业务解耦）
3. 去重检测：同部门已有「同名+同大小」或「内容 hash 相同」的文档 → 拒绝重复入库
4. 创建 Document 记录（status=pending），打标签
5. BackgroundTasks 后台执行 process_document：
   解析文本(progress=10) → 切片(progress=40) → 向量化写入 Chroma(progress=70) →
   生成 AI 摘要(progress=100) → status=success
6. 前端轮询文档列表，看到状态由"解析中"变为"已就绪"，即可参与检索问答
7. 删除 = 软删除进回收站；回收站可批量恢复（后台重建向量）或永久删除（删向量+物理文件）
```

### 4.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/documents/upload` | 上传文档（异步解析） |
| GET | `/api/documents` | 文档列表（关键词/类型/状态/标签筛选 + 分页） |
| GET | `/api/documents/{id}` | 文档详情 |
| PUT | `/api/documents/{id}` | 更新元信息（重命名/标签） |
| DELETE | `/api/documents/{id}` | 软删除（进回收站） |
| GET | `/api/documents/trash` | 回收站列表 |
| POST | `/api/documents/trash/batch-restore` | 批量恢复 |
| POST | `/api/documents/trash/batch-delete` | 永久删除（不可恢复） |
| GET | `/api/documents/export` | 按当前筛选导出 Excel 清单 |

### 4.4 核心代码（带注释）

**上传入口（`server/app/api/document.py`）**

```python
@router.post("/upload")
async def upload_doc(background: BackgroundTasks, file: UploadFile = File(...),
                     doc_name: str = Form(""), tag_names: str = Form(""),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    origin_name = file.filename or "未命名文件"
    # ① 安全落盘：类型白名单 + 大小限制 + 魔数校验（服务层实现）
    path = doc_service.save_upload_file(file, user.dept_id)
    # ② 去重：同名+同大小 或 内容hash 命中 → 拒绝并清理已落盘文件
    dup = doc_service.find_duplicate(db, dept_id=user.dept_id,
                                     origin_file_name=origin_name,
                                     file_size=doc_service._file_size(path),
                                     file_hash_value=doc_service.file_hash(path))
    if dup:
        doc_service.remove_saved_file(path)
        raise BizError(CONFLICT, f"文档库已有该文档，请勿重复上传（命中：{dup.doc_name}）")
    # ③ 建记录 + 打标签
    doc = doc_service.create_document(db, dept_id=user.dept_id, user_id=user.id, ...)
    if tag_names:
        tags = [t.strip() for t in tag_names.split(",") if t.strip()]
        if tags:
            doc_service.assign_tags(db, doc, tags)
    # ④ 后台异步解析（不阻塞响应）
    background.add_task(doc_service.process_document, db, doc.id, vector_store)
    return ok(data=..., message="上传成功，后台解析中")
```

**魔数校验（`server/app/services/doc_service.py`）**

```python
_MAGIC_MAP = {   # 文件头签名表：扩展名 → 合法二进制头
    "pdf":  (b"%PDF",),
    "png":  (b"\x89PNG\r\n\x1a\n",),
    "jpg":  (b"\xff\xd8\xff",),
    "docx": (b"PK\x03\x04",),   # Office 文件本质是 ZIP 容器
    "xlsx": (b"PK\x03\x04",),
    "pptx": (b"PK\x03\x04",),
    "txt":  (), "md": (),      # 纯文本无固定头
}

def _check_magic(path: str, suffix: str) -> None:
    """读取文件前 8 字节与签名表比对；不符 → 判定为伪造扩展名，删除并拒绝上传。"""
    signatures = _MAGIC_MAP.get(suffix)
    if not signatures:
        return
    with open(path, "rb") as f:
        head = f.read(8)
    if not head.startswith(signatures[0]):
        os.remove(path)
        raise BizError(FILE_UPLOAD_FAIL, "文件内容与扩展名不符，已拒绝上传")
```

**异步解析与向量化（`server/app/services/doc_service.py` 的 process_document）**

```python
def process_document(db, doc_id, vector_store):
    """解析 → 切片 → 向量化 → 摘要，全程更新进度供前端展示。"""
    doc = db.get(Document, doc_id)
    doc.status = "processing"; doc.progress = 10; db.commit()
    text, extra = parse_document(doc.file_path, doc.file_type)   # 按类型调用解析器
    doc.progress = 40; db.commit()
    # 扫描版 PDF 无文本层 → 标记失败，提示需 OCR（审核意见 P0）
    if doc.file_type == "pdf" and not text.strip():
        doc.status = "failed"; doc.fail_msg = "PDF 为扫描件或无文本层，需 OCR 服务支持"
        doc.progress = 100; db.commit(); return
    chunks_text = split_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)  # 切片（带重叠）
    doc.progress = 70; db.commit()
    chunk_records, vector_chunks = [], []
    for idx, chunk_text in enumerate(chunks_text):
        cid = make_chunk_id()   # 全局唯一切片 ID（Chroma id）
        chunk_records.append(DocChunk(doc_id=doc.id, chunk_text=chunk_text,
                                      page_no=idx + 1, chunk_index=idx, chroma_id=cid))
        vector_chunks.append({"id": cid, "text": chunk_text,
                              "dept_id": doc.dept_id, "page_no": idx + 1, "sheet_name": None})
    if chunk_records:
        db.add_all(chunk_records); db.commit()
        vector_store.add_chunks(doc.id, vector_chunks)   # 写入 Chroma（携带 dept_id 用于部门隔离）
    # 生成 AI 摘要：LLM 优先，失败降级为文本首段
    try:
        snippet = text[:1800]
        summary = chat_completion(db, user_id, [...], scenario="doc_summary") or snippet[:200]
        doc.summary = summary
    except Exception:
        doc.summary = text[:200]
    doc.status = "success"; doc.progress = 100; db.commit()
```

**前端文档管理页关键能力**

- 上传组件：`el-upload` 携带 token 调 `/api/documents/upload`，成功后轮询列表刷新状态进度条。
- 列表：支持关键词 / 类型 / 状态 / 标签筛选，卡片上直接显示 AI 摘要与版本号。
- 回收站：软删除与永久删除分离，恢复时自动重建向量索引。

### 4.5 怎么完成 / 演示效果

1. 进入"知识库"页 → 点击上传 → 选择一份 PDF/Word/Excel → 看到"解析中"进度条，数秒后变为"已就绪"，卡片出现 AI 摘要与标签。
2. 再次上传同一份文件 → 提示"文档库已有该文档，请勿重复上传"（去重生效）。
3. 勾选文档 → 删除 → 回收站出现；恢复后文档重新进入检索；永久删除后无法找回。
4. 点击"导出" → 下载当前列表的 Excel 清单（依赖 openpyxl，已安装）。

---
## 5. RAG 智能对话

### 5.1 功能说明

基于「检索增强生成（Retrieval-Augmented Generation）」的企业智能问答：用户提问后，系统先在部门向量库中检索最相关的知识切片，再把这些切片作为上下文交给大模型生成回答，并**实时引用来源角标 [1][2]**。支持 SSE 流式输出、会话管理、联网搜索增强、智能联网兜底、敏感词过滤与关联知识图谱实体推送。

### 5.2 执行流程

```
1. 用户输入问题 → 前端建立 SSE 连接 POST /api/chat/stream
2. 后端校验会话归属 → 保存用户消息 → 用部门ID限定向量检索（top_k 切片）
3. 切片去重（同文档同页合并，保证 [i] 角标与 citations 一一对应）
4. 组装上下文：每条切片带「文档名/页码/工作表」来源；文档热度 +1（喂给看板）
5. 关联图谱：命中文档若有已抽取实体 → 附带实体列表供前端展示
6. 联网增强：用户开启 → 实时搜索融合 [W1][W2]；未开启但本地检索为空 → 自动联网兜底
7. 构造 system prompt（结论先行/引用角标/禁止编造/网络来源区分）→ 调 LLM 流式生成
8. 输出事件流：先推 citations（来源卡片），再逐段推 delta（实时打码过滤敏感词）
9. 完成后持久化助手消息（记录引用切片 ID）→ 推 done 事件（含会话/消息 ID）
```

### 5.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/stream` | SSE 流式对话（question/conv_id/web_search/doc_ids） |
| GET | `/api/chat/conversations` | 会话列表 |
| GET | `/api/chat/conversations/{conv_id}` | 会话详情（消息+引用） |
| DELETE | `/api/chat/conversations/{conv_id}` | 删除会话 |

**SSE 事件流示例**

```
data: {"type":"citations","data":[{"chunk_id":1,"doc_id":12,"doc_name":"Langgraph课件","content":"...","page_no":3,"score":0.82}],"related_entities":[...]}

data: {"type":"delta","content":"根据知识库资料，..."}      // 逐段增量
data: {"type":"delta","content":"该方案的步骤分为三步。"}
data: {"type":"web_sources","data":[{"title":"...","url":"...","snippet":"..."}]}   // 仅联网时
data: {"type":"done","conv_id":3,"msg_id":88}
```

### 5.4 核心代码（带注释）

**切片去重（`server/app/services/chat_service.py`）**

```python
def _dedupe_chunks(chunks):
    """同一文档同一页（含工作表）的多个切片合并为一条，优先保留分数更高、文本更长的切片。
    修复引用角标与来源卡片错位问题：[i] 编号、citations、ref_ids 三者严格一一对应。"""
    deduped: dict[tuple, dict] = {}
    for c in chunks:
        key = (c.get("doc_id"), c.get("page_no"), c.get("sheet_name") or "")
        prev = deduped.get(key)
        if prev is None or (c.get("score", 0), len(c.get("text", ""))) > (
            prev.get("score", 0), len(prev.get("text", ""))):
            deduped[key] = c   # 同页多条时保留最优
    return list(deduped.values())
```

**SSE 生成主流程（`server/app/services/chat_service.py` 的 chat_sse）**

```python
# 检索 + 部门隔离：dept_id 是硬隔离边界，用户只能命中本部门文档
chunks = vector_store.query(question, dept_id=user.dept_id,
                            top_k=settings.RAG_TOP_K, doc_ids=doc_ids)
chunks = _dedupe_chunks(chunks)                    # 引用去重
# 命中文档热度 +1：智能看板「检索热度」的数据来源
for d in docs:
    d.retrieve_count = (d.retrieve_count or 0) + 1
# 组装带来源编号的上下文（模型可见）
context_parts.append(f"[{i}] {src}\n{c['text']}")
# 智能联网兜底：本地检索为空时自动补网络结果，不改变用户开关
elif not chunks:
    try: web_sources = await asyncio.to_thread(search_web, question)
    except Exception: web_sources = []
    if web_sources: use_web = True
# system prompt：结论先行 / 角标引用 / 禁止编造 / 网络来源用 [W1] 区分
# 流式事件循环
async def event_stream():
    queue = asyncio.Queue()
    def on_delta(text):
        safe = filter_sensitive(text)              # 输出侧实时敏感词打码
        queue.put_nowait(json.dumps({"type": "delta", "content": safe}))
    # 先推来源卡片与关联图谱，再推正文增量
    yield f"data: {json.dumps({'type': 'citations', 'data': citations, 'related_entities': related_entities})}\n\n"
    if web_sources:
        yield f"data: {json.dumps({'type': 'web_sources', 'data': web_sources})}\n\n"
    producer = asyncio.create_task(_produce())     # 后台流式生成（支持供应商失败回退）
    while True:
        item = await queue.get()
        if item is None: break
        yield f"data: {item}\n\n"
    # 持久化助手消息并记录引用切片 ID（用于消息级溯源）
    assistant_msg = ConversationMsg(conv_id=conv.id, role="assistant",
                                    content=answer, ref_chunk_ids=ref_ids)
    yield f"data: {json.dumps({'type': 'done', 'conv_id': conv.id, 'msg_id': assistant_msg.id})}\n\n"
return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**向量检索降级（`server/app/services/vector_store.py`）**

```python
class VectorStoreRepository:
    def __init__(self):
        # Chroma 优先；初始化失败自动降级为内存模式（哈希嵌入），保证功能可用
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
            self.mode = "chroma"
        except Exception:
            self.mode = "memory"
            self._mem_store = {}      # doc_id -> {chunk_id: text}
    def query(self, text, dept_id, top_k, doc_ids=None):
        # 混合检索：先用关键词/向量粗筛，再按 dept_id 硬过滤，最后按分数排序截断 top_k
        ...
```

**前端 Copilot 对话面板**

- 通过 `EventSource`/fetch 读取 SSE 流，按 `type` 分发：`citations` 渲染来源卡片（点击跳转文档）、`delta` 追加正文、`web_sources` 渲染网络来源、`done` 结束。
- 引用角标与来源卡片编号由后端 citations 顺序保证一一对应。

### 5.5 怎么完成 / 演示效果

1. 进入"智能对话"页，输入如"Langgraph 课件讲了什么？" → 回答以流式逐字出现，右下角出现来源卡片（文档名+页码），点击可定位原文。
2. 提问本地库没有答案的问题（如"今天天气"）→ 回答自动融合实时网络结果，网络来源以 [W1] 角标区分。
3. 多轮追问同一会话，回答始终基于上下文与知识库引用，不编造。

---

## 6. 文档 Copilot

### 6.1 功能说明

在文档详情页直接对当前文档做 AI 加工：**总结 / 问答 / 续写 / 翻译** 四种动作。不离开文档页面即可获得全文摘要、针对文档内容的问答、按上下文续写内容、中英翻译。

### 6.2 执行流程

```
1. 用户打开文档详情页 → 前端读取文档正文切片（chunks）
2. 点击 Copilot 动作（总结/问答/续写/翻译）→ POST /api/document-copilot/action
3. 后端按动作构造不同提示词模板，注入文档上下文（限量切片，控制 token）
4. 调 LLM 生成 → 返回结构化结果（result + 引用/动作说明）
5. 前端在 Copilot 面板展示结果，支持复制与重新生成
```

### 6.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/document-copilot/action` | 执行 Copilot 动作（action=summary/qa/write/translate，doc_id，可选 question） |
| GET | `/api/document-copilot/history` | 历史动作记录 |

**请求/响应示例**

```json
// POST /api/document-copilot/action
{"doc_id": 12, "action": "summary"}
{"doc_id": 12, "action": "qa", "question": "这份合同的核心风险条款有哪些？"}
{"doc_id": 12, "action": "translate", "question": "翻译为英文"}
// 响应
{"code": 0, "data": {"action": "summary", "result": "本文档主要介绍...", "ref_chunk_ids": [..]}}
```

### 6.4 核心代码（带注释）

**Copilot 服务（`server/app/services/copilot_service.py`）**

```python
def run_copilot(db, user, doc_id, action, question=""):
    """四种动作的提示词路由 + 文档上下文注入 + LLM 生成。"""
    doc = db.get(Document, doc_id)
    # 部门校验：只能操作本部门文档
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    # 读取文档切片（按序拼接，限量 30000 字符，避免超长上下文）
    chunks = db.query(DocChunk).filter(DocChunk.doc_id == doc_id) \
             .order_by(DocChunk.chunk_index.asc()).all()
    context = "\n\n".join(c.chunk_text for c in chunks)[:30000]
    # 动作 → 提示词模板
    if action == "summary":
        prompt = f"请对以下文档进行结构化总结：核心要点、关键结论、风险点。\n{context}"
    elif action == "qa":
        prompt = f"请仅依据文档内容回答：{question}\n{context}"     # 限定来源，防编造
    elif action == "write":
        prompt = f"请基于文档现有内容继续续写，保持风格一致：\n{context}"
    elif action == "translate":
        prompt = f"请将以下文档{question or '翻译为英文'}，保持术语准确：\n{context}"
    else:
        raise BizError(PARAM_ERROR, "不支持的 Copilot 动作")
    result = chat_completion(db, user.id,
                             [{"role": "system", "content": "你是企业文档助手，严格基于文档内容回答。"},
                              {"role": "user", "content": prompt}],
                             scenario=f"copilot_{action}")
    # 记录历史与审计
    CopilotHistory(doc_id=doc_id, user_id=user.id, action=action, question=question, result=result)
    record_audit(db, user, f"copilot_{action}", "document", f"对文档《{doc.doc_name}》执行{action}")
    return {"action": action, "result": result}
```

### 6.5 怎么完成 / 演示效果

1. 打开任意文档 → 右侧"文档 Copilot"面板。
2. 点"总结" → 数秒内生成结构化全文摘要。
3. 输入问题点"问答" → 基于本文档回答并给出结论。
4. 点"续写" → 在文档末尾按现有风格生成延续内容。
5. 点"翻译" → 输出目标语言全文。

---

## 7. 知识图谱 GraphRAG

### 7.1 功能说明

超越传统向量检索的差异化能力：系统从文档中**自动抽取实体（人物/组织/概念/技术等）与关系**，构建可交互的知识图谱。回答问题时不仅引用原文，还联动展示与答案相关的图谱实体，实现"知识网络"级检索。支持图谱可视化、实体详情、按部门隔离。

### 7.2 执行流程

```
1. 文档解析完成后，后台任务对该文档执行 GraphRAG 抽取
2. 抽取器调 LLM：从正文识别实体（名称/类型/描述）与实体间关系（主语-谓词-宾语）
3. 实体与关系写入 Entity / Relation 表（携带 doc_id 与 dept_id）
4. 前端知识图谱页加载：GET /api/kg/graph → 返回节点(实体)+边(关系)供 x6/ECharts 渲染
5. RAG 问答命中某文档时，附带该文档已抽取实体（related_entities）推送到前端
6. 用户点击实体 → 查看详情与关联文档
```

### 7.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/kg/graph` | 获取知识图谱（节点+边，可按部门/文档过滤） |
| GET | `/api/kg/entities/{entity_id}` | 实体详情 |
| GET | `/api/kg/relations` | 关系列表 |
| POST | `/api/kg/rebuild/{doc_id}` | 重新抽取某文档图谱 |

### 7.4 核心代码（带注释）

**图谱抽取（`server/app/services/kg_service.py`）**

```python
def extract_kg(db, doc_id, user):
    """对文档正文执行实体与关系抽取，写入图谱表。"""
    doc = db.get(Document, doc_id)
    chunks = db.query(DocChunk).filter(DocChunk.doc_id == doc_id) \
             .order_by(DocChunk.chunk_index.asc()).all()
    text = "\n".join(c.chunk_text for c in chunks)[:20000]   # 限制抽取范围控制成本
    # 结构化输出提示：要求模型返回 JSON 数组（实体+关系），便于解析入库
    prompt = (
        "从以下文档中抽取关键实体与实体关系，输出 JSON：\n"
        '{"entities": [{"name": "...", "type": "人物/组织/概念/技术/地点/其他", "description": "..."}], '
        '"relations": [{"source": "实体A", "target": "实体B", "relation": "关系描述"}]}\n' + text
    )
    raw = chat_completion(db, user.id, [...], scenario="kg_extract")
    data = parse_structured_json(raw)      # 容错解析模型输出（剥除代码块/修正括号）
    # 入库：先清理该文档旧实体，再写入新实体与关系（保证重建幂等）
    db.query(Entity).filter(Entity.doc_id == doc_id).delete()
    db.query(Relation).filter(Relation.doc_id == doc_id).delete()
    for e in data.get("entities", []):
        db.add(Entity(doc_id=doc_id, dept_id=doc.dept_id, entity_name=e["name"],
                      entity_type=e.get("type", "其他"), description=e.get("description", "")))
    for r in data.get("relations", []):
        db.add(Relation(doc_id=doc_id, dept_id=doc.dept_id,
                        source_entity=r["source"], target_entity=r["target"],
                        relation_desc=r.get("relation", "")))
    db.commit()
```

**RAG 联动图谱（`server/app/services/chat_service.py`）**

```python
# 命中文档若已有抽取实体 → 附带实体列表供前端展示"关联图谱"
related_entities = [{"id": e.id, "name": e.entity_name, "type": e.entity_type,
                     "description": e.description or "", "doc_id": e.doc_id}
                    for e in db.query(Entity).filter(Entity.doc_id.in_(doc_ids))
                               .order_by(Entity.id.desc()).limit(30).all()]
```

### 7.5 怎么完成 / 演示效果

1. 上传几篇关于"公司产品/项目"的文档，等待解析完成并触发图谱抽取。
2. 进入"知识图谱"页 → 看到节点与连边的可视化图，节点按类型着色，可拖拽缩放。
3. 在智能对话中问相关知识 → 回答区附带"关联图谱"缩略图，点击实体可跳转图谱查看完整网络。

---

## 8. Agent 拖拽工作流

### 8.1 功能说明

把"知识检索 + 大模型生成"封装成可编排的 Agent 任务：内置**周报 / 文档对比 / 方案撰写**三种模板，支持指定文档范围、周期任务、完成通知；更高级的是**拖拽式画布工作流**——用节点连线编排"规划→检索→生成→反思→精修"，一键切换 LangGraph 引擎执行，全程生成可审计的工作流轨迹。

### 8.2 执行流程

```
1. 用户选择任务类型（周报/文档对比/方案撰写）或拖拽画布自定义流程
2. 选择文档范围（可选）+ 补充参数（含 web_search 联网开关、extra 附加要求）
3. 创建任务：立即执行部门向量检索，保存候选切片（status=retrieving）
4. 一次性任务进入 waiting_confirm：展示"检索到 N 条依据"供用户人工确认
5. 用户确认后：
   - 画布任务 → run_canvas_workflow：按连线顺序执行节点（检索/生成/反思等）
   - LangGraph 任务 → run_langgraph_workflow：规划→检索→生成→反思→精修
   - 经典任务 → 单轮 LLM 生成
6. 生成结果落库 + 记录 workflow_trace 轨迹 + 按需通知用户
7. 周期任务（schedule_type=periodic）创建后自动执行，按 cron 定期运行
```

### 8.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent/tasks` | 创建任务（task_type/doc_ids/params/schedule/canvas_json） |
| GET | `/api/agent/tasks` | 任务列表 |
| GET | `/api/agent/tasks/{id}` | 任务详情（含检索依据与结果） |
| POST | `/api/agent/tasks/{id}/confirm` | 确认/取消（confirm=true/false） |
| DELETE | `/api/agent/tasks/{id}` | 删除任务 |
| GET | `/api/agent/templates` | 任务模板列表 |
| POST | `/api/agent/templates` | 保存模板（复用任务配置） |

### 8.4 核心代码（带注释）

**创建任务 + 人工确认（`server/app/services/agent_service.py`）**

```python
def create_agent_task(db, user, task_type, doc_ids, params, vector_store,
                      schedule_type="once", ...):
    # ① 补充参数安全校验：敏感词/提示注入直接拒绝（不进入 prompt）
    param_text = json.dumps(params or {}, ensure_ascii=False)
    if contains_sensitive(param_text):
        raise BizError(SENSITIVE_CONTENT, "任务补充参数包含敏感词，请修改后重试")
    if contains_injection(param_text):
        raise BizError(SENSITIVE_CONTENT, "任务补充参数包含提示注入内容，已拒绝创建")
    # ② 建任务记录，先执行检索（预取依据，供确认页展示）
    task = AgentTask(user_id=user.id, task_type=task_type, selected_doc_ids=doc_ids,
                     params=params, status="retrieving", ...)
    db.add(task); db.commit(); db.refresh(task)
    chunks = _retrieve_for_task(db, user, task_type, doc_ids, vector_store)
    task.retrieval_chunks = chunks          # 检索依据快照
    # ③ 一次性任务等确认；周期任务直接自动执行
    task.status = "waiting_confirm" if schedule_type == "once" else "finished"
    if task.status == "finished":
        task.task_result = _build_result(db, user, task)
    db.commit()

def confirm_task(db, user, task_id, confirm):
    # 确认时按引擎分流：画布 / LangGraph / 经典
    if task.canvas_json and (task.params or {}).get("graph_engine") == "canvas":
        result, trace = run_canvas_workflow(db, user, task, provider_id=provider_id)
        task.workflow_trace = trace          # 记录每一步的输入输出，可审计
    elif (task.params or {}).get("graph_engine") == "langgraph":
        result, trace = run_langgraph_workflow(db, user, task, _vector_store, ...)
        task.workflow_trace = trace
    else:
        task.task_result = _build_result(db, user, task)   # 经典单轮生成
```

**结果生成（`_build_result`）**

```python
# 任务上下文 = 检索切片 + 联网来源（构建统一上下文文本）
context = build_context_text(chunks, task.web_sources or [], doc_map)
prompt = TASK_PROMPTS.get(task.task_type)    # 周报/对比/方案 各自模板
extra = (task.params or {}).get("extra")
if extra:
    prompt = f"{prompt}\n\n用户补充要求：{guard_user_content(str(extra))}"   # 注入防御
# 注入防御提示词（DEFENSIVE_SYSTEM_HINT），要求模型只基于知识片段回答
system = "你是「知寻 KnowSeek」企业智能 Agent。请严格基于知识片段生成结果..." + DEFENSIVE_SYSTEM_HINT
return chat_completion(db, user.id, [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}],
                       scenario=f"agent_{task.task_type}", provider_id=provider_id)
```

**拖拽画布（前端 `WorkflowCanvasBuilder.vue` + 后端 `canvas_workflow.py`）**

- 前端基于 x6 流程图库：左侧拖拽"检索/生成/反思/精修/结束"节点到画布，连线表示执行顺序；点击节点配置参数（如生成节点选模型）；导出 `canvas_json`（节点+边）随任务提交。
- 后端 `run_canvas_workflow`：解析 `canvas_json` 拓扑顺序，按边依赖依次执行节点，聚合前序输出传入后序，最终产出结果并记录每节点轨迹（模型、耗时、输入输出摘要）→ `workflow_trace`。

### 8.5 怎么完成 / 演示效果

1. 进入"Agent 任务"页 → 新建"周报任务"，选择文档范围 → 提交。
2. 看到任务状态"等待确认"与"检索到 N 条依据"预览 → 点击确认 → 生成结构化周报。
3. 切换到"拖拽工作流"页 → 拖入"检索→生成→反思→精修"节点并连线 → 运行 → 查看最终结果与每一步的执行轨迹。
4. 在任务列表勾选"完成后通知我" → 结果生成后收到站内通知。

---
## 9. 团队组织与审批

### 9.1 功能说明

组织协作层提供：**多级部门树**（部门层级管理）、**团队共享知识库**（团队所有者的文档对全体成员可见，支持按版本预览正文）、**下载审批**（成员下载共享文档需向 owner/admin 申请，审批通过后才能下载，owner/admin 直接下载，下载文件自动叠加水印）、**退出审批**（成员退出需提交申请，审批通过后自动移除成员）。所有审批动作写入审计日志并触发站内通知。

### 9.2 执行流程

**下载审批流程**

```
1. 团队所有者上传文档 → 该文档自动进入团队"共享知识库"
2. 成员浏览共享文档列表 → 查看正文预览（不暴露物理路径）
3. 成员点击下载 → 若为 owner/admin 直接放行（status=direct）
4. 普通成员 → 填写申请理由 → POST download-request → 生成 pending 审批单
5. 系统通知所有 owner/admin（"新的下载审批申请"）
6. 审批人通过 → 申请人收到"下载审批已通过"通知 → 携带 approval_id 调下载接口
7. 后端校验 approval 归属与状态 → 生成水印副本 → FileResponse 返回
```

**退出审批流程**

```
1. 成员提交退出申请（owner 不可退出）
2. 系统通知 owner/admin
3. 审批通过 → 自动删除成员关系 + 团队日志 + 通知申请人
```

### 9.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/team/{team_id}/shared-docs` | 共享知识库列表 |
| GET | `/api/team/{team_id}/shared-docs/{doc_id}` | 共享文档详情（正文预览，限量） |
| POST | `/api/team/{team_id}/shared-docs/{doc_id}/download-request` | 提交下载申请（owner/admin 直接放行） |
| GET | `/api/team/{team_id}/shared-docs/{doc_id}/download` | 下载（成员需 approval_id，带水印） |
| GET | `/api/team/{team_id}/approvals/downloads` | 下载审批列表（owner/admin） |
| POST | `/api/team/{team_id}/approvals/downloads/{id}/approve` | 通过下载申请 |
| POST | `/api/team/{team_id}/approvals/downloads/{id}/reject` | 拒绝下载申请 |
| POST | `/api/team/{team_id}/approvals/exits` | 提交退出申请 |
| GET | `/api/team/{team_id}/approvals/exits` | 退出审批列表 |
| POST | `/api/team/{team_id}/approvals/exits/{id}/approve` | 通过退出申请（自动移除成员） |
| POST | `/api/team/{team_id}/approvals/exits/{id}/reject` | 拒绝退出申请 |
| GET | `/api/team/{team_id}/approvals/my` | 我的申请记录（下载/退出/补卡） |
| GET | `/api/team/{team_id}/approvals/pending-count` | 待审批计数 |

### 9.4 核心代码（带注释）

**共享文档下载（带水印，`server/app/api/org_extra.py`）**

```python
@router.get("/{team_id}/shared-docs/{doc_id}/download")
def download_shared_doc(team_id, doc_id, approval_id=Query(0),
                        user=Depends(get_current_user), db=Depends(get_db)):
    team = _get_team(db, team_id)
    me = _require_member(db, team_id, user)          # 必须是团队成员
    latest = _latest_doc(db, main_doc.id) or main_doc  # 取最新版本
    if me.role not in ("owner", "admin"):
        # 成员下载必须携带已批准的 approval_id（归属、文档、状态三重校验）
        ap = db.get(DownloadApproval, approval_id) if approval_id else None
        if not ap or ap.team_id != team_id or ap.doc_id != doc_id \
           or ap.applicant_id != user.id or ap.status != "approved":
            raise BizError(NO_PERMISSION, "该文档需审批通过后才能下载")
    # 下载水印：叠加"用户名+时间"水印防泄密溯源（产物为临时副本，不污染原文件）
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wm_path = apply_watermark(latest.file_path, user.username, ts)
    record_audit(db, user, "download_watermarked", "team",
                 f"下载共享文档《{latest.doc_name}》(doc#{doc_id}) 已叠加水印 [{user.username} {ts}]")
    return FileResponse(wm_path, filename=latest.origin_file_name)
```

**审批通过并自动移除成员（`approve_exit` 核心段）**

```python
ap.status = "approved"; ap.approver_id = user.id; ap.handle_time = datetime.now()
if tm:
    db.delete(tm)          # 直接从 TeamMember 表移除成员关系
db.add(TeamLog(team_id=team_id, user_id=user.id, action="exit_approve",
               message=f"审批通过 {ap.applicant_id} 的退出申请，已移除成员"))
db.commit()
if applicant:
    notify_user(db, applicant.id, "退出申请已通过", f"您已退出团队「{team.name}」",
                category="approval", ntype="approval", related_id=team_id)
record_audit(db, user, "exit_approve", "team", f"通过成员 {ap.applicant_id} 的退出申请，已移除成员")
```

### 9.5 怎么完成 / 演示效果

1. 管理员在"组织中心"维护多级部门树，创建团队并任命 owner/admin。
2. owner 上传文档 → 团队成员在"共享知识库"看到文档并可预览正文。
3. 成员点下载 → 提示"需审批"并提交申请 → owner 收到待办 → 通过后成员可下载，下载文件带"用户名+时间"水印。
4. 成员申请退出 → owner 审批通过 → 成员即时被移除并收到通知。

---

## 10. 企业打卡

### 10.1 功能说明

企业移动考勤：**四段班次**（上午上班 09:00 / 上午下班 12:00 / 下午上班 14:00 / 下午下班 18:30），**地理围栏强校验**（必须在团队配置的工作区域内打卡），服务端时间权威（客户端时间不可信）、防重复打卡、防篡改（记录经纬度/IP/UA/时间戳）、限流防刷、补卡审批。

### 10.2 执行流程

```
1. 管理员配置团队工作区域（中心经纬度 + 半径）→ PUT attendance/geo
2. 成员点击打卡 → 浏览器/App 获取定位 → POST attendance/clock?slot=am_in&lat=..&lng=..
3. 服务端校验：团队成员 → 限流（1 分钟 5 次）→ 班次合法 → 地理围栏（距离≤半径）
4. 服务端时间窗口校验：当前时刻必须在班次窗口内
5. 前置校验：pm_out 需先完成 pm_in（依序打卡）；同班次重复打卡拒绝
6. 写入 AttendanceRecord（四段时间 + checkin_meta JSON 记录经纬度/IP/UA）→ 审计
7. 查看今日状态：本人四段 + 团队统计（各段打卡人数、出勤率、最新打卡时间）
```

### 10.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/team/{team_id}/attendance/clock` | 打卡（slot/lat/lng） |
| GET | `/api/team/{team_id}/attendance/geo` | 查看工作区域配置 |
| PUT | `/api/team/{team_id}/attendance/geo` | 配置工作区域（owner/admin） |
| GET | `/api/team/{team_id}/attendance/today` | 今日打卡状态 + 团队统计 |
| POST | `/api/team/{team_id}/attendance/fix` | 提交补卡申请 |
| GET | `/api/team/{team_id}/attendance/history` | 打卡历史 |

### 10.4 核心代码（带注释）

**打卡主流程（`server/app/api/org_extra.py` 的 clock）**

```python
@router.post("/{team_id}/attendance/clock")
def clock(team_id, request: Request, slot=Query(...), lat=Query(...), lng=Query(...),
          user=Depends(get_current_user), db=Depends(get_db)):
    _get_team(db, team_id); _require_member(db, team_id, user)
    _clock_rate_limit(team_id, user)              # 防刷：1 分钟最多 5 次
    if slot not in SHIFT_SLOTS:
        raise BizError(PARAM_ERROR, "无效班次")
    geo = _validate_geo_clock(db, team_id, lat, lng)  # 地理围栏强校验
    # 服务端时间权威：以服务器当前时刻判断是否在班次窗口内（客户端时间不可信）
    now = datetime.now()
    cur_min = now.hour * 60 + now.minute
    win = SHIFT_SLOTS[slot]
    if not (win["start"] <= cur_min <= win["end"]):
        raise BizError(PARAM_ERROR, f"当前时间不在「{win['label']}」打卡时段")
    rec = db.query(AttendanceRecord).filter(team_id==team_id, user_id==user.id, date==today).first()
    if win["prev"] and (not rec or not _get_slot_time(rec, win["prev"])):
        raise BizError(PARAM_ERROR, f"请先完成「{SHIFT_SLOTS[win['prev']]['label']}」打卡")  # 依序打卡
    if rec and _get_slot_time(rec, slot):
        raise BizError(CONFLICT, f"今日「{win['label']}」已打卡，请勿重复打卡")
    # 写入打卡时间 + 元数据（经纬度/IP/UA/时间戳），防篡改可审计
    meta[slot] = {"lat": round(lat,6), "lng": round(lng,6), "ip": _client_ip(request),
                  "ua": (request.headers.get("user-agent") or "")[:200], "ts": _fmt(now)}
    rec.checkin_meta = json.dumps(meta, ensure_ascii=False)
    db.commit()
    record_audit(db, user, f"attendance_clock_{slot}", "team",
                 f"企业打卡：{today} {win['label']}（距围栏中心 {int(dist)}m）")
```

**地理围栏校验（`_validate_geo_clock`）**

```python
def _validate_geo_clock(db, team_id, lat, lng):
    """未配置/未启用/不在围栏内均拒绝打卡；球面距离（Haversine）计算。"""
    geo = db.query(TeamGeoConfig).filter(TeamGeoConfig.team_id == team_id).first()
    if not geo or not geo.enabled:
        raise BizError(PARAM_ERROR, "团队尚未配置工作区域，请联系管理员配置后打卡")
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise BizError(PARAM_ERROR, "定位坐标不合法")
    dist = _haversine_m(lat, lng, geo.lat, geo.lng)   # 米级球面距离
    if dist > geo.radius_m:
        raise BizError(NO_PERMISSION,
                       f"您不在工作区域内（距离 {int(dist)}m，围栏半径 {geo.radius_m}m），禁止打卡")
    return geo
```

### 10.5 怎么完成 / 演示效果

1. 管理员进入团队设置 → 配置工作区域（公司坐标 + 半径 500m）。
2. 成员打卡页自动定位 → 点击"上午上班" → 在区域内提示"打卡成功（距围栏中心 12m）"。
3. 离开区域打卡 → 提示"您不在工作区域内，禁止打卡"。
4. 重复打卡/跳过前置班次 → 分别提示"已打卡"、"请先完成上午上班打卡"。
5. 团队成员打卡统计页：今日出勤率、各时段已打卡人数实时更新。

---

## 11. 智能看板

### 11.1 功能说明

面向运营与管理者的数据驾驶舱：聚合**文档规模、检索热度、部门活跃、增长趋势、模型用量**五大维度，一屏掌握知识库运行状态。数据来自检索命中计数、上传/对话/任务等真实业务事件。

### 11.2 执行流程

```
1. 文档上传/解析、RAG 检索命中、Agent 任务执行等业务动作实时写库（retrieve_count 等）
2. 看板页加载 → 并行请求 5 个聚合接口
3. 后端 SQL 聚合（按部门/按天/按模型分组）→ 返回统计序列
4. 前端 ECharts 渲染柱状图/折线图/环形图/排行榜
```

### 11.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/dashboard/stats` | 总览统计（文档/切片/用户/任务数） |
| GET | `/api/dashboard/doc-trend` | 文档增长趋势（按天） |
| GET | `/api/dashboard/hot-docs` | 检索热度 Top 文档 |
| GET | `/api/dashboard/dept-active` | 部门活跃度 |
| GET | `/api/dashboard/model-usage` | 模型调用量与 Token 用量 |

### 11.4 核心代码（带注释）

**热度聚合（`server/app/api/dashboard.py` 示例段）**

```python
@router.get("/hot-docs")
def hot_docs(user=Depends(get_current_user), db=Depends(get_db)):
    # 取本部门检索命中次数最高的文档 Top10（retrieve_count 在 RAG 命中时 +1）
    rows = db.query(Document).filter(Document.dept_id == user.dept_id,
                                     Document.is_deleted.is_(False),
                                     Document.status == "success") \
             .order_by(Document.retrieve_count.desc()).limit(10).all()
    return ok(data=[{"id": d.id, "doc_name": d.doc_name, "retrieve_count": d.retrieve_count or 0}
                    for d in rows])

@router.get("/doc-trend")
def doc_trend(user=Depends(get_current_user), db=Depends(get_db)):
    # 按天统计本部门新增文档量（近 14 天），返回日期+数量序列供折线图
    # 实现：对 Document.create_time 做 date 分组聚合，补全无数据日期为 0
    ...
```

### 11.5 怎么完成 / 演示效果

1. 进入"智能看板"页 → 顶部总览卡片（文档数/切片数/用户数/任务数）。
2. 中部：文档增长折线图、部门活跃条形图。
3. 右侧：检索热度 Top10 文档排行榜、模型调用量统计。
4. 在对话页提问多次后回到看板 → 命中文档热度实时上升。

---

## 12. 演示模式

### 12.1 功能说明

面向交付与 Demo 场景：**一键灌入演示数据**（预置部门、用户、文档、知识图谱实体、Agent 任务），**一键清除**恢复干净环境。演示前无需手工造数据，10 秒即可进入可讲解状态。

### 12.2 执行流程

```
1. 管理员打开"演示模式"页 → 点击"灌入演示数据"
2. 后端 demo_service 依次创建：演示部门/成员 → 上传演示文档 → 等待解析 →
   触发图谱抽取 → 创建示例 Agent 任务 → 返回汇总
3. 前端提示"演示数据准备完成（N 个部门 / M 个文档 / K 个图谱实体）"
4. 演示结束 → 点击"清除演示数据" → 删除演示部门及其文档/图谱/任务（不触碰真实数据）
```

### 12.3 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/demo/seed` | 灌入演示数据 |
| POST | `/api/demo/cleanup` | 清除演示数据 |
| GET | `/api/demo/status` | 演示数据状态 |

### 12.4 核心代码（带注释）

**灌入演示数据（`server/app/services/demo_service.py` 核心段）**

```python
def seed_demo_data(db):
    """按固定 ID 前缀创建演示数据（可重复执行，幂等更新）。"""
    demo_dept = Dept(id=DEMO_DEPT_ID, name="演示事业部", parent_id=...)   # 预置部门
    demo_user = User(email="demo@knowseek.com", username="演示用户", dept_id=DEMO_DEPT_ID, ...)
    # 上传演示文档（内置样例文件）→ 触发后台解析/向量化/图谱抽取
    docs = upload_demo_docs(db, demo_user, DEMO_DEPT_ID)
    # 创建示例 Agent 任务（周报），演示人工确认流程
    create_demo_task(db, demo_user)
    return {"departments": 1, "users": 1, "documents": len(docs), "tasks": 1}

def cleanup_demo_data(db):
    """按部门 ID 删除演示数据（物理删除文档与向量，不触碰其他真实数据）。"""
    # 删除演示部门的文档记录、DocChunk、Entity/Relation、AgentTask、用户
    ...
```

### 12.5 怎么完成 / 演示效果

1. 演示前点击"灌入演示数据" → 数秒后知识库/图谱/任务页出现完整演示数据。
2. 用演示账号登录 → 演示文档问答、Copilot、图谱、Agent 任务全流程。
3. 结束后点击"清除演示数据" → 页面恢复干净初始状态。

---

## 13. 安全与审计

### 13.1 功能说明

企业合规基座：**全量操作审计**（请求中间件自动记录每个 /api 请求的用户/动作/路径/IP/耗时/结果）、**业务语义审计**（登录/上传/下载/审批等记录语义化 action）、**下载水印**、**敏感词过滤**（输入输出双侧）、**提示注入防护**、**登录锁定与异地告警**、**JWT 强密钥**（已替换为 64 位随机密钥）。

### 13.2 核心接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/audit/logs` | 审计日志列表（分页/筛选） |
| GET | `/api/audit/stats` | 审计统计 |

### 13.3 核心代码（带注释）

**请求审计中间件（`server/app/services/audit.py`）**

```python
def audit_middleware(get_db_session, get_user_from_token):
    """审计中间件：所有 /api 请求（除登录注册刷新外）自动写入 OperationLog。"""
    async def middleware(request: Request, call_next):
        start = time.monotonic()
        user = None
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            user = get_user_from_token(auth[7:])   # 从 Token 解析用户（用于日志归属）
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        if request.url.path.startswith("/api") and request.url.path not in SKIP_PATHS:
            db.add(OperationLog(
                user_id=user.id if user else None,
                username=user.username if user else None,
                dept_id=user.dept_id if user else None,
                action=request.method, module=segs[2],  # /api/xxx/... → 模块名取第二段
                path=request.url.path,
                ip=request.client.host if request.client else "",
                status="success" if response.status_code < 400 else "fail",
                duration_ms=duration_ms,
            ))
            db.commit()
        return response
    return middleware
```

**输入输出双侧敏感词防护**

- 输入侧：`guard_user_content(question)` 清洗用户问题；`contains_sensitive` / `contains_injection` 在 Agent 参数层拒绝敏感/注入内容。
- 输出侧：`filter_sensitive(text)` 在 SSE delta 与最终答案上实时打码，并注入 `DEFENSIVE_SYSTEM_HINT` 系统提示，要求模型不响应越权指令。

### 13.4 安全基线（已落地）

- JWT_SECRET：64 位强随机密钥（`.env` 配置，原始文件已备份到 temp 目录）；替换后**存量 Token 失效，用户需重新登录**。
- 数据库连接与 Chroma 目录：改为基于 `BASE_DIR` 的相对路径，不再硬编码绝对路径。
- 密码存储：bcrypt 哈希，不存明文。
- 上传校验：扩展名白名单 + 魔数校验 + 大小限制 + 去重。

---

## 14. 工程化与运维

### 14.1 健康体检修复记录（本次交付）

| 项目 | 发现 | 处理结果 |
|---|---|---|
| JWT_SECRET | 开发占位符（弱密钥） | 已替换为 64 位随机密钥并写入 `.env`；原 `.env` 已备份至 temp 目录；存量 Token 失效需重新登录 |
| 冗余文件 | `main_20261026_145032_717.py`、`_fix_code.py`、`_fix_code2.py`、`ai_assistant.db.bak_dept_upgrade` | 已删除（进入回收站） |
| 路径硬编码 | `DATABASE_URL`、`CHROMA_DIR` 写死绝对路径 | 已改为基于 `BASE_DIR` 的相对路径，重启验证登录与 RAG 检索正常 |
| 前端主包 | 首包 1.15MB | `vite.config.ts` 增加 `manualChunks` 拆包，主包降至约 21KB |

**数据库/Chroma 相对路径改造（`server/app/core/config.py`）**

```python
BASE_DIR = Path(__file__).resolve().parent.parent.parent   # = server/（项目根）
# 数据库：sqlite 相对 server 目录定位，迁移服务器无需改路径
DATABASE_URL = f"sqlite:///{(BASE_DIR / 'ai_assistant.db').as_posix()}"
# Chroma 向量目录：同样基于 BASE_DIR
CHROMA_DIR = str((BASE_DIR / "chroma_data").as_posix())
```

**前端拆包（`web/vite.config.ts`）**

```typescript
build: {
  rollupOptions: {
    output: {
      // 手动拆包：高频第三方依赖从业务主包分离，缩小首屏主包体积
      manualChunks(id) {
        if (!id.includes('node_modules')) return undefined
        if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus' // UI 全家桶（含图标，最大）
        if (id.includes('vue') || id.includes('@vue')) return 'vue-vendor'                    // Vue 运行时
        if (id.includes('pinia') || id.includes('axios')) return 'store-vendor'              // 状态+网络层
        return 'vendor'                                                                      // 其余三方依赖
      },
    },
  },
}
// 构建结果对比：主包 1151561B → 21060B；vendor/vue-vendor/element-plus/store-vendor 按需并行加载
```

### 14.2 后端重启验证

```bash
# 重启后端（无 reload 生产形态）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 探活
GET /api/health → {"code":0,"data":{"app":"知寻 KnowSeek 后端服务","version":"1.0.0"}}
# 登录（新 JWT）→ 200 成功；文档列表 → 200；RAG Copilot 摘要 → code=0 返回结构化摘要（citations=1）
```

### 14.3 环境与依赖

- 后端：Python 3.14；关键依赖 FastAPI / SQLAlchemy / ChromaDB / openpyxl（导出）/ python-jose / bcrypt / pypdf 等。
- 前端：Node + Vite 5 / Vue 3 / TypeScript / Element Plus / Pinia / ECharts / @antv-x6。
- 数据存储：SQLite `server/ai_assistant.db`；向量库 `server/chroma_data`。

---

## 15. 演示与验收指南

### 15.1 环境准备

1. 启动后端：`cd E:\AI-Agent知识库\server && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. 启动前端：`cd E:\AI-Agent知识库\web && npm run dev -- --host 127.0.0.1 --port 5174`
3. 浏览器访问 `http://127.0.0.1:5174`，使用 `admin@knowseek.com / admin123456` 登录（若此前 Token 已失效，重新登录即可）。

### 15.2 验收清单（客户可逐项打勾）

| # | 验收项 | 操作 | 预期 |
|---|---|---|---|
| 1 | 登录与安全 | 连续输错 5 次密码 | 账号锁定，可管理员解锁；换设备登录触发异地告警 |
| 2 | 文档知识库 | 上传 PDF/Word/Excel | 异步解析完成，生成摘要与标签，重复上传被拦截 |
| 3 | RAG 问答 | 提问知识库相关问题 | 流式回答 + 来源卡片 + 页码定位；离线问题自动联网兜底 |
| 4 | 文档 Copilot | 打开文档执行总结/问答/续写/翻译 | 四种动作均产出可用结果 |
| 5 | 知识图谱 | 查看图谱页 / 对话中关联实体 | 实体关系可视化，问答联动图谱 |
| 6 | Agent 任务 | 创建周报任务 → 确认 | 检索依据预览 → 确认后生成周报；拖拽画布可编排并留轨迹 |
| 7 | 团队与审批 | 成员申请下载/退出 | 审批流闭环，下载带水印，退出自动移除成员 |
| 8 | 企业打卡 | 区域内/区域外打卡 | 围栏校验、四段依序、防重复防刷 |
| 9 | 智能看板 | 浏览五大聚合图 | 数据随业务动作实时更新 |
| 10 | 演示模式 | 灌入/清除演示数据 | 10 秒就绪，一键恢复干净环境 |
| 11 | 审计 | 系统管理-审计日志 | 每个操作可追溯（用户/IP/路径/耗时/结果） |
| 12 | 构建 | `npm run build` | 构建通过，主包约 21KB（拆包后） |

### 15.3 常见问题

- **存量 Token 失效**：JWT_SECRET 已更换，所有用户需重新登录一次，属预期行为。
- **扫描版 PDF 无法解析**：当前版本提示"需 OCR 服务支持"，属审核意见 P0 预留项。
- **打卡提示未配置工作区域**：需管理员先在团队设置中配置经纬度与半径。

---

*本文档由知寻 KnowSeek 项目交付材料自动生成，覆盖核心功能实现原理、接口与演示路径，可直接交付开发与客户阅读。*


*（内容由AI生成，仅供参考）*
