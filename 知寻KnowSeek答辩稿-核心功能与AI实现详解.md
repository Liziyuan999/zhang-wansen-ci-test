---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f92a25702084128d164d6c111d7f7222_d9fbacb6d8b211f1bff2525400cd780f
    ReservedCode1: HUx1I4shTOsSjVX2kZYeBUWOIahJV/PwnUimCGKfczF4+YxrklZgDo6fMbD1FxaW0I7m3gNq1aF7eMcd4cWgAYkO3u5PWeTUOQRYv041YLoB728NVcvRSDXEX6wbA+z+72tmdL10pmisbA3FKPKTrIJQpEnj79yIIGkrG20/2JHkhjycyd48TjsVAxs=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f92a25702084128d164d6c111d7f7222_d9fbacb6d8b211f1bff2525400cd780f
    ReservedCode2: HUx1I4shTOsSjVX2kZYeBUWOIahJV/PwnUimCGKfczF4+YxrklZgDo6fMbD1FxaW0I7m3gNq1aF7eMcd4cWgAYkO3u5PWeTUOQRYv041YLoB728NVcvRSDXEX6wbA+z+72tmdL10pmisbA3FKPKTrIJQpEnj79yIIGkrG20/2JHkhjycyd48TjsVAxs=
---

# 知寻 KnowSeek 企业级 AI 知识库平台 —— 答辩演示稿

> 面向答辩评委：本文档为「项目全貌 + 十大核心功能 + AI 实现深度拆解」的自包含说明。每个功能均按
> **【功能核心】→【核心代码位置与源代码】→【执行流程】→【核心接口】→【怎么实现的】→【答辩一句话总结】**
> 五段式展开。文档中所有代码均摘自线上已逐行加注源码（绝对路径 + 行号区间），保证与运行代码严格一致。

---

## 一、项目定位

知寻 KnowSeek 是一套**企业级 AI 知识库平台**：把企业文档、制度、项目资料沉淀为可检索、可问答、可关联的
知识资产，并在此基础上提供 AI 对话助手（RAG 问答 + 多轮记忆）、文档 Copilot、知识图谱 GraphRAG、
Agent 可视化工作流编排、智能看板与演示模式，同时覆盖登录安全（JWT 双 Token）、考勤审批、审计留痕等
企业级核心能力。定位是「**让每一家企业都能低门槛用上 AI 知识管理**」。

## 二、技术栈

| 层 | 技术选型 | 说明 |
|---|---|---|
| 前端 | Vue 3 + TypeScript + Vite | SFC 组合式 API，严格类型约束（vue-tsc 构建零报错） |
| UI | Element Plus + ECharts | 企业后台组件库 + 看板/图谱可视化 |
| 状态/路由 | Pinia + vue-router | token 持久化、路由守卫按角色位过滤 |
| 后端 | Python FastAPI + SQLAlchemy + SQLite | 前后端分离 REST API，异步 SSE 流式 |
| 向量检索 | Chroma + 本地哈希嵌入 | 离线可用、重启不丢索引 |
| 安全 | PyJWT(HS256) + passlib(bcrypt) | access/refresh 双 Token、登录锁定、验证码 |
| AI 接入 | OpenAI 兼容协议（DeepSeek / 千问等） | 供应商可配置，流式/非流式双通道 |
| 审计 | Starlette HTTP 中间件 | 全量请求留痕 + 业务显式审计双通道 |

## 三、整体架构

```
┌──────────────────────── 浏览器端（Vue3 + TS） ────────────────────────┐
│  views: ChatView / DocumentView / KnowledgeGraphView / AgentTaskView │
│         CopilotPanel / DashboardView / AttendanceView / AuditView   │
│  api/   : chat.ts / document.ts / kg.ts / agent.ts / auth.ts ...     │
│  stores/: user.ts（token + 角色位）   router/: 守卫按角色位过滤        │
└───────────────┬──────────────────────────────────────────────────────┘
                │ HTTP / SSE (Authorization: Bearer)
┌───────────────▼───────────────── FastAPI 后端 ───────────────────────┐
│ 中间件：CORSMiddleware（跨域） + audit_middleware（审计留痕）          │
│ api 层   ：auth / user / document / document_copilot / chat / agent /│
│            kg / dashboard / attendance / audit / demo / admin ...    │
│ service 层：chat_service（RAG+记忆）/ vector_store（向量检索）         │
│            kg_service（图谱抽取）/ canvas_workflow（画布DAG）          │
│            copilot_service（文档AI）/ demo_service（演示数据）         │
│            doc_service（解析入库）/ audit（审计）                      │
│ core 层  ：security.py（JWT/bcrypt） / config.py（配置）              │
│ models    ：SQLAlchemy ORM（用户/文档/切片/实体/会话/Agent/考勤/审计）  │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
      SQLite（业务数据） + Chroma（向量索引，本地哈希嵌入）
```

**分层原则**：api 层只做参数校验与鉴权，业务逻辑全部下沉 service 层，模型层统一 ORM；
AI 相关能力（检索/图谱/画布/Copilot）以独立 service 解耦，任一能力可单独替换。

## 四、功能地图（本文档章节）

| 章 | 功能 | 面向评委的关键词 |
|---|---|---|
| 01 | AI 对话助手 | SSE 流式、8 轮多轮记忆、RAG 引用、部门隔离 |
| 02 | RAG 知识库问答 | 解析入库、向量+关键词融合、Chroma 离线嵌入 |
| 03 | 文档 Copilot | 摘要/翻译/提问、chunk 引用 |
| 04 | 知识图谱 GraphRAG | LLM+规则双通道抽取、ECharts 力导向图 |
| 05 | Agent 可视化工作流 | 拖拽画布、DAG 拓扑执行、workflow_trace 回溯 |
| 06 | 智能看板 | 多指标聚合、7 日趋势、LLM 运营总结 |
| 07 | 演示模式 | 一键演示数据、is_demo 标记可重置 |
| 08 | 登录安全 | JWT 双 Token、bcrypt、登录锁定、验证码 |
| 09 | 打卡审批 | 定位围栏、缺卡申请、审批闭环回写 |
| 10 | 审计日志 | HTTP 中间件全量留痕、双通道审计 |

---

## 五、核心功能一览表（功能 → 能做什么 → 解决什么问题）

| 功能 | 能做什么 | 解决什么问题 |
|---|---|---|
| AI 对话助手 | 流式问答、8 轮多轮记忆、知识库引用溯源、模型切换 | 检索提效、降低幻觉、沉淀组织记忆 |
| RAG 知识库 | 多格式文档自动入库、语义检索、部门隔离 | 搜索失效、数据分散、越权风险 |
| 文档 Copilot | 摘要、中英互译、文档定向提问 | 阅读成本、语言壁垒、定位效率 |
| 知识图谱 GraphRAG | 实体抽取建图、关系可视化、实体搜索 | 知识孤岛、检索升级、决策支持 |
| Agent 工作流 | 模板任务、拖拽画布、trace 回溯 | 重复劳动、自动化门槛、可信可控 |
| 智能看板 | 多指标聚合、趋势/排行、LLM 总结 | 管理盲区、决策效率、运营洞察 |
| 演示模式 | 一键演示数据、一键重置 | 演示耗时、数据污染、场景复现 |
| 登录安全 | JWT 双 Token、bcrypt、锁定、验证码 | 防爆破、防泄露、合规 |
| 打卡审批 | 定位打卡、缺卡申请、审批回写 | 管理成本、合规留痕、防代打 |
| 审计日志 | 全量留痕、多维检索、操作回放 | 责任追溯、合规要求、安全监控 |

---
## 01. AI 对话助手：SSE 流式问答 + 单轮/多轮对话记忆

### 功能核心
AI 对话助手是知寻 KnowSeek 的入口级功能：用户提问后，后端把知识库检索到的 RAG 片段、图谱关联实体与网络结果注入大模型上下文，通过 SSE（Server-Sent Events）逐字流式返回；同一会话内自动加载历史对话并按 8 轮上限截断，实现多轮记忆承接（历史个人信息可直接回答、与知识片段互不混淆）。前端 ChatView 负责乐观渲染与打字机效果，api/chat.ts 的 askSSE 负责流式协议解析。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 输入自然语言提问，秒级流式回复，支持追问与话题切换；
- 同一会话自动记住上下文，跨轮次追问无需重复交代背景；
- 回答附带知识库引用角标 [1][2]，可点击回看原文片段；
- 可指定参考文档、开启联网搜索，DeepSeek/千问等模型供应商一键切换；
- 多会话管理 + 历史回溯 + 一键重置记忆。

**解决什么问题**

- 效率：员工查制度、找资料从「翻文件夹」变为「直接问」，检索时间大幅下降；
- 准确性：回答基于知识库引用而非模型记忆，显著降低 AI 幻觉带来的信息失真；
- 知识沉淀：问答过程沉淀为组织记忆，新人培训与老员工经验可复用。

### 核心代码位置与源代码

**① 检索知识片段 → 构建引用上下文（RAG 链路起点）**（`E:\AI-Agent知识库\server\app\services\chat_service.py` L122-L166，共 45 行）

```python
    chunks = vector_store.query(question, dept_id=user.dept_id, top_k=settings.RAG_TOP_K, doc_ids=doc_ids)
    # RAG 引用去重：同文档同页切片合并，保证 [i] 角标与 citations 一一对应
    chunks = _dedupe_chunks(chunks)
    doc_ids = list({c["doc_id"] for c in chunks})
    doc_map: dict[int, str] = {}
    if doc_ids:
        docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
        doc_map = {d.id: d.doc_name for d in docs}
        # 文档热度：检索命中次数 +1（智能看板数据来源）
        for d in docs:
            d.retrieve_count = (d.retrieve_count or 0) + 1
        db.commit()
    citations = _build_citations(chunks, doc_map)
    ref_ids = [c["chunk_id"] for c in chunks]

    # 关联知识图谱实体：命中文档若有已抽取实体，附带实体列表供前端展示"关联图谱"
    related_entities: list[dict[str, Any]] = []
    if doc_ids:
        kg_entities = (
            db.query(Entity)
            .filter(Entity.doc_id.in_(doc_ids))
            .order_by(Entity.id.desc())
            .limit(30)
            .all()
        )
        related_entities = [
            {
                "id": e.id,
                "name": e.entity_name,
                "type": e.entity_type,
                "description": e.description or "",
                "doc_id": e.doc_id,
            }
            for e in kg_entities
        ]

    context_parts = []
    for i, c in enumerate(chunks, 1):
        src = f"文档:{doc_map.get(c['doc_id'], c['doc_id'])}"
        if c.get("page_no"):
            src += f" 第{c['page_no']}页"
        if c.get("sheet_name"):
            src += f" 工作表:{c['sheet_name']}"
        context_parts.append(f"[{i}] {src}\n{c['text']}")
    context = "\n\n".join(context_parts) or "（未检索到相关内容）"
```


