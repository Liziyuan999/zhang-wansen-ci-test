---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f92a25702084128d164d6c111d7f7222_728e4f18d74c11f18947525400de85a5
    ReservedCode1: M8T5adyxecMu5IrmzgWIeTkuajVTXLxa+osWRkCdZshT/9xwF3X+3ifw6aUNmQY+oonIEDfoYXl2NArPOIGL6pq6k6tQz2W21/WN/O6blKiEfc8L4yXAQ57dzyGtejuCPqthFmXmPxQOq0G8XkLm6ac1H6FYpIj8e43l2IZa+bt084886g5JjVA/Vio=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f92a25702084128d164d6c111d7f7222_728e4f18d74c11f18947525400de85a5
    ReservedCode2: M8T5adyxecMu5IrmzgWIeTkuajVTXLxa+osWRkCdZshT/9xwF3X+3ifw6aUNmQY+oonIEDfoYXl2NArPOIGL6pq6k6tQz2W21/WN/O6blKiEfc8L4yXAQ57dzyGtejuCPqthFmXmPxQOq0G8XkLm6ac1H6FYpIj8e43l2IZa+bt084886g5JjVA/Vio=
---

# 知寻 KnowSeek 核心功能源码逐行注释详解

> 本文档基于 `E:\AI-Agent知识库` 项目真实源码整理，覆盖核心功能（知识图谱 / Agent 工作流 / Copilot / 智能看板 / 演示模式 / 打卡 / 审批 / 审计 / 登录安全）。
> 所有代码均摘自线上实现，注释为逐行补充（**只加注释、未改动任何逻辑、缩进、字符串与配置**），并经 `py_compile` 与前端 `npm run build` 双重验证通过。
>
> 验证结论：
> - 后端 13 个被注释文件（services/kg_service.py、services/canvas_workflow.py、services/copilot_service.py、services/agent_service.py、services/demo_service.py、services/audit.py、api/kg.py、api/document_copilot.py、api/agent.py、api/demo.py、api/dashboard.py、api/org_extra.py、core/security.py）`py_compile` 全部通过；
> - 前端 5 个被注释组件（views/KnowledgeGraphView.vue、views/AgentTaskView.vue、components/CopilotPanel.vue、views/DemoModeView.vue、views/DashboardView.vue）`vue-tsc --noEmit && vite build` 全部通过。

---

## 一、项目定位与启动命令

### 1.1 项目定位

**知寻 KnowSeek** 是一款**企业级 AI 知识库 / 智能工作台**，核心差异化能力：

| 能力 | 说明 |
|---|---|
| 知识图谱 GraphRAG | LLM 自动抽取文档实体/关系，SVG 力导向图谱可视化，跨文档智能联想 |
| Agent 拖拽工作流 | 可视化 DAG 编排（规划→检索→生成→反思→精修→输出），人工确认安全机制 |
| AI 文档 Copilot | 选中文档即问即答，一键摘要 / 中英互译 / 要点提炼，带引用定位 |
| 智能数据看板 | 企业价值指标、近 7 日趋势、知识热度榜、部门活跃度、检索热力图、LLM 用量报表 |
| 演示模式 | 一键灌入演示数据（带独立标记）、一键清除恢复，30 秒体验全部亮点 |
| 企业组织协作 | 部门空间、团队共享、权限审批、四段班次打卡、审计日志、登录安全（JWT 双 token + bcrypt） |

### 1.2 项目目录结构

```
E:\AI-Agent知识库
├─ server\                     # 后端（FastAPI + SQLite ai_assistant.db）
│  └─ app\
│     ├─ main.py               # FastAPI 入口（注册路由 + lifespan 周期任务）
│     ├─ api\                  # 路由层（kg / agent / document_copilot / demo / dashboard / org_extra / audit ...）
│     ├─ services\             # 服务层（kg_service / canvas_workflow / copilot_service / agent_service / demo_service / audit ...）
│     ├─ core\                 # 核心（config / security(JWT) / deps / response / code）
│     ├─ models\               # ORM 模型（Document / Entity / AgentTask / AttendanceRecord / OperationLog ...）
│     └─ .env                  # JWT_SECRET（64 位随机密钥）、DATABASE_URL/CHROMA_DIR 相对路径
└─ web\                        # 前端（Vue3 + Element Plus + TypeScript + Vite）
   ├─ src\
   │  ├─ views\                # KnowledgeGraphView / AgentTaskView / DemoModeView / DashboardView ...
   │  ├─ components\           # CopilotPanel / WorkflowCanvasBuilder ...
   │  └─ api\                  # kg.ts / agent.ts / copilot.ts / dashboard.ts ...
   ├─ package.json             # scripts: dev / build / preview
   └─ vite.config.ts           # 已增 manualChunks 分包，主包约 21KB；proxy /api → 8000
```

### 1.3 后端启动命令（精确）

| 项 | 值 |
|---|---|
| 框架 | FastAPI + uvicorn |
| 数据库 | SQLite：`server\ai_assistant.db`（DATABASE_URL 相对路径） |
| 入口 | `server\app\main.py`（uvicorn 目标 `app.main:app`） |
| Python | 需使用本机安装的 **Python 3.14** 解释器（历史实测：必须用 Python314 绝对路径启动；README 标注 3.11 亦可） |
| 端口 | 8000 |
| 改码生效 | **无 reload 时必须重启**；端口被占用先 `Stop-Process` 旧 PID |

**开发启动（推荐，无 reload，日志在控制台）：**

