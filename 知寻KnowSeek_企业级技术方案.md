---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f92a25702084128d164d6c111d7f7222_435de9e7cde311f1ba6e525400de85a5
    ReservedCode1: A+VYp4DS8wewv0dfqdRAmNpFXk4K8KFpxyrzO/700GPeHWCap7jZwRPqfcpZFuz0vzBc7mOJAGpdvyf0zPNNX839YKVcX3rlKiDOkmYGMvWXTvlrasEGeMkIyxA1ki8MEq9SCfHKBRUfz/Cxay86w75rtd728WEysqA05yE8oSvWK1mU+SSNEkh9TeU=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f92a25702084128d164d6c111d7f7222_435de9e7cde311f1ba6e525400de85a5
    ReservedCode2: A+VYp4DS8wewv0dfqdRAmNpFXk4K8KFpxyrzO/700GPeHWCap7jZwRPqfcpZFuz0vzBc7mOJAGpdvyf0zPNNX839YKVcX3rlKiDOkmYGMvWXTvlrasEGeMkIyxA1ki8MEq9SCfHKBRUfz/Cxay86w75rtd728WEysqA05yE8oSvWK1mU+SSNEkh9TeU=
---

---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f92a25702084128d164d6c111d7f7222_54ca9980cde011f1ba6e525400de85a5
    ReservedCode1: XXsejRwd9+c7rQVPGfA5xURXJyLeHl4sZX/uoZvUn2XsYoB1Bwab6A801VrwSwBgS8TOPzP5o9f6hXHXaCuQcAKpn2QnXG+rxeOCnYfp8Oh4UZVQYPs8ujQ81pcioeSad/crjaf8xYHdSv+olDfprz0ma4EmhNgVRP9KY5DmhLzo1VM4xXdOvN46/rw=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f92a25702084128d164d6c111d7f7222_54ca9980cde011f1ba6e525400de85a5
    ReservedCode2: XXsejRwd9+c7rQVPGfA5xURXJyLeHl4sZX/uoZvUn2XsYoB1Bwab6A801VrwSwBgS8TOPzP5o9f6hXHXaCuQcAKpn2QnXG+rxeOCnYfp8Oh4UZVQYPs8ujQ81pcioeSad/crjaf8xYHdSv+olDfprz0ma4EmhNgVRP9KY5DmhLzo1VM4xXdOvN46/rw=
---

# 知寻 KnowSeek —— 企业级智能知识中枢（企业级技术方案）

> 版本：V1.0 ｜ 状态：已评审定稿 ｜ 日期：2026-10-22
> 定位：让企业知识触手可及
> 适用范围：知寻 KnowSeek —— 企业级智能知识中枢（RAG + 文档解析 + LangGraph Agent）从零开发到落地的整体技术方案
> 编制依据：《企业内部智能助手开发文档》(Excel) 与《审核意见_企业级修订要求》

---

## 目录