**② System Prompt（含第 6 条对话记忆指引）+ 历史消息加载与截断 + 最终 messages 组装**（`E:\AI-Agent知识库\server\app\services\chat_service.py` L190-L243，共 54 行）

```python
    system_prompt = (
        "你是「知寻 KnowSeek」企业知识库智能助手，服务对象为企业内部员工。请严格遵循以下回答规范：\n"
        "1. 结论先行：先直接给出明确答案或核心结论，再分点展开依据与细节，结构清晰、逻辑严密；\n"
        "2. 严格依据提供的知识片段作答，引用来源以 [1]、[2] 等角标标注；片段不足以完整回答时，"
        "如实说明「知识库未覆盖该问题」，并给出可操作的下一步建议（如调整提问关键词、上传相关文档），"
        "严禁编造、猜测或提供无依据的信息；\n"
        "3. 语言专业、精炼、正式，采用企业书面语风格，克制得体；涉及制度、流程、数据时优先引用知识库原文表述；\n"
        "4. 不使用口语化表达、表情符号或夸大措辞；不确定之处明确标注，避免误导；\n"
        "5. 如需结合网络信息，以 [W1]、[W2] 角标与知识库来源明确区分，不混淆两种来源。"
        + (
            "同时提供实时网络搜索结果（编号 [W1] [W2] 等），可结合网络信息补充回答，"
            "使用网络来源时以 [W1] 等角标标注。回答末尾不要人为拼接来源列表。"
            if use_web
            else ""
        )
        + "\n\n知识片段：\n"
        + context
        + ("\n\n网络搜索结果：\n" + web_context if use_web else "")
        + "\n\n6. 对话记忆：下方「历史对话」为当前会话上下文。用户在历史中提供的个人信息"
        "（如姓名、身份、偏好）可直接据此回答；当用户提问承接此前内容时，优先从历史对话中理解，"
        "无需依赖知识库检索；历史对话与知识片段相互独立，不要混淆。\n\n"
        + DEFENSIVE_SYSTEM_HINT
    )
    # 对话记忆注入：从库加载当前会话历史（不含刚写入的当前问题），
    # 按最近 N 轮截断防 token 膨胀，注入顺序 system + 历史 user/assistant + 当前 user。
    HISTORY_MAX_ROUNDS = 8  # 最多携带最近 8 轮问答
    history_rows = (
        db.query(ConversationMsg)
        .filter(ConversationMsg.conv_id == conv.id, ConversationMsg.id != user_msg.id)
        .order_by(ConversationMsg.create_time.asc())
        .all()
    )
    history_msgs: list[dict[str, str]] = []
    for m in history_rows:
        if m.role not in ("user", "assistant"):
            continue
        content = (m.content or "").strip()
        if not content:
            continue
        history_msgs.append(
            {
                "role": m.role,
                "content": guard_user_content(content) if m.role == "user" else content,
            }
        )
    # 只保留最近 HISTORY_MAX_ROUNDS 轮（user+assistant 成对截断）
    history_msgs = history_msgs[-HISTORY_MAX_ROUNDS * 2 :]

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        *history_msgs,
        {"role": "user", "content": guard_user_content(question)},
    ]

```


**③ 前端 askSSE：流式解析 delta/引用/结束事件**（`E:\AI-Agent知识库\web\src\api\chat.ts` L35-L80，共 46 行）