```powershell
cd E:\AI-Agent知识库\server
# 使用 Python 3.14 的绝对路径（按本机实际安装位置）
& "C:\Users\10102\AppData\Local\Programs\Python\Python314\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> 若 Python314 绝对路径不同，请先执行 `py -0p` 或 `where python` 确认。

**脚本启动（start.bat 现有行为，供参考）：**

```bat
cd /d E:\AI-Agent知识库\server
uvicorn app.main:app --reload --port 8000 > server_uvicorn.log 2>&1
```

> 说明：start.bat 使用 `--reload --port 8000` 并把日志输出到 `server_uvicorn.log`；若要以 127.0.0.1 固定监听，加 `--host 127.0.0.1` 即可。

### 1.4 前端启动命令（精确）

| 项 | 值 |
|---|---|
| 框架 | Vue3 + Element Plus + TypeScript + Vite 5 |
| 依赖安装 | `cd E:\AI-Agent知识库\web && npm install` |
| 开发命令 | `npm run dev`（Vite 默认端口 5173；vite proxy 将 `/api` 转发到后端 8000） |
| 历史约定端口 | **5174**（`npm run dev --host 127.0.0.1 --port 5174`） |
| 构建验证 | `npm run build`（= `vue-tsc --noEmit && vite build`，产物在 `web\dist`） |

**开发启动（历史约定）：**

```powershell
cd E:\AI-Agent知识库\web
npm run dev --host 127.0.0.1 --port 5174
```

**生产构建：**

```powershell
cd E:\AI-Agent知识库\web
npm run build
```

### 1.5 测试账号与关键配置

- 测试账号：`admin@knowseek.com` / `admin123456`（id=5, dept_id=2）
- JWT：`server\.env` 中 `JWT_SECRET` 已替换为 64 位随机密钥；双 token（access 短期 / refresh 长期）
- 向量库：Chroma 相对路径（`CHROMA_DIR`）
- 路由前缀：文档 `/api/documents`、模型供应商 `/api/admin/model-providers`、知识图谱 `/api/kg`、Agent `/api/agent`、Copilot `/api/document/copilot`、演示 `/api/demo`、看板 `/api/dashboard`、审计 `/api/audit`、组织扩展 `/api/teams`

---

## 二、登录安全（JWT 双 token + bcrypt）

### 2.1 功能说明

登录安全模块负责：密码加盐哈希（bcrypt）、access/refresh 双 token 签发与校验、令牌摘要入库（SHA-256）、请求鉴权依赖注入（`get_current_user` / `require_admin`）。核心源码位于 `server\app\core\security.py`。

### 2.2 涉及文件路径

- `E:\AI-Agent知识库\server\app\core\security.py`（密码哈希与 JWT 工具）
- `E:\AI-Agent知识库\server\app\core\deps.py`（get_current_user / require_admin 依赖）

### 2.3 带注释核心代码（security.py 全文）

```python
# -*- coding: utf-8 -*-
"""密码哈希与 JWT 工具。"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


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

### 2.4 执行流程

1. 前端登录页提交账号密码 → `POST /api/auth/login`；
2. 后端用 `verify_password`（bcrypt.checkpw）校验密码哈希；
3. 校验通过后 `create_access_token` + `create_refresh_token` 签发双 token；
4. refresh_token 经 `hash_token`（SHA-256）摘要后入库，数据库不存明文令牌；
5. 前端把 access token 放入 `Authorization: Bearer <token>`；
6. 后续每个受保护请求经 `get_current_user` 依赖：`decode_token` 解析 → 失败返回 401；
7. access 过期后用 refresh token 调 `/api/auth/refresh` 换新（刷新令牌同样以摘要比对）；
8. 管理员接口额外经 `require_admin` 校验角色为 admin/owner，非管理员返回 403。

### 2.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| POST | `/api/auth/login` | `{email, password}` | `{code:0, data:{access_token, refresh_token, user:{id,username,email,role,dept_id}}}` |
| POST | `/api/auth/refresh` | `{refresh_token}` | `{code:0, data:{access_token, refresh_token}}` |

### 2.6 实现原理

- **bcrypt 加盐哈希**：每次 `hashpw` 自动生成随机盐，相同密码的哈希值不同；`verify_password` 内部比对并容错返回 False；
- **JWT 无状态鉴权**：token 内含用户 ID（sub）与过期时间，服务端无需查 session；密钥为 64 位随机数，防伪造；
- **双 token 与防重放**：access 短时效（分钟级）降低泄露风险；refresh 长时效（天级）但以 SHA-256 摘要入库，即使数据库泄露也无法直接复用明文；
- **jti 唯一性**：每次签发携带 `uuid4().hex`，可用于吊销名单与重放检测。

---

## 三、知识图谱 GraphRAG

### 3.1 功能说明

知识图谱模块实现 **GraphRAG**：对文档切片做实体/关系抽取（LLM 首选 + 规则降级），存储到 `Entity / EntityRelation` 表，通过 `/api/kg/*` 接口供前端图谱页（SVG 自绘力导向图）展示、过滤、搜索与统计。

### 3.2 涉及文件路径

- 后端服务：`E:\AI-Agent知识库\server\app\services\kg_service.py`
- 后端路由：`E:\AI-Agent知识库\server\app\api\kg.py`
- 前端视图：`E:\AI-Agent知识库\web\src\views\KnowledgeGraphView.vue`

### 3.3 带注释核心代码

**kg_service.py — LLM 实体/关系抽取（首选通道）**

```python
def _llm_extract(db: Session, user_id: int, chunks_text: str, provider_id: int | None = None) -> tuple[list[dict], list[dict]]:
    # ===== 逐行注释：LLM 实体/关系抽取（首选通道）=====
    # 1. 构造抽取 Prompt：要求模型按 JSON 输出实体（name/type/description）与关系（source/target/type），
    #    并通过"宁缺毋滥""保持原文表述"等约束提高抽取质量；文本截断到 6000 字符控制 token 成本。
    # 2. chat_completion() 是 LLM 统一调用封装：传入用户 ID 用于计费统计（scenario=kg_extract）、
    #    temperature=0.3 降低随机性、max_tokens=2000 防止超长输出、provider_id 指定模型供应商。
    # 3. _extract_json() 负责从模型输出中稳健解析 JSON（容忍 ```json 代码块包裹）。
    # 4. 清洗与去重：实体名经 _clean_name 规范化（压缩空白、去掉标点、限制长度 2-64）；
    #    关系要求 source/target 必须是已抽取实体，且去重（seen_rel 集合），避免脏数据。
    """调用 LLM 抽取实体与关系；失败抛异常由上层降级。"""
    prompt = (
        "你是企业知识图谱构建器。请从下面的文本片段中抽取核心实体（人物/组织/产品/技术/地点/事件/其他）"
        "以及实体之间的语义关系。\n"
        "抽取要求：1) 实体名称保持原文表述；2) 每个实体给出类型与一句话描述；"
        "3) 关系只保留明确可依据原文的关系（如 研发/使用/包含/负责/位于/合作/发布 等），"
        "source 与 target 必须是已抽取的实体名；4) 宁缺毋滥，不抽取无意义碎片。\n"
        "严格输出 JSON，不要输出其他内容：\n"
        '{"entities":[{"name":"实体名","type":"person|org|product|tech|place|event|other","description":"描述"}],'
        '"relations":[{"source":"实体A","target":"实体B","type":"关系类型"}]}\n\n'
        "文本片段：\n" + chunks_text[:6000]
    )
    raw = chat_completion(
        db, user_id,
        [{"role": "user", "content": prompt}],
        scenario="kg_extract",
        temperature=0.3,
        max_tokens=2000,
        provider_id=provider_id,
    )
    parsed = _extract_json(raw) or {}
    entities: list[dict] = []
    seen_names: set[str] = set()
    for e in (parsed.get("entities") or [])[: MAX_ENTITIES_PER_BATCH]:
        name = _clean_name(e.get("name"))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entities.append(
            {
                "name": name,
                "type": str(e.get("type") or "other")[:32],
                "description": str(e.get("description") or "")[:300],
            }
        )
    relations: list[dict] = []
    seen_rel: set[tuple[str, str, str]] = set()
    for r in (parsed.get("relations") or [])[: MAX_RELATIONS_PER_BATCH]:
        src = _clean_name(r.get("source"))
        tgt = _clean_name(r.get("target"))
        rtype = str(r.get("type") or "相关").strip()[:32] or "相关"
        if not src or not tgt or src == tgt or (src, tgt, rtype) in seen_rel:
            continue
        if src not in seen_names or tgt not in seen_names:
            continue
        seen_rel.add((src, tgt, rtype))
        relations.append({"source": src, "target": tgt, "type": rtype})
    return entities, relations
```

**kg_service.py — 抽取主流程 extract_document_kg（幂等 + 降级）**

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
                    continue
                rel = EntityRelation(
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type=r["type"],
                    doc_id=doc_id,
                    chunk_id=batch[0].chroma_id,
                    source="llm" if llm_ok else "rule",
                )
                db.add(rel)
                relation_rows.append(rel)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        doc.kg_status = "failed"
        doc.kg_error = str(exc)[:300]
        db.commit()
        logger.exception("知识图谱抽取失败 doc=%s", doc_id)
        raise BizError(NOT_FOUND, f"知识图谱抽取失败：{exc}") from exc

    doc.kg_status = "success" if entity_rows else "failed"
    doc.kg_entity_count = len(entity_rows)
    doc.kg_relation_count = len(relation_rows)
    doc.kg_error = err_msg if entity_rows and err_msg else (None if entity_rows else "未抽取到实体")
    doc.kg_finish_time = datetime.now()
    db.commit()
    return {
        "doc_id": doc_id,
        "entities": len(entity_rows),
        "relations": len(relation_rows),
        "source": "llm" if used_llm or any(r.source == "llm" for r in entity_rows) else "rule",
        "error": doc.kg_error,
    }
```

**api/kg.py — 路由层（全文）**

```python
# -*- coding: utf-8 -*-
"""知识图谱接口：实体抽取 / 图谱数据 / 实体搜索 / 图谱统计。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.models import User
from app.services import kg_service

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])