1. [项目定位与目标](#1-项目定位与目标)
2. [总体架构设计](#2-总体架构设计)
3. [技术选型及理由](#3-技术选型及理由)
4. [系统模块设计](#4-系统模块设计)
5. [数据库设计](#5-数据库设计)
6. [接口设计](#6-接口设计)
7. [安全设计](#7-安全设计)
8. [部署架构](#8-部署架构)
9. [测试策略与性能指标](#9-测试策略与性能指标)
10. [监控运维与备份恢复](#10-监控运维与备份恢复)
11. [里程碑排期](#11-里程碑排期)
12. [风险清单](#12-风险清单)

---

# 第 1 章 项目定位与目标

## 1.1 项目定位

**知寻 KnowSeek —— 企业级智能知识中枢**（定位语：让企业知识触手可及）是一套面向企业内部员工与管理员的知识库问答与任务编排平台。它以 RAG（检索增强生成）为核心，集成文档解析、OCR 识别、多版本文档管理、部门数据隔离与 LangGraph Agent 任务编排，帮助员工从分散的 PDF、Word、Excel 及扫描件中快速获取答案、生成周报、对比文档差异、撰写方案。

系统面向两类角色：

| 角色 | 职责 |
| --- | --- |
| 普通员工（staff） | 上传/管理自有文档与标签，进行 RAG 多轮问答与原文溯源，使用 Agent 任务（周报/文档对比/方案撰写），提交问答反馈 |
| 管理员（admin） | 创建/删除部门，查看全部文档/对话/反馈，管理全部标签，处理反馈流转 |

## 1.2 建设目标

### 1.2.1 功能目标

| 目标域 | 目标描述 |
| --- | --- |
| 文档知识化 | 支持 PDF、扫描版 PDF、Word、Excel（预留 PPT/TXT/Markdown）上传解析；自动摘要、会议纪要信息抽取（时间/参会人/待办）；重叠切片入库 |
| 检索问答 | 多轮上下文问答、原文溯源（PDF 页码 / Excel 工作表定位）、参考资料分页、一键复制与满意度反馈 |
| 智能编排 | LangGraph Agent 完成周报生成、文档对比、方案撰写三类任务，检索结果经人工确认后生成最终输出 |
| 权限隔离 | 部门级数据隔离、角色级权限管控，普通员工仅见自己的数据 |
| 管理后台 | 部门管理、全量文档/对话/反馈查看、反馈跟进处理 |

### 1.2.2 非功能目标（量化验收标准）

| 指标 | 目标值 | 说明 |
| --- | --- | --- |
| 核心接口响应 | P95 < 2s | 登录、列表、文档详情等常规接口 |
| RAG 首字/完成时间 | 流式首 Token ≤ 3s，整轮 ≤ 30s | 不含 LLM 异常降级场景 |
| 检索质量 | Top5 检索命中率 ≥ 90% | 以标注测试集评估 |
| 并发能力 | 支持 200 并发在线用户，50 并发 RAG 请求 | 生产环境压测验证 |
| 可用性 | 月度可用性 ≥ 99.5% | 排除计划维护窗口 |
| 数据安全 | 传输加密、存储加密、审计留痕 100% 覆盖关键操作 | 见安全设计章节 |
| 工期 | 总工期 ≤ 120 人天 | 见里程碑排期章节 |

## 1.3 范围边界

**本期包含**：文档解析入库全链路、RAG 多轮问答与溯源、LangGraph Agent 三类任务、部门隔离与权限后台、前端全部页面、容器化部署与 CI/CD、监控告警与备份。

**本期明确排除**（与原文档保持一致，并对 P2 建议进行取舍）：

| 排除项 | 处理策略 |
| --- | --- |
| 容器化/内网隧道等部署增强 | 容器化已纳入本期（P0 修订）；内网隧道不在范围 |
| Agent 输出 Markdown 导出 | 原文档排除，审核意见建议支持（P2）：本期纳入"导出 Markdown"为可选项，排期见第 11 章，若资源紧张可降级为 P2 后置 |
| 反馈列表展示原始问答 | 保持排除，仅展示反馈元数据（反馈 ID/用户/评价/原因/时间） |
| 多租户 SaaS 化、计费、工作流自定义 | 不在本期范围，架构预留扩展点 |

## 1.4 成功标准

1. 文档从上传到可检索全链路稳定，支持多版本切换且检索结果与版本严格一致；
2. RAG 回答均附带可点击溯源引用，检索命中率达标（Top5 ≥ 90%）；
3. Agent 三类任务人工确认流程闭环，任务状态可追踪、可重试、可超时终止；
4. 部门隔离与角色权限在服务端强校验，越权访问 0 通过；
5. 一键 Docker Compose 拉起开发环境，CI/CD 流水线实现提交即构建、测试、部署；
6. 监控告警、日志、备份恢复演练齐备，满足可用性与 RPO/RTO 目标。

---

# 第 2 章 总体架构设计

## 2.1 架构设计原则

| 原则 | 说明 |
| --- | --- |
| 单体模块化 | 采用 FastAPI 单体应用 + 清晰模块分层，避免微服务初期运维复杂度过高；模块边界（文档/对话/Agent/权限）以包结构与依赖倒置隔离，为未来拆分预留 |
| 异步解耦 | 耗时任务（解析/OCR/切片/向量化/Agent 生成）全部通过消息队列异步执行，主 API 仅负责受理与进度查询 |
| 存储抽象 | 向量存储、对象存储均设计 repository 接口层，生产可替换 pgvector/Milvus、本地磁盘/MinIO 而不改业务代码 |
| 权限服务端强校验 | RBAC + 部门数据隔离在服务层统一校验，前端隐藏不作为安全依据 |
| 可观测 | 日志、指标、链路追踪三件套全量接入，关键链路可排查可告警 |

## 2.2 总体架构图（分层视图）

```
┌────────────────────────────────────────────────────────────────┐
│  前端（Vue3 + Element Plus + Pinia + Axios）                     │
│  登录 / 文档库 / 对话页 / Agent 任务页 / 管理员后台                 │
└───────────────┬────────────────────────────────────────────────┘
                │ HTTPS / REST + SSE（EventSource）
┌───────────────▼────────────────────────────────────────────────┐
│  接入层：Nginx（静态资源 + 反向代理 + TLS 终结 + 限流）            │
└───────────────┬────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────┐
│  API 层：FastAPI（/api/v1）                                     │
│  鉴权中间件(JWT双token) → RBAC → 部门隔离校验 → 路由 → 统一响应    │
│  模块：文档 / 标签 / 对话 / 反馈 / Agent / 部门 / 管理员 / 用户    │
└───────┬──────────────────┬──────────────────┬──────────────────┘
        │                  │                  │
┌───────▼───────┐  ┌──────▼────────┐  ┌──────▼──────────────────┐
│ 业务数据库     │  │ 向量存储       │  │ 对象/文件存储            │
│ PostgreSQL    │  │ pgvector(主)  │  │ MinIO(生产)/本地磁盘(开发) │
│ + pgvector    │  │ Milvus(备选)  │  │ 原始文件+OCR全文+导出产物  │
└───────┬───────┘  └──────┬────────┘  └──────┬──────────────────┘
        │                  │                  │
┌───────▼──────────────────▼──────────────────▼──────────────────┐
│  异步任务层：Celery + Redis（Broker/Result）                     │
│  文档解析任务 / OCR 任务 / 切片向量化任务 / Agent 生成任务         │
│  进度状态机：pending → parsing → ocr → chunking → embedding     │
│                → success / failed（含失败原因）                  │
└───────┬────────────────────────────────────────────────────────┘
┌───────▼────────────────────────────────────────────────────────┐
│  外部依赖：通义千问（LLM） / PaddleOCR 独立服务（可选第三方OCR）   │
│  LLM 网关层：超时/重试/熔断/计费统计/内容安全过滤                  │
└────────────────────────────────────────────────────────────────┘
```

## 2.3 核心业务链路

### 2.3.1 文档入库链路

```
上传(POST /document/upload) → 落文件存储 → 写 document(pending)
  → Celery 任务链：
     ① 格式解析（PDF/Word/Excel/扫描版识别）
     ② 扫描版走 PaddleOCR 服务（独立进程/容器）
     ③ 摘要 + 会议纪要抽取（LLM）
     ④ 重叠切片 → 写 doc_chunk → 向量化 → 写 pgvector
     ⑤ 更新 document.status = success / failed(fail_msg)
  → 前端轮询 /document/progress/{doc_id} 展示进度条
```

### 2.3.2 RAG 问答链路

```
POST /chat/rag（SSE 流式）
  → 权限/会话校验 → 确定检索版本范围（selected_doc_version_ids）
  → 向量检索 TopN（含重叠切片去重） → 组装上下文
  → 通义千问流式生成 → SSE 事件流：
     event: retrieval（引用切片分页数据）
     event: delta（增量文本）
     event: done（结束 + 引用）
  → 消息落库（content + ref_chunk_ids） → 前端渲染溯源引用
```

### 2.3.3 Agent 任务链路

```
POST /agent/task/create → 建任务(retrieving) → Celery 异步检索
  → 检索完成 → 任务置 waiting_confirm，Graph 在 human_confirm 节点中断
  → 用户查看检索资料 → POST /agent/task/{id}/confirm
  → 继续执行生成节点 → 任务置 finished / failed（写 task_result / error_msg）
  → 超时兜底：waiting_confirm 超 10 分钟未确认自动 failed
```

## 2.4 关键技术决策（回应审核意见）

| 审核意见 | 本方案决策 |
| --- | --- |
| P0：弃用 SQLite，生产用 PostgreSQL | 开发/测试/生产统一使用 PostgreSQL 15+，删除"可无缝迁移 MySQL"表述 |
| P0：向量库企业级选型 | 主选 pgvector（同库事务一致、运维简单），备选 Milvus（亿级向量/高并发）；通过 `VectorStoreRepository` 抽象隔离 |
| P0：容器化 + CI/CD | Docker Compose 开发/测试一键起；生产镜像 Dockerfile；GitLab CI 流水线（构建→测试→推送→部署） |
| P0：OCR 独立服务化 | PaddleOCR 独立容器/进程，通过 Celery 队列解耦；`OcrProvider` 接口预留第三方 OCR 接入 |
| P1：安全/接口/测试/监控/备份 | 见第 7/6/9/10 章详细设计 |

## 2.5 模块拓扑与依赖

```
┌──────────────────────── 后端模块包结构（示意） ────────────────────────┐
│ app/                                                                 │
│ ├── api/           路由层（depends: auth, rbac, dept_scope）           │
│ ├── core/          配置、安全、异常、响应模型                          │
│ ├── models/        SQLAlchemy ORM 模型                                │
│ ├── schemas/       Pydantic 请求/响应模型                             │
│ ├── services/      业务层：document/rag/agent/tag/conv/feedback/...  │
│ ├── repositories/  存储抽象：vector_store/object_store/llm_gateway    │
│ ├── tasks/         Celery 任务：parse/ocr/chunk/embedding/agent      │
│ ├── workers/       PaddleOCR 独立服务                                 │
│ └── langgraph/     Agent 状态图（retrieval/human_confirm/generate）   │
└──────────────────────────────────────────────────────────────────────┘
```

模块间依赖方向：`api → service → repository → 基础设施（PG/Redis/向量/对象存储/LLM）`，禁止反向依赖，保证可测试性与可替换性。

---

# 第 3 章 技术选型及理由

## 3.1 选型总览

| 技术域 | 主选方案 | 备选/演进方向 | 选型性质 |
| --- | --- | --- | --- |
| 后端框架 | Python FastAPI + SQLAlchemy 2.x + Alembic | — | 沿用原方案，P0 保留 |
| 前端框架 | Vue3 + Element Plus + Pinia + Axios | — | 沿用原方案 |
| 业务数据库 | PostgreSQL 15+ | — | P0 修订（替代 SQLite） |
| 向量存储 | pgvector 0.6+ | Milvus 2.x | P0 修订（替代 Chroma） |
| 对象/文件存储 | MinIO | 本地磁盘（开发）、云对象存储 | P1 补文件方案 |
| OCR | PaddleOCR 独立服务 | 腾讯云 OCR / 自研 | P0 服务化修订 |
| 异步任务 | Celery + Redis | RabbitMQ（需可靠投递时） | P0 新增 |
| 缓存 | Redis（会话/进度/限流） | — | P1 新增 |
| LLM | 通义千问（qwen-plus/max） | 兼容 OpenAI 协议的私有化模型 | 沿用 + 网关化 |
| 编排 | LangGraph | — | 沿用原方案 |
| 搜索/检索 | pgvector HNSW + BM25 混合（可选 pg_trgm） | Elasticsearch（全文增强） | P2 演进 |
| 部署 | Docker Compose + Nginx | Kubernetes | P0 修订 |
| CI/CD | GitLab CI | GitHub Actions | P0 修订 |
| 监控 | Prometheus + Grafana + Loki | — | P1 新增 |
| 日志 | structlog + Loki/Promtail | ELK | P1 新增 |

## 3.2 数据库选型：PostgreSQL 替代 SQLite

**背景**：原方案使用 SQLite（开发阶段，可无缝迁移 MySQL）。审核意见 P0 要求直接采用企业级数据库，开发与生产同库型。

**决策：主选 PostgreSQL 15+，开发/测试/生产统一，删除"可无缝迁移 MySQL"表述。**

| 维度 | SQLite | PostgreSQL 15+ | 结论 |
| --- | --- | --- | --- |
| 并发写入 | 单写锁，多进程写冲突 | MVCC 高并发读写 | PG 胜 |
| 数据类型 | 有限 | 原生 JSONB、数组、UUID、全文检索、GIS | PG 胜 |
| 向量扩展 | 不支持 | pgvector 同库集成 | PG 胜 |
| 可靠性 | 无 WAL 归档/主从 | WAL、流复制、PITR、备份工具 | PG 胜 |
| 运维生态 | 弱 | 成熟（监控/备份/HA） | PG 胜 |

**收益**：① 开发与生产行为一致，消除环境差异导致的隐性 Bug；② 事务内可同时写业务数据与向量（pgvector 同库），保证"文档-切片-向量"一致性；③ 数据迁移、备份、审计能力完备。

## 3.3 向量库选型：pgvector 主选 / Milvus 备选

**背景**：原方案 Chroma 仅存向量。审核意见 P0 要求设计向量存储抽象层，生产使用 pgvector/Milvus，避免换库重写检索代码。

**取舍分析**：

| 维度 | pgvector（主选） | Milvus 2.x（备选） |
| --- | --- | --- |
| 架构 | PostgreSQL 扩展，同库部署 | 独立分布式服务 |
| 数据一致性 | 与业务数据同事务（强一致） | 需双写与补偿 |
| 规模 | 千万级向量可用；亿级需调优 | 亿级 + 高并发 QPS 专长 |
| 运维复杂度 | 低（随 PG 一起） | 高（独立集群 + 元数据存储） |
| 过滤检索 | SQL 级任意条件过滤 | 标量过滤 + 分区 |
| 混合检索 | 可与全文检索同 SQL 融合 | 需外部融合 |

**决策**：默认采用 **pgvector（HNSW 索引）**——本项目预计文档切片在百万级以内，pgvector 同库事务一致、运维简单，契合"企业级且不过度复杂"的目标。预留 **`VectorStoreRepository` 接口**（add/delete/search/health），当数据量或并发超出 pgvector 承载（如切片 > 5000 万、QPS > 500）时，切换到 Milvus 仅需实现新 Repository，检索业务代码零改动。

**存储抽象层接口（示意）**：

```python
class VectorStoreRepository(Protocol):
    def add(self, chunks: list[ChunkEmbedding]) -> None: ...
    def delete_by_doc_id(self, doc_id: int) -> None: ...
    def search(self, embedding: list[float], top_k: int,
               filters: dict | None = None) -> list[VectorHit]: ...
    def health(self) -> bool: ...
```

## 3.4 OCR 选型：PaddleOCR 独立服务化

**背景**：原方案 PaddleOCR 内嵌主服务处理扫描版 PDF。审核意见 P0 要求独立服务化并通过异步任务队列解耦。

**决策**：PaddleOCR 以**独立容器/进程**部署，对外暴露 HTTP 识别接口；主服务通过 Celery 队列投递 OCR 任务，识别结果回写 `document.ocr_content`。同时定义 `OcrProvider` 接口，预留腾讯云/百度 OCR 等第三方平台接入。

```python
class OcrProvider(Protocol):
    def recognize(self, file_key: str) -> OcrResult: ...   # 文本 + 置信度
    def health(self) -> bool: ...
```

**收益**：① 扫描件处理不阻塞 API 主进程；② OCR 服务可独立扩缩容；③ 第三方 OCR 可无缝替换，降低识别率风险。

## 3.5 异步任务队列与缓存：Celery + Redis

- **Celery**：承载文档解析、OCR 触发、切片向量化、Agent 生成等重任务；任务链编排、失败重试（指数退避）、进度状态回写。
- **Redis**：Celery Broker/Result Backend + 会话缓存 + 上传进度 + 限流计数 + SSE 分布式锁。
- 未来若需消息可靠投递审计，可切换 RabbitMQ（Celery broker 兼容）。

## 3.6 LLM 网关：通义千问 + 统一网关层

- **模型**：默认通义千问（qwen-plus 用于摘要/抽取/问答，qwen-max 用于 Agent 复杂生成，按任务分级调用以控成本）。
- **网关职责**：统一鉴权与 Key 管理、超时控制、指数退避重试、熔断降级、调用计费统计（写 `llm_call_log`）、内容安全过滤（敏感词/合规审核）。
- **兼容性**：网关层采用 OpenAI 兼容协议适配，可切换到私有化部署模型（如 Qwen 开源版、DeepSeek 等）而业务代码不变。

## 3.7 前端与渲染

- **Vue3 + Element Plus + Pinia + Axios**：沿用原方案，生态成熟、团队熟悉度高。
- **PDF 预览**：pdf.js 定位页码跳转；**Excel 预览**：xlsx.js 前端渲染工作表定位；**Word 预览**：docx-preview 或转 PDF 预览（P2 细化）。
- **SSE 客户端**：EventSource（原生）封装，处理 retrieval/delta/done 事件与断线重连。

## 3.8 部署与运维组件选型

- **Nginx**：静态资源 + 反向代理 + TLS 终结 + 限流 + 上传大小限制。
- **Docker Compose**：开发/测试环境一键起（PG/Redis/MinIO/OCR/API/Worker/前端）。
- **Prometheus + Grafana + Loki**：指标采集、可视化、日志聚合与告警。
- 生产环境按资源规模决定是否升级 Kubernetes（单机可先用 Docker Compose + systemd 守护，规模上来再上 K8s，见第 8 章）。

---

# 第 4 章 系统模块设计

## 4.1 模块总览

| 模块 | 核心职责 | 关键状态机/流程 |
| --- | --- | --- |
| 文档模块 | 上传、解析、OCR、摘要抽取、切片向量化、多版本、标签、筛选、删除 | document.status: pending → parsing → ocr → chunking → embedding → success/failed |
| RAG 对话模块 | 会话管理、流式问答、原文溯源、重置上下文、反馈 | SSE 事件流（retrieval/delta/done） |
| Agent 任务模块 | 周报/文档对比/方案撰写、人工确认、持久化、超时取消 | agent_task.status: retrieving → waiting_confirm → finished/failed |
| 权限后台 | 部门管理、数据查看、反馈处理 | RBAC + dept_scope 过滤 |
| 标签模块 | 标签 CRUD、文档绑定/解绑 | — |

## 4.2 文档模块

### 4.2.1 支持格式与解析策略

| 格式 | 解析方式 | 备注 |
| --- | --- | --- |
| PDF（文本型） | pdfplumber / PyMuPDF 提取文本 | 按页记录 page_no |
| 扫描版 PDF | 转图片 → PaddleOCR 独立服务 | 识别全文存 ocr_content |
| Word（.docx） | python-docx 提取段落/表格 | 段落级定位 |
| Excel（.xlsx） | openpyxl 读工作表 | 记录 sheet_name，Agent 可统计汇总 |
| PPT/TXT/Markdown（P2） | 预留解析器注册表 | 扩展 `DocParserProvider` |

解析器采用**注册表模式**：`DocParserProvider.register(file_type, parser)`，新增格式不改主流程。

### 4.2.2 文件上传与限制

| 项 | 约束 |
| --- | --- |
| 单次文件数 | 1 个 |
| 单文件大小 | 默认 ≤ 50MB（Nginx `client_max_body_size` + 后端双重校验） |
| 文件类型 | 白名单校验（扩展名 + MIME + magic bytes） |
| 重复上传 | 按 file_hash 识别，同一用户同 hash 同一文件按"新版本"处理（version_no+1），不同用户同 hash 视为新文档 |
| 存储路径 | `{storage_root}/{dept_id}/{upload_user_id}/{date}/{file_hash}.{ext}`（见 4.2.6） |

### 4.2.3 摘要与信息抽取

- 摘要：LLM 生成文档摘要（截断至配置上限，如 500 字），异步任务中完成；
- 会议纪要抽取：固定抽取**时间 / 参会人 / 待办事项**，结构化 JSON 存 `extract_result`，支持导出 Markdown（`/document/{id}/extract/export`）；
- 抽取失败不阻塞入库，仅置 warning 标记并在前端提示。

### 4.2.4 重叠切片策略

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| chunk_size | 500 字 | 单切片目标长度 |
| chunk_overlap | 50 字 | 相邻切片重叠，避免语义截断 |
| 切分规则 | 按段落/标题优先，其次按句 | 避免硬切碎句子 |
| Excel 切片 | 每个工作表按行分组切片 | sheet_name + 行范围定位 |

切片元信息落 `doc_chunk` 表（page_no / sheet_name / chunk_index / chroma_id），向量写入 pgvector，`chroma_id` 改为 `vector_id`（与 pgvector 记录 id 绑定，命名沿用时注明兼容字段）。

### 4.2.5 多版本管理

- 同文件重复上传：`parent_doc_id` 分组 + `version_no` 递增，**版本上限 5 个**（超出时自动淘汰最旧版本，删除该版本切片与向量，前端提示）；
- 切换版本：`/chat/rag` 与 `/document/list` 均按 `selected_doc_version_ids` 限定检索范围，**仅检索选中版本向量**；
- 版本信息：原始文件名、大小、hash、上传时间、解析状态完整保留。

### 4.2.6 文件存储方案（P1 修订）

| 文件类型 | 存储位置 | 说明 |
| --- | --- | --- |
| 原始上传文件 | MinIO（生产）/ 本地磁盘（开发） | 路径规则 `{dept_id}/{user_id}/{yyyy-mm-dd}/{file_hash}{ext}` |
| OCR 全文 | 独立对象或 `document` 表外挂 `ocr_file_key` | **不塞主表大字段**，读取时按需拉取 |
| 摘要/抽取结果 | PostgreSQL 表字段 | 小文本，直接存 |
| 导出产物（Markdown） | 对象存储临时目录 | 带过期清理 |
| 权限 | 桶/路径 ACL + 服务端鉴权 | 下载/预览接口校验 dept 与 role 后发放临时 URL |

> 说明：原表将 `ocr_content` 定义为 text 主表字段，审核意见 P1 要求大字段不塞主表。方案改为：`ocr_content` 保留字段用于中小文件（< 5MB 文本），大文件 OCR 全文存对象存储并在 `document` 表记录 `ocr_file_key`，按需读取。

## 4.3 RAG 对话模块

### 4.3.1 会话管理

- 新建会话、会话列表（按用户）、清空会话（会话 + 消息软删）；
- **重置上下文**：`is_context_reset` 标记，保留对话记录，后续提问不再携带历史上下文；页面顶部常驻提示条；
- 消息分页查询（page/size）。

### 4.3.2 检索与生成

- 检索范围：会话绑定选中文档版本（`selected_doc_version_ids`）+ 部门隔离（自动注入 dept 过滤）；
- 检索策略：向量 TopN（默认 5）+ 可选关键词增强（P2）；结果去重（重叠切片合并）；
- 上下文组装：按相关性排序拼接，限制 token 上限，超出截断最不相关切片；
- 生成：通义千问流式输出，SSE 协议见第 6 章。

### 4.3.3 原文溯源

- 回答携带 `ref_chunk_ids`；前端点击引用弹窗展示切片原文 + 页码/工作表；
- PDF 溯源跳转 pdf.js 指定页码；Excel 溯源定位工作表；
- 检索参考资料分页展示（`page/size`），避免一次返回过长。

### 4.3.4 反馈

- 用户对 AI 回答点赞/点踩（good/bad），可填写原因（feedback.content）；
- 管理员后台查看反馈列表（不含原始问答），并可标记处理状态（待处理/已跟进/已关闭）。

## 4.4 Agent 任务模块

### 4.4.1 三类任务定义

| 任务类型 | 输入 | 输出 |
| --- | --- | --- |
| weekly_report（周报） | 用户选择文档 + 人工补充要点（P2：明确输入来源） | 结构化周报（本周进展/问题/下周计划） |
| doc_compare（文档对比） | 选择 2+ 个文档版本 | 差异对比表/摘要 |
| write_plan（方案撰写） | 选择文档 + 需求描述 | 完整方案 |

### 4.4.2 LangGraph 状态机

```
[start] → retrieval_node（向量检索 selected_doc_ids）→ human_confirm_node（中断）
        → [等待用户确认：查看检索资料 / 确认并生成 / 取消]
        → generate_node（LLM 生成最终结果）→ [finished / failed]
```

- 状态字段：`status = retrieving / waiting_confirm / finished / failed / cancelled`；
- 超时机制：`waiting_confirm` 超 10 分钟未确认自动置 `failed`（并记录 error_msg），前端支持取消按钮；
- 失败重试：生成节点失败自动重试 2 次（指数退避），仍失败置 failed 并记录 error_msg；
- 人工确认：确认后 Graph 从中断点恢复执行。

### 4.4.3 任务持久化

- `agent_task` 表保存：任务类型、选中文档、检索切片快照、确认状态、最终结果、error_msg、起止时间；
- 员工可回看历史任务结果；**本期支持 Markdown 导出（P2 采纳）**：`GET /agent/task/{id}/result/export` 返回 Markdown 文件流。

## 4.5 权限后台模块

- 部门管理：管理员新建/删除部门；**删除保护**：部门下存在成员或文档时拒绝删除（或迁移至默认部门后再删）；
- 数据查看：普通员工仅看自己的对话/Agent 任务/上传文档；管理员可看全部；
- 反馈处理：管理员更新反馈状态（待处理/已跟进/已关闭）。

## 4.6 标签模块

- 标签 CRUD：员工可管理自有标签，管理员可管理全部标签；
- 文档绑定/解绑（多对多）；`/document/list` 筛选支持 `tag_ids` 多值（P1 修订，替代单一 tag_id）；
- 删除标签时自动清理关联关系，不影响文档。

## 4.7 进度与异常设计

- 上传进度：Redis 记录解析阶段进度（0-100%），前端轮询 `/document/progress/{doc_id}`；
- 异常兜底：解析失败（加密/损坏）前端弹窗提示原因（fail_msg）；LLM 调用失败/超时给出友好报错并记录 llm_call_log；任务超时自动取消。

---

# 第 5 章 数据库设计

## 5.1 设计总则

- 数据库：PostgreSQL 15+；ORM：SQLAlchemy 2.x；迁移：Alembic（每个里程碑评审迁移脚本）。
- 主键统一 `BIGSERIAL`（或 `BIGINT GENERATED ALWAYS AS IDENTITY`）；时间统一 `TIMESTAMPTZ`。
- 软删除：业务表增加 `is_deleted` + `deleted_at`，物理删除仅由数据清理任务执行。
- 大字段：原文与 OCR 全文不塞主表，见 4.2.6；`ocr_content` 保留但限中小文件。
- 一致性：向量与业务记录删除采用「先删向量 → 删业务记录 → 校验补偿」流程（见 5.4）。

## 5.2 表清单（14 张）

| 表名 | 用途 | 修订要点 |
| --- | --- | --- |
| user | 用户 | +status、last_login_time；password 存 bcrypt 哈希 |
| department | 部门 | 删除保护 |
| document | 文档版本 | +file_size、file_hash、update_time、is_deleted、deleted_at、ocr_file_key |
| doc_tag | 标签 | 同原设计 |
| doc_tag_rel | 文档-标签关联 | 同原设计 |
| doc_chunk | 切片元信息 | vector_id 替代 chroma_id（兼容保留 chroma_id 别名列） |
| conversation | 对话会话 | 同原设计 + is_deleted |
| conversation_msg | 对话消息 | +is_deleted |
| feedback | 问答反馈 | +content（不满原因）、status（待处理/已跟进/已关闭） |
| agent_task | Agent 任务 | +error_msg、cancelled 状态、timeout_at |
| operation_log | 操作审计日志 | 新增（登录/上传/删除/确认/管理员操作） |
| llm_call_log | 模型调用记录 | 新增（计费、失败率、延迟监控） |
| sys_config | 系统配置 | 新增（KV 配置：切片参数、超时、版本上限等） |
| refresh_token | 刷新令牌 | 新增（双 token 支持） |

## 5.3 完整表结构（DDL）

```sql
-- 1. 用户表
CREATE TABLE "user" (
    id               BIGSERIAL PRIMARY KEY,
    username         VARCHAR(64)  NOT NULL UNIQUE,
    password_hash    VARCHAR(128) NOT NULL,             -- bcrypt 哈希
    role             VARCHAR(16)  NOT NULL DEFAULT 'staff'
                     CHECK (role IN ('admin','staff')),
    dept_id          BIGINT       NOT NULL REFERENCES department(id),
    status           VARCHAR(16)  NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','disabled')),
    last_login_time  TIMESTAMPTZ,
    create_time      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    update_time      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMPTZ
);

-- 2. 部门表
CREATE TABLE department (
    id          BIGSERIAL PRIMARY KEY,
    dept_name   VARCHAR(64) NOT NULL UNIQUE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. 文档主表（一条 = 一个版本）
CREATE TABLE document (
    id                BIGSERIAL PRIMARY KEY,
    doc_name          VARCHAR(255) NOT NULL,            -- 存储文件名
    origin_file_name  VARCHAR(255) NOT NULL,            -- 原始文件名
    file_type         VARCHAR(16)  NOT NULL
                      CHECK (file_type IN ('pdf','scan_pdf','word','excel','ppt','txt','markdown')),
    file_size         BIGINT       NOT NULL DEFAULT 0,  -- 字节
    file_hash         CHAR(64)     NOT NULL,            -- SHA-256，防重复
    dept_id           BIGINT       NOT NULL REFERENCES department(id),
    upload_user_id    BIGINT       NOT NULL REFERENCES "user"(id),
    parent_doc_id     BIGINT,                           -- 同文件父 id，多版本分组
    version_no        INT          NOT NULL DEFAULT 1,
    status            VARCHAR(16)  NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','parsing','ocr','chunking','embedding','success','failed')),
    fail_msg          TEXT,
    ocr_content       TEXT,                             -- 中小文件 OCR 全文
    ocr_file_key      VARCHAR(255),                     -- 大文件 OCR 全文对象存储 key
    excel_sheet_info  JSONB,                            -- 工作表信息
    summary           TEXT,
    extract_result    JSONB,                            -- 会议纪要抽取结果
    create_time       TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time       TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted        BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at        TIMESTAMPTZ
);
CREATE INDEX idx_document_dept ON document(dept_id);
CREATE INDEX idx_document_parent ON document(parent_doc_id, version_no);
CREATE INDEX idx_document_hash ON document(file_hash);

-- 4. 标签表
CREATE TABLE doc_tag (
    id            BIGSERIAL PRIMARY KEY,
    tag_name      VARCHAR(64) NOT NULL,
    create_user_id BIGINT NOT NULL REFERENCES "user"(id),
    create_time   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tag_name)
);

-- 5. 标签关联表
CREATE TABLE doc_tag_rel (
    id         BIGSERIAL PRIMARY KEY,
    doc_id     BIGINT NOT NULL REFERENCES document(id),
    tag_id     BIGINT NOT NULL REFERENCES doc_tag(id),
    UNIQUE (doc_id, tag_id)
);

-- 6. 切片表（对应 pgvector）
CREATE TABLE doc_chunk (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      BIGINT  NOT NULL REFERENCES document(id),
    chunk_text  TEXT    NOT NULL,
    page_no     INT,                                    -- PDF 页码；Excel 为 NULL
    sheet_name  VARCHAR(255),                           -- Excel 工作表
    chunk_index INT     NOT NULL,                       -- 切片序号
    vector_id   VARCHAR(64),                            -- pgvector 记录 id（原 chroma_id 兼容别名）
    create_time TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_doc_chunk_doc ON doc_chunk(doc_id);

-- 7. 对话会话表
CREATE TABLE conversation (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES "user"(id),
    title            VARCHAR(255),
    is_context_reset BOOLEAN NOT NULL DEFAULT FALSE,
    create_time      TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted       BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMPTZ
);
CREATE INDEX idx_conv_user ON conversation(user_id, is_deleted);

-- 8. 对话消息表
CREATE TABLE conversation_msg (
    id            BIGSERIAL PRIMARY KEY,
    conv_id       BIGINT NOT NULL REFERENCES conversation(id),
    role          VARCHAR(16) NOT NULL CHECK (role IN ('user','assistant')),
    content       TEXT NOT NULL,
    ref_chunk_ids JSONB,                                -- 引用切片 id 列表
    create_time   TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at    TIMESTAMPTZ
);
CREATE INDEX idx_msg_conv ON conversation_msg(conv_id, create_time);

-- 9. 问答反馈表
CREATE TABLE feedback (
    id          BIGSERIAL PRIMARY KEY,
    msg_id      BIGINT NOT NULL REFERENCES conversation_msg(id),
    user_id     BIGINT NOT NULL REFERENCES "user"(id),
    score       VARCHAR(16) NOT NULL CHECK (score IN ('good','bad')),
    content     TEXT,                                   -- 不满原因/补充说明
    status      VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','processing','closed')),
    create_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. Agent 任务表
CREATE TABLE agent_task (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES "user"(id),
    task_type         VARCHAR(32) NOT NULL
                      CHECK (task_type IN ('weekly_report','doc_compare','write_plan')),
    selected_doc_ids  JSONB NOT NULL,                   -- 选中文档版本 id 列表
    retrieval_chunks  JSONB,                            -- 检索切片快照（待确认）
    is_confirmed      BOOLEAN NOT NULL DEFAULT FALSE,
    task_result       TEXT,                             -- 最终输出
    status            VARCHAR(32) NOT NULL DEFAULT 'retrieving'
                      CHECK (status IN ('retrieving','waiting_confirm','finished','failed','cancelled')),
    error_msg         TEXT,                             -- 失败原因
    timeout_at        TIMESTAMPTZ,                      -- 人工确认超时时间
    create_time       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finish_time       TIMESTAMPTZ
);
CREATE INDEX idx_agent_user ON agent_task(user_id, create_time);

-- 11. 操作审计日志表（新增）
CREATE TABLE operation_log (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT,
    username     VARCHAR(64),
    action       VARCHAR(64) NOT NULL,                  -- login/upload/delete/confirm/admin_op...
    object_type  VARCHAR(32),                           -- document/conversation/agent_task/department...
    object_id    VARCHAR(64),
    detail       JSONB,                                 -- 关键参数（脱敏后）
    ip           VARCHAR(64),
    user_agent   VARCHAR(255),
    result       VARCHAR(16) NOT NULL CHECK (result IN ('success','fail','denied')),
    create_time  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_oplog_user_time ON operation_log(user_id, create_time);
CREATE INDEX idx_oplog_action_time ON operation_log(action, create_time);

-- 12. 模型调用记录表（新增）
CREATE TABLE llm_call_log (
    id           BIGSERIAL PRIMARY KEY,
    scene        VARCHAR(32) NOT NULL,                  -- summary/extract/rag/agent/...
    model        VARCHAR(64) NOT NULL,
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    cost_amount  NUMERIC(12,6) NOT NULL DEFAULT 0,      -- 估算费用（元）
    latency_ms   INT NOT NULL DEFAULT 0,
    status       VARCHAR(16) NOT NULL CHECK (status IN ('success','fail','timeout')),
    error_msg    TEXT,
    create_time  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_llm_time ON llm_call_log(create_time);

-- 13. 系统配置表（新增）
CREATE TABLE sys_config (
    key         VARCHAR(64) PRIMARY KEY,
    value       JSONB NOT NULL,                         -- 支持标量/列表/对象
    description VARCHAR(255),
    update_time TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 14. 刷新令牌表（新增）
CREATE TABLE refresh_token (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES "user"(id),
    token_hash  VARCHAR(128) NOT NULL,                  -- 存哈希不存明文
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rt_user ON refresh_token(user_id, revoked);
```

## 5.4 关键一致性流程

### 5.4.1 删除文档（先删向量 → 删记录）

```
1. 校验权限（本人/admin）+ 部门校验
2. 从 pgvector 删除该 doc_id 全部向量（vector_id 列表由 doc_chunk 提供）
3. 标记 document.is_deleted = TRUE（软删）
4. 删除 doc_chunk 记录、doc_tag_rel 关联（软删或物理删）
5. 删除对象存储中的原始文件（异步任务，保留 30 天可恢复期）
6. 失败补偿：步骤 2 失败则不执行 3-5 并记录 operation_log(fail)；重试任务兜底清理孤儿向量
```

### 5.4.2 版本上限

- 同一 `parent_doc_id` 下 `version_no` 超上限（默认 5）时，删除最旧版本（走 5.4.1 流程），保持版本数 ≤ 5。

### 5.4.3 切片与向量一致性

- 写入：先写 `doc_chunk`（含 vector_id 占位）→ 向量化成功回填 vector_id → 全部成功后 document.status=success；
- 失败：任一切片失败则整批回滚（删除已写向量与切片），任务失败重试，避免半截数据。

## 5.5 索引与查询策略

- 列表查询（文档库）：组合索引 `(dept_id, is_deleted, create_time DESC)`，标签筛选走 `doc_tag_rel` 反查后 IN 过滤；
- 会话消息分页：`(conv_id, create_time)` 索引；
- 向量检索：pgvector HNSW 索引（vector 列，distance 用 cosine）；
- 模糊搜索：可选 pg_trgm 的 GIN 索引支持文件名 LIKE 检索（P2 可选全文检索升级）。

## 5.6 迁移与初始化

- Alembic 管理全量迁移；提供 `init_db.py` 初始化：建表、初始部门、初始管理员账号（首次启动强制改密）、sys_config 默认值（切片参数/超时/版本上限/模型配置）。

---

# 第 6 章 接口设计

## 6.1 接口通用约定

- 基础前缀：`/api/v1`；全部接口需 JWT 鉴权（登录/刷新除外）。
- 请求/响应 Content-Type：`application/json`；上传用 `multipart/form-data`；流式用 `text/event-stream`（SSE）。
- 统一响应结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": { }
}
```

- 分页结构（PageResult）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [ ... ],
    "page": 1,
    "size": 10,
    "total": 123,
    "total_pages": 13
  }
}
```

- 时间格式：ISO 8601（`2026-10-22T10:30:00+08:00`）。

## 6.2 错误码规范

| 错误码 | HTTP | 含义 |
| --- | --- | --- |
| 0 | 200 | 成功 |
| 10001 | 400 | 参数校验失败（含 message 详情） |
| 10002 | 401 | 未认证/Token 无效/过期 |
| 10003 | 403 | 无权限（越权访问） |
| 10004 | 404 | 资源不存在（含软删） |
| 10005 | 409 | 资源冲突（重复上传/部门有成员等） |
| 10006 | 429 | 请求过于频繁（限流） |
| 20001 | 500 | 服务器内部错误 |
| 20002 | 502 | LLM 调用失败（网关错误） |
| 20003 | 504 | LLM 调用超时 |
| 30001 | 422 | 文件类型不支持 |
| 30002 | 413 | 文件超过大小限制 |
| 30003 | 400 | 文件解析失败（加密/损坏，fail_msg 带原因） |
| 30004 | 404 | 文件不存在/已删除 |

## 6.3 认证接口

### POST /api/v1/auth/login

- 请求：`{"username": "...", "password": "..."}`
- 返回：`{"access_token": "...", "refresh_token": "...", "expires_in": 3600, "user_info": {...}}`
- 安全：登录失败统一错误信息（防用户枚举），失败次数超阈值（如 5 次/5 分钟）触发验证码或临时锁定；写 operation_log。

### POST /api/v1/auth/refresh

- 请求：`{"refresh_token": "..."}`
- 返回：新 `access_token` + `refresh_token`（轮换），旧 refresh token 立即失效（单次使用）。
- 安全：refresh_token 存哈希、可撤销（登出/泄露处置）。

### POST /api/v1/auth/logout

- 撤销当前 refresh_token + 使 access_token 进入黑名单（Redis 短 TTL 缓存，TTL 至原过期时间）。

## 6.4 统一分页与列表查询

列表接口统一支持 `page`（默认 1）、`size`（默认 10，最大 100）。文档列表：

`GET /api/v1/document/list?keyword=&file_types=pdf,word&tag_ids=1,2&parent_doc_id=&page=&size=`

- 多值参数用逗号分隔（`tag_ids`，P1 修订替代单一 `tag_id`）。

## 6.5 核心接口清单

| 模块 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 认证 | POST | /auth/login | 登录（双 token） |
| 认证 | POST | /auth/refresh | 刷新 access token |
| 认证 | POST | /auth/logout | 登出 |
| 用户 | GET | /user/info | 当前用户信息 |
| 部门 | POST/GET/DELETE | /dept、/dept/{id} | 部门管理（admin，删除保护） |
| 文档 | POST | /document/upload | 上传（单文件，返回 doc_id + 解析任务 id） |
| 文档 | GET | /document/progress/{doc_id} | 解析进度（阶段 + 百分比） |
| 文档 | GET | /document/list | 文档列表（多条件筛选 + 分页） |
| 文档 | GET | /document/{doc_id} | 文档详情（摘要/抽取/版本） |
| 文档 | GET | /document/version/list?parent_doc_id= | 版本列表 |
| 文档 | DELETE | /document/{doc_id} | 删除版本（向量一致性删除） |
| 文档 | GET | /document/{doc_id}/download | 下载原始文件（鉴权 + 临时 URL） |
| 文档 | GET | /document/{doc_id}/preview | 在线预览（pdf.js/xlsx.js 数据） |
| 文档 | GET | /document/{doc_id}/extract/export | 导出抽取结果 Markdown |
| 标签 | POST/GET/PUT/DELETE | /tag、/tag/{id} | 标签 CRUD |
| 标签 | POST/DELETE | /document/{doc_id}/tag/bind、/document/{doc_id}/tag/{tag_id} | 绑定/解绑 |
| 对话 | POST/GET/DELETE | /conv、/conv/{id} | 会话新建/列表/清空 |
| 对话 | PUT | /conv/{id}/reset-context | 重置上下文标记 |
| 对话 | GET | /conv/{id}/msg?page=&size= | 会话消息分页 |
| 对话 | POST | /chat/rag | RAG 问答（SSE 流式 + 溯源） |
| 反馈 | POST | /feedback | 提交问答反馈（score + content） |
| 管理员 | GET | /admin/conv、/admin/document、/admin/feedback | 全部对话/文档/反馈（分页，反馈不含原文） |
| 管理员 | PUT | /admin/feedback/{id}/status | 反馈状态流转（待处理/已跟进/已关闭） |
| Agent | POST | /agent/task/create | 创建任务并检索 |
| Agent | GET | /agent/task | 当前用户任务列表 |
| Agent | GET | /agent/task/{id} | 任务详情（检索资料分页） |
| Agent | POST | /agent/task/{id}/confirm | 确认检索并继续生成 |
| Agent | POST | /agent/task/{id}/cancel | 取消任务 |
| Agent | GET | /agent/task/{id}/result | 获取最终结果 |
| Agent | GET | /agent/task/{id}/result/export | 导出结果 Markdown（P2 采纳） |

## 6.6 SSE 流式协议（/chat/rag）

响应头：`Content-Type: text/event-stream; charset=utf-8`、`Cache-Control: no-cache`、`Connection: keep-alive`。

事件协议（`event: 类型\ndata: JSON\n\n`）：

```text
event: retrieval
data: {"refs": [{"chunk_id": 101, "doc_id": 5, "page_no": 3, "sheet_name": null,
                 "text_preview": "...", "score": 0.87}], "total": 5, "page": 1, "size": 10}

event: delta
data: {"content": "根据检索到的文档，"}

event: delta
data: {"content": "该项目..."}

event: done
data: {"conv_id": 12, "msg_id": 88, "ref_chunk_ids": [101, 102, 103]}

event: error
data: {"code": 20003, "message": "模型调用超时，请稍后重试"}
```

- `retrieval`：首个事件，携带溯源引用切片（前端分页渲染）；
- `delta`：增量文本（可多条）；
- `done`：结束事件，返回会话/消息 id 用于反馈；
- `error`：异常事件（LLM 失败/超时），随后关闭流；
- 心跳：服务端每 15s 发送 `event: ping` 保持连接；客户端断线自动重连（EventSource 内置），重连后提示"上下文已保留"。
- 溯源点击：前端从 `retrieval` 引用中按 chunk_id 拉取 `/document/chunk/{id}`（切片原文 + 页码/工作表）弹窗展示。

## 6.7 文件上传与下载

- 上传：`multipart/form-data` 单文件；校验类型白名单 + 大小 ≤ 50MB；大文件分片/断点续传列为 P2 可选项（预留 `upload_id`/分片接口设计，本期不做）。
- 下载/预览：服务端校验文档归属与角色后，返回对象存储临时签名 URL（有效期 5 分钟）或代理流。
- 导出：Markdown 导出走接口返回文件流（`Content-Disposition` 指定文件名，UTF-8 文件名 URL 编码）。

## 6.8 接口安全约束

- 所有接口经 JWT 中间件；service 层执行 RBAC 角色校验 + 部门数据隔离过滤（`dept_scope` 注入 SQL/ORM 查询）；
- 写操作（上传/删除/确认/后台管理）写 operation_log；
- 幂等与重放：上传/删除类接口支持幂等键（`Idempotency-Key` 可选），刷新 token 单次使用；
- 限流：登录（IP+账号）、上传（用户）、SSE 问答（用户）分级限流。

---

# 第 7 章 安全设计

## 7.1 安全目标与基线

| 层 | 目标 |
| --- | --- |
| 认证 | 双 token、过期、登出、失效处置，防暴力破解 |
| 授权 | RBAC + 部门数据隔离服务端强校验，越权 0 通过 |
| 数据 | 传输加密、敏感信息脱敏、密钥托管 |
| 审计 | 关键操作留痕，可追溯谁/何时/做了什么 |
| 文件 | 上传安全、存储权限、下载鉴权 |
| 基础设施 | TLS、限流、安全加固 |

## 7.2 认证设计

### 7.2.1 密码安全

- 密码哈希：**bcrypt**（cost=12，推荐）或 argon2id；**禁止明文/弱哈希存储**；
- 强度策略：最小 8 位且含数字与字母（管理员 12 位以上强制）；
- 登录失败保护：5 次失败触发验证码，10 次失败临时锁定 5 分钟；
- 管理员首次登录强制改密。

### 7.2.2 双 Token 机制

| Token | 有效期 | 存放 | 说明 |
| --- | --- | --- | --- |
| access_token | 60 分钟 | 内存/会话（前端禁止 localStorage 敏感场景可 HttpOnly Cookie） | JWT，含 uid/role/dept_id/exp；每次请求校验 |
| refresh_token | 7 天 | 哈希存数据库 | 单次使用 + 轮换；过期自动失效 |

- 刷新接口签发新 access + 新 refresh；旧 refresh 置 revoked；
- 登出：撤销 refresh + access 进 Redis 黑名单（TTL 至过期）；
- JWT 密钥：HS256 或 RS256（生产 RS256 公私钥对，公钥放应用，私钥托管在密钥管理）。

### 7.2.3 Token 泄露处置

- 管理端支持按用户强制下线（撤销该用户全部 refresh token + access 黑名单）；
- 检测到异常（异地/频率异常）可选二次验证（P2）。

## 7.3 授权设计（RBAC + 部门隔离）

### 7.3.1 权限模型

| 权限点 | staff | admin |
| --- | --- | --- |
| 上传/管理自有文档 | ✅ | ✅ |
| 管理自有标签 | ✅ | ✅ |
| RAG 对话/Agent 任务/反馈 | ✅ | ✅ |
| 创建/删除部门 | ❌ | ✅ |
| 查看全部文档/对话/反馈 | ❌ | ✅ |
| 管理全部标签 | ❌ | ✅ |
| 删除任意文档 | ❌ | ✅ |
| 反馈状态流转 | ❌ | ✅ |

### 7.3.2 服务端强校验（非前端隐藏）

1. 每个 service 方法接收当前用户上下文（uid/role/dept_id）；
2. 数据访问统一走带 `dept_scope` 的查询构造器（ORM 自动追加 `dept_id = 当前用户 dept_id`）；
3. 资源归属校验：文档/会话/任务操作前校验 `upload_user_id / user_id` 与当前 uid 一致（staff）或角色 admin；
4. 接口层返回 10003（403）而非仅前端路由隐藏；
5. 权限校验写审计日志（denied 事件记录）。

## 7.4 审计日志

- **覆盖动作**：登录成功/失败、上传、下载、删除（文档/会话/部门）、标签管理、Agent 创建/确认/取消、反馈状态流转、管理员查看全量数据、权限拒绝事件；
- **记录字段**：user_id、username、action、object_type/id、detail（脱敏 JSON）、ip、user_agent、result、create_time；
- 审计日志只增不改，普通管理员不可删除；保留 ≥ 180 天（可按策略转归档）。

## 7.5 敏感信息保护与脱敏

| 数据 | 策略 |
| --- | --- |
| 密码 | bcrypt 哈希，永不回显 |
| 文档内容 | 仅授权部门/用户可见；对话引用切片按权限过滤；导出/下载走鉴权 |
| 对话内容 | 员工本人可见，管理员可见列表不含原文（原文档排除项保持）；日志/审计中脱敏 |
| 个人信息 | 列表接口默认脱敏（username 脱敏规则可配），详情接口按权限返回 |
| LLM 请求 | 发送至通义千问前按策略过滤敏感字段（可选本地敏感词/合规过滤，P2 细化） |
| 审计 detail | 不含密码、完整正文、完整 token |

## 7.6 密钥管理

- **不落代码库**：密钥只经环境变量 / .env（不入 Git）/ 部署平台的 Secret 注入；
- 生产采用密钥管理：Docker Secrets / GitLab CI 变量 / 云 KMS（根据部署环境选一）；
- 密钥清单：JWT 私钥、DB 密码、Redis 密码、MinIO 密钥、LLM API Key、OCR 服务密钥；
- 定期轮换策略：JWT 密钥 90 天、数据库密码 180 天，轮换流程写入运维手册。

## 7.7 文件安全

- 上传：扩展名白名单 + MIME + magic bytes 三重校验；文件重命名（hash 命名）防路径穿越与上传可执行文件；
- 存储：MinIO 私有桶，不开放匿名访问；路径含 dept_id 但**不依赖路径做权限**，下载走服务端鉴权后临时 URL；
- 扫描：可选病毒扫描（ClamAV，P2）；
- 预览：pdf.js 沙箱渲染；下载响应加 `Content-Disposition: attachment` + 正确 Content-Type，防 XSS（SVG 等风险类型限制）。

## 7.8 传输与基础设施安全

- 全链路 HTTPS（Nginx TLS 终结，TLS 1.2+）；
- Nginx 层安全头：HSTS、X-Content-Type-Options、X-Frame-Options、CSP；
- 限流：IP 级（Nginx）+ 用户级（Redis：登录/上传/SSE）；
- 依赖安全：CI 中依赖漏洞扫描（pip-audit/npm audit）、镜像漏洞扫描（Trivy）；
- 运行加固：应用以非 root 运行、最小权限 DB 账号（业务账号仅 DML，迁移用独立账号）、容器只读根文件系统（可选）。

---

# 第 8 章 部署架构

## 8.1 部署总体架构

```
                        ┌──────────────────────────────┐
   用户浏览器 (HTTPS)    │         Nginx (TLS/静态/限流)   │
        │               └──────────────┬───────────────┘
        │                     /api/*    │ /(静态资源)
        │                ┌──────────────▼───────────────┐
        │                │   FastAPI 应用服务 (api)       │
        │                │  (gunicorn/uvicorn 多 worker) │
        │                └───────┬──────────┬───────────┘
        │                         │          │
   ┌────▼────────┐    ┌───────────▼──┐  ┌───▼─────────────┐
   │  PostgreSQL │    │  Redis        │  │  Celery Worker  │
   │  (+pgvector)│    │  (缓存/队列)  │  │  (解析/OCR/向量/  │
   └────┬────────┘    └───────────┬──┘  │   Agent 任务)     │
        │                         │     └───────┬─────────┘
   ┌────▼────────┐    ┌───────────▼──┐          │
   │   MinIO     │    │  PaddleOCR    │          │
   │ 对象存储     │    │  独立服务      │          │
   └─────────────┘    └──────────────┘          │
                                                ▼
                                    ┌───────────────────────┐
                                    │   通义千问 API（外部）    │
                                    └───────────────────────┘
```

## 8.2 服务与容器清单

| 服务 | 镜像/技术 | 端口（内部） | 说明 |
| --- | --- | --- | --- |
| nginx | nginx:1.27-alpine | 80/443 | 静态资源、反向代理、TLS、限流 |
| api | 自建（python:3.12-slim） | 8000 | FastAPI，gunicorn + uvicorn worker |
| worker | 同 api 镜像（不同 command） | — | Celery worker + beat（如需定时） |
| ocr | 自建（PaddleOCR） | 8100 | OCR 识别独立服务 |
| db | postgres:15 + pgvector 扩展 | 5432 | 业务 + 向量 |
| redis | redis:7-alpine | 6379 | 缓存/队列/限流 |
| minio | minio/minio | 9000/9001 | 对象存储 + 控制台 |
| prometheus/grafana/loki | 官方镜像 | 9090/3000/3100 | 监控告警（部署环境启动） |

## 8.3 Docker Compose（开发/测试环境）

```yaml
version: "3.9"

services:
  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: ai_assistant
      POSTGRES_USER: ai_app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ai_app -d ai_assistant"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data

  ocr:
    build:
      context: ./services/ocr
    expose: ["8100"]

  api:
    build:
      context: .
      dockerfile: Dockerfile
    command: gunicorn app.main:app -k uvicorn.workers.UvicornWorker -c gunicorn.conf.py
    environment:
      DATABASE_URL: postgresql+psycopg://ai_app:${DB_PASSWORD}@db:5432/ai_assistant
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      MINIO_ENDPOINT: minio:9000
      OCR_SERVICE_URL: http://ocr:8100
      LLM_API_KEY: ${LLM_API_KEY}
      JWT_PRIVATE_KEY: ${JWT_PRIVATE_KEY}
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
      minio: { condition: service_started }
    ports: ["8000:8000"]

  worker:
    build: .
    command: celery -A app.celery_app worker -l info --concurrency=4
    environment: *API_ENV_ALIAS   # 实际以环境文件统一注入
    depends_on:
      - db
      - redis
      - ocr

  nginx:
    image: nginx:1.27-alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
    ports: ["80:80", "443:443"]
    depends_on:
      - api
```

> 说明：`environment: *API_ENV_ALIAS` 为示意，实际统一用 `.env` 文件注入（Compose 自动读取），并禁止 `.env` 提交 Git。

## 8.4 生产镜像规范

- 基础镜像：`python:3.12-slim`（后端）、`node:20-alpine`（前端构建）→ `nginx:alpine` 产物镜像；
- 多阶段构建：前端 `npm run build` 产出 dist 复制进 nginx 镜像；后端安装依赖（`--no-cache-dir`）后拷贝应用；
- 非 root 运行：后端镜像创建 `appuser`，`USER appuser`；容器内不写系统目录；
- 健康检查：每个服务实现 `/healthz`（应用）/ `pg_isready`（DB）/ `redis-cli ping`；
- 镜像体积与安全：`--no-cache`、裁剪开发依赖、Trivy 扫描（漏洞阻断发布）；
- 标签：`{app}:{git_short_sha}`，可追溯代码版本。

## 8.5 CI/CD 流水线

### 8.5.1 CI（GitLab CI / GitHub Actions）

| 阶段 | 步骤 |
| --- | --- |
| lint & format | ruff / flake8（后端）、eslint + prettier（前端） |
| 单元测试 | pytest + coverage（后端，覆盖率 ≥ 80% 门禁）、vitest（前端） |
| 集成测试 | docker compose 起依赖，跑接口级测试 |
| 依赖扫描 | pip-audit、npm audit |
| 构建镜像 | 多阶段构建后端/前端/OCR 镜像，Trivy 漏洞扫描 |
| 推送制品 | 推送镜像仓库（带 git_short_sha 标签） |

### 8.5.2 CD（测试/预生产/生产）

- **测试环境**：merge 到 develop 自动部署（docker compose up）；
- **预生产**：打 tag（v*）自动部署并跑回归（冒烟 + 关键链路）；
- **生产**：人工确认按钮发布，采用蓝绿或滚动发布（规模小先蓝绿：新版本起一组，Nginx 切换权重，回滚切回旧组）；
- 迁移策略：**发布前先跑 Alembic 迁移（只进不退）**，数据库备份先行；迁移失败立即停止发布，回滚应用版本；
- 回滚：镜像保留最近 N 个版本，一键回滚上一稳定镜像 + 数据库按需恢复。

## 8.6 环境划分

| 环境 | 用途 | 数据 | 资源 |
| --- | --- | --- | --- |
| dev | 开发自测 | 样本数据 | 单机 docker compose |
| test | 联调/测试 | 脱敏测试数据 | 单机 docker compose |
| staging | 预生产验收 | 准生产数据（脱敏） | 单机或双机 |
| prod | 生产 | 真实数据 | 生产服务器（初期单机 + 定期备份，规模增长上多机/K8s） |

## 8.7 网络与安全加固（部署侧）

- Nginx 仅暴露 80/443；内部服务不暴露公网（Docker 内网网络）；
- 数据库/Redis 仅内网访问并设置强密码；
- 上传大小限制、请求体限制、超时配置；
- 生产环境启用 WAF/防火墙策略（可选托管 WAF，P2）；
- 容器日志接入 Loki/Promtail 统一采集。

---

# 第 9 章 测试策略与性能指标

## 9.1 测试分层策略

| 层级 | 范围 | 工具 | 质量门禁 |
| --- | --- | --- | --- |
| 单元测试 | service/repository/工具函数 | pytest | 覆盖率 ≥ 80% |
| 接口测试 | API 契约、鉴权、权限、错误码 | pytest + httpx | 核心接口 100% 覆盖 |
| 组件测试 | 文档解析/切片/OCR/向量入库 | pytest + 真实依赖（test 环境） | 关键链路通过 |
| 前端测试 | 组件/路由权限/SSE 渲染 | vitest + Vue Test Utils | 关键组件用例通过 |
| E2E 测试 | 主链路（上传→检索→问答→反馈/Agent 确认） | Playwright | 冒烟用例全通过 |
| 性能测试 | 接口压测、向量检索、并发 | Locust / k6 | 达标（见 9.3） |
| 安全测试 | 越权/注入/上传绕过/暴力破解 | 手工 + 工具扫描（ZAP 可选） | 高危漏洞 0 |
| 验收测试 | 按里程碑验收标准逐项验证 | 手工 + 脚本 | 里程碑通过 |

## 9.2 测试数据与隔离

- 单元测试：内存/独立测试库，隔离外部服务（mock LLM/OCR）；
- 集成测试：docker compose 起 PG+Redis+MinIO+OCR 测试环境，**独立数据库实例**，测试后清理；
- 种子数据：`tests/fixtures` 提供样本 PDF/Word/Excel/扫描件、部门与账号矩阵（staff/admin、跨部门用例）；
- LLM 依赖：RAG/Agent 接口测试使用 mock 或固定响应（避免外部依赖不稳定）；真实 LLM 用例独立标 @slow 标签，不在常规 CI 全跑。

## 9.3 性能指标与压测目标

| 指标 | 目标值 | 说明 |
| --- | --- | --- |
| RAG 问答首 token 延迟（SSE） | P50 ≤ 1s | 向量检索 + 首包输出 |
| RAG 问答完整响应（≤3 切片输入） | P95 ≤ 20s | 受 LLM 生成时长影响，记录并监控 |
| 向量检索（50 万切片规模） | P95 ≤ 500ms | pgvector HNSW |
| 文档列表/分页查询 | P95 ≤ 500ms | 索引 + 分页 |
| 并发会话 | 200 并发用户 | 登录 + RAG 混合场景，错误率 < 1% |
| 系统可用性 | ≥ 99.5% | 月度 |
| 解析吞吐 | 单文档（≤50MB）解析入库 ≤ 3 分钟 | 不含 OCR 长文档排队 |
| OCR 吞吐 | 扫描 PDF 单页 ≤ 5s | OCR 服务压测 |

**压测方案要点**：
1. 工具：Locust（HTTP 并发场景）或 k6（脚本化 RAG SSE 场景）；
2. 场景：登录 + 文档列表、上传并发（少量）、RAG 问答（重点）、Agent 任务创建；
3. 基线环境：生产同等规格（预生产环境）执行，记录基线数值入库；
4. 报告：每次压测输出 P50/P95/P99、错误率、资源使用（CPU/内存/连接数），与目标对照。

## 9.4 功能验收用例（抽样）

| 编号 | 用例 | 预期 |
| --- | --- | --- |
| TC-01 | 上传 PDF/Word/Excel/扫描版各 1 个 | 状态流转 success，进度条走完 |
| TC-02 | 上传加密/损坏 PDF | 前端弹窗提示原因，fail_msg 展示 |
| TC-03 | 重复上传同文件 | version_no+1，可切换版本，仅检索选中版本 |
| TC-04 | 跨部门访问文档 | 返回 403，列表不可见 |
| TC-05 | staff 删除他人文档 | 返回 403，审计记录 denied |
| TC-06 | RAG 问答带引用 | 回答附引用，点击跳转页码/工作表 |
| TC-07 | 重置上下文后提问 | 不再携带历史上下文，顶部提示条出现 |
| TC-08 | Agent 任务人工确认 | retrieving → waiting_confirm → finished |
| TC-09 | Agent 确认超时 | 10 分钟未确认自动 failed |
| TC-10 | 管理员查看反馈 | 列表不含原始问答 |
| TC-11 | LLM 超时 | 返回 20003 错误事件，前端友好提示 |
| TC-12 | 删除文档 | 业务记录 + 切片 + 向量全部清理 |

## 9.5 质量门禁（CI 强制）

- 单元覆盖率 < 80% → 流水线失败；
- 接口测试任一失败 → 阻断合并；
- 高危安全漏洞 → 阻断发布；
- 性能基线回归（关键接口 P95 劣化 > 20%）→ 需评审后合入。

---

# 第 10 章 监控运维与备份恢复

## 10.1 监控体系

### 10.1.1 指标采集（Prometheus）

| 指标 | 来源 | 说明 |
| --- | --- | --- |
| API QPS / 延迟 P50/P95/P99 | FastAPI Prometheus 中间件 | 分接口、分路径标签 |
| SSE 连接数与成功率 | 应用埋点 | RAG 流式健康度 |
| 业务指标 | 应用埋点 | 上传/解析/OCR/向量化任务数、成功率、队列深度 |
| Agent 任务状态分布 | 应用埋点 | retrieving/waiting_confirm/finished/failed |
| LLM 调用指标 | llm_call_log 统计导出 | 调用量、失败率、超时率、费用估算、token 消耗 |
| DB/Redis/MinIO/OCR 健康 | exporters + 探针 | 连接数、延迟、磁盘、内存 |
| 主机资源 | node_exporter | CPU/内存/磁盘/网络 |

### 10.1.2 日志（Loki + Promtail / structlog）

- 应用结构化日志：`structlog` 输出 JSON（ts/level/service/trace_id/user_id/action/duration/error）；
- 请求全链路：中间件生成 `trace_id`（Header 透传），日志与监控关联；
- 日志分级：info（业务）、warn（重试/降级）、error（异常/失败）、audit（审计）；
- 日志保留：热存储 7 天、冷归档 30+ 天（按合规要求可延长至 180 天）。

### 10.1.3 告警规则

| 告警 | 阈值（示例） | 级别 | 动作 |
| --- | --- | --- | --- |
| API 错误率 | > 2% 持续 5 分钟 | P1 | 通知 + 拉群 |
| RAG 首 token 延迟 P95 | > 3s 持续 10 分钟 | P2 | 通知 |
| LLM 调用失败/超时率 | > 5% 持续 5 分钟 | P1 | 通知 + 检查网关 |
| 队列积压（Celery） | > 100 且持续 10 分钟 | P2 | 扩容 worker |
| 磁盘使用 | > 80% | P2 | 扩容/清理 |
| 容器重启 | 5 分钟内重启 ≥ 3 次 | P1 | 通知 |
| 备份失败 | 任何一次 | P1 | 通知 |
| DB 连接数 | > 80% 上限 | P2 | 通知 |

## 10.2 运维 SOP（标准操作流程）

| 场景 | SOP 要点 |
| --- | --- |
| 版本发布 | 备份 DB → Alembic 迁移 → 蓝绿切换 → 冒烟验证 → 观察指标 30 分钟 |
| 回滚 | 切回上一稳定镜像；DB 已迁移则先评估兼容（前向兼容原则：迁移只加不破坏） |
| 扩容 | worker 增加实例/并发；API 增加副本（Nginx upstream）；OCR 单页延迟劣化时增加 OCR 实例 |
| 配置变更 | 改 sys_config + 环境变量，走发布流程，变更留痕 |
| 日志排查 | 按 trace_id 聚合；先查 Loki 再对指标 |
| 每周巡检 | 备份完整性、磁盘、证书到期、依赖漏洞提醒 |

## 10.3 备份与恢复

### 10.3.1 PostgreSQL

- 备份：每日全量 `pg_dump`（或 `pg_basebackup`）+ 每日 WAL 归档（连续归档支持 PITR）；
- 保留：全量保留 30 天，月度归档 12 个月；
- 存储：备份至异地/独立存储（MinIO 备份桶或云对象存储），加密存储；
- 恢复演练：每季度执行一次**恢复演练**（到独立实例，验证数据完整性与启动可用性）；
- RPO：≤ 24h（每日全量 + WAL）；RTO：≤ 4h（标准恢复流程）；关键升级场景前追加手动快照（RPO 近 0）。

### 10.3.2 Redis

- 数据多为缓存/进度/限流，可重建；持久化开启 AOF（appendfsync everysec）；
- 关键会话上下文不建议强依赖 Redis（会话数据以 PG 为准，Redis 缓存可重建）。

### 10.3.3 MinIO 对象存储

- 启用版本控制 + 生命周期策略（文档文件保留多版本 30 天）；
- 定时镜像/异地复制（备选）；误删恢复走版本回溯。

### 10.3.4 向量数据

- pgvector 数据随 PostgreSQL 一并备份（同库），无需单独流程；
- 恢复后验证：抽样检索 TopK 返回一致性（自检脚本）。

### 10.3.5 恢复流程清单

1. 通知相关方，进入应急预案；
2. 恢复 PG（最近全量 + WAL 到目标时间点）→ 校验表数量与行数；
3. 恢复 MinIO（版本回溯/镜像拉取）→ 校验关键文件可下载；
4. 启动应用（迁移版本与备份版本一致校验）；
5. 冒烟测试（登录/列表/检索问答/Agent）；
6. 记录复盘报告。

## 10.4 高可用与容灾（分阶段）

- **上线一期（单机）**：Docker Compose 部署、每日备份 + 恢复演练、告警监控；满足企业试运行；
- **上线二期（推荐）**：PG 主从流复制（同步备库）、API/Worker 多副本 + Nginx 负载、MinIO 异地复制、跨机部署，可用性达 99.9%；
- **演进（可选）**：Kubernetes 编排、自动伸缩、多云容灾。

## 10.5 容量规划（预估）

| 资源 | 起步配置 | 说明 |
| --- | --- | --- |
| CPU | 8 核（API 2 + Worker 4 + OCR 2） | 视并发与 OCR 负载调整 |
| 内存 | 32GB（PG 8G、Redis 4G、API/Worker 16G） | pgvector HNSW 索引占用内存 |
| 磁盘 | 500GB SSD（DB + MinIO 分盘） | 按文档量与版本数扩展 |
| 网络 | 带宽 ≥ 100Mbps | LLM 依赖外网，必要时专线/代理 |

---

# 第 11 章 里程碑排期

## 11.1 整体思路：从零开发到落地

**开发主线**：先骨架与基础设施 → 文档入库链路 → RAG 问答链路 → Agent 链路 → 前端串联 → 企业级加固（安全/测试/监控/部署）→ 试运行落地。**每个里程碑以"可演示、可验收"为出口，而不是"代码写完"**。

**项目节奏**：共 6 个里程碑（M0-M5），总投入约 **120 人天**（后端 55 / 前端 35 / 测试与联调 20 / 运维与安全 10），周期约 4 个月（按 2 人后端 + 1.5 人前端 + 0.5 人测试/运维折算，可并行压缩至 3 个月）。

## 11.2 里程碑排期与验收标准

| 里程碑 | 周期 | 人天 | 关键交付 | 验收标准 |
| --- | --- | --- | --- | --- |
| **M0 项目启动与基础设施** | 第 1-2 周 | 12 | 项目骨架（FastAPI+Vue3）、PG/pgvector/Redis/MinIO 容器化、Alembic 迁移框架、CI 流水线骨架、日志与错误码规范落地 | docker compose 一键起服务；CI lint+单测通过；登录接口可调通 |
| **M1 认证与权限体系** | 第 2-3 周 | 14 | 双 token 认证、RBAC + 部门隔离中间件、用户/部门管理接口、审计日志框架、前端登录与路由拦截 | 越权用例返回 403；审计日志完整；权限矩阵用例全过 |
| **M2 文档入库链路** | 第 3-6 周 | 28 | 上传/解析/OCR 服务化/摘要抽取/重叠切片/向量入库/多版本/标签/筛选/进度条/删除一致性 | 四类文档解析入库成功；版本切换仅检索选中版本；删除后向量无孤儿；进度条实时 |
| **M3 RAG 问答链路** | 第 6-8 周 | 22 | 会话管理、SSE 流式问答、原文溯源、重置上下文、反馈；前端对话页 | 带溯源流式回答可交互；溯源跳转页码/工作表；反馈入库管理员可见 |
| **M4 Agent 任务链路** | 第 8-10 周 | 20 | LangGraph 三任务、人工确认中断、超时取消、持久化与回看、前端 Agent 页 | 周报/对比/方案全流程走通；确认/取消/超时三态正确；任务结果可回看导出 |
| **M5 企业级加固与交付** | 第 10-14 周 | 24 | 管理员后台、E2E 与压测、安全加固、监控告警、备份恢复、预生产部署、上线演练、文档与运维手册 | 压测达标（200 并发/错误率<1%）；恢复演练通过；可用性达标；交付验收清单全绿 |

## 11.3 分阶段人天预估明细

| 阶段 | 后端 | 前端 | 测试/联调 | 运维/安全 | 小计 |
| --- | --- | --- | --- | --- | --- |
| M0 启动与基础设施 | 6 | 2 | 2 | 2 | 12 |
| M1 认证与权限 | 8 | 4 | 2 | 0 | 14 |
| M2 文档入库链路 | 16 | 8 | 3 | 1 | 28 |
| M3 RAG 问答链路 | 10 | 8 | 3 | 1 | 22 |
| M4 Agent 任务链路 | 11 | 6 | 3 | 0 | 20 |
| M5 加固与交付 | 4 | 7 | 7 | 6 | 24 |
| **合计** | **55** | **35** | **20** | **10** | **120** |

## 11.4 关键路径与依赖关系

```
M0 ──▶ M1 ──▶ M2 ──▶ M3 ──▶ M4 ──▶ M5
                 ▲        ▲
                 │        └── 依赖 M2（向量检索）
                 └── 依赖 M1（权限）；M2 内部 OCR 服务可与 API 并行开发
```

- 关键路径：M0 → M1 → M2 → M3 → M5（M4 可与 M3 部分并行）；
- 风险缓冲：每里程碑预留 10% 缓冲（LLM/OCR 调优、集成问题）；
- 里程碑出口准则：验收标准全过才进入下一里程碑，未过则修复后复验。

## 11.5 交付物清单

| 类型 | 交付物 |
| --- | --- |
| 代码 | 后端源码、前端源码、OCR 服务、部署文件（Dockerfile/Compose/Nginx）、迁移脚本 |
| 文档 | 技术方案（本文档）、接口文档（OpenAPI 导出）、数据库设计文档、部署手册、运维手册、备份恢复手册 |
| 测试 | 测试用例集、压测报告、验收报告 |
| 数据 | 种子数据、初始化脚本、配置模板（.env.example） |
| 上线 | 预生产环境、生产环境部署记录、监控仪表盘、告警规则 |

## 11.6 上线与试运行计划

1. **试点阶段（2 周）**：选择一个部门试运行，观察检索质量、性能、稳定性，收集反馈；
2. **质量调优（1 周）**：按反馈调整切片参数、Prompt、版本策略；
3. **全量推广**：分批开放全部门，监控告警就绪；
4. **稳定运行观察（4 周）**：达到 99.5% 可用性与性能目标后转入正式运维；
5. **复盘**：输出试运行复盘报告，滚动优化。

---

# 第 12 章 风险清单

## 12.1 风险总览与应对

| 编号 | 风险 | 等级 | 概率 | 影响 | 应对措施 | 责任人/阶段 |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | LLM 服务（通义千问）不可用/限流/超时 | 高 | 中 | 高 | LLM 网关：超时重试 + 熔断降级 + 备用模型/渠道；降级提示"暂时无法作答"；调用量监控告警 | 后端/M3 |
| R-02 | RAG 检索质量差（切得不合理、回答不准） | 高 | 中 | 高 | 重叠切片调优、top_k 与阈值调参、Prompt 工程、反馈闭环驱动优化、试点评估指标（Top5 命中率） | 后端/M3 |
| R-03 | 扫描版 PDF OCR 识别率低 | 中 | 高 | 中 | OCR 独立服务 + 置信度监控；低置信度提示；第三方 OCR 备用（OcrProvider 抽象）；可人工补充录入（P2） | 后端/M2 |
| R-04 | 数据越权（跨部门/跨用户）漏洞 | 高 | 低 | 极高 | 服务端 dept_scope 强校验 + 越权用例测试 + 审计日志；安全评审关口 | 后端/M1、M5 |
| R-05 | 文档删除后向量残留（孤儿数据） | 中 | 中 | 中 | 先删向量后删记录 + 补偿任务每日扫描清理孤儿向量 | 后端/M2 |
| R-06 | 大文档/大量版本导致存储与检索性能劣化 | 中 | 中 | 中 | 版本上限、文件大小限制、容量监控、索引维护、归档策略 | 后端/M5 |
| R-07 | 并发上升后 PG/pgvector 或 API 成为瓶颈 | 中 | 中 | 中 | 压测基线、索引优化、缓存、横向扩容（worker/副本）、备选 Milvus | 后端/M5 |
| R-08 | 需求蔓延（超出原技术文档范围的功能） | 中 | 高 | 中 | 范围边界明确（第 1 章），变更走变更评审，P2 项统一放入后续迭代 | 全员/全阶段 |
| R-09 | 团队对 LangGraph 中断恢复/SSE 实现经验不足 | 中 | 中 | 中 | 里程碑前技术预研（M4 前 Spikes）、明确参考实现、保留替代方案（状态机自实现） | 后端/M4 |
| R-10 | 密钥/凭据泄露 | 高 | 低 | 极高 | 密钥不入库、Secret 管理、最小权限账号、轮换策略、扫描告警 | 运维/全阶段 |
| R-11 | 前端 XSS/上传恶意文件 | 中 | 低 | 高 | 文件三重校验、CSP 等安全头、pdf.js 沙箱、依赖扫描 | 前端/M5 |
| R-12 | 依赖供应链漏洞 | 中 | 中 | 中 | pip-audit / npm audit / Trivy 门禁，定期更新 | 运维/CI 起 |
| R-13 | 数据备份失败/恢复不可用 | 中 | 低 | 极高 | 备份告警 + 季度恢复演练 + 异地存储 | 运维/M5 |
| R-14 | 排期延期（OCR/LLM 调优超预期） | 中 | 中 | 中 | 里程碑缓冲 10%、关键路径管理、范围裁剪预案（先交付核心链路） | 项目组/全阶段 |
| R-15 | 管理员误操作（误删部门/文档） | 中 | 低 | 高 | 删除保护、二次确认、回收站/软删恢复期、审计追溯 | 全阶段 |

## 12.2 风险应对机制

1. **风险登记与例会**：里程碑例会更新风险状态（概率/影响/应对进度）；
2. **风险触发预案**：R-01/R-04 等高危风险提前制定预案文档，预演一次；
3. **变更控制**：超出范围需求统一登记 backlog，不打断当前里程碑；
4. **技术预研（Spike）**：M4 前完成 LangGraph 中断与 SSE 长连接预研，降低 R-09；
5. **上线安全评审**：M5 交付前做安全与备份演练双评审，未通过不投产。

## 12.3 依赖外部条件

| 依赖 | 说明 | 风险 |
| --- | --- | --- |
| 通义千问 API Key 与配额 | 需企业账号与额度评估 | 高（见 R-01） |
| 部署服务器资源 | 生产/预生产服务器申请 | 中 |
| 企业网络策略 | LLM 外网访问/防火墙放行 | 中 |
| 测试数据 | 需要真实脱敏文档样本 | 中 |

---
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