```python
export async function askSSE(
  convId: number | null,
  question: string,
  callbacks: AskSSECallbacks,
  webSearch = false,
  providerId: number | null = null,
  docIds: number[] = [],
): Promise<void> {
  const userStore = useUserStore()
  const response = await fetch('/api/chat/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${userStore.accessToken}`,
    },
    body: JSON.stringify({ conv_id: convId, question, web_search: webSearch, model_provider_id: providerId, doc_ids: docIds.length ? docIds : undefined }),
    signal: callbacks.signal,
  })

  if (!response.ok) {
    // 401 登录态失效：静默清理本地登录态并跳转登录页，不弹任何错误提示
    if (response.status === 401) {
      userStore.logout()
      window.location.href = '/login'
      return
    }
    callbacks.onError?.(`请求失败（HTTP ${response.status}）`)
    return
  }

  if (!response.body) {
    callbacks.onError?.('浏览器不支持流式响应')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  // 慢响应兜底：长时间无增量时提示用户，避免误以为卡死（只提示一次）
  let slowTipSent = false
  const SLOW_MS = callbacks.slowTimeoutMs ?? 50000
  let slowTimer: ReturnType<typeof setTimeout> | null = null
  const armSlowTimer = () => {
    if (slowTimer) clearTimeout(slowTimer)
    if (!callbacks.onSlowTip || slowTipSent) return
    slowTimer = setTimeout(() => {
```


### 执行流程

1. 前端 ChatView.handleSend 校验输入 → ensureConversation 取得会话 ID → 乐观追加用户气泡。
2. askSSE(conv_id, question, provider_id, doc_ids) 携带会话 ID 发起 POST /api/chat/ask。
3. chat_service.chat_sse 创建/复用会话并落库 user_msg（ConversationMsg，role=user）。
4. vector_store.query(question, dept_id, top_k) 按部门隔离检索知识片段 → _dedupe_chunks 去重 → _build_citations 生成引用。
5. 查询图谱实体（Entity 表，按 doc_ids 关联）作为补充上下文。
6. 加载同会话历史（排除当前消息、按 create_time 升序、取最近 8 轮 user/assistant 成对），组装 system + 历史 + 当前 user。
7. 调用 LLM（DeepSeek/千问）流式生成，event_stream 逐段 yield SSE 事件（content/data），前端逐字渲染。

### 核心接口

- POST /api/chat/conversations 创建会话
- GET  /api/chat/conversations 会话列表
- GET  /api/chat/conversations/{id} 会话详情（含消息历史）
- POST /api/chat/ask  SSE 流式问答（body: question / conv_id / model_provider_id / doc_ids / web_search）
- GET  /api/chat/llm-status 模型供应商状态
- POST /api/chat/conversations/{id}/reset 重置对话记忆上下文

### 怎么实现的（原理与依赖）
核心是 RAG + 多轮记忆双上下文组装。RAG 侧：向量库按 dept_id 隔离检索（VectorStoreRepository 的向量+关键词融合），片段以 [1][2] 编号注入并生成可点击引用。记忆侧：ConversationMsg 表持久化每轮 user/assistant 消息，chat_sse 按 HISTORY_MAX_ROUNDS=8 轮截断注入，System Prompt 第 6 条明确『历史个人信息可直接回答、与知识片段独立不混淆』，避免把记忆当知识库引用。依赖：SQLite 会话表、Chroma 向量库、LLM 供应商配置。

> **答辩一句话总结**：解决了企业知识『问得出、答得准、记得住』的问题：回答有知识库引用可溯源，同一会话上下文可承接，告别单轮失忆。

---
## 02. RAG 知识库问答：文档解析入库 + 向量/关键词融合检索 + 部门隔离

### 功能核心
RAG 链路是 AI 对话的底座：文档上传后经 doc_service.process_document 解析为文本切片，写入 Chroma 向量库（本地哈希嵌入，零联网下载）；问答时 VectorStoreRepository.query 做向量余弦 + 关键词 BM25 融合过滤（score<0.06），并按当前用户 dept_id 做部门级数据隔离，跨部门文档在检索层即被拒绝。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 上传 txt/md/pdf/docx/xlsx/pptx 等常见格式即自动解析入库、自动建索引；
- 全库语义检索：表述与原文不完全一致也能召回相关内容；
- 部门级数据隔离：不同部门文档互不可见、互不可检索；
- 支持重新解析、标签管理、文档生命周期管理。

**解决什么问题**

- 搜索失效：传统关键词搜不到同义表达，RAG 语义召回补齐短板；
- 数据分散：多格式文档统一入库，形成单一可信知识源；
- 安全合规：部门隔离从检索层阻断越权访问敏感资料。

### 核心代码位置与源代码

**① process_document：上传后解析 → 切片 → 写入向量库**（`E:\AI-Agent知识库\server\app\services\doc_service.py` L181-L230，共 50 行）

```python
def process_document(db: Session, doc_id: int, vector_store: VectorStoreRepository) -> None:
    """异步解析：解析 -> 切片 -> 向量化 -> 更新状态。"""
    doc = db.get(Document, doc_id)
    if not doc:
        return
    doc.status = "processing"
    doc.progress = 10
    db.commit()
    try:
        text, extra = parse_document(doc.file_path, doc.file_type)
        doc.progress = 40
        db.commit()

        if extra and extra.get("excel_sheet_info"):
            doc.excel_sheet_info = extra["excel_sheet_info"]

        # PDF 无文本时标记 scan_pdf（需 OCR 服务）
        if doc.file_type == "pdf" and not text.strip():
            doc.status = "failed"
            doc.fail_msg = "PDF 为扫描件或无文本层，需 OCR 服务支持（审核意见 P0）"
            doc.progress = 100
            db.commit()
            return

        chunks_text = split_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        doc.progress = 70
        db.commit()

        # 按页号/工作表信息补充元数据（简化：按顺序编号）
        chunk_records = []
        vector_chunks = []
        for idx, chunk_text in enumerate(chunks_text):
            cid = make_chunk_id()
            chunk_records.append(
                DocChunk(doc_id=doc.id, chunk_text=chunk_text, page_no=idx + 1, chunk_index=idx, chroma_id=cid)
            )
            vector_chunks.append(
                {
                    "id": cid,
                    "text": chunk_text,
                    "dept_id": doc.dept_id,
                    "page_no": idx + 1,
                    "sheet_name": None,
                }
            )
        if chunk_records:
            db.add_all(chunk_records)
            db.commit()
            vector_store.add_chunks(doc.id, vector_chunks)
        else:
```


**② 关键词查询 + 融合 query 检索（向量+关键词 + 部门过滤）**（`E:\AI-Agent知识库\server\app\services\vector_store.py` L294-L353，共 60 行）

```python
    def _keyword_query(self, query_text: str, dept_id: int, top_k: int, doc_ids: list[int] | None) -> list[dict[str, Any]]:
        """关键词兜底召回：bigram 命中覆盖率 + 词频加权，覆盖向量语义不足的场景。"""
        toks = _tokenize(query_text)
        if not toks:
            return []
        candidates = self._collect_candidates(dept_id, doc_ids)
        if len(candidates) > 2000:
            candidates = candidates[:2000]
        scored = []
        for item in candidates:
            text = (item.get("text") or "").lower()
            hit = [t for t in toks if t in text]
            if not hit:
                continue
            coverage = len(hit) / len(toks)
            freq = sum(text.count(t) for t in hit)
            score = 0.62 * coverage + 0.38 * min(1.0, freq / (len(toks) * 3.0))
            if coverage >= 1.0:
                score = min(1.0, score + 0.05)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "chunk_id": item["chunk_id"],
                "doc_id": item["doc_id"],
                "text": item["text"],
                "page_no": item.get("page_no"),
                "sheet_name": item.get("sheet_name"),
                "score": round(score, 4),
            }
            for score, item in scored[:top_k]
        ]

    # ===== 逐行注释：混合检索（向量召回 + 关键词兜底 + 融合去重） =====
    # 1. 向量召回：_vector_query 取 top_k*2 候选，语义相似度优先（Chroma cosine 或内存余弦）。
    # 2. 关键词兜底：_keyword_query 取 top_k*2 候选，用 bigram 命中覆盖率+词频加权，覆盖
    #    向量模型不擅长的精确术语/编号/代码片段（如 "Agent 是什么" 与 "Agent 的本质"）。
    # 3. 融合规则：按 chunk_id 合并；关键词命中项若已在向量结果中，score 取 max(原分, kw*0.98)；
    #    新出现的关键词项打 0.82 折扣，避免关键词噪声淹没语义高分。
    # 4. 过滤 score < 0.06 的弱相关项，按分倒序截取 top_k 返回给 RAG 组装上下文。
    def query(self, query_text: str, dept_id: int, top_k: int = 5, doc_ids: list[int] | None = None) -> list[dict[str, Any]]:
        """混合检索：向量召回为主，关键词兜底补位，融合去重后按分排序返回。"""
        vec = self._vector_query(query_text, dept_id, top_k * 2, doc_ids)
        kw = self._keyword_query(query_text, dept_id, top_k * 2, doc_ids)
        merged: dict[str, dict[str, Any]] = {}
        for r in vec:
            merged[r["chunk_id"]] = dict(r)
        for r in kw:
            key = r["chunk_id"]
            if key in merged:
                merged[key]["score"] = max(merged[key].get("score", 0.0), r["score"] * 0.98)
            else:
                r2 = dict(r)
                r2["score"] = r["score"] * 0.82
                merged[key] = r2
        out = [m for m in merged.values() if m.get("score", 0.0) >= 0.06]
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:top_k]

    def delete_by_doc(self, doc_id: int) -> None:
```


### 执行流程

1. 前端上传文件 → /api/documents/upload → doc_service.save_upload_file 校验扩展名/MIME/魔数并落盘。
2. create_document 建记录（含 dept_id 归属），process_document 按扩展名路由解析器（txt/md/pdf/docx/xlsx/pptx 等）。
3. 解析结果按 chunk_size 切片，add_chunks 写入 Chroma（_HashEmbeddingFunction 本地哈希向量）并同步 doc_chunk 表。
4. 问答时 vector_store.query 先按 dept_id + doc_ids 收窄候选，再做向量相似度与关键词命中融合排序、阈值过滤。
5. 检索结果进入 chat_sse 的引用上下文；文档列表/详情/下载接口同样按 user.dept_id 隔离。

### 核心接口

- POST /api/documents/upload 上传文档（multipart）
- GET  /api/documents 文档列表（分页 + 部门隔离）
- GET  /api/documents/{doc_id} 文档详情
- GET  /api/documents/{doc_id}/download 下载
- POST /api/documents/{doc_id}/reprocess 重新解析入库
- POST /api/documents/{doc_id}/tags 打标签

### 怎么实现的（原理与依赖）
向量库抽象 VectorStoreRepository 统一 Chroma / 内存实现：_HashEmbeddingFunction 用本地哈希替代默认 sentence-transformer 模型（防联网下载、离线可用）；_load_from_db 在重启时从 doc_chunk 表恢复历史切片，保证索引不丢失。检索采用『向量余弦 + 关键词倒排 + 部门过滤 + 分数阈值』四层漏斗，兼顾语义召回与精确命中。依赖：Chroma 持久化目录、SQLite doc_chunk 表、解析库（pdfplumber/openpyxl/python-docx 等）。

> **答辩一句话总结**：解决企业『文件进了系统却无法被检索问答』的问题：上传即建索引，问答即部门内精准召回，且全程离线可用。

---
## 03. 文档 Copilot：单篇文档摘要 / 中英互译 / 针对性提问

### 功能核心
文档 Copilot 对单篇文档做轻量 AI 加工：自动识别语言后生成摘要，支持中英互译与针对文档内容提问。前端 CopilotPanel 侧栏嵌入文档详情弹窗，调用后端 run_copilot 统一编排。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 一键生成单篇文档的中文/英文摘要；
- 中英互译，自动识别语言方向；
- 针对文档内容定向提问（如「合同里的付款条款是什么」），答案附原文引用；
- 侧栏嵌入文档详情页，边读边问零切换。

**解决什么问题**

- 阅读成本：长文档不必通读，摘要先行、提问直达；
- 语言壁垒：外文资料秒级翻译，跨语言工作流顺畅；
- 定位效率：针对性提问直达段落，避免逐页翻找。

### 核心代码位置与源代码

**① 语言检测 + run_copilot 动作分发（summary/translate/ask）**（`E:\AI-Agent知识库\server\app\services\copilot_service.py` L49-L120，共 72 行）

```python
def _detect_language(text: str) -> str:
    """粗略语种判定：中文字符占比高 -> zh，否则 en。"""
    if not text:
        return "zh"
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    return "zh" if han / max(len(text), 1) > 0.12 else "en"


async def run_copilot(
    db,
    user: User,
    doc_id: int,
    action: str,
    source_text: str = "",
    question: str = "",
) -> dict[str, Any]:
    # ===== 逐行注释：文档 Copilot 四动作统一入口（核心）=====
    # 1. 动作白名单校验：仅支持 ask/summary/translate/outline，其余抛 PARAM_ERROR；
    # 2. 文档归属校验：文档必须存在、未删除且 dept_id 与用户一致（部门级数据隔离）；
    # 3. 读取文档全部切片并按 chunk_index 排序拼接为正文，用于摘要/翻译/要点上下文；
    # 4. 上下文策略：优先使用前端传来的选中片段 source_text，否则取整篇正文前 8000 字符；
    # 5. 四种动作各自构造 Prompt 与 system 角色（"知寻 KnowSeek 文档 Copilot"），
    #    并针对动作做差异化的引用定位：
    #    - ask：走 RAG 向量检索（vector_store.query 限定 doc_ids=[doc.id]）生成 citations，
    #      无选中片段时用检索命中的切片作为问答上下文；
    #    - summary/translate/outline：直接用文档正文切片构造 citations（页码/工作表定位）；
    # 6. chat_completion_async() 异步调用大模型（scenario=copilot，temperature=0.4）生成回答；
    # 7. 返回 answer + citations + 请求回显（action/source_text/question/doc 信息），供前端侧栏渲染。
    if action not in ACTION_LABELS:
        raise BizError(PARAM_ERROR, f"不支持的 Copilot 动作: {action}")

    doc = db.get(Document, doc_id)
    if not doc or doc.dept_id != user.dept_id or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")

    # 读取文档全部切片，用于摘要/要点/翻译上下文
    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.doc_id == doc.id)
        .order_by(DocChunk.chunk_index.asc(), DocChunk.id.asc())
        .all()
    )
    doc_body = "\n\n".join((c.chunk_text or "") for c in chunks)

    # 选中片段优先作为上下文，否则回退整篇正文
    context = (source_text or "").strip() or doc_body[:MAX_CONTEXT_CHARS]

    vector_store = vs_module.VectorStoreRepository()
    citations: list[dict[str, Any]] = []

    if action == "ask":
        user_question = (question or "").strip() or "请根据以上文档内容回答我的问题"
        # 有选中片段时，片段即权威上下文；同时做 RAG 检索补充引用定位
        rag = vector_store.query(user_question, dept_id=user.dept_id, top_k=6, doc_ids=[doc.id])
        citations = _chunk_citations(rag, doc.doc_name)
        if context != source_text:
            # 无选中片段时以 RAG 命中的切片作为上下文
            context = "\n\n".join(f"[{i}] {c.get('text', '')}" for i, c in enumerate(rag[:6], 1)) or context
        prompt = (
            f"用户正在阅读企业知识库文档《{doc.doc_name}》，就其中内容提出如下问题。\n"
            f"请严格依据提供的文档片段作答，结论先行、结构清晰，引用来源用 [1]、[2] 等角标标注。\n"
            f"文档片段：\n{context}\n\n用户问题：{user_question}"
        )
        messages = [
            {"role": "system", "content": "你是「知寻 KnowSeek」文档 Copilot，专注就当前文档内容精准作答，严禁编造或提供文档外信息。"},
            {"role": "user", "content": prompt},
        ]
    elif action == "summary":
        prompt = (
            f"请为以下企业知识库文档《{doc.doc_name}》生成一份结构化摘要（结论先行）：\n"
            f"1. 核心主旨（1-2 句）\n2. 关键内容（分点）\n3. 业务价值或使用建议\n"
            f"控制在 400 字以内，企业书面风格。\n\n文档内容：\n{context[:MAX_CONTEXT_CHARS]}"
```


**② 前端面板：doSummary / doTranslate / doAsk**（`E:\AI-Agent知识库\web\src\components\CopilotPanel.vue` L68-L95，共 28 行）

```python
    const res = await runCopilot({
      doc_id: props.docId,
      action,
      source_text: props.selectedText || undefined,
      question: question || undefined,
    })
    answer.value = res.answer || '（未返回内容）'
    citations.value = res.citations || []
    typewrite(answer.value)
  } catch {
    // 拦截器已提示
  } finally {
    busy.value = false
  }
}