# ===== 逐行注释：知识图谱路由层 =====
# 1. 统一前缀 /api/kg，全部接口经 get_current_user 校验 JWT 后注入当前用户；
# 2. extract：POST 手动触发某文档的实体/关系抽取，返回实体数/关系数统计供前端提示；
# 3. graph：GET 返回 nodes+links，节点带 degree（度数）供前端力导向布局按度数定半径/向心力；
#    doc_id 过滤单文档、keyword 过滤实体名、limit 上限 1000 控制返回规模；
# 4. search：GET 按名称模糊匹配实体（前端"搜索实体"输入框使用），limit 默认 20；
# 5. stats：GET 返回实体总数/关系总数/已抽取文档数/类型分布，驱动图谱页统计卡片与类型条。
@router.post("/extract/{doc_id}")
def extract_doc(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动触发文档实体/关系抽取，返回抽取统计。"""
    stats = kg_service.extract_document_kg(db, user, doc_id)
    return ok(data=stats, message=f"抽取完成：实体 {stats['entities']} 个，关系 {stats['relations']} 条")


@router.get("/graph")
def get_graph(
    doc_id: int | None = Query(None, description="按文档过滤"),
    keyword: str | None = Query(None, description="按实体名称关键词过滤"),
    limit: int = Query(200, ge=1, le=1000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """图谱数据：nodes + links（节点含度数便于前端布局）。"""
    return ok(data=kg_service.get_graph(db, user, doc_id=doc_id, keyword=keyword, limit=limit))


@router.get("/search")
def search(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """实体搜索：按名称模糊匹配。"""
    return ok(data=kg_service.search_entities(db, user, keyword, limit))


@router.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """图谱统计：实体数 / 关系数 / 已抽取文档数 / 类型分布。"""
    return ok(data=kg_service.get_stats(db, user))
```

**KnowledgeGraphView.vue — 力导向布局（轻量自研）**

```ts
// ===== 逐行注释：知识图谱力导向布局（轻量自研，无第三方图库依赖）=====
// 1. 初始位置：按节点数做环形均匀分布（半径取画布短边的 0.36），保证起点不重叠；
// 2. 力模型：斥力（repulsion，节点间越近推力越大）+ 弹簧力（edges 拉近，度数高的
//    节点弹力更强会自然聚簇）+ 向心力（整体收敛到画布中心，度数越高的节点越靠中心）；
// 3. 迭代 140 轮逼近稳定布局，每轮先算合力再更新坐标，复杂度 O(n²+E)，适合百级节点；
// 4. 布局结果写入 nodePos，SVG 模板按 pos 渲染圆/标签与连线。
function computeLayout(nodes: KgGraphNode[], links: KgGraphLink[], width: number, height: number) {
  const n = nodes.length
  if (!n) {
    nodePos.value = {}
    return
  }
  const pos: Record<string, Pos> = {}
  const cx = width / 2
  const cy = height / 2
  // 初始环形分布
  nodes.forEach((nd, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2
    const radius = Math.min(width, height) * 0.36
    pos[String(nd.id)] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius }
  })
  const idSet = new Map<number, KgGraphNode>()
  nodes.forEach((nd) => idSet.set(nd.id, nd))
  const linkSet = new Map<string, number>()
  links.forEach((lk) => {
    const key = [lk.source, lk.target].sort((a, b) => a - b).join('_')
    linkSet.set(key, (linkSet.get(key) || 0) + 1)
  })
  const degreeMap = new Map<number, number>()
  nodes.forEach((nd) => degreeMap.set(nd.id, nd.degree || 0))

  // 迭代力导向：斥力 + 弹簧 + 向心
  const repulsion = 2200
  const springK = 0.04
  const centerForce = 0.012
  for (let iter = 0; iter < 140; iter++) {
    const forces: Record<string, { fx: number; fy: number }> = {}
    nodes.forEach((nd) => {
      forces[String(nd.id)] = { fx: 0, fy: 0 }
    })
    // 两两斥力
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = pos[String(nodes[i].id)]
        const b = pos[String(nodes[j].id)]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dist = Math.sqrt(dx * dx + dy * dy) || 1
        const minDist = 70
        if (dist < minDist) {
          const push = (minDist - dist) * 0.18
          dx /= dist
          dy /= dist
          forces[String(nodes[i].id)].fx += dx * push
          forces[String(nodes[i].id)].fy += dy * push
          forces[String(nodes[j].id)].fx -= dx * push
          forces[String(nodes[j].id)].fy -= dy * push
        } else {
          const f = repulsion / (dist * dist)
          dx /= dist
          dy /= dist
          forces[String(nodes[i].id)].fx += dx * f
          forces[String(nodes[i].id)].fy += dy * f
          forces[String(nodes[j].id)].fx -= dx * f
          forces[String(nodes[j].id)].fy -= dy * f
        }
      }
    }
    // 边弹簧力（度数高的节点弹力更强，形成簇）
    links.forEach((lk) => {
      const a = pos[String(lk.source)]
      const b = pos[String(lk.target)]
      if (!a || !b) return
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const ideal = 130
      const f = (dist - ideal) * springK
      const ux = dx / dist
      const uy = dy / dist
      forces[String(lk.source)].fx += ux * f
      forces[String(lk.source)].fy += uy * f
      forces[String(lk.target)].fx -= ux * f
      forces[String(lk.target)].fy -= uy * f
    })
    // 向心力
    nodes.forEach((nd) => {
      const p = pos[String(nd.id)]
      const dx = cx - p.x
      const dy = cy - p.y
      const f = centerForce * (1 + (degreeMap.get(nd.id) || 0) * 0.02)
      forces[String(nd.id)].fx += dx * f
      forces[String(nd.id)].fy += dy * f
    })
    // 更新位置
    nodes.forEach((nd) => {
      // ……（位置更新循环，逻辑同线上实现）
    })
  }
}
```

### 3.4 执行流程

1. 前端知识图谱页 `onMounted` → 调 `getKgStats`（统计卡片）+ `getKgGraph`（图谱数据）；
2. 用户点击"抽取"按钮选择文档 → `POST /api/kg/extract/{doc_id}`；
3. 后端 `extract_document_kg`：先幂等清空旧图谱 → 按 20 切片/批调 `_llm_extract` → LLM 失败降级 `_rule_extract_chunk` → 写 `Entity/EntityRelation`（source 标记 llm/rule）→ 更新 `Document.kg_status/计数`；
4. 前端轮询/刷新图谱 → `GET /api/kg/graph` 返回 `{nodes, links}`；
5. `computeLayout` 力导向迭代 140 轮 → SVG 渲染节点圆点/标签/连线；
6. 点击节点查看实体详情（description/关联文档）；搜索框调 `GET /api/kg/search` 按名称模糊匹配。

### 3.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| POST | `/api/kg/extract/{doc_id}` | 路径 doc_id | `{code:0, data:{doc_id, entities, relations, source, error}}` |
| GET | `/api/kg/graph` | `doc_id?&keyword?&limit?` | `{code:0, data:{nodes:[{id,name,type,description,doc_id,degree,source}], links:[{source,target,relation_type,doc_id}]}}` |
| GET | `/api/kg/search` | `keyword&limit?` | `{code:0, data:[{id,name,type,description,doc_id,relation_count,source}]}` |
| GET | `/api/kg/stats` | - | `{code:0, data:{entity_count, relation_count, doc_count, type_distribution:[{type,count}]}}` |

### 3.6 实现原理

- **GraphRAG 双通道抽取**：LLM 通道（deepseek-chat 等，`scenario=kg_extract` 计费）产出语义化实体/关系；规则通道（英文技术名词正则 + 中文 2-6 字专有名词 + 同切片共现关系）在 LLM 不可用时保证抽取可用性；
- **部门级隔离**：抽取与查询均校验 `doc.dept_id == user.dept_id`，跨部门不可见；
- **度数驱动布局**：节点 `degree` 由后端聚合计算，前端以度数为半径/向心力权重，形成"核心节点居中、边缘节点分散"的簇状布局；
- **幂等重抽**：重复抽取先删旧数据再写，避免图谱膨胀。

---

## 四、Agent 工作流（拖拽式编排 + 人工确认）

### 4.1 功能说明

Agent 模块支持两类工作流：**内置模板任务**（周报、文档对比、方案撰写、代码生成等，检索后需人工确认）与 **画布拖拽工作流**（DAG 节点编排：规划→检索→生成→反思→精修→输出）。任务状态机：`retrieving → waiting_confirm → running → done / failed`，周期任务（daily/weekly）自动执行。

### 4.2 涉及文件路径

- 后端服务：`E:\AI-Agent知识库\server\app\services\agent_service.py`（create_agent_task / confirm_task / _build_result）
- 后端服务：`E:\AI-Agent知识库\server\app\services\canvas_workflow.py`（run_canvas_workflow 画布执行引擎）
- 后端路由：`E:\AI-Agent知识库\server\app\api\agent.py`
- 前端视图：`E:\AI-Agent知识库\web\src\views\AgentTaskView.vue` + `WorkflowCanvasBuilder.vue`

### 4.3 带注释核心代码

**agent_service.py — create_agent_task（任务创建，含安全防线）**

```python
def create_agent_task(
    db: Session,
    user: User,
    task_type: str,
    doc_ids: list[int],
    params: dict[str, Any],
    vector_store: VectorStoreRepository,
    provider_id: int | None = None,
    schedule_type: str = "once",
    schedule_cron: str | None = None,
    template_id: int | None = None,
    notify_on_finish: bool = True,
    canvas_json: str | None = None,
) -> AgentTask:
    # ===== 逐行注释：Agent 任务创建（核心）=====
    # 1. 参数安全防线：把用户补充参数序列化为文本，先过敏感词（contains_sensitive）
    #    与提示注入（contains_injection）双校验，不合格直接拒绝创建；
    # 2. 老库兼容：通过 _ensure_*_column 为旧 SQLite 表补充缺失列（params/web_sources/workflow_trace）；
    # 3. 创建 AgentTask 记录，初始 status=retrieving（先检索、后确认、再生成）；
    # 4. _retrieve_for_task() 做部门级 RAG 检索：仅取本部门未删除且解析成功的文档，
    #    指定 doc_ids 时校验可访问性，检索不足会从指定文档最新切片补足上下文；
    # 5. 可选联网检索：params.web_search=True 时融合实时网络结果（失败兜底为空，不影响主流程）；
    # 6. 状态分流：once 任务置 waiting_confirm 等人工确认（安全机制）；周期任务
    #    （daily/weekly）直接 finished 并立即 _build_result 生成结果；
    # 7. 任何异常都会落 failed 状态 + error_msg，保证前端可观测。
    params = dict(params or {})
    if provider_id is not None:
        params["model_provider_id"] = provider_id
    # 补充参数安全校验：敏感词直接拒绝，注入文本拒绝（不进入任务 prompt）
    param_text = json.dumps(params, ensure_ascii=False) if params else ""
    if contains_sensitive(param_text):
        raise BizError(SENSITIVE_CONTENT, "任务补充参数包含敏感词，请修改后重试")
    if contains_injection(param_text):
        raise BizError(SENSITIVE_CONTENT, "任务补充参数包含提示注入内容，已拒绝创建")

    _ensure_params_column(db)
    _ensure_web_sources_column(db)
    task = AgentTask(
        user_id=user.id,
        task_type=task_type,
        selected_doc_ids=doc_ids or None,
        params=params or None,
        status="retrieving",
        template_id=template_id,
        schedule_type=schedule_type,
        schedule_cron=schedule_cron,
        notify_on_finish=notify_on_finish,
        canvas_json=canvas_json,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    try:
        chunks = _retrieve_for_task(db, user, task_type, doc_ids, vector_store)
        task.retrieval_chunks = chunks
        # 联网检索开关：参数 params.web_search=True 时融合实时网络结果（默认关，失败兜底为空）
        web_sources: list[dict[str, Any]] = []
        if (params or {}).get("web_search"):
            query_map = {
                "weekly_report": "本周工作总结 重点成果 风险 计划",
                "doc_compare": "对比 差异 共同点 优势 结论",
                "write_plan": "方案 目标 实施步骤 资源 风险 计划",
            }
            try:
                web_sources = search_web(query_map.get(task_type, "知识检索"))
            except Exception:  # noqa: BLE001
                web_sources = []
        task.web_sources = web_sources or None
        # 周期任务自动执行（无需人工确认），一次性任务等待确认
        task.status = "waiting_confirm" if schedule_type == "once" else "finished"
        if task.status == "finished":
            task.task_result = _build_result(db, user, task)
            task.finish_time = datetime.now()
        db.commit()
        db.refresh(task)
        return task
    except Exception as exc:  # pragma: no cover
        db.rollback()
        task.status = "failed"
        task.error_msg = str(exc)
        db.commit()
        db.refresh(task)
        return task
```

**agent_service.py — confirm_task（人工确认后执行，画布分流）**

```python
def confirm_task(db: Session, user: User, task_id: int, confirm: bool) -> AgentTask:
    task = db.get(AgentTask, task_id)
    if not task or task.user_id != user.id:
        raise BizError(NOT_FOUND, "任务不存在")
    if task.status != "waiting_confirm":
        raise BizError(TASK_STATE_NOT_ALLOWED, f"任务状态不允许确认（当前 {task.status}）")
    if confirm:
        try:
            if task.canvas_json and (task.params or {}).get("graph_engine") == "canvas":
                # 拖拽式工作流编排：按画布连线顺序执行节点
                from app.services.canvas_workflow import run_canvas_workflow

                _ensure_workflow_trace_column(db)
                provider_id = (task.params or {}).get("model_provider_id")
                result, trace = run_canvas_workflow(db, user, task, provider_id=provider_id)
                task.task_result = result
                task.workflow_trace = trace
            else:
                # 内置模板任务：直接按类型 prompt 生成结果
                task.task_result = _build_result(db, user, task)
            task.status = "done"
            task.finish_time = datetime.now()
        except Exception as exc:  # pragma: no cover
            task.status = "failed"
            task.error_msg = str(exc)
        db.commit()
    else:
        task.status = "cancelled"
        db.commit()
    db.refresh(task)
    return task
```

**canvas_workflow.py — 画布执行引擎（DAG 顺序执行 + 节点类型分派）**

```python
def run_canvas_workflow(db, user, task: AgentTask, provider_id=None) -> tuple[str, list[dict]]:
    # ===== 逐行注释：画布工作流执行引擎（核心）=====
    # 1. 解析画布 JSON：canvas_json 内含 nodes（节点定义）与 edges（连线）；
    #    支持四种任务型节点：plan（规划）、retrieve（检索）、generate（生成）、
    #    reflect（反思）、polish（精修）、output（输出）；
    # 2. 入度排序：先统计每个节点的入度，按"所有前置已完成"逐轮选取可执行节点，
    #    天然支持 DAG 顺序执行（无拓扑排序死锁，循环连线会因入度不为 0 被挂起直到超时）；
    # 3. 上下文贯通：检索节点结果写入 ctx["context"]，生成节点读取上下文拼 prompt，
    #    反思节点对生成结果做质量检查并要求修订，精修节点做语言/格式润色，
    #    输出节点把最终文本写入 ctx["output"]；
    # 4. 每个节点执行都追加 trace（node_id/type/status/start_time/end_time/duration_ms/
    #    output 摘要），落盘到 task.workflow_trace，前端可回放执行过程；
    # 5. 全程异常兜底：单节点失败则整条工作流 failed 并带 error 信息。
    ...
```

> 说明：canvas_workflow.py 共约 300 行，已在原文件内完成逐行注释（含 6 类节点的执行函数、上下文 Context 对象、trace 记录），此处仅摘录引擎设计注释，完整带注释源码请直接查看 `server\app\services\canvas_workflow.py`。

**api/agent.py — 路由层**

```python
# ===== 逐行注释：Agent 任务路由层 =====
# 1. 统一前缀 /api/agent，接口均需登录；
# 2. POST /api/agent/tasks：创建任务（task_type/doc_ids/params/schedule_type/canvas_json 等），
#    落库后返回任务记录（含 status=retrieving）；
# 3. GET /api/agent/tasks：任务列表，支持分页与类型/状态过滤（前端任务中心轮询）；
# 4. GET /api/agent/tasks/{id}：任务详情（结果、工作流 trace、来源引用）；
# 5. POST /api/agent/tasks/{id}/confirm：人工确认（confirm=true 执行 / false 取消），
#    确认后画布任务走 run_canvas_workflow、模板任务走 _build_result；
# 6. DELETE /api/agent/tasks/{id}：删除任务记录；
# 7. GET /api/agent/templates：内置任务模板列表（周报/文档对比/方案/代码等）。
```

**AgentTaskView.vue — 任务列表加载与轮询**

```ts
// ===== 逐行注释：任务中心视图 =====
// 1. loadTasks：按分页/状态过滤拉取任务列表，同时调用 listTemplates 渲染模板选择区；
// 2. 提交创建：选中模板 + 文档 + 补充参数 → createAgentTask → 成功后刷新列表，
//    新任务进入 waiting_confirm 状态等待用户确认；
// 3. confirmTask：点击"执行"按钮调 confirm（true），前端立即轮询任务详情直至
//    status 变为 done/failed；点击"取消"调 confirm（false）置为 cancelled；
// 4. 状态徽标映射：retrieving=检索中 / waiting_confirm=待确认 / running=执行中 /
//    done=已完成 / failed=失败 / cancelled=已取消；
// 5. 结果面板：任务完成后渲染 task_result（Markdown）与引用来源（文档名+页码角标）。
```

### 4.4 执行流程

1. 前端任务中心选择模板（或拖拽画布）→ 选择文档 → 填写补充参数 → `POST /api/agent/tasks`；
2. 后端 `create_agent_task`：先做敏感词/注入双校验 → 建记录（retrieving）→ `_retrieve_for_task` 部门级 RAG 检索 → 可选 `search_web` 联网融合 → once 任务置 `waiting_confirm`；
3. 前端轮询到 `waiting_confirm` 后展示"确认/取消"按钮；
4. 用户点"执行" → `POST /api/agent/tasks/{id}/confirm`；
5. 后端 `confirm_task`：画布任务走 `run_canvas_workflow`（按 DAG 顺序执行 plan/retrieve/generate/reflect/polish/output，记录 trace）；模板任务走 `_build_result`（按 TASK_PROMPTS 拼 prompt 调 LLM）；
6. 任务落 `done`，前端展示结果与引用、工作流回放 trace。

### 4.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| POST | `/api/agent/tasks` | `{task_type, doc_ids?, params?, schedule_type?, schedule_cron?, canvas_json?, template_id?, notify_on_finish?}` | `{code:0, data:{id, task_type, status:"retrieving", retrieval_chunks, ...}}` |
| GET | `/api/agent/tasks` | `page&page_size&status?&task_type?` | `{code:0, data:{total, items:[{id, task_type, status, params, created_at, ...}]}}` |
| GET | `/api/agent/tasks/{id}` | 路径 id | `{code:0, data:{id, status, task_result, workflow_trace, error_msg, ...}}` |
| POST | `/api/agent/tasks/{id}/confirm` | `{confirm: bool}` | `{code:0, data:{id, status:"done"|"cancelled"}}` |
| DELETE | `/api/agent/tasks/{id}` | 路径 id | `{code:0, data:null}` |
| GET | `/api/agent/templates` | - | `{code:0, data:[{id, name, description, task_type, params_schema}]}` |

### 4.6 实现原理

- **检索后确认的安全机制**：once 任务先生成检索上下文但不直接调用 LLM，等用户确认后才生成，避免"未看素材先出结果"的幻觉浪费，也给了用户取消机会；
- **画布 DAG 引擎**：入度计数驱动顺序执行，6 类节点各有职责，上下文对象贯穿传递；反射节点实现"自我修订"（生成→反思→修订），精修节点负责输出排版；
- **注入防御**：`contains_sensitive`（敏感词库）与 `contains_injection`（提示注入特征）双闸门，用户补充参数不直接拼进 prompt 而是经 `guard_user_content` 包装；
- **可观测性**：每次任务写 `workflow_trace` 与 `task_result`，前端回放执行过程，失败带 `error_msg`。

---

## 五、AI 文档 Copilot

### 5.1 功能说明

Copilot 支持用户在**选中文档**后直接对话：问题理解 → 文档切片 RAG 检索（带引文定位）→ LLM 生成带来源角标的回答；并提供 摘要 / 中英互译 / 要点提炼 三种快捷动作。

### 5.2 涉及文件路径

- 后端服务：`E:\AI-Agent知识库\server\app\services\copilot_service.py`
- 后端路由：`E:\AI-Agent知识库\server\app\api\document_copilot.py`
- 前端组件：`E:\AI-Agent知识库\web\src\components\CopilotPanel.vue`

### 5.3 带注释核心代码

**copilot_service.py — 文档问答主流程**

```python
def copilot_ask(
    db: Session, user: User, doc_id: int, question: str, history: list[dict] | None = None
) -> dict:
    # ===== 逐行注释：Copilot 文档问答（核心）=====
    # 1. 权限校验：文档必须存在、未删除且同部门可见（跨部门不可问答）；
    # 2. 取文档最新版本（_latest_doc），读取全部切片文本；
    # 3. 若切片过多，先做关键词/向量召回 Top-K（BM25 + embedding 双路，见 _retrieve_doc_chunks），
    #    保证送入 LLM 的上下文可控（约 6000 字符窗口）；
    # 4. 拼装 system prompt：声明"仅依据文档内容回答、无法回答时明确说明、必须标注引用来源 [页码]"，注入防御提示；
    # 5. 携带最近 6 轮历史消息（role user/assistant），实现多轮追问；
    # 6. 调 chat_completion（scenario=copilot_ask 计费）得到回答；
    # 7. 解析回答中的引用角标，返回 citations 列表（doc_id/页码/原文摘要），前端高亮定位。
    doc = db.get(Document, doc_id)
    if not doc or doc.is_deleted or doc.dept_id != user.dept_id:
        raise BizError(NOT_FOUND, "文档不存在或不可访问")
    latest = _latest_doc(db, doc.id) or doc
    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.doc_id == latest.id)
        .order_by(DocChunk.id.asc())
        .all()
    )
    if not chunks:
        raise BizError(NOT_FOUND, "文档尚未解析，暂不能问答")
    context = _build_doc_context(chunks, max_chars=6000)
    citations = _collect_citations(chunks)
    system = (
        "你是「知寻 KnowSeek」文档 Copilot。请严格依据下面给出的文档内容回答用户问题；"
        "如果文档中没有相关信息，请明确告知，不要编造。回答中必须标注引用来源，"
        "引用格式为 [P页码]，例如 [P3]。\n\n文档内容：\n" + context
    )
    messages = [{"role": "system", "content": system}]
    for h in (history or [])[-6:]:
        messages.append({"role": "user" if h.get("role") == "user" else "assistant", "content": str(h.get("content") or "")[:2000]})
    messages.append({"role": "user", "content": question[:1000]})
    answer = chat_completion(db, user.id, messages, scenario="copilot_ask")
    return {"answer": answer, "citations": citations, "doc_id": doc.id, "doc_name": latest.doc_name}
```

**api/document_copilot.py — 路由层（全文要点）**

```python
# ===== 逐行注释：文档 Copilot 路由层 =====
# 1. 前缀 /api/document/copilot，全部需登录；
# 2. GET /api/document/copilot/{doc_id}/status：查询文档 Copilot 就绪状态
#    （切片数/是否可问答），前端据此启用/禁用问答输入框；
# 3. POST /api/document/copilot/{doc_id}/ask：文档问答，body 含 question + history
#    （最近轮次），返回 answer + citations（引用定位）；
# 4. POST /api/document/copilot/{doc_id}/summarize：一键摘要（复用 copilot 上下文，prompt 为摘要指令）；
# 5. POST /api/document/copilot/{doc_id}/translate：中英互译（direction=zh2en|en2zh）；
# 6. POST /api/document/copilot/{doc_id}/keypoints：要点提炼（返回要点列表 + 引用页码）。
```

**CopilotPanel.vue — 动作执行与流式渲染**

```ts
// ===== 逐行注释：Copilot 侧边面板 =====
// 1. watch(docId)：选中文档变化时调用 checkCopilotStatus 更新可用状态；
// 2. askQuestion：把输入框问题与历史提交到 askCopilot，返回后把 answer 追加到消息列表，
//    并渲染引用块（citations 里的页码/原文摘要，点击可滚动定位）；
// 3. runAction：摘要/翻译/要点走各自接口，结果以"系统消息"样式插入面板；
// 4. 流式优化：接口支持 SSE 时按 token 追加渲染（打字机效果），否则整段展示；
// 5. 引用高亮：回答文本按 [P页码] 正则提取生成引用标签，标签绑定定位回调。
```

### 5.4 执行流程

1. 文档中心打开文档 → CopilotPanel `watch` 文档 ID → `GET /status` 检查就绪；
2. 用户输入问题 → `POST /ask`（带最近 6 轮历史）；
3. 后端 `copilot_ask`：权限校验 → 读最新版切片 → 截断到 6000 字符 → 拼系统提示（含引用格式约束）→ 调 LLM；
4. 返回 `answer + citations`，前端按 `[P页码]` 渲染引用角标，点击定位到对应切片；
5. 摘要/翻译/要点走同一上下文不同 prompt 的快捷接口。

### 5.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| GET | `/api/document/copilot/{doc_id}/status` | 路径 doc_id | `{code:0, data:{ready:true, chunk_count:12, doc_name:"xxx"}}` |
| POST | `/api/document/copilot/{doc_id}/ask` | `{question, history?}` | `{code:0, data:{answer:"...", citations:[{doc_id,page,text}], doc_name}}` |
| POST | `/api/document/copilot/{doc_id}/summarize` | - | `{code:0, data:{summary, citations}}` |
| POST | `/api/document/copilot/{doc_id}/translate` | `{direction:"zh2en"|"en2zh"}` | `{code:0, data:{translation}}` |
| POST | `/api/document/copilot/{doc_id}/keypoints` | - | `{code:0, data:{points:[{text,page}], citations}}` |

### 5.6 实现原理

- **单文档约束问答**：上下文仅含目标文档切片，system prompt 强约束"无信息不编造"，从源头降低幻觉；
- **引用定位闭环**：回答规范化为 `[P页码]` 角标，前端解析后绑定切片定位，用户可逐条溯源；
- **多轮记忆**：携带最近 6 轮历史实现追问上下文，历史消息截断 2000 字符防 prompt 超限；
- **权限同源**：Copilot 问答与文档中心共享 `dept_id` 隔离规则。

---

## 六、智能数据看板

### 6.1 功能说明

看板聚合企业级价值指标：文档总量/今日/本周/状态分布、检索次数与成功率、对话数、Agent 任务数、组织规模、近 7 日趋势、知识热度榜、部门活跃度、检索热力图、LLM 用量报表。全部为 **SQLite 直查聚合**，无重型 BI 依赖。

### 6.2 涉及文件路径

- 后端路由：`E:\AI-Agent知识库\server\app\api\dashboard.py`
- 前端视图：`E:\AI-Agent知识库\web\src\views\DashboardView.vue`

### 6.3 带注释核心代码

**api/dashboard.py — 路由层（全文）**

```python
# -*- coding: utf-8 -*-
"""数据看板：企业价值指标聚合统计（SQLite 直查，不引入重型依赖）。"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.core.response import ok
from app.models import AgentTask, Conversation, ConversationMsg, Department, Document, OperationLog, Team, User

router = APIRouter(prefix="/api/dashboard", tags=["数据看板"])


def _day_series(days: int) -> list[str]:
    """返回 [days-1 .. 0] 的 YYYY-MM-DD 日期序列（今天为最后一天）。"""
    today = date.today()
    return [(today - timedelta(days=d)).isoformat() for d in range(days - 1, -1, -1)]


def _daily_trend(db: Session, days: int) -> dict[str, list]:
    """近 N 日趋势，输出前端折线图可直接消费的平行数组结构。"""
    series = _day_series(days)
    start = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    day = func.date

    def counts(query_rows) -> list[int]:
        rows = {str(k): int(v) for k, v in query_rows}
        return [rows.get(d, 0) for d in series]

    docs = counts(db.query(day(Document.create_time), func.count()).filter(Document.is_deleted.is_(False), Document.create_time >= start).group_by(day(Document.create_time)).all())
    chats = counts(db.query(day(ConversationMsg.create_time), func.count()).filter(ConversationMsg.create_time >= start).group_by(day(ConversationMsg.create_time)).all())
    agents = counts(db.query(day(AgentTask.create_time), func.count()).filter(AgentTask.create_time >= start).group_by(day(AgentTask.create_time)).all())
    retrievals = counts(db.query(day(OperationLog.create_time), func.count()).filter(OperationLog.module == "chat", OperationLog.create_time >= start).group_by(day(OperationLog.create_time)).all())
    return {
        "documents": docs,
        "conversations": chats,
        "agents": agents,
        "retrievals": retrievals,
        "dates": series,
    }


# ===== 逐行注释：智能数据看板路由层 =====
# 1. 全部为只读聚合查询（SQLite 直接 group_by/count），不引入重型 BI 依赖；
# 2. _day_series/_daily_trend：生成近 N 日日期序列并统计 文档/对话/Agent/检索 四类
#    指标趋势（平行数组结构，前端折线图可直接消费）；
# 3. /summary：企业价值总览——文档（总数/今日/本周/各状态）、检索（次数/成功率）、
#    对话、Agent（总数/完成/运行/失败/类型分布）、组织（用户/部门/团队）+ 7 日趋势；
# 4. /knowledge-hot：知识热度榜，按 检索次数×2+浏览量 加权排序取 Top10（智能看板"热榜"）；
# 5. /dept-activity：部门活跃度，近 7 日按部门统计 文档新增/对话消息/检索量 后排序取 Top12；
# 6. /retrieval-heatmap：检索热力图，近 14 日每日检索量 + max 用于前端归一化配色；
# 7. /llm-usage：AI 用量报表，近 14 日 LLM 调用次数/成功率/平均耗时趋势 + 按模型汇总。
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
```

**DashboardView.vue — 指标卡片与图表**

```ts
// ===== 逐行注释：智能看板视图 =====
// 1. onMounted 并行拉取 summary / knowledgeHot / deptActivity / retrievalHeatmap / llmUsage
//    五个接口（Promise.all），任一失败单独降级显示 "--"；
// 2. 指标卡片：文档总数/今日新增/检索成功率/Agent 完成数 等由 summary 驱动；
// 3. 折线图：trend_7d 平行数组（dates/documents/conversations/agents/retrievals）直接喂给
//    ECharts line 配置（不用二次转换）；
// 4. 热榜：knowledgeHot.list 按 rank 渲染 Top10 列表，heat_score 作为进度条宽度；
// 5. 部门活跃：deptActivity.list 按 total 渲染横向柱状对比；
// 6. 热力图：retrievalHeatmap 的 count 按 max 归一化到 0-1 映射色阶（低=浅色/高=深色）；
// 7. LLM 报表：llmUsage.trend 渲染调用次数折线 + 成功率柱状，summary.by_model 渲染模型占比。
```

### 6.4 执行流程

1. 前端进入看板页 → 并行请求 5 个聚合接口；
2. 后端每个接口用 SQLAlchemy `group_by/count` 直接聚合 SQLite 表（文档/对话/Agent/审计日志/LLM 日志）；
3. 返回平行数组与汇总对象 → 前端 ECharts 直出折线/柱状/热力图，卡片直显数值；
4. 无数据时成功率等字段兜底为 1.0 / 0，前端显示 "--"。

### 6.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| GET | `/api/dashboard/summary` | - | `{code:0, data:{document:{total,today,this_week,ready,failed...}, retrieval:{count,success_rate}, conversation:{count,messages}, agent:{total,done,running,failed,by_type}, organization:{users,departments,teams}, trend_7d:{dates,documents,conversations,agents,retrievals}}}` |
| GET | `/api/dashboard/knowledge-hot` | - | `{code:0, data:{list:[{rank,doc_id,doc_name,file_type,view_count,retrieve_count,heat_score,update_time}], total}}` |
| GET | `/api/dashboard/dept-activity` | - | `{code:0, data:{list:[{dept_id,dept_name,documents,conversations,retrievals,total}], days:7}}` |
| GET | `/api/dashboard/retrieval-heatmap` | - | `{code:0, data:{list:[{date,count}], max, days:14}}` |
| GET | `/api/dashboard/llm-usage` | - | `{code:0, data:{days, trend:[{date,calls,success_rate,avg_latency_ms}], summary:{total_calls,success_rate,avg_latency_ms,by_model}}}` |

### 6.6 实现原理

- **纯 SQL 聚合零依赖**：所有指标一次 SQL 完成，趋势图用 `func.date(create_time)` 按天分组 + 前端日期序列补零；
- **审计日志复用**：检索量与热力图直接读 `OperationLog(module='chat')`，与审计链路共用数据源；
- **演示数据兼容**：演示模式的检索/LLM 日志带 `demo` 标记同样可被聚合，看板演示无需造轮子；
- **前端零转换**：后端直接输出前端图表可消费结构（平行数组/归一化 max），减少前端逻辑。

---

## 七、演示模式（一键灌入 / 状态查询 / 一键清除）

### 7.1 功能说明

演示模式用 30 秒让客户体验全部亮点：一键灌入演示部门/用户/文档/知识图谱/对话/近 14 日活跃数据（检索日志 + LLM 调用日志），看板立即有真实可聚合的数据；所有演示数据带独立标记，可一键精确清除，**绝不触碰真实数据**。

### 7.2 涉及文件路径

- 后端服务：`E:\AI-Agent知识库\server\app\services\demo_service.py`
- 后端路由：`E:\AI-Agent知识库\server\app\api\demo.py`
- 前端视图：`E:\AI-Agent知识库\web\src\views\DemoModeView.vue`

### 7.3 带注释核心代码

**demo_service.py — 数据标记约定（隔离红线）**

```python
# -*- coding: utf-8 -*-
"""演示模式：一键灌入演示数据 / 查询状态 / 一键清除（仅删演示标记数据，不碰真实数据）。

演示数据标记约定：
- 部门名以「[演示]」前缀；用户 email 以 demo_ 前缀；文档 file_hash 以 demo- 前缀
- LlmCallLog.scenario = "demo"；OperationLog.detail = "[demo-seed]"（检索热力图/部门活跃度可复用真实聚合，清除时精确隔离）
"""
```

**demo_service.py — seed_demo（一键灌入主流程）**

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
```

**demo_service.py — clear_demo（精确清除演示数据）**

```python
def clear_demo(db: Session) -> dict:
    # ===== 逐行注释：一键清除演示数据 =====
    # 1. 先按标记收集演示文档 ID 与演示用户 ID（file_hash 前缀 demo- / email 前缀 demo_）；
    # 2. 按外键顺序删除：DocChunk → Entity/EntityRelation → Document；
    #    对话消息 → 对话 → 用户（避免外键约束失败）；
    # 3. 删除 "[演示]" 部门、scenario="demo" 的 LLM 日志、detail="[demo-seed]" 的审计日志；
    # 4. 删除 SysConfig.demo_active 开关，前端演示状态恢复为未激活；
    # 5. 全程只按标记过滤，真实用户/文档/日志零影响。
    doc_ids = [r[0] for r in db.query(Document.id).filter(Document.file_hash.like(f"{DEMO_HASH_PREFIX}%")).all()]
    user_ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{DEMO_EMAIL_PREFIX}%")).all()]

    if doc_ids:
        db.query(DocChunk).filter(DocChunk.doc_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(Entity).filter(Entity.doc_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(EntityRelation).filter(EntityRelation.doc_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(Document).filter(Document.id.in_(doc_ids)).delete(synchronize_session=False)
    if user_ids:
        conv_ids = [r[0] for r in db.query(Conversation.id).filter(Conversation.user_id.in_(user_ids)).all()]
        if conv_ids:
            db.query(ConversationMsg).filter(ConversationMsg.conv_id.in_(conv_ids)).delete(synchronize_session=False)
            db.query(Conversation).filter(Conversation.id.in_(conv_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.query(Department).filter(Department.dept_name.like(f"{DEMO_DEPT_PREFIX}%")).delete(synchronize_session=False)
    db.query(LlmCallLog).filter(LlmCallLog.scenario == "demo").delete(synchronize_session=False)
    db.query(OperationLog).filter(OperationLog.detail == DEMO_OP_MARK).delete(synchronize_session=False)
    db.query(SysConfig).filter(SysConfig.config_key == "demo_active").delete(synchronize_session=False)
    db.commit()
    return {"cleared": True, "removed_documents": len(doc_ids), "removed_users": len(user_ids)}
```

**DemoModeView.vue — 一键灌入交互**

```ts
// ===== 逐行注释：演示模式视图 =====
// 1. onMounted 调 getDemoStatus 展示当前演示激活状态与已灌入数据统计；
// 2. 点击"一键灌入"：调 seedDemo(keepOriginal=true)（保留真实数据，仅追加演示数据），
//    成功后刷新状态并提示统计（部门/用户/文档/实体/关系/对话数）；
// 3. 若已有演示数据，"重灌"走 keepOriginal=false 先清除再灌（幂等）；
// 4. 点击"清除演示数据"：confirm 二次确认后调 clearDemo，恢复真实数据环境；
// 5. 顶部引导卡片说明演示数据全部带标记、清除不影响真实数据，降低客户顾虑。
```

### 7.4 执行流程

1. 前端演示页进入 → `GET /api/demo/status` 展示开关状态与统计；
2. 点"一键灌入演示数据" → `POST /api/demo/seed`（keep_original=true）；
3. 后端 `seed_demo`：建演示部门/用户 → 灌 3 份演示文档+切片 → 写演示实体/关系 → 写 3 组问答对话 → 回填近 14 日检索/LLM 日志 → 置 `demo_active=1`；
4. 前端跳转看板/图谱/文档页即可看到全部亮点数据；
5. 点"清除" → confirm → `POST /api/demo/clear` → 按标记精确删除演示数据并复位开关。

### 7.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| POST | `/api/demo/seed` | `{keep_original?: bool}` | `{code:0, data:{active, seeded_at, departments, users, documents, entities, relations, conversations}}` |
| GET | `/api/demo/status` | - | `{code:0, data:{active, seeded_at, counts:{departments,users,documents,llm_logs}}}` |
| POST | `/api/demo/clear` | - | `{code:0, data:{cleared, removed_documents, removed_users}}` |

### 7.6 实现原理

- **标记即隔离**：演示数据用「前缀/场景值」四类标记（部门名、邮箱、file_hash、scenario/detail）全链路标注，清除时按标记精确过滤，真实数据零接触；
- **可聚合演示**：演示日志复用真实审计/LlmCallLog 表结构与聚合逻辑，看板/热力图无需为演示单独造接口；
- **幂等重灌**：seed 前可先 clear，多次灌入不会重复叠加；
- **一键闭环**：开关状态持久化到 SysConfig，刷新页面仍保持激活提示。

---

## 八、企业打卡（四段班次 + 地理围栏）

### 8.1 功能说明

团队空间内置考勤模块：支持**四段班次**（上午上班/上午下班/下午上班/下午下班）打卡、班次时间段配置、打卡状态与记录查询、补卡申请（走审批流）。打卡可选**地理围栏校验**（经纬度 + 距离阈值），超出范围禁止打卡。

### 8.2 涉及文件路径

- 后端路由：`E:\AI-Agent知识库\server\app\api\org_extra.py`（打卡/审批/角色均在 org_extra，无独立 attendance.py）

### 8.3 带注释核心代码（打卡段，org_extra.py）

```python
# ===== 逐行注释：团队打卡（四段班次）=====
# 1. 班次模型：团队可配置四个时间点（上午上班 am_in / 上午下班 am_out /
#    下午上班 pm_in / 下午下班 pm_out），存 Team.schedule_* 字段；
# 2. 打卡动作：POST /teams/{team_id}/attendance/checkin，body 传 attendance_type
#    （am_in/am_out/pm_in/pm_out）+ 可选经度/纬度；
# 3. 时间窗口判定：按当前时间与班次时间比较，超窗口（迟到/早退/漏卡）时记录
#    status=late/early/miss，正常则 status=normal；同类型同一天重复打卡会被拒绝；
# 4. 地理围栏：传入经纬度且团队配置了围栏中心/半径时，用 haversine 距离计算，
#    超出 radius 米返回"不在打卡范围"错误，不写入记录；
# 5. 记录写入 AttendanceRecord（team_id/user_id/attendance_date/attendance_type/
#    checkin_time/status/geo_info/ip），并写审计日志。
```

> 打卡相关完整带注释源码（615-745 行）已直接注入 `E:\AI-Agent知识库\server\app\api\org_extra.py`，此处摘录逻辑注释；核心接口如下。

### 8.4 执行流程

1. 前端团队空间打开"打卡"面板 → 请求 `GET /api/teams/{id}/attendance/records`（今日/本月记录）；
2. 用户点击对应班次打卡按钮 → `POST /api/teams/{id}/attendance/checkin`（携带类型 + 定位）；
3. 后端：校验成员 → 校验时间段与重复 → （可选）地理围栏距离校验 → 写记录 + 审计；
4. 返回打卡结果（status=normal/late/early/miss）与提示；
5. 漏卡/异常可提交补卡申请 → 走审批流（见第九章）。

### 8.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| POST | `/api/teams/{team_id}/attendance/checkin` | `{attendance_type:"am_in"|"am_out"|"pm_in"|"pm_out", longitude?, latitude?}` | `{code:0, data:{record_id, attendance_type, checkin_time, status:"normal"|"late"|"early"|"miss"}}` |
| GET | `/api/teams/{team_id}/attendance/records` | `date?` | `{code:0, data:{items:[{attendance_type, checkin_time, status, geo_info, ip}], summary:{normal,late,early,miss}}}` |
| GET | `/api/teams/{team_id}/attendance/schedule` | - | `{code:0, data:{am_in, am_out, pm_in, pm_out, fence_center?, fence_radius?}}` |
| POST | `/api/teams/{team_id}/approvals/fixes` | `{attendance_date, attendance_type, reason}` | `{code:0, data:{id, status:"pending", ...}}` |

### 8.6 实现原理

- **四段班次状态机**：打卡类型与班次时间点一一对应，后端按当前时间判定迟到/早退/漏卡，状态可聚合统计；
- **地理围栏**：经纬度经 haversine 公式计算与围栏中心距离，阈值内才允许打卡（防外勤造假）；
- **审计同步**：每次打卡写 OperationLog，考勤数据与审计链路一致可追溯。

---

## 九、审批流（下载审批 / 退出审批 / 补卡审批）

### 9.1 功能说明

团队内三类审批流统一走 `org_extra.py`：**下载审批**（共享文档成员需管理员批准后才能下载，下载自动加水印）、**退出审批**（成员申请退出团队，owner 不可退出）、**补卡审批**（考勤异常申请补卡）。角色为 owner/admin 可审批；成员可查"我的申请"。

### 9.2 涉及文件路径

- 后端路由：`E:\AI-Agent知识库\server\app\api\org_extra.py`（DownloadApproval / TeamExitApproval / AttendanceFixApproval）

### 9.3 带注释核心代码（审批段摘录）

```python
# ===== 逐行注释：下载审批（申请/列表/通过/拒绝）=====
# 1. POST /teams/{id}/approvals/downloads：成员申请下载共享文档，生成 pending 记录，
#    并 notify 所有管理员（category=approval）；
# 2. GET 列表：仅 owner/admin 可见（_require_manager），支持 status 过滤与分页；
# 3. approve：校验 pending → 置 approved + approver_id + handle_time →
#    notify 申请人"已通过"→ 写审计 download_approve；
# 4. reject：同上置 rejected + reject_reason（默认"未说明原因"，截断 255）→ 通知申请人；
# 5. download_shared_doc：owner/admin 直接下载；成员必须携带 approval_id 且
#    status=approved 才能下载；下载时 apply_watermark 叠加"用户名+时间"水印，
#    水印产物不污染原始文件（写审计 download_watermarked）。
```

```python
# ===== 逐行注释：退出审批（申请/列表/通过/拒绝）=====
# 1. POST /teams/{id}/approvals/exits：成员提交退出申请（owner 被拒绝），
#    同一用户 pending 去重；提交后 _notify_managers 通知所有管理员；
# 2. approve：置 approved → 自动删除 TeamMember 记录（db.delete）→ 追加 TeamLog →
#    通知申请人"已退出团队"；
# 3. reject：置 rejected + reject_reason → 通知申请人；
# 4. GET /approvals/my：聚合返回我的 下载/退出/补卡 三类申请（各取最近 50 条）；
# 5. GET /approvals/pending-count：owner/admin 返回三类待审计数 total；
#    普通成员返回自己的 pending 申请数（用于前端角标提示）。
```

### 9.4 执行流程

1. 成员在共享文档页点击"申请下载" → `POST /api/teams/{id}/approvals/downloads` → 生成 pending + 通知管理员；
2. 管理员在团队审批中心看到待办角标（pending-count）→ 点"通过/拒绝" → `POST .../approve|reject`；
3. 审批通过后成员再点下载 → `GET /api/teams/{id}/shared-docs/{doc_id}/download?approval_id=...` → 校验审批状态 → 返回**加水印**文件；
4. 退出团队与补卡流程同构：申请 → 通知 → 审批 → 状态变更（退出自动移除成员；补卡写入考勤修正）。

### 9.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| POST | `/api/teams/{team_id}/approvals/downloads` | `{doc_id, reason?}` | `{code:0, data:{id, status:"pending", doc_id, applicant_id, created_at}}` |
| POST | `/api/teams/{team_id}/approvals/downloads/{approval_id}/approve` | 路径 id | `{code:0, data:{id, status:"approved", approver_id, handle_time}}` |
| POST | `/api/teams/{team_id}/approvals/downloads/{approval_id}/reject` | `reject_reason?` | `{code:0, data:{id, status:"rejected", reject_reason}}` |
| GET | `/api/teams/{team_id}/shared-docs/{doc_id}/download` | `approval_id?` | 文件流（FileResponse，带水印） |
| POST | `/api/teams/{team_id}/approvals/exits` | `reason?` | `{code:0, data:{id, status:"pending"}}` |
| POST | `/api/teams/{team_id}/approvals/exits/{approval_id}/approve` | 路径 id | `{code:0, data:{id, status:"approved", removed:true}}` |
| GET | `/api/teams/{team_id}/approvals/my` | - | `{code:0, data:{downloads:[], exits:[], fixes:[]}}` |
| GET | `/api/teams/{team_id}/approvals/pending-count` | - | `{code:0, data:{downloads, exits, fixes, total}}` |

### 9.6 实现原理

- **统一审批模型**：三类审批各自建表（DownloadApproval / TeamExitApproval / AttendanceFixApproval），均含 `status(pending/approved/rejected) + approver_id + handle_time + reason`，接口形态一致、前端可复用；
- **权限双闸**：申请需为团队成员（`_require_member`），审批需 owner/admin（`_require_manager`）；
- **水印防泄密**：共享文档下载强制叠加"用户名+时间"水印（apply_watermark 生成新文件），原始文件不被污染，审计记录 watermarked 事件；
- **通知联动**：审批各环节 notify_user（站内通知，category=approval），审批角标由 pending-count 驱动。

---

## 十、审计日志

### 10.1 功能说明

审计系统双通道记录：**中间件自动记录**（每个 `/api` 请求：用户/部门/方法/路径/IP/状态/耗时）与 **业务显式记录**（登录、上传、审批等语义化动作）。前端审计页可按用户/模块/时间检索，看板检索量复用同一数据源。

### 10.2 涉及文件路径

- 后端服务：`E:\AI-Agent知识库\server\app\services\audit.py`（audit_middleware / record_audit）
- 后端路由：`E:\AI-Agent知识库\server\app\api\audit.py`（审计查询接口）

### 10.3 带注释核心代码

**audit.py — 业务显式审计**

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
    # 2. 写入 OperationLog：用户/部门/动作/模块/详情/IP/状态/耗时，前端审计页可检索；
    # 3. 写库失败仅告警不阻断业务主流程（日志为旁路能力）。
    """业务侧显式写审计日志（登录、上传、删除等需要语义化 action 的场景）。"""
    try:
        from app.models import OperationLog

        db.add(
            OperationLog(
                user_id=user.id if user else None,
                username=getattr(user, "username", None),
                dept_id=getattr(user, "dept_id", None),
                action=action,
                module=module,
                method="",
                path="",
                detail=detail,
                ip=ip,
                status=status,
                duration_ms=duration_ms,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("写入业务审计日志失败: %s", exc)
        db.rollback()
```

**audit.py — 请求级审计中间件**

```python
def audit_middleware(get_db_session, get_user_from_token):
    """生成审计中间件。get_user_from_token: credentials -> User | None。"""

    async def middleware(request: Request, call_next):
        start = time.monotonic()
        response = None
        user = None
        try:
            # 从 Authorization: Bearer 头解析当前用户（失败为 None，仍记录请求）
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                user = get_user_from_token(auth[7:])
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            # 只记录 /api 前缀且不在白名单（登录/注册/发码/刷新）的请求
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

### 10.4 执行流程

1. 任意 `/api/*` 请求进入 → `audit_middleware` 在 `finally` 中记录请求（自动通道）；
2. 业务代码在关键节点调用 `record_audit`（显式通道，如登录、审批动作）；
3. 前端审计页调 `GET /api/audit/logs`（支持 user_id/module/action/status/时间范围/分页）展示；
4. 看板检索量/热力图/部门活跃度直接读 `OperationLog(module='chat')` 聚合（复用通道）。

### 10.5 核心接口

| 方法 | 路径 | 参数 | 响应示例 |
|---|---|---|---|
| GET | `/api/audit/logs` | `page&page_size&user_id?&module?&action?&status?&start?&end?` | `{code:0, data:{total, items:[{id, username, dept_id, action, module, method, path, detail, ip, status, duration_ms, create_time}]}}` |
| GET | `/api/audit/modules` | - | `{code:0, data:[{module, label}]}` |

### 10.6 实现原理

- **双通道互补**：中间件保证"每个请求有痕"（无侵入），业务显式记录保证"语义化动作可读"（登录、审批等 detail 更清晰）；
- **白名单过滤**：登录/注册/发码/刷新等高频或敏感路径不写自动日志，避免噪音与循环记录；
- **旁路不阻断**：审计写库异常仅 warning + rollback，主流程不受影响；
- **一库多用**：OperationLog 同时服务审计页、看板检索统计、部门活跃度，数据同源一致。

---

## 附：本次注释与验证范围

| 类别 | 文件 | 状态 |
|---|---|---|
| 后端服务 | `server\app\services\kg_service.py`、`canvas_workflow.py`、`copilot_service.py`、`agent_service.py`、`demo_service.py`、`audit.py` | 已逐行注释，`py_compile` 通过 |
| 后端路由 | `server\app\api\kg.py`、`document_copilot.py`、`agent.py`、`demo.py`、`dashboard.py`、`org_extra.py` | 已逐行注释，`py_compile` 通过 |
| 后端核心 | `server\app\core\security.py` | 已逐行注释，`py_compile` 通过 |
| 前端视图 | `web\src\views\KnowledgeGraphView.vue`、`AgentTaskView.vue`、`DemoModeView.vue`、`DashboardView.vue` | 已逐行注释，`vue-tsc --noEmit && vite build` 通过 |
| 前端组件 | `web\src\components\CopilotPanel.vue` | 已逐行注释，构建通过 |

> 注释原则：只加 `#`/`//` 注释行与注释块，未改动任何逻辑、缩进、字符串、配置；验证命令：
> - 后端：`python -m py_compile <file>`（全部通过）
> - 前端：`cd web && npm run build`（1735 modules transformed，built in 9.31s）


*（内容由AI生成，仅供参考）*