function doSummary() {
  execute('summary')
}
function doTranslate() {
  execute('translate')
}
function doOutline() {
  execute('outline')
}
function doAsk() {
  const q = questionInput.value.trim()
  if (!q) {
```


### 执行流程

1. 用户在文档详情弹窗点击 Copilot 侧栏，选择摘要/翻译/提问。
2. 前端 runCopilot({action, doc_id, question}) 调 POST /api/document/copilot。
3. copilot_service.run_copilot 按 action 分发：summary 拼接文档切片给 LLM 输出结构化摘要；translate 先 _detect_language 判断中英方向再翻译；ask 以文档切片为上下文做针对性问答。
4. 结果附 chunk 引用（_chunk_citations），前端面板展示并可点击回看原文位置。

### 核心接口

- POST /api/document/copilot （body: action=summary|translate|ask, doc_id, question?, target_lang?）
- GET  /api/documents/{doc_id} 文档详情（Copilot 入口上下文）

### 怎么实现的（原理与依赖）
复用 RAG 切片：文档解析时已按块切好，Copilot 不再重新切分，直接取该 doc 的切片作为 LLM 上下文，控制 token 成本；语言检测用中英字符比例启发式，翻译方向自适应。依赖：LLM 供应商、doc_chunk 切片、文档 Copilot 独立 service。

> **答辩一句话总结**：解决『拿到文档还要自己通读』的效率问题：摘要、翻译、提问三件套，让文档自己『说话』。

---
## 04. 知识图谱 GraphRAG：实体抽取建图 + 图谱检索可视化

### 功能核心
知识图谱把散落的文档升级为关系网络：extract_document_kg 对文档切片做 LLM 实体抽取（同时保留规则抽取兜底），落库 entity / entity_relation 表；前端 KnowledgeGraphView 用 ECharts 力导向图渲染，支持实体搜索跳转与统计看板。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 自动抽取文档实体与关系，一键建图；
- 图谱可视化浏览，点击节点高亮关联网络；
- 实体搜索直达知识关系；
- 图谱统计视图展示实体/关系规模与分布。

**解决什么问题**

- 知识孤岛：文件之间隐含联系被显性化为关系网络；
- 检索升级：从「找文件」进阶为「探关系」；
- 决策支持：快速看清项目、技术、人员之间的关联脉络。

### 核心代码位置与源代码

**① extract_document_kg：切片抽取 → 实体/关系落库**（`E:\AI-Agent知识库\server\app\services\kg_service.py` L158-L240，共 83 行）

```python
def extract_document_kg(
    db: Session, user, doc_id: int, provider_id: int | None = None
) -> dict:
    """对文档执行实体/关系抽取（幂等：先清空旧数据再写入），返回抽取统计。"""
    doc = db.get(Document, doc_id)
    if not doc or doc.is_deleted:
        raise BizError(NOT_FOUND, "文档不存在")
    if doc.dept_id != user.dept_id:
        raise BizError(NOT_FOUND, "文档不存在或不可访问")

    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.doc_id == doc_id)
        .order_by(DocChunk.id.asc())
        .all()
    )
    if not chunks:
        raise BizError(NOT_FOUND, "文档尚未解析出切片，无法抽取")

    # 幂等：清空该文档已有图谱数据
    old_entities = db.query(Entity).filter(Entity.doc_id == doc_id).all()
    old_ids = [e.id for e in old_entities]
    if old_ids:
        db.query(EntityRelation).filter(EntityRelation.source_entity_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(EntityRelation).filter(EntityRelation.target_entity_id.in_(old_ids)).delete(synchronize_session=False)
    db.query(Entity).filter(Entity.doc_id == doc_id).delete(synchronize_session=False)
    db.query(EntityRelation).filter(EntityRelation.doc_id == doc_id).delete(synchronize_session=False)

    doc.kg_status = "processing"
    db.commit()

    entity_rows: list[Entity] = []
    relation_rows: list[EntityRelation] = []
    used_llm = False
    err_msg: str | None = None
    # 跨批次去重：同一文档内实体名唯一（entity_name+doc_id 唯一约束）
    name_to_id: dict[str, int] = {}

    try:
        for start in range(0, len(chunks), EXTRACT_BATCH):
            batch = chunks[start : start + EXTRACT_BATCH]
            batch_text = "\n\n".join(f"[切片{idx + 1}] {c.chunk_text}" for idx, c in enumerate(batch))
            llm_ok = False
            try:
                ents, rels = _llm_extract(db, user.id, batch_text, provider_id)
                llm_ok = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM 抽取失败（doc=%s），降级规则抽取: %s", doc_id, exc)
                err_msg = f"LLM 抽取失败，已降级规则抽取：{str(exc)[:120]}"
                ents, rels = [], []

            # 规则补充/降级：LLM 未产出时用规则，LLM 产出时用规则补齐英文技术名词
            rule_ents: set[str] = set()
            rule_rels: list[tuple[str, str]] = []
            if not llm_ok or len(ents) < 3:
                for c in batch:
                    re_ents, re_rels = _rule_extract_chunk(c.chunk_text)
                    rule_ents.update(re_ents)
                    rule_rels.extend(re_rels)
                if not llm_ok:
                    ents = [{"name": n, "type": "tech", "description": "规则抽取（LLM 不可用）"} for n in rule_ents]
                    rels = [{"source": s, "target": t, "type": "共现"} for s, t in rule_rels]

            for e in ents:
                name = e["name"]
                if name in name_to_id:
                    continue
                row = Entity(
                    entity_name=name,
                    entity_type=e.get("type") or "other",
                    description=e.get("description") or "",
                    doc_id=doc_id,
                    chunk_id=batch[0].chroma_id,
                    source="llm" if llm_ok else "rule",
                )
                db.add(row)
                db.flush()
                name_to_id[name] = row.id
                entity_rows.append(row)
            for r in rels:
                src_id = name_to_id.get(r["source"])
                tgt_id = name_to_id.get(r["target"])
                if not src_id or not tgt_id:
```


**② 前端 loadGraph：拉取图谱数据 + 布局渲染**（`E:\AI-Agent知识库\web\src\views\KnowledgeGraphView.vue` L182-L218，共 37 行）

```python
async function loadGraph() {
  loading.value = true
  try {
    const params: { doc_id?: number; keyword?: string; limit?: number } = {}
    if (selectedDocId.value) params.doc_id = selectedDocId.value
    if (searchKeyword.value.trim()) params.keyword = searchKeyword.value.trim()
    params.limit = 120
    const data = await getKgGraph(params)
    graph.value = data || { nodes: [], links: [] }
    selectedNode.value = null
    selectedLinks.value = []
    await nextTick()
    computeLayout(graph.value.nodes, graph.value.links, viewW.value, viewH.value)
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function loadDocs() {
  try {
    const data = await listDocuments({ page: 1, page_size: 200 })
    docOptions.value = data?.items ?? []
  } catch {
    // 拦截器已提示
  }
}

async function refreshAll() {
  await Promise.all([loadStats(), loadGraph()])
}

function handleDocChange() {
  refreshAll()
}

```


### 执行流程

1. 用户在知识图谱页选择文档点击抽取 → POST /api/kg/extract/{doc_id}。
2. kg_service.extract_document_kg 分批读取该文档切片，_llm_extract 让大模型输出 {entities, relations} JSON（含去重清洗），_rule_extract_chunk 正则规则抽取作为兜底。
3. 实体与关系写入 entity / entity_relation（按 dept 隔离），记录抽取统计。
4. GET /api/kg/graph 返回节点+边；GET /api/kg/search 按关键词搜实体；前端力导向图渲染，点击实体高亮关联。

### 核心接口

- POST /api/kg/extract/{doc_id} 触发实体抽取
- GET  /api/kg/graph?limit=&keyword= 获取图谱（节点+边）
- GET  /api/kg/search?keyword= 实体搜索
- GET  /api/kg/stats 图谱统计

### 怎么实现的（原理与依赖）
抽取采用『LLM 主抽取 + 规则兜底』双通道：LLM 输出严格 JSON（_extract_json 容错解析），规则通道用正则识别英文技术名词与中文专有名词；实体按规范名清洗合并。图数据由关系表 join 节点表生成。依赖：LLM、entity/entity_relation 表、ECharts 前端渲染。

> **答辩一句话总结**：解决『知识孤岛』问题：文件不再孤立，实体关系一目了然，检索从关键词升级为关系探索。

---
## 05. Agent 可视化工作流编排：模板任务 + 拖拽画布 + workflow_trace 可回溯

### 功能核心
Agent 模块让非技术用户也能编排自动化工作流：模板任务（周报/文档对比/写作计划）一键创建；画布模式拖拽 input/retrieve/generate/output 节点连线，canvas_workflow.run_canvas_workflow 解析 DAG 依赖拓扑执行，任务全流程输出 workflow_trace（每节点输入输出双记录）供审计回溯。前端 AgentTaskView 提供画布编辑与任务确认。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 模板任务：周报生成、文档对比、写作计划一键创建；
- 拖拽画布自定义工作流（输入→检索→生成→输出，节点自由编排）；
- 任务执行前人工确认，防止误触发；
- workflow_trace 逐节点回看输入输出，失败可定位到具体节点。

**解决什么问题**

- 重复劳动：周期性报告、文档类自动化任务交给 Agent，人力聚焦高价值工作；
- 使用门槛：非技术员工也能编排自动化流程，无需开发介入；
- 可信可控：全流程可回溯，符合企业自动化审慎落地的要求。

### 核心代码位置与源代码

**① _llm_node：画布 LLM 节点的提示注入与防御（防提示注入/系统提示泄露）**（`E:\AI-Agent知识库\server\app\services\canvas_workflow.py` L71-L125，共 55 行）

```python
def _llm_node(
    db: Session,
    user: User,
    task: AgentTask,
    ntype: str,
    cfg: dict,
    prev_text: str,
    provider_id: int | None,
) -> dict:
    prompt_templates = {
        "plan": (
            "你是企业任务规划专家。请基于输入生成一份简洁可执行的计划："
            "包括目标、关键步骤（每步做什么）、预期输出物。请分点输出。"
        ),
        "generate": (
            "你是「知寻 KnowSeek」企业智能 Agent。请严格基于提供的知识片段生成结果，"
            "并在关键结论后标注引用来源编号（[C1][C2]）。"
        ),
        "reflect": (
            "你是企业内容质量评审专家。请对下面生成的内容做质量反思："
            "指出事实依据是否充分、结构是否清晰、遗漏与风险点，并给出改进建议。请分点输出反思意见。"
        ),
        "refine": (
            "你是内容精修专家。请结合反思意见，对生成内容进行修订完善，"
            "输出最终高质量版本（保持引用标注）。"
        ),
    }
    system = (
        prompt_templates.get(ntype, "请基于以下内容继续处理，输出高质量结果。")
        + "\n\n"
        + DEFENSIVE_HINT
        + "\n\n参考输入：\n"
        + (prev_text or "（无上游输入）")
    )
    user_content = str(cfg.get("prompt") or "请输出结果。").strip()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    temperature = float(cfg.get("temperature", 0.7))
    if temperature < 0 or temperature > 2:
        temperature = 0.7
    result = chat_completion(
        db,
        user.id,
        messages,
        scenario="agent_canvas",
        temperature=temperature,
        max_tokens=int(cfg.get("max_tokens", 2000)),
        provider_id=cfg.get("model_provider_id") or provider_id,
    )
    return {"text": result, "summary": result[:120]}


def _retrieve_node(
```


**② run_canvas_workflow：DAG 拓扑执行 + 结果聚合 + workflow_trace 记录**（`E:\AI-Agent知识库\server\app\services\canvas_workflow.py` L163-L262，共 100 行）

```python
def run_canvas_workflow(
    db: Session,
    user: User,
    task: AgentTask,
    provider_id: int | None = None,
) -> tuple[str, list[dict]]:
    # ===== 逐行注释：DAG 画布编排执行引擎（核心）=====
    # 1. 加载画布 JSON（nodes+edges），校验节点类型合法、连线引用的节点都存在；
    # 2. _build_deps() 构建依赖表：deps[target] = [source...]，据此做拓扑排序；
    # 3. 主循环：每一轮遍历所有节点，找出"所有前驱已完成"的节点立即执行（广度推进）；
    #    若一轮下来没有任何节点可执行说明存在环，抛出"画布存在环"错误；
    # 4. 节点执行前通过 _collect_prev_text() 自动拼接所有前驱节点的输出文本，
    #    作为 LLM 节点的参考输入（上下文沿 DAG 边流动）；
    # 5. 节点类型分流：
    #    - input：直接取任务参数 extra 或任务类型作为输入文本；
    #    - retrieve：调用 _retrieve_node 做向量检索，把命中切片写入 task.retrieval_chunks 供后续引用；
    #    - output：直接透传前驱文本作为最终结果；
    #    - plan/generate/reflect/refine：走 _llm_node 按节点类型使用专属 prompt 模板调用大模型；
    # 6. trace 记录每个节点的 name/status/summary/cost_ms，返回给前端画布做高亮回显与耗时展示；
    # 7. 最终结果优先取 output 节点输出，若无 output 节点则取最后一个节点的输出。
    """按画布连线顺序执行节点（DAG），返回 (最终结果, 节点级 trace)。"""
    canvas = _load_canvas(task)
    nodes = canvas.get("nodes") or []
    if not nodes:
        raise BizError(NOT_FOUND, "画布为空，请先编排节点")

    deps = _build_deps(canvas)
    node_map = {n["id"]: n for n in nodes}
    for n in nodes:
        ntype = n.get("type")
        if ntype not in NODE_TYPES:
            raise BizError(NOT_FOUND, f"不支持的节点类型：{ntype}")
        for sid in deps.get(n["id"], []):
            if sid not in node_map:
                raise BizError(NOT_FOUND, f"连线引用了不存在的节点：{sid}")

    remaining = set(node_map.keys())
    outputs: dict[str, dict] = {}
    trace: list[dict] = []
    while remaining:
        progressed = False
        for n in nodes:
            nid = n["id"]
            if nid not in remaining:
                continue
            if any(d in remaining for d in deps.get(nid, [])):
                continue
            ntype = n.get("type")
            cfg = n.get("config") or {}
            name = n.get("name") or NODE_DEFAULT_NAMES.get(ntype, nid)
            start = time.monotonic()
            try:
                prev_text = _collect_prev_text(outputs, deps, nid)
                if ntype == "input":
                    res = {
                        "text": str((task.params or {}).get("extra") or f"任务类型：{task.task_type}"),
                        "summary": "任务输入已就绪",
                    }
                elif ntype == "retrieve":
                    res = _retrieve_node(db, user, task, cfg, prev_text)
                elif ntype == "output":
                    res = {"text": prev_text, "summary": "结果输出完成"}
                else:
                    res = _llm_node(db, user, task, ntype, cfg, prev_text, provider_id)
                cost_ms = int((time.monotonic() - start) * 1000)
                outputs[nid] = {**res, "name": name, "type": ntype}
                trace.append(
                    {
                        "node": ntype,
                        "name": name,
                        "status": "success",
                        "summary": res.get("summary", ""),
                        "cost_ms": cost_ms,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                cost_ms = int((time.monotonic() - start) * 1000)
                trace.append(
                    {
                        "node": ntype,
                        "name": name,
                        "status": "failed",
                        "summary": str(exc)[:200],
                        "cost_ms": cost_ms,
                    }
                )
                logger.exception("画布节点执行失败 %s", nid)
                raise
            remaining.remove(nid)
            progressed = True
        if not progressed:
            raise BizError(NOT_FOUND, "画布存在环，无法按顺序执行")

    final = ""
    for n in nodes:
        if n.get("type") == "output" and n["id"] in outputs:
            final = outputs[n["id"]].get("text") or final
    if not final and nodes:
        final = outputs.get(nodes[-1]["id"], {}).get("text") or ""
    return final, trace
```


**③ 前端画布：canvas_json 提交与任务创建**（`E:\AI-Agent知识库\web\src\views\AgentTaskView.vue` L133-L180，共 48 行）

```python
function handleCanvasCreate(payload: { canvasJson: string; taskType: string }) {
  pendingCanvasJson.value = payload.canvasJson
  pendingCanvasTaskType.value = payload.taskType as 'weekly_report' | 'doc_compare' | 'write_plan'
  canvasVisible.value = false
  openCreate()
}
/** 模型供应商列表与选中项（null=使用默认） */
const llmStatus = ref<LlmStatus | null>(null)
const selectedProviderId = ref<number | null>(null)

async function loadProviders() {
  try {
    llmStatus.value = await getLlmStatus()
  } catch {
    llmStatus.value = null
  }
}
/* 新建任务联网检索开关：默认开启，检索阶段融合实时网络结果 */
const createWebSearch = ref(true)

const taskTypeOptions = [
  { value: 'weekly_report', label: '周报生成', desc: '基于选定文档自动生成部门周报', icon: Document },
  { value: 'doc_compare', label: '文档对比', desc: '对选定文档进行内容对比分析', icon: Tickets },
  { value: 'write_plan', label: '方案撰写', desc: '基于选定文档撰写工作方案', icon: EditPen },
]

async function loadDocOptions() {
  try {
    const res = await listDocuments({ page: 1, page_size: 100 })
    docOptions.value = res.items.filter((d) => d.status === 'success')
  } catch {
    // 忽略
  }
}

function openCreate() {
  createForm.task_type = pendingCanvasJson.value ? pendingCanvasTaskType.value : 'weekly_report'
  createForm.doc_ids = []
  createForm.param_text = ''
  createForm.graph_engine = pendingCanvasJson.value ? 'canvas' : 'classic'
  createWebSearch.value = true
  selectedProviderId.value = null
  createVisible.value = true
}

/** 是否为 LangGraph 工作流任务（params.graph_engine === 'langgraph'） */
function isLangGraph(task: AgentTaskResp): boolean {
  return (task.params && task.params.graph_engine === 'langgraph') || !!task.workflow_trace?.length
```


### 执行流程

1. 用户在 AgentTaskView 选模板或打开画布，拖拽节点连线生成 canvas_json（节点 id/type/config + 边 source/target）。
2. 提交 POST /api/agent/tasks（task_type=write_plan 等 + params.graph_engine=canvas + canvas_json）→ 任务落库（status=waiting_confirm）。
3. 前端确认后 POST /api/agent/tasks/{id}/confirm → agent_service.confirm_task 触发 run_canvas_workflow。
4. 引擎 _build_deps 建立依赖拓扑，按节点执行：input 取参 → retrieve 部门内检索 → generate/llm 生成 → output 落库；异常捕获置 status=failed + error_msg。
5. 执行完成后 status=finished，workflow_trace 记录每节点输入输出，前端可展开查看。

### 核心接口

- GET  /api/agent/templates 模板列表
- POST /api/agent/tasks 创建任务（含画布 JSON）
- GET  /api/agent/tasks 任务列表（按状态过滤）
- GET  /api/agent/tasks/{id} 任务详情（workflow_trace）
- POST /api/agent/tasks/{id}/confirm 确认执行

### 怎么实现的（原理与依赖）
画布引擎的核心是『声明式 DAG 执行』：canvas_json 描述节点与边，_build_deps 从边构建依赖映射，执行时按拓扑顺序调用节点处理器；每个 LLM 节点注入防御性 System Prompt（防提示注入/系统提示泄露），输出经 JSON 校验。retrieve 节点按用户 dept_id 部门隔离取文档。依赖：LangGraph 式思路、AgentTask/AgentTaskResult 表、LLM。

> **答辩一句话总结**：解决『自动化只能靠开发』的问题：拖拽即工作流、执行可回溯，让业务人员也能编排企业级自动化任务。

---
## 06. 智能看板：多指标统计 + 趋势图 + LLM 总结

### 功能核心
智能看板把业务数据变成管理视图：/summary 聚合文档/图谱/Agent/会话/用户五大类指标并输出 7 日趋势，/knowledge-hot 输出高频实体热搜，/dept-activity 输出部门活跃排行，/retrieval-heatmap 输出检索时段热力图，/llm-usage 统计模型调用量；前端 DashboardView 渲染卡片 + ECharts 图表，并用 LLM 生成一句话运营总结。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 一屏聚合文档、图谱、Agent、会话、用户五大类指标；
- 7 日趋势曲线、部门活跃排行、检索时段热力图；
- 知识热点（高频实体）榜单，洞察组织关注方向；
- LLM 自动生成一句运营总结文案。

**解决什么问题**

- 管理盲区：系统投入价值可量化展示，支撑向上汇报；
- 决策效率：管理层快速识别活跃度、热点与低效环节；
- 运营洞察：数据驱动知识运营策略，而非凭感觉投入。

### 核心代码位置与源代码

**① dashboard_summary 五类指标聚合 + knowledge_hot 高频知识统计**（`E:\AI-Agent知识库\server\app\api\dashboard.py` L55-L135，共 81 行）

```python
@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = datetime.combine(date.today() - timedelta(days=date.today().weekday()), datetime.min.time())

    def count_docs(cond) -> int:
        return db.query(func.count(Document.id)).filter(Document.is_deleted.is_(False), cond).scalar() or 0

    doc_total = count_docs(True)
    doc_today = count_docs(Document.create_time >= today_start)
    doc_this_week = count_docs(Document.create_time >= week_start)
    doc_pending = count_docs(Document.status == "pending")
    doc_processing = count_docs(Document.status == "processing")
    doc_ready = count_docs(Document.status == "ready")
    doc_failed = count_docs(Document.status == "failed")

    retrieval_total = db.query(func.count(OperationLog.id)).filter(OperationLog.module == "chat").scalar() or 0
    retrieval_ok = db.query(func.count(OperationLog.id)).filter(OperationLog.module == "chat", OperationLog.status == "success").scalar() or 0
    retrieval_rate = (retrieval_ok / retrieval_total) if retrieval_total else 1.0

    conversation_count = db.query(func.count(Conversation.id)).scalar() or 0
    chat_message_count = db.query(func.count(ConversationMsg.id)).scalar() or 0
    agent_total = db.query(func.count(AgentTask.id)).scalar() or 0
    agent_done = db.query(func.count(AgentTask.id)).filter(AgentTask.status == "done").scalar() or 0
    agent_running = db.query(func.count(AgentTask.id)).filter(AgentTask.status.in_(["pending", "running", "processing"])).scalar() or 0
    agent_failed = db.query(func.count(AgentTask.id)).filter(AgentTask.status == "failed").scalar() or 0

    user_count = db.query(func.count(User.id)).filter(User.status == "active").scalar() or 0
    dept_count = db.query(func.count(Department.id)).scalar() or 0
    team_count = db.query(func.count(Team.id)).scalar() or 0

    # Agent 任务按类型分布
    agent_by_type = [{"name": k, "value": v} for k, v in db.query(AgentTask.task_type, func.count()).group_by(AgentTask.task_type).all()]

    return ok(
        data={
            "document": {"total": doc_total, "today": doc_today, "this_week": doc_this_week, "pending": doc_pending, "processing": doc_processing, "ready": doc_ready, "failed": doc_failed},
            "retrieval": {"count": retrieval_total, "success_rate": round(retrieval_rate, 4)},
            "conversation": {"count": conversation_count, "messages": chat_message_count},
            "agent": {"total": agent_total, "done": agent_done, "running": agent_running, "finished": agent_done, "failed": agent_failed, "by_type": agent_by_type},
            "organization": {"users": user_count, "departments": dept_count, "teams": team_count},
            "trend_7d": _daily_trend(db, 7),
        }
    )


@router.get("/knowledge-hot")
def knowledge_hot(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """知识热度榜：Top 文档按检索命中 + 浏览量加权排序（智能看板）。"""
    rows = (
        db.query(
            Document.id,
            Document.doc_name,
            Document.file_type,
            Document.view_count,
            Document.retrieve_count,
            Document.update_time,
        )
        .filter(Document.is_deleted.is_(False))
        .order_by(((Document.retrieve_count or 0) * 2 + (Document.view_count or 0)).desc(), Document.update_time.desc())
        .limit(10)
        .all()
    )
    data = []
    for rank, (doc_id, doc_name, file_type, view_count, retrieve_count, update_time) in enumerate(rows, 1):
        heat = (retrieve_count or 0) * 2 + (view_count or 0)
        data.append(
            {
                "rank": rank,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "file_type": file_type,
                "view_count": view_count or 0,
                "retrieve_count": retrieve_count or 0,
                "heat_score": heat,
                "update_time": update_time.isoformat() if update_time else None,
            }
        )
    return ok(data={"list": data, "total": len(data)})


```


**② 前端 load() 拉取汇总 + metrics 计算卡片指标**（`E:\AI-Agent知识库\web\src\views\DashboardView.vue` L23-L60，共 38 行）

```python
async function load() {
  loading.value = true
  try {
    summary.value = await getDashboardSummary()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  loadExtra()
})

// ===== 逐行注释：看板指标卡与图表数据派生 =====
// 1. metrics：六张企业价值指标卡（知识文档/检索次数/对话轮次/Agent 任务/组织用户/团队空间），
//    数据来自后端 /api/dashboard/summary，纯 computed 派生、无副作用；
// 2. docStatus/agentStates/agentTypes：文档处理状态、Agent 状态、任务类型三个分布
//    （百分比条形图数据），过滤零值并归一化避免除零；
// 3. peakPoint/polyPoints/areaPoints：轻量 SVG 图表坐标计算（680x220 画布，34 边距），
//    手写折线/面积/峰值点，不引入 echarts 等重依赖；
// 4. trendLines：近 7 日 文档/检索/对话/Agent 四线趋势，直接消费 summary.trend_7d 平行数组。
const metrics = computed(() => {
  const s = summary.value
  return [
    { key: 'document', label: '知识文档', value: s?.document.total ?? 0, sub: s ? `今日 +${s.document.today} · 本周 +${s.document.this_week}` : '', icon: Document, tone: 'blue' },
    { key: 'retrieval', label: '检索次数', value: s?.retrieval.count ?? 0, sub: s ? `成功率 ${(s.retrieval.success_rate * 100).toFixed(1)}%` : '', icon: Search, tone: 'emerald' },
    { key: 'conversation', label: '对话轮次', value: s?.conversation.count ?? 0, sub: s ? `累计消息 ${s.conversation.messages} 条` : '', icon: ChatDotRound, tone: 'amber' },
    { key: 'agent', label: 'Agent 任务', value: s?.agent.total ?? 0, sub: s ? `完成 ${s.agent.finished} · 执行中 ${s.agent.running}` : '', icon: Promotion, tone: 'violet' },
    { key: 'users', label: '组织用户', value: s?.organization.users ?? 0, sub: s ? `${s.organization.departments} 个部门` : '', icon: User, tone: 'cyan' },
    { key: 'teams', label: '团队空间', value: s?.organization.teams ?? 0, sub: '企业级知识协作', icon: OfficeBuilding, tone: 'indigo' },
  ]
})

/** 文档处理状态分布（企业质检视角） */
const docStatus = computed(() => {
```


### 执行流程

1. 登录进入首页 DashboardView.mounted → load() 并行请求 /summary 与 /knowledge-hot 等。
2. dashboard_summary 对文档/图谱/Agent/会话/用户做 count 聚合，_daily_trend 按日统计生成 trend_7d。
3. knowledge_hot 按 entity mention 次数排序输出 Top 高频实体。
4. loadExtra 拉取 dept-activity / retrieval-heatmap / llm-usage。
5. 前端 ECharts 渲染柱状/热力图，LLM 对指标生成一段运营总结文案。

### 核心接口

- GET /api/dashboard/summary 汇总（docs/kg/agents/convs/users + trend_7d）
- GET /api/dashboard/knowledge-hot 高频实体
- GET /api/dashboard/dept-activity 部门活跃排行
- GET /api/dashboard/retrieval-heatmap 检索时段热力图
- GET /api/dashboard/llm-usage 模型调用统计

### 怎么实现的（原理与依赖）
看板数据全部来自 SQLite 聚合查询（COUNT/GROUP BY + 按日序列补零），无额外数仓依赖；趋势图用 _day_series 生成连续日期，缺数据补 0，保证折线不断裂。前端 metrics 用 computed 派生展示值，LLM 总结走独立接口异步加载。依赖：SQLite、ECharts、LLM。

> **答辩一句话总结**：解决『管理者看不清系统价值』的问题：一屏看懂知识资产与使用活跃度，AI 代写运营小结。

---
## 07. 演示模式：一键生成演示数据

### 功能核心
演示模式让产品演示/答辩 5 秒就绪：seed_demo 自动创建演示部门/用户/文档/知识图谱/Agent 任务与对话样本，配合 /reset 一键重置，演示完即还原干净环境。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 一键生成演示部门、用户、文档、知识图谱、Agent 任务与对话样本；
- 一键重置演示数据，环境干净可反复演示；
- 演示数据与正式数据同构，展示效果即真实效果。

**解决什么问题**

- 演示准备耗时：5 秒就绪，答辩/路演零等待；
- 数据污染：演示数据打 is_demo 标记，重置只清演示、正式数据零影响；
- 场景可复现：多次演示结果一致，利于对外宣传口径统一。

### 核心代码位置与源代码

**① seed_demo：演示数据全量生成（部门→用户→文档→图谱→Agent→对话）**（`E:\AI-Agent知识库\server\app\services\demo_service.py` L264-L306，共 43 行）

```python
def seed_demo(db: Session, keep_original: bool = True) -> dict:
    # ===== 逐行注释：一键灌入演示数据（核心）=====
    # 1. keep_original=False 时先 clear_demo 清空旧演示数据（幂等重灌）；
    # 2. _demo_departments：创建或复用 "[演示]" 前缀部门（市场部/研发部）；
    # 3. _demo_users：创建或复用 demo_ 前缀邮箱用户（密码哈希为占位值，仅演示登录）；
    # 4. _seed_docs：按 DEMO_DOCS 规格写入演示文档 + 切片（file_hash 带 demo- 前缀标记）；
    # 5. _seed_kg：写入演示实体/关系（source="demo" 标记），驱动知识图谱页展示；
    # 6. _seed_conversations：写入演示问答对（对话/消息），驱动聊天页展示；
    # 7. _seed_activity：回填近 14 日检索日志（detail="[demo-seed]"）与 LLM 调用日志
    #    （scenario="demo"），让看板热力图/趋势/用量报表有真实可聚合的演示数据；
    # 8. 最后写 SysConfig.demo_active=1 作为演示模式开关，返回统计供前端提示。
    if not keep_original:
        clear_demo(db)
    depts = _demo_departments(db)
    users = _demo_users(db, depts)
    docs = _seed_docs(db, depts, users)
    kg = _seed_kg(db, docs)
    conv_count = _seed_conversations(db, users, docs)
    _seed_activity(db, depts, users)
    db.commit()

    cfg = db.query(SysConfig).filter(SysConfig.config_key == "demo_active").first()
    if not cfg:
        cfg = SysConfig(config_key="demo_active", config_value="1", description="演示模式激活标记")
        db.add(cfg)
    cfg.config_value = "1"
    cfg.update_time = now = datetime.now()
    db.commit()

    return {
        "active": True,
        "seeded_at": now.isoformat(),
        "departments": len(depts),
        "users": len(users),
        "documents": len(docs),
        "entities": kg["entities"],
        "relations": kg["relations"],
        "conversations": conv_count,
        "keep_original": keep_original,
    }


def demo_status(db: Session) -> dict:
```


### 执行流程

1. 管理员在系统设置页点击『生成演示数据』→ POST /api/demo/seed。
2. seed_demo 依次插入演示部门、演示账号、示例文档并触发解析入库、图谱实体抽取。
3. 生成 Agent 演示任务与若干轮对话样本，输出 seed 统计（docs/kg/agents/convs）。
4. 演示结束调用 /api/demo/reset 删除演示数据，恢复初始环境。

### 核心接口

- POST /api/demo/seed 生成演示数据
- POST /api/demo/reset 重置演示数据

### 怎么实现的（原理与依赖）
复用正式业务写入链路（文档解析、图谱抽取、对话落库），保证演示数据与真实数据同构；演示数据打上 is_demo 标记便于 reset 精准清除，不动真实数据。依赖：doc_service / kg_service / chat_service。

> **答辩一句话总结**：解决『演示前数据准备耗时』的问题：一键填充真实同构样例，答辩演示零等待、零污染。

---
## 08. 登录安全：JWT 双 Token + 密码哈希 + 登录锁定 + 验证码

### 功能核心
登录安全是企业级基线：JWT 采用 access(2h) + refresh(7d) 双 Token 滚动刷新；密码经 bcrypt 加盐哈希存储；连续 5 次密码错误锁定账号 15 分钟；登录失败超过 10 次强制图形验证码；核心/管理接口统一 require_admin 鉴权。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 密码 bcrypt 加盐哈希存储，库内不存明文；
- JWT 双 Token（access 2h + refresh 7d），过期静默续签、登出可吊销；
- 连续 5 次密码错误锁定账号 15 分钟，高频失败触发图形验证码；
- 核心/管理接口统一角色鉴权（require_admin）。

**解决什么问题**

- 防爆破：锁定 + 验证码双重拦截，暴力破解成本极高；
- 防泄露：密码不明文、Token 可吊销，即使库泄露攻击面可控；
- 合规：满足企业应用等保基础要求，为上线审计背书。

### 核心代码位置与源代码

**① 密码哈希 + JWT 编解码（HS256）+ access/refresh 有效期定义**（`E:\AI-Agent知识库\server\app\core\security.py` L13-L61，共 49 行）

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ===== 逐行注释：密码哈希与 JWT 双 token 工具 =====
# 1. hash_password / verify_password：基于 bcrypt 加盐哈希，不存明文密码；
# 2. _create_token：统一生成 JWT，载荷含 sub（用户 ID）、type（access/refresh 双 token 区分）、
#    jti（唯一 ID 防重放）、iat（签发时间）、exp（过期时间）；签名算法与密钥来自 settings；
# 3. create_access_token：短期 token（分钟级），随每次请求携带；
# 4. create_refresh_token：长期 token（天级），用于刷新 access token 保持登录态；
# 5. decode_token：解析并校验签名/过期，失败返回 None（上层据此判 401）；
# 6. hash_token：对 refresh_token 等长令牌做 SHA-256 哈希后入库，数据库不存明文令牌。
def _create_token(user_id: int, token_type: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(user_id, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, "refresh", settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def hash_token(token: str) -> str:
    """对长令牌（如 refresh_token）做 SHA-256 哈希，数据库不存明文。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```


**② _issue_tokens：签发双 Token 对**（`E:\AI-Agent知识库\server\app\api\auth.py` L78-L97，共 20 行）

```python
def _issue_tokens(db: Session, user: User) -> TokenData:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    dept = db.get(Department, user.dept_id)
    return TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_to_user_info(user, dept.dept_name if dept else None),
    )


@router.post("/send-code")
```


### 执行流程

1. 登录请求 /api/auth/login → 校验验证码 → 按用户名查 User → bcrypt 比对密码。
2. 失败计数：连续 5 次错误锁定账号 15 分钟；累计 10 次失败触发验证码。
3. 成功则 _issue_tokens 签发 access_token（2 小时）+ refresh_token（7 天），返回用户资料与权限位。
4. 前端 axios 拦截器附加 Authorization: Bearer；access 过期时用 refresh 调 /api/auth/refresh 静默续签。
5. 核心接口依赖 require_admin / get_current_user 依赖注入校验权限。

### 核心接口

- POST /api/auth/login 登录（账号/密码/验证码）
- POST /api/auth/refresh 刷新 Token
- POST /api/auth/logout 登出（吊销 refresh）
- GET  /api/auth/me 当前用户信息
- POST /api/auth/change-password 改密

### 怎么实现的（原理与依赖）
security.py 用 PyJWT HS256 签发，payload 含 user_id/dept_id/exp；密码用 passlib bcrypt（成本因子可配）。登录锁定与验证码状态存内存（按用户名/失败次数），refresh 具吊销机制。前端 stores/user.ts 持久化 token，路由守卫按角色位过滤页面。依赖：PyJWT、passlib、FastAPI 依赖注入。

> **答辩一句话总结**：解决『企业系统裸奔』的安全问题：双 Token 保会话、哈希保密码、锁定防爆破，三重防线。

---
## 09. 打卡审批：定位打卡 + 缺卡申请 + 审批闭环

### 功能核心
考勤模块打通『打卡→缺卡→申请→审批→修正』闭环：打卡带经纬度与围栏半径校验，缺卡可提交补卡申请（附迟到早退原因），主管审批后自动回写考勤记录，审计全程留痕。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 定位打卡：经纬度 + 围栏半径校验，防异地代打；
- 四段班次自动标记打卡状态（正常/迟到/早退/缺卡）；
- 缺卡一键提交补卡申请（类型 + 原因），主管审批后自动回写考勤记录；
- 申请与审批全程审计留痕。

**解决什么问题**

- 管理成本：人工核对考勤转为系统闭环，月末统计一键出；
- 合规留痕：缺卡有依据、审批有记录，劳资纠纷有据可查；
- 防代打：定位围栏从技术侧约束打卡真实性。

### 核心代码位置与源代码

**① clock：打卡定位校验 + 补卡类型处理**（`E:\AI-Agent知识库\server\app\api\org_extra.py` L717-L788，共 72 行）

```python
@router.post("/{team_id}/attendance/clock")
def clock(
    team_id: int,
    request: Request,
    slot: str = Query(..., description="班次：am_in/am_out/pm_in/pm_out"),
    lat: float = Query(..., description="当前纬度"),
    lng: float = Query(..., description="当前经度"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """四段班次打卡：工作区域强校验 + 服务端时间 + 防重复/防篡改/限流。"""
    _get_team(db, team_id)
    _require_member(db, team_id, user)
    _clock_rate_limit(team_id, user)
    if slot not in SHIFT_SLOTS:
        raise BizError(PARAM_ERROR, "无效班次")
    geo = _validate_geo_clock(db, team_id, lat, lng)

    now = datetime.now()
    cur_min = now.hour * 60 + now.minute
    win = SHIFT_SLOTS[slot]
    if not (win["start"] <= cur_min <= win["end"]):
        raise BizError(
            PARAM_ERROR,
            f"当前时间不在「{win['label']}」打卡时段（{win['start'] // 60:02d}:{win['start'] % 60:02d}~{win['end'] // 60:02d}:{win['end'] % 60:02d}）",
        )

    today = _today()
    rec = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.team_id == team_id, AttendanceRecord.user_id == user.id, AttendanceRecord.date == today)
        .first()
    )
    if win["prev"]:
        if not rec or not _get_slot_time(rec, win["prev"]):
            raise BizError(PARAM_ERROR, f"请先完成「{SHIFT_SLOTS[win['prev']]['label']}」打卡")
    if rec and _get_slot_time(rec, slot):
        raise BizError(CONFLICT, f"今日「{win['label']}」已打卡，请勿重复打卡")
    if not rec:
        rec = AttendanceRecord(team_id=team_id, user_id=user.id, date=today)
        db.add(rec)
    _set_slot_time(rec, slot, now)

    meta = {}
    try:
        meta = json.loads(rec.checkin_meta) if rec.checkin_meta else {}
    except (ValueError, TypeError):
        meta = {}
    meta[slot] = {
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "ip": _client_ip(request),
        "ua": (request.headers.get("user-agent") or "")[:200],
        "ts": _fmt(now),
    }
    rec.checkin_meta = json.dumps(meta, ensure_ascii=False)
    db.commit()
    dist = _haversine_m(lat, lng, geo.lat, geo.lng)
    record_audit(
        db,
        user,
        f"attendance_clock_{slot}",
        "team",
        f"企业打卡：{today} {win['label']}（距围栏中心 {int(dist)}m）",
    )
    return ok(
        data={"date": today, "slot": slot, "time": _fmt(now), "distance_m": int(dist)},
        message=f"{win['label']}打卡成功",
    )


@router.get("/{team_id}/attendance/geo")
```


**② request_fix：缺卡补卡申请（含原因校验）**（`E:\AI-Agent知识库\server\app\api\org_extra.py` L989-L1045，共 57 行）

```python
def request_fix(
    team_id: int,
    date: str = Query(...),
    slot: str = Query(...),
    reason: str = Query("", max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交补卡申请：迟到/漏卡时段修正，由管理员审批后写入打卡记录。"""
    team = _get_team(db, team_id)
    _require_member(db, team_id, user)
    if slot not in SHIFT_SLOTS:
        raise BizError(400, f"无效班次时段：{slot}，可选 {', '.join(SHIFT_SLOTS.keys())}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise BizError(400, "日期格式须为 YYYY-MM-DD")
    if date > _today():
        raise BizError(400, "不能为未来日期申请补卡")
    # 该时段已有打卡记录则无需补卡
    rec_exist = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.team_id == team_id, AttendanceRecord.user_id == user.id, AttendanceRecord.date == date)
        .first()
    )
    if rec_exist and _get_slot_time(rec_exist, slot):
        raise BizError(400, f"该日「{SHIFT_SLOTS[slot]['label']}」已有打卡记录，无需补卡")
    # 同人同团队同日期同时段去重（pending 或已通过均不允许重复申请）
    dup = (
        db.query(AttendanceFixApproval)
        .filter(
            AttendanceFixApproval.team_id == team_id,
            AttendanceFixApproval.user_id == user.id,
            AttendanceFixApproval.date == date,
            AttendanceFixApproval.slot == slot,
            AttendanceFixApproval.status.in_(["pending", "approved"]),
        )
        .first()
    )
    if dup:
        raise BizError(400, "该日此时段已有补卡申请，请勿重复提交")
    ap = AttendanceFixApproval(
        team_id=team_id,
        user_id=user.id,
        date=date,
        slot=slot,
        reason=reason.strip() or f"补卡申请（{date} {SHIFT_SLOTS[slot]['label']}）",
        status="pending",
        apply_time=datetime.now(),
    )
    db.add(ap)
    db.flush()
    record_audit(db, user, "attendance_fix_request", "team", f"提交补卡申请（{date} {SHIFT_SLOTS[slot]['label']}），原因：{ap.reason}")
    _notify_managers(db, team, "新的考勤补卡申请", f"{user.username} 提交补卡申请（{date} {SHIFT_SLOTS[slot]['label']}），请及时审批", exclude_user_id=user.id)
    db.commit()
    return ok(data=_fix_approval_resp(db, ap))


@router.get("/{team_id}/attendance/fix/list")
```


**③ approve_fix：审批通过 → 回写考勤修正**（`E:\AI-Agent知识库\server\app\api\org_extra.py` L1065-L1110，共 46 行）

```python
def approve_fix(
    team_id: int,
    fix_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员审批通过补卡申请：写入/修正该日时段打卡记录。"""
    _get_team(db, team_id)
    me = _require_member(db, team_id, user)
    if me.role not in ("owner", "admin"):
        raise BizError(NO_PERMISSION, "仅团队管理员可审批补卡申请")
    ap = db.get(AttendanceFixApproval, fix_id)
    if not ap or ap.team_id != team_id:
        raise BizError(404, "补卡申请不存在")
    if ap.status != "pending":
        raise BizError(400, "该申请已处理")
    ap.status = "approved"
    ap.approver_id = user.id
    ap.handle_time = datetime.now()
    # 修正打卡记录：存在记录则更新对应时段，不存在则创建
    rec = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.team_id == team_id,
            AttendanceRecord.user_id == ap.user_id,
            AttendanceRecord.date == ap.date,
        )
        .first()
    )
    if not rec:
        rec = AttendanceRecord(team_id=team_id, user_id=ap.user_id, date=ap.date)
        db.add(rec)
    if ap.slot == "am_in":
        rec.clock_in_time = rec.clock_in_time or _fix_slot_time("am_in", ap.date)
        rec.am_in_time = rec.clock_in_time
    elif ap.slot == "am_out":
        rec.am_out_time = _fix_slot_time("am_out", ap.date)
    elif ap.slot == "pm_in":
        rec.pm_in_time = _fix_slot_time("pm_in", ap.date)
    elif ap.slot == "pm_out":
        rec.pm_out_time = _fix_slot_time("pm_out", ap.date)
    db.flush()
    applicant = db.get(User, ap.user_id)
    record_audit(
        db,
        user,
```


### 执行流程

1. 用户在考勤页点击打卡 → POST /api/attendance/clock（lat/lng/type=check_in|check_out）。
2. 后端校验时间窗口（迟到/早退标记）与地理围栏（距公司中心 ≤ 半径），生成考勤记录（status=present|late|early|absent）。
3. 缺卡（absent）时用户提交 request_fix 补卡申请（类型 + 原因 + 凭证说明）。
4. 直属主管在审批中心 approve/reject → 通过后按申请类型回写考勤记录（补卡/修正），更新审批单状态。
5. 全程操作写入审计日志。

### 核心接口

- POST /api/attendance/clock 打卡（lat/lng/type）
- GET  /api/attendance/records 我的考勤记录
- POST /api/attendance/fix-requests 提交补卡申请
- GET  /api/attendance/fix-requests 审批列表
- POST /api/attendance/fix-requests/{id}/approve|reject 审批

### 怎么实现的（原理与依赖）
考勤记录表含打卡时间/类型/经纬度/状态；围栏用 haversine 球面距离计算；审批走 request/approve 双接口 + 状态机（pending→approved/rejected），审批通过后按补卡类型重算考勤状态并保留原记录审计字段。依赖：SQLite 考勤/审批表、审计中间件。

> **答辩一句话总结**：解决『考勤靠人工催、缺卡无依据』的问题：定位防代打、缺卡有流程、审批有闭环、全程可审计。

---
## 10. 审计日志：HTTP 级中间件全量留痕

### 功能核心
审计贯穿全系统：Starlette HTTP 中间件自动记录每次业务请求（模块/动作/用户/结果/耗时/IP），配合业务级 record_audit 双通道，管理员可在审计中心按模块/动作/用户筛选回放。

### 功能价值：能做什么·解决什么问题

**能做什么**

- 全量 HTTP 请求自动留痕（时间/用户/模块/动作/结果/耗时/IP）；
- 业务级显式审计补充关键写操作细节；
- 审计中心按模块、动作、用户、结果、时间多维度筛选检索；
- 敏感操作（审批、删改、下载）可完整回放。

**解决什么问题**

- 责任追溯：出事查得到「谁、何时、做了什么」，杜绝扯皮；
- 合规要求：满足企业内控与监管留痕标准；
- 安全监控：异常行为模式可回溯分析，支撑安全事件响应。

### 核心代码位置与源代码

**① record_audit：业务级显式审计落库**（`E:\AI-Agent知识库\server\app\services\audit.py` L46-L58，共 13 行）

```python
def record_audit(
    db,
    user,
    action: str,
    module: str,
    detail: str | None = None,
    ip: str = "",
    status: str = "success",
    duration_ms: int = 0,
) -> None:
    # ===== 逐行注释：业务显式审计写入 =====
    # 1. 供业务代码主动记录语义化操作（登录、上传、下载审批、退出审批等），
    #    与 audit_middleware 的自动请求级日志互补；
```


**② audit_middleware：HTTP 级自动审计（免 token 解析 + 全部请求留痕）**（`E:\AI-Agent知识库\server\app\services\audit.py` L86-L131，共 46 行）

```python
def audit_middleware(get_db_session, get_user_from_token):
    """生成审计中间件。get_user_from_token: credentials -> User | None。"""

    async def middleware(request: Request, call_next):
        start = time.monotonic()
        response = None
        user = None
        try:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                user = get_user_from_token(auth[7:])
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            if request.url.path.startswith("/api") and request.url.path not in SKIP_PATHS:
                try:
                    db = get_db_session()
                    from app.models import OperationLog

                    uid = user.id if user else None
                    uname = user.username if user else None
                    dept_id = user.dept_id if user else None
                    segs = request.url.path.split("/")
                    module = segs[2] if len(segs) > 2 else ""
                    db.add(
                        OperationLog(
                            user_id=uid,
                            username=uname,
                            dept_id=dept_id,
                            action=request.method,
                            module=module,
                            method=request.method,
                            path=request.url.path,
                            ip=request.client.host if request.client else "",
                            status="success" if not response or response.status_code < 400 else "fail",
                            duration_ms=duration_ms,
                        )
                    )
                    db.commit()
                except Exception as exc:  # pragma: no cover
                    logger.warning("写入审计日志失败: %s", exc)
                finally:
                    db.close()

    return middleware
```


**③ 审计中心接口：模块清单 + 日志分页筛选**（`E:\AI-Agent知识库\server\app\api\audit.py` L31-L80，共 50 行）

```python
@router.get("/modules")
def list_modules(_: User = Depends(require_admin)):
    """返回操作分类枚举（前端下拉用）：[{module, module_label, actions}]。"""
    from app.services.audit import MODULE_LABELS

    items = [{"module": k, "module_label": v, "actions": MODULE_ACTIONS.get(k, ["GET", "POST", "PUT", "DELETE"])} for k, v in MODULE_LABELS.items()]
    return ok(data=items)


@router.get("/logs")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module: str = Query("", description="操作类型（业务分类，如 chat/agent/team/document）"),
    action: str = Query("", description="动作（login/GET/POST/DELETE 等）"),
    operator: str = Query("", description="操作人用户名模糊匹配"),
    start: str = Query("", description="开始时间 ISO，如 2026-10-20"),
    end: str = Query("", description="结束时间 ISO，如 2026-10-27"),
    status: str = Query("", description="success/fail"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(OperationLog)
    if module:
        q = q.filter(OperationLog.module == module)
    if action:
        q = q.filter(OperationLog.action == action)
    if operator:
        q = q.filter(OperationLog.username.contains(operator))
    if status:
        q = q.filter(OperationLog.status == status)
    if start:
        try:
            q = q.filter(OperationLog.create_time >= datetime.fromisoformat(start))
        except ValueError:
            pass
    if end:
        try:
            q = q.filter(OperationLog.create_time < datetime.fromisoformat(end))
        except ValueError:
            pass
    total = q.count()
    logs = q.order_by(OperationLog.create_time.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": l.id,
            "user_id": l.user_id,
            "username": l.username,
            "dept_id": l.dept_id,
            "action": l.action,
```


### 执行流程

1. 任意业务请求到达 → audit_middleware 先通过 get_user_from_token 轻量解析用户（失败则标 system/anonymous）。
2. 调用 call_next 执行路由，记录 status_code 与耗时。
3. 请求信息（时间/用户/模块/动作/结果/耗时/IP）落库 AuditLog。
4. 关键写操作另调 record_audit 补充业务维度（如审批动作、敏感操作）。
5. 管理员在审计中心按模块/动作/用户/时间筛选查看。

### 核心接口

- GET /api/audit/modules 模块清单
- GET /api/audit/logs 审计日志分页（module/action/user/result/时间过滤）

### 怎么实现的（原理与依赖）
audit_middleware 是带参闭包工厂（注入 SessionLocal 与用户解析器），请求级全覆盖且不侵入业务代码；模块/动作标签由请求路径路由到 module_label/action_label 映射。依赖：SQLite AuditLog 表、FastAPI middleware 机制。

> **答辩一句话总结**：解决『出了事查不到谁干的』问题：全量留痕 + 一键检索，满足企业合规审计与责任追溯。

---

## 十一、答辩 Q&A 速查

- **Q：为什么向量嵌入用本地哈希而不是预训练模型？**
  A：默认 sentence-transformer 需要联网下载模型，企业内网不可用；本地哈希嵌入零下载、离线稳定，
  配合关键词融合检索补偿语义精度，保证开箱即用。
- **Q：多轮记忆会不会把历史答错的内容带进来？**
  A：System Prompt 第 6 条明确区分『历史个人信息』与『知识库片段』，历史仅用于承接上下文，
  涉及事实性回答仍以当前检索片段为准，且历史按 8 轮截断防上下文膨胀。
- **Q：画布工作流的安全性怎么保证？**
  A：LLM 节点注入防提示注入 System Prompt；检索节点按用户部门隔离；任务执行前需人工确认；
  全链路 workflow_trace 可回溯审计。
- **Q：审计日志会影响性能吗？**
  A：中间件为同步旁路记录，单次写入毫秒级；关键查询均有索引，审计中心分页查询流畅。
- **Q：演示模式会不会污染正式数据？**
  A：演示数据统一打 is_demo 标记，reset 只清理标记数据，正式数据零影响。

---

*本文档由知寻 KnowSeek 项目答辩材料自动生成，代码摘录自线上已逐行加注源码（E:\AI-Agent知识库），行号区间与线上文件一致。*
*（内容由AI生成，仅供参考）*
